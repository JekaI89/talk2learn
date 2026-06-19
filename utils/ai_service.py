import os
import asyncio
from openai import AsyncOpenAI
from gtts import gTTS
from pathlib import Path

# Groq API
GROQ_API_KEY = "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"

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

async def convert_ogg_to_wav(ogg_path: str, wav_path: str):
    """Конвертация .ogg (из Telegram) в .wav для Whisper"""
    try:
        import subprocess
        subprocess.run([
            'ffmpeg', '-i', ogg_path, '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', wav_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"❌ Ошибка конвертации ogg → wav: {e}")
        return False


async def transcribe_voice(file_path: str) -> str:
    """Распознавание речи (поддержка .ogg и .wav)"""
    original_path = file_path
    wav_path = None

    try:
        if file_path.lower().endswith('.ogg'):
            wav_path = file_path.replace('.ogg', '.wav')
            await convert_ogg_to_wav(file_path, wav_path)
            file_path = wav_path

        with open(file_path, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                language="en"
            )
        return transcript.text.strip()

    except Exception as e:
        print(f"❌ Ошибка транскрипции: {e}")
        return "Sorry, I couldn't understand your voice message."
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)


async def get_ai_response(user_text: str, user_level: str = "A1") -> str:
    # Ограничения и правила для каждого уровня
    level_instructions = {
        "A1": (
            "You are an English tutor for an AI Speaking Club. The user's level is A1 (Beginner). "
            "Respond in VERY simple, short sentences (10-20 words). Use elementary vocabulary, "
            "present simple/past simple, and avoid idioms. Do not write just 3 words—give a complete, "
            "simple response. Always end with one very simple, clear question to keep the conversation going."
        ),
        "A2": (
            "You are an English tutor. The user's level is A2 (Elementary). "
            "Use simple grammar but slightly longer sentences (2-3 sentences). You can use basic conjugations "
            "and simple future tense. Keep your vocabulary clear and easy, and ask a straightforward question at the end."
        ),
        "B1": (
            "You are an English tutor. The user's level is B1 (Intermediate). "
            "Use natural English with intermediate vocabulary and standard grammar structures (conditionals, perfect tenses). "
            "Your response should be around 3-4 sentences. Engage in a meaningful dialogue and ask open-ended questions."
        ),
        "B2": (
            "You are an English tutor. The user's level is B2 (Upper-Intermediate). "
            "Speak naturally, use idiomatic expressions, phrasal verbs, and complex sentence structures. "
            "Challenge the user slightly, express abstract ideas, and keep the conversation professional and engaging."
        ),
        "C1": (
            "You are an English tutor. The user's level is C1/C2 (Advanced). "
            "Use sophisticated, advanced vocabulary, precise metaphors, and complex grammatical nuances. "
            "Discuss deep topics, debate if necessary, and use native-level speed and flow in your thoughts."
        )
    }

    # На всякий случай приводим к верхнему регистру (A1, B2 и т.д.)
    level_key = user_level.upper() if user_level else "A1"
    system_prompt = level_instructions.get(level_key, level_instructions["A1"])

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]
        
        # Делаем реальный запрос к Groq API
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Быстрая и умная модель
            messages=messages,
            temperature=0.7
        )
        
        ai_reply = response.choices[0].message.content.strip()
        print(f"💬 ИИ ответил для уровня {level_key}: {ai_reply}")
        return ai_reply
        
    except Exception as e:
        print(f"❌ Ошибка в get_ai_response: {e}")
        return "I'm sorry, I'm having trouble understanding right now. Could you repeat that?"


async def generate_voice(text: str, output_path: str):
    """Озвучивание через gTTS"""
    try:
        def save_tts():
            tts = gTTS(text=text, lang='en', tld='com')  # американский акцент
            tts.save(output_path)
        
        await asyncio.to_thread(save_tts)
    except Exception as e:
        print(f"❌ Ошибка генерации аудио: {e}")