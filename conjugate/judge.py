"""LLMを呼ばないルールベースの採点ロジック。

4段階評価:
  - correct            完全正解（変換すべき箇所が合っていれば主語Tuの有無は問わない）
  - pronoun_error       再帰代名詞te抜け／me・teの混同（gustar型含む）
  - conjugation_error   動詞本体はほぼ合っているが活用形が間違っている
  - way_off             全く違う

アクセント記号（á,é,í,ó,ú,ñ）・大文字小文字・句読点・前後の空白の揺れは
normalize_text() で吸収する。厳密モード（strict）ではアクセントの違いも
別物として扱う。

評価の重心:
  yo形からtú形へ「変化させる語」が正しく変わっていること。
  元の文と同じままの語は、発話全体が正解とかけ離れていない限り許容する。
  主語代名詞（yo / tú / usted）の有無は採点対象にしない。
"""
import difflib
import re
import unicodedata

from conjugate.data.conjugations import build_forms
from conjugate.data.gustar import GUSTAR_HINT

_ACCENT_MAP = str.maketrans(
    "áéíóúÁÉÍÓÚñÑ",
    "aeiouAEIOUnN",
)

# 正規化後の表記。tú → tu
_OPTIONAL_SUBJECTS = {"yo", "tu", "usted"}
_STRUCTURE_WORDS = {"estas", "estoy", "vas", "voy", "a", "yo", "tu", "usted"}
_WAY_OFF_RATIO = 0.32


