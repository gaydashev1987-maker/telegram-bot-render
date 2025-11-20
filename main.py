import os
import sqlite3
import random
import logging
from flask import Flask, request, jsonify
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("=" * 50)
print("🚀 ЗАПУСК БОТА НА RENDER.COM")
print("=" * 50)

# ===== КОНФИГУРАЦИЯ =====
BOT_TOKEN = os.environ.get('8362961253:AAGdU6IjPqAWsCGdTJAF3hlo3c-E5DvhpUY')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 8526339637))
CHANNEL_ID = int(os.environ.get('CHANNEL_ID', -1003371879030))
CHANNEL_LINK = os.environ.get('CHANNEL_LINK', 'https://t.me/+zWVuu6USvyo3NjA6')

print(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}..." if BOT_TOKEN else "❌ BOT_TOKEN: НЕ НАЙДЕН")
print(f"✅ ADMIN_ID: {ADMIN_ID}")
print(f"✅ CHANNEL_ID: {CHANNEL_ID}")
print(f"✅ CHANNEL_LINK: {CHANNEL_LINK}")

# Проверяем обязательные переменные
if not BOT_TOKEN:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не установлен!")
    exit(1)

# ===== ИНИЦИАЛИЗАЦИЯ =====
app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)

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
    """Генерация простой математической каптчи"""
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
        "platform": "render.com"
    }), 200

@app.route('/set_webhook')
def set_webhook():
    """Установка вебхука для Telegram"""
    try:
        webhook_url = f"https://{request.host}/webhook"
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
        process_update(update)
        return 'OK'
    except Exception as e:
        print(f"❌ Ошибка в вебхуке: {e}")
        return 'ERROR', 500

# ===== ОБРАБОТЧИКИ TELEGRAM =====
def process_update(update):
    """Обрабатывает обновление от Telegram"""
    try:
        if update.message and update.message.text:
            handle_message(update.message)
        elif update.callback_query:
            handle_callback(update.callback_query)
    except Exception as e:
        print(f"❌ Ошибка обработки update: {e}")

def handle_message(message):
    """Обрабатывает текстовые сообщения"""
    chat_id = message.chat.id
    text = message.text
    user = message.from_user
    
    print(f"📨 Сообщение от {user.id} ({user.first_name}): {text}")
    
    if text == '/start':
        handle_start_command(chat_id, user)
    elif chat_id in active_captchas:
        handle_captcha_response(chat_id, text, user)
    else:
        bot.send_message(chat_id, "❌ Для начала работы отправьте /start")

def handle_start_command(chat_id, user):
    """Обрабатывает команду /start"""
    try:
        # Сохраняем пользователя в БД
        cursor.execute(
            'INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, datetime("now"))',
            (user.id, user.username, user.first_name)
        )
        conn.commit()
        
        # Генерируем каптчу
        captcha_text, answer = generate_captcha()
        active_captchas[chat_id] = answer
        
        # Отправляем каптчу пользователю
        bot.send_message(
            chat_id,
            f"👋 Привет, {user.first_name}!\n\n"
            f"Для доступа к боту реши простой пример:\n\n"
            f"🔢 <b>{captcha_text}</b>\n\n"
            f"Отправь ответ числом:",
            parse_mode='HTML'
        )
        print(f"✅ Каптча отправлена пользователю {user.id}")
        
    except Exception as e:
        print(f"❌ Ошибка в /start: {e}")
        bot.send_message(chat_id, "❌ Произошла ошибка. Попробуйте снова.")

def handle_captcha_response(chat_id, user_answer, user):
    """Проверяет ответ на каптчу"""
    try:
        correct_answer = active_captchas.get(chat_id)
        
        if user_answer.strip() == correct_answer:
            # Каптча пройдена
            del active_captchas[chat_id]
            cursor.execute('UPDATE users SET captcha_passed = 1 WHERE user_id = ?', (user.id,))
            conn.commit()
            
            # Проверяем подписку на канал
            check_channel_subscription(chat_id, user)
        else:
            # Неверный ответ
            bot.send_message(chat_id, "❌ Неверный ответ! Попробуй снова: /start")
            if chat_id in active_captchas:
                del active_captchas[chat_id]
                
    except Exception as e:
        print(f"❌ Ошибка проверки каптчи: {e}")
        bot.send_message(chat_id, "❌ Ошибка проверки. Попробуй снова: /start")

