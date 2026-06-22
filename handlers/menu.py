from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os

from database.db import check_is_admin

router = Router()

WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://talk2learn-4gmx.onrender.com")
ADMIN_IDS = [377424247, 696767499]


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    base_url = WEBAPP_URL.rstrip('/')

    builder.add(types.InlineKeyboardButton(
        text="🚀 Открыть Академию",
        web_app=types.WebAppInfo(url=f"{base_url}/")
    ))
    
    builder.add(types.InlineKeyboardButton(
        text="🎙 Разговорный клуб",
        callback_data="enter_speaking_club"
    ))

    builder.adjust(1)

    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        "Добро пожаловать в <b>Talk2Learn</b> 🇬🇧\n\n"
        "Выбери, чем хочешь заняться:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Вход в админ-панель"""
    user_id = message.from_user.id
    
    # Проверка через ADMIN_IDS + базу
    is_admin = user_id in ADMIN_IDS or await check_is_admin(user_id)
    
    if not is_admin:
        await message.answer("⚠️ У вас нет прав администратора.")
        return

    builder = InlineKeyboardBuilder()
    admin_url = f"{WEBAPP_URL.rstrip('/')}/admin"

    builder.add(types.InlineKeyboardButton(
        text="⚙️ Открыть Админ-панель",
        web_app=types.WebAppInfo(url=admin_url)
    ))

    await message.answer(
        "🔐 <b>Админ-панель активирована</b>\n\n"
        "Теперь вы можете управлять пользователями, уроками и статистикой.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )