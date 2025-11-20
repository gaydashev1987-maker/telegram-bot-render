import os
import sqlite3
import random
import logging
import requests
import threading
import time
from flask import Flask, request, jsonify
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

print("=" * 50)
print("🚀 БОТ ЗАПУЩЕН НА RENDER.COM - 24/7")
print("=" * 50)

# ===== КОНФИГУРАЦИЯ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8362961253:AAGdU6IjPqAWsCGdTJAF3hlo3c-E5DvhpUY')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 8526339637))
CHANNEL_ID = int(os.environ.get('CHANNEL_ID', -1003371879030))
CHANNEL_LINK = os.environ.get('CHANNEL_LINK', 'https://t.me/+zWVuu6USvyo3NjA6')
RENDER_URL = "https://telegram-bot-2djw.onrender.com"

print(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}...")
print(f"✅ ADMIN_ID: {ADMIN_ID}")
print(f"✅ CHANNEL_ID: {CHANNEL_ID}")
print(f"✅ RENDER_URL: {RENDER_URL}")

# ===== ИНИЦИАЛИЗАЦИЯ =====
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

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
    print("✅ База данных инициализирована")
    return conn, cursor

conn, cursor = init_db()
active_captchas = {}

# ===== САМОПИНГ ДЛЯ ПОДДЕРЖАНИЯ АКТИВНОСТИ =====
def self_ping():
    """Периодически пингует сервис для поддержания активности"""
    while True:
        try:
            response = requests.get(f"{RENDER_URL}/health", timeout=10)
            if response.status_code == 200:
                print(f"✅ Самопинг выполнен: {time.strftime('%H:%M:%S')}")
            else:
                print(f"⚠️ Самопинг: статус {response.status_code}")
        except Exception as e:
            print(f"❌ Ошибка самопинга: {e}")
        
        # Ждем 8 минут между запросами (меньше 15 минут сна Render)
        time.sleep(480)  # 8 минут

# Запускаем самопинг в отдельном потоке
ping_thread = threading.Thread(target=self_ping, daemon=True)
ping_thread.start()
print("🔁 Самопинг запущен (каждые 8 минут)")

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
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

# ===== FLASK МАРШРУТЫ =====
@app.route('/')
def home():
    return """
    <h1>🤖 Telegram Bot Active 24/7</h1>
    <p>Бот успешно запущен на Render.com и работает круглосуточно!</p>
    <p><strong>Статус:</strong> ✅ Активен</p>
    <p><strong>Самопинг:</strong> ✅ Включен</p>
    <p><a href="/health">Проверить здоровье</a></p>
    <p><a href="/set_webhook">Установить вебхук</a></p>
    <p><a href="/stats">Статистика</a></p>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "OK", 
        "service": "telegram-bot",
        "platform": "render.com",
        "24_7": True,
        "self_ping": "active",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }), 200

@app.route('/stats')
def stats():
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE captcha_passed = 1')
    passed_users = cursor.fetchone()[0]
    
    return jsonify({
        "total_users": total_users,
        "passed_captcha": passed_users,
        "active_captchas": len(active_captchas)
    })

@app.route('/set_webhook')
def set_webhook():
    """Установка вебхука для Telegram"""
    try:
        webhook_url = f"{RENDER_URL}/webhook"
        bot.remove_webhook()
        success = bot.set_webhook(webhook_url)
        return jsonify({
            "status": "success" if success else "error",
            "webhook_url": webhook_url,
            "message": "Вебхук установлен" if success else "Ошибка установки вебхука",
            "24_7": True
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Ошибка: {str(e)}"
        }), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """Основной обработчик вебхука от Telegram"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Invalid content type', 403

