"""Удаляет старые закрытые обращения поддержки и служебные связи сообщений.

Запуск вручную:
    python scripts/cleanup_support_data.py

Рекомендуется запускать раз в сутки после резервного копирования.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from config import SUPPORT_RETENTION_DAYS
from database.engine import async_session, engine
from database.models import SupportMessageLink, SupportTicket


async def cleanup() -> tuple[int, int]:
    cutoff = datetime.now() - timedelta(days=max(1, SUPPORT_RETENTION_DAYS))

    async with async_session() as session:
        result = await session.execute(
            select(SupportTicket.id).where(
                SupportTicket.status == "closed",
                SupportTicket.closed_at.is_not(None),
                SupportTicket.closed_at < cutoff,
            )
        )
        ticket_ids = list(result.scalars())
        if not ticket_ids:
            return 0, 0

        links_result = await session.execute(
            delete(SupportMessageLink)
            .where(SupportMessageLink.ticket_id.in_(ticket_ids))
            .returning(SupportMessageLink.id)
        )
        removed_links = len(list(links_result.scalars()))

        tickets_result = await session.execute(
            delete(SupportTicket)
            .where(SupportTicket.id.in_(ticket_ids))
            .returning(SupportTicket.id)
        )
        removed_tickets = len(list(tickets_result.scalars()))
        await session.commit()
        return removed_tickets, removed_links


async def main() -> None:
    try:
        tickets, links = await cleanup()
        print(f"Удалено обращений: {tickets}; связей сообщений: {links}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
