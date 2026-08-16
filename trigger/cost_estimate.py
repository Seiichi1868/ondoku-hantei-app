"""1セッションあたりのAPIコスト概算（管理画面表示用）。

質問数・トピック数を増やすほど、TTS・Whisper・評価用GPT呼び出しの回数が線形に
増えることを可視化するための簡易試算。実測値ではなく目安。
"""
from trigger.config import TASK_KEYS
from trigger.model_catalog import estimate_chat_cost_usd
from trigger.model_pricing import TTS_MODEL_PRICING, WHISPER_MODEL_PRICING

# 簡易トークン/文字数/秒数の想定値（実測に基づき将来調整可能）
ASSUMED = {
    "script_translate": {"input_tokens": 400, "output_tokens": 500},
    "pronunciation_eval": {"input_tokens": 350, "output_tokens": 250},
    "qa_generate": {"input_tokens": 400, "output_tokens": 300},
    "qa_evaluate": {"input_tokens": 350, "output_tokens": 200},
    "speech_topic": {"input_tokens": 400, "output_tokens": 300},
    "speech_evaluate": {"input_tokens": 400, "output_tokens": 250},
    "report_final": {"input_tokens": 600, "output_tokens": 400},
    "sample_tts_chars": 400,
    "question_tts_chars": 80,
    "topic_tts_chars": 100,
    "readaloud_sec": 25,
    "qa_answer_sec": 15,
    "speech_sec": 60,
}

USD_JPY = 155.0


def estimate_session_cost_usd(settings: dict) -> dict:
    task_modes = settings.get("task_model_modes") or {}
    qa_count = int(settings.get("qa_question_count", 3))
    topic_count = int(settings.get("speech_topic_count", 1))
    topic_tts_enabled = bool(settings.get("speech_topic_tts_enabled", False))
    whisper_model = settings.get("whisper_model", "whisper-1")

    breakdown = {}

    call_counts = {
        "script_translate": 1,
        "pronunciation_eval": 1,
        "qa_generate": 1,
        "qa_evaluate": qa_count,
        "speech_topic": 1,
        "speech_evaluate": topic_count,
        "report_final": 1,
    }
    chat_total = 0.0
    for key in TASK_KEYS:
        assumed = ASSUMED[key]
        per_call = estimate_chat_cost_usd(task_modes.get(key), assumed["input_tokens"], assumed["output_tokens"])
        count = call_counts[key]
        cost = per_call * count
        chat_total += cost
        breakdown[key] = {"per_call_usd": round(per_call, 5), "count": count, "subtotal_usd": round(cost, 5)}

    tts_entry = TTS_MODEL_PRICING.get("tts-1", {"cost_per_1k_chars_usd": 0.015})
    tts_chars = ASSUMED["sample_tts_chars"] + ASSUMED["question_tts_chars"] * qa_count
    if topic_tts_enabled:
        tts_chars += ASSUMED["topic_tts_chars"] * topic_count
    tts_cost = (tts_chars / 1000.0) * tts_entry["cost_per_1k_chars_usd"]

    whisper_entry = WHISPER_MODEL_PRICING.get(whisper_model, WHISPER_MODEL_PRICING["whisper-1"])
    whisper_sec = ASSUMED["readaloud_sec"] + ASSUMED["qa_answer_sec"] * qa_count + ASSUMED["speech_sec"] * topic_count
    whisper_cost = (whisper_sec / 60.0) * whisper_entry["cost_per_min_usd"]

    total_usd = chat_total + tts_cost + whisper_cost
    return {
        "chat_breakdown": breakdown,
        "chat_total_usd": round(chat_total, 4),
        "tts_total_usd": round(tts_cost, 4),
        "whisper_total_usd": round(whisper_cost, 4),
        "total_usd": round(total_usd, 4),
        "total_jpy": round(total_usd * USD_JPY),
        "qa_question_count": qa_count,
        "speech_topic_count": topic_count,
    }
