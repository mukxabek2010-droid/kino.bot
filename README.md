from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config import ADMIN_IDS
from keyboards import (
    admin_menu_kb, movie_type_kb, cancel_kb,
    payment_approve_kb, broadcast_confirm_kb, main_menu_kb
)
import database as db

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── FSM STATES ───────────────────────────────────────────────────────────────

class AddMovieState(StatesGroup):
    waiting_type = State()
    waiting_code = State()
    waiting_title = State()
    waiting_file = State()
    waiting_caption = State()


class DeleteMovieState(StatesGroup):
    waiting_code = State()


class GivePremiumState(StatesGroup):
    waiting_user_id = State()
    waiting_months = State()


class BroadcastState(StatesGroup):
    waiting_message = State()
    confirm = State()


# ─── ADMIN START ──────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Siz admin emassiz!")
    await message.answer(
        "👑 <b>Admin panel</b>\n\nXush kelibsiz, admin!",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )


# ─── STATISTIKA ───────────────────────────────────────────────────────────────

@router.message(F.text == "📊 Statistika")
async def stats_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    users = db.get_user_count()
    premiums = db.get_premium_count()
    movies = db.get_movie_count()
    await message.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"👤 Jami foydalanuvchilar: <b>{users}</b>\n"
        f"⭐ Premium foydalanuvchilar: <b>{premiums}</b>\n"
        f"🎬 Jami kinolar: <b>{movies}</b>",
        parse_mode="HTML"
    )


# ─── KINOLAR RO'YXATI ─────────────────────────────────────────────────────────

@router.message(F.text == "🎬 Kinolar ro'yxati")
async def movies_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    movies = db.get_all_movies(limit=30)
    if not movies:
        return await message.answer("🎬 Hozircha kino yo'q.")
    text = "🎬 <b>Kinolar ro'yxati:</b>\n\n"
    for m in movies:
        icon = "⭐" if m["is_premium"] else "🆓"
        text += f"{icon} <code>{m['code']}</code> — {m['title']}\n"
    await message.answer(text, parse_mode="HTML")


# ─── KINO QO'SHISH ────────────────────────────────────────────────────────────

@router.message(F.text == "🎬 Kino qo'shish")
async def add_movie_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AddMovieState.waiting_type)
    await message.answer(
        "🎬 <b>Kino turini tanlang:</b>",
        reply_markup=movie_type_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("movie_type:"), AddMovieState.waiting_type)
async def movie_type_chosen(call: CallbackQuery, state: FSMContext):
    movie_type = call.data.split(":")[1]
    await state.update_data(is_premium=1 if movie_type == "premium" else 0)
    await state.set_state(AddMovieState.waiting_code)
    type_text = "⭐ Premium" if movie_type == "premium" else "🆓 Oddiy"
    await call.message.edit_text(
        f"✅ Tur: <b>{type_text}</b>\n\n"
        "🔢 <b>Kino kodini kiriting</b> (masalan: <code>001</code>):",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )


@router.message(AddMovieState.waiting_code)
async def movie_code_entered(message: Message, state: FSMContext):
    code = message.text.strip()
    existing = db.get_movie(code)
    if existing:
        return await message.answer(
            f"❌ <b>{code}</b> kodi allaqachon mavjud! Boshqa kod kiriting:",
            parse_mode="HTML"
        )
    await state.update_data(code=code)
    await state.set_state(AddMovieState.waiting_title)
    await message.answer(
        "📝 <b>Kino nomini kiriting:</b>",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )


@router.message(AddMovieState.waiting_title)
async def movie_title_entered(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AddMovieState.waiting_file)
    await message.answer(
        "🎬 <b>Kino faylini (video) yuboring:</b>",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )


@router.message(AddMovieState.waiting_file, F.content_type == ContentType.VIDEO)
async def movie_file_received(message: Message, state: FSMContext):
    file_id = message.video.file_id
    await state.update_data(file_id=file_id)
    await state.set_state(AddMovieState.waiting_caption)
    await message.answer(
        "💬 <b>Kino tavsifi kiriting</b> (yoki /skip yuboring):",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )


