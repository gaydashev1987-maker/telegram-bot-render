import os
import sqlite3
import random
import logging
from flask import Flask, request, jsonify
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

print("=" * 50)
print("🚀 ЗАПУСК БОТА НА RENDER.COM")
print("=" * 50)

# ===== КОНФИГУРАЦИЯ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8362961253:AAGdU6IjPqAWsCGdTJAF3hlo3c-E5DvhpUY')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 8526339637))
CHANNEL_ID = int(os.environ.get('CHANNEL_ID', -1003371879030))
CHANNEL_LINK = os.environ.get('CHANNEL_LINK', 'https://t.me/+zWVuu6USvyo3NjA6')

print(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}..." if BOT_TOKEN else "❌ BOT_TOKEN: НЕ НАЙДЕН")
print(f"✅ ADMIN_ID: {ADMIN_ID}")
print(f"✅ CHANNEL_ID: {CHANNEL_ID}")
print(f"✅ CHANNEL_LINK: {CHANNEL_LINK}")

if not BOT_TOKEN:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не установлен!")
    exit(1)

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
    print(f"🔐 Сгенерирована каптча: {question} = {answer}")
    return question, str(answer)

# ===== FLASK МАРШРУТЫ =====
@app.route('/')
def home():
    return """
    <h1>🤖 Telegram Bot Active</h1>
    <p>Бот успешно запущен на Render.com!</p>
    <p><a href="/health">Проверить здоровье</a></p>
    <p><a href="/set_webhook">Установить вебхук</a></p>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "OK", 
        "service": "telegram-bot",
        "platform": "render.com",
        "bot": "pyTelegramBotAPI"
    }), 200

@app.route('/set_webhook')
def set_webhook():
    """Установка вебхука для Telegram"""
    try:
        webhook_url = f"https://telegram-bot-2djw.onrender.com/webhook"
        success = bot.set_webhook(webhook_url)
        return jsonify({
            "status": "success" if success else "error",
            "webhook_url": webhook_url,
            "message": "Вебхук установлен" if success else "Ошибка установки вебхука"
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
    """Обрабатывает команду /start"""
    try:
        user = message.from_user
        chat_id = message.chat.id
        
        print(f"🎯 Команда /start от {user.id} ({user.first_name})")
        
        # Сохраняем пользователя в БД
        cursor.execute(
            'INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, datetime("now"))',
            (user.id, user.username, user.first_name)
        )
        conn.commit()
        
        # Генерируем каптчу
        captcha_text, answer = generate_captcha()
        active_captchas[str(chat_id)] = answer
        
        # Отправляем каптчу пользователю
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
    """Обрабатывает все текстовые сообщения"""
    try:
        user = message.from_user
        chat_id = message.chat.id
        text = message.text
        
        print(f"📨 Сообщение от {user.id}: {text}")
        
        # Проверяем, ожидаем ли мы ответ на каптчу
        if str(chat_id) in active_captchas:
            handle_captcha_response(message)
        else:
            bot.send_message(chat_id, "❌ Для начала работы отправьте /start")
            
    except Exception as e:
        print(f"❌ Ошибка обработки сообщения: {e}")

def handle_captcha_response(message):
    """Проверяет ответ на каптчу"""
    try:
        user = message.from_user
        chat_id = message.chat.id
        user_answer = message.text.strip()
        correct_answer = active_captchas.get(str(chat_id))
        
        if user_answer == correct_answer:
            # Каптча пройдена
            del active_captchas[str(chat_id)]
            cursor.execute('UPDATE users SET captcha_passed = 1 WHERE user_id = ?', (user.id,))
            conn.commit()
            
            # Проверяем подписку на канал
            check_channel_subscription(chat_id, user)
        else:
            # Неверный ответ
            bot.send_message(chat_id, "❌ Неверный ответ! Попробуй снова: /start")
            if str(chat_id) in active_captchas:
                del active_captchas[str(chat_id)]
                
    except Exception as e:
        print(f"❌ Ошибка проверки каптчи: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка проверки. Попробуй снова: /start")

def check_channel_subscription(chat_id, user):
    """Проверяет подписку на канал"""
    try:
        member = bot.get_chat_member(CHANNEL_ID, user.id)
        
        if member.status in ['member', 'administrator', 'creator']:
            # Пользователь подписан
            bot.send_message(
                chat_id,
                "🎉 **Поздравляю! Доступ открыт!**\n\n"
                "Ты успешно прошел проверку и подписан на канал!",
                parse_mode='Markdown'
            )
            print(f"✅ Пользователь {user.id} получил доступ")
        else:
            # Пользователь не подписан
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)
            )
            keyboard.row(
                InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")
            )
            
            bot.send_message(
                chat_id,
                "✅ **Каптча пройдена!**\n\n"
                "Теперь подпишись на наш канал чтобы получить доступ:",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        print(f"❌ Ошибка проверки подписки: {e}")
        # Если ошибка, все равно показываем кнопку
        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)
        )
        keyboard.row(
            InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")
        )
        
        bot.send_message(
            chat_id,
            "✅ **Каптча пройдена!**\n\n"
            "Теперь подпишись на наш канал:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Обрабатывает нажатия инлайн-кнопок"""
    try:
        user = call.from_user
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        
        print(f"🔘 Нажата кнопка пользователем {user.id}")
        
        if call.data == "check_sub":
            # Проверяем подписку при нажатии кнопки
            try:
                member = bot.get_chat_member(CHANNEL_ID, user.id)
                
                if member.status in ['member', 'administrator', 'creator']:
                    # Подписка подтверждена
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="🎉 **Поздравляю! Доступ открыт!**",
                        parse_mode='Markdown'
                    )
                    print(f"✅ Пользователь {user.id} подтвердил подписку")
                else:
                    # Все еще не подписан
                    keyboard = InlineKeyboardMarkup()
                    keyboard.row(
                        InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)
                    )
                    keyboard.row(
                        InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")
                    )
                    
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
        webhook_url = "https://telegram-bot-2djw.onrender.com/webhook"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"✅ Вебхук установлен: {webhook_url}")
    except Exception as e:
        print(f"⚠️ Ошибка установки вебхука: {e}")
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Запуск на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
