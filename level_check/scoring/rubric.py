"""採点ルーブリック（スピーキング5軸／リスニング2軸）と Speaking Level Score（10〜90）・CEFR帯変換。

重みはここがデフォルト値。実際に使う重みは管理画面設定
（level_check_settings.json）に保存された値を優先し、コード変更なしで調整できる。
"""

from level_check.config import DEFAULT_OVERALL_WEIGHTS

# ── スピーキング（カテゴリ B・E・F） ─────────────────────────
DEFAULT_SPEAKING_RUBRIC = {
    "fluency": {
        "label": "流暢さ",
        "weight": 0.2,
        "description": "間・言い淀み・発話速度",
    },
    "pronunciation": {
        "label": "発音・明瞭性",
        "weight": 0.2,
        "description": "聞き取りやすさ・明瞭性",
    },
    "accuracy": {
        "label": "文法的正確性",
        "weight": 0.2,
        "description": "文法的正確性",
    },
    "vocabulary": {
        "label": "語彙運用",
        "weight": 0.2,
        "description": "場面に応じた語彙運用",
    },
    "response_latency": {
        "label": "応答速度",
        "weight": 0.2,
        "description": "出題から発話開始までの応答速度",
    },
}

# ── リスニング（カテゴリ A・C・D） ───────────────────────────
DEFAULT_LISTENING_RUBRIC = {
    "comprehension_accuracy": {
        "label": "内容理解",
        "weight": 0.7,
        "description": "質問・会話・文章の内容を正しく理解できているか",
    },
    "response_relevance": {
        "label": "応答の的確さ",
        "weight": 0.3,
        "description": "聞かれたことに対して的確に答えられているか",
    },
}

SPEAKING_AXES = tuple(DEFAULT_SPEAKING_RUBRIC.keys())
LISTENING_AXES = tuple(DEFAULT_LISTENING_RUBRIC.keys())

# 後方互換エイリアス（旧コード参照用）
DEFAULT_RUBRIC = DEFAULT_SPEAKING_RUBRIC
RUBRIC_AXES = SPEAKING_AXES

# response_latency は LLM ではなく実測ミリ秒から機械的に 1〜5 点へ変換する
LATENCY_THRESHOLDS_MS = {
    "A": [(2000, 5), (3500, 4), (5500, 3), (8500, 2)],
    "B": [(1200, 5), (2000, 4), (3200, 3), (5000, 2)],
    "C": [(2500, 5), (4000, 4), (6000, 3), (9000, 2)],
    "D": [(2500, 5), (4000, 4), (6000, 3), (9000, 2)],
    "E": [(3000, 5), (5000, 4), (8000, 3), (12000, 2)],
    "F": [(2500, 5), (4000, 4), (6500, 3), (10000, 2)],
}
LATENCY_MIN_SCORE = 1

# Speaking Level Score（10〜90）→ CEFR 帯（参考スケールチャート準拠）
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
CEFR_BANDS = ("A1>", "A1", "A2", "A2+", "B1", "B1+", "B2", "B2+", "C1", "C2")

# パート単位で CEFR 帯を出すカテゴリ（スピーキング産出系のみ）
CEFR_PART_CATEGORIES = frozenset({"E", "F"})

SCORE_SCALE_MIN = 10
SCORE_SCALE_MAX = 90


def normalize_weights(raw: dict | None, defaults: dict, axes: tuple[str, ...]) -> dict:
    """weight のみを取り出し合計1.0になるよう正規化する。不正値はデフォルトへ。"""
    weights = {}
    for axis in axes:
        try:
            value = float((raw or {}).get(axis, defaults[axis]["weight"]))
        except (TypeError, ValueError):
            value = defaults[axis]["weight"]
        weights[axis] = max(0.0, value)

    total = sum(weights.values())
    if total <= 0:
        return {axis: defaults[axis]["weight"] for axis in axes}
    return {axis: weights[axis] / total for axis in axes}


def normalize_speaking_weights(raw: dict | None) -> dict:
    return normalize_weights(raw, DEFAULT_SPEAKING_RUBRIC, SPEAKING_AXES)


