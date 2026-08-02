"""管理画面の「AIで追加生成」機能: 各カテゴリの問題をAIで新規生成する。

商用テストの問題形式を複製するものではなく、独自ルーブリックのための
オリジナル問題を生成する。生成後は管理画面で教員がレビュー・編集できる。
"""
from level_check.scoring.openai_utils import create_json_chat_completion

_SCHEMA_HINT = {
    "A": '{"question": "短く即答できる質問文", "expected_answer": "想定される短い答えの目安", "level": "A2"}',
    "B": '{"text": "6〜14語程度の復唱用英文", "level": "A2"}',
    "C": '{"dialog_text": "A/Bの短い会話（3〜6行）", "question": "会話内容に関する質問", "expected_answer": "正解の目安", "level": "A2"}',
    "D": '{"passage_text": "40〜80語程度の短い文章", "question": "文章内容に関する質問", "expected_answer": "正解の目安", "level": "B1"}',
    "E": '{"story_text": "40〜90語程度の短いストーリー", "level": "B1", "time_limit_sec": 30}',
    "F": '{"prompt": "30秒程度で意見を述べられるテーマ文", "level": "B1", "time_limit_sec": 30}',
}

_TASK_PROMPT_CONTEXT = {
    "A": "短い質問を聞き短く即答する「質問応答」課題の、質問文と想定解答の目安",
    "B": "聞いた英文をそのまま復唱する「復唱」課題の、お題となる英文",
    "C": "短い会話を聞いて内容質問に答える「会話理解」課題の、会話文・質問・想定解答",
    "D": "やや長めの文章を聞いて内容質問に答える「文章理解」課題の、文章・質問・想定解答",
    "E": "短いストーリーを聞き自分の言葉で言い換える「要約リテリング」課題の、ストーリー文",
    "F": "テーマについて意見を自由に述べる「自由回答」課題の、テーマ文",
}


def _system_prompt(category: str, count: int) -> str:
    context = _TASK_PROMPT_CONTEXT.get(category, _TASK_PROMPT_CONTEXT["F"])
    schema = _SCHEMA_HINT.get(category, _SCHEMA_HINT["F"])
    return f"""あなたは英語教育の専門家です。日本の高校生〜大学生向けの、独自設計のスピーキング瞬発力・運用力
チェックテストの問題を作成します。特定の商用スピーキングテストの名称・ロゴ・公式問題形式を複製せず、
オリジナルの問題として作成してください。

{context}を、CEFR A2〜B2程度の難易度をバランスよく混ぜて {count} 件作成してください。
既存の問題と内容が重複しないようにしてください。会話・文章は自然な英語にしてください。

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

    category = str(task_type or "").strip().upper()
    if category not in _SCHEMA_HINT:
        raise ValueError(f"不明なカテゴリ: {task_type}")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    data = create_json_chat_completion(
        client,
        model,
        [
            {"role": "system", "content": _system_prompt(category, count)},
            {"role": "user", "content": _user_prompt(existing_texts or [])},
        ],
        temperature=0.8,
    )
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("AIからの応答形式が不正です。")
    return [item for item in items if isinstance(item, dict)][:count]
