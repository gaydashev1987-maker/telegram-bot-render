import os
import sqlite3
import random
import logging
from flask import Flask, request, jsonify
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
import threading

print("🚀 Запускаем бота с вебхуком...")

# ===== КОНФИГУРАЦИЯ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8362961253:AAGdU6IjPqAWsCGdTJAF3hlo3c-E5DvhpUY')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 8526339637))
CHANNEL_ID = int(os.environ.get('CHANNEL_ID', -1003371879030))
CHANNEL_LINK = os.environ.get('CHANNEL_LINK', 'https://t.me/+zWVuu6USvyo3NjA6')

print(f"🔧 Токен: {BOT_TOKEN[:10]}...")
print(f"🔧 ADMIN_ID: {ADMIN_ID}")
print(f"🔧 CHANNEL_ID: {CHANNEL_ID}")

# ===== FLASK APP =====
app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)

@app.route('/')
def home():
    return "🤖 Бот активен на Render.com с вебхуком!"

@app.route('/health')
def health():
    return jsonify({"status": "OK", "platform": "render", "webhook": True}), 200

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка вебхука"""
    webhook_url = f"https://telegram-bot-2djw.onrender.com/webhook"
    result = bot.set_webhook(webhook_url)
    return jsonify({"status": "webhook set", "url": webhook_url, "success": result})

@app.route('/webhook', methods=['POST'])
def webhook():
    """Основной обработчик вебхука от Telegram"""
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        handle_update(update)
        return 'OK'
    except Exception as e:
        print(f"❌ Ошибка в вебхуке: {e}")
        return 'ERROR'

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
    conn.commit()
    return conn, cursor

conn, cursor = init_db()
active_captchas = {}

# ===== ОБРАБОТЧИКИ =====
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

def handle_update(update):
    """Обрабатывает обновление от Telegram"""
    try:
        if update.message and update.message.text:
            text = update.message.text
            chat_id = update.message.chat.id
            user = update.message.from_user
            
            print(f"📨 Получено сообщение: {text} от {user.id}")
            
            if text == '/start':
                handle_start(chat_id, user)
            elif chat_id in active_captchas:
                handle_captcha(chat_id, text, user)
            else:
                bot.send_message(chat_id, "❌ Сначала отправьте /start")
                
        elif update.callback_query:
            handle_callback(update.callback_query)
            
    except Exception as e:
        print(f"❌ Ошибка обработки update: {e}")

def handle_start(chat_id, user):
    """Обработчик команды /start"""
    try:
        cursor.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, datetime("now"))',
                      (user.id, user.username, user.first_name))
        conn.commit()
        
        captcha_text, answer = generate_captcha()
        active_captchas[chat_id] = answer
        
        bot.send_message(
            chat_id,
            f"👋 Привет {user.first_name}! Для доступа решите пример:\n\n"
            f"🔢 **{captcha_text}**\n\n"
            f"Отправьте ответ числом:"
        )
        print(f"✅ Каптча отправлена пользователю {user.id}")
        
    except Exception as e:
        print(f"❌ Ошибка в /start: {e}")
        bot.send_message(chat_id, "❌ Ошибка. Попробуйте снова.")

def handle_captcha(chat_id, text, user):
    """Обработчик ответа на каптчу"""
    try:
        correct_answer = active_captchas.get(chat_id)
        
        if text == correct_answer:
            del active_captchas[chat_id]
            cursor.execute('UPDATE users SET captcha_passed = 1 WHERE user_id = ?', (user.id,))
            conn.commit()
            check_subscription(chat_id, user)
        else:
            bot.send_message(chat_id, "❌ Неверно! Попробуйте снова: /start")
            if chat_id in active_captchas:
                del active_captchas[chat_id]
                
    except Exception as e:
        print(f"❌ Ошибка проверки каптчи: {e}")
        bot.send_message(chat_id, "❌ Ошибка. Попробуйте снова: /start")

def check_subscription(chat_id, user):
    """Проверка подписки на канал"""
    try:
        member = bot.get_chat_member(CHANNEL_ID, user.id)
        
        if member.status in ['member', 'administrator', 'creator']:
            bot.send_message(chat_id, "🎉 **Доступ открыт!**")
        else:
            keyboard = [
                [InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)],
                [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            bot.send_message(
                chat_id,
                "✅ Каптча пройдена! Подпишитесь на канал:",
                reply_markup=reply_markup
            )
            
    except Exception as e:
        print(f"❌ Ошибка проверки подписки: {e}")
        keyboard = [
            [InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        bot.send_message(
            chat_id,
            "✅ Каптча пройдена! Подпишитесь на канал:",
            reply_markup=reply_markup
        )

def handle_callback(callback_query):
    """Обработчик нажатия кнопок"""
    try:
        user_id = callback_query.from_user.id
        chat_id = callback_query.message.chat.id
        
        if callback_query.data == "check_sub":
            try:
                member = bot.get_chat_member(CHANNEL_ID, user_id)
                
                if member.status in ['member', 'administrator', 'creator']:
                    bot.edit_message_text(
                        "🎉 **Доступ открыт!**",
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id
                    )
                else:
                    keyboard = [
                        [InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)],
                        [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    bot.edit_message_text(
                        "❌ Вы еще не подписались!",
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        reply_markup=reply_markup
                    )
                    
            except Exception as e:
                print(f"❌ Ошибка проверки подписки в callback: {e}")
                
    except Exception as e:
        print(f"❌ Ошибка обработки callback: {e}")

# ===== ЗАПУСК ПРИЛОЖЕНИЯ =====
if __name__ == '__main__':
    # Устанавливаем вебхук при запуске
    webhook_url = f"https://telegram-bot-2djw.onrender.com/webhook"
    print(f"🌐 Устанавливаем вебхук: {webhook_url}")
    
    try:
        bot.set_webhook(webhook_url)
        print("✅ Вебхук установлен!")
    except Exception as e:
        print(f"❌ Ошибка установки вебхука: {e}")
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Запускаем Flask на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
