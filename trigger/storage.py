"""JSON ファイルによる永続化（trigger 独自。他アプリとは別ファイル・別スキーマ）。

- trigger_settings.json     : AIモデル選択・問題数/トピック数・スピーチ音声設定など
- trigger_themes.json       : テーマプール（管理画面で編集）
- trigger_students.json     : 生徒名簿（roster）
- trigger_submissions.json  : 完了済みセッションの最終評価サマリ
- sessions/<id>.json        : 進行中〜完了直後のセッション本体
"""
import io
import json
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import openpyxl

from trigger.config import (
    DEFAULT_QA_QUESTION_COUNT,
    DEFAULT_SPEECH_TOPIC_COUNT,
    DEFAULT_SPEECH_TOPIC_TTS_ENABLED,
    DEFAULT_STUDENT_INFO_REQUIRED,
    DEFAULT_TASK_MODEL_MODES,
    DEFAULT_VERSANT_WEIGHTS,
    QA_QUESTION_COUNT_RANGE,
    SESSIONS_DIR,
    SETTINGS_FILE,
    SPEECH_TOPIC_COUNT_RANGE,
    STUDENTS_FILE,
    SUBMISSIONS_FILE,
    TASK_KEYS,
    THEMES_FILE,
    DEFAULT_WHISPER_MODEL,
    ensure_dirs,
)
from trigger.model_catalog import resolve_ai_model_mode

_lock = threading.Lock()
_session_locks: dict[str, threading.Lock] = {}
_session_locks_guard = threading.Lock()

JST = timezone(timedelta(hours=9))


def _now_iso() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def _read_json(path, default):
    if not path.is_file():
        return deepcopy(default)
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return deepcopy(default)


def _write_json(path, data) -> None:
    ensure_dirs()
    tmp_path = path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


# ── 設定 ────────────────────────────────────────────────────

DEFAULT_SETTINGS = {
    "task_model_modes": dict(DEFAULT_TASK_MODEL_MODES),
    "whisper_model": DEFAULT_WHISPER_MODEL,
    "qa_question_count": DEFAULT_QA_QUESTION_COUNT,
    "speech_topic_count": DEFAULT_SPEECH_TOPIC_COUNT,
    "speech_topic_tts_enabled": DEFAULT_SPEECH_TOPIC_TTS_ENABLED,
    "student_info_required": DEFAULT_STUDENT_INFO_REQUIRED,
    "versant_weights": dict(DEFAULT_VERSANT_WEIGHTS),
}


def _normalize_task_model_modes(raw) -> dict:
    result = dict(DEFAULT_TASK_MODEL_MODES)
    if not isinstance(raw, dict):
        return result
    for key in TASK_KEYS:
        result[key] = resolve_ai_model_mode(raw.get(key))
    return result


def _normalize_versant_weights(raw: dict | None) -> dict:
    weights = {}
    for key, default in DEFAULT_VERSANT_WEIGHTS.items():
        try:
            value = float((raw or {}).get(key, default))
        except (TypeError, ValueError):
            value = default
        weights[key] = max(0.0, value)
    total = sum(weights.values())
    if total <= 0:
        return dict(DEFAULT_VERSANT_WEIGHTS)
    return {key: value / total for key, value in weights.items()}


def _normalize_settings(raw: dict | None) -> dict:
    data = deepcopy(DEFAULT_SETTINGS)
    if not isinstance(raw, dict):
        return data

    data["task_model_modes"] = _normalize_task_model_modes(raw.get("task_model_modes"))
    data["whisper_model"] = str(raw.get("whisper_model") or DEFAULT_WHISPER_MODEL)

    try:
        qa_count = int(raw.get("qa_question_count", DEFAULT_QA_QUESTION_COUNT))
    except (TypeError, ValueError):
        qa_count = DEFAULT_QA_QUESTION_COUNT
    data["qa_question_count"] = max(QA_QUESTION_COUNT_RANGE[0], min(QA_QUESTION_COUNT_RANGE[1], qa_count))

    try:
        topic_count = int(raw.get("speech_topic_count", DEFAULT_SPEECH_TOPIC_COUNT))
    except (TypeError, ValueError):
        topic_count = DEFAULT_SPEECH_TOPIC_COUNT
    data["speech_topic_count"] = max(
        SPEECH_TOPIC_COUNT_RANGE[0], min(SPEECH_TOPIC_COUNT_RANGE[1], topic_count)
    )

    data["speech_topic_tts_enabled"] = bool(raw.get("speech_topic_tts_enabled", DEFAULT_SPEECH_TOPIC_TTS_ENABLED))
    data["student_info_required"] = bool(raw.get("student_info_required", DEFAULT_STUDENT_INFO_REQUIRED))
    data["versant_weights"] = _normalize_versant_weights(raw.get("versant_weights"))
    return data


def load_settings() -> dict:
    ensure_dirs()
    with _lock:
        return _normalize_settings(_read_json(SETTINGS_FILE, DEFAULT_SETTINGS))


def save_settings(data: dict) -> dict:
    normalized = _normalize_settings(data)
    with _lock:
        _write_json(SETTINGS_FILE, normalized)
    return normalized


def update_settings(**kwargs) -> dict:
    current = load_settings()
    current.update({k: v for k, v in kwargs.items() if v is not None})
    return save_settings(current)


# ── テーマプール ────────────────────────────────────────────

def _normalize_theme(raw: dict) -> dict:
    return {
        "id": str(raw.get("id") or uuid.uuid4().hex[:10]),
        "title": str(raw.get("title") or "").strip(),
        "description_hint": str(raw.get("description_hint") or "").strip(),
        "is_active": bool(raw.get("is_active", True)),
        "created_at": str(raw.get("created_at") or _now_iso()),
    }


