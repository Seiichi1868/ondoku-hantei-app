import json
import os
import threading
from copy import deepcopy
from pathlib import Path

import flask_app.state as state
from flask_app.state import (
    DEFAULT_BACKGROUND_ID,
    DEFAULT_BACKGROUND_OPACITY,
    DEFAULT_ENABLED_LANGUAGES,
)
from flask_app.utils.language_utils import (
    normalize_ai_mode,
    normalize_enabled_languages,
    normalize_ui_language,
)
from flask_app.utils.section_utils import DEFAULT_VISIBLE_SECTIONS, normalize_visible_sections

BACKGROUND_PRESETS = {
    "meadow": {"label": "草原", "image": "images/bg/meadow.jpg"},
    "forest": {"label": "森", "image": "images/bg/forest.jpg"},
    "mountain": {"label": "山", "image": "images/bg/mountain.jpg"},
    "ocean": {"label": "海", "image": "images/bg/ocean.jpg"},
    "misty-lake": {"label": "湖", "image": "images/bg/misty-lake.jpg"},
}

_lock = threading.Lock()
DATA_DIR = Path(
    os.environ.get("NEWS_DATA_DIR", str(Path(__file__).resolve().parent.parent.parent / "data"))
).expanduser()
SETTINGS_FILE = DATA_DIR / "vibespeak_runtime.json"

DEFAULT_SETTINGS = {
    "tts_enabled": False,
    "gate_lock_enabled": None,
    "ai_mode": None,
    "enabled_study_languages": None,
    "default_ui_language": None,
    "visible_sections": None,
    "background_id": DEFAULT_BACKGROUND_ID,
    "background_opacity": DEFAULT_BACKGROUND_OPACITY,
}


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_settings(raw: dict | None) -> dict:
    data = deepcopy(DEFAULT_SETTINGS)
    if not isinstance(raw, dict):
        return data

    if "tts_enabled" in raw:
        data["tts_enabled"] = bool(raw.get("tts_enabled"))

    if "gate_lock_enabled" in raw:
        value = raw.get("gate_lock_enabled")
        if isinstance(value, bool):
            data["gate_lock_enabled"] = value

    if raw.get("ai_mode"):
        try:
            data["ai_mode"] = normalize_ai_mode(str(raw.get("ai_mode")))
        except ValueError:
            data["ai_mode"] = None

    if raw.get("enabled_study_languages") is not None:
        try:
            data["enabled_study_languages"] = normalize_enabled_languages(raw.get("enabled_study_languages"))
        except ValueError:
            data["enabled_study_languages"] = None

    if raw.get("default_ui_language"):
        data["default_ui_language"] = normalize_ui_language(raw.get("default_ui_language"))

    if raw.get("visible_sections") is not None:
        data["visible_sections"] = normalize_visible_sections(raw.get("visible_sections"))

    bg_id = raw.get("background_id")
    if bg_id in BACKGROUND_PRESETS:
        data["background_id"] = bg_id

    if "background_opacity" in raw:
        data["background_opacity"] = _clamp_opacity(raw.get("background_opacity"))

    return data


def _clamp_opacity(value, default: float = DEFAULT_BACKGROUND_OPACITY) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    return round(max(0.0, min(n, 1.0)), 2)


def resolve_background(background_id: str | None = None) -> dict:
    preset_id = background_id if background_id in BACKGROUND_PRESETS else DEFAULT_BACKGROUND_ID
    preset = BACKGROUND_PRESETS[preset_id]
    return {
        "background_id": preset_id,
        "background_label": preset["label"],
        "background_image": preset["image"],
    }


def appearance_context() -> dict:
    settings = load_runtime_settings()
    return {
        **resolve_background(settings.get("background_id")),
        "background_opacity": settings.get("background_opacity", DEFAULT_BACKGROUND_OPACITY),
        "backgrounds": BACKGROUND_PRESETS,
    }


def appearance_response() -> dict:
    ctx = appearance_context()
    return {"ok": True, **ctx}


def load_runtime_settings() -> dict:
    _ensure_data_dir()
    with _lock:
        if not SETTINGS_FILE.is_file():
            return deepcopy(DEFAULT_SETTINGS)
        try:
            with SETTINGS_FILE.open(encoding="utf-8") as handle:
                return _normalize_settings(json.load(handle))
        except (json.JSONDecodeError, OSError):
            return deepcopy(DEFAULT_SETTINGS)


def save_runtime_settings(data: dict) -> dict:
    _ensure_data_dir()
    normalized = _normalize_settings(data)
    with _lock:
        with SETTINGS_FILE.open("w", encoding="utf-8") as handle:
            json.dump(normalized, handle, ensure_ascii=False, indent=2)
    return normalized


def current_runtime_settings() -> dict:
    return {
        "tts_enabled": bool(state.TTS_ENABLED),
        "gate_lock_enabled": bool(state.CLASS_CODE_LOCK_ENABLED),
        "ai_mode": state.AI_MODE,
        "enabled_study_languages": list(state.ENABLED_STUDY_LANGUAGES),
        "default_ui_language": state.DEFAULT_UI_LANGUAGE,
        "visible_sections": dict(state.VISIBLE_SECTIONS),
        "background_id": state.BACKGROUND_ID,
        "background_opacity": state.BACKGROUND_OPACITY,
    }


def persist_current_runtime_settings() -> dict:
    return save_runtime_settings(current_runtime_settings())


def apply_runtime_settings(data: dict | None = None) -> None:
    normalized = _normalize_settings(data or load_runtime_settings())

    state.TTS_ENABLED = bool(normalized["tts_enabled"])

    if normalized["gate_lock_enabled"] is not None:
        state.CLASS_CODE_LOCK_ENABLED = bool(normalized["gate_lock_enabled"])

    if normalized["ai_mode"]:
        state.AI_MODE = normalized["ai_mode"]

    if normalized["enabled_study_languages"]:
        state.ENABLED_STUDY_LANGUAGES = list(normalized["enabled_study_languages"])
    else:
        state.ENABLED_STUDY_LANGUAGES = list(DEFAULT_ENABLED_LANGUAGES)

    if normalized["default_ui_language"]:
        state.DEFAULT_UI_LANGUAGE = normalized["default_ui_language"]

    if normalized.get("visible_sections") is not None:
        state.VISIBLE_SECTIONS = dict(normalized["visible_sections"])
    else:
        state.VISIBLE_SECTIONS = dict(DEFAULT_VISIBLE_SECTIONS)

    bg = resolve_background(normalized.get("background_id"))
    state.BACKGROUND_ID = bg["background_id"]
    state.BACKGROUND_OPACITY = float(normalized.get("background_opacity", DEFAULT_BACKGROUND_OPACITY))


def update_runtime_settings(**kwargs) -> dict:
    current = current_runtime_settings()
    current.update(kwargs)
    saved = save_runtime_settings(current)
    apply_runtime_settings(saved)
    return saved


def load_and_apply_runtime_settings() -> None:
    apply_runtime_settings(load_runtime_settings())
