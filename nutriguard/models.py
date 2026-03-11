from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _clean_text_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        normalized = text.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


@dataclass(slots=True)
class UserProfile:
    name: str = "User"
    allergies: list[str] = field(default_factory=list)
    diet: str | None = None
    avoid_ingredients: list[str] = field(default_factory=list)
    strict_mode: bool = True
    health_goals: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.allergies = _clean_text_list(self.allergies)
        self.avoid_ingredients = _clean_text_list(self.avoid_ingredients)
        self.health_goals = _clean_text_list(self.health_goals)
        self.diet = self.diet.strip().lower() if isinstance(self.diet, str) and self.diet.strip() else None
        self.name = self.name.strip() or "User"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UserProfile":
        return cls(
            name=payload.get("name", "User"),
            allergies=list(payload.get("allergies", [])),
            diet=payload.get("diet"),
            avoid_ingredients=list(payload.get("avoid_ingredients", [])),
            strict_mode=bool(payload.get("strict_mode", True)),
            health_goals=list(payload.get("health_goals", [])),
        )


@dataclass(slots=True)
class NutritionFacts:
    nutrition_score: float | None = None
    energy_kj: float | None = None
    fat_g: float | None = None
    saturated_fat_g: float | None = None
    sugars_g: float | None = None
    carbohydrates_g: float | None = None
    proteins_g: float | None = None
    salt_g: float | None = None
    nutrition_grade: str | None = None


@dataclass(slots=True)
class ProductRecord:
    barcode: str | None = None
    normalized_barcode: str | None = None
    product_name: str | None = None
    main_category: str | None = None
    ingredients_text: str | None = None
    allergens_text: str | None = None
    traces_text: str | None = None
    image_url: str | None = None
    nutrition: NutritionFacts = field(default_factory=NutritionFacts)
    source: str = "unknown"


@dataclass(slots=True)
class ImagePrediction:
    label: str
    confidence: float
    top_k: list[dict[str, float | str]]
    source: str = "vision_model"
    raw_label: str | None = None
    raw_confidence: float | None = None
    heuristic_reason: str | None = None


@dataclass(slots=True)
class AlternativeRecommendation:
    barcode: str | None
    product_name: str
    main_category: str | None
    nutrition_score: float | None
    nutrition_grade: str | None
    reason: str


@dataclass(slots=True)
class RiskBreakdown:
    overall: float
    allergy_component: float
    diet_component: float
    nutrition_component: float
    vision_component: float
    detail: dict[str, float]


@dataclass(slots=True)
class AnalysisRequest:
    profile: UserProfile
    image_path: str | None = None
    ingredients_text: str | None = None
    barcode: str | None = None
    top_k_predictions: int = 5


@dataclass(slots=True)
class AnalysisResult:
    product_name: str
    safe_to_eat: bool
    status: str
    risk_score: float
    risk_breakdown: RiskBreakdown
    summary: str
    warnings: list[str]
    health_notes: list[str]
    healthier_alternatives: list[AlternativeRecommendation]
    detected_allergens: list[str]
    trace_allergens: list[str]
    probable_allergens: list[str]
    diet_conflicts: list[str]
    avoid_matches: list[str]
    parsed_ingredients: list[str]
    evidence: dict[str, Any]
    image_prediction: ImagePrediction | None = None
    barcode_product: ProductRecord | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
