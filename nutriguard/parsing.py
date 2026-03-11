from __future__ import annotations

import re
import unicodedata

from .config import ALLERGEN_SYNONYMS


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = text.replace("_", " ")
    text = re.sub(r"[^a-z0-9,%\s\-()/]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_barcode(value: str | None) -> str:
    if not value:
        return ""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return ""
    return digits.lstrip("0") or "0"


def canonicalize_allergy_terms(values: list[str] | None) -> list[str]:
    if not values:
        return []
    canonicalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if not normalized:
            continue
        canonical = normalized
        for allergen, synonyms in ALLERGEN_SYNONYMS.items():
            options = {normalize_text(allergen), *(normalize_text(item) for item in synonyms)}
            if normalized in options:
                canonical = allergen
                break
        if canonical in seen:
            continue
        seen.add(canonical)
        canonicalized.append(canonical)
    return canonicalized


def parse_ingredients_text(ingredients_text: str | None) -> list[str]:
    text = normalize_text(ingredients_text)
    if not text:
        return []
    text = text.replace("may contain", ", may contain ")
    text = re.sub(r"\([^)]*\)", lambda match: ", " + match.group(0)[1:-1] + ", ", text)
    text = re.sub(r"\d+(?:[.,]\d+)?\s*%", " ", text)
    raw_parts = re.split(r"[,;:.]", text)
    parts: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        cleaned = re.sub(r"\s+", " ", part).strip(" -")
        if len(cleaned) < 2:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        parts.append(cleaned)
    return parts


def _collect_term_matches(text: str, terms: tuple[str, ...] | list[str]) -> list[str]:
    matches: list[str] = []
    for term in terms:
        normalized_term = normalize_text(term)
        if not normalized_term:
            continue
        pattern = rf"\b{re.escape(normalized_term)}\b"
        if re.search(pattern, text):
            matches.append(normalized_term)
    return sorted(set(matches))


def detect_allergen_matches(*texts: str | None) -> dict[str, list[str]]:
    combined = normalize_text(" ".join(text for text in texts if text))
    matches: dict[str, list[str]] = {}
    for canonical, synonyms in ALLERGEN_SYNONYMS.items():
        found = _collect_term_matches(combined, list(synonyms) + [canonical])
        if found:
            matches[canonical] = found
    return matches


def find_ingredient_terms(terms: list[str], *texts: str | None) -> list[str]:
    combined = normalize_text(" ".join(text for text in texts if text))
    return _collect_term_matches(combined, terms)


def tokenize_label(value: str | None) -> set[str]:
    text = normalize_text(value)
    if not text:
        return set()
    tokens = {token for token in text.split() if len(token) > 2}
    return tokens
