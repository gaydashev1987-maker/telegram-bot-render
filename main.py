import os
import sqlite3
import random
import logging
import time
import requests
from flask import Flask, jsonify
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Conflict, NetworkError

# ===== ВЕБ-СЕРВЕР =====
app = Flask('')

@app.route('/')
def home():
    return "🤖 Бот активен и работает! Время: " + time.strftime("%Y-%m-%d %H:%M:%S")

@app.route('/health')
def health():
    return jsonify({"status": "OK", "timestamp": time.time()}), 200

@app.route('/ping')
def ping():
    return "pong", 200

@app.route('/status')
def status():
    return jsonify({
        "status": "active",
        "bot": "running", 
        "self_ping": "enabled"
    })

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    try:
        server = Thread(target=run_flask)
        server.daemon = True
        server.start()
        print("🌐 Веб-сервер запущен на порту 8080")
    except Exception as e:
        print(f"❌ Ошибка запуска веб-сервера: {e}")

# ===== САМОПИНГ =====
def self_ping():
    """Периодически пингует сам себя для поддержания активности"""
    ping_url = "https://bb94efbc-5fdd-4b67-bd64-bb7f2ec7c046-00-3tr1nljwi6ead.sisko.replit.dev/ping"

    while True:
        try:
            response = requests.get(ping_url, timeout=10)
            if response.status_code == 200:
                print(f"✅ Самопинг успешен: {time.strftime('%H:%M:%S')}")
            else:
                print(f"⚠️ Самопинг: статус {response.status_code}")
        except Exception as e:
            print(f"❌ Ошибка самопинга: {e}")

        # Ждем 4 минуты между запросами
        time.sleep(240)

def start_self_ping():
    """Запускает самопинг в отдельном потоке"""
    ping_thread = Thread(target=self_ping)
    ping_thread.daemon = True
    ping_thread.start()
    print("🔁 Самопинг запущен (каждые 4 минуты)")

# ===== КОНФИГУРАЦИЯ БОТА =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Уменьшаем логирование
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)

print("🚀 Бот запускается...")

BOT_TOKEN = '8362961253:AAGdU6IjPqAWsCGdTJAF3hlo3c-E5DvhpUY'
ADMIN_ID = 8526339637
CHANNEL_ID = -1003371879030
CHANNEL_LINK = "https://t.me/+zWVuu6USvyo3NjA6"

