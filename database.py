import sqlite3
import random
from datetime import datetime, timedelta

DB_NAME = "numbers.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE users ADD COLUMN last_bonus TEXT")
    except:
        pass
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 1000.0,
        created_at TEXT,
        last_bonus TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        number TEXT,
        country TEXT,
        rarity TEXT,
        buy_price REAL,
        buy_date TEXT
    )''')
    conn.commit()
    conn.close()

def get_or_create_user(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        now = datetime.now().isoformat()
        c.execute("INSERT INTO users (user_id, username, balance, created_at, last_bonus) VALUES (?, ?, ?, ?, ?)",
                  (user_id, username, 1000.0, now, now))
        conn.commit()
        user = (user_id, username, 1000.0, now, now)
    conn.close()
    return user

def get_balance(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else 0

def add_balance(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def set_balance(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# ===== ГЕНЕРАЦИЯ НОМЕРОВ =====

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
    if country == "Россия": return gen_ru()
    if country == "Беларусь": return gen_by()
    if country == "Украина": return gen_ua()
    if country == "Казахстан": return gen_kz()
    return gen_ru()

def get_rarity(number):
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
    return rarity, price

def issue_number(user_id, country, price=500):
    """Выдать случайный номер выбранной страны"""
    number = generate_number(country)
    rarity, value = get_rarity(number)
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO inventory (user_id, number, country, rarity, buy_price, buy_date) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, number, country, rarity, value, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return number, country, rarity, value

def get_user_inventory(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM inventory WHERE user_id = ?", (user_id,))
    r = c.fetchall()
    conn.close()
    return r

def sell_number(user_id, inventory_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM inventory WHERE id = ? AND user_id = ?", (inventory_id, user_id))
    item = c.fetchone()
    if not item:
        conn.close()
        return False, "Этот номер тебе не принадлежит!"
    _, _, number, country, rarity, buy_price, _ = item
    sell_price = int(buy_price * 0.8)
    c.execute("DELETE FROM inventory WHERE id = ?", (inventory_id,))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (sell_price, user_id))
    conn.commit()
    conn.close()
    return True, f"Номер {number} ({country}) продан за {sell_price}₽!"

# ===== БОНУС С КД =====

def can_get_bonus(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
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
    bonus = random.randint(100, 500)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ?, last_bonus = ? WHERE user_id = ?", 
              (bonus, datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()
    return bonus

# ===== АДМИН =====

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC")
    r = c.fetchall()
    conn.close()
    return r

def get_user_info(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if user:
        c.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ?", (user_id,))
        cnt = c.fetchone()[0]
        conn.close()
        return user, cnt
    conn.close()
    return None, 0

def give_number_to_user(user_id, number, country, rarity, price):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO inventory (user_id, number, country, rarity, buy_price, buy_date) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, number, country, rarity, price, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def remove_from_inventory(inventory_id, user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM inventory WHERE id = ? AND user_id = ?", (inventory_id, user_id))
    conn.commit()
    conn.close()

def get_user_inventory_full(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM inventory WHERE user_id = ?", (user_id,))
    r = c.fetchall()
    conn.close()
    return r

def send_message_to_all():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    r = c.fetchall()
    conn.close()
    return [row[0] for row in r]

init_db()
