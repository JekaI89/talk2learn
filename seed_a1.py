"""
Скрипт наполнения базы данных: 10 уроков уровня A1
Каждый урок = теория (content_type='lesson') + 3 вопроса практики (task_type='multiple_choice')

Запуск:
    python seed_a1.py

Скрипт идемпотентен: проверяет наличие урока по названию перед добавлением,
повторный запуск не создаст дубликатов.
"""

import asyncio
import aiosqlite

DB_PATH = "bot_database.db"

# ============================================================
# ДАННЫЕ: 10 уроков A1
# Структура: (order_num, title, lesson_text, questions)
# questions: список (question_text, opt1, opt2, opt3, correct_option)
# ============================================================

LESSONS = [
    (
        1,
        "Алфавит и произношение",
        """🔤 <b>The English Alphabet</b>

В английском языке 26 букв. Произносятся они иначе, чем пишутся.

<b>Гласные (Vowels):</b> A, E, I, O, U
<b>Согласные (Consonants):</b> все остальные 21 буква

<b>Полезные слова для запоминания букв:</b>
• A — Apple 🍎
• B — Book 📚
• C — Cat 🐱
• D — Dog 🐶
• E — Egg 🥚
• F — Fish 🐟

<b>Буквы, которые читаются неожиданно:</b>
• W читается как «дабл-ю»
• Y читается как «вай»
• G читается как «джи»
• H читается как «эйч»

💡 <b>Совет:</b> Учите алфавит песенкой — это самый быстрый способ!""",
        [
            ("How many letters are in the English alphabet?", "24", "26", "28", 2),
            ("Which of these is a vowel?", "B", "C", "E", 3),
            ("How do you say the letter 'W' in English?", "Ви", "Дабл-ю", "Ву", 2),
        ]
    ),
    (
        2,
        "Приветствия и прощания",
        """👋 <b>Greetings & Goodbyes</b>

<b>Как поздороваться:</b>
• Hello! — Привет! / Здравствуйте!
• Hi! — Привет! (неформально)
• Good morning! — Доброе утро! (до 12:00)
• Good afternoon! — Добрый день! (12:00–18:00)
• Good evening! — Добрый вечер! (после 18:00)

<b>Как ответить:</b>
• How are you? — Как дела?
• I'm fine, thanks! — Я в порядке, спасибо!
• I'm great! — Отлично!
• Not bad. — Неплохо.

<b>Как попрощаться:</b>
• Goodbye! / Bye! — До свидания! / Пока!
• See you later! — До встречи!
• Good night! — Спокойной ночи!
• Take care! — Береги себя!

💡 <b>Совет:</b> «Good night» говорят только перед сном, не как приветствие вечером!""",
        [
            ("What do you say in the morning?", "Good night!", "Good morning!", "Goodbye!", 2),
            ("How do you say 'Как дела?' in English?", "What is your name?", "Where are you?", "How are you?", 3),
            ("Which phrase means 'До встречи'?", "See you later!", "Good evening!", "Take care!", 1),
        ]
    ),
    (
        3,
        "Местоимения: I, You, He, She",
        """🙋 <b>Personal Pronouns</b>

Местоимения заменяют имена людей и предметов.

<b>Личные местоимения:</b>
• I — Я
• You — Ты / Вы
• He — Он
• She — Она
• It — Оно (для предметов и животных)
• We — Мы
• They — Они

<b>Примеры:</b>
• I am a student. — Я студент.
• She is my friend. — Она моя подруга.
• He is tall. — Он высокий.
• We are happy. — Мы счастливы.
• They are from Russia. — Они из России.

<b>Важно!</b>
• «I» всегда пишется с большой буквы.
• «You» используется и для одного человека, и для группы.
• «It» — для животных, когда пол неважен, и для предметов.

💡 <b>Совет:</b> Замените имена в предложениях на местоимения — это лучшая тренировка!""",
        [
            ("What is the pronoun for 'Она'?", "He", "It", "She", 3),
            ("Fill in: ___ am a student.", "He", "I", "They", 2),
            ("Which pronoun do we use for objects?", "She", "He", "It", 3),
        ]
    ),
    (
        4,
        "Глагол TO BE: am, is, are",
        """✅ <b>The verb TO BE</b>

«To be» — самый важный глагол в английском. Означает «быть / являться».

<b>Формы глагола:</b>
• I <b>am</b> — Я есть / Я являюсь
• You <b>are</b> — Ты есть
• He / She / It <b>is</b> — Он/Она/Оно есть
• We / They <b>are</b> — Мы/Они есть

<b>Утвердительные предложения:</b>
• I am a teacher. — Я учитель.
• She is beautiful. — Она красивая.
• We are friends. — Мы друзья.

<b>Отрицательные (добавляем NOT):</b>
• I am not tired. — Я не устал.
• He is not here. — Его здесь нет.
• They are not ready. — Они не готовы.

<b>Вопросительные (меняем порядок):</b>
• Are you happy? — Ты счастлив?
• Is she at home? — Она дома?
• Am I right? — Я прав?

💡 <b>Совет:</b> Сокращения: I'm, you're, he's, she's, it's, we're, they're""",
        [
            ("Fill in: She ___ my sister.", "am", "are", "is", 3),
            ("Which is correct?", "I is happy.", "I am happy.", "I are happy.", 2),
            ("How do you make a negative with TO BE?", "Add DO NOT", "Add NOT after to be", "Change word order", 2),
        ]
    ),
    (
        5,
        "Числа от 1 до 20",
        """🔢 <b>Numbers 1–20</b>

<b>1–10:</b>
1 — one, 2 — two, 3 — three, 4 — four, 5 — five
6 — six, 7 — seven, 8 — eight, 9 — nine, 10 — ten

<b>11–20:</b>
11 — eleven, 12 — twelve, 13 — thirteen, 14 — fourteen, 15 — fifteen
16 — sixteen, 17 — seventeen, 18 — eighteen, 19 — nineteen, 20 — twenty

<b>Обратите внимание:</b>
• 11 и 12 — особые слова, не по правилу
• 13–19: добавляем -teen (thirteen, fourteen...)
• После 20 всё просто: twenty-one, twenty-two...

<b>Числа в повседневной жизни:</b>
• I have two cats. — У меня два кота.
• She is fifteen years old. — Ей пятнадцать лет.
• There are ten students. — Там десять студентов.

💡 <b>Совет:</b> Не путайте 13 (thirteen) и 30 (thirty) — разница в ударении!""",
        [
            ("How do you write the number 15?", "Fifty", "Fifteen", "Five", 2),
            ("What comes after 'eleven'?", "Thirteen", "Twenty", "Twelve", 3),
            ("How do you say '8' in English?", "Eighty", "Eight", "Eighteen", 2),
        ]
    ),
    (
        6,
        "Цвета",
        """🎨 <b>Colours</b>

<b>Основные цвета:</b>
• red — красный 🔴
• blue — синий 🔵
• yellow — жёлтый 🟡
• green — зелёный 🟢
• orange — оранжевый 🟠
• purple — фиолетовый 🟣
• pink — розовый 🩷
• white — белый ⚪
• black — чёрный ⚫
• grey — серый 🩶
• brown — коричневый 🟤

<b>Как использовать в предложениях:</b>
В английском прилагательное стоит ПЕРЕД существительным:
• a red car — красная машина
• a blue sky — голубое небо
• a black cat — чёрная кошка

<b>Вопрос о цвете:</b>
• What colour is it? — Какого это цвета?
• It is green. — Это зелёного цвета.

💡 <b>Совет:</b> В американском английском пишут «color», в британском — «colour». Оба варианта верны!""",
        [
            ("What colour is the sky usually?", "Red", "Blue", "Green", 2),
            ("How do you say 'красный' in English?", "Pink", "Orange", "Red", 3),
            ("Where does an adjective go in English?", "After the noun", "Before the noun", "At the end", 2),
        ]
    ),
    (
        7,
        "Дни недели и месяцы",
        """📅 <b>Days & Months</b>

<b>Дни недели (Days of the week):</b>
• Monday — Понедельник
• Tuesday — Вторник
• Wednesday — Среда
• Thursday — Четверг
• Friday — Пятница
• Saturday — Суббота
• Sunday — Воскресенье

<b>Месяцы (Months):</b>
January, February, March, April, May, June,
July, August, September, October, November, December

<b>Важные правила:</b>
• Дни и месяцы всегда пишутся с БОЛЬШОЙ буквы
• Неделя в англоязычных странах часто начинается с воскресенья
• Weekdays — будние дни (Mon–Fri)
• Weekend — выходные (Sat–Sun)

<b>Примеры:</b>
• Today is Monday. — Сегодня понедельник.
• My birthday is in July. — Мой день рождения в июле.
• See you on Friday! — До встречи в пятницу!

💡 <b>Совет:</b> Запомните: «on» используется с днями, «in» — с месяцами!""",
        [
            ("Which day comes after Tuesday?", "Monday", "Thursday", "Wednesday", 3),
            ("What is the 6th month of the year?", "July", "May", "June", 3),
            ("Which preposition do we use with days? 'on ___ Monday'", "in", "at", "on", 3),
        ]
    ),
    (
        8,
        "Семья: members of the family",
        """👨‍👩‍👧‍👦 <b>Family Members</b>

<b>Ближайшая семья (Immediate family):</b>
• mother / mum — мама
• father / dad — папа
• sister — сестра
• brother — брат
• son — сын
• daughter — дочь
• parents — родители
• children — дети

<b>Расширенная семья (Extended family):</b>
• grandmother / grandma — бабушка
• grandfather / grandpa — дедушка
• aunt — тётя
• uncle — дядя
• cousin — двоюродный брат/сестра
• wife — жена
• husband — муж

<b>Примеры предложений:</b>
• I have one sister and two brothers. — У меня одна сестра и два брата.
• My mother is a doctor. — Моя мама — врач.
• Her grandparents live in London. — Её бабушка и дедушка живут в Лондоне.

💡 <b>Совет:</b> «Cousin» в английском — это и брат, и сестра. Контекст подскажет пол!""",
        [
            ("What is 'мама' in English?", "Sister", "Mother", "Daughter", 2),
            ("How do you say 'дядя'?", "Uncle", "Cousin", "Brother", 1),
            ("Which word means both 'двоюродный брат' and 'двоюродная сестра'?", "Sibling", "Cousin", "Relative", 2),
        ]
    ),
    (
        9,
        "Простые вопросы: What, Where, Who",
        """❓ <b>Question Words</b>

<b>Вопросительные слова:</b>
• What? — Что? / Какой?
• Where? — Где? / Куда?
• Who? — Кто?
• When? — Когда?
• How? — Как?
• Why? — Почему?
• How much? — Сколько? (для неисчисляемого)
• How many? — Сколько? (для исчисляемого)

<b>Примеры вопросов:</b>
• What is your name? — Как вас зовут?
• Where are you from? — Откуда вы?
• Who is she? — Кто она?
• When is your birthday? — Когда ваш день рождения?
• How are you? — Как дела?

<b>Ответы:</b>
• My name is Anna. — Меня зовут Анна.
• I am from Russia. — Я из России.
• She is my teacher. — Она моя учительница.

💡 <b>Совет:</b> Вопросительное слово всегда стоит в НАЧАЛЕ вопроса в английском!""",
        [
            ("Which word asks about a place?", "Who", "What", "Where", 3),
            ("'What is your ___?' — what fits?", "From", "Name", "Are", 2),
            ("Which word means 'Кто?'", "When", "Who", "Why", 2),
        ]
    ),
    (
        10,
        "Present Simple: повседневные действия",
        """⏰ <b>Present Simple Tense</b>

Present Simple используется для регулярных, повседневных действий и фактов.

<b>Структура утверждения:</b>
• I / You / We / They + глагол (основная форма)
• He / She / It + глагол + <b>-s</b>

<b>Примеры:</b>
• I wake up at 7 AM. — Я просыпаюсь в 7 утра.
• She drinks coffee every morning. — Она пьёт кофе каждое утро.
• They play football on Sundays. — Они играют в футбол по воскресеньям.

<b>Отрицание (don't / doesn't):</b>
• I don't eat meat. — Я не ем мясо.
• He doesn't like Mondays. — Он не любит понедельники.

<b>Вопрос (Do / Does):</b>
• Do you speak English? — Ты говоришь по-английски?
• Does she work here? — Она здесь работает?

<b>Маркеры времени:</b>
every day, always, usually, often, sometimes, never

💡 <b>Совет:</b> Если подлежащее he/she/it — добавляй -s к глаголу: work → works, play → plays!""",
        [
            ("Fill in: She ___ coffee every day. (drink)", "drink", "drinks", "drinking", 2),
            ("Which is the correct negative form?", "I not like it.", "I doesn't like it.", "I don't like it.", 3),
            ("Which word is a time marker for Present Simple?", "Yesterday", "Now", "Always", 3),
        ]
    ),
]