def normalize_text(text: str, strict: bool = False) -> str:
    """比較用に正規化する。strict=Trueの場合はアクセントを保持する。"""
    if not text:
        return ""
    s = text.strip().lower()
    # 句点等の記号を除去（¡ ¿ 等も含む）。文字・数字・空白・アクセント文字のみ残す。
    s = re.sub(r"[^\w\sáéíóúñÁÉÍÓÚÑ]", " ", s, flags=re.UNICODE)
    if not strict:
        s = s.translate(_ACCENT_MAP)
    else:
        # strictでも全角/合成済み文字のゆらぎだけは正規化する
        s = unicodedata.normalize("NFC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _tokens(s: str) -> list[str]:
    return s.split() if s else []


def _core_tokens(norm: str) -> list[str]:
    """主語代名詞（yo/tú/usted）を除いたトークン。"""
    return [t for t in _tokens(norm) if t not in _OPTIONAL_SUBJECTS]


def _content_word(expected_norm: str) -> str:
    """構造語（estas/vas/a/voy/yo/te）を除いた、活用の核となる語を1語返す。"""
    for tok in reversed(_core_tokens(expected_norm)):
        if tok not in _STRUCTURE_WORDS and tok != "te":
            return tok
    cores = _core_tokens(expected_norm)
    return cores[-1] if cores else expected_norm


def _has_stem_overlap(expected_word: str, actual_tokens: list[str]) -> bool:
    if not expected_word:
        return False
    overlap_len = max(2, min(4, len(expected_word) - 1))
    prefix = expected_word[:overlap_len]
    return any(tok.startswith(prefix) or expected_word.startswith(tok[:overlap_len]) for tok in actual_tokens if tok)


def _fuzzy_ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _changed_tokens(yo_tokens: list[str], tu_tokens: list[str]) -> list[str]:
    """yo形には無く、tú形で新たに現れる語＝変換すべき箇所。"""
    yo_set = set(yo_tokens)
    return [t for t in tu_tokens if t not in yo_set]


def _transformation_done(must_change: list[str], actual_tokens: list[str]) -> bool:
    if not must_change:
        return False
    return all(token in actual_tokens for token in must_change)


def _close_enough_overall(expected_core: str, actual_core: str, actual_tokens: list[str], content_word: str) -> bool:
    """変換はできている前提で、発話全体が正解から大きく外れていないか。"""
    ratio = _fuzzy_ratio(expected_core, actual_core)
    return ratio >= _WAY_OFF_RATIO or _has_stem_overlap(content_word, actual_tokens)


def _pronoun_only_mismatch(expected_tokens: list[str], actual_tokens: list[str]) -> bool:
    """me/te 以外が一致している（代名詞ミス専用）。"""
    core_expected = " ".join(t for t in expected_tokens if t != "te")
    core_actual = " ".join(t for t in actual_tokens if t not in ("te", "me"))
    return bool(core_expected) and core_actual == core_expected


def _empty_answer_message(source: str) -> str:
    if source == "typed":
        return "入力が空です。スペルをタイプしてください。"
    return "発話が認識できませんでした。もう一度はっきり発話してください。"


def grade_regular(verb: dict, tense: str, transcript: str, strict: bool = False, source: str = "speech") -> dict:
    """通常の99語ドリル（現在形/進行形/近接未来/点過去）の採点。"""
    forms = build_forms(verb)[tense]
    expected_sentence = forms["tu"]
    yo_sentence = forms["yo"]
    expected_norm = normalize_text(expected_sentence.rstrip("."), strict)
    actual_norm = normalize_text(transcript, strict)
    yo_norm = normalize_text(yo_sentence.rstrip("."), strict)

    result = {
        "expected_sentence": expected_sentence,
        "yo_sentence": yo_sentence,
        "transcript": transcript,
    }

    if not actual_norm:
        result["level"] = "way_off"
        result["message"] = _empty_answer_message(source)
        return result

    expected_tokens = _core_tokens(expected_norm)
    actual_tokens = _core_tokens(actual_norm)
    yo_tokens = _core_tokens(yo_norm)
    expected_core = " ".join(expected_tokens)
    actual_core = " ".join(actual_tokens)

    if expected_tokens and expected_tokens == actual_tokens:
        result["level"] = "correct"
        result["message"] = "完璧です！正解です。"
        return result

    reflexive = bool(verb.get("reflexive"))
    if reflexive and _pronoun_only_mismatch(expected_tokens, actual_tokens):
        if "te" not in actual_tokens and "me" in actual_tokens:
            result["level"] = "pronoun_error"
            result["message"] = "動詞の形は正解です。ただしtúなので「me」ではなく「te」を使いましょう。"
            return result
        if "te" not in actual_tokens:
            result["level"] = "pronoun_error"
            result["message"] = "動詞の形は正解ですが、再帰代名詞「te」が抜けています。"
            return result

    must_change = _changed_tokens(yo_tokens, expected_tokens)
    content_word = _content_word(expected_norm)

    if _transformation_done(must_change, actual_tokens) and _close_enough_overall(
        expected_core, actual_core, actual_tokens, content_word
    ):
        result["level"] = "correct"
        result["message"] = "完璧です！正解です。"
        return result

    if _has_stem_overlap(content_word, actual_tokens) or _fuzzy_ratio(expected_core, actual_core) >= 0.55:
        result["level"] = "conjugation_error"
        result["message"] = f"動詞は近いですが活用形が違います。正解は「{expected_sentence}」です。"
        return result

    result["level"] = "way_off"
    result["message"] = f"正解と大きく異なります。正解は「{expected_sentence}」です。"
    return result


def grade_gustar(item: dict, transcript: str, strict: bool = False, source: str = "speech") -> dict:
    """#29 gustar 特殊構文モードの採点（動詞は不変、me→teのみ変化）。"""
    expected_sentence = item["tu_sentence"]
    yo_sentence = item["yo_sentence"]
    expected_norm = normalize_text(expected_sentence.rstrip("."), strict)
    actual_norm = normalize_text(transcript, strict)
    yo_norm = normalize_text(yo_sentence.rstrip("."), strict)

    result = {
        "expected_sentence": expected_sentence,
        "yo_sentence": yo_sentence,
        "transcript": transcript,
    }

    if not actual_norm:
        result["level"] = "way_off"
        result["message"] = _empty_answer_message(source)
        return result

    expected_tokens = _core_tokens(expected_norm)
    actual_tokens = _core_tokens(actual_norm)
    yo_tokens = _core_tokens(yo_norm)
    expected_core = " ".join(expected_tokens)
    actual_core = " ".join(actual_tokens)

    if expected_tokens and expected_tokens == actual_tokens:
        result["level"] = "correct"
        result["message"] = "完璧です！gustarはme→teの変化だけでOKでしたね。"
        return result

    # 典型的な誤答: gustar自体を活用してしまう（gustas等）
    verb_token = next((t for t in expected_tokens if t.startswith("gust")), "")
    wrong_conjugated = any(
        t.startswith("gust") and t != verb_token and t not in ("gusta", "gustan")
        for t in actual_tokens
    )
    if wrong_conjugated:
        result["level"] = "conjugation_error"
        result["message"] = GUSTAR_HINT
        return result

    if _pronoun_only_mismatch(expected_tokens, actual_tokens):
        result["level"] = "pronoun_error"
        if "me" in actual_tokens:
            result["message"] = f"惜しい！túに話しかけるので「me」ではなく「te」を使います。正解: {expected_sentence}"
        else:
            result["message"] = f"惜しい！「te」が抜けています。正解: {expected_sentence}"
        return result

    must_change = _changed_tokens(yo_tokens, expected_tokens)
    content_word = _content_word(expected_norm)
    if _transformation_done(must_change, actual_tokens) and _close_enough_overall(
        expected_core, actual_core, actual_tokens, content_word
    ):
        result["level"] = "correct"
        result["message"] = "完璧です！gustarはme→teの変化だけでOKでしたね。"
        return result

    if _fuzzy_ratio(expected_core, actual_core) >= 0.55:
        result["level"] = "conjugation_error"
        result["message"] = f"少し違います。正解は「{expected_sentence}」です。{GUSTAR_HINT}"
        return result

    result["level"] = "way_off"
    result["message"] = f"正解と大きく異なります。正解は「{expected_sentence}」です。"
    return result


LEVEL_LABELS = {
    "correct": "正解",
    "pronoun_error": "代名詞ミス（惜しい）",
    "conjugation_error": "活用形間違い",
    "way_off": "全く違う",
}
