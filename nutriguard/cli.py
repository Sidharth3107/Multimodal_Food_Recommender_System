from __future__ import annotations

import argparse
import json
from pathlib import Path

from .html_report import save_html_report
from .models import AnalysisRequest, UserProfile
from .reporting import render_json_report, render_text_report
from .service import FoodAnalysisService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze food images, ingredients, and barcodes against a user profile.")
    parser.add_argument("--profile", required=True, help="Path to a JSON file containing the user profile.")
    parser.add_argument("--image", help="Path to an input image of the food item.")
    parser.add_argument("--ingredients", help="Ingredient text supplied by the user or label OCR.")
    parser.add_argument("--barcode", help="Barcode / UPC / EAN of the product.")
    parser.add_argument("--json", action="store_true", help="Render the response as JSON.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of image predictions to return.")
    parser.add_argument(
        "--dataset",
        default="data/raw/en.openfoodfacts.org.products.tsv",
        help="Path to the OpenFoodFacts TSV file.",
    )
    parser.add_argument(
        "--checkpoint",
        default="Food_Vision_Model/checkpoint-2400",
        help="Path to the local image classification checkpoint.",
    )
    parser.add_argument("--html-report", help="Optional path to save a polished HTML report.")
    parser.add_argument("--save-json", help="Optional path to save the JSON response.")
    parser.add_argument("--report-title", help="Optional title override for the HTML report.")
    return parser


def load_profile(profile_path: str | Path) -> UserProfile:
    payload = json.loads(Path(profile_path).read_text(encoding="utf-8-sig"))
    return UserProfile.from_dict(payload)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    profile = load_profile(args.profile)
    service = FoodAnalysisService(dataset_path=args.dataset, vision_checkpoint=args.checkpoint)
    request = AnalysisRequest(
        profile=profile,
        image_path=args.image,
        ingredients_text=args.ingredients,
        barcode=args.barcode,
        top_k_predictions=args.top_k,
    )
    result = service.analyze(request)
    payload = render_json_report(result)

    if args.save_json:
        json_path = Path(args.save_json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(payload, encoding="utf-8")

    if args.html_report:
        save_html_report(result, args.html_report, title=args.report_title)

    if args.json:
        print(payload)
    else:
        print(render_text_report(result))
        if args.html_report:
            print(f"HTML report saved to {args.html_report}")
        if args.save_json:
            print(f"JSON report saved to {args.save_json}")
    return 0
