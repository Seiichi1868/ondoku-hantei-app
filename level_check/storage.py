"""JSON ファイルによる永続化（level_check 独自。news_app / debate とは別ファイル・別スキーマ）。

- level_check_settings.json   : ルーブリック重み・AIモデル・生徒情報レベル・出題数などの設定
- level_check_students.json   : 生徒名簿（roster）
- level_check_questions.json  : カテゴリ別の問題バンク（教員が編集可能）
- level_check_submissions.json: 受験結果（採点済みサマリ）
- sessions/<id>.json          : 受験中〜受験直後の進行状況
"""
import io
import json
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import openpyxl

from level_check.config import (
    CATEGORIES,
    DEFAULT_AI_MODEL_MODE,
    DEFAULT_BACKGROUND_OPACITY,
    DEFAULT_INFO_LEVEL,
    DEFAULT_OVERALL_WEIGHTS,
    DEFAULT_QUESTIONS_PER_CATEGORY,
    DEFAULT_TIME_LIMIT_SEC,
    QUESTIONS_FILE,
    SESSIONS_DIR,
    SETTINGS_FILE,
    STUDENTS_FILE,
    SUBMISSIONS_FILE,
    ensure_dirs,
    resolve_ai_model_mode,
    resolve_info_level,
)
from level_check.scoring.rubric import (
    DEFAULT_LISTENING_RUBRIC,
    DEFAULT_SPEAKING_RUBRIC,
    LISTENING_AXES,
    SPEAKING_AXES,
    normalize_listening_weights,
    normalize_overall_weights,
    normalize_speaking_weights,
)

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
    "speaking_rubric_weights": {axis: DEFAULT_SPEAKING_RUBRIC[axis]["weight"] for axis in SPEAKING_AXES},
    "listening_rubric_weights": {axis: DEFAULT_LISTENING_RUBRIC[axis]["weight"] for axis in LISTENING_AXES},
    "overall_weights": dict(DEFAULT_OVERALL_WEIGHTS),
    "ai_model_mode": DEFAULT_AI_MODEL_MODE,
    "student_info_level": DEFAULT_INFO_LEVEL,
    "questions_per_category": dict(DEFAULT_QUESTIONS_PER_CATEGORY),
    "background_opacity": DEFAULT_BACKGROUND_OPACITY,
}


def _normalize_questions_per_category(raw) -> dict:
    result = dict(DEFAULT_QUESTIONS_PER_CATEGORY)
    # 旧設定 questions_per_task（単一整数）からの移行
    if isinstance(raw, int):
        for cat in CATEGORIES:
            result[cat] = max(1, min(15, raw))
        return result
    if not isinstance(raw, dict):
        return result
    for cat in CATEGORIES:
        try:
            count = int(raw.get(cat, DEFAULT_QUESTIONS_PER_CATEGORY[cat]))
        except (TypeError, ValueError):
            count = DEFAULT_QUESTIONS_PER_CATEGORY[cat]
        result[cat] = max(0, min(15, count))
    return result


def _normalize_settings(raw: dict | None) -> dict:
    data = deepcopy(DEFAULT_SETTINGS)
    if not isinstance(raw, dict):
        return data

    speaking_raw = raw.get("speaking_rubric_weights")
    if speaking_raw is None and isinstance(raw.get("rubric_weights"), dict):
        speaking_raw = raw.get("rubric_weights")
    data["speaking_rubric_weights"] = normalize_speaking_weights(speaking_raw)
    data["listening_rubric_weights"] = normalize_listening_weights(raw.get("listening_rubric_weights"))
    data["overall_weights"] = normalize_overall_weights(raw.get("overall_weights"))
    data["ai_model_mode"] = resolve_ai_model_mode(raw.get("ai_model_mode"))
    data["student_info_level"] = resolve_info_level(raw.get("student_info_level"))

    qpc = raw.get("questions_per_category")
    if qpc is None and raw.get("questions_per_task") is not None:
        qpc = raw.get("questions_per_task")
    data["questions_per_category"] = _normalize_questions_per_category(qpc)

    try:
        opacity = float(raw.get("background_opacity", DEFAULT_BACKGROUND_OPACITY))
    except (TypeError, ValueError):
        opacity = DEFAULT_BACKGROUND_OPACITY
    data["background_opacity"] = round(max(0.0, min(1.0, opacity)), 2)

    # 後方互換フィールド（旧UI向け）
    data["rubric_weights"] = data["speaking_rubric_weights"]
    data["questions_per_task"] = data["questions_per_category"].get("B", 3)
    return data


