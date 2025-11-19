import os
import sqlite3
import random
import logging
from flask import Flask, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import threading

# ===== КОНФИГУРАЦИЯ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8362961253:AAGdU6IjPqAWsCGdTJAF3hlo3c-E5DvhpUY')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 8526339637))
CHANNEL_ID = int(os.environ.get('CHANNEL_ID', -1003371879030))
CHANNEL_LINK = os.environ.get('CHANNEL_LINK', 'https://t.me/+zWVuu6USvyo3NjA6')

# ===== FLASK APP =====
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот активен на Render.com!"

@app.route('/health')
def health():
    return jsonify({"status": "OK", "platform": "render"}), 200

@app.route('/ping')
def ping():
    return "pong", 200

# ===== БАЗА ДАННЫХ =====
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

# ===== ГЕНЕРАЦИЯ КАПТЧИ =====
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
                await query.edit_message_text("🎉 **Доступ открыт!**")
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

# ===== ЗАПУСК БОТА =====
def run_bot():
    """Запускает Telegram бота в отдельном потоке"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("🤖 Telegram бот запущен на Render!")
        
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")

# ===== ЗАПУСК ПРИЛОЖЕНИЯ =====
if __name__ == '__main__':
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask сервер
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Запускаем веб-сервер на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)