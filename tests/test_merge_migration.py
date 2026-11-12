"""Profil birlashtirish va bir martalik migratsiya — soxta Firestore bilan."""
import asyncio
import hashlib
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKENTESTTOKENTESTTOKENTESTTOKEN")

try:
    from services import firestore_service as fs
    from scripts.migrate_profiles import migrate
    from tests.fake_firestore import Db
except ImportError:  # aiogram / firebase-admin oʻrnatilmagan
    fs = None


def award_path(uid, quiz_id):
    return f"users/{uid}/xp_awards/{hashlib.sha256(f'quiz:{quiz_id}'.encode()).hexdigest()}"


@unittest.skipIf(fs is None, "bot dependencies not installed")
class MergeTest(unittest.TestCase):
    def setUp(self):
        self.store = {}
        self.db = Db(self.store)
        self.patches = [
            mock.patch.object(fs, "get_db", return_value=self.db),
            mock.patch.object(fs.firestore, "transactional", lambda f: f),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def seed_bot_profile(self):
        self.store.update({
            "users/tg_42": {"telegram_id": "42", "xp": 90, "level": 1, "quiz_correct": 9,
                            "courtName": "Yunusobod sudi", "role": "judge"},
            "users/appUid": {"email": "x", "xp": 40, "level": "levelBeginner", "role": "assistant",
                             "quizzesPassed": 0, "totalQuizzesAced": 0},
            "quiz_attempts/a1": {"userId": "tg_42", "quizId": "q1", "score": 6, "totalQuestions": 10},
            "quiz_attempts/a2": {"userId": "tg_42", "quizId": "q1", "score": 8, "totalQuestions": 10},
            "quiz_attempts/a3": {"userId": "tg_42", "quizId": "q2", "score": 5, "totalQuestions": 5},
            "quiz_attempts/a4": {"userId": "tg_42", "quizId": "random_mix", "score": 5, "totalQuestions": 5},
        })

    def test_merge_moves_attempts_and_recomputes_xp(self):
        self.seed_bot_profile()
        self.assertEqual(fs.FirestoreService.merge_profile("tg_42", "appUid"), 90)  # 20 + 70
        dst = self.store["users/appUid"]
        self.assertEqual(dst["xp"], 130)
        self.assertEqual(dst["level"], "levelIntermediate")
        self.assertEqual(dst["quizzesPassed"], 2)
        self.assertEqual(dst["totalQuizzesAced"], 1)
        self.assertEqual(dst["role"], "assistant")  # ilova roli saqlanadi
        self.assertEqual(dst["courtName"], "Yunusobod sudi")  # boʻsh maydon toʻldirildi
        self.assertEqual(dst["quiz_correct"], 9)
        for k in ("a1", "a2", "a3", "a4"):
            self.assertEqual(self.store[f"quiz_attempts/{k}"]["userId"], "appUid")
        self.assertEqual(self.store["users/tg_42"]["mergedInto"], "appUid")

    def test_merge_skips_quizzes_already_awarded_in_app(self):
        self.seed_bot_profile()
        self.store[award_path("appUid", "q2")] = {"key": "quiz:q2"}
        self.assertEqual(fs.FirestoreService.merge_profile("tg_42", "appUid"), 20)

    def test_merge_is_idempotent(self):
        self.seed_bot_profile()
        fs.FirestoreService.merge_profile("tg_42", "appUid")
        self.assertIsNone(fs.FirestoreService.merge_profile("tg_42", "appUid"))
        self.assertEqual(self.store["users/appUid"]["xp"], 130)

    def test_linking_merges_previous_bot_profile(self):
        self.seed_bot_profile()
        self.store["telegram_links/42"] = {"uid": "tg_42"}
        self.store["telegram_link_codes/ABCDEFGH"] = {
            "uid": "appUid", "expiresAt": datetime.now(timezone.utc) + timedelta(minutes=5)}
        status = asyncio.run(fs.FirestoreService.link_with_code("ABCDEFGH", 42))
        self.assertEqual(status, "linked")
        self.assertEqual(self.store["users/tg_42"]["mergedInto"], "appUid")
        self.assertEqual(self.store["users/appUid"]["xp"], 130)


@unittest.skipIf(fs is None, "bot dependencies not installed")
class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.store = {
            "users/autoId1": {"telegram_id": "42", "xp": 90, "level": 1, "role": "judge"},
            "users/autoId2": {"telegram_id": "43", "xp": 0, "level": 1, "role": "archive"},
            "users/app1": {"email": "x", "xp": 150, "level": "Boshlang'ich"},
            "users/app2": {"email": "y", "xp": 10, "level": "levelBeginner"},
            "quiz_attempts/a1": {"userId": "42", "quizId": "q1", "score": 7, "totalQuestions": 10},
            "quiz_attempts/a2": {"userId": "app1", "quizId": "q1", "score": 7, "totalQuestions": 10},
        }
        self.db = Db(self.store)

    def test_dry_run_writes_nothing(self):
        before = {k: dict(v) for k, v in self.store.items()}
        counts, levels = migrate(self.db, apply=False)
        self.assertEqual(self.store, before)
        self.assertEqual(counts["legacy_moved"], 2)
        self.assertEqual(counts["attempts_rekeyed"], 1)
        self.assertEqual(counts["levels_fixed"], 1)
        self.assertEqual(levels, {"str:Boshlang'ich -> levelIntermediate": 1})

    def test_apply_moves_legacy_profiles_and_is_repeatable(self):
        migrate(self.db, apply=True)
        self.assertEqual(self.store["users/tg_42"]["migratedFrom"], "autoId1")
        self.assertEqual(self.store["telegram_links/42"]["uid"], "tg_42")
        self.assertEqual(self.store["users/autoId1"]["mergedInto"], "tg_42")
        self.assertEqual(self.store["quiz_attempts/a1"]["userId"], "tg_42")
        self.assertEqual(self.store["quiz_attempts/a2"]["userId"], "app1")
        self.assertEqual(self.store["users/app1"]["level"], "levelIntermediate")

        counts, _ = migrate(self.db, apply=True)
        self.assertEqual(counts.get("legacy_moved", 0), 0)
        self.assertEqual(counts.get("attempts_rekeyed", 0), 0)
        self.assertEqual(counts.get("levels_fixed", 0), 0)

    def test_moved_profile_is_found_by_bot(self):
        migrate(self.db, apply=True)
        with mock.patch.object(fs, "get_db", return_value=self.db):
            user = asyncio.run(fs.FirestoreService.get_user(42))
        self.assertEqual(user["id"], "tg_42")


if __name__ == "__main__":
    unittest.main()
