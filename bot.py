import asyncio
import os
from threading import Thread
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import F
from flask import Flask, jsonify, request
import database as db
from config import BOT_TOKEN, ADMIN_IDS, PORT

flask_app = Flask(__name__, static_folder='static')

@flask_app.route("/")
def home(): return "✅ Nova Bot работает!"
@flask_app.route("/health")
def health(): return "OK"
@flask_app.route("/app")
def webapp(): return flask_app.send_static_file('index.html')

@flask_app.route("/api/user/<int:user_id>")
def get_user(user_id):
    db.get_or_create_user(user_id, request.args.get("username"))
    db.update_last_seen(user_id)
    can, wait = db.can_issue(user_id)
    return jsonify({"balance": db.get_balance(user_id), "is_admin": user_id in ADMIN_IDS,
                    "issue_price": db.get_issue_price(user_id), "can_issue": can, "issue_wait": wait})

@flask_app.route("/api/issue/<int:user_id>/<country>", methods=["POST"])
def issue_api(user_id, country):
    can, wait = db.can_issue(user_id)
    if not can: return jsonify({"success": False, "message": f"Подожди {wait} сек!"})
    country_map = {"ru": "Россия", "by": "Беларусь", "ua": "Украина", "kz": "Казахстан"}
    country_name = country_map.get(country, "Россия")
    price = db.get_issue_price(user_id)
    if db.get_balance(user_id) < price: return jsonify({"success": False, "message": f"Нужно {price}₽"})
    db.add_balance(user_id, -price)
    db.set_last_issue(user_id)
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
    rarity = request.json.get("rarity", "all")
    s, m = db.auto_sell_by_rarity(user_id, rarity)
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

@flask_app.route("/api/market/remove/<int:user_id>/<int:listing_id>", methods=["POST"])
def remove_market_api(user_id, listing_id):
    is_admin = user_id in ADMIN_IDS
    s, m = db.remove_market_listing(listing_id, user_id, is_admin)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/market/buy/<int:buyer_id>/<int:listing_id>", methods=["POST"])
def buy_from_market_api(buyer_id, listing_id):
    s, m = db.buy_from_market(buyer_id, listing_id)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/bonus/<int:user_id>", methods=["POST"])
def bonus_api(user_id):
    can, wait = db.can_get_bonus(user_id)
    if not can: return jsonify({"success": False, "message": f"Бонус через {wait}"})
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
    days = int(request.json.get("days", 7))
    s, m = db.deposit_safe(user_id, amount, days)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/safe/withdraw/<int:user_id>", methods=["POST"])
def withdraw_api(user_id):
    is_admin = user_id in ADMIN_IDS
    s, m = db.withdraw_safe(user_id, is_admin)
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

@flask_app.route("/api/auctions/remove/<int:user_id>/<int:lot_id>", methods=["POST"])
def remove_auction_api(user_id, lot_id):
    is_admin = user_id in ADMIN_IDS
    s, m = db.remove_auction_listing(lot_id, user_id, is_admin)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/auctions/bid/<int:user_id>/<int:lot_id>", methods=["POST"])
def bid_api(user_id, lot_id):
    bid = float(request.json.get("bid", 0))
    s, m = db.make_bid(user_id, lot_id, bid)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/daily/<int:user_id>")
def daily_api(user_id):
    can, wait = db.can_claim_daily_case(user_id)
    conn = db.get_conn(); c = conn.cursor()
    try:
        c.execute("SELECT streak FROM daily_case WHERE user_id = %s", (user_id,))
        r = c.fetchone(); streak = r[0] if r else 0
    except: streak = 0
    conn.close()
    return jsonify({"can_claim": can, "wait": wait, "streak": streak})

@flask_app.route("/api/daily/claim/<int:user_id>", methods=["POST"])
def daily_claim_api(user_id):
    success, msg = db.claim_daily_case(user_id)
    if success and "Выбит" in msg:
        parts = msg.split()
        number = parts[1] if len(parts) > 1 else ""
        rarity = parts[2].replace("(", "").replace(")", "") if len(parts) > 2 else ""
        return jsonify({"success": True, "number": number, "rarity": rarity, "country": "Россия", "message": msg})
    return jsonify({"success": False, "message": msg})

@flask_app.route("/api/promos/active")
def active_promos():
    promos = db.get_active_promos()
    return jsonify([{"id": p[0], "code": p[1], "type": p[2], "reward_type": p[3], "reward_value": p[4], "max_uses": p[5], "current_uses": p[6]} for p in promos])

@flask_app.route("/api/promo/use/<int:user_id>/<code>", methods=["POST"])
def use_promo_api(user_id, code):
    s, m = db.use_promo_code(user_id, code)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/promo/delete/<code>", methods=["POST"])
def delete_promo_api(code):
    s, m = db.delete_promo_code(code)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/referral/<int:user_id>")
