"""ストリーク・累計練習数・習得（3回連続正解）の純ロジック。

永続化は storage 側。ここは dict を受け取って破壊的に更新し、
テストしやすいよう today を注入できるようにする。
"""
from datetime import date, datetime, timedelta, timezone

from conjugate.data.conjugations import TENSE_ORDER
from conjugate.data.verbs import drillable_verbs

JST = timezone(timedelta(hours=9))
MASTERY_THRESHOLD = 3

DEFAULT_PROGRESS = {
    "last_practice_date": None,
    "current_streak": 0,
    "longest_streak": 0,
    "total_attempts": 0,
    "verbs": {},
}


def today_jst(now: datetime | None = None) -> date:
    current = now or datetime.now(JST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=JST)
    return current.astimezone(JST).date()


def normalize_progress(raw: dict | None) -> dict:
    data = {
        "last_practice_date": None,
        "current_streak": 0,
        "longest_streak": 0,
        "total_attempts": 0,
        "verbs": {},
    }
    if not isinstance(raw, dict):
        return data

    last = raw.get("last_practice_date")
    if isinstance(last, str) and last:
        data["last_practice_date"] = last[:10]

    for key in ("current_streak", "longest_streak", "total_attempts"):
        try:
            data[key] = max(0, int(raw.get(key) or 0))
        except (TypeError, ValueError):
            pass

    verbs = raw.get("verbs")
    if isinstance(verbs, dict):
        cleaned = {}
        for verb_id, entry in verbs.items():
            if not isinstance(entry, dict):
                continue
            tense_map = {}
            for tense, tense_entry in entry.items():
                if tense not in TENSE_ORDER or not isinstance(tense_entry, dict):
                    continue
                try:
                    consecutive = max(0, int(tense_entry.get("consecutive_correct") or 0))
                except (TypeError, ValueError):
                    consecutive = 0
                tense_map[tense] = {
                    "consecutive_correct": consecutive,
                    "mastered": bool(tense_entry.get("mastered")),
                }
            if tense_map:
                cleaned[str(verb_id)] = tense_map
        data["verbs"] = cleaned
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
    progress["last_practice_date"] = today.isoformat()
    return True


def apply_mastery(progress: dict, verb_id, tense: str | None, is_correct: bool) -> bool:
    """動詞×文型の連続正解を更新。新たにマスターしたら True。"""
    if verb_id is None or tense not in TENSE_ORDER:
        return False
    try:
        key = str(int(verb_id))
    except (TypeError, ValueError):
        return False

    verbs = progress.setdefault("verbs", {})
    entry = verbs.setdefault(key, {})
    tense_entry = entry.setdefault(tense, {"consecutive_correct": 0, "mastered": False})
    was_mastered = bool(tense_entry.get("mastered"))

    if is_correct:
        consecutive = int(tense_entry.get("consecutive_correct") or 0) + 1
        tense_entry["consecutive_correct"] = consecutive
        if consecutive >= MASTERY_THRESHOLD:
            tense_entry["mastered"] = True
    else:
        tense_entry["consecutive_correct"] = 0

    entry[tense] = tense_entry
    verbs[key] = entry
    return bool(tense_entry.get("mastered")) and not was_mastered


def apply_attempt(
    progress: dict,
    *,
    verb_id=None,
    tense: str | None = None,
    is_correct: bool = False,
    today: date | None = None,
) -> dict:
    """1回の判定を進捗に反映する。"""
    today = today or today_jst()
    progress["total_attempts"] = int(progress.get("total_attempts") or 0) + 1
    streak_incremented = apply_streak(progress, today)
    newly_mastered = apply_mastery(progress, verb_id, tense, is_correct)
    return {
        "streak_incremented": streak_incremented,
        "newly_mastered": newly_mastered,
        "current_streak": int(progress.get("current_streak") or 0),
        "longest_streak": int(progress.get("longest_streak") or 0),
        "total_attempts": int(progress.get("total_attempts") or 0),
        "mastered_count": mastered_verb_count(progress),
    }


def verb_is_mastered(entry: dict | None) -> bool:
    if not isinstance(entry, dict):
        return False
    return any(bool((entry.get(tense) or {}).get("mastered")) for tense in TENSE_ORDER)


def mastered_verb_count(progress: dict) -> int:
    verbs = progress.get("verbs") or {}
    count = 0
    for verb in drillable_verbs():
        if verb_is_mastered(verbs.get(str(verb["id"]))):
            count += 1
    return count


def learner_level(mastered_count: int) -> int:
    return max(1, 1 + max(0, int(mastered_count)) // 5)


def progress_view(progress: dict) -> dict:
    mastered = mastered_verb_count(progress)
    total_verbs = len(drillable_verbs())
    last = progress.get("last_practice_date")
    practiced_today = last == today_jst().isoformat()
    percent = round((mastered / total_verbs) * 100) if total_verbs else 0
    return {
        "last_practice_date": last,
        "current_streak": int(progress.get("current_streak") or 0),
        "longest_streak": int(progress.get("longest_streak") or 0),
        "total_attempts": int(progress.get("total_attempts") or 0),
        "mastered_count": mastered,
        "total_verbs": total_verbs,
        "mastered_percent": percent,
        "practiced_today": practiced_today,
        "level": learner_level(mastered),
        "xp": mastered * 10,
    }


def verb_progress_list(progress: dict) -> list[dict]:
    verbs_data = progress.get("verbs") or {}
    rows = []
    for verb in drillable_verbs():
        entry = verbs_data.get(str(verb["id"])) or {}
        tenses = {}
        for tense in TENSE_ORDER:
            tense_entry = entry.get(tense) or {}
            tenses[tense] = {
                "consecutive_correct": int(tense_entry.get("consecutive_correct") or 0),
                "mastered": bool(tense_entry.get("mastered")),
            }
        rows.append(
            {
                "id": verb["id"],
                "infinitive": verb["infinitive"],
                "meaning_ja": verb["meaning_ja"],
                "category": verb["category"],
                "mastered": verb_is_mastered(entry),
                "consecutive_correct": tenses["present"]["consecutive_correct"],
                "tenses": tenses,
            }
        )
    return rows
