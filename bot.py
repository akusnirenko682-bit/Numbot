import asyncio
import os
import sqlite3
from threading import Thread

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, jsonify, request

import database as db
from config import BOT_TOKEN, ADMIN_IDS, PORT

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
    db.get_or_create_user(user_id, request.args.get("username"))
    return jsonify({
        "balance": db.get_balance(user_id),
        "is_admin": user_id in ADMIN_IDS,
        "issue_price": db.get_issue_price(user_id)
    })

@flask_app.route("/api/issue/<int:user_id>/<country>", methods=["POST"])
def issue_api(user_id, country):
    country_map = {"ru": "Россия", "by": "Беларусь", "ua": "Украина", "kz": "Казахстан"}
    country_name = country_map.get(country, "Россия")
    price = db.get_issue_price(user_id)
    if db.get_balance(user_id) < price:
        return jsonify({"success": False, "message": f"Нужно {price}₽"})
    db.add_balance(user_id, -price)
    number, c, rarity, value, _ = db.issue_number(user_id, country_name)
    return jsonify({"success": True, "number": number, "country": c, "rarity": rarity, "price": value})

@flask_app.route("/api/inventory/<int:user_id>")
def get_inventory(user_id):
    items = db.get_user_inventory(user_id)
    return jsonify([{"id": i[0], "number": i[1], "country": i[2], "rarity": i[3], "buy_price": i[4]} for i in items])

@flask_app.route("/api/sell/<int:user_id>/<int:item_id>", methods=["POST"])
def sell_api(user_id, item_id):
    s, m = db.sell_number(user_id, item_id)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/auto_sell/<int:user_id>", methods=["POST"])
def auto_sell_api(user_id):
    s, m = db.auto_sell(user_id)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/market")
def get_market():
    items = db.get_market_listings(30)
    return jsonify([{"id": i[0], "seller_id": i[1], "number": i[2], "country": i[3], "rarity": i[4], "price": i[5]} for i in items])

@flask_app.route("/api/market/sell/<int:user_id>/<int:item_id>", methods=["POST"])
def sell_to_market(user_id, item_id):
    price = float(request.json.get("price", 0))
    s, m = db.create_market_listing(user_id, item_id, price)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/market/buy/<int:buyer_id>/<int:listing_id>", methods=["POST"])
def buy_from_market_api(buyer_id, listing_id):
    s, m = db.buy_from_market(buyer_id, listing_id)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/bonus/<int:user_id>", methods=["POST"])
def bonus_api(user_id):
    can, wait = db.can_get_bonus(user_id)
    if not can:
        return jsonify({"success": False, "message": f"Бонус через {wait}"})
    bonus = db.give_bonus(user_id)
    return jsonify({"success": True, "message": f"Получено {bonus}₽!"})

@flask_app.route("/api/top/balance")
def top_balance():
    users = db.get_top_balance(10)
    return jsonify([{"rank": i, "username": u[1] or f"User{u[0]}", "balance": u[2]} for i, u in enumerate(users, 1)])

@flask_app.route("/api/top/rare")
def top_rare():
    users = db.get_top_rare_numbers(10)
    return jsonify([{"rank": i, "username": u[1] or f"User{u[0]}", "count": u[1]} for i, u in enumerate(users, 1)])

@flask_app.route("/api/tasks/<int:user_id>")
def get_tasks(user_id):
    return jsonify(db.get_or_create_tasks(user_id))

@flask_app.route("/api/tasks/claim/<int:user_id>/<key>", methods=["POST"])
def claim_task_api(user_id, key):
    s, m = db.claim_task(user_id, key)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/safe/<int:user_id>")
def get_safe_api(user_id):
    return jsonify(db.get_safe(user_id))

@flask_app.route("/api/safe/deposit/<int:user_id>", methods=["POST"])
def deposit_api(user_id):
    amount = float(request.json.get("amount", 0))
    s, m = db.deposit_safe(user_id, amount)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/safe/withdraw/<int:user_id>", methods=["POST"])
def withdraw_api(user_id):
    s, m = db.withdraw_safe(user_id)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/upgrades/<int:user_id>")
def upgrades_api(user_id):
    return jsonify(db.get_upgrades_status(user_id))

@flask_app.route("/api/upgrades/buy/<int:user_id>/<key>", methods=["POST"])
def buy_upgrade_api(user_id, key):
    s, m = db.buy_upgrade(user_id, key)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/auctions")
def auctions_api():
    lots = db.get_auctions()
    return jsonify([{"id": l[0], "seller_id": l[1], "number": l[2], "country": l[3], "rarity": l[4],
                     "min_price": l[5], "current_bid": l[6], "current_bidder": l[7], "ends_at": l[8]} for l in lots])

@flask_app.route("/api/auctions/create/<int:user_id>/<int:item_id>", methods=["POST"])
def create_auction_api(user_id, item_id):
    price = float(request.json.get("min_price", 100))
    s, m = db.create_auction(user_id, item_id, price)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/auctions/bid/<int:user_id>/<int:lot_id>", methods=["POST"])
