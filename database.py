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
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        number TEXT,
        country TEXT,
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


# ===== ГЕНЕРАЦИЯ НОМЕРОВ РАЗНЫХ СТРАН =====

def generate_russian_number():
    """Россия: А123БВ77"""
    letters = "АВЕКМНОРСТУХ"
    digits = "0123456789"
    letter1 = random.choice(letters)
    digits_part = "".join(random.choices(digits, k=3))
    letter2 = random.choice(letters)
    letter3 = random.choice(letters)
    region = random.randint(1, 199)
    return f"{letter1}{digits_part}{letter2}{letter3}{region:02d}"


def generate_belarus_number():
    """Беларусь: 1234АВ-5"""
    letters = "АВЕКМНОРСТУХ"
    digits = "0123456789"
    digits_part = "".join(random.choices(digits, k=4))
    letter1 = random.choice(letters)
    letter2 = random.choice(letters)
    region = random.randint(1, 7)
    return f"{digits_part}{letter1}{letter2}-{region}"


def generate_ukraine_number():
    """Украина: АА1234ВВ"""
    letters = "АВЕКМНОРСТУХІ"
    digits = "0123456789"
    letter1 = random.choice(letters)
    letter2 = random.choice(letters)
    digits_part = "".join(random.choices(digits, k=4))
    letter3 = random.choice(letters)
    letter4 = random.choice(letters)
    return f"{letter1}{letter2}{digits_part}{letter3}{letter4}"


def generate_kazakhstan_number():
    """Казахстан: А123ВСМ"""
    letters = "АВЕКМНОРСТУХ"
    digits = "0123456789"
    letter1 = random.choice(letters)
    digits_part = "".join(random.choices(digits, k=3))
    letter2 = random.choice(letters)
    letter3 = random.choice(letters)
    letter4 = random.choice(letters)
    return f"{letter1}{digits_part}{letter2}{letter3}{letter4}"


def generate_random_number():
    """Случайный номер из любой страны"""
    countries = ["Россия", "Беларусь", "Украина", "Казахстан"]
    country = random.choice(countries)
    
    if country == "Россия":
        number = generate_russian_number()
    elif country == "Беларусь":
        number = generate_belarus_number()
    elif country == "Украина":
        number = generate_ukraine_number()
    else:
        number = generate_kazakhstan_number()
    
    return country, number


def get_rarity(country, number):
    """Определяет редкость номера"""
    digits = "".join(c for c in number if c.isdigit())
    letters = "".join(c for c in number if c.isalpha())
    
    rarity = "Обычный"
    price = random.randint(100, 300)
    
    # Красивые цифры
    if len(digits) >= 3 and digits[0] == digits[1] == digits[2]:
        rarity = "Редкий"
        price = random.randint(1000, 3000)
    elif len(digits) >= 2 and (digits[0] == digits[1] or digits[-1] == digits[-2]):
        rarity = "Необычный"
        price = random.randint(500, 1000)
    
    # Зеркальные цифры
    if len(digits) >= 3 and digits == digits[::-1]:
        rarity = "Эпический"
        price = random.randint(3000, 8000)
    
    # Все одинаковые цифры
    if len(digits) >= 3 and len(set(digits)) == 1:
        rarity = "Легендарный"
        price = random.randint(10000, 50000)
    
    # Все одинаковые буквы
    if len(letters) >= 3 and len(set(letters)) == 1:
        rarity = "Легендарный"
        price = random.randint(15000, 60000)
    
    return rarity, price


def open_case(user_id):
    """Открыть кейс и получить случайный номер"""
    country, number = generate_random_number()
    rarity, price = get_rarity(country, number)
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO inventory (user_id, number, country, rarity, buy_price, buy_date) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, number, country, rarity, price, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return number, country, rarity, price


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
    _, _, number, country, rarity, buy_price, _ = item
    sell_price = int(buy_price * 0.8)
    c.execute("DELETE FROM inventory WHERE id = ?", (inventory_id,))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (sell_price, user_id))
    conn.commit()
    conn.close()
    return True, f"Номер {number} ({country}) продан за {sell_price}₽!"


# ===== АДМИН-ФУНКЦИИ =====

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
