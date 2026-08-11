"""/public/ 配下向け Kill-Switch の状態管理。

Redis 等の追加インフラは使わず、既存のファイルシステム（Render の永続ディスク
がマウントされている ``data/`` ディレクトリ）に小さな JSON ファイルを置くだけで
稼働中/停止中の状態を保持する。

Render は複数プロセス（gunicorn workers）で動くため、プロセス内メモリの
キャッシュは使わず、毎回ファイルから読み直すことで即時反映を保証する。
書き込み時は ``fcntl`` によるファイルロックで多重書き込みを防ぐ（POSIX のみ。
本番の Render / macOS 開発環境はいずれも POSIX なので問題ない）。
"""

import json
import threading
from datetime import datetime
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows 等 fcntl が無い環境向けフォールバック
    fcntl = None

DATA_DIR = Path(
    __file__
).resolve().parent.parent.parent / "data"
STATUS_FILE = DATA_DIR / "service_status.json"

_thread_lock = threading.Lock()

DEFAULT_STATUS = {
    "public_enabled": True,
    "updated_at": "",
    "updated_by": "",
}


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _normalize(raw: dict | None) -> dict:
    if not isinstance(raw, dict):
        return dict(DEFAULT_STATUS)
    return {
        "public_enabled": bool(raw.get("public_enabled", True)),
        "updated_at": str(raw.get("updated_at") or ""),
        "updated_by": str(raw.get("updated_by") or ""),
    }


def get_public_status() -> dict:
    """常にファイルから読み直して最新状態を返す（プロセス間で即時反映するため）。"""
    _ensure_data_dir()
    if not STATUS_FILE.is_file():
        return dict(DEFAULT_STATUS)

    with _thread_lock:
        try:
            with STATUS_FILE.open("r", encoding="utf-8") as handle:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
                try:
                    raw = json.load(handle)
                finally:
                    if fcntl is not None:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except (OSError, json.JSONDecodeError):
            return dict(DEFAULT_STATUS)

    return _normalize(raw)


def is_public_enabled() -> bool:
    return get_public_status()["public_enabled"]


def set_public_status(enabled: bool, admin_user: str = "admin") -> dict:
    _ensure_data_dir()
    data = {
        "public_enabled": bool(enabled),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "updated_by": str(admin_user or "admin"),
    }

    with _thread_lock:
        STATUS_FILE.touch(exist_ok=True)
        with STATUS_FILE.open("r+", encoding="utf-8") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                handle.seek(0)
                handle.truncate()
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.flush()
            finally:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    return data
