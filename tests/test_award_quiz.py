"""FirestoreService.award_quiz mantigʻi — soxta Firestore bilan (tarmoqsiz)."""
import asyncio
import os
import unittest
from unittest import mock

os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKENTESTTOKENTESTTOKENTESTTOKEN")

try:
    from services import firestore_service as fs
except ImportError as e:  # aiogram / firebase-admin oʻrnatilmagan
    fs = None
    _skip_reason = str(e)


class _Snap:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class _Doc:
    def __init__(self, store, path):
        self.store, self.path = store, path

    def get(self, transaction=None):
        return _Snap(self.store.get(self.path))

    def collection(self, name):
        return _Col(self.store, f"{self.path}/{name}")


class _Col:
    def __init__(self, store, path):
        self.store, self.path = store, path

    def document(self, doc_id):
        return _Doc(self.store, f"{self.path}/{doc_id}")


class _Tx:
    def __init__(self, store):
        self.store = store

    def create(self, ref, data):
        assert ref.path not in self.store, "create on existing doc"
        self.store[ref.path] = dict(data)

    def update(self, ref, data):
        self.store[ref.path].update(data)


class _Db:
    def __init__(self, store):
        self.store = store

    def collection(self, name):
        return _Col(self.store, name)

    def transaction(self):
        return _Tx(self.store)


@unittest.skipIf(fs is None, "bot dependencies not installed")
class AwardQuizTest(unittest.TestCase):
    def setUp(self):
        self.store = {"users/u1": {"telegram_id": "42", "xp": 90, "quizzesPassed": 0, "totalQuizzesAced": 0}}
        db = _Db(self.store)
        self.patches = [
            mock.patch.object(fs, "get_db", return_value=db),
            mock.patch.object(fs.firestore, "transactional", lambda f: f),
            mock.patch.object(fs.FirestoreService, "get_user",
                              mock.AsyncMock(return_value={"id": "u1", **self.store["users/u1"]})),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def award(self, quiz_id, score, total):
        return asyncio.run(fs.FirestoreService.award_quiz("42", quiz_id, score, total))

    def awards(self):
        return [k for k in self.store if "/xp_awards/" in k]

    def test_failed_quiz_gives_nothing(self):
        self.assertEqual(self.award("q1", 6, 10), (0, "not_eligible"))
        self.assertEqual(self.store["users/u1"]["xp"], 90)
        self.assertEqual(self.awards(), [])

    def test_pass_awards_once_and_updates_level(self):
        self.assertEqual(self.award("q1", 7, 10), (20, "awarded"))
        user = self.store["users/u1"]
        self.assertEqual(user["xp"], 110)
        self.assertEqual(user["level"], "levelIntermediate")
        self.assertEqual(user["quizzesPassed"], 1)
        self.assertEqual(len(self.awards()), 1)

        self.assertEqual(self.award("q1", 10, 10), (0, "duplicate"))
        self.assertEqual(self.store["users/u1"]["xp"], 110)

    def test_perfect_score_counts_as_aced(self):
        self.assertEqual(self.award("q2", 5, 5), (70, "awarded"))
        self.assertEqual(self.store["users/u1"]["totalQuizzesAced"], 1)

    def test_practice_quiz_gives_nothing(self):
        self.assertEqual(self.award("random_mix", 5, 5), (0, "not_eligible"))

    def test_award_key_matches_app_hash(self):
        import hashlib
        self.award("q1", 7, 10)
        expected = hashlib.sha256(b"quiz:q1").hexdigest()
        self.assertEqual(self.awards(), [f"users/u1/xp_awards/{expected}"])


if __name__ == "__main__":
    unittest.main()
