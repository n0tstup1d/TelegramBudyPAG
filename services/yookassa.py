from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import uuid4

import aiohttp

from config import (
    BOT_PUBLIC_URL,
    PRODUCT_PRICE,
    PROJECT_NAME,
    YOOKASSA_API_BASE_URL,
    YOOKASSA_API_TIMEOUT_SECONDS,
    YOOKASSA_RETURN_URL,
    YOOKASSA_SECRET_KEY,
    YOOKASSA_SHOP_ID,
)


class YooKassaError(RuntimeError):
    """Ошибка взаимодействия с API ЮKassa без раскрытия секретов."""


@dataclass(frozen=True)
class CreatedPayment:
    payment_id: str
    status: str
    confirmation_url: str
    raw: dict[str, Any]


def is_yookassa_configured() -> bool:
    return bool(YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY)


def amount_value(rubles: int) -> str:
    return f"{Decimal(rubles):.2f}"


def build_payment_payload(*, user_id: int, order_id: str) -> dict[str, Any]:
    return {
        "amount": {
            "value": amount_value(PRODUCT_PRICE),
            "currency": "RUB",
        },
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": YOOKASSA_RETURN_URL or BOT_PUBLIC_URL,
        },
        "description": f"Бессрочный доступ к {PROJECT_NAME}",
        "save_payment_method": False,
        "metadata": {
            "order_id": order_id,
            "telegram_user_id": str(user_id),
            "product": "vega_lifetime_access",
        },
    }


async def _request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    idempotence_key: str | None = None,
) -> dict[str, Any]:
    if not is_yookassa_configured():
        raise YooKassaError("Не заданы YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY")

    headers = {"Accept": "application/json"}
    if idempotence_key:
        headers["Idempotence-Key"] = idempotence_key

    timeout = aiohttp.ClientTimeout(total=YOOKASSA_API_TIMEOUT_SECONDS)
    auth = aiohttp.BasicAuth(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
    url = f"{YOOKASSA_API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(auth=auth, timeout=timeout, headers=headers) as session:
                async with session.request(method, url, json=json_body) as response:
                    try:
                        payload = await response.json(content_type=None)
                    except Exception:
                        payload = {"description": (await response.text())[:500]}

                    if response.status == 200:
                        if not isinstance(payload, dict):
                            raise YooKassaError("ЮKassa вернула ответ неожиданного формата")
                        return payload

                    description = payload.get("description") or payload.get("code") or "неизвестная ошибка"
                    error = YooKassaError(f"ЮKassa вернула HTTP {response.status}: {description}")
                    if response.status not in {429, 500} or attempt == 2:
                        raise error

                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = max(1.0, float(retry_after)) if retry_after else float(2 ** attempt)
                    except ValueError:
                        delay = float(2 ** attempt)
                    last_error = error
                    await asyncio.sleep(delay)

        except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
            last_error = exc
            if attempt == 2:
                break
            await asyncio.sleep(float(2 ** attempt))

    if isinstance(last_error, asyncio.TimeoutError):
        raise YooKassaError("ЮKassa не ответила вовремя") from last_error
    if isinstance(last_error, aiohttp.ClientError):
        raise YooKassaError(f"Сетевая ошибка при обращении к ЮKassa: {last_error}") from last_error
    if isinstance(last_error, YooKassaError):
        raise last_error
    raise YooKassaError("Не удалось получить ответ от ЮKassa")


async def create_payment(*, user_id: int, order_id: str | None = None) -> CreatedPayment:
    order_id = order_id or uuid4().hex
    idempotence_key = uuid4().hex
    payload = await _request(
        "POST",
        "/payments",
        json_body=build_payment_payload(user_id=user_id, order_id=order_id),
        idempotence_key=idempotence_key,
    )

    payment_id = str(payload.get("id") or "").strip()
    status = str(payload.get("status") or "").strip()
    confirmation = payload.get("confirmation") or {}
    confirmation_url = str(confirmation.get("confirmation_url") or "").strip()

    if not payment_id or not confirmation_url:
        raise YooKassaError("ЮKassa не вернула идентификатор платежа или ссылку на оплату")

    return CreatedPayment(
        payment_id=payment_id,
        status=status or "pending",
        confirmation_url=confirmation_url,
        raw=payload,
    )


async def get_payment(payment_id: str) -> dict[str, Any]:
    payment_id = payment_id.strip()
    if not payment_id:
        raise YooKassaError("Не указан идентификатор платежа")
    return await _request("GET", f"/payments/{payment_id}")
