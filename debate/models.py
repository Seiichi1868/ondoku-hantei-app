"""データスキーマ（PDA_debate_app_spec.md 「1. データスキーマ」）に準拠したデータ生成処理。"""
import uuid
from datetime import datetime, timedelta, timezone

from debate.config import PART_DEFS, PART_ORDER

JST = timezone(timedelta(hours=9))


def now_iso() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def new_part(part: str) -> dict:
    defaults = PART_DEFS[part]
    return {
        "part": part,
        "side": defaults["side"],
        "part_order": defaults["part_order"],
        "speaker_name": "",
        "audio_url": "",
        "transcript_raw": "",
        "transcript_edited": "",
        "transcript_error": "",
        "transcription_mode": "",
        "transcribe_retry_at": None,
        "start_time": None,
        "end_time": None,
        "time_limit_sec": defaults["time_limit_sec"],
        "elapsed_sec": None,
        "status": "not_started",
    }


def new_judge_result() -> dict:
    """ジャッジ結果の空の器（status: idle→judging→done/error）。"""
    return {
        "status": "idle",
        "error": "",
        "model": "",
        "transcription_mode": "",
        "started_at": None,
        "judged_at": None,
        "argument_flow": [],
        "winner": None,
        "standing_point_count": {"gov": 0, "opp": 0},
        "scores": {
            "content": {"reasoning": None, "examples": None, "relevance": None},
            "method": {
                "rebuttal_accuracy": None,
                "flow_consistency": None,
                "role_fulfillment": None,
            },
        },
        "overall_feedback": "",
        "part_feedback": [{"part": part, "comment": ""} for part in PART_ORDER],
    }


def new_session(motion: str, speaker_name: str = "") -> dict:
    parts = [new_part(part) for part in PART_ORDER]
    if speaker_name:
        for part in parts:
            part["speaker_name"] = speaker_name

    return {
        "session_id": str(uuid.uuid4()),
        "motion": motion.strip(),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "parts": parts,
        "judge_result": new_judge_result(),
    }
