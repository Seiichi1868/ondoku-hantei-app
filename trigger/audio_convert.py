"""録音フォーマットの標準化（ブラウザ間差異への対応）。

conjugate/audio_convert.py・level_check/audio_convert.py と同じ考え方の独自コピー。
iOS Safari は audio/mp4、他ブラウザは audio/webm など MediaRecorder の出力形式が
ブラウザにより異なるため、サーバー側で 16kHz モノラル WAV に変換して以後の処理
（Whisper 文字起こし）を安定させる。変換に失敗した場合は元ファイルをそのまま使う。
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def normalize_audio_file(src_path: Path) -> Path:
    try:
        from pydub import AudioSegment

        wav_path = src_path.with_suffix(".norm.wav")
        audio = AudioSegment.from_file(src_path)
        audio = audio.set_channels(1).set_frame_rate(16000)
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("trigger audio normalize skipped (%s): %s", src_path.name, exc)
        return src_path


def audio_duration_sec(path: Path) -> float | None:
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(path)
        return len(audio) / 1000.0
    except Exception:  # noqa: BLE001
        return None
