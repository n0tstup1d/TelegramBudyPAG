"""Одноразовая очистка устаревших файлов после распаковки обновления.

Запустите из корня проекта:
    python scripts/apply_update.py
"""
from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

OBSOLETE_FILES = [
    "data/data.zip",
    "handlers/admin.py",
    "handlers/content.py",
    "handlers/profile.py",
    "handlers/shops.py",
    "handlers/start.py",
]


def main() -> None:
    removed: list[str] = []
    for relative in OBSOLETE_FILES:
        path = ROOT / relative
        if path.exists() and path.is_file():
            path.unlink()
            removed.append(relative)

    for cache in ROOT.rglob("__pycache__"):
        if cache.is_dir():
            shutil.rmtree(cache, ignore_errors=True)
            removed.append(str(cache.relative_to(ROOT)) + "/")

    for bytecode in ROOT.rglob("*.py[co]"):
        bytecode.unlink(missing_ok=True)
        removed.append(str(bytecode.relative_to(ROOT)))

    print("Очистка завершена.")
    if removed:
        print("Удалено:")
        for item in sorted(set(removed)):
            print(f"  - {item}")
    else:
        print("Устаревших файлов не найдено.")


if __name__ == "__main__":
    main()
