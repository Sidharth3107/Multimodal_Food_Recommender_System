from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from nutriguard.html_report import save_html_report
from nutriguard.models import AnalysisRequest, UserProfile
from nutriguard.service import FoodAnalysisService

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "webapp" / "static"
GENERATED_DIR = ROOT / "webapp" / "generated"
UPLOAD_DIR = GENERATED_DIR / "uploads"
SHOWCASE_DIR = ROOT / "examples" / "showcase_output"
CASES_PATH = ROOT / "examples" / "demo_cases.json"


def _resolve_default_dataset() -> Path:
    env_path = os.environ.get("NUTRIGUARD_DATASET")
    if env_path:
        return Path(env_path)
    candidates = [
        ROOT / "data" / "deploy_openfoodfacts.tsv",
        ROOT / "data" / "raw" / "en.openfoodfacts.org.products.tsv",
        ROOT / "tests" / "data" / "sample_openfoodfacts.tsv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def _resolve_default_checkpoint() -> Path:
    env_path = os.environ.get("NUTRIGUARD_CHECKPOINT")
    if env_path:
        return Path(env_path)
    return ROOT / "Food_Vision_Model" / "checkpoint-2400"


DEFAULT_DATASET = _resolve_default_dataset()
DEFAULT_CHECKPOINT = _resolve_default_checkpoint()


class NutriguardWebState:
    def __init__(self) -> None:
        self._services: dict[tuple[str, str], FoodAnalysisService] = {}

    def get_service(self, dataset: str | None = None, checkpoint: str | None = None) -> FoodAnalysisService:
        dataset_path = str(Path(dataset) if dataset else DEFAULT_DATASET)
        checkpoint_path = str(Path(checkpoint) if checkpoint else DEFAULT_CHECKPOINT)
        key = (dataset_path, checkpoint_path)
        if key not in self._services:
            self._services[key] = FoodAnalysisService(dataset_path=dataset_path, vision_checkpoint=checkpoint_path)
        return self._services[key]


class NutriguardRequestHandler(BaseHTTPRequestHandler):
    server_version = "NutriguardHTTP/1.0"

    @property
    def state(self) -> NutriguardWebState:
        return self.server.state  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            self._send_json({"ok": True, "service": "nutriguard-web"})
            return
        if path == "/api/showcase":
            self._send_json(self._load_showcase_payload())
            return
        self._serve_file(path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/analyze":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return

        try:
            payload = self._read_json_body()
            response = self._run_analysis(payload)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json(response)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _read_json_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _run_analysis(self, payload: dict[str, object]) -> dict[str, object]:
        profile_data = payload.get("profile")
        if not isinstance(profile_data, dict):
            raise ValueError("A 'profile' object is required.")
        profile = UserProfile.from_dict(profile_data)

        image_path = payload.get("image_path")
        image_b64 = payload.get("image_b64")
        image_name = payload.get("image_name")
        if image_b64:
            image_path = str(self._persist_uploaded_image(str(image_b64), str(image_name or "upload.png")))

        dataset = payload.get("dataset")
        checkpoint = payload.get("checkpoint")
        service = self.state.get_service(str(dataset) if dataset else None, str(checkpoint) if checkpoint else None)
        result = service.analyze(
            AnalysisRequest(
                profile=profile,
                image_path=str(image_path) if image_path else None,
                ingredients_text=str(payload.get("ingredients_text")) if payload.get("ingredients_text") else None,
                barcode=str(payload.get("barcode")) if payload.get("barcode") else None,
                top_k_predictions=int(payload.get("top_k", 5)),
            )
        )

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        html_name = f"analysis-{stamp}.html"
        json_name = f"analysis-{stamp}.json"
        html_path = GENERATED_DIR / html_name
        json_path = GENERATED_DIR / json_name
        save_html_report(result, html_path, title=result.product_name)
        json_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

        return {
            "result": result.to_dict(),
            "report_href": f"/generated/{html_name}",
            "json_href": f"/generated/{json_name}",
        }

    def _persist_uploaded_image(self, image_b64: str, image_name: str) -> Path:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        safe_suffix = Path(image_name).suffix.lower() or ".png"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        output = UPLOAD_DIR / f"upload-{stamp}{safe_suffix}"
        output.write_bytes(base64.b64decode(image_b64))
        return output

    def _load_showcase_payload(self) -> dict[str, object]:
        cases = []
        title_lookup: dict[str, str] = {}
        if CASES_PATH.exists():
            for item in json.loads(CASES_PATH.read_text(encoding="utf-8-sig")):
                title_lookup[str(item["id"])] = str(item.get("title", item["id"]))
        for json_file in sorted(SHOWCASE_DIR.glob("*.json")):
            case_id = json_file.stem
            payload = json.loads(json_file.read_text(encoding="utf-8"))
            cases.append(
                {
                    "id": case_id,
                    "title": title_lookup.get(case_id, case_id.replace("_", " ").title()),
                    "summary": payload.get("summary", ""),
                    "risk_score": payload.get("risk_score", 0),
                    "status": payload.get("status", "safe"),
                    "href": f"/showcase/{case_id}.html",
                }
            )
        return {"cases": cases}

    def _serve_file(self, request_path: str) -> None:
        path = request_path or "/"
        if path == "/":
            target = STATIC_DIR / "index.html"
        elif path.startswith("/generated/"):
            target = GENERATED_DIR / path.removeprefix("/generated/")
        elif path.startswith("/showcase/"):
            target = SHOWCASE_DIR / path.removeprefix("/showcase/")
        else:
            target = STATIC_DIR / path.lstrip("/")
        target = target.resolve()

        allowed_roots = [STATIC_DIR.resolve(), GENERATED_DIR.resolve(), SHOWCASE_DIR.resolve()]
        if not any(str(target).startswith(str(root)) for root in allowed_roots):
            self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
            return
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        content_type, _ = mimetypes.guess_type(str(target))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(target.read_bytes())

    def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class NutriguardHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], state: NutriguardWebState) -> None:
        super().__init__(server_address, NutriguardRequestHandler)
        self.state = state



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Nutriguard local website.")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", default=int(os.environ.get("PORT", "8010")), type=int)
    return parser



def main() -> int:
    args = build_parser().parse_args()
    os.makedirs(GENERATED_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    server = NutriguardHTTPServer((args.host, args.port), NutriguardWebState())
    print(f"Nutriguard web app running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


