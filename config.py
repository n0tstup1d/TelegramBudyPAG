from __future__ import annotations

from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on", "да"}:
        return True
    if normalized in {"0", "false", "no", "off", "нет"}:
        return False
    raise RuntimeError(
        f"Переменная {name} должна быть true/false, 1/0, yes/no или on/off; получено: {value!r}"
    )


def _env_int(name: str, *, default: int | None = None, required: bool = False) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        if required:
            raise RuntimeError(f"Не задана обязательная переменная окружения {name}")
        if default is None:
            raise RuntimeError(f"Для переменной {name} не задано значение по умолчанию")
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Переменная {name} должна быть целым числом; получено: {raw!r}") from exc


def _required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Не задана обязательная переменная окружения {name}")
    return value


def _env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


BOT_TOKEN = _required("BOT_TOKEN")
DATABASE_URL = _required("DATABASE_URL")
TEAM_CHAT_ID = _env_int("TEAM_CHAT_ID", required=True)
USERS_CHAT_ID = _env_int("USERS_CHAT_ID", required=True)

SUPPORT_URL = (os.getenv("SUPPORT_URL") or "").strip()
PARTNERSHIP_URL = (os.getenv("PARTNERSHIP_URL") or "").strip()
CONTENT_URL = (os.getenv("CONTENT_URL") or "").strip()

# Рабочая супергруппа команды с включёнными темами (Forum Topics).
SUPPORT_DIALOG_CHAT_ID = _env_int("SUPPORT_DIALOG_CHAT_ID", default=TEAM_CHAT_ID)

# Витрина VEGA и интеграция ЮKassa.
PROJECT_NAME = os.getenv("PROJECT_NAME", "VEGA")
PRODUCT_PRICE = _env_int("PRODUCT_PRICE", default=390)
PRODUCT_ACCESS_TEXT = (os.getenv("PRODUCT_ACCESS_TEXT") or "бессрочный").strip()
PAYMENTS_ENABLED = _env_bool("PAYMENTS_ENABLED", default=False)
PAYMENT_PROVIDER_NAME = (os.getenv("PAYMENT_PROVIDER_NAME") or "ЮKassa").strip()

# ЮKassa: ключи хранятся только в .env на сервере.
YOOKASSA_SHOP_ID = (os.getenv("YOOKASSA_SHOP_ID") or "").strip()
YOOKASSA_SECRET_KEY = (os.getenv("YOOKASSA_SECRET_KEY") or "").strip()
YOOKASSA_API_BASE_URL = (os.getenv("YOOKASSA_API_BASE_URL") or "https://api.yookassa.ru/v3").strip()
YOOKASSA_API_TIMEOUT_SECONDS = _env_int("YOOKASSA_API_TIMEOUT_SECONDS", default=20)
YOOKASSA_POLL_INTERVAL_SECONDS = _env_int("YOOKASSA_POLL_INTERVAL_SECONDS", default=20)
YOOKASSA_POLL_BATCH_SIZE = _env_int("YOOKASSA_POLL_BATCH_SIZE", default=25)

# Ручное формирование чеков НПД и автоматический контроль очереди.
RECEIPT_REMINDERS_ENABLED = _env_bool("RECEIPT_REMINDERS_ENABLED", default=True)
RECEIPT_REMINDER_INTERVAL_SECONDS = _env_int("RECEIPT_REMINDER_INTERVAL_SECONDS", default=900)
RECEIPT_FIRST_REMINDER_HOURS = _env_int("RECEIPT_FIRST_REMINDER_HOURS", default=2)
RECEIPT_URGENT_REMINDER_HOURS = _env_int("RECEIPT_URGENT_REMINDER_HOURS", default=12)
RECEIPT_OVERDUE_HOURS = _env_int("RECEIPT_OVERDUE_HOURS", default=24)
RECEIPT_ITEM_NAME = (
    os.getenv("RECEIPT_ITEM_NAME")
    or "Предоставление бессрочного доступа к информационно-образовательной базе VEGA"
).strip()

