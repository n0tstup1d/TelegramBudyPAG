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
    "README_PRODAMUS.md",
    "tests/test_payment_placeholder.py",
    "tests/test_prodamus_compliance.py",
]


def _project_files(pattern: str):
    ignored = {".venv", "venv", ".git", ".idea"}
    for path in ROOT.rglob(pattern):
        if any(part in ignored for part in path.relative_to(ROOT).parts):
            continue
        yield path


def main() -> None:
    removed: list[str] = []
    for relative in OBSOLETE_FILES:
        path = ROOT / relative
        if path.exists() and path.is_file():
            path.unlink()
            removed.append(relative)

    for cache in list(_project_files("__pycache__")):
        if cache.is_dir():
            shutil.rmtree(cache, ignore_errors=True)
            removed.append(str(cache.relative_to(ROOT)) + "/")

    for pattern in ("*.pyc", "*.pyo"):
        for bytecode in _project_files(pattern):
            if bytecode.is_file():
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
