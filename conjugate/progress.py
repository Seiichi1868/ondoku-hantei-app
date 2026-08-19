"""ストリーク・累計練習数・習得の純ロジック。

活用はデフォルト5回正解で習得（累計。不正解でも回数は減らない）。
単語4択は方向（日→西 / 西→日）ごとにデフォルト5回連続正解でマスター。
間違えると連続カウントはゼロに戻る。しきい値は管理画面から渡す。
"""
from datetime import date, datetime, timedelta, timezone

from conjugate.data.conjugations import TENSE_ORDER
from conjugate.data.verbs import VERBS, drillable_verbs

JST = timezone(timedelta(hours=9))
DEFAULT_CONJUGATION_THRESHOLD = 5
DEFAULT_VOCAB_THRESHOLD = 5
DEFAULT_GUARDIAN_PRICE_COINS = 50
VOCAB_DIRECTIONS = ("ja_to_es", "es_to_ja")

DEFAULT_PROGRESS = {
    "last_practice_date": None,
    "practice_dates": [],
    "daily_attempts": {},
    "daily_goal": 0,
    "current_streak": 0,
    "longest_streak": 0,
    "total_attempts": 0,
    "coins": 0,
    "guardian_count": 0,
    "verbs": {},
    "vocab": {},
}


def today_jst(now: datetime | None = None) -> date:
    current = now or datetime.now(JST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=JST)
    return current.astimezone(JST).date()


