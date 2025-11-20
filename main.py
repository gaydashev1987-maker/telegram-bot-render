import os
import sqlite3
import random
import logging
from flask import Flask, request, jsonify
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

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
bot = Bot(token=BOT_TOKEN)

# Инициализируем диспетчер для обработки обновлений
dispatcher = Dispatcher(bot, None, workers=0)

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

# ===== ОБРАБОТЧИКИ КОМАНД =====
def start_command(update, context):
    try:
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        print(f"🎯 Команда /start от {user.id} ({user.first_name})")
        
        cursor.execute(
            'INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, datetime("now"))',
            (user.id, user.username, user.first_name)
        )
        conn.commit()
        
        captcha_text, answer = generate_captcha()
        active_captchas[chat_id] = answer
        
        update.message.reply_text(
            f"👋 Привет, {user.first_name}!\n\n"
            f"Для доступа к боту реши пример:\n\n"
            f"🔢 **{captcha_text}**\n\n"
            f"Отправь ответ числом:"
        )
        print(f"✅ Каптча отправлена пользователю {user.id}")
        
    except Exception as e:
        print(f"❌ Ошибка в /start: {e}")
        update.message.reply_text("❌ Произошла ошибка. Попробуйте снова.")

def handle_message(update, context):
    try:
        user = update.effective_user
        chat_id = update.effective_chat.id
        text = update.message.text
        
        print(f"📨 Сообщение от {user.id}: {text}")
        
        if chat_id in active_captchas:
            handle_captcha_response(update, context)
        else:
            update.message.reply_text("❌ Для начала работы отправьте /start")
            
    except Exception as e:
        print(f"❌ Ошибка обработки сообщения: {e}")

def handle_captcha_response(update, context):
    try:
        user = update.effective_user
        chat_id = update.effective_chat.id
        user_answer = update.message.text.strip()
        correct_answer = active_captchas.get(chat_id)
        
        if user_answer == correct_answer:
            del active_captchas[chat_id]
            cursor.execute('UPDATE users SET captcha_passed = 1 WHERE user_id = ?', (user.id,))
            conn.commit()
            
            check_channel_subscription(update, context)
        else:
            update.message.reply_text("❌ Неверный ответ! Попробуй снова: /start")
            if chat_id in active_captchas:
                del active_captchas[chat_id]
                
    except Exception as e:
        print(f"❌ Ошибка проверки каптчи: {e}")
        update.message.reply_text("❌ Ошибка проверки. Попробуй снова: /start")

def check_channel_subscription(update, context):
    try:
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)
        
        if member.status in ['member', 'administrator', 'creator']:
            update.message.reply_text("🎉 **Поздравляю! Доступ открыт!**")
            print(f"✅ Пользователь {user.id} получил доступ")
        else:
            keyboard = [
                [InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)],
                [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_text(
                "✅ **Каптча пройдена!**\n\n"
                "Теперь подпишись на наш канал чтобы получить доступ:",
                reply_markup=reply_markup
            )
            
    except Exception as e:
        print(f"❌ Ошибка проверки подписки: {e}")
        keyboard = [
            [InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            "✅ **Каптча пройдена!**\n\n"
            "Теперь подпишись на наш канал:",
            reply_markup=reply_markup
        )

def button_handler(update, context):
    try:
        query = update.callback_query
        user = query.from_user
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        
        print(f"🔘 Нажата кнопка пользователем {user.id}")
        
        if query.data == "check_sub":
            try:
                member = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)
                
                if member.status in ['member', 'administrator', 'creator']:
                    context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="🎉 **Поздравляю! Доступ открыт!**"
                    )
                    print(f"✅ Пользователь {user.id} подтвердил подписку")
                else:
                    keyboard = [
                        [InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)],
                        [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="❌ **Ты еще не подписался на канал!**\n\nПожалуйста, подпишись и нажми кнопку снова:",
                        reply_markup=reply_markup
                    )
                    
            except Exception as e:
                print(f"❌ Ошибка проверки подписки в callback: {e}")
                query.answer("❌ Ошибка проверки подписки")
                
    except Exception as e:
        print(f"❌ Ошибка обработки callback: {e}")
        query.answer("❌ Произошла ошибка")

# ===== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ =====
dispatcher.add_handler(CommandHandler("start", start_command))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
dispatcher.add_handler(CallbackQueryHandler(button_handler))

print("✅ Обработчики команд зарегистрированы")

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
        "bot_token_set": bool(BOT_TOKEN)
    }), 200

@app.route('/set_webhook')
def set_webhook():
    """Установка вебхука для Telegram"""
    try:
        # Получаем URL из переменных окружения Render
        render_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://telegram-bot-2djw.onrender.com')
        webhook_url = f"{render_url}/webhook"
        
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
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return 'OK'
    except Exception as e:
        print(f"❌ Ошибка в вебхуке: {e}")
        return 'ERROR', 500

# ===== ЗАПУСК ПРИЛОЖЕНИЯ =====
if __name__ == '__main__':
    print("🌐 Запуск Flask приложения...")
    
    # Устанавливаем вебхук при запуске
    try:
        render_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://telegram-bot-2djw.onrender.com')
        webhook_url = f"{render_url}/webhook"
        bot.set_webhook(webhook_url)
        print(f"✅ Вебхук установлен: {webhook_url}")
    except Exception as e:
        print(f"⚠️ Ошибка установки вебхука: {e}")
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Запуск на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
