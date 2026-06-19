"""
Скрипт наполнения PostgreSQL: 10 уроков уровня A1
Запуск: python seed_a1.py

Скрипт идемпотентен — не создаёт дубликатов при повторном запуске.
DATABASE_URL берётся из переменной окружения (как на Render).
"""

import asyncio
import asyncpg
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

LESSONS = [
    (1, "Алфавит и произношение", """🔤 <b>The English Alphabet</b>

В английском языке 26 букв. Произносятся они иначе, чем пишутся.

<b>Гласные (Vowels):</b> A, E, I, O, U
<b>Согласные (Consonants):</b> все остальные 21 буква

<b>Полезные слова для запоминания:</b>
• A — Apple 🍎  • B — Book 📚  • C — Cat 🐱  • D — Dog 🐶  • E — Egg 🥚

<b>Буквы, которые читаются неожиданно:</b>
• W читается как «дабл-ю»
• Y читается как «вай»
• H читается как «эйч»

💡 <b>Совет:</b> Учите алфавит песенкой — это самый быстрый способ!""",
     [("How many letters are in the English alphabet?", "24", "26", "28", 2),
      ("Which of these is a vowel?", "B", "C", "E", 3),
      ("How do you say the letter 'W' in English?", "Ви", "Дабл-ю", "Ву", 2)]),

    (2, "Приветствия и прощания", """👋 <b>Greetings & Goodbyes</b>

<b>Как поздороваться:</b>
• Hello! — Привет! / Здравствуйте!
• Hi! — Привет! (неформально)
• Good morning! — Доброе утро! (до 12:00)
• Good afternoon! — Добрый день! (12:00–18:00)
• Good evening! — Добрый вечер! (после 18:00)

<b>Как спросить про дела:</b>
• How are you? — Как дела?
• I'm fine, thanks! — Я в порядке, спасибо!
• I'm great! — Отлично!

<b>Как попрощаться:</b>
• Goodbye! / Bye! — До свидания!
• See you later! — До встречи!
• Good night! — Спокойной ночи!

💡 <b>Совет:</b> «Good night» говорят только перед сном, не как приветствие вечером!""",
     [("What do you say in the morning?", "Good night!", "Good morning!", "Goodbye!", 2),
      ("How do you say 'Как дела?' in English?", "What is your name?", "Where are you?", "How are you?", 3),
      ("Which phrase means 'До встречи'?", "See you later!", "Good evening!", "Take care!", 1)]),

    (3, "Местоимения: I, You, He, She", """🙋 <b>Personal Pronouns</b>

<b>Личные местоимения:</b>
• I — Я          • You — Ты / Вы
• He — Он        • She — Она
• It — Оно       • We — Мы
• They — Они

<b>Примеры:</b>
• I am a student. — Я студент.
• She is my friend. — Она моя подруга.
• He is tall. — Он высокий.
• We are happy. — Мы счастливы.

<b>Важно!</b>
• «I» всегда пишется с большой буквы.
• «You» используется и для одного, и для группы.
• «It» — для животных и предметов.

💡 <b>Совет:</b> Замените имена в предложениях на местоимения — это лучшая тренировка!""",
     [("What is the pronoun for 'Она'?", "He", "It", "She", 3),
      ("Fill in: ___ am a student.", "He", "I", "They", 2),
      ("Which pronoun do we use for objects?", "She", "He", "It", 3)]),

    (4, "Глагол TO BE: am, is, are", """✅ <b>The verb TO BE</b>

«To be» — самый важный глагол. Означает «быть / являться».

<b>Формы глагола:</b>
• I <b>am</b>              • You <b>are</b>
• He / She / It <b>is</b>  • We / They <b>are</b>

<b>Утверждение:</b>
• I am a teacher. — Я учитель.
• She is beautiful. — Она красивая.
• We are friends. — Мы друзья.

<b>Отрицание (NOT):</b>
• I am not tired. — Я не устал.
• He is not here. — Его здесь нет.

<b>Вопрос (меняем порядок):</b>
• Are you happy? — Ты счастлив?
• Is she at home? — Она дома?

💡 <b>Совет:</b> Сокращения: I'm, you're, he's, she's, we're, they're""",
     [("Fill in: She ___ my sister.", "am", "are", "is", 3),
      ("Which is correct?", "I is happy.", "I am happy.", "I are happy.", 2),
      ("How do you make negative with TO BE?", "Add DO NOT", "Add NOT after to be", "Change word order", 2)]),

    (5, "Числа от 1 до 20", """🔢 <b>Numbers 1–20</b>

<b>1–10:</b>
1 — one, 2 — two, 3 — three, 4 — four, 5 — five
6 — six, 7 — seven, 8 — eight, 9 — nine, 10 — ten

<b>11–20:</b>
11 — eleven, 12 — twelve, 13 — thirteen, 14 — fourteen, 15 — fifteen
16 — sixteen, 17 — seventeen, 18 — eighteen, 19 — nineteen, 20 — twenty

<b>Обратите внимание:</b>
• 11 и 12 — особые слова
• 13–19: добавляем -teen
• После 20: twenty-one, twenty-two...

💡 <b>Совет:</b> Не путайте 13 (thirteen) и 30 (thirty)!""",
     [("How do you write the number 15?", "Fifty", "Fifteen", "Five", 2),
      ("What comes after 'eleven'?", "Thirteen", "Twenty", "Twelve", 3),
      ("How do you say '8' in English?", "Eighty", "Eight", "Eighteen", 2)]),

    (6, "Цвета", """🎨 <b>Colours</b>

• red — красный 🔴    • blue — синий 🔵
• yellow — жёлтый 🟡  • green — зелёный 🟢
• orange — оранжевый  • purple — фиолетовый
• pink — розовый      • white — белый ⚪
• black — чёрный ⚫   • grey — серый
• brown — коричневый

<b>Прилагательное стоит ПЕРЕД существительным:</b>
• a red car — красная машина
• a blue sky — голубое небо

<b>Вопрос о цвете:</b>
• What colour is it? — Какого это цвета?
• It is green. — Это зелёного цвета.

💡 <b>Совет:</b> Американцы пишут «color», британцы — «colour». Оба варианта верны!""",
     [("What colour is the sky usually?", "Red", "Blue", "Green", 2),
      ("How do you say 'красный' in English?", "Pink", "Orange", "Red", 3),
      ("Where does an adjective go in English?", "After the noun", "Before the noun", "At the end", 2)]),

    (7, "Дни недели и месяцы", """📅 <b>Days & Months</b>

<b>Дни недели:</b>
Monday — Понедельник  •  Tuesday — Вторник
Wednesday — Среда     •  Thursday — Четверг
Friday — Пятница      •  Saturday — Суббота  •  Sunday — Воскресенье

<b>Месяцы:</b>
January, February, March, April, May, June,
July, August, September, October, November, December

<b>Важно:</b>
• Дни и месяцы всегда с БОЛЬШОЙ буквы
• Weekdays — будние дни (Mon–Fri)
• Weekend — выходные (Sat–Sun)

<b>Примеры:</b>
• Today is Monday. — Сегодня понедельник.
• My birthday is in July. — Мой день рождения в июле.

💡 <b>Совет:</b> «on» + дни, «in» + месяцы!""",
     [("Which day comes after Tuesday?", "Monday", "Thursday", "Wednesday", 3),
      ("What is the 6th month of the year?", "July", "May", "June", 3),
      ("Which preposition do we use with days?", "in", "at", "on", 3)]),

    (8, "Семья", """👨‍👩‍👧‍👦 <b>Family Members</b>

<b>Ближайшая семья:</b>
• mother / mum — мама    • father / dad — папа
• sister — сестра         • brother — брат
• son — сын               • daughter — дочь
• parents — родители      • children — дети

<b>Расширенная семья:</b>
• grandmother / grandma — бабушка
• grandfather / grandpa — дедушка
• aunt — тётя    • uncle — дядя
• cousin — двоюродный брат/сестра
• wife — жена    • husband — муж

<b>Примеры:</b>
• I have one sister and two brothers.
• My mother is a doctor.

💡 <b>Совет:</b> «Cousin» — это и брат, и сестра. Контекст подскажет пол!""",
     [("What is 'мама' in English?", "Sister", "Mother", "Daughter", 2),
      ("How do you say 'дядя'?", "Uncle", "Cousin", "Brother", 1),
      ("Which word means both 'двоюродный брат' and 'двоюродная сестра'?", "Sibling", "Cousin", "Relative", 2)]),

    (9, "Простые вопросы: What, Where, Who", """❓ <b>Question Words</b>

• What? — Что? / Какой?
• Where? — Где? / Куда?
• Who? — Кто?
• When? — Когда?
• How? — Как?
• Why? — Почему?
• How much? — Сколько? (неисчисляемое)
• How many? — Сколько? (исчисляемое)

<b>Примеры:</b>
• What is your name? — Как вас зовут?
• Where are you from? — Откуда вы?
• Who is she? — Кто она?
• When is your birthday? — Когда ваш день рождения?

<b>Ответы:</b>
• My name is Anna.
• I am from Russia.

💡 <b>Совет:</b> Вопросительное слово всегда в НАЧАЛЕ вопроса!""",
     [("Which word asks about a place?", "Who", "What", "Where", 3),
      ("'What is your ___?' — what fits?", "From", "Name", "Are", 2),
      ("Which word means 'Кто?'", "When", "Who", "Why", 2)]),

    (10, "Present Simple: повседневные действия", """⏰ <b>Present Simple Tense</b>

Используется для регулярных действий и фактов.

<b>Структура:</b>
• I / You / We / They + глагол
• He / She / It + глагол + <b>-s</b>

<b>Примеры:</b>
• I wake up at 7 AM.
• She drinks coffee every morning.
• They play football on Sundays.

<b>Отрицание:</b>
• I don't eat meat.
• He doesn't like Mondays.

<b>Вопрос:</b>
• Do you speak English?
• Does she work here?

<b>Маркеры времени:</b>
every day, always, usually, often, sometimes, never

💡 <b>Совет:</b> He/She/It → добавляй -s: work → works, play → plays!""",
     [("Fill in: She ___ coffee every day.", "drink", "drinks", "drinking", 2),
      ("Which is the correct negative form?", "I not like it.", "I doesn't like it.", "I don't like it.", 3),
      ("Which word is a time marker for Present Simple?", "Yesterday", "Now", "Always", 3)]),
]