def check_channel_subscription(chat_id, user):
    """Проверяет подписку на канал"""
    try:
        member = bot.get_chat_member(CHANNEL_ID, user.id)
        
        if member.status in ['member', 'administrator', 'creator']:
            # Пользователь подписан
            bot.send_message(
                chat_id,
                "🎉 <b>Поздравляю! Доступ открыт!</b>\n\n"
                "Ты успешно прошел проверку и подписан на канал!",
                parse_mode='HTML'
            )
            print(f"✅ Пользователь {user.id} получил доступ")
        else:
            # Пользователь не подписан
            keyboard = [
                [InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)],
                [InlineKeyboardButton("✅ Я подписался", callback_data="check_subscription")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            bot.send_message(
                chat_id,
                "✅ <b>Каптча пройдена!</b>\n\n"
                "Теперь подпишись на наш канал чтобы получить доступ:",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
    except Exception as e:
        print(f"❌ Ошибка проверки подписки: {e}")
        # Если ошибка, все равно показываем кнопку
        keyboard = [
            [InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Я подписался", callback_data="check_subscription")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        bot.send_message(
            chat_id,
            "✅ <b>Каптча пройдена!</b>\n\n"
            "Теперь подпишись на наш канал:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

def handle_callback(callback_query):
    """Обрабатывает нажатия инлайн-кнопок"""
    try:
        user = callback_query.from_user
        chat_id = callback_query.message.chat.id
        message_id = callback_query.message.message_id
        
        print(f"🔘 Нажата кнопка пользователем {user.id}")
        
        if callback_query.data == "check_subscription":
            # Проверяем подписку при нажатии кнопки
            try:
                member = bot.get_chat_member(CHANNEL_ID, user.id)
                
                if member.status in ['member', 'administrator', 'creator']:
                    # Подписка подтверждена
                    bot.edit_message_text(
                        "🎉 <b>Поздравляю! Доступ открыт!</b>",
                        chat_id=chat_id,
                        message_id=message_id,
                        parse_mode='HTML'
                    )
                    print(f"✅ Пользователь {user.id} подтвердил подписку")
                else:
                    # Все еще не подписан
                    keyboard = [
                        [InlineKeyboardButton("📢 Перейти на канал", url=CHANNEL_LINK)],
                        [InlineKeyboardButton("✅ Я подписался", callback_data="check_subscription")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    bot.edit_message_text(
                        "❌ <b>Ты еще не подписался на канал!</b>\n\n"
                        "Пожалуйста, подпишись и нажми кнопку снова:",
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
                    
            except Exception as e:
                print(f"❌ Ошибка проверки подписки в callback: {e}")
                bot.answer_callback_query(callback_query.id, "❌ Ошибка проверки подписки")
                
    except Exception as e:
        print(f"❌ Ошибка обработки callback: {e}")
        bot.answer_callback_query(callback_query.id, "❌ Произошла ошибка")

# ===== ЗАПУСК ПРИЛОЖЕНИЯ =====
if __name__ == '__main__':
    print("🌐 Запуск Flask приложения...")
    
    # Устанавливаем вебхук при запуске
    try:
        # Получаем хост из переменных окружения Render
        render_url = os.environ.get('RENDER_EXTERNAL_URL')
        if render_url:
            webhook_url = f"{render_url}/webhook"
            bot.set_webhook(webhook_url)
            print(f"✅ Вебхук установлен: {webhook_url}")
        else:
            print("⚠️ RENDER_EXTERNAL_URL не найден, вебхук не установлен")
    except Exception as e:
        print(f"⚠️ Ошибка установки вебхука: {e}")
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Запуск на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
