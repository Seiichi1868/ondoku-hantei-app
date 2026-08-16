"""ステップ4: フォローアップQ&A（質問生成・回答評価）。"""
from trigger.scoring.openai_utils import create_json_chat_completion, get_client
from trigger.scoring.rubric import clamp_score_1to5


def _generate_system_prompt(count: int) -> str:
    return f"""あなたは英語スピーキングの即興力を鍛える教師です。
生徒が事前に用意した英語スピーチ原稿の内容に基づいて、フォローアップの
短文質問を{count}問作成してください。

【方針】
- 質問はスクリプトの内容から答えられる、具体的で短い英語の質問文にする。
- 生徒が即興で1〜2文で答えられる難易度にする（Yes/Noだけで終わらない工夫をする）。
- {count}問はそれぞれ異なる観点（詳細・理由・感想・比較など）から質問する。

出力は次のJSON形式のみ:
{{
  "questions": ["Question 1?", "Question 2?", ...]
}}
（questions の要素数は必ず{count}個にすること）"""


def _evaluate_system_prompt() -> str:
    return """あなたは英語スピーキングの即興応答力を評価する教師です。
生徒が事前に用意したスピーチ原稿（script）、それに基づく質問（question）、
そして生徒の口頭回答を音声認識した文字起こし（transcript）を読み、
「スクリプトの内容を踏まえて質問に適切に答えられているか」を評価してください。

【重要な前提】
- スクリプトの内容と矛盾せず、質問の意図に沿って具体的に答えられているかを重視する。
- 文法の細かい誤りより、内容の的確さ・関連性を優先して評価する。
- 全く回答していない、または質問と無関係な場合は両軸とも1点にする。

【採点軸】
- relevance: 質問の意図に対してどれだけ的確に答えられているか
- content_consistency: スクリプトの内容を踏まえた自然な回答になっているか

出力は次のJSON形式のみ:
{
  "relevance": {"score": 1-5, "comment": "短い日本語コメント"},
  "content_consistency": {"score": 1-5, "comment": "短い日本語コメント"},
  "feedback_text": "生徒向けの日本語フィードバック（1〜2文）"
}"""


def generate_questions(*, script_text: str, count: int, model: str, api_key: str) -> list[str]:
    if not api_key:
        raise ValueError("OpenAI API キーが未設定です。")
    if not (script_text or "").strip():
        raise ValueError("スクリプトが空です。")

    client = get_client(api_key)
    data = create_json_chat_completion(
        client,
        model,
        [
            {"role": "system", "content": _generate_system_prompt(count)},
            {"role": "user", "content": f"スピーチ原稿:\n{script_text.strip()}"},
        ],
        temperature=0.6,
    )
    questions_raw = data.get("questions")
    questions: list[str] = []
    if isinstance(questions_raw, list):
        questions = [str(q).strip() for q in questions_raw if str(q or "").strip()]
    if not questions:
        raise ValueError("AIからの質問生成結果が空でした。")
    return questions[:count]


def evaluate_answer(
    *, script_text: str, question_text: str, transcript: str, model: str, api_key: str
) -> dict:
    if not api_key:
        raise ValueError("OpenAI API キーが未設定です。")
    if not (transcript or "").strip():
        raise ValueError("文字起こし結果が空のため採点できません。")

    client = get_client(api_key)
    payload = (
        f"スクリプト全文:\n{script_text}\n\n"
        f"質問:\n{question_text}\n\n"
        f"生徒の回答（音声認識結果）:\n{transcript}"
    )
    data = create_json_chat_completion(
        client,
        model,
        [
            {"role": "system", "content": _evaluate_system_prompt()},
            {"role": "user", "content": payload},
        ],
        temperature=0.2,
    )
    relevance_entry = data.get("relevance") if isinstance(data.get("relevance"), dict) else {}
    consistency_entry = data.get("content_consistency") if isinstance(data.get("content_consistency"), dict) else {}

    return {
        "transcript": transcript,
        "scores": {
            "relevance": clamp_score_1to5(relevance_entry.get("score")),
            "content_consistency": clamp_score_1to5(consistency_entry.get("score")),
        },
        "comments": {
            "relevance": str(relevance_entry.get("comment") or "").strip(),
            "content_consistency": str(consistency_entry.get("comment") or "").strip(),
        },
        "feedback_text": str(data.get("feedback_text") or "").strip(),
        "model": model,
    }