async def seed():
    print(f"🔗 Подключение к БД...")
    conn = await asyncpg.connect(DATABASE_URL)

    added_lessons = 0
    added_questions = 0

    for order_num, title, lesson_text, questions in LESSONS:
        existing = await conn.fetchrow(
            "SELECT id FROM lessons WHERE title = $1 AND level = 'A1'", title
        )

        if existing:
            lesson_id = existing["id"]
            print(f"  ⏭️  Уже существует (id={lesson_id}): {title}")
        else:
            lesson_id = await conn.fetchval("""
                INSERT INTO lessons (level, title, lesson_text, content_type, order_num, is_active)
                VALUES ('A1', $1, $2, 'lesson', $3, TRUE)
                RETURNING id
            """, title, lesson_text, order_num)
            print(f"  ✅ Добавлен #{order_num} (id={lesson_id}): {title}")
            added_lessons += 1

        q_count = await conn.fetchval(
            "SELECT COUNT(*) FROM questions WHERE lesson_id = $1", lesson_id
        )

        if q_count == 0:
            for i, (q_text, opt1, opt2, opt3, correct) in enumerate(questions, 1):
                await conn.execute("""
                    INSERT INTO questions
                    (lesson_id, level, task_type, question_text, option_1, option_2, option_3, correct_option, order_num)
                    VALUES ($1, 'A1', 'multiple_choice', $2, $3, $4, $5, $6, $7)
                """, lesson_id, q_text, opt1, opt2, opt3, correct, i)
            print(f"     ➕ Добавлено {len(questions)} вопроса")
            added_questions += len(questions)
        else:
            print(f"     ⏭️  Вопросы уже есть ({q_count} шт.)")

    await conn.close()
    print(f"\n🎉 Готово! Уроков: {added_lessons}, вопросов: {added_questions}")


if __name__ == "__main__":
    asyncio.run(seed())
