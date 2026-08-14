"""Vibe Speak Conjugate 設定。

news_app / level_check / debate とは完全に独立させ、他モジュールをimportしない。
データ（設定・セッション履歴・弱点動詞集計）は data/conjugate/ 配下に
JSONファイルとして永続化する（Render のディスクマウントを想定）。
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(
    os.environ.get("CONJUGATE_DATA_DIR", str(PROJECT_ROOT / "data" / "conjugate"))
).expanduser()
SESSIONS_DIR = DATA_DIR / "sessions"
AUDIO_TMP_DIR = DATA_DIR / "audio_tmp"

SETTINGS_FILE = DATA_DIR / "conjugate_settings.json"
SUBMISSIONS_FILE = DATA_DIR / "conjugate_submissions.json"
WEAK_VERBS_FILE = DATA_DIR / "conjugate_weak_verbs.json"

ADMIN_PASSWORD = os.environ.get("CONJUGATE_ADMIN_PASSWORD", "2479")

# ── ASRエンジン ──────────────────────────────────────────────
ASR_ENGINES = ("whisper", "web_speech")
DEFAULT_ASR_ENGINE = "whisper"

WHISPER_MODELS = {
    "whisper-1": {"label": "Whisper-1（高精度・既定）", "cost_per_min_usd": 0.006},
    "gpt-4o-mini-transcribe": {"label": "GPT-4o-mini-transcribe（低コスト）", "cost_per_min_usd": 0.003},
}
DEFAULT_WHISPER_MODEL = os.environ.get("CONJUGATE_WHISPER_MODEL", "whisper-1")
WHISPER_TIMEOUT_SEC = float(os.environ.get("CONJUGATE_WHISPER_TIMEOUT_SEC", "30"))
WHISPER_MAX_RETRIES = int(os.environ.get("CONJUGATE_WHISPER_MAX_RETRIES", "1"))

MAX_AUDIO_BYTES = 8 * 1024 * 1024
ALLOWED_AUDIO_EXTENSIONS = {"webm", "wav", "mp3", "m4a", "ogg", "mp4", "mpeg", "mpga"}

# ── 判定の厳しさ ─────────────────────────────────────────────
STRICTNESS_MODES = ("lenient", "strict")
DEFAULT_STRICTNESS = "lenient"

# ── 出題カテゴリ・文型 ───────────────────────────────────────
from conjugate.data.verbs import CATEGORY_LABELS, CATEGORY_ORDER  # noqa: E402
from conjugate.data.conjugations import TENSE_LABELS, TENSE_ORDER  # noqa: E402

DEFAULT_ENABLED_CATEGORIES = list(CATEGORY_ORDER)
DEFAULT_ENABLED_TENSES = ["present"]  # 段階的実装: まず現在形のみを既定で有効化

DEFAULT_QUESTIONS_PER_SESSION = 10
DEFAULT_TARGETS_PER_QUESTION = 1  # 1問あたりtú変換させる文型の数（1 or 2）
DEFAULT_GUSTAR_ENABLED = True
DEFAULT_GUSTAR_PER_SESSION = 1
DEFAULT_PRIORITIZE_WEAK_VERBS = True


def get_openai_api_key() -> str:
    return (os.environ.get("OPENAI_API_KEY") or "").strip()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_TMP_DIR.mkdir(parents=True, exist_ok=True)