def normalize_listening_weights(raw: dict | None) -> dict:
    return normalize_weights(raw, DEFAULT_LISTENING_RUBRIC, LISTENING_AXES)


def normalize_rubric_weights(raw: dict | None) -> dict:
    """後方互換: 旧 speaking 5軸の正規化。"""
    return normalize_speaking_weights(raw)


def normalize_overall_weights(raw: dict | None) -> dict:
    try:
        speaking = float((raw or {}).get("speaking", DEFAULT_OVERALL_WEIGHTS["speaking"]))
    except (TypeError, ValueError):
        speaking = DEFAULT_OVERALL_WEIGHTS["speaking"]
    try:
        listening = float((raw or {}).get("listening", DEFAULT_OVERALL_WEIGHTS["listening"]))
    except (TypeError, ValueError):
        listening = DEFAULT_OVERALL_WEIGHTS["listening"]
    speaking = max(0.0, speaking)
    listening = max(0.0, listening)
    total = speaking + listening
    if total <= 0:
        return dict(DEFAULT_OVERALL_WEIGHTS)
    return {"speaking": speaking / total, "listening": listening / total}


def latency_score(category: str, latency_ms: float | None) -> int:
    """応答速度（ms）を1〜5点へ変換。計測不可の場合は中央値3点。"""
    if latency_ms is None:
        return 3
    thresholds = LATENCY_THRESHOLDS_MS.get(category, LATENCY_THRESHOLDS_MS["F"])
    for limit_ms, score in thresholds:
        if latency_ms <= limit_ms:
            return score
    return LATENCY_MIN_SCORE


def weighted_total(scores: dict, weights: dict, axes: tuple[str, ...]) -> float:
    """各軸スコア（1〜5）と重みから加重平均（1〜5）を計算する。"""
    total = 0.0
    weight_sum = 0.0
    for axis in axes:
        try:
            value = float(scores.get(axis, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        value = max(0.0, min(5.0, value))
        w = float(weights.get(axis, 0) or 0)
        total += value * w
        weight_sum += w
    if weight_sum <= 0:
        return 0.0
    return round(total / weight_sum if abs(weight_sum - 1.0) > 1e-6 else total, 2)


def speaking_weighted_total(scores: dict, weights: dict | None = None) -> float:
    normalized = normalize_speaking_weights(weights)
    return weighted_total(scores, normalized, SPEAKING_AXES)


def listening_weighted_total(scores: dict, weights: dict | None = None) -> float:
    normalized = normalize_listening_weights(weights)
    return weighted_total(scores, normalized, LISTENING_AXES)


def score_1to5_to_90(score_1to5: float | None) -> int | None:
    """1〜5点の加重平均を Speaking Level Score（10〜90）へ変換する。

    参考スケールに合わせ、1点→10（観光客）、3点→50（B1）、5点→90（C2）となるよう
    線形写像する。
    """
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


def band_for_score(score_1to5: float) -> str:
    """1〜5点から CEFR 帯を返す（パート単位の目安表示用）。"""
    return band_for_score_90(score_1to5_to_90(score_1to5)) or CEFR_FLOOR_BAND


def cefr_band_for_part(category: str, score_1to5: float | None) -> str | None:
    """E/F のみ CEFR 帯を返す。それ以外は None。"""
    if str(category or "").upper() not in CEFR_PART_CATEGORIES:
        return None
    if score_1to5 is None:
        return None
    return band_for_score(score_1to5)


def combine_overall_score(
    speaking_score_90: int | None,
    listening_score_90: int | None,
    overall_weights: dict | None = None,
) -> int | None:
    """スピーキング／リスニングの 0〜90 サブスコアを合成して総合スコアを返す。"""
    weights = normalize_overall_weights(overall_weights)
    values = []
    used = []
    if speaking_score_90 is not None:
        values.append(speaking_score_90 * weights["speaking"])
        used.append(weights["speaking"])
    if listening_score_90 is not None:
        values.append(listening_score_90 * weights["listening"])
        used.append(weights["listening"])
    if not values:
        return None
    weight_used = sum(used)
    if weight_used <= 0:
        return None
    return round(sum(values) / weight_used)
