"""3タスク種別の定義（表示ラベル・説明・生徒画面での見せ方）。"""
from level_check.config import QA_DEFAULT_TIME_LIMIT_SEC

TASK_DEFINITIONS = {
    "repeat": {
        "label": "リピート課題",
        "instruction": "英文が読み上げられます。聞き終わったら「録音開始」を押し、同じ文をそのまま復唱してください。",
    },
    "sentence_build": {
        "label": "文再構成課題",
        "instruction": "バラバラに並んだ単語が表示されます。正しい語順の文を考え、「録音開始」を押して声に出して言ってください。",
    },
    "qa": {
        "label": "短時間Q&A課題",
        "instruction": f"質問が表示されます。「録音開始」を押し、{QA_DEFAULT_TIME_LIMIT_SEC}秒以内に口頭で答えてください。",
    },
}
