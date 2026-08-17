"""ストリーク・累計練習数・習得の純ロジック。

活用はデフォルト5回正解で習得、単語はデフォルト10回正解でマスター。
しきい値は管理画面から渡す。永続化は storage 側。
"""
from datetime import date, datetime, timedelta, timezone

from conjugate.data.conjugations import TENSE_ORDER
from conjugate.data.verbs import VERBS, drillable_verbs

JST = timezone(timedelta(hours=9))
DEFAULT_CONJUGATION_THRESHOLD = 5
DEFAULT_VOCAB_THRESHOLD = 10

DEFAULT_PROGRESS = {
    "last_practice_date": None,
    "practice_dates": [],
    "daily_attempts": {},
    "daily_goal": 0,
    "current_streak": 0,
    "longest_streak": 0,
    "total_attempts": 0,
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

    for key in ("current_streak", "longest_streak", "total_attempts"):
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
            count = _as_nonneg_int(entry.get("correct_count"))
            cleaned_vocab[str(verb_id)] = {
                "correct_count": count,
                "mastered": bool(entry.get("mastered")) or count >= DEFAULT_VOCAB_THRESHOLD,
            }
        data["vocab"] = cleaned_vocab
    return data


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


def apply_vocab_mastery(
    progress: dict,
    verb_id,
    is_correct: bool,
    threshold: int = DEFAULT_VOCAB_THRESHOLD,
) -> bool:
    """単語クイズの累計正解を更新。新たにマスターしたら True。"""
    if verb_id is None or not is_correct:
        return False
    try:
        key = str(int(verb_id))
    except (TypeError, ValueError):
        return False

    threshold = max(1, int(threshold or DEFAULT_VOCAB_THRESHOLD))
    vocab = progress.setdefault("vocab", {})
    entry = vocab.setdefault(key, {"correct_count": 0, "mastered": False})
    was_mastered = int(entry.get("correct_count") or 0) >= threshold
    entry["correct_count"] = int(entry.get("correct_count") or 0) + 1
    entry["mastered"] = entry["correct_count"] >= threshold
    vocab[key] = entry
    return bool(entry["mastered"]) and not was_mastered


def apply_attempt(
    progress: dict,
    *,
    verb_id=None,
    tense: str | None = None,
    is_correct: bool = False,
    today: date | None = None,
    kind: str = "conjugation",
    threshold: int | None = None,
) -> dict:
    """1回の判定を進捗に反映する。"""
    today = today or today_jst()
    iso = today.isoformat()
    progress["total_attempts"] = int(progress.get("total_attempts") or 0) + 1
    daily = progress.setdefault("daily_attempts", {})
    daily[iso] = int(daily.get(iso) or 0) + 1
    streak_incremented = apply_streak(progress, today)

    if kind == "vocab":
        vocab_threshold = threshold if threshold is not None else DEFAULT_VOCAB_THRESHOLD
        newly_mastered = apply_vocab_mastery(progress, verb_id, is_correct, vocab_threshold)
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


def mastered_vocab_count(progress: dict, threshold: int = DEFAULT_VOCAB_THRESHOLD) -> int:
    vocab = progress.get("vocab") or {}
    limit = max(1, int(threshold or DEFAULT_VOCAB_THRESHOLD))
    count = 0
    for verb in VERBS:
        entry = vocab.get(str(verb["id"])) or {}
        if _as_nonneg_int(entry.get("correct_count")) >= limit:
            count += 1
    return count


def learner_level(mastered_count: int) -> int:
    return max(1, 1 + max(0, int(mastered_count)) // 5)


def progress_view(
    progress: dict,
    *,
    conjugation_threshold: int = DEFAULT_CONJUGATION_THRESHOLD,
    vocab_threshold: int = DEFAULT_VOCAB_THRESHOLD,
) -> dict:
    conj_th = max(1, int(conjugation_threshold or DEFAULT_CONJUGATION_THRESHOLD))
    vocab_th = max(1, int(vocab_threshold or DEFAULT_VOCAB_THRESHOLD))
    mastered = mastered_verb_count(progress, conj_th)
    vocab_mastered = mastered_vocab_count(progress, vocab_th)
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
        "total_vocab": total_vocab,
        "conjugation_threshold": conj_th,
        "vocab_threshold": vocab_th,
        "practiced_today": practiced_today,
        "level": learner_level(mastered),
        "xp": mastered * 10,
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
            }
        )
    return rows
