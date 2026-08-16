"""ステップ3: 発音評価（音読判定 Vibe Speak と同様の評価粒度・考え方を踏襲した独自実装）。

生徒の音読音声を Whisper で文字起こしし、模範スクリプトとの一致度・流暢さを
GPTで採点する。音素レベルの高精度発音評価（Azure Pronunciation Assessment等）は
今回のスコープ外とし、既存の Vibe Speak 系アプリと同等の精度・粒度に留める。
"""
import difflib
import re

from trigger.scoring.openai_utils import create_json_chat_completion, get_client
from trigger.scoring.rubric import clamp_score_1to5


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", (text or "").lower())


def word_match_ratio(reference: str, transcript: str) -> int:
    """簡易的な一致率（%）。音声認識テキストと模範スクリプトの単語列を比較する。"""
    ref_tokens = _tokenize(reference)
    hyp_tokens = _tokenize(transcript)
    if not ref_tokens:
        return 0
    matcher = difflib.SequenceMatcher(a=ref_tokens, b=hyp_tokens)
    return round(matcher.ratio() * 100)


def _system_prompt() -> str:
    return """あなたは英語音読の採点者です。生徒が読むべき模範スクリプトと、
生徒の音読を音声認識した文字起こしを比較し、以下の観点でそれぞれ1〜5点
（1=非常に不十分、3=平均的、5=優秀）で採点してください。

【重要な前提】
- 入力は音声認識結果のテキストのみで、音声そのものは聞けない。
- accuracy はスクリプトの単語・語順をどれだけ正確に読めているかを、
  fluency は文字起こしの乱れ・不自然な区切れ・言い直しなどから推測できる
  範囲で評価する。
- 句読点や大文字化の違いは減点しない。
- word_match_percent（単語一致率）を参考値として使ってよい。

【採点軸】
- accuracy: スクリプトを正確に読めているか
- fluency: 流暢に途切れず読めているか

出力は次のJSON形式のみ:
{
  "accuracy": {"score": 1-5, "comment": "短い日本語コメント"},
  "fluency": {"score": 1-5, "comment": "短い日本語コメント"},
  "feedback_text": "生徒向けの日本語フィードバック（2〜3文、具体的な改善点と励ましを含める）"
}"""


def evaluate_pronunciation(*, reference_text: str, transcript: str, model: str, api_key: str) -> dict:
    if not api_key:
        raise ValueError("OpenAI API キーが未設定です。")
    if not (transcript or "").strip():
        raise ValueError("文字起こし結果が空のため採点できません。")

    match_percent = word_match_ratio(reference_text, transcript)

    client = get_client(api_key)
    payload = (
        f"模範スクリプト:\n{reference_text}\n\n"
        f"生徒の音読（音声認識結果）:\n{transcript}\n\n"
        f"単語一致率（参考値）: {match_percent}%"
    )
    data = create_json_chat_completion(
        client,
        model,
        [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": payload},
        ],
        temperature=0.2,
    )

    accuracy_entry = data.get("accuracy") if isinstance(data.get("accuracy"), dict) else {}
    fluency_entry = data.get("fluency") if isinstance(data.get("fluency"), dict) else {}

    return {
        "transcript": transcript,
        "word_match_percent": match_percent,
        "scores": {
            "accuracy": clamp_score_1to5(accuracy_entry.get("score")),
            "fluency": clamp_score_1to5(fluency_entry.get("score")),
        },
        "comments": {
            "accuracy": str(accuracy_entry.get("comment") or "").strip(),
            "fluency": str(fluency_entry.get("comment") or "").strip(),
        },
        "feedback_text": str(data.get("feedback_text") or "").strip(),
        "model": model,
    }
