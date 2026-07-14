from __future__ import annotations

from types import SimpleNamespace
import unittest

from database.settings import parse_bool_setting
from services.access_policy import has_access
from services.permissions import is_staff_role, is_superadmin_role
from services.support_policy import validate_support_message


class FeatureDefaultsTests(unittest.TestCase):
    def test_missing_flags_are_disabled(self) -> None:
        self.assertFalse(parse_bool_setting(None, default=False))
        self.assertFalse(parse_bool_setting("unknown", default=False))

    def test_admin_can_explicitly_enable(self) -> None:
        for value in ("true", "1", "yes", "on", "да"):
            self.assertTrue(parse_bool_setting(value, default=False))


class AccessTests(unittest.TestCase):
    def test_regular_user_without_subscription_has_no_access(self) -> None:
        self.assertFalse(has_access(SimpleNamespace(role="user", has_subscription=False)))

    def test_subscriber_has_access(self) -> None:
        self.assertTrue(has_access(SimpleNamespace(role="user", has_subscription=True)))

    def test_staff_has_access(self) -> None:
        self.assertTrue(has_access(SimpleNamespace(role="moderator", has_subscription=False)))


class PermissionTests(unittest.TestCase):
    def test_only_staff_roles_can_answer_as_project(self) -> None:
        self.assertTrue(is_staff_role("admin"))
        self.assertTrue(is_staff_role("moderator"))
        self.assertFalse(is_staff_role("user"))
        self.assertFalse(is_staff_role("banned"))
        self.assertFalse(is_staff_role(None))

    def test_superadmin_is_stricter(self) -> None:
        self.assertTrue(is_superadmin_role("admin"))
        self.assertFalse(is_superadmin_role("moderator"))


class SupportPolicyTests(unittest.TestCase):
    def test_content_accepts_text(self) -> None:
        message = SimpleNamespace(text="Что означает этот общий вывод?", photo=None)
        allowed, error = validate_support_message(message, "content")
        self.assertTrue(allowed)
        self.assertIsNone(error)

    def test_content_rejects_files_and_photos(self) -> None:
        message = SimpleNamespace(text=None, photo=[SimpleNamespace(file_size=1000)], caption=None)
        allowed, error = validate_support_message(message, "content")
        self.assertFalse(allowed)
        self.assertIn("только текст", error or "")

    def test_technical_support_accepts_small_screenshot(self) -> None:
        message = SimpleNamespace(text=None, photo=[SimpleNamespace(file_size=1000)], caption="Ошибка")
        allowed, error = validate_support_message(message, "tech")
        self.assertTrue(allowed)
        self.assertIsNone(error)

    def test_technical_support_rejects_documents(self) -> None:
        message = SimpleNamespace(text=None, photo=None, document=SimpleNamespace(file_size=1000))
        allowed, error = validate_support_message(message, "tech")
        self.assertFalse(allowed)
        self.assertIn("Документы", error or "")


if __name__ == "__main__":
    unittest.main()
