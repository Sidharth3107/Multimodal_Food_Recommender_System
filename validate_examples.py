from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from nutriguard.models import AnalysisRequest, UserProfile
from nutriguard.service import FoodAnalysisService

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "examples" / "validation_output"
DEMO_CASES_PATH = ROOT / "examples" / "demo_cases.json"
SAMPLE_DATASET = ROOT / "tests" / "data" / "sample_openfoodfacts.tsv"


def _service_cache() -> dict[str, FoodAnalysisService]:
    return {}


def _get_service(cache: dict[str, FoodAnalysisService], dataset_path: str | None) -> FoodAnalysisService:
    resolved = str((ROOT / dataset_path).resolve()) if dataset_path else str(SAMPLE_DATASET.resolve())
    if resolved not in cache:
        cache[resolved] = FoodAnalysisService(dataset_path=resolved)
    return cache[resolved]


def _load_profile(item: dict[str, object]) -> UserProfile:
    profile = item.get("profile")
    if isinstance(profile, dict):
        return UserProfile.from_dict(profile)
    profile_path = item.get("profile_path")
    if isinstance(profile_path, str):
        payload = json.loads((ROOT / profile_path).read_text(encoding="utf-8-sig"))
        return UserProfile.from_dict(payload)
    return UserProfile()


def _make_salad_image(path: Path) -> None:
    image = Image.new("RGB", (320, 320), (238, 242, 231))
    draw = ImageDraw.Draw(image)
    draw.ellipse((30, 30, 290, 290), fill=(82, 137, 79))
    draw.ellipse((86, 72, 136, 122), fill=(200, 38, 48))
    draw.ellipse((182, 96, 232, 146), fill=(232, 206, 78))
    draw.ellipse((112, 186, 162, 236), fill=(246, 245, 236))
    image.save(path)


def _make_unknown_scene(path: Path) -> None:
    image = Image.new("RGB", (320, 320), (120, 148, 182))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 220, 320, 320), fill=(84, 96, 110))
    draw.rectangle((30, 40, 140, 170), fill=(164, 180, 196))
    draw.polygon([(180, 80), (290, 60), (250, 180)], fill=(98, 110, 126))
    draw.line((0, 220, 320, 220), fill=(230, 232, 235), width=6)
    image.save(path)


def _summarize(case_id: str, result) -> dict[str, object]:
    prediction = result.image_prediction
    return {
        "id": case_id,
        "product_name": result.product_name,
        "status": result.status,
        "safe_to_eat": result.safe_to_eat,
        "risk_score": result.risk_score,
        "probable_allergens": result.probable_allergens,
        "warnings": result.warnings,
        "image_label": prediction.label if prediction else None,
        "image_confidence": prediction.confidence if prediction else None,
        "image_source": prediction.source if prediction else None,
        "summary": result.summary,
    }


def _write_outputs(rows: list[dict[str, object]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "validation_matrix.json"
    md_path = OUTPUT_DIR / "validation_matrix.md"
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    lines = [
        "# Validation Matrix",
        "",
        "| Case | Product | Status | Risk | Image label | Source |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['product_name']} | {row['status']} | {row['risk_score']:.1f} | {row['image_label'] or '-'} | {row['image_source'] or '-'} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    cache = _service_cache()
    results: list[dict[str, object]] = []

    for item in json.loads(DEMO_CASES_PATH.read_text(encoding="utf-8-sig")):
        service = _get_service(cache, item.get("dataset") if isinstance(item, dict) else None)
        request = AnalysisRequest(
            profile=_load_profile(item),
            barcode=item.get("barcode") if isinstance(item.get("barcode"), str) else None,
            image_path=str((ROOT / item["image_path"]).resolve()) if isinstance(item.get("image_path"), str) else None,
            ingredients_text=item.get("ingredients_text") if isinstance(item.get("ingredients_text"), str) else None,
        )
        results.append(_summarize(str(item.get("id", "case")), service.analyze(request)))

    with TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        salad_path = temp_dir_path / "visual_case.png"
        unknown_path = temp_dir_path / "scene_case.png"
        _make_salad_image(salad_path)
        _make_unknown_scene(unknown_path)

        service = _get_service(cache, None)
        salad_result = service.analyze(
            AnalysisRequest(
                profile=UserProfile(name="Alex", allergies=["milk"], diet="vegan"),
                image_path=str(salad_path),
            )
        )
        unknown_result = service.analyze(
            AnalysisRequest(
                profile=UserProfile(name="Alex", allergies=["milk"], diet="vegan"),
                image_path=str(unknown_path),
            )
        )
        results.append(_summarize("synthetic_salad_image", salad_result))
        results.append(_summarize("synthetic_unknown_scene", unknown_result))

    _write_outputs(results)

    for row in results:
        print(
            f"{row['id']}: {row['product_name']} | status={row['status']} | risk={row['risk_score']:.1f} | "
            f"image={row['image_label'] or '-'} ({row['image_source'] or '-'})"
        )
    print(f"Saved validation outputs to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

