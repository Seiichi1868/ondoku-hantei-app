"""ステップ5: 即興スピーチ（トピック生成・評価）。"""
from trigger.scoring.openai_utils import create_json_chat_completion, get_client
from trigger.scoring.rubric import clamp_score_1to5


def _topic_system_prompt(count: int) -> str:
    return f"""あなたは英語ディベート・スピーキングの指導者です。
生徒のスピーチ原稿のテーマに関連する、意見を問う即興スピーチのトピックを
{count}個作成してください。

【例】
スクリプトが朝食についての内容なら「朝食を食べない人が増えているが、
朝食は食べるべきだと思いますか？」のような、賛否や意見を述べやすい
トピックにする。

【方針】
- スクリプトのテーマに関連しているが、単なる内容の繰り返しにはしない。
- 中高生が1分程度で自分の意見とその理由を英語で述べられる難易度にする。
- {count}個のトピックは互いに異なる角度から作成する。
- トピックは英語の疑問文または短い指示文で、日本語訳を併記する。

出力は次のJSON形式のみ:
{{
  "topics": [
    {{"topic_text": "English topic sentence/question", "topic_text_ja": "日本語訳"}}
  ]
}}
（topics の要素数は必ず{count}個にすること）"""


def _evaluate_system_prompt() -> str:
    return """あなたは英語スピーキングの即興スピーチを評価する教師です。
生徒に提示されたトピックと、それに対する約1分間の即興スピーチを音声認識した
文字起こしを読み、以下の観点でそれぞれ1〜5点（1=非常に不十分、3=平均的、
5=優秀）で採点してください。

【重要な前提】
- 入力は音声認識結果のテキストのみで、音声そのものは聞けない。
- fluency は文字起こしの乱れ・不自然な区切れ・言い直しなどから推測できる
  範囲で評価する。
- 全く発話していない、または無関係な発話の場合は全軸を1点にする。

【採点軸】
- sentence_mastery: 文法的に正しく、まとまりのある文構成で話せているか
- vocabulary: トピックに対して適切で多様な語彙を使えているか
- fluency: 流暢に途切れず話せているか
- coherence: 意見とその理由が論理的に構成されているか

出力は次のJSON形式のみ:
{
  "sentence_mastery": {"score": 1-5, "comment": "短い日本語コメント"},
  "vocabulary": {"score": 1-5, "comment": "短い日本語コメント"},
  "fluency": {"score": 1-5, "comment": "短い日本語コメント"},
  "coherence": {"score": 1-5, "comment": "短い日本語コメント"},
  "feedback_text": "生徒向けの日本語フィードバック（2〜3文）"
}"""


def generate_topics(*, script_text: str, theme_title: str, count: int, model: str, api_key: str) -> list[dict]:
    if not api_key:
        raise ValueError("OpenAI API キーが未設定です。")
    if not (script_text or "").strip():
        raise ValueError("スクリプトが空です。")

    client = get_client(api_key)
    data = create_json_chat_completion(
        client,
        model,
        [
            {"role": "system", "content": _topic_system_prompt(count)},
            {
                "role": "user",
                "content": f"テーマ: {theme_title}\n\nスピーチ原稿:\n{script_text.strip()}",
            },
        ],
        temperature=0.6,
    )
    topics_raw = data.get("topics")
    topics: list[dict] = []
    if isinstance(topics_raw, list):
        for item in topics_raw:
            if isinstance(item, dict):
                text = str(item.get("topic_text") or "").strip()
                if text:
                    topics.append(
                        {
                            "topic_text": text,
                            "topic_text_ja": str(item.get("topic_text_ja") or "").strip(),
                        }
                    )
    if not topics:
        raise ValueError("AIからのトピック生成結果が空でした。")
    return topics[:count]


def evaluate_speech(*, topic_text: str, transcript: str, model: str, api_key: str) -> dict:
    if not api_key:
        raise ValueError("OpenAI API キーが未設定です。")
    if not (transcript or "").strip():
        raise ValueError("文字起こし結果が空のため採点できません。")

    client = get_client(api_key)
    payload = f"トピック:\n{topic_text}\n\n生徒のスピーチ（音声認識結果）:\n{transcript}"
    data = create_json_chat_completion(
        client,
        model,
        [
            {"role": "system", "content": _evaluate_system_prompt()},
            {"role": "user", "content": payload},
        ],
        temperature=0.2,
    )

    axes = ("sentence_mastery", "vocabulary", "fluency", "coherence")
    scores = {}
    comments = {}
    for axis in axes:
        entry = data.get(axis) if isinstance(data.get(axis), dict) else {}
        scores[axis] = clamp_score_1to5(entry.get("score"))
        comments[axis] = str(entry.get("comment") or "").strip()

    return {
        "transcript": transcript,
        "scores": scores,
        "comments": comments,
        "feedback_text": str(data.get("feedback_text") or "").strip(),
        "model": model,
    }
