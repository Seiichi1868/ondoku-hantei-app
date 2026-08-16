"""Whisper API による音声文字起こし（trigger 独自実装。他アプリと同種だが独立コピー）。"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_client(timeout: float | None = None, max_retries: int | None = None):
    from openai import OpenAI

    from trigger.config import WHISPER_MAX_RETRIES, WHISPER_TIMEOUT_SEC, get_openai_api_key

    api_key = get_openai_api_key()
    if not api_key:
        return None
    return OpenAI(
        api_key=api_key,
        timeout=timeout if timeout is not None else WHISPER_TIMEOUT_SEC,
        max_retries=max_retries if max_retries is not None else WHISPER_MAX_RETRIES,
    )


def transcribe_audio(file_path: Path, model: str = "whisper-1", language: str = "en") -> str:
    client = _get_client()
    if not client:
        raise RuntimeError("OPENAI_API_KEYが設定されていないため、文字起こしできません。")

    kwargs = {"model": model, "language": language}
    if model == "whisper-1":
        kwargs["temperature"] = 0

    with open(file_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(file=audio_file, **kwargs)
    return (getattr(result, "text", "") or "").strip()
