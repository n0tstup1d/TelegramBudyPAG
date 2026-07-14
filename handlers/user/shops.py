from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select

from database.engine import async_session
from database.models import Shop, ShopClick
from database.settings import is_shops_enabled
from keyboards.user.shops import shops_menu, shop_card_menu

router = Router()


@router.callback_query(F.data == "section:shops")
async def show_shops(callback: CallbackQuery):
    async with async_session() as session:
        shops_enabled = await is_shops_enabled(session)
        if not shops_enabled:
            await callback.answer("Раздел магазинов сейчас скрыт", show_alert=True)
            return

        result = await session.execute(
            select(Shop).where(Shop.is_active == True)
        )
        shops = result.scalars().all()

    if not shops:
        await callback.message.edit_text(
            "🏪 Магазины БАДов\n\nПока нет доступных магазинов.",
            reply_markup=shops_menu([])
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "🏪 Магазины БАДов\n\nВыбери магазин:",
        reply_markup=shops_menu(shops)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shop:"))
async def show_shop(callback: CallbackQuery):
    shop_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        if not await is_shops_enabled(session):
            await callback.answer("Раздел магазинов сейчас скрыт", show_alert=True)
            return
        shop = await session.get(Shop, shop_id)

        if not shop:
            await callback.answer("Магазин не найден", show_alert=True)
            return

        await callback.message.edit_text(
            f"🏪 {shop.name}\n\n"
            f"🌍 Страна: {shop.country}\n\n"
            f"Нажми кнопку ниже чтобы перейти в магазин:",
            reply_markup=shop_card_menu(shop.id)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("shop_click:"))
async def shop_click(callback: CallbackQuery):
    shop_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        if not await is_shops_enabled(session):
            await callback.answer("Раздел магазинов сейчас скрыт", show_alert=True)
            return
        shop = await session.get(Shop, shop_id)

        if not shop:
            await callback.answer("Магазин не найден", show_alert=True)
            return

        # записываем клик
        click = ShopClick(
            user_id=callback.from_user.id,
            shop_id=shop_id
        )
        session.add(click)
        await session.commit()

        await callback.answer("Открываем магазин...", show_alert=False)
        await callback.message.answer(
            f"🔗 Ссылка на магазин {shop.name}:\n{shop.url}"
        )