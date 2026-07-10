from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from database.engine import async_session
from database.models import PromoCode
from handlers.admin.guards import is_admin
from states.admin import PromoStates
from keyboards.admin.promos import promo_menu, promo_list_menu, promo_card_menu

router = Router()


@router.callback_query(F.data == "admin:promo")
async def admin_promo(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🎟 Промокоды",
        reply_markup=promo_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:promo_list")
async def admin_promo_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    async with async_session() as session:
        result = await session.execute(select(PromoCode).order_by(PromoCode.created_at.desc()))
        promos = result.scalars().all()

    if not promos:
        await callback.message.edit_text(
            "🎟 Промокодов пока нет",
            reply_markup=promo_menu()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "🎟 Список промокодов:",
        reply_markup=promo_list_menu(promos)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo_card:"))
async def admin_promo_card(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    promo_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        promo = await session.get(PromoCode, promo_id)
        if not promo:
            await callback.answer("Промокод не найден", show_alert=True)
            return

        status = "✅ Активен" if promo.is_active else "❌ Выключен"
        text = (
            f"🎟 Промокод: {promo.code}\n\n"
            f"💰 Скидка: {promo.discount} ₽\n"
            f"📊 Использований: {promo.used_count}/{promo.usage_limit}\n"
            f"Статус: {status}"
        )

        await callback.message.edit_text(
            text,
            reply_markup=promo_card_menu(promo_id, promo.is_active)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo_toggle:"))
async def admin_promo_toggle(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    promo_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        promo = await session.get(PromoCode, promo_id)
        if promo:
            promo.is_active = not promo.is_active
            await session.commit()
            await callback.answer("✅ Статус изменён")
            await admin_promo_card(callback)


@router.callback_query(F.data.startswith("admin:promo_delete:"))
async def admin_promo_delete(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    promo_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        promo = await session.get(PromoCode, promo_id)
        if promo:
            await session.delete(promo)
            await session.commit()

    await callback.answer("🗑 Промокод удалён")
    await callback.message.edit_text(
        "🎟 Промокоды",
        reply_markup=promo_menu()
    )


@router.callback_query(F.data == "admin:promo_create")
async def admin_promo_create(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await state.set_state(PromoStates.waiting_code)
    await callback.message.edit_text(
        "🎟 Создание промокода\n\n"
        "Введи код промокода (только латиница и цифры):\n"
        "Например: HEALTH20",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:promo")]
        ])
    )
    await callback.answer()


@router.message(PromoStates.waiting_code)
async def admin_promo_code(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    code = message.text.strip().upper()

    async with async_session() as session:
        result = await session.execute(
            select(PromoCode).where(PromoCode.code == code)
        )
        exists = result.scalar_one_or_none()

    if exists:
        await message.answer("⚠️ Такой промокод уже существует. Введи другой:")
        return

    await state.update_data(code=code)
    await state.set_state(PromoStates.waiting_discount)
    await message.answer(
        f"✅ Код: {code}\n\nВведи размер скидки в рублях:"
    )


@router.message(PromoStates.waiting_discount)
async def admin_promo_discount(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    if not message.text.isdigit():
        await message.answer("⚠️ Введи число")
        return

    await state.update_data(discount=int(message.text))
    await state.set_state(PromoStates.waiting_limit)
    await message.answer("Введи лимит использований (сколько раз можно применить):")


@router.message(PromoStates.waiting_limit)
async def admin_promo_limit(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    if not message.text.isdigit():
        await message.answer("⚠️ Введи число")
        return

    data = await state.get_data()
    await state.clear()

    async with async_session() as session:
        promo = PromoCode(
            code=data["code"],
            discount=data["discount"],
            usage_limit=int(message.text)
        )
        session.add(promo)
        await session.commit()

    await message.answer(
        f"✅ Промокод создан!\n\n"
        f"Код: {data['code']}\n"
        f"Скидка: {data['discount']} ₽\n"
        f"Лимит: {message.text} использований",
        reply_markup=promo_menu()
    )
