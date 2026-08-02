"""録音フォーマットの標準化（ブラウザ間差異への対応）。

iOS Safari は audio/mp4、他ブラウザは audio/webm など、MediaRecorder の出力形式が
ブラウザにより異なる。Whisper API はこれらを直接受け付けられるが、念のためサーバー側で
16kHz モノラル WAV へ変換しておくことで、以後の処理（文字起こし・将来的な音響解析）を
安定させる。変換に失敗した場合（ffmpeg 未導入等）は元ファイルをそのまま使う。
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def normalize_audio_file(src_path: Path) -> Path:
    """可能なら 16kHz モノラル WAV に変換したファイルのパスを返す。失敗時は src_path をそのまま返す。"""
    try:
        from pydub import AudioSegment

        wav_path = src_path.with_suffix(".norm.wav")
        audio = AudioSegment.from_file(src_path)
        audio = audio.set_channels(1).set_frame_rate(16000)
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("audio normalize skipped (%s): %s", src_path.name, exc)
        return src_path
