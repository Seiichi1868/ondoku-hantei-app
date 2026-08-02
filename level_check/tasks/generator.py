"""管理画面の「AIで追加生成」機能: 各タスク種別の問題をAIで新規生成する。

Versant等の商用テストの問題形式を複製するものではなく、独自ルーブリックのための
オリジナル問題を生成する。生成後は管理画面で教員がレビュー・編集できる。
"""
from level_check.scoring.openai_utils import create_json_chat_completion

_SCHEMA_HINT = {
    "repeat": '{"text": "6〜14語程度の英文", "level": "A2"}',
    "sentence_build": '{"target_sentence": "6〜12語程度の正しい語順の英文", "level": "B1"}',
    "qa": '{"question": "15秒程度で口頭回答できる意見・経験を問う質問文", "level": "A2"}',
}

_TASK_PROMPT_CONTEXT = {
    "repeat": "短い英文を聞いてそのまま復唱する「リピート課題」の、お題となる英文",
    "sentence_build": "語順をバラバラにして提示し、正しい語順の文を音声で組み立てる「文再構成課題」の、正解となる英文",
    "qa": "制限時間内に口頭で自由回答する「短時間Q&A課題」の、質問文",
}


def _system_prompt(task_type: str, count: int) -> str:
    context = _TASK_PROMPT_CONTEXT.get(task_type, _TASK_PROMPT_CONTEXT["qa"])
    schema = _SCHEMA_HINT.get(task_type, _SCHEMA_HINT["qa"])
    return f"""あなたは英語教育の専門家です。日本の高校生〜大学生向けの、独自設計のスピーキング瞬発力・運用力
チェックテストの問題を作成します。特定の商用テスト（Versant等）の名称・ロゴ・公式問題形式を複製せず、
オリジナルの問題として作成してください。

{context}を、CEFR A2〜B2程度の難易度をバランスよく混ぜて {count} 件作成してください。
既存の問題と内容が重複しないようにしてください。

出力は次のJSON形式のみ（前置き・Markdown装飾なし）:
{{"items": [{schema}, ...（{count}件）]}}"""


def _user_prompt(existing_texts: list[str]) -> str:
    if not existing_texts:
        return "既存の問題はまだありません。"
    joined = "\n".join(f"- {text}" for text in existing_texts[:60])
    return f"既存の問題（重複を避けてください）:\n{joined}"


def generate_questions(
    *, task_type: str, count: int, model: str, api_key: str, existing_texts: list[str] | None = None
) -> list[dict]:
    if not api_key:
        raise ValueError("OpenAI API キーが未設定のため生成できません。")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    data = create_json_chat_completion(
        client,
        model,
        [
            {"role": "system", "content": _system_prompt(task_type, count)},
            {"role": "user", "content": _user_prompt(existing_texts or [])},
        ],
        temperature=0.8,
    )
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("AIからの応答形式が不正です。")
    return [item for item in items if isinstance(item, dict)][:count]
