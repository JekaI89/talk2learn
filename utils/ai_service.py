import os
import asyncio
import json
from openai import AsyncOpenAI
from gtts import gTTS

# Groq API
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# ── Языки ──────────────────────────────────────────────────────────
LANG_NAMES = {
    'ru': 'Russian',    'en': 'English',    'de': 'German',
    'fr': 'French',     'es': 'Spanish',    'it': 'Italian',
    'pt': 'Portuguese', 'zh': 'Chinese',    'ja': 'Japanese',
}

# Коды языков для Whisper
WHISPER_LANG = {
    'ru': 'ru', 'en': 'en', 'de': 'de', 'fr': 'fr',
    'es': 'es', 'it': 'it', 'pt': 'pt', 'zh': 'zh', 'ja': 'ja',
}

# Коды языков для gTTS
GTTS_LANG = {
    'ru': ('ru', 'com'), 'en': ('en', 'com'), 'de': ('de', 'de'),
    'fr': ('fr', 'fr'),  'es': ('es', 'es'),  'it': ('it', 'it'),
    'pt': ('pt', 'com'), 'zh': ('zh-CN', 'com'), 'ja': ('ja', 'co.jp'),
}

LEVEL_RULES = {
    "A1": "Use VERY simple, short sentences (10-20 words). Elementary vocabulary only. Always end with one simple question.",
    "A2": "Use simple grammar, 2-3 sentences. Basic conjugations. Ask a straightforward question at the end.",
    "B1": "Use natural intermediate vocabulary (conditionals, perfect tenses). 3-4 sentences. Ask open-ended questions.",
    "B2": "Speak naturally with idiomatic expressions, phrasal verbs, complex structures.",
    "C1": "Use sophisticated vocabulary, complex grammatical nuances. Native-level flow.",
    "C2": "Use sophisticated vocabulary, precise metaphors, complex nuances. Native-level flow.",
}

SITUATION_ROLES = {
    "shop":        "a friendly shop assistant in a supermarket",
    "restaurant":  "a polite waiter in a mid-range restaurant",
    "airport":     "a check-in agent at an international airport",
    "emergency":   "a calm emergency dispatcher",
    "hotel":       "a receptionist at a 4-star hotel",
    "doctor":      "a friendly general practitioner (GP) doctor",
}


# ── Конвертация ogg → wav ────────────────────────────────────────────
async def convert_ogg_to_wav(ogg_path: str, wav_path: str):
    try:
        import subprocess
        subprocess.run(
            ['ffmpeg', '-i', ogg_path, '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', wav_path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True
    except Exception as e:
        print(f"❌ ogg → wav: {e}")
        return False


# ── Транскрипция ─────────────────────────────────────────────────────
async def transcribe_voice(file_path: str, target_lang: str = 'en') -> str:
    wav_path = None
    try:
        if file_path.lower().endswith('.ogg'):
            wav_path = file_path.replace('.ogg', '.wav')
            await convert_ogg_to_wav(file_path, wav_path)
            file_path = wav_path

        whisper_lang = WHISPER_LANG.get(target_lang, target_lang)
        with open(file_path, "rb") as f:
            transcript = await client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                language=whisper_lang
            )
        return transcript.text.strip()
    except Exception as e:
        print(f"❌ Транскрипция: {e}")
        return ""
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)


# ── AI-ответ репетитора ───────────────────────────────────────────────
async def get_ai_response(
    user_text: str,
    user_level: str = "A1",
    situation: str = "",
    target_lang: str = "en",
    native_lang: str = "ru"
) -> str:
    target_name = LANG_NAMES.get(target_lang, "English")
    native_name  = LANG_NAMES.get(native_lang, "Russian")
    level_key    = (user_level or "A1").upper()
    level_rule   = LEVEL_RULES.get(level_key, LEVEL_RULES["A1"])

    if situation and situation in SITUATION_ROLES:
        role = SITUATION_ROLES[situation]
        system_prompt = (
            f"You are {role}. The learner's native language is {native_name} "
            f"and they are practising {target_name}. "
            f"Conduct the entire conversation ONLY in {target_name}. "
            f"Stay fully in character. Never break character or switch languages. "
            f"The learner's {target_name} level is {level_key}: {level_rule}"
        )
    else:
        system_prompt = (
            f"You are a friendly {target_name} language tutor. "
            f"The learner's native language is {native_name} and their {target_name} level is {level_key}. "
            f"Speak ONLY in {target_name}. {level_rule} "
            f"Always end with a question to keep the conversation going."
        )

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_text}
            ],
            temperature=0.7
        )
        reply = response.choices[0].message.content.strip()
        print(f"💬 AI [{target_name}/{level_key}][{situation or 'club'}]: {reply[:80]}")
        return reply
    except Exception as e:
        print(f"❌ get_ai_response: {e}")
        return "Sorry, I'm having trouble. Could you repeat that?"


# ── Озвучивание ───────────────────────────────────────────────────────
async def generate_voice(text: str, output_path: str, target_lang: str = 'en'):
    try:
        lang_code, tld = GTTS_LANG.get(target_lang, ('en', 'com'))
        def save():
            tts = gTTS(text=text, lang=lang_code, tld=tld)
            tts.save(output_path)
        await asyncio.to_thread(save)
    except Exception as e:
        print(f"❌ generate_voice: {e}")


# ── Перевод слова ─────────────────────────────────────────────────────
async def translate_word(
    word: str,
    context: str = "",
    native_lang: str = "ru",
    target_lang: str = "en"
) -> dict:
    """
    Переводит слово с target_lang на native_lang.
    Возвращает {translation, transcription, example} или translation="" при ошибке.
    """
    target_name = LANG_NAMES.get(target_lang, "English")
    native_name  = LANG_NAMES.get(native_lang, "Russian")

    system_prompt = (
        f"You are a precise {target_name}-{native_name} dictionary assistant. "
        f"Given a {target_name} word (and optionally the sentence it appeared in for context), "
        "respond with ONLY a valid JSON object and nothing else — no markdown, no code fences, "
        "no explanations. The JSON must have exactly these keys: "
        f'"translation" (short accurate {native_name} translation of the word in this context), '
        f'"transcription" (IPA transcription of the {target_name} word, e.g. /wɜːrd/), '
        f'"example" (one short simple {target_name} sentence using the word).'
    )
    user_content = f"Word: {word}"
    if context.strip():
        user_content += f"\nSentence: {context.strip()}"

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content}
            ],
            temperature=0.2
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        return {
            "translation":   str(data.get("translation", "")).strip(),
            "transcription": str(data.get("transcription", "")).strip(),
            "example":       str(data.get("example", "")).strip()
        }
    except Exception as e:
        print(f"❌ translate_word '{word}': {e}")
        return {"translation": "", "transcription": "", "example": ""}
