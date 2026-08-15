"""出題セッションの構築・進行・採点をまとめるロジック層。"""
import random
import uuid

from conjugate.config import USD_JPY, format_jpy_amount
from conjugate.data.conjugations import TENSE_ORDER, build_forms
from conjugate.data.gustar import GUSTAR_EXAMPLES
from conjugate.data.verbs import VERBS_BY_ID, verbs_by_category
from conjugate.judge import grade_gustar, grade_regular
from conjugate.storage import record_answer_result, record_progress, top_weak_verb_ids

GUSTAR_BY_ID = {item["id"]: item for item in GUSTAR_EXAMPLES}


def _build_verb_question(verb: dict, enabled_tenses: list[str], targets_per_question: int) -> dict:
    all_forms = build_forms(verb)
    display_tenses = [t for t in TENSE_ORDER if t in enabled_tenses]
    if not display_tenses:
        display_tenses = ["present"]

    k = min(targets_per_question, len(display_tenses))
    targets = random.sample(display_tenses, k=k) if k > 0 else [display_tenses[0]]
    # 出題順は文型の並びを保つ（present→progressive→near_future→preterite）
    targets = [t for t in TENSE_ORDER if t in targets]

    return {
        "question_id": uuid.uuid4().hex[:10],
        "kind": "verb",
        "verb_id": verb["id"],
        "infinitive": verb["infinitive"],
        "meaning_ja": verb["meaning_ja"],
        "category": verb["category"],
        "reflexive": bool(verb.get("reflexive")),
        "note": verb.get("note", ""),
        "display_tenses": display_tenses,
        "targets": targets,
        "forms": all_forms,  # サーバー側保持。tú形はpublic変換時に除去する。
        "answers": {},
    }


def _build_gustar_question(item: dict) -> dict:
    return {
        "question_id": uuid.uuid4().hex[:10],
        "kind": "gustar",
        "gustar_id": item["id"],
        "topic_ja": item["topic_ja"],
        "subject_type": item["subject_type"],
        "targets": ["gustar"],
        "yo_sentence": item["yo_sentence"],
        "tu_sentence": item["tu_sentence"],
        "answers": {},
    }


def build_session_questions(
    *,
    categories: list[str],
    tenses: list[str],
    count: int,
    targets_per_question: int,
    gustar_enabled: bool,
    gustar_count: int,
    prioritize_weak: bool,
) -> list[dict]:
    pool = verbs_by_category(categories)
    if not pool:
        pool = verbs_by_category(["motion_daily"])  # フォールバック

    if prioritize_weak:
        weak_ids = set(top_weak_verb_ids())
        weak_pool = [v for v in pool if v["id"] in weak_ids]
        other_pool = [v for v in pool if v["id"] not in weak_ids]
    else:
        weak_pool = []
        other_pool = list(pool)

    random.shuffle(weak_pool)
    random.shuffle(other_pool)
    ordered = weak_pool + other_pool

    if len(ordered) >= count:
        chosen = ordered[:count]
    else:
        chosen = list(ordered)
        while len(chosen) < count:
            chosen.append(random.choice(pool))

    random.shuffle(chosen)

    questions = [_build_verb_question(v, tenses, targets_per_question) for v in chosen]

    if gustar_enabled and gustar_count > 0:
        sample_size = min(gustar_count, len(GUSTAR_EXAMPLES))
        gustar_items = random.sample(GUSTAR_EXAMPLES, k=sample_size)
        gustar_questions = [_build_gustar_question(item) for item in gustar_items]
        insert_positions = sorted(random.sample(range(len(questions) + 1), k=len(gustar_questions))) if questions else [0] * len(gustar_questions)
        for offset, (pos, gq) in enumerate(zip(insert_positions, gustar_questions)):
            questions.insert(pos + offset, gq)

    return questions


def public_question(question: dict) -> dict:
    """クライアントへ送るtú形（答え）を除いたバージョン。"""
    q = {k: v for k, v in question.items() if k not in ("forms", "tu_sentence", "answers")}
    if question["kind"] == "verb":
        forms = question["forms"]
        q["forms"] = {
            tense: {"yo": data["yo"]} for tense, data in forms.items() if tense in question["display_tenses"]
        }
    else:
        q["yo_sentence"] = question["yo_sentence"]
    q["answers"] = {
        target: {"level": ans["level"]} for target, ans in question.get("answers", {}).items()
    }
    return q


def grade_target(question: dict, target: str, transcript: str, strict: bool) -> dict:
    if question["kind"] == "gustar":
        item = GUSTAR_BY_ID[question["gustar_id"]]
        result = grade_gustar(item, transcript, strict=strict)
        record_answer_result(verb_id="gustar", infinitive="gustar", level=result["level"])
        progress = record_progress(verb_id=None, tense=None, is_correct=result["level"] == "correct")
        result["newly_mastered"] = False
        result["progress"] = progress
        return result

    verb = VERBS_BY_ID[question["verb_id"]]
    result = grade_regular(verb, target, transcript, strict=strict)
    record_answer_result(verb_id=verb["id"], infinitive=verb["infinitive"], level=result["level"])
    progress = record_progress(
        verb_id=verb["id"],
        tense=target,
        is_correct=result["level"] == "correct",
    )
    result["newly_mastered"] = bool(progress.get("newly_mastered"))
    result["progress"] = progress
    return result


def build_summary(session: dict) -> dict:
    total = 0
    correct = 0
    level_counts = {"correct": 0, "pronoun_error": 0, "conjugation_error": 0, "way_off": 0}
    weak_items = []

    for q in session["questions"]:
        for target, ans in q.get("answers", {}).items():
            total += 1
            level = ans.get("level", "way_off")
            level_counts[level] = level_counts.get(level, 0) + 1
            if level == "correct":
                correct += 1
            else:
                label = q["infinitive"] if q["kind"] == "verb" else "gustar"
                weak_items.append(
                    {
                        "infinitive": label,
                        "meaning_ja": q.get("meaning_ja") or q.get("topic_ja", ""),
                        "target": target,
                        "level": level,
                        "expected_sentence": ans.get("expected_sentence", ""),
                        "transcript": ans.get("transcript", ""),
                    }
                )

    accuracy = round((correct / total) * 100, 1) if total else 0.0
    usage = session.get("usage") or {}
    cost_usd = float(usage.get("cost_usd") or 0)
    cost_jpy = cost_usd * USD_JPY

    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "level_counts": level_counts,
        "weak_items": weak_items,
        "newly_mastered": session.get("newly_mastered") or [],
        "cost_jpy_display": format_jpy_amount(cost_jpy),
    }
