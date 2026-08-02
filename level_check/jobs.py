"""録音アップロード後のバックグラウンド処理（文字起こし→採点）。

本番は gunicorn + gevent（monkey.patch_all）のため、通常の threading.Thread では
OpenAI 呼び出しの同期 HTTP がワーカー全体を塞ぐ。gevent.threadpool（OS スレッド）で実行する
（debate/transcription_jobs.py と同じ方式の独立実装）。
"""
import logging
import threading
from pathlib import Path

from level_check.audio_convert import normalize_audio_file
from level_check.config import resolve_ai_model_id
from level_check.models import now_iso
from level_check.scoring.evaluator import evaluate_response
from level_check.storage import get_part, get_session_lock, load_session, load_settings, save_session, save_submission
from level_check.transcription import transcribe_audio

logger = logging.getLogger(__name__)

_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    global _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        try:
            from gevent.threadpool import ThreadPool

            _pool = ThreadPool(4)
            logger.info("level_check jobs: using gevent.threadpool.ThreadPool")
        except Exception as exc:  # noqa: BLE001
            logger.warning("level_check jobs: gevent threadpool unavailable (%s)", exc)
            _pool = False
        return _pool


def _finalize_session_if_complete(session: dict) -> None:
    parts = session.get("parts", [])
    if not parts or any(p.get("status") not in ("done", "error") for p in parts):
        return

    from level_check.scoring.rubric import band_for_score

    scored_parts = [p for p in parts if p.get("weighted_total") is not None]
    overall_total = None
    overall_band = None
    if scored_parts:
        overall_total = round(sum(p["weighted_total"] for p in scored_parts) / len(scored_parts), 2)
        overall_band = band_for_score(overall_total)

    session["overall"] = {"weighted_total": overall_total, "cefr_band": overall_band}
    session["status"] = "done"
    save_session(session)

    save_submission(
        {
            "session_id": session["session_id"],
            "info_level": session.get("info_level"),
            "student_info": session.get("student_info"),
            "ai_model_mode": session.get("ai_model_mode"),
            "overall": session["overall"],
            "task_results": [
                {
                    "task_type": p.get("task_type"),
                    "question_id": p.get("question_id"),
                    "question_text": p.get("question_text"),
                    "target_text": p.get("target_text"),
                    "transcript": p.get("transcript"),
                    "response_latency_ms": p.get("response_latency_ms"),
                    "scores": p.get("scores"),
                    "comments": p.get("comments"),
                    "weighted_total": p.get("weighted_total"),
                    "cefr_band": p.get("cefr_band"),
                    "status": p.get("status"),
                    "transcript_error": p.get("transcript_error"),
                }
                for p in parts
            ],
        }
    )


def run_process_part_job(session_id: str, part_id: str, file_path: Path) -> None:
    error_message = ""
    transcript = ""
    eval_result = None

    try:
        if not file_path.is_file():
            raise RuntimeError("音声ファイルが見つかりません。")
        normalized_path = normalize_audio_file(file_path)
        transcript = transcribe_audio(normalized_path)
        if not transcript.strip():
            raise RuntimeError("文字起こし結果が空でした。発話が録音できているかご確認ください。")
    except RuntimeError as exc:
        error_message = str(exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Transcription failed session=%s part=%s: %s", session_id, part_id, exc)
        error_message = f"文字起こしに失敗しました（{type(exc).__name__}）。もう一度録音してください。"

    with get_session_lock(session_id):
        session = load_session(session_id)
        if not session:
            return
        part = get_part(session, part_id)
        if not part or part.get("status") != "transcribing":
            return

        if error_message:
            part["transcript_error"] = error_message
            part["status"] = "error"
            save_session(session)
            _finalize_session_if_complete(session)
            return

        part["transcript"] = transcript
        part["status"] = "scoring"
        save_session(session)

    settings = load_settings()
    model_mode = session.get("ai_model_mode") or settings.get("ai_model_mode")
    try:
        from level_check.config import get_openai_api_key

        eval_result = evaluate_response(
            task_type=part["task_type"],
            question_text=part.get("question_text", ""),
            target_text=part.get("target_text", ""),
            transcript=transcript,
            response_latency_ms=part.get("response_latency_ms"),
            model=resolve_ai_model_id(model_mode),
            api_key=get_openai_api_key(),
            rubric_weights=settings.get("rubric_weights"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scoring failed session=%s part=%s: %s", session_id, part_id, exc)
        error_message = f"採点に失敗しました（{type(exc).__name__}）。"

    with get_session_lock(session_id):
        session = load_session(session_id)
        if not session:
            return
        part = get_part(session, part_id)
        if not part or part.get("status") != "scoring":
            return

        if error_message:
            part["transcript_error"] = error_message
            part["status"] = "error"
        else:
            part["scores"] = eval_result["scores"]
            part["comments"] = eval_result["comments"]
            part["weighted_total"] = eval_result["weighted_total"]
            part["cefr_band"] = eval_result["cefr_band"]
            part["status"] = "done"
        part["end_time"] = part.get("end_time") or now_iso()
        save_session(session)
        logger.info(
            "level_check part finished session=%s part=%s status=%s",
            session_id,
            part_id,
            part["status"],
        )
        _finalize_session_if_complete(session)


def start_process_part_job(session_id: str, part_id: str, file_path: Path) -> None:
    pool = _get_pool()
    if pool and pool is not False:
        pool.spawn(run_process_part_job, session_id, part_id, file_path)
        return
    thread = threading.Thread(
        target=run_process_part_job,
        args=(session_id, part_id, file_path),
        daemon=True,
        name=f"level-check-process-{part_id}",
    )
    thread.start()
