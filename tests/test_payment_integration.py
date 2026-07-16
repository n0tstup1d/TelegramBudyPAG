from __future__ import annotations

import os
from pathlib import Path
import unittest

# config.py требует минимальный набор ENV уже при импорте.
os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
os.environ.setdefault("TEAM_CHAT_ID", "-1001")
os.environ.setdefault("USERS_CHAT_ID", "-1002")
os.environ.setdefault("SELLER_CITY", "Москва")

from services.payments import _payment_amount_matches  # noqa: E402
from services.yookassa import amount_value, build_payment_payload  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class YooKassaPaymentTests(unittest.TestCase):
    def test_payment_payload_is_one_stage_and_non_recurring(self) -> None:
        payload = build_payment_payload(user_id=7017959194, order_id="order-1")
        self.assertEqual(payload["amount"], {"value": "390.00", "currency": "RUB"})
        self.assertTrue(payload["capture"])
        self.assertFalse(payload["save_payment_method"])
        self.assertEqual(payload["confirmation"]["type"], "redirect")
        self.assertEqual(payload["metadata"]["telegram_user_id"], "7017959194")
        self.assertEqual(payload["metadata"]["product"], "vega_lifetime_access")

    def test_amount_format(self) -> None:
        self.assertEqual(amount_value(390), "390.00")


    def test_payment_amount_is_checked_against_stored_order_amount(self) -> None:
        payment = {"amount": {"value": "390.00", "currency": "RUB"}}
        self.assertTrue(_payment_amount_matches(payment, 390))
        self.assertFalse(_payment_amount_matches(payment, 50))

    def test_checkout_copy_requires_explicit_check_and_has_no_roadmap_block(self) -> None:
        storefront = (ROOT / "handlers/user/storefront.py").read_text(encoding="utf-8")
        common = (ROOT / "keyboards/common.py").read_text(encoding="utf-8")
        self.assertIn("Я оплатил — проверить", storefront)
        self.assertIn("Я оплатил — проверить", common)
        self.assertNotIn("Кнопка «Проверить оплату» доступна как резервный вариант", storefront)
        self.assertNotIn("завершите оплату на странице ЮKassa", storefront)
        self.assertIn("Чек будет сформирован и направлен вам отдельным сообщением", storefront)
        payment_block = storefront.split('"💳 <b>Платёж создан</b>', 1)[1].split('markup = yookassa_checkout_keyboard', 1)[0]
        self.assertNotIn("VEGA развивается", payment_block)

    def test_admin_has_payment_check_and_history_actions(self) -> None:
        handler = (ROOT / "handlers/admin/users.py").read_text(encoding="utf-8")
        keyboard = (ROOT / "keyboards/admin/users.py").read_text(encoding="utf-8")
        self.assertIn("admin:payment_check:", handler)
        self.assertIn("admin:payment_history:", handler)
        self.assertIn("Проверить последний платёж", keyboard)
        self.assertIn("История платежей", keyboard)

    def test_no_early_access_or_obsolete_provider_copy(self) -> None:
        paths = [
            ROOT / "config.py",
            ROOT / "handlers/user/start.py",
            ROOT / "handlers/user/storefront.py",
            ROOT / "keyboards/common.py",
            ROOT / "services/navigation.py",
            ROOT / "legal/oferta_vega.txt",
            ROOT / "legal/privacy_policy_vega.txt",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths).lower()
        for forbidden in ("раннего доступа", "ранний доступ", "prodamus", "robokassa", "5 (пять) лет"):
            self.assertNotIn(forbidden, text)
        self.assertIn("юkassa", text)
        self.assertIn("бессроч", text)


if __name__ == "__main__":
    unittest.main()
