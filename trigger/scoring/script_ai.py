"""ステップ1: 台本作成（日本語→英訳 / 英語→校正）。"""
from trigger.scoring.openai_utils import create_json_chat_completion, get_client


def _system_prompt_translate(theme_title: str, description_hint: str) -> str:
    return f"""あなたは中高生の英語スピーキング学習を支援する英語教師です。
生徒が日本語で書いたテーマ「{theme_title}」についての文章を、生徒自身が声に出して読む
スピーチ原稿として自然な英語に翻訳してください。

【テーマのヒント】
{description_hint or "（特になし）"}

【方針】
- 直訳ではなく、声に出して読みやすい自然な英語にする。
- 生徒の学年（中高生）が発音・音読練習に使える平易な語彙・構文を優先する。
- 生徒が書いた内容・意図はできるだけ忠実に反映する。
- 全体で3〜6文程度の分量にまとめる。

出力は次のJSON形式のみ:
{{
  "output_text": "完成した英文スピーチ原稿",
  "notes": "翻訳時に工夫した点や意訳した箇所の簡単な日本語コメント（1〜2文）"
}}"""


def _system_prompt_correct(theme_title: str, description_hint: str) -> str:
    return f"""あなたは中高生の英語スピーキング学習を支援する英語教師です。
生徒が英語で書いたテーマ「{theme_title}」についてのスピーチ原稿を校正してください。

【テーマのヒント】
{description_hint or "（特になし）"}

【方針】
- 文法・語彙・自然さの誤りを修正し、声に出して読みやすい自然な英語にする。
- 生徒が書いた内容・意図・文の長さはできるだけ維持する（書き直しすぎない）。
- 修正箇所は簡潔に列挙する。

出力は次のJSON形式のみ:
{{
  "output_text": "校正後の完成英文",
  "corrections": [
    {{"before": "修正前の該当箇所", "after": "修正後の該当箇所", "reason": "短い日本語の理由"}}
  ],
  "notes": "全体的な講評（1〜2文、日本語、励ましを含める）"
}}"""


def translate_script(*, input_text: str, theme_title: str, description_hint: str, model: str, api_key: str) -> dict:
    if not api_key:
        raise ValueError("OpenAI API キーが未設定です。")
    if not (input_text or "").strip():
        raise ValueError("入力テキストが空です。")

    client = get_client(api_key)
    data = create_json_chat_completion(
        client,
        model,
        [
            {"role": "system", "content": _system_prompt_translate(theme_title, description_hint)},
            {"role": "user", "content": input_text.strip()},
        ],
        temperature=0.4,
    )
    output_text = str(data.get("output_text") or "").strip()
    if not output_text:
        raise ValueError("AIからの翻訳結果が空でした。")
    return {
        "output_text": output_text,
        "notes": str(data.get("notes") or "").strip(),
        "corrections": [],
    }


def correct_script(*, input_text: str, theme_title: str, description_hint: str, model: str, api_key: str) -> dict:
    if not api_key:
        raise ValueError("OpenAI API キーが未設定です。")
    if not (input_text or "").strip():
        raise ValueError("入力テキストが空です。")

    client = get_client(api_key)
    data = create_json_chat_completion(
        client,
        model,
        [
            {"role": "system", "content": _system_prompt_correct(theme_title, description_hint)},
            {"role": "user", "content": input_text.strip()},
        ],
        temperature=0.3,
    )
    output_text = str(data.get("output_text") or "").strip()
    if not output_text:
        raise ValueError("AIからの校正結果が空でした。")
    corrections_raw = data.get("corrections")
    corrections = []
    if isinstance(corrections_raw, list):
        for item in corrections_raw:
            if isinstance(item, dict):
                corrections.append(
                    {
                        "before": str(item.get("before") or "").strip(),
                        "after": str(item.get("after") or "").strip(),
                        "reason": str(item.get("reason") or "").strip(),
                    }
                )
    return {
        "output_text": output_text,
        "notes": str(data.get("notes") or "").strip(),
        "corrections": corrections,
    }