async def seed():
    async with aiosqlite.connect(DB_PATH) as db:
        added_lessons = 0
        added_questions = 0

        for order_num, title, lesson_text, questions in LESSONS:
            # Проверяем — не существует ли уже урок с таким названием
            async with db.execute(
                "SELECT id FROM lessons WHERE title = ? AND level = 'A1'", (title,)
            ) as c:
                existing = await c.fetchone()

            if existing:
                lesson_id = existing[0]
                print(f"  ⏭️  Урок уже существует (id={lesson_id}): {title}")
            else:
                await db.execute("""
                    INSERT INTO lessons (level, title, lesson_text, content_type, order_num, is_active)
                    VALUES ('A1', ?, ?, 'lesson', ?, 1)
                """, (title, lesson_text, order_num))
                await db.commit()

                async with db.execute("SELECT last_insert_rowid()") as c:
                    lesson_id = (await c.fetchone())[0]

                print(f"  ✅ Добавлен урок #{order_num} (id={lesson_id}): {title}")
                added_lessons += 1

            # Добавляем вопросы только если их ещё нет для этого урока
            async with db.execute(
                "SELECT COUNT(*) FROM questions WHERE lesson_id = ?", (lesson_id,)
            ) as c:
                q_count = (await c.fetchone())[0]

            if q_count == 0:
                for i, (q_text, opt1, opt2, opt3, correct) in enumerate(questions, 1):
                    await db.execute("""
                        INSERT INTO questions
                        (lesson_id, level, task_type, question_text, option_1, option_2, option_3, correct_option, order_num)
                        VALUES ('A1' , 'A1', 'multiple_choice', ?, ?, ?, ?, ?, ?)
                    """, (q_text, opt1, opt2, opt3, correct, i))
                await db.commit()
                print(f"     ➕ Добавлено {len(questions)} вопроса к уроку")
                added_questions += len(questions)
            else:
                print(f"     ⏭️  Вопросы уже есть ({q_count} шт.), пропускаем")

        print(f"\n🎉 Готово! Добавлено уроков: {added_lessons}, вопросов: {added_questions}")


if __name__ == "__main__":
    asyncio.run(seed())
