"""ジャッジ用AIモデルの単価・性能スコア定義と、コスパ／性能バーの算出。

単価と performance_score（1–5）は debate/judge_model_pricing.py に集約する。
画面のバー表示・コスト比較はこのモジュール経由で参照すること。
"""
from __future__ import annotations

from copy import deepcopy

from debate.judge_model_pricing import JUDGE_MODEL_PRICING

DEFAULT_JUDGE_MODEL_MODE = "5.6-luna"


def _load_raw_pricing() -> dict[str, dict]:
    return JUDGE_MODEL_PRICING


def _combined_price_per_1m(entry: dict) -> float:
    return (float(entry["input_price_per_1m"]) + float(entry["output_price_per_1m"])) / 2.0


def _cost_ratio(entry: dict) -> float:
    """価格 ÷ 性能スコア。値が小さいほどコスパが良い。"""
    score = max(int(entry.get("performance_score", 1)), 1)
    return _combined_price_per_1m(entry) / score


def _normalize_cost_performance(ratio: float, min_ratio: float, max_ratio: float) -> int:
    span = max_ratio - min_ratio
    if span <= 0:
        return 3
    normalized = 1.0 - (ratio - min_ratio) / span
    return max(1, min(5, round(normalized * 4 + 1)))


def get_judge_model_options() -> dict[str, dict]:
    """judge_model_pricing.py から選択肢を構築し、コスパ／性能バー（1–5）を付与して返す。"""
    raw = _load_raw_pricing()
    ratios = {mode_id: _cost_ratio(entry) for mode_id, entry in raw.items()}
    min_ratio = min(ratios.values())
    max_ratio = max(ratios.values())

    options: dict[str, dict] = {}
    for mode_id, entry in raw.items():
        performance_score = int(entry["performance_score"])
        options[mode_id] = {
            "label": str(entry["label"]),
            "model": str(entry["model"]),
            "input_price_per_1m": float(entry["input_price_per_1m"]),
            "output_price_per_1m": float(entry["output_price_per_1m"]),
            "performance_score": performance_score,
            "cost_performance": _normalize_cost_performance(ratios[mode_id], min_ratio, max_ratio),
            "performance": performance_score,
        }
    return options


def resolve_judge_model_mode(mode: str | None = None, *, fallback_mode: str | None = None) -> str:
    options = get_judge_model_options()
    if mode in options:
        return mode
    if fallback_mode in options:
        return str(fallback_mode)
    return DEFAULT_JUDGE_MODEL_MODE


def resolve_judge_model_id(mode: str | None = None) -> str:
    options = get_judge_model_options()
    selected = resolve_judge_model_mode(mode)
    return str(options[selected]["model"])


def resolve_judge_model_metadata(mode: str | None = None) -> dict:
    """ジャッジ結果に保存するモデルID・単価情報。"""
    options = get_judge_model_options()
    selected = resolve_judge_model_mode(mode)
    entry = options[selected]
    return {
        "mode_id": selected,
        "model": entry["model"],
        "input_price_per_1m": entry["input_price_per_1m"],
        "output_price_per_1m": entry["output_price_per_1m"],
        "performance_score": entry["performance_score"],
    }


def public_judge_model_modes() -> list[dict]:
    """管理画面API向け: 表示順は judge_model_pricing.py のキー順。"""
    options = get_judge_model_options()
    return [{"id": mode_id, **deepcopy(options[mode_id])} for mode_id in options]
