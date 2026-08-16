"""Versant 相当カテゴリ・CEFR 帯変換（level_check/scoring/rubric.py と同じ考え方の独自コピー）。

Versantカテゴリへのマッピング方針:
  Sentence Mastery … ステップ5（即興スピーチの文構成）
  Vocabulary        … ステップ5（語彙選択）
  Fluency           … ステップ3・ステップ5（発話の滑らかさ）
  Pronunciation     … ステップ3（音読評価）
  Comprehension     … ステップ4（Q&Aの受け答え適切性）
  Overall / CEFR    … 全ステップの加重平均
"""

VERSANT_CATEGORIES = ("sentence_mastery", "vocabulary", "fluency", "pronunciation", "comprehension")

VERSANT_LABELS = {
    "sentence_mastery": "Sentence Mastery（文構成）",
    "vocabulary": "Vocabulary（語彙）",
    "fluency": "Fluency（流暢さ）",
    "pronunciation": "Pronunciation（発音）",
    "comprehension": "Comprehension（内容理解・応答）",
}

# 1〜5点 → 10〜90点（Speaking Level Score 相当）への線形写像
SCORE_SCALE_MIN = 10
SCORE_SCALE_MAX = 90

CEFR_BAND_THRESHOLDS_90 = (
    (85, "C2"),
    (76, "C1"),
    (67, "B2+"),
    (59, "B2"),
    (51, "B1+"),
    (43, "B1"),
    (36, "A2+"),
    (30, "A2"),
    (22, "A1"),
)
CEFR_FLOOR_BAND = "A1>"


def clamp_score_1to5(value) -> int:
    try:
        score = round(float(value))
    except (TypeError, ValueError):
        return 3
    return max(1, min(5, score))


def score_1to5_to_90(score_1to5: float | None) -> int | None:
    if score_1to5 is None:
        return None
    clamped = max(0.0, min(5.0, float(score_1to5)))
    span = SCORE_SCALE_MAX - SCORE_SCALE_MIN
    mapped = SCORE_SCALE_MIN + (clamped - 1.0) * (span / 4.0)
    return round(max(SCORE_SCALE_MIN, min(SCORE_SCALE_MAX, mapped)))


def band_for_score_90(score_90: float | None) -> str | None:
    if score_90 is None:
        return None
    for threshold, band in CEFR_BAND_THRESHOLDS_90:
        if score_90 >= threshold:
            return band
    return CEFR_FLOOR_BAND


def band_for_score_1to5(score_1to5: float | None) -> str | None:
    return band_for_score_90(score_1to5_to_90(score_1to5))


def average(values: list[float]) -> float | None:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 2)


def normalize_versant_weights(raw: dict | None) -> dict:
    from trigger.config import DEFAULT_VERSANT_WEIGHTS

    weights = {}
    for key, default in DEFAULT_VERSANT_WEIGHTS.items():
        try:
            value = float((raw or {}).get(key, default))
        except (TypeError, ValueError):
            value = default
        weights[key] = max(0.0, value)
    total = sum(weights.values())
    if total <= 0:
        return dict(DEFAULT_VERSANT_WEIGHTS)
    return {key: value / total for key, value in weights.items()}


def combine_overall_1to5(category_scores_1to5: dict, weights: dict | None = None) -> float | None:
    normalized_weights = normalize_versant_weights(weights)
    total = 0.0
    weight_sum = 0.0
    for category in VERSANT_CATEGORIES:
        value = category_scores_1to5.get(category)
        if value is None:
            continue
        w = normalized_weights.get(category, 0.0)
        total += float(value) * w
        weight_sum += w
    if weight_sum <= 0:
        return None
    return round(total / weight_sum, 2)
