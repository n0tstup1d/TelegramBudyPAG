"""Локальная проверка проекта перед запуском.

Запуск из корня проекта:
    python scripts/project_check.py
"""
from __future__ import annotations

import compileall
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass
DATA_DIR = ROOT / "data"

REQUIRED_ENV = [
    "BOT_TOKEN", "DATABASE_URL", "TEAM_CHAT_ID", "USERS_CHAT_ID",
    "SELLER_CITY",
]
OPTIONAL_ENV = [
    "PAYMENTS_ENABLED",
    "YOOKASSA_SHOP_ID",
    "YOOKASSA_SECRET_KEY",
    "YOOKASSA_RETURN_URL",
    "SUPPORT_DIALOG_CHAT_ID",
    "SUPPORT_URL",
    "CONTENT_URL",
    "PARTNERSHIP_URL",
    "REDIS_URL",
    "CONTENT_PROTECTION_ENABLED",
    "CONTENT_MARK_SECRET",
    "CONTENT_VISIBLE_WATERMARK",
    "CONTENT_HIDDEN_FINGERPRINT",
]

CATEGORY_ALIASES = {
    "sleep": ["sleep", "Sleep"],
    "nutrition": ["nutrition", "Nutrition"],
    "brain": ["brain", "Focus_and_Brain"],
    "supplements": ["supplements", "Supplements"],
    "recovery": ["recovery", "Recovery"],
    "analytics": ["analytics", "Tests_and_Monitoring"],
}

OBSOLETE_FILES = [
    "data/data.zip",
    "handlers/admin.py",
    "handlers/content.py",
    "handlers/profile.py",
    "handlers/shops.py",
    "handlers/start.py",
]


def check_env() -> list[str]:
    lines = ["🔐 ENV"]
    for name in REQUIRED_ENV:
        value = (os.getenv(name) or "").strip()
        invalid_placeholder = name == "SELLER_CITY" and value.upper() in {"УКАЖИТЕ_ГОРОД", "ВАШ_ГОРОД"}
        ok = bool(value) and not invalid_placeholder
        note = " — замените заглушку реальным городом" if invalid_placeholder else ""
        lines.append(f"  {'✅' if ok else '❌'} {name}{note}")
    payments_enabled = (os.getenv("PAYMENTS_ENABLED") or "").strip().lower() in {"1", "true", "yes", "on", "да"}
    for name in OPTIONAL_ENV:
        value = os.getenv(name)
        marker = "✅" if value else "⚠️"
        note = "" if value else " (не задано)"
        if name == "REDIS_URL" and not value:
            note += " — FSM будет теряться после перезапуска"
        if payments_enabled and name in {"YOOKASSA_SHOP_ID", "YOOKASSA_SECRET_KEY"} and not value:
            marker = "❌"
            note += " — обязательно при PAYMENTS_ENABLED=true"
        if name in {"YOOKASSA_SECRET_KEY", "CONTENT_MARK_SECRET"} and value:
            note = " — задан (значение скрыто)"
        if name == "CONTENT_MARK_SECRET" and not value:
            note += " — будет использован fallback от BOT_TOKEN; для продакшена лучше отдельный секрет"
        lines.append(f"  {marker} {name}{note}")
    protection_enabled = (os.getenv("CONTENT_PROTECTION_ENABLED") or "true").strip().lower() in {
        "1", "true", "yes", "on", "да"
    }
    if protection_enabled:
        lines.append("  ✅ защита платных материалов включена")
    else:
        lines.append("  ⚠️ защита платных материалов отключена")
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
        lines.append(
            f"  {'✅' if topic_keys else '❌'} {section_id}: {len(topic_keys)} тем "
            f"({', '.join(found) if found else 'не найдено'})"
        )

    legacy = DATA_DIR / "supplements.json"
    legacy_ok = legacy.exists() and read_json_keys(legacy) == set()
    lines.append(
        f"  {'✅' if legacy_ok else '❌'} data/supplements.json не перезаписывает подробную тему vitamin_D"
    )
    return lines


def check_files() -> list[str]:
    lines = ["🧹 Структура"]
    leftovers = [path for path in OBSOLETE_FILES if (ROOT / path).exists()]
    if leftovers:
        lines.append("  ⚠️ Найдены устаревшие файлы; выполните: python scripts/apply_update.py")
        lines.extend(f"    - {item}" for item in leftovers)
    else:
        lines.append("  ✅ Устаревшие файлы удалены")

    ignored = {".venv", "venv", ".git", ".idea"}
    caches = [
        path for path in ROOT.rglob("__pycache__")
        if not any(part in ignored for part in path.parts)
    ]
    lines.append(f"  {'⚠️' if caches else '✅'} __pycache__: {len(caches)}")

    try:
        (ROOT / "requirements.txt").read_text(encoding="utf-8")
        lines.append("  ✅ requirements.txt: UTF-8")
    except UnicodeDecodeError:
        lines.append("  ❌ requirements.txt: не UTF-8")
    return lines


def check_compile() -> list[str]:
    targets = [
        ROOT / "config.py", ROOT / "main.py", ROOT / "database", ROOT / "handlers",
        ROOT / "keyboards", ROOT / "middlewares", ROOT / "services", ROOT / "states",
        ROOT / "utils", ROOT / "scripts", ROOT / "tests", ROOT / "migrations",
    ]
    ok = True
    for target in targets:
        if target.is_file():
            ok = compileall.compile_file(target, quiet=1) and ok
        elif target.is_dir():
            ok = compileall.compile_dir(target, quiet=1, maxlevels=10) and ok
    return ["🐍 Python", f"  {'✅' if ok else '❌'} py_compile"]


def check_tests() -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    lines = ["🧪 Тесты", f"  {'✅' if result.returncode == 0 else '❌'} unittest"]
    if result.returncode != 0:
        tail = (result.stdout + "\n" + result.stderr).strip().splitlines()[-12:]
        lines.extend(f"    {line}" for line in tail)
    else:
        lines.append("  ✅ тесты интеграции ЮKassa")
    return lines


def main() -> None:
    for block in (check_env(), check_content(), check_files(), check_compile(), check_tests()):
        print("\n".join(block))
        print()


if __name__ == "__main__":
    main()
