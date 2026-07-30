"""セッションデータの永続化（JSONファイル、data/debate/sessions/<session_id>.json）。

ブラウザのリロードや通信断でもデータが失われないよう、各操作の完了時点で
逐次ディスクへ保存する（仕様書「エラーハンドリング」節に対応）。
"""
import json
import threading
from pathlib import Path

from debate.config import SESSIONS_DIR, ensure_dirs

_lock = threading.Lock()


def _safe_id(session_id: str) -> str:
    return "".join(c for c in session_id if c.isalnum() or c == "-")


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{_safe_id(session_id)}.json"


def save_session(session: dict) -> dict:
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


def list_sessions(limit: int = 10) -> list[dict]:
    """論題入力画面に表示する最近のセッション一覧（続きから再開できるように）。"""
    ensure_dirs()
    files = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    summaries = []
    for path in files[:limit]:
        try:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            continue

        parts = data.get("parts", [])
        confirmed = sum(1 for part in parts if part.get("status") == "confirmed")
        summaries.append(
            {
                "session_id": data.get("session_id"),
                "motion": data.get("motion"),
                "created_at": data.get("created_at"),
                "confirmed_parts": confirmed,
                "total_parts": len(parts),
            }
        )
    return summaries
