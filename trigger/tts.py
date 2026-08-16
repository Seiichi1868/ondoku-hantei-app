"""模範音声・質問/トピック音声用 TTS（OpenAI）。trigger 独自実装・キャッシュ付き。

音読判定 Vibe Speak 等の TTS 実装ロジックと同じ考え方を踏襲した独立コピー
（キャッシュキー方式・保存先ディレクトリ構成は level_check/tts.py に準拠）。
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from trigger.config import (
    PROMPT_AUDIO_DIR,
    TTS_MODEL,
    TTS_SPEED,
    TTS_VOICE,
    ensure_dirs,
    get_openai_api_key,
)

logger = logging.getLogger(__name__)


def _cache_key(text: str) -> str:
    digest = hashlib.sha256(f"trigger\n{TTS_MODEL}\n{TTS_VOICE}\n{TTS_SPEED}\n{text}".encode("utf-8")).hexdigest()
    return digest[:32]


def prompt_audio_path(cache_key: str) -> Path:
    return PROMPT_AUDIO_DIR / f"{cache_key}.mp3"


def prompt_audio_url(cache_key: str) -> str:
    return f"/trigger/prompt-audio/{cache_key}.mp3"


def synthesize_prompt(text: str, *, force: bool = False) -> tuple[str, bool]:
    """テキストを TTS してキャッシュする。戻り値: (cache_key, was_cached)。"""
    content = str(text or "").strip()
    if not content:
        raise ValueError("TTS 用テキストが空です。")

    ensure_dirs()
    key = _cache_key(content)
    cache_path = prompt_audio_path(key)
    if cache_path.is_file() and not force:
        return key, True

    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("OpenAI API キーが未設定のため TTS を生成できません。")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    speech = client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=content,
        response_format="mp3",
        speed=max(0.25, min(4.0, TTS_SPEED)),
    )
    cache_path.write_bytes(speech.read())
    logger.info("trigger TTS cached: %s (%d chars)", cache_path.name, len(content))
    return key, False


def ensure_prompt_audio(text: str) -> str | None:
    """可能な場合は TTS を用意し URL を返す。失敗時は None（クライアント側フォールバック）。"""
    content = str(text or "").strip()
    if not content:
        return None
    try:
        key, _ = synthesize_prompt(content)
        return prompt_audio_url(key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("trigger TTS skipped: %s", exc)
        return None
