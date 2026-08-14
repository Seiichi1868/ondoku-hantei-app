"""Whisper API（OpenAI）による音声文字起こし。

スペイン語（tú形の短文）の認識精度を優先し、language="es" を明示する。
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_client():
    from openai import OpenAI

    from conjugate.config import WHISPER_MAX_RETRIES, WHISPER_TIMEOUT_SEC, get_openai_api_key

    api_key = get_openai_api_key()
    if not api_key:
        return None
    return OpenAI(api_key=api_key, timeout=WHISPER_TIMEOUT_SEC, max_retries=WHISPER_MAX_RETRIES)


def transcribe_audio(file_path: Path, model: str = "whisper-1", language: str = "es") -> str:
    client = _get_client()
    if not client:
        raise RuntimeError("OPENAI_API_KEYが設定されていないため、文字起こしできません。")

    with open(file_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
            language=language,
        )
    return (getattr(result, "text", "") or "").strip()
