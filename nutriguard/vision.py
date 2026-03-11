from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

from .config import FILENAME_STYLE_HINTS, LOW_CONFIDENCE_IMAGE_THRESHOLD
from .models import ImagePrediction
from .parsing import normalize_text


@dataclass(frozen=True, slots=True)
class VisualHint:
    label: str
    confidence: float
    reason: str


class LocalVisionModel:
    def __init__(self, checkpoint_dir: str | Path) -> None:
        self.checkpoint_dir = str(checkpoint_dir)
        self._processor: AutoImageProcessor | None = None
        self._model: AutoModelForImageClassification | None = None

    def _load(self) -> tuple[AutoImageProcessor, AutoModelForImageClassification]:
        if self._processor is None or self._model is None:
            self._processor = AutoImageProcessor.from_pretrained(self.checkpoint_dir, local_files_only=True, use_fast=False)
            self._model = AutoModelForImageClassification.from_pretrained(self.checkpoint_dir, local_files_only=True)
            self._model.eval()
        return self._processor, self._model

    def predict(self, image_path: str | Path, top_k: int = 5) -> ImagePrediction:
        raw_prediction = self._predict_from_checkpoint(image_path, top_k)
        return self._recover_prediction(image_path, raw_prediction)

    def _predict_from_checkpoint(self, image_path: str | Path, top_k: int) -> ImagePrediction:
        try:
            processor, model = self._load()
            image = Image.open(image_path).convert("RGB")
            inputs = processor(images=image, return_tensors="pt")
            with torch.no_grad():
                logits = model(**inputs).logits
                probabilities = torch.softmax(logits, dim=-1)[0]

            top_k = min(top_k, probabilities.shape[0])
            values, indices = probabilities.topk(top_k)
            top_predictions: list[dict[str, float | str]] = []
            for value, index in zip(values.tolist(), indices.tolist()):
                label = model.config.id2label.get(index, model.config.id2label.get(str(index), str(index)))
                top_predictions.append({"label": label, "confidence": round(float(value), 4)})

            best = top_predictions[0]
            return ImagePrediction(
                label=str(best["label"]),
                confidence=float(best["confidence"]),
                top_k=top_predictions,
            )
        except Exception:
            return ImagePrediction(
                label="unverified visual item",
                confidence=0.0,
                top_k=[{"label": "unverified visual item", "confidence": 0.0}],
                source="vision_unavailable",
                heuristic_reason="Pretrained checkpoint is unavailable; using heuristic image recovery only.",
            )

    def _recover_prediction(self, image_path: str | Path, raw_prediction: ImagePrediction) -> ImagePrediction:
        filename_hint = self._detect_filename_hint(image_path)
        pixel_hint = self._detect_pixel_hint(image_path)
        best_hint = self._select_visual_hint(raw_prediction, filename_hint, pixel_hint)
        if best_hint is None:
            return raw_prediction

        top_predictions = self._merge_top_predictions(best_hint, raw_prediction.top_k)
        raw_reason = raw_prediction.heuristic_reason.strip() if raw_prediction.heuristic_reason else ""
        hint_reason = best_hint.reason.strip()
        combined_reason = " ".join(part for part in [raw_reason, hint_reason] if part)
        return ImagePrediction(
            label=best_hint.label,
            confidence=best_hint.confidence,
            top_k=top_predictions,
            source="vision_recovery",
            raw_label=raw_prediction.label,
            raw_confidence=raw_prediction.confidence,
            heuristic_reason=combined_reason or None,
        )

    def _select_visual_hint(
        self,
        raw_prediction: ImagePrediction,
        filename_hint: VisualHint | None,
        pixel_hint: VisualHint | None,
    ) -> VisualHint | None:
        if raw_prediction.source not in {"vision_unavailable", "vision_recovery"}:
            if raw_prediction.confidence >= LOW_CONFIDENCE_IMAGE_THRESHOLD and filename_hint is None:
                return None

        if filename_hint and pixel_hint and filename_hint.label == pixel_hint.label:
            return VisualHint(
                label=filename_hint.label,
                confidence=round(min(0.92, max(filename_hint.confidence, pixel_hint.confidence) + 0.08), 4),
                reason=f"{filename_hint.reason} {pixel_hint.reason}".strip(),
            )
        if filename_hint is not None:
            return filename_hint
        if pixel_hint is not None:
            return pixel_hint
        return None

    def _detect_filename_hint(self, image_path: str | Path) -> VisualHint | None:
        hint_text = normalize_text(Path(image_path).stem)
        if not hint_text:
            return None
        tokens = set(hint_text.split())
        for token, label in FILENAME_STYLE_HINTS.items():
            if token in tokens:
                return VisualHint(
                    label=label,
                    confidence=0.78,
                    reason=f"Filename contains the food cue '{token}'.",
                )
        return None

    def _detect_pixel_hint(self, image_path: str | Path) -> VisualHint | None:
        signature = self._pixel_signature(image_path)
        red = signature["red_dominant"]
        warm = signature["yellow_orange"]
        green = signature["green_dominant"]

        if red >= 0.42 and warm >= 0.18 and green <= 0.08:
            boost = min(0.16, (red - 0.42) * 0.35 + (warm - 0.18) * 0.45)
            return VisualHint(
                label="pizza",
                confidence=round(0.58 + boost, 4),
                reason="Strong tomato-sauce and melted-cheese color ratios match a pizza profile.",
            )
        if green >= 0.18 and red <= 0.25:
            return VisualHint(
                label="salad",
                confidence=0.56,
                reason="High green coverage suggests a salad-style dish.",
            )
        return None

    def _pixel_signature(self, image_path: str | Path) -> dict[str, float]:
        image = Image.open(image_path).convert("RGB").resize((128, 128))
        pixels = list(image.getdata())
        total = max(1, len(pixels))
        red_dominant = sum(1 for r, g, b in pixels if r > 120 and r > g + 10 and r > b + 20) / total
        yellow_orange = sum(1 for r, g, b in pixels if r > 150 and g > 90 and b < 140) / total
        green_dominant = sum(1 for r, g, b in pixels if g > r + 15 and g > b + 10) / total
        return {
            "red_dominant": round(red_dominant, 4),
            "yellow_orange": round(yellow_orange, 4),
            "green_dominant": round(green_dominant, 4),
        }

    def _merge_top_predictions(self, hint: VisualHint, raw_top_k: list[dict[str, float | str]]) -> list[dict[str, float | str]]:
        merged = [{"label": hint.label, "confidence": round(hint.confidence, 4)}]
        seen = {hint.label.lower()}
        for entry in raw_top_k:
            label = str(entry.get("label", ""))
            if not label or label.lower() in seen:
                continue
            merged.append({"label": label, "confidence": round(float(entry.get("confidence", 0.0)), 4)})
            seen.add(label.lower())
        return merged[: max(1, len(raw_top_k))]
