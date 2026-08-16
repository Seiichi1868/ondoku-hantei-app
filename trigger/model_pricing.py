"""Vibe Speak Trigger 用 AI モデルの単価・性能スコア定義（1箇所で管理）。

flask_app/ai_model_pricing.py と同じ構成パターンを踏襲した独自コピー
（相互 import はしない）。価格改定時はこのファイルのみ更新する。
管理画面のバー表示・コスト概算は trigger/model_catalog.py がここを参照して算出する。
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

# Whisper（音声文字起こし）モデルの単価（$/分）。QA・スピーチ・音読の全STTで共通利用。
WHISPER_MODEL_PRICING: dict[str, dict] = {
    "whisper-1": {"label": "Whisper-1（高精度・既定）", "model": "whisper-1", "cost_per_min_usd": 0.006},
    "gpt-4o-mini-transcribe": {
        "label": "GPT-4o-mini-transcribe（低コスト）",
        "model": "gpt-4o-mini-transcribe",
        "cost_per_min_usd": 0.003,
    },
}

# TTS（音声合成）単価（$/1000文字）。tts-1 の公表単価に基づく概算。
TTS_MODEL_PRICING: dict[str, dict] = {
    "tts-1": {"label": "TTS-1（標準）", "model": "tts-1", "cost_per_1k_chars_usd": 0.015},
    "tts-1-hd": {"label": "TTS-1-HD（高音質）", "model": "tts-1-hd", "cost_per_1k_chars_usd": 0.030},
}
