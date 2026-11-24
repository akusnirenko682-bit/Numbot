import asyncio
import os
import random
from threading import Thread

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, jsonify

import database as db
from config import BOT_TOKEN, ADMIN_ID, PORT

flask_app = Flask(__name__, static_folder='static')

# ===== Flask роуты =====
@flask_app.route("/")
def home():
    return "✅ NumBot работает!"

@flask_app.route("/health")
def health():
    return "OK"

@flask_app.route("/app")
def webapp():
    return flask_app.send_static_file('index.html')

@flask_app.route("/api/user/<int:user_id>")
def get_user(user_id):
    db.get_or_create_user(user_id, None)
    balance = db.get_balance(user_id)
    return jsonify({"balance": balance})

@flask_app.route("/api/shop/<int:user_id>")
def get_shop(user_id):
    for _ in range(5):
        db.add_number_to_shop()
    items = db.get_shop_numbers(5)
    result = []
    for item in items:
        result.append({
            "id": item[0],
            "number": item[1],
            "rarity": item[2],
            "price": item[3]
        })
    return jsonify(result)

@flask_app.route("/api/buy/<int:user_id>/<int:item_id>", methods=["POST"])
def buy_number_api(user_id, item_id):
    success, msg = db.buy_number(user_id, item_id)
    return jsonify({"success": success, "message": msg})

@flask_app.route("/api/inventory/<int:user_id>")
def get_inventory(user_id):
    items = db.get_user_inventory(user_id)
    result = []
    for item in items:
        result.append({
            "id": item[0],
            "number": item[2],
            "rarity": item[3],
            "buy_price": item[4]
        })
    return jsonify(result)

@flask_app.route("/api/sell/<int:user_id>/<int:item_id>", methods=["POST"])
def sell_number_api(user_id, item_id):
    success, msg = db.sell_number(user_id, item_id)
    return jsonify({"success": success, "message": msg})

@flask_app.route("/api/bonus/<int:user_id>", methods=["POST"])
def get_bonus_api(user_id):
    bonus = random.randint(100, 500)
    db.add_balance(user_id, bonus)
    new_balance = db.get_balance(user_id)
    return jsonify({"success": True, "message": f"Получено {bonus}₽! Баланс: {new_balance}₽"})

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

# ===== Telegram бот =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    db.get_or_create_user(message.from_user.id, message.from_user.username)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')}/app"))]
    ])
    
    await message.answer(
        f"🚗 <b>Добро пожаловать в Numbers Bot!</b>\n\n"
        f"Нажми кнопку ниже, чтобы начать игру!",
        parse_mode="HTML",
        reply_markup=keyboard
    )

async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Веб-сервер запущен")
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