def referral_api(user_id):
    code = db.get_referral_code(user_id)
    count = db.get_referral_stats(user_id)
    return jsonify({"code": code, "count": count})

@flask_app.route("/api/season/<int:user_id>")
def season_api(user_id):
    return jsonify(db.get_season_info(user_id))

@flask_app.route("/api/channel/check/<int:user_id>")
def channel_check(user_id):
    return jsonify({"subscribed": db.check_channel_subscription(user_id)})

@flask_app.route("/api/channel/claim/<int:user_id>", methods=["POST"])
def channel_claim(user_id):
    s, m = db.give_channel_bonus(user_id)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/users/online")
def users_online():
    users = db.get_all_users()
    return jsonify([{"user_id": u[0], "username": u[1], "balance": u[2], "online": db.is_user_online(u[0])} for u in users])

# ===== ТРЕЙДЫ API =====

@flask_app.route("/api/trades/users/<int:user_id>")
def trade_users(user_id):
    users = db.get_online_users(user_id)
    return jsonify(users)

@flask_app.route("/api/trades/inventory/<int:user_id>")
def trade_inventory(user_id):
    items = db.get_user_inventory_for_trade(user_id)
    return jsonify(items)

@flask_app.route("/api/trades/create/<int:user_id>", methods=["POST"])
def create_trade_api(user_id):
    d = request.json
    receiver_id = int(d.get("receiver_id"))
    money = float(d.get("money", 0))
    items = d.get("items", [])
    success, trade_id, msg = db.create_trade(user_id, receiver_id, money, items)
    if success:
        conn = db.get_conn(); c = conn.cursor()
        c.execute("SELECT username FROM users WHERE user_id = %s", (user_id,))
        sender_name = c.fetchone()[0] or f"User{user_id}"
        conn.close()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    send_trade_notification(receiver_id, sender_name, trade_id, money, len(items)),
                    loop
                )
            else:
                loop.run_until_complete(send_trade_notification(receiver_id, sender_name, trade_id, money, len(items)))
        except Exception as e:
            print(f"Trade notification error: {e}")
    return jsonify({"success": success, "message": msg})

@flask_app.route("/api/trades/pending/<int:user_id>")
def pending_trades(user_id):
    trades = db.get_pending_trades(user_id)
    result = []
    for t in trades:
        result.append({"id": t[0], "sender_id": t[1], "sender_name": t[2], "money": t[3], "items": t[4], "expires_at": t[5]})
    return jsonify(result)

@flask_app.route("/api/trades/accept/<int:user_id>/<int:trade_id>", methods=["POST"])
def accept_trade_api(user_id, trade_id):
    s, m = db.accept_trade(trade_id, user_id)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/trades/decline/<int:user_id>/<int:trade_id>", methods=["POST"])
def decline_trade_api(user_id, trade_id):
    s, m = db.decline_trade(trade_id, user_id)
    return jsonify({"success": s, "message": m})

# ===== АДМИН API =====

@flask_app.route("/api/admin/stats")
def admin_stats():
    users = db.get_all_users()
    conn = db.get_conn(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM inventory"); total_inv = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM market"); total_market = c.fetchone()[0]
    conn.close()
    return jsonify({"total_users": len(users), "total_balance": sum(u[2] for u in users),
                    "total_inventory": total_inv, "total_market": total_market})

@flask_app.route("/api/admin/users")
def admin_users():
    users = db.get_all_users()
    return jsonify([{"user_id": u[0], "username": u[1], "balance": u[2], "online": db.is_user_online(u[0])} for u in users])

@flask_app.route("/api/admin/give_money", methods=["POST"])
def admin_give_money():
    d = request.json; amount = float(d["amount"])
    if amount <= 0: return jsonify({"success": False, "message": "Сумма > 0!"})
    db.add_balance(int(d["user_id"]), amount)
    nb = db.get_balance(int(d["user_id"]))
    return jsonify({"success": True, "message": f"Выдано {amount}₽. Баланс: {nb}₽"})

@flask_app.route("/api/admin/take_money", methods=["POST"])
def admin_take_money():
    d = request.json; user_id = int(d["user_id"]); amount = float(d["amount"])
    if amount <= 0: return jsonify({"success": False, "message": "Сумма > 0!"})
    cur = db.get_balance(user_id)
    if cur < amount: return jsonify({"success": False, "message": f"У игрока только {cur}₽!"})
    db.add_balance(user_id, -amount)
    nb = db.get_balance(user_id)
    return jsonify({"success": True, "message": f"Списано {amount}₽. Баланс: {nb}₽"})

@flask_app.route("/api/admin/set_balance", methods=["POST"])
def admin_set_balance():
    d = request.json; amount = float(d["amount"])
    if amount < 0: return jsonify({"success": False, "message": "Баланс >= 0!"})
    db.set_balance(int(d["user_id"]), amount)
    return jsonify({"success": True, "message": f"Баланс: {amount}₽"})