# ===== ОБРАБОТЧИКИ TELEGRAM =====
@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        user = message.from_user
        chat_id = message.chat.id
        
        print(f"🎯 Команда /start от {user.id} ({user.first_name})")
        
        cursor.execute(
            'INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, datetime("now"))',
            (user.id, user.username, user.first_name)
        )
        conn.commit()
        
        captcha_text, answer = generate_captcha()
        active_captchas[str(chat_id)] = answer
        
        bot.send_message(
            chat_id,
            f"👋 Привет, {user.first_name}!\n\n"
            f"Для доступа к боту реши пример:\n\n"
            f"🔢 **{captcha_text}**\n\n"
            f"Отправь ответ числом:",
            parse_mode='Markdown'
        )
        print(f"✅ Каптча отправлена пользователю {user.id}")
        
    except Exception as e:
        print(f"❌ Ошибка в /start: {e}")
        bot.reply_to(message, "❌ Произошла ошибка. Попробуйте снова.")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        user = message.from_user
        chat_id = message.chat.id
        text = message.text
        
        print(f"📨 Сообщение от {user.id}: {text}")
        
        if str(chat_id) in active_captchas:
            handle_captcha_response(message)
        else:
            bot.send_message(chat_id, "❌ Для начала работы отправьте /start")
            
    except Exception as e:
        print(f"❌ Ошибка обработки сообщения: {e}")

def handle_captcha_response(message):
    try:
        user = message.from_user
        chat_id = message.chat.id
        user_answer = message.text.strip()
        correct_answer = active_captchas.get(str(chat_id))
        
        if user_answer == correct_answer:
            del active_captchas[str(chat_id)]
            cursor.execute('UPDATE users SET captcha_passed = 1 WHERE user_id = ?', (user.id,))
            conn.commit()
            check_channel_subscription(chat_id, user)
        else:
            bot.send_message(chat_id, "❌ Неверный ответ! Попробуй снова: /start")
            if str(chat_id) in active_captchas:
                del active_captchas[str(chat_id)]
                
    except Exception as e:
        print(f"❌ Ошибка проверки каптчи: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка проверки. Попробуй снова: /start")

def check_channel_subscription(chat_id, user):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user.id)
        
        if member.status in ['member', 'administrator', 'creator']:
            bot.send_message(
                chat_id,
                "🎉 **Поздравляю! Доступ открыт!**\n\n"
                "Ты успешно прошел проверку и подписан на канал!",
                parse_mode='Markdown'
            )
            print(f"✅ Пользователь {user.id} получил доступ")
        else:
            keyboard = InlineKeyboardMarkup()
            keyboard.row(InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK))
            keyboard.row(InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
            
            bot.send_message(
                chat_id,
                "✅ **Каптча пройдена!**\n\n"
                "Теперь подпишись на наш канал чтобы получить доступ:",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        print(f"❌ Ошибка проверки подписки: {e}")
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK))
        keyboard.row(InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        
        bot.send_message(
            chat_id,
            "✅ **Каптча пройдена!**\n\n"
            "Теперь подпишись на наш канал:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        user = call.from_user
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        
        print(f"🔘 Нажата кнопка пользователем {user.id}")
        
        if call.data == "check_sub":
            try:
                member = bot.get_chat_member(CHANNEL_ID, user.id)
                
                if member.status in ['member', 'administrator', 'creator']:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="🎉 **Поздравляю! Доступ открыт!**",
                        parse_mode='Markdown'
                    )
                    print(f"✅ Пользователь {user.id} подтвердил подписку")
                else:
                    keyboard = InlineKeyboardMarkup()
                    keyboard.row(InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK))
                    keyboard.row(InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
                    
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="❌ **Ты еще не подписался на канал!**\n\n"
                             "Пожалуйста, подпишись и нажми кнопку снова:",
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                    
            except Exception as e:
                print(f"❌ Ошибка проверки подписки в callback: {e}")
                bot.answer_callback_query(call.id, "❌ Ошибка проверки подписки")
                
    except Exception as e:
        print(f"❌ Ошибка обработки callback: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка")

# ===== ЗАПУСК ПРИЛОЖЕНИЯ =====
if __name__ == '__main__':
    print("🌐 Запуск Flask приложения...")
    
    # Устанавливаем вебхук при запуске
    try:
        webhook_url = f"{RENDER_URL}/webhook"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"✅ Вебхук установлен: {webhook_url}")
    except Exception as e:
        print(f"⚠️ Ошибка установки вебхука: {e}")
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Запуск на порту {port}")
    print("✅ Бот готов к работе 24/7!")
    app.run(host='0.0.0.0', port=port, debug=False)
