"""表示用の背景・オープニング情報。Flaskのurl_forだけを使い、他アプリには依存しない。"""
from flask import url_for

from conjugate.config import (
    BACKGROUND_PRESETS,
    DEFAULT_BACKGROUND_OPACITY,
    DEFAULT_OPENING_ENABLED,
    DEFAULT_OPENING_MS,
    resolve_background,
)
from conjugate.storage import load_settings


def appearance_context(settings: dict | None = None) -> dict:
    data = settings if isinstance(settings, dict) else load_settings()
    bg = resolve_background(data.get("background_id"))
    return {
        "appearance": {
            **bg,
            "background_image_url": url_for("conjugate.static", filename=bg["background_image"]),
            "background_opacity": data.get("background_opacity", DEFAULT_BACKGROUND_OPACITY),
            "opening_enabled": bool(data.get("opening_enabled", DEFAULT_OPENING_ENABLED)),
            "opening_ms": int(data.get("opening_ms", DEFAULT_OPENING_MS)),
        },
        "background_presets": {
            key: {**meta, "url": url_for("conjugate.static", filename=meta["image"])}
            for key, meta in BACKGROUND_PRESETS.items()
        },
    }
