"""VibeSpeak 用 AI モデルの単価・性能スコア定義（1箇所で管理）。

価格改定時はこのファイルのみ更新する。画面のバー表示・コスト計算は
flask_app/ai_models.py がここを参照して動的に算出する。
"""

AI_MODEL_PRICING: dict[str, dict] = {
    "5.6-luna": {
        "label": "gpt-5.6-luna",
        "model": "gpt-5.6-luna",
        "input_price_per_1m": 0.20,
        "output_price_per_1m": 1.20,
        "performance_score": 4,
    },
    "5.6-terra": {
        "label": "gpt-5.6-terra",
        "model": "gpt-5.6-terra",
        "input_price_per_1m": 2.00,
        "output_price_per_1m": 12.00,
        "performance_score": 4,
    },
    "5.6-sol": {
        "label": "gpt-5.6-sol",
        "model": "gpt-5.6-sol",
        "input_price_per_1m": 5.00,
        "output_price_per_1m": 30.00,
        "performance_score": 5,
    },
    "4o-mini": {
        "label": "gpt-4o-mini",
        "model": "gpt-4o-mini",
        "input_price_per_1m": 0.15,
        "output_price_per_1m": 0.60,
        "performance_score": 3,
    },
    "5.4-mini": {
        "label": "gpt-5.4-mini",
        "model": "gpt-5.4-mini",
        "input_price_per_1m": 0.40,
        "output_price_per_1m": 1.60,
        "performance_score": 4,
    },
    "5.4-nano": {
        "label": "gpt-5.4-nano",
        "model": "gpt-5.4-nano",
        "input_price_per_1m": 0.10,
        "output_price_per_1m": 0.40,
        "performance_score": 2,
    },
}
