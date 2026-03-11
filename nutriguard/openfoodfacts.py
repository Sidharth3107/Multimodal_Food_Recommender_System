from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import OPENFOODFACTS_COLUMNS
from .models import NutritionFacts, ProductRecord
from .parsing import normalize_barcode, normalize_text, tokenize_label


@dataclass(slots=True)
class CandidateQuery:
    category: str | None
    predicted_label: str | None
    product_name: str | None
    ingredient_terms: list[str] | None = None
    current_barcode: str | None = None
    current_nutrition_score: float | None = None


class OpenFoodFactsIndex:
    def __init__(self, dataset_path: str | Path) -> None:
        self.dataset_path = Path(dataset_path)
        self._table: pd.DataFrame | None = None

    def _load(self) -> pd.DataFrame:
        if self._table is not None:
            return self._table

        table = pd.read_csv(
            self.dataset_path,
            sep="\t",
            usecols=OPENFOODFACTS_COLUMNS,
            low_memory=False,
            dtype={"code": str},
        )
        table = table.rename(
            columns={
                "main_category_en": "main_category",
                "allergens_en": "allergens_text",
                "traces_en": "traces_text",
                "nutrition-score-fr_100g": "nutrition_score",
                "nutrition_grade_fr": "nutrition_grade",
                "energy_100g": "energy_kj",
                "fat_100g": "fat_g",
                "saturated-fat_100g": "saturated_fat_g",
                "sugars_100g": "sugars_g",
                "carbohydrates_100g": "carbohydrates_g",
                "proteins_100g": "proteins_g",
                "salt_100g": "salt_g",
            }
        )
        table["code"] = table["code"].fillna("").astype(str)
        table["normalized_barcode"] = table["code"].map(normalize_barcode)
        table["main_category_norm"] = table["main_category"].fillna("").map(normalize_text)
        table["search_blob"] = (
            table["product_name"].fillna("")
            + " "
            + table["main_category"].fillna("")
            + " "
            + table["ingredients_text"].fillna("")
        ).map(normalize_text)
        self._table = table
        return self._table

    @property
    def table(self) -> pd.DataFrame:
        return self._load()

    def lookup_barcode(self, barcode: str | None) -> ProductRecord | None:
        normalized = normalize_barcode(barcode)
        if not normalized:
            return None
        matches = self.table.loc[self.table["normalized_barcode"] == normalized]
        if matches.empty:
            return None
        return self._row_to_record(matches.iloc[0], source="barcode")

    def find_candidates(self, query: CandidateQuery, pool_size: int = 300) -> list[ProductRecord]:
        subset = self.table.loc[self.table["nutrition_score"].notna()].copy()

        current_barcode = normalize_barcode(query.current_barcode)
        if current_barcode:
            subset = subset.loc[subset["normalized_barcode"] != current_barcode]

        target_category = normalize_text(query.category)
        used_exact_category = False
        if target_category:
            exact = subset.loc[subset["main_category_norm"] == target_category]
            if not exact.empty:
                subset = exact
                used_exact_category = True

        if not used_exact_category:
            anchor_tokens = self._anchor_tokens(query)
            if anchor_tokens:
                subset["token_overlap"] = subset["search_blob"].map(lambda text: _count_token_overlap(text, anchor_tokens))
                token_subset = subset.loc[subset["token_overlap"] > 0].copy()
                if not token_subset.empty:
                    subset = token_subset

        if query.current_nutrition_score is not None:
            better = subset.loc[subset["nutrition_score"] < query.current_nutrition_score]
            if not better.empty:
                subset = better

        sort_columns = ["nutrition_score", "product_name"]
        ascending = [True, True]
        if "token_overlap" in subset.columns:
            sort_columns = ["token_overlap", "nutrition_score", "product_name"]
            ascending = [False, True, True]
        subset = subset.sort_values(sort_columns, ascending=ascending).head(pool_size)
        return [self._row_to_record(row, source="openfoodfacts") for _, row in subset.iterrows()]

    def _anchor_tokens(self, query: CandidateQuery) -> list[str]:
        tokens = set()
        tokens.update(tokenize_label(query.category))
        tokens.update(tokenize_label(query.predicted_label))
        tokens.update(tokenize_label(query.product_name))
        if query.ingredient_terms:
            tokens.update(tokenize_label(" ".join(query.ingredient_terms[:8])))
        return sorted(tokens)

    def _row_to_record(self, row: pd.Series, source: str) -> ProductRecord:
        nutrition = NutritionFacts(
            nutrition_score=_float_or_none(row.get("nutrition_score")),
            energy_kj=_float_or_none(row.get("energy_kj")),
            fat_g=_float_or_none(row.get("fat_g")),
            saturated_fat_g=_float_or_none(row.get("saturated_fat_g")),
            sugars_g=_float_or_none(row.get("sugars_g")),
            carbohydrates_g=_float_or_none(row.get("carbohydrates_g")),
            proteins_g=_float_or_none(row.get("proteins_g")),
            salt_g=_float_or_none(row.get("salt_g")),
            nutrition_grade=_clean_optional_text(row.get("nutrition_grade")),
        )
        return ProductRecord(
            barcode=_clean_optional_text(row.get("code")),
            normalized_barcode=_clean_optional_text(row.get("normalized_barcode")),
            product_name=_clean_optional_text(row.get("product_name")),
            main_category=_clean_optional_text(row.get("main_category")),
            ingredients_text=_clean_optional_text(row.get("ingredients_text")),
            allergens_text=_clean_optional_text(row.get("allergens_text")),
            traces_text=_clean_optional_text(row.get("traces_text")),
            image_url=_clean_optional_text(row.get("image_url")),
            nutrition=nutrition,
            source=source,
        )


def _count_token_overlap(text: str, tokens: list[str]) -> int:
    if not text:
        return 0
    normalized = normalize_text(text)
    return sum(1 for token in tokens if token and token in normalized)


def _float_or_none(value: object) -> float | None:
    if value is None or value != value:
        return None
    return float(value)


def _clean_optional_text(value: object) -> str | None:
    if value is None or value != value:
        return None
    text = str(value).strip()
    return text or None
