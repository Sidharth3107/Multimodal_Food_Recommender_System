from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .config import LOW_CONFIDENCE_IMAGE_THRESHOLD, STYLE_ALTERNATIVE_HINTS, VISUAL_STYLE_PROFILES
from .diets import evaluate_diet_conflicts
from .models import AnalysisRequest, AnalysisResult, AlternativeRecommendation, ImagePrediction, NutritionFacts, ProductRecord
from .openfoodfacts import CandidateQuery, OpenFoodFactsIndex
from .parsing import canonicalize_allergy_terms, detect_allergen_matches, find_ingredient_terms, parse_ingredients_text, tokenize_label
from .risk import compute_risk_breakdown
from .vision import LocalVisionModel


class FoodAnalysisService:
    def __init__(
        self,
        dataset_path: str | Path = "data/raw/en.openfoodfacts.org.products.tsv",
        vision_checkpoint: str | Path = "Food_Vision_Model/checkpoint-2400",
        food_index: OpenFoodFactsIndex | None = None,
        vision_model: LocalVisionModel | None = None,
    ) -> None:
        self.food_index = food_index or OpenFoodFactsIndex(dataset_path)
        self.vision_model = vision_model or LocalVisionModel(vision_checkpoint)

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        barcode_product = self.food_index.lookup_barcode(request.barcode)
        image_prediction = self.vision_model.predict(request.image_path, top_k=request.top_k_predictions) if request.image_path else None

        profile_allergies = set(canonicalize_allergy_terms(request.profile.allergies))
        ingredients_text = request.ingredients_text or (barcode_product.ingredients_text if barcode_product else None)
        allergens_text = barcode_product.allergens_text if barcode_product else None
        traces_text = barcode_product.traces_text if barcode_product else None
        parsed_ingredients = parse_ingredients_text(ingredients_text)
        ingredient_style = self._infer_food_style(parsed_ingredients)
        resolved_style = self._resolve_visual_style(image_prediction, ingredient_style)
        insufficient_evidence = self._has_insufficient_evidence(
            barcode_product,
            ingredients_text,
            image_prediction,
            resolved_style,
        )

        allergen_matches = detect_allergen_matches(ingredients_text, allergens_text)
        trace_matches = detect_allergen_matches(traces_text)
        direct_allergens = sorted(set(allergen_matches).intersection(profile_allergies))
        trace_allergens = sorted(set(trace_matches).intersection(profile_allergies))
        probable_allergens = self._infer_probable_allergens(profile_allergies, barcode_product, ingredients_text, resolved_style)

        avoid_matches = find_ingredient_terms(
            request.profile.avoid_ingredients,
            ingredients_text,
            allergens_text,
            traces_text,
        )
        nutrition = barcode_product.nutrition if barcode_product else NutritionFacts()
        diet_conflicts = self._merge_unique(
            evaluate_diet_conflicts(
                request.profile,
                nutrition,
                ingredients_text,
                allergens_text,
                traces_text,
            ),
            self._infer_visual_diet_conflicts(request, barcode_product, ingredients_text, resolved_style),
        )

        mismatch_note = self._image_barcode_mismatch(image_prediction.label, barcode_product) if image_prediction and barcode_product else None
        risk = compute_risk_breakdown(
            direct_allergen_count=len(direct_allergens),
            trace_allergen_count=len(trace_allergens),
            probable_allergen_count=len(probable_allergens),
            diet_conflict_count=len(diet_conflicts) + len(avoid_matches),
            nutrition=nutrition,
            image_prediction=image_prediction,
        )

        status, safe_to_eat = self._decide_status(
            direct_allergens=direct_allergens,
            trace_allergens=trace_allergens,
            probable_allergens=probable_allergens,
            diet_conflicts=diet_conflicts,
            avoid_matches=avoid_matches,
            strict_mode=request.profile.strict_mode,
            insufficient_evidence=insufficient_evidence,
            risk_score=risk.overall,
        )
        warnings = self._build_warnings(
            direct_allergens,
            trace_allergens,
            probable_allergens,
            diet_conflicts,
            avoid_matches,
            insufficient_evidence,
            mismatch_note,
        )
        health_notes = self._build_health_notes(
            nutrition,
            image_prediction,
            ingredient_style,
            insufficient_evidence,
            risk.overall,
        )
        alternatives = self._find_alternatives(
            barcode_product=barcode_product,
            image_prediction=image_prediction,
            inferred_style=resolved_style,
            parsed_ingredients=parsed_ingredients,
            request=request,
            profile_allergies=profile_allergies,
        )

        product_name = self._resolve_product_name(barcode_product, image_prediction, resolved_style, parsed_ingredients)
        summary = self._build_summary(product_name, safe_to_eat, status, insufficient_evidence, risk.overall)
        evidence = {
            "barcode_lookup_used": barcode_product is not None,
            "image_used": image_prediction is not None,
            "ingredients_used": bool(ingredients_text),
            "resolved_category": barcode_product.main_category if barcode_product else None,
            "barcode": barcode_product.barcode if barcode_product else request.barcode,
            "nutrition": asdict(nutrition),
            "matched_allergen_terms": allergen_matches,
            "matched_trace_terms": trace_matches,
            "image_barcode_mismatch": mismatch_note,
            "inferred_style": ingredient_style,
            "resolved_visual_style": resolved_style,
            "probable_allergens": probable_allergens,
            "visual_recovery": bool(image_prediction and image_prediction.source == "vision_recovery"),
            "insufficient_evidence": insufficient_evidence,
        }

        return AnalysisResult(
            product_name=product_name,
            safe_to_eat=safe_to_eat,
            status=status,
            risk_score=risk.overall,
            risk_breakdown=risk,
            summary=summary,
            warnings=warnings,
            health_notes=health_notes,
            healthier_alternatives=alternatives,
            detected_allergens=direct_allergens,
            trace_allergens=trace_allergens,
            probable_allergens=probable_allergens,
            diet_conflicts=diet_conflicts,
            avoid_matches=avoid_matches,
            parsed_ingredients=parsed_ingredients,
            evidence=evidence,
            image_prediction=image_prediction,
            barcode_product=barcode_product,
        )

    def _resolve_product_name(
        self,
        barcode_product: ProductRecord | None,
        image_prediction: ImagePrediction | None,
        inferred_style: str | None,
        parsed_ingredients: list[str],
    ) -> str:
        if barcode_product and barcode_product.product_name:
            return barcode_product.product_name
        if image_prediction and image_prediction.confidence >= LOW_CONFIDENCE_IMAGE_THRESHOLD:
            return image_prediction.label.title()
        if inferred_style:
            return f"{inferred_style.title()}-style item"
        if parsed_ingredients:
            return "Ingredient-defined food item"
        if image_prediction:
            return f"Unverified food item ({image_prediction.label})"
        return "Unknown food item"

    def _build_summary(
        self,
        product_name: str,
        safe_to_eat: bool,
        status: str,
        insufficient_evidence: bool,
        risk_score: float,
    ) -> str:
        if insufficient_evidence:
            return (
                f"{product_name} cannot be fully verified from the current evidence alone. "
                f"Add ingredients or a barcode for a reliable safety decision. Estimated risk score: {risk_score:.1f}/100."
            )
        if safe_to_eat and status == "safe":
            return f"{product_name} looks compatible with the current profile. Estimated risk score: {risk_score:.1f}/100."
        if safe_to_eat:
            return f"{product_name} is profile-compatible, but it carries some nutritional or uncertainty risk. Estimated risk score: {risk_score:.1f}/100."
        return f"{product_name} is not recommended for the current profile. Estimated risk score: {risk_score:.1f}/100."

    def _decide_status(
        self,
        direct_allergens: list[str],
        trace_allergens: list[str],
        probable_allergens: list[str],
        diet_conflicts: list[str],
        avoid_matches: list[str],
        strict_mode: bool,
        insufficient_evidence: bool,
        risk_score: float,
    ) -> tuple[str, bool]:
        if direct_allergens or diet_conflicts or avoid_matches:
            return "avoid", False
        if probable_allergens:
            if strict_mode:
                return "avoid", False
            return "caution", True
        if insufficient_evidence:
            return "caution", False
        if trace_allergens or risk_score >= 65.0:
            return "caution", True
        return "safe", True

    def _build_warnings(
        self,
        direct_allergens: list[str],
        trace_allergens: list[str],
        probable_allergens: list[str],
        diet_conflicts: list[str],
        avoid_matches: list[str],
        insufficient_evidence: bool,
        mismatch_note: str | None,
    ) -> list[str]:
        warnings: list[str] = []
        for allergen in direct_allergens:
            warnings.append(f"Direct allergen match for '{allergen}'.")
        for allergen in trace_allergens:
            warnings.append(f"Possible trace exposure to '{allergen}'.")
        for allergen in probable_allergens:
            warnings.append(f"Visual evidence suggests this item likely contains '{allergen}'; verify the ingredient list before eating.")
        warnings.extend(diet_conflicts)
        for match in avoid_matches:
            warnings.append(f"Contains '{match}', which is on the custom avoid list.")
        if insufficient_evidence:
            warnings.append("Current evidence is too weak for a fully reliable safe-to-eat decision; add a barcode or ingredients list.")
        if mismatch_note:
            warnings.append(mismatch_note)
        return warnings

    def _build_health_notes(
        self,
        nutrition: NutritionFacts,
        image_prediction: ImagePrediction | None,
        inferred_style: str | None,
        insufficient_evidence: bool,
        risk_score: float,
    ) -> list[str]:
        notes: list[str] = []
        if nutrition.nutrition_score is not None:
            if nutrition.nutrition_score <= 0:
                notes.append(f"Nutrition score is favorable at {nutrition.nutrition_score:.1f}.")
            elif nutrition.nutrition_score <= 10:
                notes.append(f"Nutrition score is moderate at {nutrition.nutrition_score:.1f}.")
            else:
                notes.append(f"Nutrition score is high-risk at {nutrition.nutrition_score:.1f}; moderation is advisable.")
        if nutrition.sugars_g is not None and nutrition.sugars_g >= 15:
            notes.append(f"Sugars are elevated at {nutrition.sugars_g:.1f} g per 100 g.")
        if nutrition.salt_g is not None and nutrition.salt_g >= 1.0:
            notes.append(f"Salt is elevated at {nutrition.salt_g:.2f} g per 100 g.")
        if image_prediction is not None:
            confidence_text = f"{image_prediction.confidence * 100:.1f}%"
            if image_prediction.source == "vision_recovery":
                raw_note = ""
                if image_prediction.raw_label and image_prediction.raw_confidence is not None:
                    raw_note = f" Raw classifier guess was '{image_prediction.raw_label}' at {image_prediction.raw_confidence * 100:.1f}%."
                reason_note = f" {image_prediction.heuristic_reason}" if image_prediction.heuristic_reason else ""
                visual_note = f"Visual recovery resolved this image as '{image_prediction.label}' at {confidence_text}.{reason_note}{raw_note}"
                notes.append(visual_note.strip())
            elif image_prediction.source == "vision_unavailable":
                reason_note = f" {image_prediction.heuristic_reason}" if image_prediction.heuristic_reason else ""
                notes.append(f"Pretrained vision checkpoint was unavailable for this run.{reason_note}".strip())
            elif image_prediction.confidence < LOW_CONFIDENCE_IMAGE_THRESHOLD:
                notes.append(f"Image model is uncertain: top guess is '{image_prediction.label}' at {confidence_text} confidence.")
            else:
                notes.append(f"Image model predicts '{image_prediction.label}' with {confidence_text} confidence.")
        if inferred_style:
            notes.append(f"Ingredient pattern most closely resembles a {inferred_style} item.")
        if insufficient_evidence:
            notes.append("Image evidence alone is not strong enough here; add ingredients text or scan a barcode for a dependable recommendation.")
        if risk_score >= 75:
            notes.append("Overall risk is high because the profile constraints dominate the nutrition signal.")
        return notes

    def _find_alternatives(
        self,
        barcode_product: ProductRecord | None,
        image_prediction: ImagePrediction | None,
        inferred_style: str | None,
        parsed_ingredients: list[str],
        request: AnalysisRequest,
        profile_allergies: set[str],
    ) -> list[AlternativeRecommendation]:
        image_anchor = image_prediction.label if image_prediction and image_prediction.confidence >= LOW_CONFIDENCE_IMAGE_THRESHOLD else None
        anchor = barcode_product.main_category if barcode_product else (inferred_style or image_anchor)
        query = CandidateQuery(
            category=anchor,
            predicted_label=inferred_style or image_anchor,
            product_name=barcode_product.product_name if barcode_product else (inferred_style or image_anchor),
            ingredient_terms=parsed_ingredients,
            current_barcode=barcode_product.barcode if barcode_product else request.barcode,
            current_nutrition_score=barcode_product.nutrition.nutrition_score if barcode_product else None,
        )
        alternatives = self._collect_profile_compatible_alternatives(
            self.food_index.find_candidates(query),
            request,
            profile_allergies,
            barcode_product,
        )
        if alternatives or not inferred_style:
            return alternatives

        fallback_hints = STYLE_ALTERNATIVE_HINTS.get(inferred_style, ())
        for hint in fallback_hints:
            fallback_query = CandidateQuery(
                category=hint,
                predicted_label=hint,
                product_name=hint,
                current_barcode=barcode_product.barcode if barcode_product else request.barcode,
            )
            additional = self._collect_profile_compatible_alternatives(
                self.food_index.find_candidates(fallback_query),
                request,
                profile_allergies,
                barcode_product,
                existing=alternatives,
            )
            alternatives.extend(additional)
            if len(alternatives) >= 3:
                break
        return alternatives[:3]

    def _collect_profile_compatible_alternatives(
        self,
        candidates: list[ProductRecord],
        request: AnalysisRequest,
        profile_allergies: set[str],
        current_product: ProductRecord | None,
        existing: list[AlternativeRecommendation] | None = None,
    ) -> list[AlternativeRecommendation]:
        alternatives: list[AlternativeRecommendation] = []
        seen_names = {item.product_name.lower() for item in existing or []}
        for candidate in candidates:
            if not candidate.product_name:
                continue
            allergen_matches = detect_allergen_matches(candidate.ingredients_text, candidate.allergens_text)
            if set(allergen_matches).intersection(profile_allergies):
                continue
            diet_conflicts = evaluate_diet_conflicts(
                request.profile,
                candidate.nutrition,
                candidate.ingredients_text,
                candidate.allergens_text,
                candidate.traces_text,
            )
            if diet_conflicts:
                continue

            normalized_name = candidate.product_name.lower()
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            alternatives.append(
                AlternativeRecommendation(
                    barcode=candidate.barcode,
                    product_name=candidate.product_name,
                    main_category=candidate.main_category,
                    nutrition_score=candidate.nutrition.nutrition_score,
                    nutrition_grade=candidate.nutrition.nutrition_grade,
                    reason=self._build_alternative_reason(candidate, current_product),
                )
            )
            if len(alternatives) == 3:
                break
        return alternatives

    def _build_alternative_reason(self, candidate: ProductRecord, current_product: ProductRecord | None) -> str:
        candidate_score = candidate.nutrition.nutrition_score
        current_score = current_product.nutrition.nutrition_score if current_product else None
        if candidate_score is not None and current_score is not None:
            improvement = current_score - candidate_score
            if improvement > 0:
                return f"Same category with a lower nutrition risk score by {improvement:.1f} points."
        if candidate_score is not None:
            return f"Compatible with the profile and carries a nutrition score of {candidate_score:.1f}."
        return "Compatible with the profile and selected from a similar category."

    def _image_barcode_mismatch(self, image_label: str, barcode_product: ProductRecord) -> str | None:
        anchor_tokens = tokenize_label(image_label)
        product_tokens = tokenize_label(barcode_product.product_name) | tokenize_label(barcode_product.main_category)
        if not anchor_tokens or not product_tokens:
            return None
        overlap = anchor_tokens.intersection(product_tokens)
        if overlap:
            return None
        return f"Image prediction '{image_label}' does not closely match the barcode product metadata."

    def _infer_food_style(self, parsed_ingredients: list[str]) -> str | None:
        if not parsed_ingredients:
            return None
        combined = " ".join(parsed_ingredients)
        heuristics = [
            ("pizza", (("tomato", "mozzarella", "pepperoni", "basil", "cheese"), ("flour", "dough", "crust"))),
            ("salad", (("lettuce", "cucumber", "greens", "arugula"), ("olive oil", "vinegar", "tomato"))),
            ("burger", (("patty", "beef", "bun", "pickle"), ("cheese", "ketchup", "mustard"))),
            ("sandwich", (("bread", "ham", "turkey", "lettuce"), ("cheese", "mayo", "mustard"))),
            ("pasta", (("pasta", "spaghetti", "penne", "ravioli"), ("tomato", "cheese", "basil"))),
        ]
        for label, (core_terms, support_terms) in heuristics:
            core_hits = sum(1 for term in core_terms if term in combined)
            support_hits = sum(1 for term in support_terms if term in combined)
            if core_hits >= 2 or (core_hits >= 1 and support_hits >= 1):
                return label
        return None

    def _resolve_visual_style(self, image_prediction: ImagePrediction | None, ingredient_style: str | None) -> str | None:
        if ingredient_style:
            return ingredient_style
        if image_prediction and image_prediction.confidence >= LOW_CONFIDENCE_IMAGE_THRESHOLD:
            return image_prediction.label.lower()
        return None

    def _has_insufficient_evidence(
        self,
        barcode_product: ProductRecord | None,
        ingredients_text: str | None,
        image_prediction: ImagePrediction | None,
        resolved_style: str | None,
    ) -> bool:
        if barcode_product or ingredients_text:
            return False
        if image_prediction is None:
            return True
        if resolved_style and image_prediction.confidence >= LOW_CONFIDENCE_IMAGE_THRESHOLD:
            return False
        return image_prediction.confidence < LOW_CONFIDENCE_IMAGE_THRESHOLD or not resolved_style

    def _infer_probable_allergens(
        self,
        profile_allergies: set[str],
        barcode_product: ProductRecord | None,
        ingredients_text: str | None,
        resolved_style: str | None,
    ) -> list[str]:
        if barcode_product or ingredients_text or not resolved_style:
            return []
        style_profile = VISUAL_STYLE_PROFILES.get(resolved_style)
        if not style_profile:
            return []
        return sorted(set(style_profile.likely_allergens).intersection(profile_allergies))

    def _infer_visual_diet_conflicts(
        self,
        request: AnalysisRequest,
        barcode_product: ProductRecord | None,
        ingredients_text: str | None,
        resolved_style: str | None,
    ) -> list[str]:
        if barcode_product or ingredients_text or not request.profile.diet or not resolved_style:
            return []
        style_profile = VISUAL_STYLE_PROFILES.get(resolved_style)
        if not style_profile:
            return []
        message = style_profile.diet_conflicts.get(request.profile.diet)
        return [message] if message else []

    def _merge_unique(self, base: list[str], additional: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for item in [*base, *additional]:
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
        return merged