@router.message(AddMovieState.waiting_caption)
async def movie_caption_entered(message: Message, state: FSMContext):
    caption = "" if message.text == "/skip" else message.text.strip()
    data = await state.get_data()

    success = db.add_movie(
        code=data["code"],
        title=data["title"],
        is_premium=data["is_premium"],
        file_id=data["file_id"],
        caption=caption
    )

    await state.clear()
    if success:
        type_text = "⭐ Premium" if data["is_premium"] else "🆓 Oddiy"
        await message.answer(
            f"✅ <b>Kino muvaffaqiyatli qo'shildi!</b>\n\n"
            f"📌 Kod: <code>{data['code']}</code>\n"
            f"🎬 Nom: {data['title']}\n"
            f"🏷 Tur: {type_text}",
            reply_markup=admin_menu_kb(),
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Xatolik yuz berdi!", reply_markup=admin_menu_kb())


# ─── KINO O'CHIRISH ───────────────────────────────────────────────────────────

@router.message(F.text == "🗑 Kino o'chirish")
async def delete_movie_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(DeleteMovieState.waiting_code)
    await message.answer(
        "🗑 <b>O'chiriluvchi kino kodini kiriting:</b>",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )


@router.message(DeleteMovieState.waiting_code)
async def delete_movie_code(message: Message, state: FSMContext):
    code = message.text.strip()
    success = db.delete_movie(code)
    await state.clear()
    if success:
        await message.answer(f"✅ <code>{code}</code> kodi o'chirildi!", reply_markup=admin_menu_kb(), parse_mode="HTML")
    else:
        await message.answer(f"❌ <code>{code}</code> topilmadi!", reply_markup=admin_menu_kb(), parse_mode="HTML")


# ─── PREMIUM BERISH ───────────────────────────────────────────────────────────

@router.message(F.text == "👑 Premium berish")
async def give_premium_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(GivePremiumState.waiting_user_id)
    await message.answer(
        "👑 <b>Premium berish</b>\n\nFoydalanuvchi ID sini kiriting:",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )


@router.message(GivePremiumState.waiting_user_id)
async def give_premium_user_id(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
        await state.update_data(target_user_id=uid)
        await state.set_state(GivePremiumState.waiting_months)
        await message.answer(
            "📅 Necha oylik premium berish? (1, 3, 6, 12):",
            reply_markup=cancel_kb()
        )
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")


@router.message(GivePremiumState.waiting_months)
async def give_premium_months(message: Message, state: FSMContext, bot: Bot):
    try:
        months = int(message.text.strip())
        data = await state.get_data()
        uid = data["target_user_id"]
        expires = db.add_premium(uid, months)
        await state.clear()
        await message.answer(
            f"✅ <b>Premium berildi!</b>\n"
            f"👤 ID: <code>{uid}</code>\n"
            f"📅 Muddat: {expires.strftime('%d.%m.%Y')}\n"
            f"⏳ {months} oy",
            reply_markup=admin_menu_kb(),
            parse_mode="HTML"
        )
        try:
            await bot.send_message(
                uid,
                f"🎉 <b>Tabriklaymiz!</b>\n\n"
                f"Sizga <b>{months} oylik Premium</b> faollashtirildi!\n"
                f"⏳ Muddati: {expires.strftime('%d.%m.%Y')} gacha\n\n"
                f"⭐ Endi barcha premium kinolarni tomosha qila olasiz!",
                parse_mode="HTML"
            )
        except Exception:
            pass
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")


# ─── TO'LOVLAR ────────────────────────────────────────────────────────────────

@router.message(F.text == "💳 To'lovlar")
async def show_payments(message: Message):
    if not is_admin(message.from_user.id):
        return
    payments = db.get_pending_payments()
    if not payments:
        return await message.answer("✅ Kutilayotgan to'lovlar yo'q.")
    for p in payments:
        await message.answer(
            f"💳 <b>To'lov so'rovi #{p['id']}</b>\n"
            f"👤 Foydalanuvchi ID: <code>{p['user_id']}</code>\n"
            f"📅 Sana: {p['created_at']}",
            reply_markup=payment_approve_kb(p["id"], p["user_id"]),
            parse_mode="HTML"
        )
        if p["receipt_file_id"]:
            await message.answer_photo(p["receipt_file_id"])


@router.callback_query(F.data.startswith("pay_approve:"))
async def payment_approved(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    _, req_id, user_id = call.data.split(":")
    req_id, user_id = int(req_id), int(user_id)

    expires = db.add_premium(user_id, 1)
    db.update_payment_status(req_id, "approved")

    await call.message.edit_reply_markup()
    await call.message.answer(f"✅ To'lov #{req_id} tasdiqlandi. Premium berildi.")

    try:
        await bot.send_message(
            user_id,
            f"🎉 <b>To'lovingiz tasdiqlandi!</b>\n\n"
            f"⭐ <b>1 oylik Premium</b> faollashtirildi!\n"
            f"⏳ Muddat: {expires.strftime('%d.%m.%Y')} gacha\n\n"
            f"Endi barcha premium kinolarni tomosha qiling! 🎬",
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("pay_reject:"))
async def payment_rejected(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    _, req_id, user_id = call.data.split(":")
    req_id, user_id = int(req_id), int(user_id)

    db.update_payment_status(req_id, "rejected")
    await call.message.edit_reply_markup()
    await call.message.answer(f"❌ To'lov #{req_id} rad etildi.")

    try:
        await bot.send_message(
            user_id,
            "❌ <b>To'lovingiz tasdiqlanmadi.</b>\n\n"
            "Iltimos, to'g'ri chek rasmini yuboring yoki admin bilan bog'laning.",
            parse_mode="HTML"
        )
    except Exception:
        pass


# ─── XABAR YUBORISH (BROADCAST) ───────────────────────────────────────────────

@router.message(F.text == "📨 Xabar yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(BroadcastState.waiting_message)
    await message.answer(
        "📨 <b>Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:</b>",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )


@router.message(BroadcastState.waiting_message)
async def broadcast_preview(message: Message, state: FSMContext):
    await state.update_data(broadcast_msg_id=message.message_id, chat_id=message.chat.id)
    await state.set_state(BroadcastState.confirm)
    await message.answer(
        "⬆️ Yuqoridagi xabar barcha foydalanuvchilarga yuboriladi.\n\nTasdiqlaysizmi?",
        reply_markup=broadcast_confirm_kb()
    )


@router.callback_query(F.data == "broadcast_confirm", BroadcastState.confirm)
async def broadcast_send(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()

    users = db.get_all_users()
    sent = 0
    failed = 0

    await call.message.edit_text(f"📨 Yuborilmoqda... ({len(users)} ta foydalanuvchi)")

    for uid in users:
        try:
            await bot.copy_message(uid, data["chat_id"], data["broadcast_msg_id"])
            sent += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
        except Exception:
            failed += 1

    await call.message.answer(
        f"✅ <b>Xabar yuborildi!</b>\n\n"
        f"✔️ Muvaffaqiyatli: {sent}\n"
        f"❌ Yuborilmadi: {failed}",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )


# ─── CANCEL ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel")
async def cancel_action(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Bekor qilindi.")
