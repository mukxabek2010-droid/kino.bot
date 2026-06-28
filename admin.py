from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from utils import check_subscription
from keyboards import subscription_kb, main_menu_kb
import database as db

router = Router()


async def require_subscription(message: Message, bot: Bot) -> bool:
    """
    Foydalanuvchi obunasini tekshiradi.
    Agar obuna bo'lmasa — xabar yuboradi va False qaytaradi.
    """
    user_id = message.from_user.id
    if not await check_subscription(bot, user_id):
        await message.answer(
            "❗ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
            "Obuna bo'lgach, <b>✅ Obunani tekshirish</b> tugmasini bosing.",
            reply_markup=subscription_kb(),
            parse_mode="HTML"
        )
        return False
    return True


@router.callback_query(F.data == "check_subscription")
async def handle_check_subscription(call: CallbackQuery, bot: Bot):
    user = call.from_user
    db.add_user(user.id, user.username or "", user.full_name)

    if await check_subscription(bot, user.id):
        await call.message.delete()
        await call.message.answer(
            f"✅ <b>Rahmat, {user.full_name}!</b>\n\n"
            "Siz barcha kanallarga obuna bo'ldingiz. Botga xush kelibsiz! 🎬\n\n"
            "🔢 Kino kodini yuboring va kinoni oling.",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
    else:
        await call.answer("❌ Siz hali barcha kanallarga obuna bo'lmagansiz!", show_alert=True)
