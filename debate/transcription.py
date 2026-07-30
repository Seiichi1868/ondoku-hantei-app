"""Whisper API による音声文字起こし。"""
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_client():
    from openai import OpenAI

    from debate.config import WHISPER_MAX_RETRIES, WHISPER_TIMEOUT_SEC

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    # 既定（10分タイムアウト×2回リトライ＝最悪30分待ち）だとハングしたように
    # 見えるため、短いタイムアウトと少ないリトライ回数を明示する。
    return OpenAI(api_key=api_key, timeout=WHISPER_TIMEOUT_SEC, max_retries=WHISPER_MAX_RETRIES)


def transcribe_audio(file_path: Path, language: str = "en") -> str:
    """録音ファイルをWhisper APIで文字起こしする。

    英語ディベートを想定し既定言語は "en"。OPENAI_API_KEY 未設定時は RuntimeError。
    ネットワーク不調等でタイムアウトした場合も、既定の短いタイムアウトにより
    数十秒〜1分程度で例外が送出される（呼び出し側で needs_review に落として続行できる）。
    """
    client = _get_client()
    if not client:
        raise RuntimeError("OPENAI_API_KEYが設定されていないため、文字起こしできません。")

    from debate.config import WHISPER_MODEL

    started = time.monotonic()
    try:
        with open(file_path, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=audio_file,
                language=language,
            )
    except Exception as exc:
        elapsed = time.monotonic() - started
        logger.warning("Whisper transcription failed after %.1fs (%s): %s", elapsed, file_path.name, exc)
        raise

    elapsed = time.monotonic() - started
    logger.info("Whisper transcription finished in %.1fs (%s)", elapsed, file_path.name)
    return (getattr(result, "text", "") or "").strip()
