"""VibeSpeak 用 AI モデル選択肢とコスパ／性能バーの算出。"""
from __future__ import annotations

from copy import deepcopy

from flask_app.ai_model_pricing import AI_MODEL_PRICING

DEFAULT_AI_MODEL_MODE = "4o-mini"


def _combined_price_per_1m(entry: dict) -> float:
    return (float(entry["input_price_per_1m"]) + float(entry["output_price_per_1m"])) / 2.0


def _cost_ratio(entry: dict) -> float:
    score = max(int(entry.get("performance_score", 1)), 1)
    return _combined_price_per_1m(entry) / score


def _normalize_cost_performance(ratio: float, min_ratio: float, max_ratio: float) -> int:
    span = max_ratio - min_ratio
    if span <= 0:
        return 3
    normalized = 1.0 - (ratio - min_ratio) / span
    return max(1, min(5, round(normalized * 4 + 1)))


def get_ai_model_options() -> dict[str, dict[str, str | int]]:
    """ai_model_pricing.py から選択肢を構築し、コスパ／性能バー（1–5）を付与して返す。"""
    raw = AI_MODEL_PRICING
    ratios = {mode_id: _cost_ratio(entry) for mode_id, entry in raw.items()}
    min_ratio = min(ratios.values())
    max_ratio = max(ratios.values())

    options: dict[str, dict[str, str | int]] = {}
    for mode_id, entry in raw.items():
        performance_score = int(entry["performance_score"])
        label = str(entry["label"])
        options[mode_id] = {
            "label": label,
            "hint": label,
            "model": str(entry["model"]),
            "cost_performance": _normalize_cost_performance(ratios[mode_id], min_ratio, max_ratio),
            "performance": performance_score,
        }
    return options


def resolve_ai_model_mode(mode: str | None = None, *, fallback_mode: str | None = None) -> str:
    options = get_ai_model_options()
    if mode in options:
        return mode
    if fallback_mode in options:
        return str(fallback_mode)
    return DEFAULT_AI_MODEL_MODE


def public_ai_model_modes() -> list[dict]:
    """管理画面 API 向け: 表示順は ai_model_pricing.py のキー順。"""
    options = get_ai_model_options()
    return [{"id": mode_id, **deepcopy(options[mode_id])} for mode_id in options]
