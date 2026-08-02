"""level_check 独自のデータモデル生成処理（news_app / debate とは別テーブル・別スキーマ）。"""
import uuid
from datetime import datetime, timedelta, timezone

from level_check.config import score_track_for_category

JST = timezone(timedelta(hours=9))


def now_iso() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def new_part(
    *,
    task_type: str,
    question_id: str,
    question_text: str = "",
    prompt_text: str = "",
    stimulus_text: str = "",
    target_text: str = "",
    expected_answer: str = "",
    prompt_audio_url: str = "",
    time_limit_sec: int | None = None,
) -> dict:
    category = str(task_type or "").strip().upper()
    return {
        "part_id": uuid.uuid4().hex[:10],
        "task_type": category,
        "category": category,
        "score_track": score_track_for_category(category),
        "question_id": question_id,
        "question_text": question_text,
        "prompt_text": prompt_text,
        "stimulus_text": stimulus_text,
        "target_text": target_text,
        "expected_answer": expected_answer,
        "prompt_audio_url": prompt_audio_url,
        "time_limit_sec": time_limit_sec,
        "audio_url": "",
        "transcript": "",
        "transcript_error": "",
        "response_latency_ms": None,
        "start_time": None,
        "end_time": None,
        "status": "not_started",
        "scores": {},
        "comments": {},
        "weighted_total": None,
        "score_90": None,
        "cefr_band": None,
    }


def new_session(*, info_level: str, student_info: dict, ai_model_mode: str, parts: list[dict]) -> dict:
    return {
        "session_id": str(uuid.uuid4()),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "info_level": info_level,
        "student_info": {
            "class_name": str(student_info.get("class_name") or "").strip(),
            "number": str(student_info.get("number") or "").strip(),
            "name": str(student_info.get("name") or "").strip(),
        },
        "ai_model_mode": ai_model_mode,
        "parts": parts,
        "status": "in_progress",
        "overall": empty_overall(),
    }


def empty_overall() -> dict:
    return {
        "speaking_level_score": None,
        "cefr_band": None,
        "speaking_subscore": None,
        "listening_subscore": None,
        "speaking_axes": {},
        "listening_axes": {},
        "category_scores": {},
    }
