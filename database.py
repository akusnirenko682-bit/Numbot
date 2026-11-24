import sqlite3
import random
from datetime import datetime

DB_NAME = "numbers.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 1000.0,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS shop_numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number TEXT UNIQUE,
        rarity TEXT,
        price REAL,
        is_sold INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        number TEXT,
        rarity TEXT,
        buy_price REAL,
        buy_date TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )''')
    conn.commit()
    conn.close()


def get_or_create_user(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, username, balance, created_at) VALUES (?, ?, ?, ?)",
                  (user_id, username, 1000.0, datetime.now().isoformat()))
        conn.commit()
        user = (user_id, username, 1000.0, datetime.now().isoformat())
    conn.close()
    return user


def get_balance(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0


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


def generate_number():
    letters = "АВЕКМНОРСТУХ"
    digits = "0123456789"
    letter1 = random.choice(letters)
    digits_part = "".join(random.choices(digits, k=3))
    letter2 = random.choice(letters)
    letter3 = random.choice(letters)
    region = random.randint(1, 199)
    return f"{letter1}{digits_part}{letter2}{letter3}{region:02d}"


def get_rarity(number):
    digits = "".join(c for c in number if c.isdigit())
    letters = "".join(c for c in number if c.isalpha())
    rarity = "Обычный"
    price = random.randint(100, 500)
    if digits[0] == digits[1] == digits[2]:
        rarity = "Редкий"
        price = random.randint(1000, 3000)
    elif digits[0] == digits[1] or digits[1] == digits[2]:
        rarity = "Необычный"
        price = random.randint(500, 1000)
    if digits == digits[::-1]:
        rarity = "Эпический"
        price = random.randint(3000, 8000)
    if digits[0] == digits[1] == digits[2] and len(letters) >= 3 and letters[0] == letters[1] == letters[2]:
        rarity = "Легендарный"
        price = random.randint(10000, 50000)
    return rarity, price


def add_number_to_shop():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    while True:
        number = generate_number()
        c.execute("SELECT id FROM shop_numbers WHERE number = ?", (number,))
        if not c.fetchone():
            break
    rarity, price = get_rarity(number)
    c.execute("INSERT INTO shop_numbers (number, rarity, price) VALUES (?, ?, ?)",
              (number, rarity, price))
    conn.commit()
    conn.close()
    return number, rarity, price


def get_shop_numbers(limit=10):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM shop_numbers WHERE is_sold = 0 ORDER BY RANDOM() LIMIT ?", (limit,))
    result = c.fetchall()
    conn.close()
    return result


def buy_number(user_id, number_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM shop_numbers WHERE id = ? AND is_sold = 0", (number_id,))
    num = c.fetchone()
    if not num:
        conn.close()
        return False, "Номер уже продан!"
    _, number, rarity, price, _ = num
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = c.fetchone()[0]
    if balance < price:
        conn.close()
        return False, f"Недостаточно средств! Нужно {price}₽, у тебя {balance}₽"
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))
    c.execute("UPDATE shop_numbers SET is_sold = 1 WHERE id = ?", (number_id,))
    c.execute("INSERT INTO inventory (user_id, number, rarity, buy_price, buy_date) VALUES (?, ?, ?, ?, ?)",
              (user_id, number, rarity, price, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True, f"Куплен номер {number} ({rarity}) за {price}₽!"


def get_user_inventory(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM inventory WHERE user_id = ?", (user_id,))
    result = c.fetchall()
    conn.close()
    return result


def sell_number(user_id, inventory_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM inventory WHERE id = ? AND user_id = ?", (inventory_id, user_id))
    item = c.fetchone()
    if not item:
        conn.close()
        return False, "Этот номер тебе не принадлежит!"
    _, _, number, rarity, buy_price, _ = item
    sell_price = int(buy_price * 0.8)
    c.execute("DELETE FROM inventory WHERE id = ?", (inventory_id,))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (sell_price, user_id))
    conn.commit()
    conn.close()
    return True, f"Номер {number} продан за {sell_price}₽!"


# --- АДМИН-ФУНКЦИИ ---

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC")
    result = c.fetchall()
    conn.close()
    return result


def get_user_info(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if user:
        c.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ?", (user_id,))
        items_count = c.fetchone()[0]
        conn.close()
        return user, items_count
    conn.close()
    return None, 0


def give_number_to_user(user_id, number, rarity, price):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO inventory (user_id, number, rarity, buy_price, buy_date) VALUES (?, ?, ?, ?, ?)",
              (user_id, number, rarity, price, datetime.now().isoformat()))
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
    result = c.fetchall()
    conn.close()
    return result


def send_message_to_all(message_text):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    result = c.fetchall()
    conn.close()
    return [row[0] for row in result]


init_db()
