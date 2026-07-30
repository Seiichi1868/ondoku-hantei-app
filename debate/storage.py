"""セッションデータの永続化（JSONファイル、data/debate/sessions/<session_id>.json）。

ブラウザのリロードや通信断でもデータが失われないよう、各操作の完了時点で
逐次ディスクへ保存する（仕様書「エラーハンドリング」節に対応）。
"""
import json
import shutil
import threading
from pathlib import Path

from debate.config import AUDIO_DIR, SESSIONS_DIR, ensure_dirs

_lock = threading.Lock()

# パートごとの非同期文字起こし（バックグラウンドスレッド）と、通常のリクエスト処理
# （録音開始・確定・リセット等）が同じセッションJSONを並行して読み書きしても
# 更新内容を失わないよう、セッションIDごとに排他ロックを提供する。
_session_locks: dict[str, threading.Lock] = {}
_session_locks_guard = threading.Lock()


def _safe_id(session_id: str) -> str:
    return "".join(c for c in session_id if c.isalnum() or c == "-")


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{_safe_id(session_id)}.json"


def get_session_lock(session_id: str) -> threading.Lock:
    """「読み込み→一部更新→書き込み」を一連の操作として直列化するためのロック。"""
    safe_id = _safe_id(session_id)
    with _session_locks_guard:
        lock = _session_locks.get(safe_id)
        if lock is None:
            lock = threading.Lock()
            _session_locks[safe_id] = lock
        return lock


def save_session(session: dict) -> dict:
    from debate.models import now_iso

    session["updated_at"] = now_iso()
    ensure_dirs()
    path = _session_path(session["session_id"])
    with _lock:
        tmp_path = path.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(session, handle, ensure_ascii=False, indent=2)
        tmp_path.replace(path)
    return session


def load_session(session_id: str) -> dict | None:
    ensure_dirs()
    path = _session_path(session_id)
    if not path.is_file():
        return None
    with _lock:
        try:
            with path.open(encoding="utf-8") as handle:
                return json.load(handle)
        except (json.JSONDecodeError, OSError):
            return None


def get_part(session: dict, part: str) -> dict | None:
    for part_data in session.get("parts", []):
        if part_data.get("part") == part:
            return part_data
    return None


def delete_session(session_id: str) -> bool:
    """セッションのJSONと音声ファイル一式を削除する（管理画面からの削除用）。"""
    ensure_dirs()
    safe_id = _safe_id(session_id)
    path = SESSIONS_DIR / f"{safe_id}.json"
    with _lock:
        existed = path.is_file()
        path.unlink(missing_ok=True)
    shutil.rmtree(AUDIO_DIR / safe_id, ignore_errors=True)
    return existed


def list_sessions(limit: int = 10) -> list[dict]:
    """保存済みセッション一覧（論題入力画面・管理画面用）。"""
    ensure_dirs()
    files = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    summaries = []
    for path in files[:limit]:
        try:
            mtime = path.stat().st_mtime
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            continue

        parts = data.get("parts", [])
        confirmed = sum(1 for part in parts if part.get("status") == "confirmed")
        in_progress = sum(
            1
            for part in parts
            if part.get("status") in ("recording", "transcribing", "needs_review")
        )
        updated_at = data.get("updated_at") or data.get("created_at") or ""
        if not updated_at and mtime:
            from datetime import datetime, timedelta, timezone

            jst = timezone(timedelta(hours=9))
            updated_at = datetime.fromtimestamp(mtime, tz=jst).isoformat(timespec="seconds")

        judge_result = data.get("judge_result") or {}
        summaries.append(
            {
                "session_id": data.get("session_id"),
                "motion": data.get("motion"),
                "created_at": data.get("created_at"),
                "updated_at": updated_at,
                "confirmed_parts": confirmed,
                "in_progress_parts": in_progress,
                "total_parts": len(parts),
                "judge_status": judge_result.get("status", "idle"),
                "judge_winner": judge_result.get("winner"),
                "judge_model": judge_result.get("model", ""),
                "judge_transcription_mode": judge_result.get("transcription_mode", ""),
            }
        )
    return summaries
