from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import os
import unittest

os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
os.environ.setdefault("TEAM_CHAT_ID", "-1001")
os.environ.setdefault("USERS_CHAT_ID", "-1002")
os.environ.setdefault("SELLER_CITY", "Москва")

from services.receipts import (  # noqa: E402
    ReceiptError,
    receipt_age_hours,
    validate_receipt_url,
)

ROOT = Path(__file__).resolve().parents[1]


class ReceiptServiceTests(unittest.TestCase):
    def test_https_receipt_link_is_accepted(self) -> None:
        self.assertEqual(
            validate_receipt_url(" https://example.nalog.ru/receipt/123 "),
            "https://example.nalog.ru/receipt/123",
        )

    def test_non_https_receipt_link_is_rejected(self) -> None:
        with self.assertRaises(ReceiptError):
            validate_receipt_url("http://example.test/receipt")

    def test_receipt_age_uses_payment_update_time(self) -> None:
        now = datetime(2026, 7, 16, 20, 0, 0)
        transaction = SimpleNamespace(
            updated_at=now - timedelta(hours=3),
            created_at=now - timedelta(hours=10),
        )
        self.assertEqual(receipt_age_hours(transaction, now=now), 3.0)


class ReceiptIntegrationFilesTests(unittest.TestCase):
    def test_admin_menu_and_router_include_receipts(self) -> None:
        menu = (ROOT / "keyboards/admin/main.py").read_text(encoding="utf-8")
        routers = (ROOT / "handlers/admin/__init__.py").read_text(encoding="utf-8")
        handler = (ROOT / "handlers/admin/receipts.py").read_text(encoding="utf-8")
        keyboard = (ROOT / "keyboards/admin/receipts.py").read_text(encoding="utf-8")
        self.assertIn("🧾 Чеки", menu)
        self.assertIn("receipts_router", routers)
        self.assertIn("Добавление чека по ссылке", handler)
        self.assertIn("Добавить ссылку и отправить", keyboard)
        self.assertIn("Отправить чек повторно", keyboard)

    def test_checkout_copy_has_requested_wording(self) -> None:
        storefront = (ROOT / "handlers/user/storefront.py").read_text(encoding="utf-8")
        payments = (ROOT / "services/payments.py").read_text(encoding="utf-8")
        self.assertIn("и завершите оплату.", storefront)
        self.assertNotIn("и завершите оплату на странице ЮKassa", storefront)
        self.assertIn("Чек будет сформирован и направлен вам отдельным сообщением", storefront)
        self.assertIn("после обработки платежа.", storefront)
        self.assertIn("Чек будет сформирован и направлен вам отдельным сообщением", payments)

    def test_receipt_migration_follows_content_protection(self) -> None:
        migration = (
            ROOT / "migrations/versions/e6f7a8b9c0d1_add_receipt_delivery.py"
        ).read_text(encoding="utf-8")
        self.assertIn('down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"', migration)
        self.assertIn("receipt_status", migration)
        self.assertIn("WHERE paid = TRUE", migration)


if __name__ == "__main__":
    unittest.main()
