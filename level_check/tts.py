"""問題プロンプト用 TTS（OpenAI）。level_check 独自実装・キャッシュ付き。

カテゴリ C・D・E（および音声提示が必要な A・B）の問題文を事前に音声化し、
PROMPT_AUDIO_DIR にキャッシュする。毎回リアルタイム生成しない。
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from level_check.config import (
    PROMPT_AUDIO_DIR,
    TTS_MODEL,
    TTS_SPEED,
    TTS_VOICE,
    ensure_dirs,
    get_openai_api_key,
)

logger = logging.getLogger(__name__)


def _cache_key(text: str) -> str:
    digest = hashlib.sha256(
        f"level_check\n{TTS_MODEL}\n{TTS_VOICE}\n{TTS_SPEED}\n{text}".encode("utf-8")
    ).hexdigest()
    return digest[:32]


def prompt_audio_path(cache_key: str) -> Path:
    return PROMPT_AUDIO_DIR / f"{cache_key}.mp3"


def prompt_audio_url(cache_key: str) -> str:
    return f"/level_check/prompt-audio/{cache_key}.mp3"


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
    logger.info("level_check TTS cached: %s (%d chars)", cache_path.name, len(content))
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
        logger.warning("level_check TTS skipped: %s", exc)
        return None


def tts_text_for_question(category: str, item: dict) -> str:
    """カテゴリに応じて TTS 対象テキストを組み立てる。"""
    cat = str(category or "").upper()
    if cat == "A":
        return str(item.get("question") or "").strip()
    if cat == "B":
        return str(item.get("text") or "").strip()
    if cat == "C":
        dialog = str(item.get("dialog_text") or "").strip()
        question = str(item.get("question") or "").strip()
        if dialog and question:
            return f"{dialog}\n\nQuestion. {question}"
        return dialog or question
    if cat == "D":
        passage = str(item.get("passage_text") or "").strip()
        question = str(item.get("question") or "").strip()
        if passage and question:
            return f"{passage}\n\nQuestion. {question}"
        return passage or question
    if cat == "E":
        return str(item.get("story_text") or "").strip()
    return ""
