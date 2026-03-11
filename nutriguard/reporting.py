from __future__ import annotations

import json

from .models import AnalysisResult


def render_text_report(result: AnalysisResult) -> str:
    lines = [
        f"Product: {result.product_name}",
        f"Safe to eat: {'Yes' if result.safe_to_eat else 'No'}",
        f"Recommendation status: {result.status}",
        f"Risk score: {result.risk_score:.1f}/100",
        f"Summary: {result.summary}",
    ]

    if result.image_prediction is not None:
        lines.append(
            "Image model: "
            + ", ".join(
                f"{entry['label']} ({float(entry['confidence']) * 100:.1f}%)"
                for entry in result.image_prediction.top_k
            )
        )

    if result.detected_allergens:
        lines.append("Detected allergens: " + ", ".join(result.detected_allergens))
    if result.trace_allergens:
        lines.append("Trace allergens: " + ", ".join(result.trace_allergens))
    if result.diet_conflicts:
        lines.append("Diet conflicts: " + " | ".join(result.diet_conflicts))
    if result.avoid_matches:
        lines.append("Custom avoid matches: " + ", ".join(result.avoid_matches))
    if result.parsed_ingredients:
        lines.append("Parsed ingredients: " + ", ".join(result.parsed_ingredients[:12]))
    if result.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in result.warnings)
    if result.health_notes:
        lines.append("Health notes:")
        lines.extend(f"  - {note}" for note in result.health_notes)

    lines.append("Healthier alternatives:")
    if result.healthier_alternatives:
        for alternative in result.healthier_alternatives:
            nutrition_score = f"{alternative.nutrition_score:.1f}" if alternative.nutrition_score is not None else "n/a"
            lines.append(
                f"  - {alternative.product_name} [{alternative.main_category or 'unknown category'}], "
                f"nutrition score {nutrition_score}: {alternative.reason}"
            )
    else:
        lines.append("  - No profile-compatible healthier alternatives were found in the current search scope.")
    return "\n".join(lines)


def render_json_report(result: AnalysisResult) -> str:
    return json.dumps(result.to_dict(), indent=2)
