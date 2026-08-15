"""Whisper API（OpenAI）による音声文字起こし。

スペイン語（tú形の短文）以外は受け付けない。
language="es" に加え、スペイン語のプロンプトと非ラテン文字の再試行で
アラビア語など他言語への誤認識を抑える。
"""
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

SPANISH_PROMPT = (
    "Español solamente. Transcribe solo español. "
    "Frases cortas en forma de tú: Puedes. Hablas. Estás comiendo. "
    "Vas a estudiar. Te gusta el café. Pudiste."
)

SPANISH_RETRY_PROMPT = (
    "Idioma: español. No uses árabe ni otros idiomas. "
    "Solo español: Tú puedes. Tú hablas. Estás vendiendo. Vas a poder."
)

# アラビア語・ヘブライ語・キリル・日中韓など、スペイン語に現れない文字
_NON_SPANISH_SCRIPT = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\u0870-\u089F"
    r"\u0590-\u05FF"
    r"\u0400-\u04FF"
    r"\u3040-\u30FF\u31F0-\u31FF"
    r"\u4E00-\u9FFF"
    r"\uAC00-\uD7AF]"
)


def _get_client():
    from openai import OpenAI

    from conjugate.config import WHISPER_MAX_RETRIES, WHISPER_TIMEOUT_SEC, get_openai_api_key

    api_key = get_openai_api_key()
    if not api_key:
        return None
    return OpenAI(api_key=api_key, timeout=WHISPER_TIMEOUT_SEC, max_retries=WHISPER_MAX_RETRIES)


def _is_non_spanish_script(text: str) -> bool:
    if not text:
        return False
    hits = _NON_SPANISH_SCRIPT.findall(text)
    if not hits:
        return False
    return len(hits) >= 2 or (len(hits) / max(1, len(text)) >= 0.15)


def _transcribe_once(client, file_path: Path, model: str, prompt: str) -> str:
    kwargs = {
        "model": model,
        "language": "es",
        "prompt": prompt,
    }
    if model == "whisper-1":
        kwargs["temperature"] = 0
    with open(file_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(file=audio_file, **kwargs)
    return (getattr(result, "text", "") or "").strip()


def keep_spanish_transcript(text: str) -> str:
    """Web Speech 等の結果からも、スペイン語以外の文字起こしを落とす。"""
    cleaned = (text or "").strip()
    if _is_non_spanish_script(cleaned):
        return ""
    return cleaned


def transcribe_audio(file_path: Path, model: str = "whisper-1", language: str = "es") -> str:
    del language  # 常にスペイン語。呼び出し側の上書きは受け付けない。
    client = _get_client()
    if not client:
        raise RuntimeError("OPENAI_API_KEYが設定されていないため、文字起こしできません。")

    text = _transcribe_once(client, file_path, model, SPANISH_PROMPT)
    if _is_non_spanish_script(text):
        logger.warning("Non-Spanish script detected, retrying as Spanish-only: %s", text[:80])
        text = _transcribe_once(client, file_path, model, SPANISH_RETRY_PROMPT)
        if _is_non_spanish_script(text):
            logger.warning("Retry still non-Spanish; dropping transcript: %s", text[:80])
            return ""
    return text
