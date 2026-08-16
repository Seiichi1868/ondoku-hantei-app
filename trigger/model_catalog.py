"""trigger/model_pricing.py から選択肢を構築し、コスパ／性能バー（1-5）を付与する。

flask_app/ai_models.py と同じ考え方の独自コピー（相互 import なし）。
"""
from __future__ import annotations

from copy import deepcopy

from trigger.model_pricing import AI_MODEL_PRICING

DEFAULT_TASK_MODEL_MODE = "4o-mini"


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


def get_ai_model_options() -> dict[str, dict]:
    raw = AI_MODEL_PRICING
    ratios = {mode_id: _cost_ratio(entry) for mode_id, entry in raw.items()}
    min_ratio = min(ratios.values())
    max_ratio = max(ratios.values())

    options: dict[str, dict] = {}
    for mode_id, entry in raw.items():
        label = str(entry["label"])
        options[mode_id] = {
            "label": label,
            "model": str(entry["model"]),
            "input_price_per_1m": float(entry["input_price_per_1m"]),
            "output_price_per_1m": float(entry["output_price_per_1m"]),
            "cost_performance": _normalize_cost_performance(ratios[mode_id], min_ratio, max_ratio),
            "performance": int(entry["performance_score"]),
        }
    return options


def resolve_ai_model_mode(mode: str | None = None) -> str:
    options = get_ai_model_options()
    if mode in options:
        return mode
    return DEFAULT_TASK_MODEL_MODE


def resolve_ai_model_id(mode: str | None = None) -> str:
    return get_ai_model_options()[resolve_ai_model_mode(mode)]["model"]


def public_ai_model_modes() -> list[dict]:
    options = get_ai_model_options()
    return [{"id": mode_id, **deepcopy(options[mode_id])} for mode_id in options]


def estimate_chat_cost_usd(mode: str, input_tokens: int, output_tokens: int) -> float:
    entry = AI_MODEL_PRICING.get(resolve_ai_model_mode(mode), AI_MODEL_PRICING[DEFAULT_TASK_MODEL_MODE])
    return (input_tokens / 1_000_000.0) * entry["input_price_per_1m"] + (
        output_tokens / 1_000_000.0
    ) * entry["output_price_per_1m"]
