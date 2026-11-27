import os
import random
import string
from datetime import datetime, timedelta
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode='require')


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        balance DOUBLE PRECISION DEFAULT 1000.0,
        created_at TEXT,
        last_bonus TEXT,
        referral_code TEXT,
        referred_by BIGINT,
        channel_bonus BOOLEAN DEFAULT FALSE
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        number TEXT,
        country TEXT,
        rarity TEXT,
        buy_price DOUBLE PRECISION,
        buy_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS market (
        id SERIAL PRIMARY KEY,
        seller_id BIGINT,
        number TEXT,
        country TEXT,
        rarity TEXT,
        price DOUBLE PRECISION,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        date TEXT,
        task_key TEXT,
        progress INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS safe (
        user_id BIGINT PRIMARY KEY,
        amount DOUBLE PRECISION DEFAULT 0,
        deposit_time TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS upgrades (
        user_id BIGINT PRIMARY KEY,
        bonus_level INTEGER DEFAULT 0,
        discount_level INTEGER DEFAULT 0,
        luck_level INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS auction (
        id SERIAL PRIMARY KEY,
        seller_id BIGINT,
        number TEXT,
        country TEXT,
        rarity TEXT,
        min_price DOUBLE PRECISION,
        current_bid DOUBLE PRECISION,
        current_bidder BIGINT,
        ends_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (
        id SERIAL PRIMARY KEY,
        code TEXT UNIQUE,
        reward_type TEXT,
        reward_value DOUBLE PRECISION,
        max_uses INTEGER DEFAULT 0,
        current_uses INTEGER DEFAULT 0,
        created_at TEXT,
        expires_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_uses (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        promo_id INTEGER,
        used_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_case (
        user_id BIGINT PRIMARY KEY,
        last_claim TEXT,
        streak INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS season_pass (
        user_id BIGINT PRIMARY KEY,
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        last_updated TEXT
    )''')
    conn.commit()
    conn.close()


def get_or_create_user(user_id, username, referred_by=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = c.fetchone()
    if not user:
        now = datetime.now().isoformat()
        ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        c.execute("INSERT INTO users (user_id, username, balance, created_at, last_bonus, referral_code, referred_by) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                  (user_id, username, 1000.0, now, now, ref_code, referred_by))
        c.execute("INSERT INTO upgrades (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
        c.execute("INSERT INTO season_pass (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
        if referred_by:
            c.execute("UPDATE users SET balance = balance + 2000 WHERE user_id = %s", (user_id,))
            c.execute("UPDATE users SET balance = balance + 2000 WHERE user_id = %s", (referred_by,))
        conn.commit()
    conn.close()


def get_balance(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else 0


def add_balance(user_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, user_id))
    conn.commit()
    conn.close()


def set_balance(user_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = %s WHERE user_id = %s", (amount, user_id))
    conn.commit()
    conn.close()


def gen_ru():
    L = "АВЕКМНОРСТУХ"
    return f"{random.choice(L)}{''.join(random.choices('0123456789', k=3))}{random.choice(L)}{random.choice(L)}{random.randint(1,199):02d}"

def gen_by():
    L = "АВЕКМНОРСТУХ"
    return f"{''.join(random.choices('0123456789', k=4))}{random.choice(L)}{random.choice(L)}-{random.randint(1,7)}"

def gen_ua():
    L = "АВЕКМНОРСТУХІ"
    return f"{random.choice(L)}{random.choice(L)}{''.join(random.choices('0123456789', k=4))}{random.choice(L)}{random.choice(L)}"

def gen_kz():
    L = "АВЕКМНОРСТУХ"
    return f"{random.choice(L)}{''.join(random.choices('0123456789', k=3))}{random.choice(L)}{random.choice(L)}{random.choice(L)}"


def generate_number(country):
    return {"Россия": gen_ru, "Беларусь": gen_by, "Украина": gen_ua, "Казахстан": gen_kz}.get(country, gen_ru)()


def get_rarity(number, luck=0):
    digits = "".join(c for c in number if c.isdigit())
    letters = "".join(c for c in number if c.isalpha())
    rarity, price = "Обычный", random.randint(100, 300)
    if len(digits) >= 2 and (digits[0] == digits[1] or digits[-1] == digits[-2]):
        rarity, price = "Необычный", random.randint(500, 1000)
    if len(digits) >= 3 and digits[0] == digits[1] == digits[2]:
        rarity, price = "Редкий", random.randint(1000, 3000)
    if len(digits) >= 3 and digits == digits[::-1]:
        rarity, price = "Эпический", random.randint(3000, 8000)
    if len(digits) >= 3 and len(set(digits)) == 1:
        rarity, price = "Легендарный", random.randint(10000, 50000)
    if len(letters) >= 3 and len(set(letters)) == 1:
        rarity, price = "Легендарный", random.randint(15000, 60000)
    if luck > 0 and rarity == "Обычный" and random.random() < 0.1 * luck:
        rarity, price = "Необычный", random.randint(500, 1000)
    return rarity, price


def get_upgrades(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT bonus_level, discount_level, luck_level FROM upgrades WHERE user_id = %s", (user_id,))
    r = c.fetchone()
    conn.close()
    if r:
        return {"bonus": r[0], "discount": r[1], "luck": r[2]}
    return {"bonus": 0, "discount": 0, "luck": 0}


def get_issue_price(user_id):
    up = get_upgrades(user_id)
    return max(200, 500 - up["discount"] * 50)


def issue_number(user_id, country):
    number = generate_number(country)
    up = get_upgrades(user_id)
    rarity, value = get_rarity(number, up["luck"])
    price = get_issue_price(user_id)
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO inventory (user_id, number, country, rarity, buy_price, buy_date) VALUES (%s, %s, %s, %s, %s, %s)",
              (user_id, number, country, rarity, value, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    update_task(user_id, "open", 1)
    add_season_xp(user_id, 10)
    return number, country, rarity, value, price


def get_user_inventory(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM inventory WHERE user_id = %s", (user_id,))
    r = c.fetchall()
    conn.close()
    return r


def sell_number(user_id, inventory_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM inventory WHERE id = %s AND user_id = %s", (inventory_id, user_id))
    item = c.fetchone()
    if not item:
        conn.close()
        return False, "Этот номер тебе не принадлежит!"
    _, _, number, country, rarity, buy_price, _ = item
    sell_price = int(buy_price * 0.8)
    c.execute("DELETE FROM inventory WHERE id = %s", (inventory_id,))
    c.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (sell_price, user_id))
    conn.commit()
    conn.close()
    update_task(user_id, "sell", 1)
    add_season_xp(user_id, 5)
    return True, f"Номер {number} ({country}) продан за {sell_price}₽!"


def auto_sell(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, buy_price FROM inventory WHERE user_id = %s AND rarity = 'Обычный'", (user_id,))
    items = c.fetchall()
    if not items:
        conn.close()
        return False, "Нет обычных номеров для продажи!"
    total = 0
    for iid, bp in items:
        total += int(bp * 0.8)
        c.execute("DELETE FROM inventory WHERE id = %s", (iid,))
    c.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (total, user_id))
    conn.commit()
    conn.close()
    return True, f"Продано {len(items)} номеров за {total}₽!"


def create_market_listing(user_id, inventory_id, price):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM inventory WHERE id = %s AND user_id = %s", (inventory_id, user_id))
    item = c.fetchone()
    if not item:
        conn.close()
        return False, "Этот номер тебе не принадлежит!"
    _, _, number, country, rarity, _, _ = item
    c.execute("DELETE FROM inventory WHERE id = %s", (inventory_id,))
    c.execute("INSERT INTO market (seller_id, number, country, rarity, price, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
              (user_id, number, country, rarity, price, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True, f"Номер {number} выставлен за {price}₽!"


def get_market_listings(limit=30):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM market ORDER BY price DESC LIMIT %s", (limit,))
    r = c.fetchall()
    conn.close()
    return r


def buy_from_market(buyer_id, listing_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM market WHERE id = %s", (listing_id,))
    listing = c.fetchone()
    if not listing:
        conn.close()
        return False, "Номер уже продан!"
    lid, seller_id, number, country, rarity, price, _ = listing
    c.execute("SELECT balance FROM users WHERE user_id = %s", (buyer_id,))
    balance = c.fetchone()[0]
    if balance < price:
        conn.close()
        return False, f"Недостаточно средств! Нужно {price}₽"
    c.execute("UPDATE users SET balance = balance - %s WHERE user_id = %s", (price, buyer_id))
    c.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (price, seller_id))
    c.execute("DELETE FROM market WHERE id = %s", (listing_id,))
    c.execute("INSERT INTO inventory (user_id, number, country, rarity, buy_price, buy_date) VALUES (%s, %s, %s, %s, %s, %s)",
              (buyer_id, number, country, rarity, price, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    add_season_xp(buyer_id, 15)
    return True, f"Куплен номер {number} за {price}₽!"


def can_get_bonus(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT last_bonus FROM users WHERE user_id = %s", (user_id,))
    r = c.fetchone()
    conn.close()
    if not r or not r[0]:
        return True, 0
    last = datetime.fromisoformat(r[0])
    diff = datetime.now() - last
    if diff >= timedelta(hours=24):
        return True, 0
    remaining = timedelta(hours=24) - diff
    hours = int(remaining.total_seconds() // 3600)
    minutes = int((remaining.total_seconds() % 3600) // 60)
    return False, f"{hours}ч {minutes}м"


def give_bonus(user_id):
    up = get_upgrades(user_id)
    bonus = random.randint(100 + up["bonus"] * 100, 500 + up["bonus"] * 300)
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + %s, last_bonus = %s WHERE user_id = %s",
              (bonus, datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()
    update_task(user_id, "bonus", 1)
    add_season_xp(user_id, 20)
    return bonus


TASKS = [
    {"key": "open", "name": "Открой 3 номера", "target": 3, "reward": 500},
    {"key": "sell", "name": "Продай 2 номера", "target": 2, "reward": 300},
    {"key": "bonus", "name": "Забери бонус", "target": 1, "reward": 200},
]


def get_or_create_tasks(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT task_key, progress, completed FROM tasks WHERE user_id = %s AND date = %s", (user_id, today))
    rows = c.fetchall()
    existing = {r[0]: (r[1], r[2]) for r in rows}
    result = []
    for t in TASKS:
        if t["key"] not in existing:
            c.execute("INSERT INTO tasks (user_id, date, task_key, progress, completed) VALUES (%s, %s, %s, 0, 0)",
                      (user_id, today, t["key"]))
            conn.commit()
            progress, completed = 0, 0
        else:
            progress, completed = existing[t["key"]]
        result.append({**t, "progress": progress, "completed": bool(completed)})
    conn.close()
    return result


def update_task(user_id, key, amount=1):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT progress, completed FROM tasks WHERE user_id = %s AND date = %s AND task_key = %s",
              (user_id, today, key))
    r = c.fetchone()
    if r and not r[1]:
        target = next(t["target"] for t in TASKS if t["key"] == key)
        new_progress = min(r[0] + amount, target)
        completed = 1 if new_progress >= target else 0
        c.execute("UPDATE tasks SET progress = %s, completed = %s WHERE user_id = %s AND date = %s AND task_key = %s",
                  (new_progress, completed, user_id, today, key))
        conn.commit()
    conn.close()


def claim_task(user_id, key):
    today = datetime.now().strftime("%Y-%m-%d")
    task = next((t for t in TASKS if t["key"] == key), None)
    if not task:
        return False, "Задание не найдено!"
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT progress, completed FROM tasks WHERE user_id = %s AND date = %s AND task_key = %s",
              (user_id, today, key))
    r = c.fetchone()
    if not r:
        conn.close()
        return False, "Задание не найдено!"
    progress, completed = r
    if completed:
        conn.close()
        return False, "Награда уже получена!"
    if progress < task["target"]:
        conn.close()
        return False, f"Прогресс: {progress}/{task['target']}"
    c.execute("UPDATE tasks SET completed = 1 WHERE user_id = %s AND date = %s AND task_key = %s",
              (user_id, today, key))
    c.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (task["reward"], user_id))
    conn.commit()
    conn.close()
    add_season_xp(user_id, 30)
    return True, f"Получено {task['reward']}₽!"


def deposit_safe(user_id, amount):
    if amount <= 0:
        return False, "Сумма должна быть больше 0!"
    balance = get_balance(user_id)
    if balance < amount:
        return False, f"Недостаточно средств! Баланс: {balance}₽"
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO safe (user_id, amount, deposit_time) VALUES (%s, %s, %s) "
              "ON CONFLICT (user_id) DO UPDATE SET amount = safe.amount + %s",
              (user_id, amount, datetime.now().isoformat(), amount))
    c.execute("UPDATE users SET balance = balance - %s WHERE user_id = %s", (amount, user_id))
    conn.commit()
    conn.close()
    return True, f"Внесено {amount}₽ в сейф!"


def get_safe(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT amount, deposit_time FROM safe WHERE user_id = %s", (user_id,))
    r = c.fetchone()
    conn.close()
    if not r:
        return {"amount": 0, "interest": 0}
    amount, dep_time = r
    hours = (datetime.now() - datetime.fromisoformat(dep_time)).total_seconds() / 3600
    interest = int(amount * 0.005 * hours)
    return {"amount": amount, "interest": interest}


def withdraw_safe(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT amount, deposit_time FROM safe WHERE user_id = %s", (user_id,))
    r = c.fetchone()
    if not r:
        conn.close()
        return False, "Сейф пуст!"
    amount, dep_time = r
    hours = (datetime.now() - datetime.fromisoformat(dep_time)).total_seconds() / 3600
    interest = int(amount * 0.005 * hours)
    total = amount + interest
    c.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (total, user_id))
    c.execute("UPDATE safe SET amount = 0, deposit_time = %s WHERE user_id = %s",
              (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()
    return True, f"Забрано {total}₽ (включая {interest}₽ процентов)!"


UPGRADES_INFO = {
    "bonus": {"name": "💰 Бонус+", "desc": "Увеличивает ежедневный бонус", "base_price": 2000, "max": 5},
    "discount": {"name": "🏷️ Скидка", "desc": "Уменьшает цену выдачи на 50₽ за уровень", "base_price": 5000, "max": 5},
    "luck": {"name": "🍀 Удача", "desc": "Повышает шанс редких номеров", "base_price": 10000, "max": 5},
}


def buy_upgrade(user_id, key):
    info = UPGRADES_INFO.get(key)
    if not info:
        return False, "Неизвестное улучшение!"
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"SELECT {key}_level FROM upgrades WHERE user_id = %s", (user_id,))
    r = c.fetchone()
    if not r:
        c.execute("INSERT INTO upgrades (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
        conn.commit()
        current = 0
    else:
        current = r[0]
    if current >= info["max"]:
        conn.close()
        return False, "Максимальный уровень достигнут!"
    price = info["base_price"] * (current + 1)
    c.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
    balance = c.fetchone()[0]
    if balance < price:
        conn.close()
        return False, f"Нужно {price}₽, у тебя {balance}₽"
    c.execute("UPDATE users SET balance = balance - %s WHERE user_id = %s", (price, user_id))
    c.execute(f"UPDATE upgrades SET {key}_level = {key}_level + 1 WHERE user_id = %s", (user_id,))
    conn.commit()
    conn.close()
    add_season_xp(user_id, 50)
    return True, f"Улучшение {info['name']} куплено за {price}₽! Уровень: {current + 1}"


def get_upgrades_status(user_id):
    up = get_upgrades(user_id)
    result = {}
    for key, info in UPGRADES_INFO.items():
        lvl = up.get(key, 0)
        result[key] = {
            "name": info["name"],
            "desc": info["desc"],
            "level": lvl,
            "max": info["max"],
            "price": info["base_price"] * (lvl + 1) if lvl < info["max"] else None
        }
    return result


def create_auction(user_id, inventory_id, min_price):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM inventory WHERE id = %s AND user_id = %s", (inventory_id, user_id))
    item = c.fetchone()
    if not item:
        conn.close()
        return False, "Номер не найден!"
    _, _, number, country, rarity, _, _ = item
    c.execute("DELETE FROM inventory WHERE id = %s", (inventory_id,))
    ends = (datetime.now() + timedelta(hours=1)).isoformat()
    c.execute("INSERT INTO auction (seller_id, number, country, rarity, min_price, current_bid, current_bidder, ends_at) "
              "VALUES (%s, %s, %s, %s, %s, %s, NULL, %s)",
              (user_id, number, country, rarity, min_price, min_price, ends))
    conn.commit()
    conn.close()
    return True, "Лот выставлен на аукцион на 1 час!"


def get_auctions():
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("SELECT * FROM auction WHERE ends_at > %s ORDER BY ends_at ASC", (now,))
    r = c.fetchall()
    c.execute("SELECT * FROM auction WHERE ends_at <= %s", (now,))
    expired = c.fetchall()
    for lot in expired:
        lid, seller_id, number, country, rarity, min_p, cur_bid, bidder, ends = lot
        if bidder:
            c.execute("INSERT INTO inventory (user_id, number, country, rarity, buy_price, buy_date) VALUES (%s, %s, %s, %s, %s, %s)",
                      (bidder, number, country, rarity, cur_bid, datetime.now().isoformat()))
        else:
            c.execute("INSERT INTO inventory (user_id, number, country, rarity, buy_price, buy_date) VALUES (%s, %s, %s, %s, %s, %s)",
                      (seller_id, number, country, rarity, min_p, datetime.now().isoformat()))
        c.execute("DELETE FROM auction WHERE id = %s", (lid,))
    conn.commit()
    conn.close()
    return r


def make_bid(user_id, lot_id, bid):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM auction WHERE id = %s", (lot_id,))
    lot = c.fetchone()
    if not lot:
        conn.close()
        return False, "Лот не найден!"
    lid, seller_id, number, country, rarity, min_p, cur_bid, bidder, ends = lot
    if seller_id == user_id:
        conn.close()
        return False, "Нельзя делать ставку на свой лот!"
    if bid <= cur_bid:
        conn.close()
        return False, f"Ставка должна быть выше {cur_bid}₽!"
    c.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
    balance = c.fetchone()[0]
    if balance < bid:
        conn.close()
        return False, f"Недостаточно средств! Нужно {bid}₽"
    if bidder:
        c.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (cur_bid, bidder))
    c.execute("UPDATE auction SET current_bid = %s, current_bidder = %s WHERE id = %s", (bid, user_id, lot_id))
    c.execute("UPDATE users SET balance = balance - %s WHERE user_id = %s", (bid, user_id))
    conn.commit()
    conn.close()
    return True, f"Ставка {bid}₽ принята!"


def get_referral_code(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT referral_code FROM users WHERE user_id = %s", (user_id,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else None


def get_referral_stats(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by = %s", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count


def use_promo_code(user_id, code):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM promo_codes WHERE code = %s", (code.upper(),))
    promo = c.fetchone()
    if not promo:
        conn.close()
        return False, "Промокод не найден!"
    pid, pcode, reward_type, reward_value, max_uses, current_uses, created, expires = promo
    if datetime.fromisoformat(expires) < datetime.now():
        conn.close()
        return False, "Промокод истёк!"
    if max_uses > 0 and current_uses >= max_uses:
        conn.close()
        return False, "Лимит использований исчерпан!"
    c.execute("SELECT * FROM promo_uses WHERE user_id = %s AND promo_id = %s", (user_id, pid))
    if c.fetchone():
        conn.close()
        return False, "Ты уже использовал этот промокод!"
    c.execute("INSERT INTO promo_uses (user_id, promo_id, used_at) VALUES (%s, %s, %s)",
              (user_id, pid, datetime.now().isoformat()))
    c.execute("UPDATE promo_codes SET current_uses = current_uses + 1 WHERE id = %s", (pid,))
    if reward_type == "money":
        c.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (reward_value, user_id))
        msg = f"Получено {int(reward_value)}₽!"
    else:
        number, country, rarity, value, _ = issue_number(user_id, "Россия")
        msg = f"Выбит номер {number} ({rarity})!"
    conn.commit()
    conn.close()
    add_season_xp(user_id, 25)
    return True, msg


def can_claim_daily_case(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT last_claim FROM daily_case WHERE user_id = %s", (user_id,))
    r = c.fetchone()
    conn.close()
    if not r or not r[0]:
        return True, 0
    last = datetime.fromisoformat(r[0])
    diff = datetime.now() - last
    if diff >= timedelta(hours=24):
        return True, 0
    remaining = timedelta(hours=24) - diff
    hours = int(remaining.total_seconds() // 3600)
    minutes = int((remaining.total_seconds() % 3600) // 60)
    return False, f"{hours}ч {minutes}м"


def claim_daily_case(user_id):
    can, wait = can_claim_daily_case(user_id)
    if not can:
        return False, f"Следующий кейс через {wait}"
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT streak FROM daily_case WHERE user_id = %s", (user_id,))
    r = c.fetchone()
    streak = r[0] if r else 0
    streak = (streak + 1) % 7
    number, country, rarity, value, _ = issue_number(user_id, "Россия")
    c.execute("INSERT INTO daily_case (user_id, last_claim, streak) VALUES (%s, %s, %s) "
              "ON CONFLICT (user_id) DO UPDATE SET last_claim = %s, streak = %s",
              (user_id, datetime.now().isoformat(), streak, datetime.now().isoformat(), streak))
    conn.commit()
    conn.close()
    return True, f"Выбит {number} ({rarity})! Серия: {streak+1}/7"


def get_season_info(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT level, xp FROM season_pass WHERE user_id = %s", (user_id,))
    r = c.fetchone()
    conn.close()
    if r:
        level, xp = r
        xp_for_next = level * 100
        return {"level": level, "xp": xp, "xp_for_next": xp_for_next, "progress": min(100, (xp / xp_for_next) * 100)}
    return {"level": 1, "xp": 0, "xp_for_next": 100, "progress": 0}


def add_season_xp(user_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT level, xp FROM season_pass WHERE user_id = %s", (user_id,))
    r = c.fetchone()
    if r:
        level, xp = r
        new_xp = xp + amount
        xp_for_next = level * 100
        if new_xp >= xp_for_next:
            new_level = level + 1
            new_xp = new_xp - xp_for_next
            c.execute("UPDATE season_pass SET level = %s, xp = %s, last_updated = %s WHERE user_id = %s",
                      (new_level, new_xp, datetime.now().isoformat(), user_id))
            reward = new_level * 500
            c.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (reward, user_id))
        else:
            c.execute("UPDATE season_pass SET xp = %s, last_updated = %s WHERE user_id = %s",
                      (new_xp, datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()


def check_channel_subscription(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT channel_bonus FROM users WHERE user_id = %s", (user_id,))
    r = c.fetchone()
    conn.close()
    return bool(r and r[0])


def give_channel_bonus(user_id):
    if check_channel_subscription(user_id):
        return False, "Бонус уже получен!"
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + 10000, channel_bonus = TRUE WHERE user_id = %s", (user_id,))
    conn.commit()
    conn.close()
    return True, "🎉 Получено 10000₽ за подписку на канал!"


def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC")
    r = c.fetchall()
    conn.close()
    return r


def get_user_info(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = c.fetchone()
    if user:
        c.execute("SELECT COUNT(*) FROM inventory WHERE user_id = %s", (user_id,))
        cnt = c.fetchone()[0]
        conn.close()
        return user, cnt
    conn.close()
    return None, 0


def give_number_to_user(user_id, number, country, rarity, price):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO inventory (user_id, number, country, rarity, buy_price, buy_date) VALUES (%s, %s, %s, %s, %s, %s)",
              (user_id, number, country, rarity, price, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def remove_from_inventory(inventory_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM inventory WHERE id = %s AND user_id = %s", (inventory_id, user_id))
    conn.commit()
    conn.close()


def get_user_inventory_full(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM inventory WHERE user_id = %s", (user_id,))
    r = c.fetchall()
    conn.close()
    return r


def send_message_to_all():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    r = c.fetchall()
    conn.close()
    return [row[0] for row in r]


def get_top_balance(limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT %s", (limit,))
    r = c.fetchall()
    conn.close()
    return r


def get_top_rare_numbers(limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, COUNT(*) as rare_count
        FROM inventory
        WHERE rarity IN ('Легендарный', 'Эпический')
        GROUP BY user_id
        ORDER BY rare_count DESC
        LIMIT %s
    """, (limit,))
    r = c.fetchall()
    conn.close()
    return r


init_db()
