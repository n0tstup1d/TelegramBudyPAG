from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func

from database.engine import async_session
from database.models import Shop, ShopClick
from handlers.admin.guards import is_admin
from states.admin import ShopStates
from keyboards.admin.shops import admin_shops_menu, admin_shop_card_menu

router = Router()


@router.callback_query(F.data == "admin:shops")
async def admin_shops(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🏪 Управление магазинами",
        reply_markup=admin_shops_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:shop_list")
async def admin_shop_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    async with async_session() as session:
        result = await session.execute(select(Shop).order_by(Shop.created_at.desc()))
        shops = result.scalars().all()

    if not shops:
        await callback.message.edit_text(
            "🏪 Магазинов пока нет",
            reply_markup=admin_shops_menu()
        )
        await callback.answer()
        return

    buttons = []
    for shop in shops:
        status = "✅" if shop.is_active else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {shop.name} ({shop.country})",
                callback_data=f"admin:shop_card:{shop.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:shops")])

    await callback.message.edit_text(
        "🏪 Список магазинов:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:shop_card:"))
async def admin_shop_card(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    shop_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        shop = await session.get(Shop, shop_id)
        if not shop:
            await callback.answer("Магазин не найден", show_alert=True)
            return

        clicks = await session.scalar(
            select(func.count()).select_from(ShopClick).where(ShopClick.shop_id == shop_id)
        )

        status = "✅ Активен" if shop.is_active else "❌ Выключен"
        text = (
            f"🏪 {shop.name}\n\n"
            f"🌍 Страна: {shop.country}\n"
            f"🔗 URL: {shop.url}\n"
            f"📊 Кликов: {clicks}\n"
            f"Статус: {status}"
        )

        await callback.message.edit_text(
            text,
            reply_markup=admin_shop_card_menu(shop_id, shop.is_active)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:shop_toggle:"))
async def admin_shop_toggle(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    shop_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        shop = await session.get(Shop, shop_id)
        if shop:
            shop.is_active = not shop.is_active
            await session.commit()
    await callback.answer("✅ Статус изменён")
    await admin_shop_card(callback)


@router.callback_query(F.data.startswith("admin:shop_delete:"))
async def admin_shop_delete(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    shop_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        shop = await session.get(Shop, shop_id)
        if shop:
            await session.delete(shop)
            await session.commit()

    await callback.answer("🗑 Магазин удалён")
    await callback.message.edit_text(
        "🏪 Управление магазинами",
        reply_markup=admin_shops_menu()
    )


@router.callback_query(F.data == "admin:shop_add")
async def admin_shop_add(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await state.set_state(ShopStates.waiting_name)
    await callback.message.edit_text(
        "🏪 Добавление магазина\n\nВведи название магазина:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:shops")]
        ])
    )
    await callback.answer()


@router.message(ShopStates.waiting_name)
async def admin_shop_name(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    await state.update_data(name=message.text.strip())
    await state.set_state(ShopStates.waiting_country)
    await message.answer("Введи страну (например: RU, KZ, KG):")


@router.message(ShopStates.waiting_country)
async def admin_shop_country(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    await state.update_data(country=message.text.strip().upper())
    await state.set_state(ShopStates.waiting_url)
    await message.answer("Введи реферальную ссылку на магазин:")


@router.message(ShopStates.waiting_url)
async def admin_shop_url(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    data = await state.get_data()
    await state.clear()

    async with async_session() as session:
        shop = Shop(
            name=data["name"],
            country=data["country"],
            url=message.text.strip()
        )
        session.add(shop)
        await session.commit()

    await message.answer(
        f"✅ Магазин добавлен!\n\n"
        f"🏪 {data['name']}\n"
        f"🌍 {data['country']}\n"
        f"🔗 {message.text.strip()}",
        reply_markup=admin_shops_menu()
    )
