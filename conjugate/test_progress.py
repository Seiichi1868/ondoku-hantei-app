"""ストリーク・習得ロジックの単体テスト。"""
import unittest
from datetime import date

from conjugate.progress import (
    apply_attempt,
    apply_guardian_purchase,
    apply_mastery,
    apply_streak,
    apply_vocab_mastery,
    can_afford_guardian,
    learner_level,
    mastered_verb_count,
    normalize_progress,
    progress_view,
    verb_is_mastered,
    vocab_progress_list,
)


class StreakTests(unittest.TestCase):
    def test_first_practice_starts_at_one(self):
        progress = normalize_progress({})
        today = date(2026, 8, 15)
        self.assertTrue(apply_streak(progress, today))
        self.assertEqual(progress["current_streak"], 1)
        self.assertEqual(progress["longest_streak"], 1)
        self.assertEqual(progress["last_practice_date"], "2026-08-15")
        self.assertEqual(progress["practice_dates"], ["2026-08-15"])

    def test_same_day_does_not_increment(self):
        progress = {
            "last_practice_date": "2026-08-15",
            "practice_dates": ["2026-08-15"],
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
        self.assertIn("2026-08-15", progress["practice_dates"])

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
    def test_five_correct_marks_mastered(self):
        progress = normalize_progress({})
        for _ in range(4):
            self.assertFalse(apply_mastery(progress, 1, "present", True, threshold=5))
        self.assertTrue(apply_mastery(progress, 1, "present", True, threshold=5))
        entry = progress["verbs"]["1"]
        self.assertTrue(entry["mastered"])
        self.assertEqual(entry["correct_count"], 5)

    def test_incorrect_does_not_reduce_count(self):
        progress = normalize_progress({})
        apply_mastery(progress, 1, "present", True, threshold=5)
        apply_mastery(progress, 1, "present", True, threshold=5)
        apply_mastery(progress, 1, "present", False, threshold=5)
        entry = progress["verbs"]["1"]
        self.assertEqual(entry["correct_count"], 2)
        self.assertEqual(entry["present"]["consecutive_correct"], 0)
        self.assertFalse(entry["mastered"])

    def test_gustar_and_unknown_tense_are_ignored_for_id(self):
        progress = normalize_progress({})
        self.assertFalse(apply_mastery(progress, "gustar", "present", True))
        self.assertFalse(apply_mastery(progress, 1, "gustar", True, threshold=5))
        self.assertEqual(progress["verbs"]["1"]["correct_count"], 1)

    def test_apply_attempt_increments_total_and_daily(self):
        progress = normalize_progress({})
        today = date(2026, 8, 15)
        apply_attempt(progress, verb_id=1, tense="present", is_correct=True, today=today, threshold=5)
        apply_attempt(progress, verb_id=1, tense="present", is_correct=True, today=today, threshold=5)
        self.assertEqual(progress["total_attempts"], 2)
        self.assertEqual(progress["current_streak"], 1)
        self.assertEqual(progress["daily_attempts"]["2026-08-15"], 2)
        self.assertEqual(progress["practice_dates"], ["2026-08-15"])

    def test_mastered_count_and_level(self):
        progress = normalize_progress({})
        for _ in range(5):
            apply_mastery(progress, 1, "present", True, threshold=5)
        self.assertEqual(mastered_verb_count(progress, 5), 1)
        self.assertTrue(verb_is_mastered(progress["verbs"]["1"], 5))
        self.assertEqual(learner_level(0), 1)
        self.assertEqual(learner_level(23), 5)

    def test_legacy_mastered_is_kept(self):
        progress = normalize_progress(
            {
                "verbs": {
                    "1": {"present": {"consecutive_correct": 3, "mastered": True}},
                }
            }
        )
        self.assertGreaterEqual(progress["verbs"]["1"]["correct_count"], 5)
        self.assertTrue(verb_is_mastered(progress["verbs"]["1"], 5))

    def test_vocab_mastery_uses_threshold(self):
        progress = normalize_progress({})
        for _ in range(4):
            self.assertFalse(apply_vocab_mastery(progress, 1, True, threshold=5, direction="ja_to_es"))
        self.assertTrue(apply_vocab_mastery(progress, 1, True, threshold=5, direction="ja_to_es"))
        self.assertFalse(apply_vocab_mastery(progress, 1, False, threshold=5, direction="ja_to_es"))
        self.assertEqual(progress["vocab"]["1"]["ja_to_es"]["consecutive_correct"], 0)
        self.assertTrue(progress["vocab"]["1"]["ja_to_es"]["mastered"])
        self.assertEqual(progress["vocab"]["1"]["es_to_ja"]["correct_count"], 0)
        rows = vocab_progress_list(progress, 5)
        mastered = [row for row in rows if row["id"] == 1][0]
        self.assertTrue(mastered["ja_to_es"]["mastered"])
        self.assertFalse(mastered["es_to_ja"]["mastered"])

    def test_vocab_wrong_answer_resets_streak(self):
        progress = normalize_progress({})
        for _ in range(4):
            apply_vocab_mastery(progress, 1, True, threshold=5, direction="ja_to_es")
        apply_vocab_mastery(progress, 1, False, threshold=5, direction="ja_to_es")
        self.assertEqual(progress["vocab"]["1"]["ja_to_es"]["consecutive_correct"], 0)
        self.assertFalse(progress["vocab"]["1"]["ja_to_es"]["mastered"])
        for _ in range(4):
            self.assertFalse(apply_vocab_mastery(progress, 1, True, threshold=5, direction="ja_to_es"))
        self.assertTrue(apply_vocab_mastery(progress, 1, True, threshold=5, direction="ja_to_es"))

    def test_vocab_directions_are_independent(self):
        progress = normalize_progress({})
        for _ in range(5):
            apply_vocab_mastery(progress, 1, True, threshold=5, direction="es_to_ja")
        self.assertTrue(progress["vocab"]["1"]["es_to_ja"]["mastered"])
        self.assertFalse(progress["vocab"]["1"]["ja_to_es"]["mastered"])

    def test_vocab_legacy_counts_become_streaks(self):
        progress = normalize_progress(
            {
                "vocab": {
                    "1": {"ja_to_es": {"correct_count": 3, "mastered": False}},
                }
            }
        )
        self.assertEqual(progress["vocab"]["1"]["ja_to_es"]["consecutive_correct"], 3)
        self.assertFalse(progress["vocab"]["1"]["ja_to_es"]["mastered"])

    def test_progress_view_includes_calendar_fields(self):
        progress = normalize_progress({})
        apply_attempt(
            progress,
            verb_id=1,
            tense="present",
            is_correct=True,
            today=date(2026, 8, 17),
            threshold=5,
        )
        view = progress_view(progress, conjugation_threshold=5, vocab_threshold=5)
        self.assertEqual(view["practice_dates"], ["2026-08-17"])
        self.assertEqual(view["daily_attempts"]["2026-08-17"], 1)
        self.assertEqual(view["conjugation_threshold"], 5)
        self.assertEqual(view["vocab_threshold"], 5)


class CoinEconomyTests(unittest.TestCase):
    def test_correct_answer_earns_one_coin(self):
        progress = normalize_progress({})
        today = date(2026, 8, 19)
        apply_attempt(progress, verb_id=1, tense="present", is_correct=True, today=today, threshold=5)
        self.assertEqual(progress["coins"], 1)
        apply_attempt(progress, verb_id=1, tense="present", is_correct=True, today=today, threshold=5)
        self.assertEqual(progress["coins"], 2)

    def test_wrong_answer_earns_no_coin(self):
        progress = normalize_progress({})
        today = date(2026, 8, 19)
        apply_attempt(progress, verb_id=1, tense="present", is_correct=False, today=today, threshold=5)
        self.assertEqual(progress["coins"], 0)
        self.assertEqual(progress["total_attempts"], 1)

    def test_vocab_correct_answer_also_earns_coin(self):
        progress = normalize_progress({})
        today = date(2026, 8, 19)
        apply_attempt(
            progress,
            verb_id=1,
            is_correct=True,
            today=today,
            kind="vocab",
            direction="ja_to_es",
            threshold=5,
        )
        self.assertEqual(progress["coins"], 1)

    def test_apply_attempt_delta_reports_coins(self):
        progress = normalize_progress({})
        delta = apply_attempt(progress, verb_id=1, tense="present", is_correct=True, threshold=5)
        self.assertEqual(delta["coins"], 1)
        self.assertTrue(delta["coin_earned"])
        self.assertEqual(delta["guardian_count"], 0)

    def test_guardian_purchase_requires_enough_coins(self):
        progress = normalize_progress({"coins": 49})
        self.assertFalse(can_afford_guardian(progress, price=50))
        self.assertFalse(apply_guardian_purchase(progress, price=50))
        self.assertEqual(progress["coins"], 49)
        self.assertEqual(progress["guardian_count"], 0)

    def test_guardian_purchase_spends_coins_and_grants_one(self):
        progress = normalize_progress({"coins": 120})
        self.assertTrue(can_afford_guardian(progress, price=50))
        self.assertTrue(apply_guardian_purchase(progress, price=50))
        self.assertEqual(progress["coins"], 70)
        self.assertEqual(progress["guardian_count"], 1)

    def test_progress_view_includes_coin_and_guardian_fields(self):
        progress = normalize_progress({"coins": 30, "guardian_count": 2})
        view = progress_view(progress, guardian_price=50)
        self.assertEqual(view["coins"], 30)
        self.assertEqual(view["guardian_count"], 2)
        self.assertEqual(view["guardian_price"], 50)
        self.assertEqual(view["guardian_coins_needed"], 20)
        self.assertFalse(view["can_afford_guardian"])


if __name__ == "__main__":
    unittest.main()
