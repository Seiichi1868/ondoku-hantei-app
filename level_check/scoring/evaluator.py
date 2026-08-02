"""ルーブリック設定（重み・説明文）を読み込んで動的にプロンプトを構成し、
LLM で4軸（fluency / pronunciation / accuracy / vocabulary）を採点する。

response_latency は実測ミリ秒から rubric.latency_score() で機械的に算出するため
LLM には判定させない（「実際に機能する」採点にするため、計測できる軸は計測値を使う）。
"""
import json
import time

from level_check.scoring.openai_utils import create_json_chat_completion
from level_check.scoring.rubric import (
    DEFAULT_RUBRIC,
    RUBRIC_AXES,
    band_for_score,
    latency_score,
    weighted_total,
)

LLM_AXES = ("fluency", "pronunciation", "accuracy", "vocabulary")

TASK_CONTEXT = {
    "repeat": (
        "リピート課題: 生徒はお題文（target_text）を聞いた直後にそのまま復唱することが求められる。"
        "target_text と transcript の一致度・欠落・言い換えの有無を重視して採点する。"
    ),
    "sentence_build": (
        "文再構成課題: 生徒はシャッフルされた単語群から正しい語順の文（target_text）を音声で組み立てる。"
        "語順・欠落語・余分な語・文法的正しさを重視して採点する。"
    ),
    "qa": (
        "短時間Q&A課題: 生徒は質問（question_text）に対し自由な内容で口頭回答する。"
        "内容の妥当性そのものは問わず、流暢さ・発音の明瞭性・文法・語彙運用の観点でのみ採点する。"
    ),
}


def _clamp_score(value) -> int:
    try:
        score = round(float(value))
    except (TypeError, ValueError):
        return 3
    return max(1, min(5, score))


def build_system_prompt(rubric: dict) -> str:
    axis_lines = []
    for axis in LLM_AXES:
        entry = rubric.get(axis, DEFAULT_RUBRIC[axis])
        label = entry.get("label", axis)
        description = entry.get("description", "")
        axis_lines.append(f"- {axis} ({label}): {description}")
    axis_block = "\n".join(axis_lines)

    return f"""あなたは英語スピーキングの採点者です。生徒の発話の文字起こし（Whisper APIによる音声認識結果）を読み、
以下の観点でそれぞれ1〜5点（1=非常に不十分、3=平均的、5=優秀）で採点してください。

【重要な前提】
- 入力は音声認識結果のテキストのみで、音声そのものは聞けない。pronunciation（発音・明瞭性）は、
  文字起こしの乱れ・不自然な区切れ・言い直し・聞き取り不能な語の多さなど、テキストから推測できる
  範囲で評価してよい（音響的な発音の巧拙そのものではなく、聞き取りやすさの代理指標として扱う）。
- 文字起こしは音声認識由来のため、句読点や大文字化の欠落は減点しない。
- 生徒が全く発話していない、または無関係な発話の場合は、全軸を1点にする。

【採点軸】
{axis_block}

出力は次のJSON形式のみ（前置き・Markdown装飾なし）:
{{
  "fluency": {{"score": 1-5, "comment": "短い日本語コメント"}},
  "pronunciation": {{"score": 1-5, "comment": "短い日本語コメント"}},
  "accuracy": {{"score": 1-5, "comment": "短い日本語コメント"}},
  "vocabulary": {{"score": 1-5, "comment": "短い日本語コメント"}}
}}"""


def build_user_message(task_type: str, question_text: str, target_text: str, transcript: str) -> str:
    context = TASK_CONTEXT.get(task_type, TASK_CONTEXT["qa"])
    payload = {
        "task_type": task_type,
        "context": context,
        "question_text": question_text or "",
        "target_text": target_text or "",
        "transcript": transcript or "",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _get_client(api_key: str, timeout: float, max_retries: int):
    from openai import OpenAI

    return OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)


def evaluate_response(
    *,
    task_type: str,
    question_text: str,
    target_text: str,
    transcript: str,
    response_latency_ms: float | None,
    model: str,
    api_key: str,
    rubric: dict | None = None,
    rubric_weights: dict | None = None,
    timeout: float = 60.0,
    max_retries: int = 1,
) -> dict:
    if not api_key:
        raise ValueError("OpenAI API キーが未設定のため採点できません。")
    if not (transcript or "").strip():
        raise ValueError("文字起こし結果が空のため採点できません。")

    rubric = rubric or DEFAULT_RUBRIC
    client = _get_client(api_key, timeout, max_retries)

    started = time.monotonic()
    data = create_json_chat_completion(
        client,
        model,
        [
            {"role": "system", "content": build_system_prompt(rubric)},
            {"role": "user", "content": build_user_message(task_type, question_text, target_text, transcript)},
        ],
        temperature=0.2,
    )
    elapsed = time.monotonic() - started

    scores = {}
    comments = {}
    for axis in LLM_AXES:
        entry = data.get(axis) if isinstance(data.get(axis), dict) else {}
        scores[axis] = _clamp_score(entry.get("score"))
        comments[axis] = str(entry.get("comment") or "").strip()

    scores["response_latency"] = latency_score(task_type, response_latency_ms)
    comments["response_latency"] = (
        f"応答速度: {round(response_latency_ms)}ms" if response_latency_ms is not None else "応答速度: 計測不可"
    )

    weights = rubric_weights if rubric_weights is not None else {axis: DEFAULT_RUBRIC[axis]["weight"] for axis in RUBRIC_AXES}
    total = weighted_total(scores, weights)
    band = band_for_score(total)

    return {
        "scores": scores,
        "comments": comments,
        "weighted_total": total,
        "cefr_band": band,
        "model": model,
        "elapsed_sec": round(elapsed, 2),
    }
