from __future__ import annotations

from .config import DEFAULT_VISUAL_RISK, NUTRITION_SCORE_MAX, NUTRITION_SCORE_MIN, VISUAL_RISK_PRIORS
from .models import ImagePrediction, NutritionFacts, RiskBreakdown


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def _scaled(value: float, lower: float, upper: float) -> float:
    if upper <= lower:
        return 0.0
    return _clamp(((value - lower) / (upper - lower)) * 100.0)


def compute_nutrition_component(nutrition: NutritionFacts) -> tuple[float, dict[str, float]]:
    detail: dict[str, float] = {}
    weighted_sum = 0.0
    total_weight = 0.0

    if nutrition.nutrition_score is not None:
        detail["nutrition_score"] = _scaled(nutrition.nutrition_score, NUTRITION_SCORE_MIN, NUTRITION_SCORE_MAX)
        weighted_sum += detail["nutrition_score"] * 0.45
        total_weight += 0.45
    if nutrition.sugars_g is not None:
        detail["sugars"] = _clamp((nutrition.sugars_g / 22.5) * 100.0)
        weighted_sum += detail["sugars"] * 0.20
        total_weight += 0.20
    if nutrition.salt_g is not None:
        detail["salt"] = _clamp((nutrition.salt_g / 1.5) * 100.0)
        weighted_sum += detail["salt"] * 0.15
        total_weight += 0.15
    if nutrition.saturated_fat_g is not None:
        detail["saturated_fat"] = _clamp((nutrition.saturated_fat_g / 5.0) * 100.0)
        weighted_sum += detail["saturated_fat"] * 0.10
        total_weight += 0.10
    if nutrition.energy_kj is not None:
        detail["energy"] = _clamp((nutrition.energy_kj / 2500.0) * 100.0)
        weighted_sum += detail["energy"] * 0.10
        total_weight += 0.10

    if total_weight == 0:
        return 35.0, detail
    return round(weighted_sum / total_weight, 2), detail


def compute_vision_component(image_prediction: ImagePrediction | None) -> float:
    if image_prediction is None:
        return 25.0
    prior = VISUAL_RISK_PRIORS.get(image_prediction.label.lower(), DEFAULT_VISUAL_RISK)
    confidence = image_prediction.confidence
    adjusted = (prior * confidence) + ((100.0 - confidence * 100.0) * 0.20)
    return round(_clamp(adjusted), 2)


def compute_risk_breakdown(
    direct_allergen_count: int,
    trace_allergen_count: int,
    probable_allergen_count: int,
    diet_conflict_count: int,
    nutrition: NutritionFacts,
    image_prediction: ImagePrediction | None,
) -> RiskBreakdown:
    allergy_component = 0.0
    if direct_allergen_count > 0:
        allergy_component = min(100.0, 85.0 + (direct_allergen_count - 1) * 5.0)
    elif probable_allergen_count > 0:
        allergy_component = min(82.0, 70.0 + (probable_allergen_count - 1) * 6.0)
    elif trace_allergen_count > 0:
        allergy_component = min(75.0, 55.0 + (trace_allergen_count - 1) * 7.0)

    diet_component = min(85.0, diet_conflict_count * 30.0)
    nutrition_component, nutrition_detail = compute_nutrition_component(nutrition)
    vision_component = compute_vision_component(image_prediction)

    overall = (
        allergy_component * 0.45
        + diet_component * 0.20
        + nutrition_component * 0.20
        + vision_component * 0.15
    )
    if direct_allergen_count > 0:
        overall = max(overall, 85.0)
    elif probable_allergen_count > 0:
        overall = max(overall, 72.0)
    elif diet_conflict_count > 0:
        overall = max(overall, 60.0)

    detail = {
        "allergy": round(allergy_component, 2),
        "diet": round(diet_component, 2),
        "nutrition": round(nutrition_component, 2),
        "vision": round(vision_component, 2),
    }
    detail.update({f"nutrition_{key}": round(value, 2) for key, value in nutrition_detail.items()})

    return RiskBreakdown(
        overall=round(_clamp(overall), 2),
        allergy_component=round(allergy_component, 2),
        diet_component=round(diet_component, 2),
        nutrition_component=round(nutrition_component, 2),
        vision_component=round(vision_component, 2),
        detail=detail,
    )
