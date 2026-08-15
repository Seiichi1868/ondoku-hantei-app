"""ストリーク・習得ロジックの単体テスト。"""
import unittest
from datetime import date

from conjugate.progress import (
    apply_attempt,
    apply_mastery,
    apply_streak,
    learner_level,
    mastered_verb_count,
    normalize_progress,
    verb_is_mastered,
)


class StreakTests(unittest.TestCase):
    def test_first_practice_starts_at_one(self):
        progress = normalize_progress({})
        today = date(2026, 8, 15)
        self.assertTrue(apply_streak(progress, today))
        self.assertEqual(progress["current_streak"], 1)
        self.assertEqual(progress["longest_streak"], 1)
        self.assertEqual(progress["last_practice_date"], "2026-08-15")

    def test_same_day_does_not_increment(self):
        progress = {
            "last_practice_date": "2026-08-15",
            "current_streak": 4,
            "longest_streak": 6,
        }
        self.assertFalse(apply_streak(progress, date(2026, 8, 15)))
        self.assertEqual(progress["current_streak"], 4)

    def test_yesterday_increments(self):
        progress = {
            "last_practice_date": "2026-08-14",
            "current_streak": 4,
            "longest_streak": 4,
        }
        self.assertTrue(apply_streak(progress, date(2026, 8, 15)))
        self.assertEqual(progress["current_streak"], 5)
        self.assertEqual(progress["longest_streak"], 5)

    def test_gap_resets_to_one(self):
        progress = {
            "last_practice_date": "2026-08-10",
            "current_streak": 9,
            "longest_streak": 9,
        }
        apply_streak(progress, date(2026, 8, 15))
        self.assertEqual(progress["current_streak"], 1)
        self.assertEqual(progress["longest_streak"], 9)


class MasteryTests(unittest.TestCase):
    def test_three_correct_marks_mastered(self):
        progress = normalize_progress({})
        self.assertFalse(apply_mastery(progress, 1, "present", True))
        self.assertFalse(apply_mastery(progress, 1, "present", True))
        self.assertTrue(apply_mastery(progress, 1, "present", True))
        entry = progress["verbs"]["1"]["present"]
        self.assertTrue(entry["mastered"])
        self.assertEqual(entry["consecutive_correct"], 3)

    def test_incorrect_resets_streak_keeps_mastered(self):
        progress = normalize_progress({})
        apply_mastery(progress, 1, "present", True)
        apply_mastery(progress, 1, "present", True)
        apply_mastery(progress, 1, "present", True)
        self.assertFalse(apply_mastery(progress, 1, "present", False))
        entry = progress["verbs"]["1"]["present"]
        self.assertEqual(entry["consecutive_correct"], 0)
        self.assertTrue(entry["mastered"])

    def test_gustar_and_unknown_tense_are_ignored(self):
        progress = normalize_progress({})
        self.assertFalse(apply_mastery(progress, "gustar", "present", True))
        self.assertFalse(apply_mastery(progress, 1, "gustar", True))
        self.assertEqual(progress["verbs"], {})

    def test_apply_attempt_increments_total_once_per_call(self):
        progress = normalize_progress({})
        today = date(2026, 8, 15)
        apply_attempt(progress, verb_id=1, tense="present", is_correct=True, today=today)
        apply_attempt(progress, verb_id=1, tense="present", is_correct=True, today=today)
        self.assertEqual(progress["total_attempts"], 2)
        self.assertEqual(progress["current_streak"], 1)

    def test_mastered_count_and_level(self):
        progress = normalize_progress({})
        for _ in range(3):
            apply_mastery(progress, 1, "present", True)
        self.assertEqual(mastered_verb_count(progress), 1)
        self.assertTrue(verb_is_mastered(progress["verbs"]["1"]))
        self.assertEqual(learner_level(0), 1)
        self.assertEqual(learner_level(23), 5)


if __name__ == "__main__":
    unittest.main()
