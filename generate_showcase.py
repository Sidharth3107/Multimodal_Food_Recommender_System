from __future__ import annotations

import argparse
import json
from pathlib import Path

from nutriguard.html_report import save_html_report, save_showcase_index
from nutriguard.models import AnalysisRequest, UserProfile
from nutriguard.reporting import render_json_report
from nutriguard.service import FoodAnalysisService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a multi-case HTML showcase for Nutriguard.")
    parser.add_argument("--cases", default="examples/demo_cases.json", help="Path to the showcase cases JSON file.")
    parser.add_argument("--output-dir", default="examples/showcase_output", help="Directory for generated showcase assets.")
    parser.add_argument("--default-dataset", default="data/raw/en.openfoodfacts.org.products.tsv")
    parser.add_argument("--default-checkpoint", default="Food_Vision_Model/checkpoint-2400")
    return parser


def _load_profile(case: dict[str, object]) -> UserProfile:
    if "profile" in case:
        return UserProfile.from_dict(case["profile"])
    if "profile_path" in case:
        payload = json.loads(Path(str(case["profile_path"])).read_text(encoding="utf-8-sig"))
        return UserProfile.from_dict(payload)
    raise ValueError(f"Case {case.get('id', '<unknown>')} is missing profile information")


def main() -> int:
    args = build_parser().parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8-sig"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    services: dict[tuple[str, str], FoodAnalysisService] = {}
    index_items: list[dict[str, object]] = []

    for raw_case in cases:
        case = dict(raw_case)
        case_id = str(case["id"])
        dataset = str(case.get("dataset", args.default_dataset))
        checkpoint = str(case.get("checkpoint", args.default_checkpoint))
        key = (dataset, checkpoint)
        if key not in services:
            services[key] = FoodAnalysisService(dataset_path=dataset, vision_checkpoint=checkpoint)
        service = services[key]

        profile = _load_profile(case)
        request = AnalysisRequest(
            profile=profile,
            image_path=case.get("image_path"),
            ingredients_text=case.get("ingredients_text"),
            barcode=case.get("barcode"),
            top_k_predictions=int(case.get("top_k", 5)),
        )
        result = service.analyze(request)

        html_name = f"{case_id}.html"
        json_name = f"{case_id}.json"
        html_path = output_dir / html_name
        json_path = output_dir / json_name
        title = str(case.get("title", result.product_name))

        save_html_report(result, html_path, title=title)
        json_path.write_text(render_json_report(result), encoding="utf-8")

        index_items.append(
            {
                "href": html_name,
                "title": title,
                "summary": result.summary,
                "risk_score": result.risk_score,
                "status": result.status,
            }
        )

    save_showcase_index(
        index_items,
        output_dir / "index.html",
        title="Nutriguard Showcase",
        subtitle="Batch-generated case studies for the food safety, nutrition, and recommendation engine.",
    )
    print(f"Showcase written to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