_DEFAULT_THEMES = [
    {"title": "自己紹介", "description_hint": "名前・出身・趣味・好きなことなど、自分について紹介しよう。"},
    {"title": "好きな食べ物", "description_hint": "好きな食べ物とその理由、いつ・どこで食べるかを説明しよう。"},
    {"title": "週末の過ごし方", "description_hint": "典型的な週末に何をしているか、誰とどこで過ごすかを話そう。"},
    {"title": "好きな季節", "description_hint": "好きな季節とその理由、その季節にすることを紹介しよう。"},
    {"title": "将来の夢", "description_hint": "将来やってみたいことや、なりたい職業について話そう。"},
]


def load_themes() -> list[dict]:
    ensure_dirs()
    with _lock:
        if not THEMES_FILE.is_file():
            themes = [_normalize_theme(item) for item in _DEFAULT_THEMES]
            _write_json(THEMES_FILE, themes)
            return themes
        data = _read_json(THEMES_FILE, [])
    if not isinstance(data, list):
        return []
    return [_normalize_theme(item) for item in data if isinstance(item, dict)]


def save_themes(themes: list[dict]) -> list[dict]:
    normalized = [_normalize_theme(item) for item in themes if isinstance(item, dict)]
    with _lock:
        _write_json(THEMES_FILE, normalized)
    return normalized


def active_themes() -> list[dict]:
    return [t for t in load_themes() if t.get("is_active", True)]


def add_or_update_theme(theme: dict) -> list[dict]:
    themes = load_themes()
    normalized = _normalize_theme(theme)
    for i, existing in enumerate(themes):
        if existing["id"] == normalized["id"]:
            normalized["created_at"] = existing.get("created_at", normalized["created_at"])
            themes[i] = normalized
            return save_themes(themes)
    themes.append(normalized)
    return save_themes(themes)


def delete_theme(theme_id: str) -> list[dict]:
    themes = [t for t in load_themes() if t["id"] != theme_id]
    return save_themes(themes)


def get_theme(theme_id: str) -> dict | None:
    for theme in load_themes():
        if theme["id"] == theme_id:
            return theme
    return None


# ── 生徒名簿（roster） ──────────────────────────────────────

def _normalize_student(raw: dict) -> dict:
    return {
        "id": str(raw.get("id") or uuid.uuid4().hex[:10]),
        "class_name": str(raw.get("class_name") or raw.get("hr_class") or "").strip(),
        "number": str(raw.get("number") or "").strip(),
        "name": str(raw.get("name") or "").strip(),
    }


def load_students() -> list[dict]:
    ensure_dirs()
    with _lock:
        data = _read_json(STUDENTS_FILE, [])
    if not isinstance(data, list):
        return []
    return [_normalize_student(item) for item in data if isinstance(item, dict)]


def save_students(students: list[dict]) -> list[dict]:
    normalized = [_normalize_student(item) for item in students if isinstance(item, dict)]
    with _lock:
        _write_json(STUDENTS_FILE, normalized)
    return normalized


def import_students_from_excel(file_bytes: bytes) -> list[dict]:
    """Excelの1列目=クラス、2列目=出席番号、3列目=名前として読み込む（1行目はヘッダーとして無視）。"""
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    students: list[dict] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        class_name = str(row[0]).strip() if row and row[0] is not None else ""
        number = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        name = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
        if class_name or number or name:
            students.append(_normalize_student({"class_name": class_name, "number": number, "name": name}))
    save_students(students)
    return students


def add_or_update_student(student: dict) -> list[dict]:
    students = load_students()
    normalized = _normalize_student(student)
    for i, existing in enumerate(students):
        if existing["id"] == normalized["id"]:
            students[i] = normalized
            return save_students(students)
    students.append(normalized)
    return save_students(students)


def delete_student(student_id: str) -> list[dict]:
    students = [s for s in load_students() if s["id"] != student_id]
    return save_students(students)


# ── セッション ──────────────────────────────────────────────

def _safe_id(value: str) -> str:
    return "".join(c for c in str(value) if c.isalnum() or c == "-")


def _session_path(session_id: str):
    return SESSIONS_DIR / f"{_safe_id(session_id)}.json"


def get_session_lock(session_id: str) -> threading.Lock:
    safe_id = _safe_id(session_id)
    with _session_locks_guard:
        lock = _session_locks.get(safe_id)
        if lock is None:
            lock = threading.Lock()
            _session_locks[safe_id] = lock
        return lock


def save_session(session: dict) -> dict:
    session["updated_at"] = _now_iso()
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


# ── 完了セッション（提出済みサマリ） ─────────────────────────

def load_submissions() -> list[dict]:
    ensure_dirs()
    with _lock:
        data = _read_json(SUBMISSIONS_FILE, [])
    return data if isinstance(data, list) else []


def save_submission(entry: dict) -> dict:
    ensure_dirs()
    entry = {"id": uuid.uuid4().hex[:12], "submitted_at": _now_iso(), **entry}
    with _lock:
        submissions = _read_json(SUBMISSIONS_FILE, [])
        if not isinstance(submissions, list):
            submissions = []
        submissions.append(entry)
        _write_json(SUBMISSIONS_FILE, submissions)
    return entry


def get_submissions() -> list[dict]:
    return list(reversed(load_submissions()))


def delete_submission(submission_id: str) -> bool:
    with _lock:
        submissions = _read_json(SUBMISSIONS_FILE, [])
        if not isinstance(submissions, list):
            submissions = []
        new_list = [s for s in submissions if s.get("id") != submission_id]
        if len(new_list) == len(submissions):
            return False
        _write_json(SUBMISSIONS_FILE, new_list)
    return True
