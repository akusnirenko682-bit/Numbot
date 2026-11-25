import asyncio
import os
import random
from threading import Thread

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from flask import Flask, jsonify, request

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
    return jsonify({"balance": db.get_balance(user_id)})


@flask_app.route("/api/is_admin/<int:user_id>")
def is_admin_api(user_id):
    return jsonify({"is_admin": user_id == ADMIN_ID})


@flask_app.route("/api/issue/<int:user_id>/<country>", methods=["POST"])
def issue_api(user_id, country):
    country_map = {"ru": "Россия", "by": "Беларусь", "ua": "Украина", "kz": "Казахстан"}
    country_name = country_map.get(country, "Россия")
    price = 500
    balance = db.get_balance(user_id)
    if balance < price:
        return jsonify({"success": False, "message": f"Недостаточно средств! Нужно {price}₽"})
    db.add_balance(user_id, -price)
    number, country, rarity, value = db.issue_number(user_id, country_name, price)
    return jsonify({"success": True, "number": number, "country": country, "rarity": rarity, "price": value})


@flask_app.route("/api/inventory/<int:user_id>")
def get_inventory(user_id):
    items = db.get_user_inventory(user_id)
    return jsonify([{"id": i[0], "number": i[1], "country": i[2], "rarity": i[3], "buy_price": i[4]} for i in items])


@flask_app.route("/api/sell/<int:user_id>/<int:item_id>", methods=["POST"])
def sell_api(user_id, item_id):
    success, msg = db.sell_number(user_id, item_id)
    return jsonify({"success": success, "message": msg})


@flask_app.route("/api/market")
def get_market():
    items = db.get_market_listings(30)
    return jsonify([{"id": i[0], "seller_id": i[1], "number": i[2], "country": i[3], "rarity": i[4], "price": i[5]} for i in items])


@flask_app.route("/api/market/sell/<int:user_id>/<int:item_id>", methods=["POST"])
def sell_to_market(user_id, item_id):
    try:
        price = float(request.json.get("price", 0))
        if price <= 0:
            return jsonify({"success": False, "message": "Цена должна быть больше 0!"})
    except:
        return jsonify({"success": False, "message": "Неверная цена!"})
    success, msg = db.create_market_listing(user_id, item_id, price)
    return jsonify({"success": success, "message": msg})


@flask_app.route("/api/market/buy/<int:buyer_id>/<int:listing_id>", methods=["POST"])
def buy_from_market_api(buyer_id, listing_id):
    success, msg = db.buy_from_market(buyer_id, listing_id)
    return jsonify({"success": success, "message": msg})


@flask_app.route("/api/market/remove/<int:user_id>/<int:listing_id>", methods=["POST"])
def remove_listing(user_id, listing_id):
    success, msg = db.remove_market_listing(user_id, listing_id)
    return jsonify({"success": success, "message": msg})


@flask_app.route("/api/bonus/<int:user_id>", methods=["POST"])
def bonus_api(user_id):
    can, wait = db.can_get_bonus(user_id)
    if not can:
        return jsonify({"success": False, "message": f"Бонус доступен через {wait}"})
    bonus = db.give_bonus(user_id)
    return jsonify({"success": True, "message": f"Получено {bonus}₽!"})


@flask_app.route("/api/top/balance")
def top_balance():
    users = db.get_top_balance(10)
    return jsonify([{"rank": i, "username": u[1] or f"User{u[0]}", "balance": u[2]} for i, u in enumerate(users, 1)])


@flask_app.route("/api/top/rare")
def top_rare():
    users = db.get_top_rare_numbers(10)
    result = []
    for i, (uid, count) in enumerate(users, 1):
        conn = __import__('sqlite3').connect(db.DB_NAME)
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE user_id = ?", (uid,))
        r = c.fetchone()
        conn.close()
        username = r[0] if r and r[0] else f"User{uid}"
        result.append({"rank": i, "username": username, "count": count})
    return jsonify(result)


# ===== АДМИН API ДЛЯ ВЕБ-ИНТЕРФЕЙСА =====

@flask_app.route("/api/admin/users")
def admin_get_users():
    users = db.get_all_users()
    return jsonify([{"user_id": u[0], "username": u[1], "balance": u[2]} for u in users])


@flask_app.route("/api/admin/give_money", methods=["POST"])
def admin_give_money():
    data = request.json
    user_id = int(data.get("user_id"))
    amount = float(data.get("amount", 0))
    if amount <= 0:
        return jsonify({"success": False, "message": "Сумма должна быть больше 0!"})
    db.add_balance(user_id, amount)
    nb = db.get_balance(user_id)
    return jsonify({"success": True, "message": f"Выдано {amount}₽. Новый баланс: {nb}₽"})


@flask_app.route("/api/admin/set_balance", methods=["POST"])
def admin_set_balance():
    data = request.json
    user_id = int(data.get("user_id"))
    amount = float(data.get("amount", 0))
    db.set_balance(user_id, amount)
    return jsonify({"success": True, "message": f"Баланс установлен на {amount}₽"})