def load_settings() -> dict:
    ensure_dirs()
    with _lock:
        return _normalize_settings(_read_json(SETTINGS_FILE, DEFAULT_SETTINGS))


def save_settings(data: dict) -> dict:
    normalized = _normalize_settings(data)
    # 永続化時は新キーのみ保存
    to_store = {
        "speaking_rubric_weights": normalized["speaking_rubric_weights"],
        "listening_rubric_weights": normalized["listening_rubric_weights"],
        "overall_weights": normalized["overall_weights"],
        "ai_model_mode": normalized["ai_model_mode"],
        "student_info_level": normalized["student_info_level"],
        "questions_per_category": normalized["questions_per_category"],
        "background_opacity": normalized["background_opacity"],
    }
    with _lock:
        _write_json(SETTINGS_FILE, to_store)
    return normalized


def update_settings(**kwargs) -> dict:
    current = load_settings()
    current.update({k: v for k, v in kwargs.items() if v is not None})
    return save_settings(current)


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


# ── 問題バンク ──────────────────────────────────────────────

def _base_item(raw: dict) -> dict:
    return {
        "id": str(raw.get("id") or uuid.uuid4().hex[:10]),
        "level": str(raw.get("level") or "").strip().upper() or "A2",
        "active": bool(raw.get("active", True)),
        "prompt_audio_key": str(raw.get("prompt_audio_key") or "").strip(),
    }


def _normalize_a(raw: dict) -> dict:
    item = _base_item(raw)
    item.update(
        {
            "question": str(raw.get("question") or "").strip(),
            "expected_answer": str(raw.get("expected_answer") or "").strip(),
        }
    )
    return item


def _normalize_b(raw: dict) -> dict:
    item = _base_item(raw)
    item["text"] = str(raw.get("text") or "").strip()
    return item


def _normalize_c(raw: dict) -> dict:
    item = _base_item(raw)
    item.update(
        {
            "dialog_text": str(raw.get("dialog_text") or "").strip(),
            "question": str(raw.get("question") or "").strip(),
            "expected_answer": str(raw.get("expected_answer") or "").strip(),
        }
    )
    return item


def _normalize_d(raw: dict) -> dict:
    item = _base_item(raw)
    item.update(
        {
            "passage_text": str(raw.get("passage_text") or "").strip(),
            "question": str(raw.get("question") or "").strip(),
            "expected_answer": str(raw.get("expected_answer") or "").strip(),
        }
    )
    return item


def _normalize_e(raw: dict) -> dict:
    item = _base_item(raw)
    try:
        time_limit = int(raw.get("time_limit_sec", DEFAULT_TIME_LIMIT_SEC.get("E", 30)))
    except (TypeError, ValueError):
        time_limit = DEFAULT_TIME_LIMIT_SEC.get("E", 30)
    item.update(
        {
            "story_text": str(raw.get("story_text") or "").strip(),
            "time_limit_sec": max(10, min(120, time_limit)),
        }
    )
    return item


def _normalize_f(raw: dict) -> dict:
    item = _base_item(raw)
    try:
        time_limit = int(raw.get("time_limit_sec", DEFAULT_TIME_LIMIT_SEC.get("F", 30)))
    except (TypeError, ValueError):
        time_limit = DEFAULT_TIME_LIMIT_SEC.get("F", 30)
    item.update(
        {
            "prompt": str(raw.get("prompt") or "").strip(),
            "time_limit_sec": max(10, min(120, time_limit)),
        }
    )
    return item


_NORMALIZERS = {
    "A": _normalize_a,
    "B": _normalize_b,
    "C": _normalize_c,
    "D": _normalize_d,
    "E": _normalize_e,
    "F": _normalize_f,
}

