import os
import asyncio
import json
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


async def get_ai_response(user_text: str, user_level: str = "A1", situation: str = "") -> str:
    level_instructions = {
        "A1": "Use VERY simple, short sentences (10-20 words). Elementary vocabulary, present/past simple only. Always end with one simple question.",
        "A2": "Use simple grammar, slightly longer sentences (2-3 sentences). Basic conjugations and simple future tense. Ask a straightforward question at the end.",
        "B1": "Use natural English with intermediate vocabulary (conditionals, perfect tenses). Around 3-4 sentences. Ask open-ended questions.",
        "B2": "Speak naturally, use idiomatic expressions, phrasal verbs, complex structures. Keep it engaging and professional.",
        "C1": "Use sophisticated vocabulary, precise metaphors, complex grammatical nuances. Native-level flow.",
        "C2": "Use sophisticated vocabulary, precise metaphors, complex grammatical nuances. Native-level flow.",
    }

    SITUATIONS = {
        "shop": (
            "You are a friendly shop assistant in a British supermarket. "
            "The user is a customer. Stay fully in character: greet them, help find products, "
            "mention prices, offer alternatives, process payment. Never break character. "
            "Speak naturally as a shop assistant would."
        ),
        "restaurant": (
            "You are a polite waiter in a mid-range restaurant. "
            "The user is a customer. Stay in character: present the menu, take the order, "
            "answer questions about dishes, suggest specials, handle complaints gracefully. "
            "Never break character."
        ),
        "airport": (
            "You are a check-in agent at an international airport. "
            "The user is a passenger. Stay in character: check their documents, ask about baggage, "
            "assign seats, handle delays or issues, give gate information. Never break character."
        ),
        "emergency": (
            "You are a calm emergency dispatcher. "
            "The user is calling with an emergency situation. Stay in character: "
            "ask what happened, where they are, guide them step by step. "
            "Be reassuring but efficient. Never break character."
        ),
        "hotel": (
            "You are a receptionist at a 4-star hotel. "
            "The user is a guest checking in or asking for help. Stay in character: "
            "handle check-in, answer questions about facilities, resolve complaints. Never break character."
        ),
        "doctor": (
            "You are a friendly general practitioner (GP) doctor. "
            "The user is a patient at an appointment. Stay in character: "
            "ask about symptoms, give simple advice, suggest treatment. Never break character."
        ),
    }

    level_key = (user_level or "A1").upper()
    level_rule = level_instructions.get(level_key, level_instructions["A1"])

    if situation and situation in SITUATIONS:
        system_prompt = (
            f"{SITUATIONS[situation]}\n\n"
            f"The user's English level is {level_key}. Adapt your language accordingly: {level_rule}"
        )
    else:
        base = (
            "You are an English tutor for an AI Speaking Club. "
            "Always end with a question to keep the conversation going. "
        )
        system_prompt = base + f"The user's level is {level_key}. {level_rule}"

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_text}
            ],
            temperature=0.7
        )
        ai_reply = response.choices[0].message.content.strip()
        print(f"💬 AI [{level_key}][{situation or 'club'}]: {ai_reply[:80]}")
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


async def translate_word(word: str, context: str = "") -> dict:
    """
    Автоматический перевод слова на русский через Groq (для тапа по слову
    в уроке или в разговорном клубе). Возвращает перевод, IPA-транскрипцию
    и короткий пример использования. При ошибке/невалидном JSON от модели
    возвращает translation="" — вызывающий код должен это проверить и не
    сохранять пустой перевод в словарь.
    """
    system_prompt = (
        "You are a precise English-Russian dictionary assistant. "
        "Given an English word (and optionally the sentence it appeared in for context), "
        "respond with ONLY a valid JSON object and nothing else — no markdown, no code fences, "
        "no explanations. The JSON must have exactly these keys: "
        '"translation" (short accurate Russian translation of the word in this context), '
        '"transcription" (IPA transcription in slashes, e.g. /wɜːrd/), '
        '"example" (one short, simple English sentence using the word).'
    )
    user_content = f"Word: {word}"
    if context.strip():
        user_content += f"\nSentence: {context.strip()}"

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.2
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)

        return {
            "translation": str(data.get("translation", "")).strip(),
            "transcription": str(data.get("transcription", "")).strip(),
            "example": str(data.get("example", "")).strip()
        }
    except Exception as e:
        print(f"❌ Ошибка перевода слова '{word}': {e}")
        return {"translation": "", "transcription": "", "example": ""}