@flask_app.route("/api/admin/give_number", methods=["POST"])
def admin_give_number():
    data = request.json
    user_id = int(data.get("user_id"))
    number = data.get("number", "").upper()
    country = data.get("country", "Россия")
    rarity = data.get("rarity", "Обычный")
    price = float(data.get("price", 500))
    db.give_number_to_user(user_id, number, country, rarity, price)
    return jsonify({"success": True, "message": f"Номер {number} ({country}, {rarity}) выдан!"})


@flask_app.route("/api/admin/stats")
def admin_stats():
    users = db.get_all_users()
    total_users = len(users)
    total_balance = sum(u[2] for u in users)
    conn = __import__('sqlite3').connect(db.DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM inventory")
    total_inv = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM market")
    total_market = c.fetchone()[0]
    conn.close()
    return jsonify({
        "total_users": total_users,
        "total_balance": total_balance,
        "total_inventory": total_inv,
        "total_market": total_market
    })


@flask_app.route("/api/admin/broadcast", methods=["POST"])
def admin_broadcast():
    data = request.json
    text = data.get("text", "")
    if not text:
        return jsonify({"success": False, "message": "Текст пуст!"})
    # Сохраняем в БД для отправки через бота
    conn = __import__('sqlite3').connect(db.DB_NAME)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS pending_broadcasts (id INTEGER PRIMARY KEY, text TEXT, sent INTEGER DEFAULT 0)")
    c.execute("INSERT INTO pending_broadcasts (text) VALUES (?)", (text,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Рассылка запланирована! Бот отправит её в течение минуты."})


def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ===== СЕКРЕТНАЯ АДМИНКА В TELEGRAM (резервная) =====
class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_amount = State()
    waiting_for_number = State()
    waiting_for_rarity = State()
    waiting_for_price = State()
    waiting_for_message = State()


def is_admin(user_id):
    return user_id == ADMIN_ID


@dp.message(Command("adm"))
async def secret_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён!")
        return
    hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')
    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\n"
        "Открой Mini App и нажми кнопку ⚙️ Админ — там удобнее!\n"
        "Или используй кнопки ниже:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Открыть админку", web_app=WebAppInfo(url=f"https://{hostname}/app"))]
        ])
    )


# Резервные callback-обработчики для админки в Telegram
@dp.callback_query(F.data.startswith("admin_del_"))
async def admin_delete_number(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    inv_id = int(parts[2])
    uid = int(parts[3])
    db.remove_from_inventory(inv_id, uid)
    await callback.answer(f"✅ Номер удалён у {uid}!", show_alert=True)


@dp.message(AdminStates.waiting_for_user_id)
async def process_user_id(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Используй админ-панель в Mini App — там удобнее! ⚙️")


@dp.message(AdminStates.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    await state.clear()


@dp.message(AdminStates.waiting_for_number)
async def process_number(message: Message, state: FSMContext):
    await state.clear()


@dp.message(AdminStates.waiting_for_rarity)
async def process_rarity(message: Message, state: FSMContext):
    await state.clear()


@dp.message(AdminStates.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    await state.clear()


@dp.message(AdminStates.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext):
    await state.clear()


# ===== ОСНОВНОЙ БОТ =====

@dp.message(Command("start"))
async def cmd_start(message: Message):
    db.get_or_create_user(message.from_user.id, message.from_user.username)
    hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=f"https://{hostname}/app"))]
    ])
    await message.answer(
        f"🚗 <b>Добро пожаловать в Numbers Bot!</b>\n\n"
        f"🇷🇺 Россия | 🇧🇾 Беларусь | 🇺🇦 Украина | 🇰🇿 Казахстан\n\n"
        f"Выбирай страну и получай случайный номерной знак!\n"
        f"Собирай редкие номера, продавай на рынке, соревнуйся в топе!",
        parse_mode="HTML",
        reply_markup=keyboard
    )


# Фоновая задача для отправки рассылок
async def broadcast_sender():
    while True:
        try:
            conn = __import__('sqlite3').connect(db.DB_NAME)
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS pending_broadcasts (id INTEGER PRIMARY KEY, text TEXT, sent INTEGER DEFAULT 0)")
            c.execute("SELECT id, text FROM pending_broadcasts WHERE sent = 0 LIMIT 1")
            row = c.fetchone()
            if row:
                bid, text = row
                users = db.send_message_to_all()
                sent = failed = 0
                for uid in users:
                    try:
                        await bot.send_message(uid, f"📢 <b>Рассылка:</b>\n\n{text}", parse_mode="HTML")
                        sent += 1
                    except:
                        failed += 1
                c.execute("UPDATE pending_broadcasts SET sent = 1 WHERE id = ?", (bid,))
                conn.commit()
                print(f"📢 Рассылка #{bid}: отправлено {sent}, ошибок {failed}")
            conn.close()
        except Exception as e:
            print(f"Broadcast error: {e}")
        await asyncio.sleep(30)


async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Веб-сервер запущен")
    print("🤖 Бот запущен!")
    
    # Запускаем фоновую задачу для рассылок
    asyncio.create_task(broadcast_sender())
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
