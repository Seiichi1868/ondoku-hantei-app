"""Whisper API による音声文字起こし。"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_client():
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def transcribe_audio(file_path: Path, language: str = "en") -> str:
    """録音ファイルをWhisper APIで文字起こしする。

    英語ディベートを想定し既定言語は "en"。OPENAI_API_KEY 未設定時は RuntimeError。
    """
    client = _get_client()
    if not client:
        raise RuntimeError("OPENAI_API_KEYが設定されていないため、文字起こしできません。")

    from debate.config import WHISPER_MODEL

    with open(file_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=audio_file,
            language=language,
        )
    return (getattr(result, "text", "") or "").strip()
