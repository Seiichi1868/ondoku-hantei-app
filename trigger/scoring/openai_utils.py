"""OpenAI Chat Completions 呼び出しの小さな共通処理（trigger 独自実装）。

news_app / level_check / debate と同種の処理だが、依存関係を持たせないよう
import せず trigger 内で完全に独立して実装する。
"""
import json
import re

MAX_COMPLETION_TOKENS = 2048


def parse_json_object(raw: str) -> dict:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    return data


def extract_completion_text(completion) -> str:
    if not completion.choices:
        return ""
    content = getattr(completion.choices[0].message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text") or ""))
            else:
                text = getattr(part, "text", None)
                if text:
                    parts.append(str(text))
        return "".join(parts).strip()
    return str(content or "").strip()


def is_reasoning_chat_model(model: str) -> bool:
    name = (model or "").strip().lower()
    if name.startswith("gpt-5") and "chat" not in name:
        return True
    return name.startswith(("o1", "o3", "o4"))


def create_json_chat_completion(client, model: str, messages: list, *, temperature: float = 0.3) -> dict:
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    if is_reasoning_chat_model(model):
        kwargs["max_completion_tokens"] = MAX_COMPLETION_TOKENS
        kwargs["reasoning_effort"] = "none"
    else:
        kwargs["temperature"] = temperature

    completion = client.chat.completions.create(**kwargs)
    raw = extract_completion_text(completion)
    if not raw:
        finish_reason = ""
        if completion.choices:
            finish_reason = str(completion.choices[0].finish_reason or "")
        raise ValueError(f"AIからの応答が空でした (finish_reason={finish_reason or 'unknown'})")
    return parse_json_object(raw)


def get_client(api_key: str, timeout: float = 60.0, max_retries: int = 1):
    from openai import OpenAI

    return OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)
