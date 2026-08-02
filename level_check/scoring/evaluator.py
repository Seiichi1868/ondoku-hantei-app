"""ルーブリック設定を読み込んで動的にプロンプトを構成し、LLMで採点する。

- スピーキング（B・E・F）: fluency / pronunciation / accuracy / vocabulary + 実測 latency
- リスニング（A・C・D）: comprehension_accuracy / response_relevance
"""
import json
import time

from level_check.scoring.openai_utils import create_json_chat_completion
from level_check.scoring.rubric import (
    DEFAULT_LISTENING_RUBRIC,
    DEFAULT_SPEAKING_RUBRIC,
    LISTENING_AXES,
    SPEAKING_AXES,
    cefr_band_for_part,
    latency_score,
    listening_weighted_total,
    score_1to5_to_90,
    speaking_weighted_total,
)

SPEAKING_LLM_AXES = ("fluency", "pronunciation", "accuracy", "vocabulary")

CATEGORY_CONTEXT = {
    "A": "質問応答: 短い質問（question_text）に対する短い口頭回答。意図を理解し的確に答えているかを重視。",
    "B": "復唱: お題文（target_text）を聞いた直後にそのまま復唱。一致度・欠落・言い換えの有無を重視。",
    "C": "会話理解質問: 会話（stimulus_text）を聞いたうえで質問（question_text）に答える。内容理解と応答の的確さを重視。",
    "D": "文章理解質問: 文章（stimulus_text）を聞いたうえで質問（question_text）に答える。内容理解と応答の的確さを重視。",
    "E": "要約リテリング: ストーリー（stimulus_text）を自分の言葉で言い換える。流暢さ・正確性・語彙・内容の把握を重視。",
    "F": "自由回答: テーマ（question_text）について意見を述べる。流暢さ・発音・文法・語彙運用を重視。",
}


def _clamp_score(value) -> int:
    try:
        score = round(float(value))
    except (TypeError, ValueError):
        return 3
    return max(1, min(5, score))


def build_speaking_system_prompt(rubric: dict) -> str:
    axis_lines = []
    for axis in SPEAKING_LLM_AXES:
        entry = rubric.get(axis, DEFAULT_SPEAKING_RUBRIC[axis])
        label = entry.get("label", axis)
        description = entry.get("description", "")
        axis_lines.append(f"- {axis} ({label}): {description}")
    axis_block = "\n".join(axis_lines)

    return f"""あなたは英語スピーキングの採点者です。生徒の発話の文字起こし（音声認識結果）を読み、
以下の観点でそれぞれ1〜5点（1=非常に不十分、3=平均的、5=優秀）で採点してください。

【重要な前提】
- 入力は音声認識結果のテキストのみで、音声そのものは聞けない。pronunciation は文字起こしの乱れ・
  不自然な区切れ・言い直しなどから推測できる範囲で評価する。
- 句読点や大文字化の欠落は減点しない。
- 全く発話していない、または無関係な発話の場合は全軸を1点にする。

【採点軸】
{axis_block}

出力は次のJSON形式のみ:
{{
  "fluency": {{"score": 1-5, "comment": "短い日本語コメント"}},
  "pronunciation": {{"score": 1-5, "comment": "短い日本語コメント"}},
  "accuracy": {{"score": 1-5, "comment": "短い日本語コメント"}},
  "vocabulary": {{"score": 1-5, "comment": "短い日本語コメント"}}
}}"""


def build_listening_system_prompt(rubric: dict) -> str:
    axis_lines = []
    for axis in LISTENING_AXES:
        entry = rubric.get(axis, DEFAULT_LISTENING_RUBRIC[axis])
        label = entry.get("label", axis)
        description = entry.get("description", "")
        weight = entry.get("weight", "")
        axis_lines.append(f"- {axis} ({label}, weight={weight}): {description}")
    axis_block = "\n".join(axis_lines)

    return f"""あなたは英語リスニング理解の採点者です。生徒の口頭回答の文字起こしを読み、
質問・会話・文章の内容を正しく理解して的確に答えられているかを採点してください。

【重要な前提】
- 文法・発音の巧拙は主目的ではない。理解と応答の的確さを重視する。
- expected_answer は採点の目安であり、言い回しが違っても意味が合っていれば高得点でよい。
- 全く答えられていない／無関係な場合は両軸とも1点。

【採点軸】
{axis_block}

出力は次のJSON形式のみ:
{{
  "comprehension_accuracy": {{"score": 1-5, "comment": "短い日本語コメント"}},
  "response_relevance": {{"score": 1-5, "comment": "短い日本語コメント"}}
}}"""


