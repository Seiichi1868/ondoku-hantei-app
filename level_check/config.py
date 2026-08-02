"""Speaking Level Check Test 設定。

news_app / debate とは完全に独立させ、他モジュールを import しない。
データ（名簿・問題バンク・提出結果・音声）は data/level_check/ 配下に
JSON ファイル・音声ファイルとして永続化する（Render のディスクマウントを想定）。
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(
    os.environ.get("LEVEL_CHECK_DATA_DIR", str(PROJECT_ROOT / "data" / "level_check"))
).expanduser()
AUDIO_DIR = DATA_DIR / "audio"
SESSIONS_DIR = DATA_DIR / "sessions"

STUDENTS_FILE = DATA_DIR / "level_check_students.json"
SUBMISSIONS_FILE = DATA_DIR / "level_check_submissions.json"
QUESTIONS_FILE = DATA_DIR / "level_check_questions.json"
SETTINGS_FILE = DATA_DIR / "level_check_settings.json"

ADMIN_PASSWORD = os.environ.get("LEVEL_CHECK_ADMIN_PASSWORD", "2479")

TRANSCRIBE_MODEL = os.environ.get("LEVEL_CHECK_WHISPER_MODEL", "whisper-1")
WHISPER_TIMEOUT_SEC = float(os.environ.get("LEVEL_CHECK_WHISPER_TIMEOUT_SEC", "45"))
WHISPER_MAX_RETRIES = int(os.environ.get("LEVEL_CHECK_WHISPER_MAX_RETRIES", "1"))
EVAL_TIMEOUT_SEC = float(os.environ.get("LEVEL_CHECK_EVAL_TIMEOUT_SEC", "60"))
EVAL_MAX_RETRIES = int(os.environ.get("LEVEL_CHECK_EVAL_MAX_RETRIES", "1"))

MAX_AUDIO_BYTES = 15 * 1024 * 1024
ALLOWED_AUDIO_EXTENSIONS = {"webm", "wav", "mp3", "m4a", "ogg", "mp4", "mpeg", "mpga"}

# ── タスク種別 ──────────────────────────────────────────────
TASK_TYPES = ("repeat", "sentence_build", "qa")

TASK_LABELS = {
    "repeat": "リピート課題",
    "sentence_build": "文再構成課題",
    "qa": "短時間Q&A課題",
}

TASK_DESCRIPTIONS = {
    "repeat": "短い英文を聞いて、そのまま復唱する課題。",
    "sentence_build": "語順がバラバラの単語群を、正しい語順の文として音声で組み立てる課題。",
    "qa": "簡単な質問に対し、制限時間内に口頭で回答する課題。",
}

QA_DEFAULT_TIME_LIMIT_SEC = 15

# ── 生徒への情報要求レベル（3段階） ─────────────────────────
INFO_LEVELS = ("full", "partial", "none")
DEFAULT_INFO_LEVEL = "partial"

INFO_LEVEL_LABELS = {
    "full": "氏名・クラス・番号",
    "partial": "クラス・番号のみ",
    "none": "情報要求なし",
}

# ── 評価に使う AI モデル（管理画面で切替可能。既定は Luna） ──────
AI_MODEL_MODES = {
    "luna": {"label": "Luna（GPT-5.6）", "model": "gpt-5.6-luna"},
    "terra": {"label": "Terra（GPT-5.6）", "model": "gpt-5.6-terra"},
    "gpt-4o-mini": {"label": "GPT-4o-mini", "model": "gpt-4o-mini"},
}
DEFAULT_AI_MODEL_MODE = "luna"

DEFAULT_QUESTIONS_PER_TASK = 3

# ── 背景画像（news/ の自然画像を共有 static 経由でそのまま利用） ──────
# Flask アプリ本体の static フォルダ（プロジェクトルート static/）配下のパス。
BACKGROUND_IMAGE_STATIC_PATH = "news/images/nature-bg.jpg"
DEFAULT_BACKGROUND_OPACITY = 0.35


def resolve_ai_model_mode(mode: str | None = None) -> str:
    if mode in AI_MODEL_MODES:
        return mode
    return DEFAULT_AI_MODEL_MODE


def resolve_ai_model_id(mode: str | None = None) -> str:
    return AI_MODEL_MODES[resolve_ai_model_mode(mode)]["model"]


def resolve_info_level(level: str | None = None) -> str:
    if level in INFO_LEVELS:
        return level
    return DEFAULT_INFO_LEVEL


def get_openai_api_key() -> str:
    return (os.environ.get("OPENAI_API_KEY") or "").strip()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
