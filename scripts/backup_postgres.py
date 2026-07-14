"""Создаёт резервную копию PostgreSQL через pg_dump.

Запуск из корня проекта:
    python scripts/backup_postgres.py

Для cron, например ежедневно в 03:30:
    30 3 * * * cd /path/to/project && /path/to/venv/bin/python scripts/backup_postgres.py
"""
from __future__ import annotations

from datetime import datetime, timedelta
import os
from pathlib import Path
import shutil
import subprocess
from urllib.parse import unquote, urlparse

from config import BACKUP_DIR, BACKUP_RETENTION_DAYS, DATABASE_URL


def parse_database_url(url: str) -> tuple[str, str, int, str, str | None]:
    normalized = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise RuntimeError("Скрипт резервного копирования поддерживает только PostgreSQL")
    if not parsed.hostname or not parsed.username or not parsed.path.strip("/"):
        raise RuntimeError("DATABASE_URL не содержит host, user или database")
    return (
        parsed.hostname,
        unquote(parsed.username),
        parsed.port or 5432,
        parsed.path.strip("/"),
        unquote(parsed.password) if parsed.password else None,
    )


def cleanup_old_backups(directory: Path, retention_days: int) -> int:
    cutoff = datetime.now() - timedelta(days=max(1, retention_days))
    removed = 0
    for path in directory.glob("vega_*.dump"):
        if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def main() -> None:
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise RuntimeError("Команда pg_dump не найдена. Установите PostgreSQL client tools.")

    host, user, port, database, password = parse_database_url(DATABASE_URL)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    output = BACKUP_DIR / f"vega_{datetime.now():%Y%m%d_%H%M%S}.dump"

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    command = [
        pg_dump,
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--host", host,
        "--port", str(port),
        "--username", user,
        "--file", str(output),
        database,
    ]
    subprocess.run(command, check=True, env=env)
    removed = cleanup_old_backups(BACKUP_DIR, BACKUP_RETENTION_DAYS)
    print(f"Резервная копия создана: {output}")
    print(f"Удалено старых копий: {removed}")


if __name__ == "__main__":
    main()
