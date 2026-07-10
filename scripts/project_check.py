"""Локальная проверка проекта перед тестовым запуском.

Запуск из корня проекта:
    python scripts/project_check.py
"""
from __future__ import annotations

import compileall
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass
DATA_DIR = ROOT / "data"

REQUIRED_ENV = [
    "BOT_TOKEN",
    "DATABASE_URL",
    "TEAM_CHAT_ID",
    "USERS_CHAT_ID",
]

OPTIONAL_ENV = [
    "SUPPORT_DIALOG_CHAT_ID",
    "SUPPORT_URL",
    "CONTENT_URL",
    "PARTNERSHIP_URL",
]

CATEGORY_ALIASES = {
    "sleep": ["sleep", "Sleep"],
    "nutrition": ["nutrition", "Nutrition"],
    "brain": ["brain", "Focus_and_Brain"],
    "supplements": ["supplements", "Supplements"],
    "recovery": ["recovery", "Recovery"],
    "analytics": ["analytics", "Tests_and_Monitoring"],
}


def check_env() -> list[str]:
    lines = ["🔐 ENV"]
    for name in REQUIRED_ENV:
        value = os.getenv(name)
        lines.append(f"  {'✅' if value else '❌'} {name}")
    for name in OPTIONAL_ENV:
        value = os.getenv(name)
        lines.append(f"  {'✅' if value else '⚠️'} {name} {'(не задано)' if not value else ''}")
    return lines


def read_json_keys(path: Path) -> set[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return set(data.keys()) if isinstance(data, dict) else set()


def collect_topic_keys(paths: list[Path]) -> set[str]:
    keys: set[str] = set()
    for path in paths:
        if path.is_dir():
            for file in path.glob("*.json"):
                keys.update(read_json_keys(file))
        elif path.is_file() and path.suffix == ".json":
            keys.update(read_json_keys(path))
    return keys


def check_content() -> list[str]:
    lines = ["📚 Контент"]
    for section_id, names in CATEGORY_ALIASES.items():
        paths: list[Path] = []
        found = []
        for name in names:
            folder = DATA_DIR / name
            if folder.exists():
                found.append(name)
                paths.append(folder)
            json_path = DATA_DIR / f"{name}.json"
            if json_path.exists():
                found.append(f"{name}.json")
                paths.append(json_path)
        topic_keys = collect_topic_keys(paths)
        lines.append(f"  {'✅' if topic_keys else '❌'} {section_id}: {len(topic_keys)} тем ({', '.join(found) if found else 'не найдено'})")
    return lines


def check_compile() -> list[str]:
    ok = compileall.compile_dir(ROOT, quiet=1, maxlevels=10)
    return ["🐍 Python", f"  {'✅' if ok else '❌'} py_compile"]


def main() -> None:
    for block in (check_env(), check_content(), check_compile()):
        print("\n".join(block))
        print()


if __name__ == "__main__":
    main()
