from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from nutriguard.html_report import render_html_report
from nutriguard.models import AnalysisRequest, ImagePrediction, UserProfile
from nutriguard.parsing import canonicalize_allergy_terms, parse_ingredients_text
from nutriguard.service import FoodAnalysisService
from nutriguard.vision import LocalVisionModel


class StaticVisionModel:
    def __init__(self, prediction: ImagePrediction) -> None:
        self.prediction = prediction

    def predict(self, image_path: str | None, top_k: int = 5) -> ImagePrediction:
        return self.prediction


class RuleTests(unittest.TestCase):
    def test_canonicalize_allergy_terms(self) -> None:
        self.assertEqual(set(canonicalize_allergy_terms(["Lactose", "Peanuts"])), {"milk", "peanut"})

    def test_parse_ingredients_text_flattens_groups(self) -> None:
        parsed = parse_ingredients_text("Tomato puree (tomato, salt), mozzarella cheese, basil")
        self.assertIn("tomato puree", parsed)
        self.assertIn("tomato", parsed)
        self.assertIn("salt", parsed)
        self.assertIn("mozzarella cheese", parsed)


class VisionRecoveryTests(unittest.TestCase):
    def test_pizza_photo_recovers_from_low_confidence_classifier(self) -> None:
        model = LocalVisionModel("Food_Vision_Model/checkpoint-2400")
        raw_prediction = ImagePrediction(
            label="waffles",
            confidence=0.088,
            top_k=[
                {"label": "waffles", "confidence": 0.088},
                {"label": "shrimp and grits", "confidence": 0.06},
            ],
        )

        recovered = model._recover_prediction("data/input_images/pizza.jpg", raw_prediction)

        self.assertEqual(recovered.label, "pizza")
        self.assertEqual(recovered.source, "vision_recovery")
        self.assertEqual(recovered.raw_label, "waffles")
        self.assertGreaterEqual(recovered.confidence, 0.78)
        self.assertEqual(recovered.top_k[0]["label"], "pizza")

    def test_green_image_recovers_salad_without_filename_hint(self) -> None:
        model = LocalVisionModel("Food_Vision_Model/checkpoint-2400")
        raw_prediction = ImagePrediction(
            label="miso soup",
            confidence=0.081,
            top_k=[
                {"label": "miso soup", "confidence": 0.081},
                {"label": "waffles", "confidence": 0.074},
            ],
        )

        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "visual_case.png"
            image = Image.new("RGB", (256, 256), (236, 242, 228))
            draw = ImageDraw.Draw(image)
            draw.ellipse((24, 24, 232, 232), fill=(84, 138, 83))
            draw.ellipse((72, 54, 118, 100), fill=(197, 35, 43))
            draw.ellipse((142, 76, 190, 124), fill=(230, 205, 82))
            draw.ellipse((92, 142, 140, 190), fill=(245, 244, 236))
            image.save(image_path)

            recovered = model._recover_prediction(image_path, raw_prediction)

        self.assertEqual(recovered.label, "salad")
        self.assertEqual(recovered.source, "vision_recovery")
        self.assertGreaterEqual(recovered.confidence, 0.56)

    def test_missing_checkpoint_uses_heuristics_instead_of_crashing(self) -> None:
        model = LocalVisionModel("missing-checkpoint")
        recovered = model.predict("data/input_images/pizza.jpg")

        self.assertEqual(recovered.label, "pizza")
        self.assertEqual(recovered.source, "vision_recovery")
        self.assertEqual(recovered.raw_label, "unverified visual item")
        self.assertTrue(recovered.heuristic_reason)


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = FoodAnalysisService(dataset_path="tests/data/sample_openfoodfacts.tsv")

    def test_barcode_analysis_flags_allergy_and_diet_conflict(self) -> None:
        profile = UserProfile(name="Alex", allergies=["lactose"], diet="vegan")
        result = self.service.analyze(AnalysisRequest(profile=profile, barcode="1001"))

        self.assertFalse(result.safe_to_eat)
        self.assertEqual(result.status, "avoid")
        self.assertIn("milk", result.detected_allergens)
        self.assertTrue(any("vegan" in issue for issue in result.diet_conflicts))
        self.assertTrue(any(alt.product_name == "Roasted Veggie Pizza" for alt in result.healthier_alternatives))

    def test_safe_salad_profile(self) -> None:
        profile = UserProfile(name="Alex", allergies=["milk"], diet="vegan")
        result = self.service.analyze(AnalysisRequest(profile=profile, barcode="1003"))

        self.assertTrue(result.safe_to_eat)
        self.assertEqual(result.status, "safe")
        self.assertLess(result.risk_score, 50.0)
        self.assertEqual(result.detected_allergens, [])
        self.assertEqual(result.probable_allergens, [])

    def test_ingredient_style_fallback(self) -> None:
        profile = UserProfile(name="Alex", allergies=["milk"], diet="vegan")
        result = self.service.analyze(
            AnalysisRequest(
                profile=profile,
                ingredients_text="wheat flour, tomato puree, mozzarella cheese, basil, pepperoni",
            )
        )

        self.assertEqual(result.product_name, "Pizza-style item")
        self.assertFalse(result.safe_to_eat)

    def test_image_only_pizza_uses_visual_recovery_for_safety(self) -> None:
        profile = UserProfile(name="Alex", allergies=["cheese"], diet="vegetarian")
        recovered_prediction = ImagePrediction(
            label="pizza",
            confidence=0.84,
            top_k=[
                {"label": "pizza", "confidence": 0.84},
                {"label": "waffles", "confidence": 0.088},
            ],
            source="vision_recovery",
            raw_label="waffles",
            raw_confidence=0.088,
            heuristic_reason="Filename contains the food cue 'pizza'. Strong tomato-sauce and melted-cheese color ratios match a pizza profile.",
        )
        service = FoodAnalysisService(
            dataset_path="tests/data/sample_openfoodfacts.tsv",
            vision_model=StaticVisionModel(recovered_prediction),
        )

        result = service.analyze(AnalysisRequest(profile=profile, image_path="data/input_images/pizza.jpg"))

        self.assertEqual(result.product_name, "Pizza")
        self.assertEqual(result.status, "avoid")
        self.assertFalse(result.safe_to_eat)
        self.assertIn("milk", result.probable_allergens)
        self.assertTrue(any("likely contains 'milk'" in item for item in result.warnings))
        self.assertTrue(any("Raw classifier guess was 'waffles'" in item for item in result.health_notes))

    def test_weak_image_only_case_requires_more_evidence(self) -> None:
        profile = UserProfile(name="Alex", allergies=["milk"], diet="vegan")
        weak_prediction = ImagePrediction(
            label="french toast",
            confidence=0.03,
            top_k=[
                {"label": "french toast", "confidence": 0.03},
                {"label": "macarons", "confidence": 0.02},
            ],
        )
        service = FoodAnalysisService(
            dataset_path="tests/data/sample_openfoodfacts.tsv",
            vision_model=StaticVisionModel(weak_prediction),
        )

        result = service.analyze(AnalysisRequest(profile=profile, image_path="placeholder.jpg"))

        self.assertEqual(result.status, "caution")
        self.assertFalse(result.safe_to_eat)
        self.assertTrue(result.evidence["insufficient_evidence"])
        self.assertTrue(any("too weak" in item for item in result.warnings))
        self.assertIn("cannot be fully verified", result.summary)

    def test_html_report_generation(self) -> None:
        profile = UserProfile(name="Alex", allergies=["milk"], diet="vegan")
        result = self.service.analyze(AnalysisRequest(profile=profile, barcode="1003"))
        report = render_html_report(result, title="Demo")

        self.assertIn("<!doctype html>", report.lower())
        self.assertIn("Demo", report)
        self.assertIn(result.product_name, report)
        self.assertIn("Likely allergens", report)


if __name__ == "__main__":
    unittest.main()