def build_user_message(
    *,
    category: str,
    question_text: str,
    stimulus_text: str,
    target_text: str,
    expected_answer: str,
    transcript: str,
) -> str:
    context = CATEGORY_CONTEXT.get(category, CATEGORY_CONTEXT["F"])
    payload = {
        "category": category,
        "context": context,
        "question_text": question_text or "",
        "stimulus_text": stimulus_text or "",
        "target_text": target_text or "",
        "expected_answer": expected_answer or "",
        "transcript": transcript or "",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _get_client(api_key: str, timeout: float, max_retries: int):
    from openai import OpenAI

    return OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)


def evaluate_response(
    *,
    task_type: str,
    question_text: str = "",
    target_text: str = "",
    stimulus_text: str = "",
    expected_answer: str = "",
    transcript: str,
    response_latency_ms: float | None,
    model: str,
    api_key: str,
    score_track: str | None = None,
    speaking_rubric: dict | None = None,
    listening_rubric: dict | None = None,
    speaking_weights: dict | None = None,
    listening_weights: dict | None = None,
    # 後方互換
    rubric: dict | None = None,
    rubric_weights: dict | None = None,
    timeout: float = 60.0,
    max_retries: int = 1,
) -> dict:
    if not api_key:
        raise ValueError("OpenAI API キーが未設定のため採点できません。")
    if not (transcript or "").strip():
        raise ValueError("文字起こし結果が空のため採点できません。")

    category = str(task_type or "").strip().upper()
    track = score_track or ("listening" if category in ("A", "C", "D") else "speaking")
    client = _get_client(api_key, timeout, max_retries)
    started = time.monotonic()

    if track == "listening":
        listening_rubric = listening_rubric or DEFAULT_LISTENING_RUBRIC
        data = create_json_chat_completion(
            client,
            model,
            [
                {"role": "system", "content": build_listening_system_prompt(listening_rubric)},
                {
                    "role": "user",
                    "content": build_user_message(
                        category=category,
                        question_text=question_text,
                        stimulus_text=stimulus_text,
                        target_text=target_text,
                        expected_answer=expected_answer,
                        transcript=transcript,
                    ),
                },
            ],
            temperature=0.2,
        )
        scores = {}
        comments = {}
        for axis in LISTENING_AXES:
            entry = data.get(axis) if isinstance(data.get(axis), dict) else {}
            scores[axis] = _clamp_score(entry.get("score"))
            comments[axis] = str(entry.get("comment") or "").strip()
        total = listening_weighted_total(scores, listening_weights)
    else:
        speaking_rubric = speaking_rubric or rubric or DEFAULT_SPEAKING_RUBRIC
        weights = speaking_weights if speaking_weights is not None else rubric_weights
        data = create_json_chat_completion(
            client,
            model,
            [
                {"role": "system", "content": build_speaking_system_prompt(speaking_rubric)},
                {
                    "role": "user",
                    "content": build_user_message(
                        category=category,
                        question_text=question_text,
                        stimulus_text=stimulus_text,
                        target_text=target_text,
                        expected_answer=expected_answer,
                        transcript=transcript,
                    ),
                },
            ],
            temperature=0.2,
        )
        scores = {}
        comments = {}
        for axis in SPEAKING_LLM_AXES:
            entry = data.get(axis) if isinstance(data.get(axis), dict) else {}
            scores[axis] = _clamp_score(entry.get("score"))
            comments[axis] = str(entry.get("comment") or "").strip()
        scores["response_latency"] = latency_score(category, response_latency_ms)
        comments["response_latency"] = (
            f"応答速度: {round(response_latency_ms)}ms"
            if response_latency_ms is not None
            else "応答速度: 計測不可"
        )
        total = speaking_weighted_total(scores, weights)

    elapsed = time.monotonic() - started
    score_90 = score_1to5_to_90(total)
    # CEFR は E（要約リテリング）・F（自由回答）のみ妥当。他カテゴリは付けない。
    band = cefr_band_for_part(category, total)

    return {
        "scores": scores,
        "comments": comments,
        "weighted_total": total,
        "score_90": score_90,
        "cefr_band": band,
        "score_track": track,
        "model": model,
        "elapsed_sec": round(elapsed, 2),
    }
