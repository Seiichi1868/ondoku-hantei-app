"""trigger/model_pricing.py から選択肢を構築し、コスト／性能バー（各1-5）を付与する。

flask_app/ai_models.py と同じ考え方の独自コピー（相互 import なし）。
コストと性能は別々の指標として算出する（まとめた「コスパ」1本ではなく、
コスト比較・性能比較をそれぞれ独立して行えるようにする）。
"""
from __future__ import annotations

from copy import deepcopy

from trigger.model_pricing import AI_MODEL_PRICING

DEFAULT_TASK_MODEL_MODE = "4o-mini"


def _combined_price_per_1m(entry: dict) -> float:
    return (float(entry["input_price_per_1m"]) + float(entry["output_price_per_1m"])) / 2.0


def _normalize_cost_score(price: float, min_price: float, max_price: float) -> int:
    """価格が安いほど高スコア（5）になるよう 1-5 に正規化する。"""
    span = max_price - min_price
    if span <= 0:
        return 3
    normalized = 1.0 - (price - min_price) / span
    return max(1, min(5, round(normalized * 4 + 1)))


def get_ai_model_options() -> dict[str, dict]:
    raw = AI_MODEL_PRICING
    prices = {mode_id: _combined_price_per_1m(entry) for mode_id, entry in raw.items()}
    min_price = min(prices.values())
    max_price = max(prices.values())

    options: dict[str, dict] = {}
    for mode_id, entry in raw.items():
        label = str(entry["label"])
        options[mode_id] = {
            "label": label,
            "model": str(entry["model"]),
            "input_price_per_1m": float(entry["input_price_per_1m"]),
            "output_price_per_1m": float(entry["output_price_per_1m"]),
            "cost_score": _normalize_cost_score(prices[mode_id], min_price, max_price),
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
