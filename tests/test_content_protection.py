from __future__ import annotations

import unittest

from config import (
    CONTENT_LONG_MAX_VIEWS,
    CONTENT_SHORT_MAX_VIEWS,
)
from services.content_protection import (
    evaluate_content_limits,
    make_hidden_fingerprint,
    make_license_code,
    protect_text,
)


class ContentProtectionTests(unittest.TestCase):
    def test_license_code_is_stable(self) -> None:
        self.assertEqual(make_license_code(123456), make_license_code(123456))

    def test_license_code_differs_between_users(self) -> None:
        self.assertNotEqual(make_license_code(123456), make_license_code(123457))

    def test_license_code_does_not_expose_telegram_id(self) -> None:
        user_id = 7957920325
        self.assertNotIn(str(user_id), make_license_code(user_id))

    def test_protected_text_contains_visible_license(self) -> None:
        user_id = 123456
        result = protect_text("Тестовый материал", user_id)
        self.assertIn("Тестовый материал", result)
        self.assertIn(make_license_code(user_id), result)
        self.assertIn("Только для личного использования", result)

    def test_hidden_fingerprint_is_user_specific(self) -> None:
        self.assertNotEqual(make_hidden_fingerprint(1), make_hidden_fingerprint(2))

    def test_short_limit(self) -> None:
        seconds, reason = evaluate_content_limits(CONTENT_SHORT_MAX_VIEWS + 1, 1)
        self.assertGreater(seconds, 0)
        self.assertIsNotNone(reason)

    def test_long_limit(self) -> None:
        seconds, reason = evaluate_content_limits(1, CONTENT_LONG_MAX_VIEWS + 1)
        self.assertGreater(seconds, 0)
        self.assertIsNotNone(reason)

    def test_normal_reading_is_allowed(self) -> None:
        seconds, reason = evaluate_content_limits(2, 10)
        self.assertEqual(seconds, 0)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
