"""セッション／台本／QA／スピーチ／最終評価のドキュメント（dict）ファクトリ。

level_check/models.py と同じ考え方（ORM を使わず dict ファクトリで JSON
ドキュメントのスキーマを表現する）を踏襲した独自実装。
"""
import uuid
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def _now_iso() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def new_session(*, student_info: dict, theme_id: str, theme_title: str) -> dict:
    return {
        "session_id": uuid.uuid4().hex,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "completed_at": None,
        "status": "script",  # script -> sample -> readaloud -> qa -> speech -> report -> done
        "student_info": {
            "class_name": str(student_info.get("class_name") or ""),
            "number": str(student_info.get("number") or ""),
            "name": str(student_info.get("name") or ""),
        },
        "theme_id": theme_id,
        "theme_title": theme_title,
        # scripts テーブル相当（1セッション1台本）
        "script": {
            "mode": None,
            "input_text": "",
            "output_text": "",
            "notes": "",
            "confirmed": False,
        },
        "model_snapshot": {},
        # pronunciation_results テーブル相当（1セッション1回の音読評価）
        "pronunciation_result": None,
        # qa_items テーブル相当
        "qa_items": [],
        # speech_items テーブル相当
        "speech_items": [],
        # final_evaluations テーブル相当
        "final_evaluation": None,
        "cost_usd_total": 0.0,
    }


def new_qa_item(*, question_text: str, question_audio_url: str = "") -> dict:
    return {
        "id": uuid.uuid4().hex[:10],
        "question_text": question_text,
        "question_audio_url": question_audio_url,
        "student_answer_audio_url": "",
        "student_answer_transcript": "",
        "evaluation": None,
        "created_at": _now_iso(),
    }


def new_speech_item(*, topic_text: str, topic_audio_url: str = "") -> dict:
    return {
        "id": uuid.uuid4().hex[:10],
        "topic_text": topic_text,
        "topic_audio_url": topic_audio_url,
        "student_audio_url": "",
        "student_transcript": "",
        "evaluation": None,
        "created_at": _now_iso(),
    }


def touch(session: dict) -> dict:
    session["updated_at"] = _now_iso()
    return session
