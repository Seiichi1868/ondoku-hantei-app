"""録音フォーマットの標準化（ブラウザ間差異への対応）。

iOS Safari は audio/mp4、他ブラウザは audio/webm など、MediaRecorder の出力形式が
ブラウザにより異なる。Whisper APIはこれらを直接受け付けられるが、念のためサーバー側で
16kHzモノラルWAVへ変換しておくことで文字起こしの安定性を高める。変換に失敗した場合
（ffmpeg未導入等）は元ファイルをそのまま使う。
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def audio_duration_sec(path: Path) -> float:
    """音声の長さ（秒）。計測できない場合は 0。"""
    try:
        from pydub import AudioSegment

        return max(0.0, len(AudioSegment.from_file(path)) / 1000.0)
    except Exception:  # noqa: BLE001
        pass
    try:
        import wave

        with wave.open(str(path), "rb") as wf:
            rate = float(wf.getframerate() or 1)
            return max(0.0, wf.getnframes() / rate)
    except Exception:  # noqa: BLE001
        return 0.0


def normalize_audio_file(src_path: Path) -> Path:
    """可能なら16kHzモノラルWAVに変換したファイルのパスを返す。失敗時はsrc_pathをそのまま返す。"""
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
