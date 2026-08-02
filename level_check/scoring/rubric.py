"""採点ルーブリック（5軸）の定義と、CEFR帯への変換ロジック。

RUBRIC の weight はここがデフォルト値。実際に使う重みは管理画面設定
（level_check_settings.json）に保存された値を優先し、コード変更なしで
調整できるようにする（evaluator.py / admin/routes.py 参照）。
"""

# 各軸 1〜5 点、重みは合計 1.0 になるよう正規化して使用する。
DEFAULT_RUBRIC = {
    "fluency": {
        "label": "流暢さ",
        "weight": 0.2,
        "description": "間・言い淀み・発話速度の自然さ",
    },
    "pronunciation": {
        "label": "発音・明瞭性",
        "weight": 0.2,
        "description": "聞き取りやすさ・明瞭性（文字起こし結果から推定される、聞き取りにくさ・言い直しの少なさ）",
    },
    "accuracy": {
        "label": "文法的正確性",
        "weight": 0.2,
        "description": "文法的正確性（お題文・想定解答との一致度も含む）",
    },
    "vocabulary": {
        "label": "語彙運用",
        "weight": 0.2,
        "description": "場面に応じた語彙運用の適切さ",
    },
    "response_latency": {
        "label": "応答速度",
        "weight": 0.2,
        "description": "出題（音声・文字提示の完了）から発話開始までの応答速度",
    },
}

RUBRIC_AXES = tuple(DEFAULT_RUBRIC.keys())

# response_latency はLLMではなく実測ミリ秒から機械的に1〜5点へ変換する
# （タスクにより「聞き取り→即応答」までに要する自然な準備時間が異なるため、
#  タスク種別ごとに閾値を分ける）。
LATENCY_THRESHOLDS_MS = {
    "repeat": [(1200, 5), (2000, 4), (3200, 3), (5000, 2)],
    "sentence_build": [(2500, 5), (4000, 4), (6000, 3), (9000, 2)],
    "qa": [(2000, 5), (3500, 4), (5500, 3), (8500, 2)],
}
LATENCY_MIN_SCORE = 1

# 5軸重み付き平均（1〜5）→ CEFR 帯への変換しきい値
CEFR_BAND_THRESHOLDS = (
    (4.5, "C2"),
    (4.0, "C1"),
    (3.3, "B2"),
    (2.6, "B1"),
    (1.8, "A2"),
)
CEFR_FLOOR_BAND = "A1"
CEFR_BANDS = ("A1", "A2", "B1", "B2", "C1", "C2")

# 総合評価（Versant方式の100点満点スコア）を出す際の、タスク種別ごとの比重。
# 「短時間Q&A課題」は自由発話でより総合的な運用力を反映するため比重を高くし、
# リピート課題・文再構成課題は互いに均等（かつQ&Aより低い比重）にする。
OVERALL_TASK_WEIGHTS = {
    "repeat": 0.25,
    "sentence_build": 0.25,
    "qa": 0.5,
}


def normalize_rubric_weights(raw: dict | None) -> dict:
    """weight のみを取り出し合計1.0になるよう正規化する。不正値はデフォルトへ。"""
    weights = {}
    for axis in RUBRIC_AXES:
        try:
            value = float((raw or {}).get(axis, DEFAULT_RUBRIC[axis]["weight"]))
        except (TypeError, ValueError):
            value = DEFAULT_RUBRIC[axis]["weight"]
        weights[axis] = max(0.0, value)

    total = sum(weights.values())
    if total <= 0:
        return {axis: DEFAULT_RUBRIC[axis]["weight"] for axis in RUBRIC_AXES}
    return {axis: weights[axis] / total for axis in RUBRIC_AXES}


def latency_score(task_type: str, latency_ms: float | None) -> int:
    """応答速度（ms）を1〜5点へ変換。計測不可の場合は中央値3点。"""
    if latency_ms is None:
        return 3
    thresholds = LATENCY_THRESHOLDS_MS.get(task_type, LATENCY_THRESHOLDS_MS["qa"])
    for limit_ms, score in thresholds:
        if latency_ms <= limit_ms:
            return score
    return LATENCY_MIN_SCORE


def weighted_total(scores: dict, weights: dict) -> float:
    """5軸スコア（1〜5）と重みから加重平均（1〜5）を計算する。"""
    normalized_weights = normalize_rubric_weights(weights)
    total = 0.0
    for axis in RUBRIC_AXES:
        try:
            value = float(scores.get(axis, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        value = max(0.0, min(5.0, value))
        total += value * normalized_weights[axis]
    return round(total, 2)


def band_for_score(score: float) -> str:
    for threshold, band in CEFR_BAND_THRESHOLDS:
        if score >= threshold:
            return band
    return CEFR_FLOOR_BAND


def score_to_100(score_1to5: float) -> int:
    """5点満点スコアを Versant 方式に倣った100点満点スコアへ変換する。"""
    clamped = max(0.0, min(5.0, score_1to5))
    return round(clamped / 5 * 100)


def overall_score_from_task_averages(task_averages: dict) -> float | None:
    """タスク種別ごとの平均（1〜5）から、Q&Aの比重を高くした総合スコア（1〜5）を計算する。"""
    weighted_sum = 0.0
    weight_used = 0.0
    for task_type, avg in task_averages.items():
        if avg is None:
            continue
        weight = OVERALL_TASK_WEIGHTS.get(task_type, 1.0)
        weighted_sum += avg * weight
        weight_used += weight
    if weight_used <= 0:
        return None
    return round(weighted_sum / weight_used, 2)
