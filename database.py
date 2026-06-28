from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

from config import ADMIN_IDS, PAYMENT_CARD, PAYMENT_NAME, PREMIUM_PRICE, CHANNEL_1, CHANNEL_2
from keyboards import (
    main_menu_kb, subscription_kb, premium_menu_kb, cancel_kb
)
from handlers.subscription import require_subscription
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db

router = Router()


class PaymentState(StatesGroup):
    waiting_receipt = State()


# ─── /START ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def start_handler(message: Message, bot: Bot):
    user = message.from_user
    db.add_user(user.id, user.username or "", user.full_name)

    # Obunani tekshirish
    from utils import check_subscription
    if not await check_subscription(bot, user.id):
        await message.answer(
            f"👋 Salom, <b>{user.full_name}</b>!\n\n"
            "🎬 <b>KinoBot</b>ga xush kelibsiz!\n\n"
            "📢 Botdan foydalanish uchun quyidagi <b>2 ta kanalga</b> obuna bo'ling:",
            reply_markup=subscription_kb(),
            parse_mode="HTML"
        )
        return

    is_premium_user = db.is_premium(user.id)
    premium_badge = "⭐" if is_premium_user else ""

    await message.answer(
        f"👋 Salom, <b>{user.full_name}</b>! {premium_badge}\n\n"
        "🎬 <b>KinoBot</b>ga xush kelibsiz!\n\n"
        "🔢 <b>Kino kodini yuboring</b> va kinoni oling.\n"
        "💡 Admin tomonidan har kuni yangi kinolar qo'shiladi!",
        reply_markup=main_menu_kb(is_premium_user),
        parse_mode="HTML"
    )


# ─── PROFIL ───────────────────────────────────────────────────────────────────

@router.message(F.text == "👤 Profil")
async def profile_handler(message: Message, bot: Bot):
    if not await require_subscription(message, bot):
        return

    user = message.from_user
    is_prem = db.is_premium(user.id)
    expires = db.get_premium_expires(user.id)

    if is_prem and expires:
        premium_text = f"⭐ <b>Premium</b>\n⏳ Muddat: {expires.strftime('%d.%m.%Y')}"
    else:
        premium_text = "🆓 Oddiy foydalanuvchi"

    await message.answer(
        f"👤 <b>Profil</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Ism: {user.full_name}\n"
        f"📊 Tur: {premium_text}",
        parse_mode="HTML"
    )


# ─── YORDAM ───────────────────────────────────────────────────────────────────

@router.message(F.text == "📞 Yordam")
async def help_handler(message: Message):
    await message.answer(
        "📞 <b>Yordam</b>\n\n"
        "🔢 Kino olish uchun kino kodini yuboring.\n"
        "⭐ Premium kinolarni faqat premium foydalanuvchilar ko'ra oladi.\n\n"
        f"📢 Kanallar:\n{CHANNEL_1}\n{CHANNEL_2}\n\n"
        "❓ Muammo bo'lsa admin bilan bog'laning.",
        parse_mode="HTML"
    )


# ─── PREMIUM MENU ─────────────────────────────────────────────────────────────

@router.message(F.text == "⭐ Premium")
async def premium_info_handler(message: Message, bot: Bot):
    if not await require_subscription(message, bot):
        return

    is_prem = db.is_premium(message.from_user.id)
    expires = db.get_premium_expires(message.from_user.id)

    if is_prem and expires:
        await message.answer(
            f"⭐ <b>Sizda Premium mavjud!</b>\n\n"
            f"⏳ Muddat: <b>{expires.strftime('%d.%m.%Y')}</b> gacha\n\n"
            "🎬 Barcha premium kinolardan bahramand bo'ling!",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"⭐ <b>Premium — {PREMIUM_PRICE:,} so'm/oy</b>\n\n"
            "✅ <b>Premium afzalliklari:</b>\n"
            "• Barcha premium kinolarni ko'rish\n"
            "• Yangi kinolarga birinchi kirish\n"
            "• Cheksiz kino yuklab olish\n\n"
            "💳 To'lov qilish uchun quyidagi tugmani bosing:",
            reply_markup=premium_menu_kb(),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "buy_premium")