# База данных
def init_db():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            captcha_passed INTEGER DEFAULT 0,
            join_date TEXT
        )
    ''')

    try:
        cursor.execute("SELECT join_date FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE users ADD COLUMN join_date TEXT")

    conn.commit()
    return conn, cursor

conn, cursor = init_db()

# Генерация каптчи
def generate_captcha():
    a = random.randint(1, 10)
    b = random.randint(1, 10)
    operation = random.choice(['+', '-'])

    if operation == '+':
        answer = a + b
        question = f"{a} + {b} = ?"
    else:
        answer = a - b
        question = f"{a} - {b} = ?"

    return question, str(answer)

active_captchas = {}

# ===== ОБРАБОТЧИКИ БОТА =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        user_id = user.id

        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) 
            VALUES (?, ?, ?, datetime("now"))
        ''', (user.id, user.username, user.first_name))
        conn.commit()

        captcha_text, answer = generate_captcha()
        active_captchas[user_id] = answer

        await update.message.reply_text(
            f"👋 Привет {user.first_name}! Для доступа сначала решите пример:\n\n"
            f"🔢 **{captcha_text}**\n\n"
            f"Отправьте ответ числом:"
        )

    except Exception as e:
        print(f"❌ Ошибка в команде /start: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте снова.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id

        if user_id in active_captchas:
            await verify_captcha(update, context)
        else:
            await update.message.reply_text("❌ Сначала запустите бота командой /start")

    except Exception as e:
        print(f"❌ Ошибка в обработке сообщения: {e}")

async def verify_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user_text = update.message.text.strip()

        correct_answer = active_captchas.get(user_id)
        if not correct_answer:
            await update.message.reply_text("❌ Сначала запроси каптчу: /start")
            return

        if user_text == correct_answer:
            print(f"✅ Каптча пройдена для пользователя {user_id}")
            del active_captchas[user_id]

            cursor.execute('UPDATE users SET captcha_passed = 1 WHERE user_id = ?', (user_id,))
            conn.commit()

            await check_subscription(update, context)
        else:
            await update.message.reply_text("❌ Неверный ответ! Попробуйте снова: /start")
            if user_id in active_captchas:
                del active_captchas[user_id]

    except Exception as e:
        print(f"❌ Ошибка при проверке каптчи: {e}")
        await update.message.reply_text("❌ Ошибка при проверке. Попробуйте снова: /start")

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user = update.effective_user

        chat_member = await context.bot.get_chat_member(CHANNEL_ID, user_id)

        if chat_member.status in ['member', 'administrator', 'creator']:
            await update.message.reply_text(
                "🎉 **Поздравляем! Доступ открыт!**\n\n"
                "Вы успешно прошли проверку и уже подписаны на канал!"
            )

            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"🆕 Новый пользователь!\n\n"
                    f"👤 Имя: {user.first_name}\n"
                    f"📧 @{user.username or 'нет'}\n"
                    f"🆔 ID: {user.id}"
                )
            except Exception as e:
                print(f"⚠️ Не удалось уведомить администратора: {e}")

        else:
            keyboard = [
                [InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)],
                [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "✅ Каптча пройдена!\n\n"
                "📋 Теперь подпишитесь на наш канал чтобы получить доступ:",
                reply_markup=reply_markup
            )

    except Exception as e:
        print(f"❌ Ошибка проверки подписки: {e}")
        keyboard = [
            [InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "✅ Каптча пройдена!\n\n"
            "📋 Теперь подпишитесь на наш канал чтобы получить доступ:",
            reply_markup=reply_markup
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id

        if query.data == "check_sub":
            chat_member = await context.bot.get_chat_member(CHANNEL_ID, user_id)

            if chat_member.status in ['member', 'administrator', 'creator']:
                await query.edit_message_text(
                    "🎉 **Поздравляем! Доступ открыт!**\n\n"
                    "Теперь вы можете пользоваться всеми возможностями бота!"
                )

                try:
                    user = query.from_user
                    await context.bot.send_message(
                        ADMIN_ID,
                        f"🆕 Новый пользователь!\n\n"
                        f"👤 Имя: {user.first_name}\n"
                        f"📧 @{user.username or 'нет'}\n"
                        f"🆔 ID: {user.id}"
                    )
                except Exception as e:
                    print(f"⚠️ Не удалось уведомить администратора: {e}")

            else:
                await query.edit_message_text(
                    "❌ Вы еще не подписались на канал!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)],
                        [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]
                    ])
                )

    except Exception as e:
        print(f"❌ Ошибка в обработчике кнопок: {e}")
        await query.edit_message_text("❌ Произошла ошибка. Попробуйте снова.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    if isinstance(error, Conflict):
        print("⚠️ Обнаружен конфликт - другой экземпляр бота уже запущен")
        return
    elif isinstance(error, NetworkError):
        return
    print(f"❌ Необработанная ошибка: {error}")

# ===== ЗАПУСК БОТА =====
def main():
    print("🔄 Запускаем бота...")

    # Запускаем веб-сервер
    keep_alive()

    # Запускаем самопинг
    start_self_ping()

    # Создаем приложение бота
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    print("🤖 Бот запущен!")
    print("🔗 URL: https://bb94efbc-5fdd-4b67-bd64-bb7f2ec7c046-00-3tr1nljwi6ead.sisko.replit.dev")
    print("🔁 Самопинг активирован")
    print("✅ Бот готов к работе 24/7!")

    # Запускаем бота
    try:
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")

if __name__ == '__main__':
    main()