BOT_PUBLIC_URL = os.getenv("BOT_PUBLIC_URL", "https://t.me/vega_top_bot")
YOOKASSA_RETURN_URL = (os.getenv("YOOKASSA_RETURN_URL") or BOT_PUBLIC_URL).strip()
OFFER_URL = (os.getenv("OFFER_URL") or "").strip()
PRIVACY_URL = (os.getenv("PRIVACY_URL") or "").strip()
OFFER_FILE = _env_path("OFFER_FILE", BASE_DIR / "legal" / "oferta_vega.pdf")
PRIVACY_FILE = _env_path("PRIVACY_FILE", BASE_DIR / "legal" / "privacy_policy_vega.pdf")

SELLER_FULL_NAME = os.getenv("SELLER_FULL_NAME", "Горин Герман Алексеевич").strip()
SELLER_CITY = _required("SELLER_CITY")
SELLER_INN = os.getenv("SELLER_INN", "561408485556").strip()
SELLER_PHONE = os.getenv("SELLER_PHONE", "+7 901 085-64-62").strip()
SELLER_EMAIL = os.getenv("SELLER_EMAIL", "goringerman12@gmail.com").strip()
SELLER_LICENSE_INFO = (
    os.getenv("SELLER_LICENSE_INFO")
    or "Лицензии и аккредитации отсутствуют; образовательные и медицинские услуги не оказываются."
).strip()

# Состояния FSM. Для продакшена укажите Redis, иначе состояния будут потеряны после перезапуска.
REDIS_URL = (os.getenv("REDIS_URL") or "").strip()
ALLOW_MEMORY_STORAGE = _env_bool("ALLOW_MEMORY_STORAGE", default=True)

# По умолчанию накопившиеся обновления Telegram не удаляются при запуске.
DROP_PENDING_UPDATES = _env_bool("DROP_PENDING_UPDATES", default=False)

# Антиспам для личного чата с ботом.
RATE_LIMIT_MAX_ACTIONS = _env_int("RATE_LIMIT_MAX_ACTIONS", default=12)
RATE_LIMIT_WINDOW_SECONDS = _env_int("RATE_LIMIT_WINDOW_SECONDS", default=10)
RATE_LIMIT_BLOCK_SECONDS = _env_int("RATE_LIMIT_BLOCK_SECONDS", default=15)

# Защита платных материалов от простой пересылки и массовой выгрузки.
CONTENT_PROTECTION_ENABLED = _env_bool("CONTENT_PROTECTION_ENABLED", default=True)
CONTENT_VISIBLE_WATERMARK = _env_bool("CONTENT_VISIBLE_WATERMARK", default=True)
CONTENT_HIDDEN_FINGERPRINT = _env_bool("CONTENT_HIDDEN_FINGERPRINT", default=True)
CONTENT_MARK_SECRET = (os.getenv("CONTENT_MARK_SECRET") or "").strip()
CONTENT_SHORT_WINDOW_SECONDS = _env_int("CONTENT_SHORT_WINDOW_SECONDS", default=60)
CONTENT_SHORT_MAX_VIEWS = _env_int("CONTENT_SHORT_MAX_VIEWS", default=30)
CONTENT_LONG_WINDOW_SECONDS = _env_int("CONTENT_LONG_WINDOW_SECONDS", default=3600)
CONTENT_LONG_MAX_VIEWS = _env_int("CONTENT_LONG_MAX_VIEWS", default=180)
CONTENT_SHORT_BLOCK_SECONDS = _env_int("CONTENT_SHORT_BLOCK_SECONDS", default=600)
CONTENT_LONG_BLOCK_SECONDS = _env_int("CONTENT_LONG_BLOCK_SECONDS", default=3600)
CONTENT_ALERT_COOLDOWN_SECONDS = _env_int("CONTENT_ALERT_COOLDOWN_SECONDS", default=1800)

# Ограничения поддержки.
SUPPORT_MAX_TEXT_LENGTH = _env_int("SUPPORT_MAX_TEXT_LENGTH", default=4000)
SUPPORT_MAX_FILE_MB = _env_int("SUPPORT_MAX_FILE_MB", default=10)
SUPPORT_RETENTION_DAYS = _env_int("SUPPORT_RETENTION_DAYS", default=180)

# Резервные копии PostgreSQL.
BACKUP_DIR = _env_path("BACKUP_DIR", BASE_DIR / "backups")
BACKUP_RETENTION_DAYS = _env_int("BACKUP_RETENTION_DAYS", default=14)
