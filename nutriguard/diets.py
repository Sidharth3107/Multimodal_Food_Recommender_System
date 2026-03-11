from __future__ import annotations

from .config import DIET_RULES
from .models import NutritionFacts, UserProfile
from .parsing import find_ingredient_terms


def evaluate_diet_conflicts(
    profile: UserProfile,
    nutrition: NutritionFacts,
    ingredients_text: str | None,
    allergens_text: str | None,
    traces_text: str | None,
) -> list[str]:
    if not profile.diet:
        return []
    rule = DIET_RULES.get(profile.diet)
    if rule is None:
        return []

    issues: list[str] = []
    matched_terms = find_ingredient_terms(
        list(rule.forbidden_terms),
        ingredients_text,
        allergens_text,
        traces_text,
    )
    for term in matched_terms:
        issues.append(f"Contains '{term}', which conflicts with a {profile.diet} diet.")

    for field_name, max_value in rule.nutrient_maxima.items():
        value = getattr(nutrition, field_name)
        if value is None:
            continue
        if value > max_value:
            readable = field_name.replace("_g", " (g)").replace("_", " ")
            issues.append(f"{readable.title()} is {value:.2f} per 100 g, above the {profile.diet} target of {max_value:.2f}.")

    return issues