QUESTION_PRIMARY_FIELD = {
    "A": "question",
    "B": "text",
    "C": "dialog_text",
    "D": "passage_text",
    "E": "story_text",
    "F": "prompt",
}


def _default_question_bank() -> dict:
    from level_check.tasks.seed_questions import SEED_QUESTIONS

    bank = {cat: [] for cat in CATEGORIES}
    for cat, items in SEED_QUESTIONS.items():
        if cat not in _NORMALIZERS:
            continue
        normalizer = _NORMALIZERS[cat]
        bank[cat] = [normalizer(item) for item in items]
    return bank


def _is_legacy_bank(raw: dict) -> bool:
    """旧3タスク形式（repeat / sentence_build / qa）かどうかを判定。"""
    if not isinstance(raw, dict):
        return False
    legacy_keys = {"repeat", "sentence_build", "qa"}
    new_keys = set(CATEGORIES)
    has_legacy = bool(legacy_keys & set(raw.keys()))
    has_new = bool(new_keys & set(raw.keys()))
    return has_legacy and not has_new


def load_questions() -> dict:
    ensure_dirs()
    with _lock:
        if not QUESTIONS_FILE.is_file():
            bank = _default_question_bank()
            _write_json(QUESTIONS_FILE, bank)
            return bank
        raw = _read_json(QUESTIONS_FILE, {})

    if _is_legacy_bank(raw):
        bank = _default_question_bank()
        with _lock:
            _write_json(QUESTIONS_FILE, bank)
        return bank

    bank = {cat: [] for cat in CATEGORIES}
    for cat, normalizer in _NORMALIZERS.items():
        items = raw.get(cat) if isinstance(raw, dict) else None
        if isinstance(items, list):
            bank[cat] = [normalizer(item) for item in items if isinstance(item, dict)]
    if not any(bank.values()):
        bank = _default_question_bank()
    return bank


def save_questions(bank: dict) -> dict:
    normalized = {cat: [] for cat in CATEGORIES}
    for cat, normalizer in _NORMALIZERS.items():
        items = bank.get(cat) if isinstance(bank, dict) else None
        if isinstance(items, list):
            normalized[cat] = [normalizer(item) for item in items if isinstance(item, dict)]
    with _lock:
        _write_json(QUESTIONS_FILE, normalized)
    return normalized


def add_questions(task_type: str, items: list[dict]) -> dict:
    cat = str(task_type or "").strip().upper()
    bank = load_questions()
    normalizer = _NORMALIZERS[cat]
    bank[cat] = bank.get(cat, []) + [normalizer(item) for item in items]
    return save_questions(bank)


def update_question(task_type: str, question_id: str, updates: dict) -> dict:
    cat = str(task_type or "").strip().upper()
    bank = load_questions()
    items = bank.get(cat, [])
    normalizer = _NORMALIZERS[cat]
    found = False
    for i, item in enumerate(items):
        if item.get("id") == question_id:
            items[i] = normalizer({**item, **updates, "id": question_id})
            found = True
            break
    if not found:
        raise ValueError("指定された問題が見つかりません。")
    bank[cat] = items
    return save_questions(bank)


def delete_question(task_type: str, question_id: str) -> dict:
    cat = str(task_type or "").strip().upper()
    bank = load_questions()
    bank[cat] = [item for item in bank.get(cat, []) if item.get("id") != question_id]
    return save_questions(bank)


def active_questions(task_type: str) -> list[dict]:
    cat = str(task_type or "").strip().upper()
    bank = load_questions()
    return [item for item in bank.get(cat, []) if item.get("active", True)]


# ── 受験セッション（進行中） ─────────────────────────────────

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


def get_part(session: dict, part_id: str) -> dict | None:
    for part in session.get("parts", []):
        if part.get("part_id") == part_id:
            return part
    return None


# ── 受験結果（提出済みサマリ） ───────────────────────────────

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


def get_submission(submission_id: str) -> dict | None:
    wanted = str(submission_id or "")
    if not wanted:
        return None
    for item in load_submissions():
        if str(item.get("id") or "") == wanted:
            return item
    return None


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
