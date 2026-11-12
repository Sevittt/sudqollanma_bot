import unittest

from services import gamification as g


def counters(xp=0, passed=0, aced=0, streak=0, sims=0):
    return {"xp": xp, "quizzes_passed": passed, "quizzes_aced": aced,
            "current_streak": streak, "simulations_completed": sims}


class RoleTest(unittest.TestCase):
    def test_only_app_positions_allowed(self):
        for role in ("judge", "assistant", "chancellery", "archive", "ict_specialist"):
            self.assertTrue(g.is_allowed_role(role))
        for role in ("admin", "user", "xodim", "", None, "judge "):
            self.assertFalse(g.is_allowed_role(role))


class QuizActionTest(unittest.TestCase):
    def test_pass_threshold_is_70_percent(self):
        self.assertIsNone(g.quiz_action("q1", 6, 10))
        self.assertEqual(g.quiz_action("q1", 7, 10), "quiz_passed")
        self.assertIsNone(g.quiz_action("q1", 2, 3))  # 66.7%

    def test_perfect_score_is_aced(self):
        self.assertEqual(g.quiz_action("q1", 10, 10), "quiz_aced")

    def test_practice_and_empty_quizzes_give_nothing(self):
        self.assertIsNone(g.quiz_action("random_mix", 5, 5))
        self.assertIsNone(g.quiz_action("bot_quiz", 5, 5))
        self.assertIsNone(g.quiz_action("", 5, 5))
        self.assertIsNone(g.quiz_action("q1", 0, 0))

    def test_points_match_app_rules(self):
        self.assertEqual(g.quiz_points("quiz_passed"), 20)
        self.assertEqual(g.quiz_points("quiz_aced"), 70)
        self.assertEqual(g.quiz_points(None), 0)

    def test_dedup_key_matches_app(self):
        self.assertEqual(g.quiz_dedup_key("abc"), "quiz:abc")


class LevelTest(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(g.calculate_level(counters(99)), "levelBeginner")
        self.assertEqual(g.calculate_level(counters(100)), "levelIntermediate")
        self.assertEqual(g.calculate_level(counters(500)), "levelAdvanced")
        self.assertEqual(g.calculate_level(counters(1000)), "levelSpecialist")

    def test_gatekeepers(self):
        self.assertEqual(g.calculate_level(counters(2000)), "levelSpecialist")
        self.assertEqual(g.calculate_level(counters(2000, passed=5, aced=3)), "levelExpert")
        self.assertEqual(g.calculate_level(counters(5000)), "levelExpert")
        self.assertEqual(g.calculate_level(counters(5000, streak=7, sims=3)), "levelMaster")

    def test_apply_award_updates_counters(self):
        after = g.apply_quiz_award(counters(90), "quiz_aced", 70)
        self.assertEqual(after["xp"], 160)
        self.assertEqual(after["quizzes_passed"], 1)
        self.assertEqual(after["quizzes_aced"], 1)

    def test_legacy_levels_are_recomputed(self):
        self.assertEqual(g.level_id({"level": 1, "xp": 150}), "levelIntermediate")
        self.assertEqual(g.level_id({"level": "Boshlang'ich", "xp": 0}), "levelBeginner")
        self.assertEqual(g.level_id({"level": "levelAdvanced", "xp": 0}), "levelAdvanced")
        self.assertEqual(g.level_id({}), "levelBeginner")

    def test_xp_tolerates_bad_values(self):
        self.assertEqual(g.counters_of({"xp": "120"})["xp"], 120)
        self.assertEqual(g.counters_of({"xp": None})["xp"], 0)
        self.assertEqual(g.counters_of({"xp": True})["xp"], 0)


if __name__ == "__main__":
    unittest.main()
