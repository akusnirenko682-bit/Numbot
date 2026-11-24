import asyncio
import os
import random
from threading import Thread

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from flask import Flask, jsonify

import database as db
from config import BOT_TOKEN, ADMIN_ID, PORT

flask_app = Flask(__name__, static_folder='static')

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

@flask_app.route("/api/open_case/<int:user_id>", methods=["POST"])
def open_case_api(user_id):
    balance = db.get_balance(user_id)
    case_price = 500
    
    if balance < case_price:
        return jsonify({"success": False, "message": f"Недостаточно средств! Нужно {case_price}₽"})
    
    db.add_balance(user_id, -case_price)
    number, country, rarity, price = db.open_case(user_id)
    
    return jsonify({
        "success": True,
        "number": number,
        "country": country,
        "rarity": rarity,
        "price": price
    })

@flask_app.route("/api/inventory/<int:user_id>")
def get_inventory(user_id):
    items = db.get_user_inventory(user_id)
    result = []
    for item in items:
        result.append({
            "id": item[0],
            "number": item[1],
            "country": item[2],
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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    db.get_or_create_user(message.from_user.id, message.from_user.username)
    
    hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=f"https://{hostname}/app"))]
    ])
    
    await message.answer(
        f"🚗 <b>Добро пожаловать в Numbers Bot!</b>\n\n"
        f"Открывай кейсы и выбивай редкие номера!\n"
        f"🇷🇺 Россия | 🇧🇾 Беларусь | 🇺🇦 Украина | 🇰🇿 Казахстан\n\n"
        f"Нажми кнопку ниже, чтобы начать!",
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