async def buy_premium_handler(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        f"💳 <b>Premium xarid qilish</b>\n\n"
        f"💰 Narx: <b>{PREMIUM_PRICE:,} so'm / 1 oy</b>\n\n"
        f"📲 Quyidagi kartaga o'tkazing:\n"
        f"<code>{PAYMENT_CARD}</code>\n"
        f"👤 {PAYMENT_NAME}\n\n"
        f"✅ To'lov qilgach, <b>chek rasmini yuboring</b>:",
        parse_mode="HTML"
    )
    await state.set_state(PaymentState.waiting_receipt)


@router.message(PaymentState.waiting_receipt, F.photo)
async def receipt_received(message: Message, state: FSMContext, bot: Bot):
    photo_id = message.photo[-1].file_id
    user = message.from_user

    req_id = db.create_payment_request(user.id, photo_id)
    await state.clear()

    await message.answer(
        "✅ <b>Chek qabul qilindi!</b>\n\n"
        "⏳ Admin tekshirib, tez orada premium faollashtiradi.\n"
        "📩 Tasdiqlangach xabar olasiz.",
        reply_markup=main_menu_kb(False),
        parse_mode="HTML"
    )

    # Adminlarga xabar
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💳 <b>Yangi to'lov so'rovi #{req_id}</b>\n\n"
                f"👤 Foydalanuvchi: {user.full_name}\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"💰 Summa: {PREMIUM_PRICE:,} so'm",
                parse_mode="HTML"
            )
            from keyboards import payment_approve_kb
            await bot.send_photo(
                admin_id,
                photo_id,
                caption="⬆️ Chek rasmi",
                reply_markup=payment_approve_kb(req_id, user.id)
            )
        except Exception:
            pass


@router.message(PaymentState.waiting_receipt)
async def receipt_not_photo(message: Message):
    await message.answer("❌ Iltimos, <b>chek rasmini</b> yuboring (rasm shaklida)!", parse_mode="HTML")


@router.callback_query(F.data == "close")
async def close_callback(call: CallbackQuery):
    await call.message.delete()


# ─── KINO KODI ────────────────────────────────────────────────────────────────

@router.message(F.text & ~F.text.startswith("/"))
async def movie_code_handler(message: Message, bot: Bot):
    # Admin tugmalarini o'tkazib yuborish
    admin_buttons = [
        "🎬 Kino qo'shish", "🗑 Kino o'chirish", "👑 Premium berish",
        "📊 Statistika", "📨 Xabar yuborish", "💳 To'lovlar",
        "🎬 Kinolar ro'yxati"
    ]
    menu_buttons = ["🎬 Kino qidirish", "⭐ Premium", "👤 Profil", "📞 Yordam"]

    if message.text in admin_buttons + menu_buttons:
        return

    user = message.from_user
    db.add_user(user.id, user.username or "", user.full_name)

    # Obuna tekshirish
    if not await require_subscription(message, bot):
        return

    code = message.text.strip()
    movie = db.get_movie(code)

    if not movie:
        await message.answer(
            f"❌ <b>{code}</b> kodi topilmadi.\n\n"
            "Kodni to'g'ri kiritganingizni tekshiring.",
            parse_mode="HTML"
        )
        return

    # Premium kino tekshirish
    if movie["is_premium"] and not db.is_premium(user.id):
        await message.answer(
            f"⭐ <b>Bu kino Premium foydalanuvchilar uchun!</b>\n\n"
            f"🎬 <b>{movie['title']}</b>\n\n"
            f"Premium obuna olish uchun /premium buyrug'ini yuboring yoki\n"
            f"<b>⭐ Premium</b> tugmasini bosing.\n\n"
            f"💰 Narx: <b>10,000 so'm/oy</b>",
            reply_markup=premium_menu_kb(),
            parse_mode="HTML"
        )
        return

    # Kinoni yuborish
    caption = movie["caption"] or f"🎬 {movie['title']}"
    if movie["is_premium"]:
        caption = f"⭐ {caption}"

    try:
        await bot.send_video(
            chat_id=message.chat.id,
            video=movie["file_id"],
            caption=caption,
            parse_mode="HTML"
        )
        db.log_stat(user.id, "watch", code)
    except Exception as e:
        await message.answer(f"❌ Kino yuborishda xatolik: {e}")
