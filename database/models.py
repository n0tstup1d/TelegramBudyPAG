from datetime import datetime
from sqlalchemy import (
    BigInteger, String, Boolean,
    DateTime, Integer, Index, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    has_subscription: Mapped[bool] = mapped_column(Boolean, default=False)
    subscription_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    agreed_to_terms: Mapped[bool] = mapped_column(Boolean, default=False)
    agreed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    referral_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    promo_used: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    role: Mapped[str] = mapped_column(String(16), default="user")

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    paid: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[str] = mapped_column(String(32), default="yookassa")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Чек самозанятого формируется вручную в «Мой налог», а бот хранит
    # очередь, доставляет ссылку/файл покупателю и фиксирует отправку.
    receipt_status: Mapped[str] = mapped_column(String(24), default="not_required", nullable=False, index=True)
    receipt_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    receipt_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    receipt_file_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    receipt_delivery_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    receipt_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    receipt_admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    receipt_reminder_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    receipt_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    discount: Mapped[int] = mapped_column(Integer, nullable=False)
    usage_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ShopClick(Base):
    __tablename__ = "shop_clicks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shop_id: Mapped[int] = mapped_column(Integer, nullable=False)
    clicked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ContentStat(Base):
    __tablename__ = "content_stats"
    __table_args__ = (
        Index("ix_content_stats_user_clicked_at", "user_id", "clicked_at"),
        Index("ix_content_stats_content_id", "content_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_id: Mapped[str] = mapped_column(String(128), nullable=False)
    clicked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ContentProtectionState(Base):
    __tablename__ = "content_protection_states"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_alert_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ReferralBalance(Base):
    __tablename__ = "referral_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    frozen: Mapped[int] = mapped_column(Integer, default=0)
    total_earned: Mapped[int] = mapped_column(Integer, default=0)


class WithdrawalRequest(Base):
    __tablename__ = "withdrawal_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    taken_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="support")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    staff_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    staff_thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    staff_topic_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SupportMessageLink(Base):
    __tablename__ = "support_message_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    staff_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    staff_message_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256), nullable=False)