"""ステップ6: 総合評価レポート生成。

ステップ3〜5の評価結果を Versant 相当5カテゴリに集計し（決定的な計算）、
GPTには集計済みスコアと各ステップのコメントを渡して自然な日本語の総評
（summary_text・strengths・improvements）のみを生成させるハイブリッド構成にする
（スコアそのものをLLMに再計算させない方が再現性・信頼性が高いため）。
"""
from trigger.scoring.openai_utils import create_json_chat_completion, get_client
from trigger.scoring.rubric import (
    VERSANT_CATEGORIES,
    average,
    band_for_score_90,
    combine_overall_1to5,
    score_1to5_to_90,
)


def compute_versant_scores(session: dict, versant_weights: dict | None = None) -> dict:
    pronunciation = session.get("pronunciation_result") or {}
    qa_items = [q for q in (session.get("qa_items") or []) if q.get("evaluation")]
    speech_items = [s for s in (session.get("speech_items") or []) if s.get("evaluation")]

    pron_scores = (pronunciation.get("scores") or {}) if pronunciation else {}
    pronunciation_1to5 = pron_scores.get("accuracy")

    speech_fluency_values = [s["evaluation"]["scores"].get("fluency") for s in speech_items]
    fluency_inputs = [v for v in [pron_scores.get("fluency")] + speech_fluency_values if v is not None]
    fluency_1to5 = average(fluency_inputs)

    sentence_mastery_1to5 = average([s["evaluation"]["scores"].get("sentence_mastery") for s in speech_items])
    vocabulary_1to5 = average([s["evaluation"]["scores"].get("vocabulary") for s in speech_items])

    comprehension_values = []
    for qa in qa_items:
        scores = qa["evaluation"].get("scores") or {}
        item_avg = average([scores.get("relevance"), scores.get("content_consistency")])
        if item_avg is not None:
            comprehension_values.append(item_avg)
    comprehension_1to5 = average(comprehension_values)

    category_scores_1to5 = {
        "sentence_mastery": sentence_mastery_1to5,
        "vocabulary": vocabulary_1to5,
        "fluency": fluency_1to5,
        "pronunciation": pronunciation_1to5,
        "comprehension": comprehension_1to5,
    }

    category_scores_90 = {
        category: score_1to5_to_90(value) for category, value in category_scores_1to5.items()
    }

    overall_1to5 = combine_overall_1to5(category_scores_1to5, versant_weights)
    overall_90 = score_1to5_to_90(overall_1to5)
    cefr_level = band_for_score_90(overall_90)

    return {
        "category_scores_1to5": category_scores_1to5,
        "category_scores_90": category_scores_90,
        "overall_1to5": overall_1to5,
        "overall_90": overall_90,
        "cefr_level": cefr_level,
    }


def _collect_feedback_notes(session: dict) -> str:
    notes = []
    pronunciation = session.get("pronunciation_result") or {}
    if pronunciation.get("feedback_text"):
        notes.append(f"[音読] {pronunciation['feedback_text']}")
    for i, qa in enumerate(session.get("qa_items") or [], start=1):
        evaluation = qa.get("evaluation") or {}
        if evaluation.get("feedback_text"):
            notes.append(f"[Q&A{i}] {evaluation['feedback_text']}")
    for i, speech in enumerate(session.get("speech_items") or [], start=1):
        evaluation = speech.get("evaluation") or {}
        if evaluation.get("feedback_text"):
            notes.append(f"[スピーチ{i}] {evaluation['feedback_text']}")
    return "\n".join(notes)


def _summary_system_prompt() -> str:
    labels = "\n".join(f"- {cat}" for cat in VERSANT_CATEGORIES)
    return f"""あなたは英語スピーキング学習の総合評価レポートを作成する教師です。
生徒のセッション全体（音読・Q&A・即興スピーチ）の採点結果とコメントを読み、
Versant評価基準の以下カテゴリと算出済みのCEFRレベルを踏まえた総評を作成してください。

カテゴリ:
{labels}

【方針】
- スコアの再計算は不要（既に算出済みの数値をそのまま前提として使う）。
- 生徒を励ましながら、具体的な強み・改善点を挙げる。
- 日本語で書く。

出力は次のJSON形式のみ:
{{
  "summary_text": "総評（3〜5文、日本語）",
  "strengths": ["強み1", "強み2"],
  "improvements": ["改善点1", "改善点2"]
}}"""


def generate_final_report(*, session: dict, model: str, api_key: str, versant_weights: dict | None = None) -> dict:
    computed = compute_versant_scores(session, versant_weights)
    result = {
        "versant_scores": computed["category_scores_1to5"],
        "versant_scores_90": computed["category_scores_90"],
        "overall_score_1to5": computed["overall_1to5"],
        "overall_score_90": computed["overall_90"],
        "cefr_level": computed["cefr_level"],
        "summary_text": "",
        "strengths": [],
        "improvements": [],
        "model": model,
    }

    if not api_key:
        result["summary_text"] = "OpenAI API キーが未設定のため、総評コメントは生成されませんでした。"
        return result

    theme_title = session.get("theme_title") or ""
    payload = (
        f"テーマ: {theme_title}\n\n"
        f"算出済みスコア（1〜5点）: {computed['category_scores_1to5']}\n"
        f"算出済みスコア（10〜90点）: {computed['category_scores_90']}\n"
        f"総合スコア: {computed['overall_1to5']} / 5 （{computed['overall_90']} / 90）\n"
        f"CEFRレベル: {computed['cefr_level']}\n\n"
        f"各ステップのフィードバック:\n{_collect_feedback_notes(session)}"
    )
    try:
        client = get_client(api_key)
        data = create_json_chat_completion(
            client,
            model,
            [
                {"role": "system", "content": _summary_system_prompt()},
                {"role": "user", "content": payload},
            ],
            temperature=0.4,
        )
        result["summary_text"] = str(data.get("summary_text") or "").strip()
        strengths = data.get("strengths")
        improvements = data.get("improvements")
        result["strengths"] = [str(s).strip() for s in strengths if str(s or "").strip()] if isinstance(strengths, list) else []
        result["improvements"] = (
            [str(s).strip() for s in improvements if str(s or "").strip()] if isinstance(improvements, list) else []
        )
    except Exception as exc:  # noqa: BLE001
        result["summary_text"] = f"総評コメントの生成に失敗しました: {exc}"
    return result
