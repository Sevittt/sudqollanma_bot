"""Yagona profil: telegram_links, bir martalik kod va tg_ profillar."""
import asyncio
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKENTESTTOKENTESTTOKENTESTTOKEN")

try:
    from services import firestore_service as fs
    from tests.fake_firestore import Db
except ImportError:  # aiogram / firebase-admin oʻrnatilmagan
    fs = None

NOW = datetime.now(timezone.utc)


def run(coro):
    return asyncio.run(coro)


@unittest.skipIf(fs is None, "bot dependencies not installed")
class ProfileLinkTest(unittest.TestCase):
    def setUp(self):
        self.store = {
            "users/appUid": {"name": "Ali", "xp": 40},
            "telegram_link_codes/ABCDEFGH": {"uid": "appUid", "expiresAt": NOW + timedelta(minutes=5)},
        }
        self.patches = [
            mock.patch.object(fs, "get_db", return_value=Db(self.store)),
            mock.patch.object(fs.firestore, "transactional", lambda f: f),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def link(self, code="ABCDEFGH", tg=42):
        return run(fs.FirestoreService.link_with_code(code, tg))

    def test_code_links_telegram_to_app_profile(self):
        self.assertEqual(self.link(), "linked")
        self.assertEqual(self.store["telegram_links/42"]["uid"], "appUid")
        self.assertEqual(self.store["users/appUid"]["telegram_id"], "42")
        self.assertNotIn("telegram_link_codes/ABCDEFGH", self.store)
        user = run(fs.FirestoreService.get_user(42))
        self.assertEqual(user["id"], "appUid")

    def test_code_is_single_use(self):
        self.assertEqual(self.link(), "linked")
        self.assertEqual(self.link(), "invalid")

    def test_lowercase_code_is_accepted(self):
        self.assertEqual(self.link("abcdefgh"), "linked")

    def test_expired_code_is_rejected_and_removed(self):
        self.store["telegram_link_codes/ABCDEFGH"]["expiresAt"] = NOW - timedelta(seconds=1)
        self.assertEqual(self.link(), "expired")
        self.assertNotIn("telegram_links/42", self.store)
        self.assertNotIn("telegram_link_codes/ABCDEFGH", self.store)

    def test_telegram_linked_to_another_app_account_is_refused(self):
        self.store["telegram_links/42"] = {"uid": "otherUid"}
        self.assertEqual(self.link(), "other_account")
        self.assertEqual(self.store["telegram_links/42"]["uid"], "otherUid")
        self.assertIn("telegram_link_codes/ABCDEFGH", self.store)

    def test_bot_only_profile_moves_to_app_account(self):
        self.assertTrue(run(fs.FirestoreService.create_user({"telegram_id": 42, "role": "user"})))
        self.assertEqual(self.store["telegram_links/42"]["uid"], "tg_42")
        self.assertEqual(self.link(), "linked")
        self.assertEqual(self.store["telegram_links/42"], {
            **self.store["telegram_links/42"], "uid": "appUid", "previousUid": "tg_42"})
        self.assertIn("users/tg_42", self.store)  # birlashtirish uchun saqlanadi

    def test_create_user_uses_fixed_key_and_never_duplicates(self):
        self.assertTrue(run(fs.FirestoreService.create_user({"telegram_id": 7, "role": "judge"})))
        self.assertEqual(self.store["users/tg_7"]["telegram_id"], "7")
        self.assertFalse(run(fs.FirestoreService.create_user({"telegram_id": 7, "role": "judge"})))

    def test_legacy_auto_id_profile_is_still_found(self):
        self.store["users/legacyAuto"] = {"telegram_id": 99, "xp": 5}
        user = run(fs.FirestoreService.get_user(99))
        self.assertEqual(user["id"], "legacyAuto")
        self.assertFalse(run(fs.FirestoreService.create_user({"telegram_id": 99})))

    def test_updates_go_to_linked_profile(self):
        self.link()
        self.assertTrue(run(fs.FirestoreService.update_user_role(42, "judge")))
        self.assertEqual(self.store["users/appUid"]["role"], "judge")


if __name__ == "__main__":
    unittest.main()