def bid_api(user_id, lot_id):
    bid = float(request.json.get("bid", 0))
    s, m = db.make_bid(user_id, lot_id, bid)
    return jsonify({"success": s, "message": m})


# ===== АДМИН API (ВСЕ ФУНКЦИИ) =====

def check_admin(user_id):
    return user_id in ADMIN_IDS

@flask_app.route("/api/admin/stats")
def admin_stats():
    users = db.get_all_users()
    conn = db.get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM inventory")
    total_inv = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM market")
    total_market = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM auction")
    total_auction = c.fetchone()[0]
    conn.close()
    return jsonify({
        "total_users": len(users),
        "total_balance": sum(u[2] for u in users),
        "total_inventory": total_inv,
        "total_market": total_market,
        "total_auction": total_auction
    })

@flask_app.route("/api/admin/users")
def admin_users():
    return jsonify([{"user_id": u[0], "username": u[1], "balance": u[2]} for u in db.get_all_users()])

@flask_app.route("/api/admin/give_money", methods=["POST"])
def admin_give_money():
    d = request.json
    amount = float(d["amount"])
    if amount <= 0:
        return jsonify({"success": False, "message": "Сумма должна быть больше 0!"})
    db.add_balance(int(d["user_id"]), amount)
    nb = db.get_balance(int(d["user_id"]))
    return jsonify({"success": True, "message": f"Выдано {amount}₽. Новый баланс: {nb}₽"})

@flask_app.route("/api/admin/take_money", methods=["POST"])
def admin_take_money():
    d = request.json
    user_id = int(d["user_id"])
    amount = float(d["amount"])
    if amount <= 0:
        return jsonify({"success": False, "message": "Сумма должна быть больше 0!"})
    cur = db.get_balance(user_id)
    if cur < amount:
        return jsonify({"success": False, "message": f"У игрока только {cur}₽, нельзя списать {amount}₽!"})
    db.add_balance(user_id, -amount)
    nb = db.get_balance(user_id)
    return jsonify({"success": True, "message": f"Списано {amount}₽. Новый баланс: {nb}₽"})

@flask_app.route("/api/admin/set_balance", methods=["POST"])
def admin_set_balance():
    d = request.json
    amount = float(d["amount"])
    if amount < 0:
        return jsonify({"success": False, "message": "Баланс не может быть отрицательным!"})
    db.set_balance(int(d["user_id"]), amount)
    return jsonify({"success": True, "message": f"Баланс установлен на {amount}₽"})

@flask_app.route("/api/admin/user_info/<int:user_id>")
def admin_user_info(user_id):
    user, cnt = db.get_user_info(user_id)
    if not user:
        return jsonify({"success": False, "message": f"Игрок {user_id} не найден!"})
    return jsonify({
        "success": True,
        "user_id": user[0],
        "username": user[1] or "нет",
        "balance": user[2],
        "created_at": user[3][:10] if user[3] else "?",
        "items_count": cnt
    })

@flask_app.route("/api/admin/user_inventory/<int:user_id>")
def admin_user_inventory(user_id):
    items = db.get_user_inventory_full(user_id)
    return jsonify([{"id": i[0], "number": i[1], "country": i[2], "rarity": i[3], "buy_price": i[4]} for i in items])

@flask_app.route("/api/admin/remove_number", methods=["POST"])
def admin_remove_number():
    d = request.json
    db.remove_from_inventory(int(d["inventory_id"]), int(d["user_id"]))
    return jsonify({"success": True, "message": "Номер удалён!"})

@flask_app.route("/api/admin/give_number", methods=["POST"])
def admin_give_number():
    d = request.json
    db.give_number_to_user(int(d["user_id"]), d["number"].upper(), d["country"], d["rarity"], float(d["price"]))
    return jsonify({"success": True, "message": f"Номер {d['number'].upper()} выдан!"})

@flask_app.route("/api/admin/broadcast", methods=["POST"])
def admin_broadcast():
    text = request.json.get("text", "").strip()
    if not text:
        return jsonify({"success": False, "message": "Текст пуст!"})
    conn = db.get_conn()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS pending_broadcasts (id SERIAL PRIMARY KEY, text TEXT, sent INTEGER DEFAULT 0)")
    c.execute("INSERT INTO pending_broadcasts (text) VALUES (%s)", (text,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Рассылка поставлена в очередь! Отправится в течение минуты."})


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
        f"🇷🇺 Россия | 🇧🇾 Беларусь | 🇺🇦 Украина | 🇰🇿 Казахстан\n\n"
        f"Открывай номера, продавай на рынке, соревнуйся в топе!",
        parse_mode="HTML", reply_markup=keyboard
    )

async def broadcast_sender():
    while True:
        try:
            conn = db.get_conn()
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS pending_broadcasts (id SERIAL PRIMARY KEY, text TEXT, sent INTEGER DEFAULT 0)")
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
                c.execute("UPDATE pending_broadcasts SET sent = 1 WHERE id = %s", (bid,))
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
    asyncio.create_task(broadcast_sender())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
