"""ジャッジ実行のバックグラウンド処理（transcription_jobs.pyと同様の方式）。"""
import logging
import threading

from debate.judge import run_judge
from debate.models import now_iso
from debate.storage import get_session_lock, load_session, save_session

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

            _pool = ThreadPool(2)
            logger.info("debate judge: using gevent.threadpool.ThreadPool")
        except Exception as exc:  # noqa: BLE001
            logger.warning("debate judge: gevent threadpool unavailable (%s)", exc)
            _pool = False  # sentinel: use threading fallback
        return _pool


def run_judge_job(session_id: str) -> None:
    """LLMでジャッジを実行し、完了後にセッションJSONへ反映する。"""
    error_message = ""
    result = None
    try:
        session = load_session(session_id)
        if not session:
            return
        result = run_judge(session)
    except RuntimeError as exc:
        error_message = str(exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Judge failed session=%s: %s", session_id, exc)
        error_message = (
            f"ジャッジの実行に失敗しました（{type(exc).__name__}）。時間をおいて再実行してください。"
        )

    with get_session_lock(session_id):
        session = load_session(session_id)
        if not session:
            return
        judge_result = session.get("judge_result") or {}
        if judge_result.get("status") != "judging":
            # 再実行や別操作によって上書きされていたら何もしない
            return

        if error_message:
            judge_result["status"] = "error"
            judge_result["error"] = error_message
        else:
            judge_result.update(result)
            judge_result["status"] = "done"
            judge_result["error"] = ""
            judge_result["judged_at"] = now_iso()

        session["judge_result"] = judge_result
        save_session(session)
        logger.info(
            "Judge finished session=%s status=%s error=%s",
            session_id,
            judge_result["status"],
            bool(error_message),
        )


def start_judge_job(session_id: str) -> None:
    """非ブロッキングでジャッジジョブを起動する。"""
    pool = _get_pool()
    if pool and pool is not False:
        pool.spawn(run_judge_job, session_id)
        return
    thread = threading.Thread(
        target=run_judge_job,
        args=(session_id,),
        daemon=True,
        name="debate-judge",
    )
    thread.start()
