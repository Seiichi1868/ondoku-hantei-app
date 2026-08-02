"""6カテゴリ（A〜F）の定義（表示ラベル・説明・生徒画面での見せ方）。"""
from level_check.config import (
    CATEGORIES,
    CATEGORY_DESCRIPTIONS,
    CATEGORY_LABELS,
    DEFAULT_TIME_LIMIT_SEC,
    LISTENING_CATEGORIES,
    SPEAKING_CATEGORIES,
)

TASK_DEFINITIONS = {
    "A": {
        "label": CATEGORY_LABELS["A"],
        "instruction": "短い質問が読み上げられます。聞き終わったら録音を開始し、短く答えてください。",
        "score_track": "listening",
        "has_audio_prompt": True,
        "default_time_limit_sec": DEFAULT_TIME_LIMIT_SEC.get("A"),
    },
    "B": {
        "label": CATEGORY_LABELS["B"],
        "instruction": "英文が読み上げられます。聞き終わったら、同じ文をそのまま復唱してください。",
        "score_track": "speaking",
        "has_audio_prompt": True,
        "default_time_limit_sec": None,
    },
    "C": {
        "label": CATEGORY_LABELS["C"],
        "instruction": "短い会話と質問が読み上げられます。内容をよく聞いてから答えてください。",
        "score_track": "listening",
        "has_audio_prompt": True,
        "default_time_limit_sec": None,
    },
    "D": {
        "label": CATEGORY_LABELS["D"],
        "instruction": "やや長めの文章と質問が読み上げられます。内容をよく聞いてから答えてください。",
        "score_track": "listening",
        "has_audio_prompt": True,
        "default_time_limit_sec": None,
    },
    "E": {
        "label": CATEGORY_LABELS["E"],
        "instruction": f"短いストーリーが読み上げられます。聞き終わったら、{DEFAULT_TIME_LIMIT_SEC.get('E', 30)}秒以内に自分の言葉で内容を言い換えて話してください。",
        "score_track": "speaking",
        "has_audio_prompt": True,
        "default_time_limit_sec": DEFAULT_TIME_LIMIT_SEC.get("E"),
    },
    "F": {
        "label": CATEGORY_LABELS["F"],
        "instruction": f"テーマが表示されます。{DEFAULT_TIME_LIMIT_SEC.get('F', 30)}秒以内に自分の意見を自由に話してください。",
        "score_track": "speaking",
        "has_audio_prompt": False,
        "default_time_limit_sec": DEFAULT_TIME_LIMIT_SEC.get("F"),
    },
}

# 起動画面などで一覧表示するときの補足
for cat in CATEGORIES:
    TASK_DEFINITIONS[cat]["description"] = CATEGORY_DESCRIPTIONS[cat]
    TASK_DEFINITIONS[cat]["is_speaking"] = cat in SPEAKING_CATEGORIES
    TASK_DEFINITIONS[cat]["is_listening"] = cat in LISTENING_CATEGORIES