@flask_app.route("/api/admin/user_info/<int:user_id>")
def admin_user_info(user_id):
    user, cnt = db.get_user_info(user_id)
    if not user: return jsonify({"success": False, "message": f"Игрок {user_id} не найден!"})
    return jsonify({"success": True, "user_id": user[0], "username": user[1] or "нет",
                    "balance": user[2], "created_at": user[3][:10] if user[3] else "?", "items_count": cnt})

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

@flask_app.route("/api/admin/create_promo", methods=["POST"])
def admin_create_promo():
    d = request.json
    code = d.get("code", "").strip().upper()
    promo_type = d.get("type", "money")
    reward_value = float(d.get("reward_value", 0))
    max_uses = int(d.get("max_uses", 0))
    if not code or reward_value <= 0: return jsonify({"success": False, "message": "Заполни код и сумму!"})
    reward_type = "money" if promo_type == "money" else "case"
    s, m = db.create_promo_code(code, promo_type, reward_type, reward_value, max_uses)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/admin/delete_promo/<code>", methods=["POST"])
def admin_delete_promo(code):
    s, m = db.delete_promo_code(code)
    return jsonify({"success": s, "message": m})

@flask_app.route("/api/admin/broadcast", methods=["POST"])
def admin_broadcast():
    text = request.json.get("text", "").strip()
    if not text: return jsonify({"success": False, "message": "Текст пуст!"})
    conn = db.get_conn(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS pending_broadcasts (id SERIAL PRIMARY KEY, text TEXT, sent INTEGER DEFAULT 0)")
    c.execute("INSERT INTO pending_broadcasts (text) VALUES (%s)", (text,))
    conn.commit(); conn.close()
    return jsonify({"success": True, "message": "Рассылка в очереди!"})

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def send_trade_notification(receiver_id, sender_name, trade_id, money, items_count):
    text = f"🤝 <b>Новый трейд!</b>\n\n"
    text += f"👤 <b>{sender_name}</b> предлагает вам трейд #{trade_id}\n"
    if money > 0: text += f"💰 Деньги: <b>{int(money)}₽</b>\n"
    if items_count > 0: text += f"🎒 Номеров: <b>{items_count}</b>\n"
    text += f"\n⏰ Действует 5 минут"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"trade_accept_{trade_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"trade_decline_{trade_id}")]
    ])
    try:
        await bot.send_message(receiver_id, text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        print(f"Trade notification error: {e}")

@dp.callback_query(F.data.startswith("trade_accept_"))
async def trade_accept_callback(callback: CallbackQuery):
    trade_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    success, msg = db.accept_trade(trade_id, user_id)
    await callback.answer(msg, show_alert=True)
    if success:
        await callback.message.edit_text(f"✅ Трейд #{trade_id} принят!")

@dp.callback_query(F.data.startswith("trade_decline_"))
async def trade_decline_callback(callback: CallbackQuery):
    trade_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    success, msg = db.decline_trade(trade_id, user_id)
    await callback.answer(msg, show_alert=True)
    if success:
        await callback.message.edit_text(f"❌ Трейд #{trade_id} отклонён!")

@dp.message(CommandStart(deep_link=True))
async def cmd_start_referral(message: Message):
    args = message.text.split(maxsplit=1)
    referred_by = None
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_code = args[1][4:]
        conn = db.get_conn(); c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE referral_code = %s", (ref_code,))
        r = c.fetchone(); conn.close()
        if r: referred_by = r[0]
    db.get_or_create_user(message.from_user.id, message.from_user.username, referred_by)
    hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=f"https://{hostname}/app"))]
    ])
    ref_text = "\n\n🎁 Друг пригласил тебя! +2000₽!" if referred_by else ""
    await message.answer(f"🚗 <b>Добро пожаловать в Nova Bot!</b>{ref_text}\n\n🇷🇺 Россия | 🇧🇾 Беларусь | 🇺🇦 Украина | 🇰🇿 Казахстан",
                         parse_mode="HTML", reply_markup=keyboard)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    db.get_or_create_user(message.from_user.id, message.from_user.username)
    hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=f"https://{hostname}/app"))]
    ])
    await message.answer(f"🚗 <b>Добро пожаловать в Nova Bot!</b>\n\n🇷🇺 Россия | 🇧🇾 Беларусь | 🇺🇦 Украина | 🇰🇿 Казахстан",
                         parse_mode="HTML", reply_markup=keyboard)

async def broadcast_sender():
    while True:
        try:
            conn = db.get_conn(); c = conn.cursor()
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
                    except: failed += 1
                c.execute("UPDATE pending_broadcasts SET sent = 1 WHERE id = %s", (bid,))
                conn.commit()
                print(f"📢 Рассылка #{bid}: {sent} ок, {failed} ошибок")
            conn.close()
        except Exception as e: print(f"Broadcast error: {e}")
        await asyncio.sleep(30)

async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Веб-сервер запущен"); print("🤖 Бот запущен!")
    asyncio.create_task(broadcast_sender())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
