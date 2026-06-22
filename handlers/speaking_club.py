from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import os
from pathlib import Path

from utils.ai_service import transcribe_voice, get_ai_response, generate_voice
from database.db import check_is_admin, get_user_level

router = Router()

# Используем /data (persistent disk Render) в продакшене, temp/ локально
TEMP_DIR = Path(os.environ.get("TEMP_DIR", "/data" if os.path.exists("/data") else "temp"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class ClubStates(StatesGroup):
    in_conversation = State()


@router.callback_query(F.data == "enter_speaking_club")
async def enter_club(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ClubStates.in_conversation)
    await callback.answer()

    exit_kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="◀️ Покинуть клуб")]],
        resize_keyboard=True
    )

    await callback.message.answer(
        "👋 <b>Welcome to the Speaking Club!</b> 🇬🇧\n\n"
        "Теперь ты можешь общаться со мной голосом или текстом.\n\n"
        "Я буду исправлять ошибки и отвечать голосом.\n\n"
        "Давай начнём разговор! Как у тебя сегодня настроение?",
        reply_markup=exit_kb,
        parse_mode="HTML"
    )


@router.message(ClubStates.in_conversation, F.text == "◀️ Покинуть клуб")
async def exit_club(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "✅ Вы вышли из разговорного клуба.\n"
        "Чтобы вернуться в главное меню — нажми /start",
        reply_markup=types.ReplyKeyboardRemove()
    )


@router.message(ClubStates.in_conversation, F.text)
async def club_text_message(message: types.Message):
    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        # Получаем уровень пользователя из БД
        user_level = await get_user_level(message.from_user.id)

        ai_text = await get_ai_response(message.text, user_level=user_level)
        voice_path = str(TEMP_DIR / f"ai_voice_{message.from_user.id}.mp3")

        await generate_voice(ai_text, voice_path)

        await message.answer(ai_text)
        if os.path.exists(voice_path):
            await message.answer_voice(types.FSInputFile(voice_path))
            os.remove(voice_path)

    except Exception as e:
        print(f"[Speaking Club Text Error]: {e}")
        await message.answer("😔 Что-то пошло не так. Попробуй ещё раз.")


@router.message(ClubStates.in_conversation, F.voice)
async def club_voice_message(message: types.Message):
    await message.bot.send_chat_action(message.chat.id, "record_voice")

    user_id = message.from_user.id
    input_ogg = str(TEMP_DIR / f"user_{user_id}.ogg")
    output_mp3 = str(TEMP_DIR / f"ai_{user_id}.mp3")

    try:

        voice_file = await message.bot.get_file(message.voice.file_id)
        await message.bot.download_file(voice_file.file_path, input_ogg)

        user_text = await transcribe_voice(input_ogg)

        # Получаем уровень пользователя из БД
        user_level = await get_user_level(user_id)

        ai_text = await get_ai_response(user_text, user_level=user_level)

        await generate_voice(ai_text, output_mp3)

        await message.reply(
            f"🗣 <b>Ты сказал:</b> {user_text}\n\n"
            f"🤖 <b>Преподаватель:</b> {ai_text}",
            parse_mode="HTML"
        )
        await message.answer_voice(types.FSInputFile(output_mp3))

    except Exception as e:
        print(f"[Speaking Club Voice Error]: {e}")
        await message.answer("😔 Не удалось обработать голосовое сообщение. Попробуй ещё раз.")
    finally:
        for file in [input_ogg, output_mp3]:
            if os.path.exists(file):
                os.remove(file)