def _as_nonneg_int(value, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _iso_date(value) -> str | None:
    text = str(value or "").strip()[:10]
    if len(text) != 10:
        return None
    try:
        date.fromisoformat(text)
    except ValueError:
        return None
    return text


def normalize_progress(raw: dict | None) -> dict:
    data = {
        "last_practice_date": None,
        "practice_dates": [],
        "daily_attempts": {},
        "daily_goal": 0,
        "current_streak": 0,
        "longest_streak": 0,
        "total_attempts": 0,
        "coins": 0,
        "guardian_count": 0,
        "verbs": {},
        "vocab": {},
    }
    if not isinstance(raw, dict):
        return data

    last = _iso_date(raw.get("last_practice_date"))
    if last:
        data["last_practice_date"] = last

    dates = []
    seen = set()
    raw_dates = raw.get("practice_dates")
    if isinstance(raw_dates, list):
        for item in raw_dates:
            iso = _iso_date(item)
            if iso and iso not in seen:
                seen.add(iso)
                dates.append(iso)
    if last and last not in seen:
        dates.append(last)
    dates.sort()
    data["practice_dates"] = dates

    daily = raw.get("daily_attempts")
    if isinstance(daily, dict):
        cleaned_daily = {}
        for key, value in daily.items():
            iso = _iso_date(key)
            if iso:
                cleaned_daily[iso] = _as_nonneg_int(value)
        data["daily_attempts"] = cleaned_daily

    data["daily_goal"] = min(100, _as_nonneg_int(raw.get("daily_goal")))

    for key in ("current_streak", "longest_streak", "total_attempts", "coins", "guardian_count"):
        data[key] = _as_nonneg_int(raw.get(key))

    verbs = raw.get("verbs")
    if isinstance(verbs, dict):
        cleaned = {}
        for verb_id, entry in verbs.items():
            if not isinstance(entry, dict):
                continue
            tense_map = {}
            max_correct = 0
            any_mastered = False
            for tense, tense_entry in entry.items():
                if tense not in TENSE_ORDER or not isinstance(tense_entry, dict):
                    continue
                consecutive = _as_nonneg_int(tense_entry.get("consecutive_correct"))
                t_correct = _as_nonneg_int(tense_entry.get("correct_count"), consecutive)
                t_correct = max(t_correct, consecutive)
                mastered = bool(tense_entry.get("mastered"))
                any_mastered = any_mastered or mastered
                max_correct = max(max_correct, t_correct)
                tense_map[tense] = {
                    "consecutive_correct": consecutive,
                    "correct_count": t_correct,
                    "mastered": mastered,
                }
            verb_correct = max(_as_nonneg_int(entry.get("correct_count")), max_correct)
            # 旧仕様（3回連続で習得）のマスター済み語を、新しきい値でも落とさない
            if any_mastered or bool(entry.get("mastered")):
                verb_correct = max(verb_correct, DEFAULT_CONJUGATION_THRESHOLD)
            row = {
                "correct_count": verb_correct,
                "mastered": verb_correct >= DEFAULT_CONJUGATION_THRESHOLD,
            }
            row.update(tense_map)
            cleaned[str(verb_id)] = row
        data["verbs"] = cleaned

    vocab = raw.get("vocab")
    if isinstance(vocab, dict):
        cleaned_vocab = {}
        for verb_id, entry in vocab.items():
            if not isinstance(entry, dict):
                continue
            cleaned_vocab[str(verb_id)] = _normalize_vocab_entry(entry)
        data["vocab"] = cleaned_vocab
    return data


def _vocab_side(raw_side, fallback: int = 0) -> dict:
    consecutive = 0
    mastered = False
    if isinstance(raw_side, dict):
        consecutive = _as_nonneg_int(raw_side.get("consecutive_correct"))
        if consecutive <= 0 and "consecutive_correct" not in raw_side:
            consecutive = _as_nonneg_int(raw_side.get("correct_count"))
        mastered = bool(raw_side.get("mastered"))
    if consecutive <= 0:
        consecutive = fallback
    mastered = mastered or consecutive >= DEFAULT_VOCAB_THRESHOLD
    return {
        "consecutive_correct": consecutive,
        "correct_count": consecutive,
        "mastered": mastered,
    }


def _normalize_vocab_entry(entry: dict) -> dict:
    legacy = _as_nonneg_int(entry.get("correct_count"))
    has_sides = any(isinstance(entry.get(direction), dict) for direction in VOCAB_DIRECTIONS)
    fallback = 0 if has_sides else legacy
    sides = {direction: _vocab_side(entry.get(direction), fallback) for direction in VOCAB_DIRECTIONS}
    total = sum(side["correct_count"] for side in sides.values())
    row = {
        "correct_count": total,
        "mastered": any(side["mastered"] for side in sides.values()),
    }
    row.update(sides)
    return row


def apply_streak(progress: dict, today: date) -> bool:
    """練習日を反映する。同日なら False（加算なし）、新しい日なら True。"""
    last_raw = progress.get("last_practice_date")
    last_date = None
    if last_raw:
        try:
            last_date = date.fromisoformat(str(last_raw)[:10])
        except ValueError:
            last_date = None

    iso = today.isoformat()
    dates = progress.setdefault("practice_dates", [])
    if iso not in dates:
        dates.append(iso)
        dates.sort()

    if last_date == today:
        return False

    if last_date == today - timedelta(days=1):
        progress["current_streak"] = int(progress.get("current_streak") or 0) + 1
    else:
        progress["current_streak"] = 1

    progress["longest_streak"] = max(
        int(progress.get("longest_streak") or 0),
        int(progress["current_streak"]),
    )
    progress["last_practice_date"] = iso
    return True


def apply_mastery(
    progress: dict,
    verb_id,
    tense: str | None,
    is_correct: bool,
    threshold: int = DEFAULT_CONJUGATION_THRESHOLD,
) -> bool:
    """動詞の累計正解を更新。新たにマスターしたら True。"""
    if verb_id is None:
        return False
    try:
        key = str(int(verb_id))
    except (TypeError, ValueError):
        return False

    threshold = max(1, int(threshold or DEFAULT_CONJUGATION_THRESHOLD))
    verbs = progress.setdefault("verbs", {})
    entry = verbs.setdefault(key, {"correct_count": 0, "mastered": False})
    was_mastered = int(entry.get("correct_count") or 0) >= threshold

    if tense in TENSE_ORDER:
        tense_entry = entry.setdefault(
            tense, {"consecutive_correct": 0, "correct_count": 0, "mastered": False}
        )
        if is_correct:
            tense_entry["consecutive_correct"] = int(tense_entry.get("consecutive_correct") or 0) + 1
            tense_entry["correct_count"] = int(tense_entry.get("correct_count") or 0) + 1
        else:
            tense_entry["consecutive_correct"] = 0
        entry[tense] = tense_entry

    if is_correct:
        entry["correct_count"] = int(entry.get("correct_count") or 0) + 1

    entry["mastered"] = int(entry.get("correct_count") or 0) >= threshold
    if tense in TENSE_ORDER:
        entry[tense]["mastered"] = entry["mastered"]
    verbs[key] = entry
    return bool(entry["mastered"]) and not was_mastered


def _vocab_streak(side) -> int:
    if not isinstance(side, dict):
        return 0
    if "consecutive_correct" in side:
        return _as_nonneg_int(side.get("consecutive_correct"))
    return _as_nonneg_int(side.get("correct_count"))


def _vocab_side_mastered(side, threshold: int) -> bool:
    if not isinstance(side, dict):
        return False
    return bool(side.get("mastered")) or _vocab_streak(side) >= threshold


def apply_vocab_mastery(
    progress: dict,
    verb_id,
    is_correct: bool,
    threshold: int = DEFAULT_VOCAB_THRESHOLD,
    direction: str | None = "ja_to_es",
) -> bool:
    """単語クイズの方向別連続正解を更新。新たにマスターしたら True。"""
    if verb_id is None:
        return False
    try:
        key = str(int(verb_id))
    except (TypeError, ValueError):
        return False

    side_key = direction if direction in VOCAB_DIRECTIONS else "ja_to_es"
    threshold = max(1, int(threshold or DEFAULT_VOCAB_THRESHOLD))
    vocab = progress.setdefault("vocab", {})
    entry = vocab.setdefault(key, _normalize_vocab_entry({}))
    blank_side = {"consecutive_correct": 0, "correct_count": 0, "mastered": False}
    for direction_id in VOCAB_DIRECTIONS:
        entry.setdefault(direction_id, dict(blank_side))
    side = entry[side_key]
    was_mastered = _vocab_side_mastered(side, threshold)
    streak = _vocab_streak(side)
    if is_correct:
        streak += 1
    else:
        streak = 0
    side["consecutive_correct"] = streak
    side["correct_count"] = streak
    side["mastered"] = was_mastered or streak >= threshold
    entry[side_key] = side
    entry["correct_count"] = sum(_vocab_streak(entry.get(d)) for d in VOCAB_DIRECTIONS)
    entry["mastered"] = any(_vocab_side_mastered(entry.get(d), threshold) for d in VOCAB_DIRECTIONS)
    vocab[key] = entry
    return bool(side["mastered"]) and not was_mastered


def can_afford_guardian(progress: dict, price: int = DEFAULT_GUARDIAN_PRICE_COINS) -> bool:
    """コイン残高がGuardián交換価格以上あるか。"""
    price = max(1, int(price or DEFAULT_GUARDIAN_PRICE_COINS))
    return int(progress.get("coins") or 0) >= price


def apply_guardian_purchase(progress: dict, price: int = DEFAULT_GUARDIAN_PRICE_COINS) -> bool:
    """コインを消費してGuardiánを1体購入する（発動ロジックはPart 2）。

    残高不足の場合は何も変更せずFalseを返す。
    """
    price = max(1, int(price or DEFAULT_GUARDIAN_PRICE_COINS))
    coins = int(progress.get("coins") or 0)
    if coins < price:
        return False
    progress["coins"] = coins - price
    progress["guardian_count"] = int(progress.get("guardian_count") or 0) + 1
    return True


def apply_attempt(
    progress: dict,
    *,
    verb_id=None,
    tense: str | None = None,
    is_correct: bool = False,
    today: date | None = None,
    kind: str = "conjugation",
    threshold: int | None = None,
    direction: str | None = None,
) -> dict:
    """1回の判定を進捗に反映する。"""
    today = today or today_jst()
    iso = today.isoformat()
    progress["total_attempts"] = int(progress.get("total_attempts") or 0) + 1
    daily = progress.setdefault("daily_attempts", {})
    daily[iso] = int(daily.get(iso) or 0) + 1
    streak_incremented = apply_streak(progress, today)

    if is_correct:
        progress["coins"] = int(progress.get("coins") or 0) + 1

    if kind == "vocab":
        vocab_threshold = threshold if threshold is not None else DEFAULT_VOCAB_THRESHOLD
        newly_mastered = apply_vocab_mastery(
            progress, verb_id, is_correct, vocab_threshold, direction=direction
        )
        conj_threshold = DEFAULT_CONJUGATION_THRESHOLD
    else:
        conj_threshold = threshold if threshold is not None else DEFAULT_CONJUGATION_THRESHOLD
        newly_mastered = apply_mastery(progress, verb_id, tense, is_correct, conj_threshold)

    return {
        "streak_incremented": streak_incremented,
        "newly_mastered": newly_mastered,
        "current_streak": int(progress.get("current_streak") or 0),
        "longest_streak": int(progress.get("longest_streak") or 0),
        "total_attempts": int(progress.get("total_attempts") or 0),
        "mastered_count": mastered_verb_count(progress, conj_threshold),
        "coins": int(progress.get("coins") or 0),
        "coin_earned": bool(is_correct),
        "guardian_count": int(progress.get("guardian_count") or 0),
    }


def verb_is_mastered(entry: dict | None, threshold: int = DEFAULT_CONJUGATION_THRESHOLD) -> bool:
    if not isinstance(entry, dict):
        return False
    return _as_nonneg_int(entry.get("correct_count")) >= max(1, int(threshold or DEFAULT_CONJUGATION_THRESHOLD))


def mastered_verb_count(progress: dict, threshold: int = DEFAULT_CONJUGATION_THRESHOLD) -> int:
    verbs = progress.get("verbs") or {}
    count = 0
    for verb in drillable_verbs():
        if verb_is_mastered(verbs.get(str(verb["id"])), threshold):
            count += 1
    return count


def mastered_vocab_count(
    progress: dict,
    threshold: int = DEFAULT_VOCAB_THRESHOLD,
    direction: str | None = None,
) -> int:
    vocab = progress.get("vocab") or {}
    limit = max(1, int(threshold or DEFAULT_VOCAB_THRESHOLD))
    count = 0
    for verb in VERBS:
        entry = vocab.get(str(verb["id"])) or {}
        if direction in VOCAB_DIRECTIONS:
            if _vocab_side_mastered(entry.get(direction), limit):
                count += 1
        elif any(_vocab_side_mastered(entry.get(d), limit) for d in VOCAB_DIRECTIONS):
            count += 1
    return count


def learner_level(mastered_count: int) -> int:
    return max(1, 1 + max(0, int(mastered_count)) // 5)


def progress_view(
    progress: dict,
    *,
    conjugation_threshold: int = DEFAULT_CONJUGATION_THRESHOLD,
    vocab_threshold: int = DEFAULT_VOCAB_THRESHOLD,
    guardian_price: int = DEFAULT_GUARDIAN_PRICE_COINS,
) -> dict:
    conj_th = max(1, int(conjugation_threshold or DEFAULT_CONJUGATION_THRESHOLD))
    vocab_th = max(1, int(vocab_threshold or DEFAULT_VOCAB_THRESHOLD))
    guardian_price = max(1, int(guardian_price or DEFAULT_GUARDIAN_PRICE_COINS))
    coins = int(progress.get("coins") or 0)
    guardian_count = int(progress.get("guardian_count") or 0)
    mastered = mastered_verb_count(progress, conj_th)
    vocab_mastered = mastered_vocab_count(progress, vocab_th)
    vocab_mastered_ja = mastered_vocab_count(progress, vocab_th, "ja_to_es")
    vocab_mastered_es = mastered_vocab_count(progress, vocab_th, "es_to_ja")
    total_verbs = len(drillable_verbs())
    total_vocab = len(VERBS)
    last = progress.get("last_practice_date")
    practiced_today = last == today_jst().isoformat()
    percent = round((mastered / total_verbs) * 100) if total_verbs else 0
    daily_goal = min(100, _as_nonneg_int(progress.get("daily_goal")))
    return {
        "last_practice_date": last,
        "practice_dates": list(progress.get("practice_dates") or []),
        "daily_attempts": dict(progress.get("daily_attempts") or {}),
        "daily_goal": daily_goal,
        "current_streak": int(progress.get("current_streak") or 0),
        "longest_streak": int(progress.get("longest_streak") or 0),
        "total_attempts": int(progress.get("total_attempts") or 0),
        "mastered_count": mastered,
        "total_verbs": total_verbs,
        "mastered_percent": percent,
        "vocab_mastered_count": vocab_mastered,
        "vocab_mastered_ja_to_es": vocab_mastered_ja,
        "vocab_mastered_es_to_ja": vocab_mastered_es,
        "total_vocab": total_vocab,
        "conjugation_threshold": conj_th,
        "vocab_threshold": vocab_th,
        "practiced_today": practiced_today,
        "level": learner_level(mastered),
        "xp": mastered * 10,
        "coins": coins,
        "guardian_count": guardian_count,
        "guardian_price": guardian_price,
        "guardian_coins_needed": max(0, guardian_price - coins),
        "can_afford_guardian": coins >= guardian_price,
    }


def verb_progress_list(
    progress: dict,
    threshold: int = DEFAULT_CONJUGATION_THRESHOLD,
) -> list[dict]:
    verbs_data = progress.get("verbs") or {}
    limit = max(1, int(threshold or DEFAULT_CONJUGATION_THRESHOLD))
    rows = []
    for verb in drillable_verbs():
        entry = verbs_data.get(str(verb["id"])) or {}
        tenses = {}
        for tense in TENSE_ORDER:
            tense_entry = entry.get(tense) or {}
            tenses[tense] = {
                "consecutive_correct": int(tense_entry.get("consecutive_correct") or 0),
                "correct_count": int(tense_entry.get("correct_count") or 0),
                "mastered": bool(tense_entry.get("mastered")),
            }
        correct_count = _as_nonneg_int(entry.get("correct_count"))
        rows.append(
            {
                "id": verb["id"],
                "infinitive": verb["infinitive"],
                "meaning_ja": verb["meaning_ja"],
                "category": verb["category"],
                "correct_count": correct_count,
                "threshold": limit,
                "mastered": correct_count >= limit,
                "consecutive_correct": tenses["present"]["consecutive_correct"],
                "tenses": tenses,
            }
        )
    return rows


def vocab_progress_list(
    progress: dict,
    threshold: int = DEFAULT_VOCAB_THRESHOLD,
) -> list[dict]:
    vocab_data = progress.get("vocab") or {}
    limit = max(1, int(threshold or DEFAULT_VOCAB_THRESHOLD))
    rows = []
    for verb in VERBS:
        entry = vocab_data.get(str(verb["id"])) or {}
        sides = {}
        for direction in VOCAB_DIRECTIONS:
            side = entry.get(direction) or {}
            streak = _vocab_streak(side)
            mastered = _vocab_side_mastered(side, limit)
            sides[direction] = {
                "consecutive_correct": streak,
                "correct_count": max(streak, limit) if mastered else streak,
                "mastered": mastered,
            }
        rows.append(
            {
                "id": verb["id"],
                "infinitive": verb["infinitive"],
                "meaning_ja": verb["meaning_ja"],
                "category": verb["category"],
                "correct_count": sides["ja_to_es"]["correct_count"] + sides["es_to_ja"]["correct_count"],
                "threshold": limit,
                "mastered": sides["ja_to_es"]["mastered"] or sides["es_to_ja"]["mastered"],
                "ja_to_es": sides["ja_to_es"],
                "es_to_ja": sides["es_to_ja"],
            }
        )
    return rows
