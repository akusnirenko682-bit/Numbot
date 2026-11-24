import asyncio
import os
import random
from threading import Thread

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from flask import Flask

import database as db
from config import BOT_TOKEN, ADMIN_ID, PORT

# ===== Flask для Render =====
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ NumBot работает!"

@flask_app.route("/health")
def health():
    return "OK"

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

# ===== Telegram бот =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== FSM состояния =====
class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_amount = State()
    waiting_for_number = State()
    waiting_for_rarity = State()
    waiting_for_price = State()
    waiting_for_message = State()
    waiting_for_inventory_id = State()

# ===== ПРОВЕРКА АДМИНА =====
def is_admin(user_id):
    return user_id == ADMIN_ID

# ===== КОМАНДА /start =====
@dp.message(Command("start"))
async def cmd_start(message: Message):
    db.get_or_create_user(message.from_user.id, message.from_user.username)
    balance = db.get_balance(message.from_user.id)
    
    await message.answer(
        f"🚗 <b>Добро пожаловать в Numbers Bot!</b>\n\n"
        f"👤 @{message.from_user.username}\n"
        f"💰 Баланс: {balance}₽\n\n"
        f"Собирай редкие автономера!",
        parse_mode="HTML",
        reply_markup=main_menu()
    )

def main_menu():
    keyboard = [
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop"),
         InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
         InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ]
    
    # Кнопка админки только для админа
    if is_admin(message.from_user.id if 'message' in dir() else 0):
        keyboard.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Динамическое меню с проверкой админа
def get_main_menu(user_id):
    keyboard = [
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop"),
         InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
         InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ]
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ===== МАГАЗИН =====
@dp.callback_query(F.data == "shop")
async def shop_menu(callback: CallbackQuery):
    for _ in range(5):
        db.add_number_to_shop()
    
    shop_items = db.get_shop_numbers(5)
    
    text = "🛒 <b>Магазин автономеров</b>\n\n"
    keyboard = []
    
    for item in shop_items:
        item_id, number, rarity, price, _ = item
        emoji = {"Обычный": "⚪", "Необычный": "🟢", "Редкий": "🔵", 
                 "Эпический": "🟣", "Легендарный": "🟡"}.get(rarity, "⚪")
        text += f"{emoji} <b>{number}</b> — {rarity} — {price}₽\n"
        keyboard.append([InlineKeyboardButton(text=f"Купить {number}", callback_data=f"buy_{item_id}")])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back")])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data.startswith("buy_"))
async def buy_number(callback: CallbackQuery):
    number_id = int(callback.data.split("_")[1])
    success, msg = db.buy_number(callback.from_user.id, number_id)
    await callback.answer(msg, show_alert=True)
    if success:
        await shop_menu(callback)

# ===== ИНВЕНТАРЬ =====
@dp.callback_query(F.data == "inventory")
async def inventory_menu(callback: CallbackQuery):
    items = db.get_user_inventory(callback.from_user.id)
    
    if not items:
        text = "🎒 Инвентарь пуст!"
        keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="back")]]
    else:
        text = "🎒 <b>Твой инвентарь</b>\n\n"
        keyboard = []
        for item in items:
            item_id, _, number, rarity, buy_price, _ = item
            sell_price = int(buy_price * 0.8)
            text += f"🔸 <b>{number}</b> ({rarity})\n   Куплен: {buy_price}₽ | Продажа: {sell_price}₽\n\n"
            keyboard.append([InlineKeyboardButton(text=f"Продать {number}", callback_data=f"sell_{item_id}")])
        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back")])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data.startswith("sell_"))
async def sell_number(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    success, msg = db.sell_number(callback.from_user.id, item_id)
    await callback.answer(msg, show_alert=True)
    await inventory_menu(callback)

# ===== БАЛАНС =====
@dp.callback_query(F.data == "balance")
async def balance_menu(callback: CallbackQuery):
    balance = db.get_balance(callback.from_user.id)
    items = db.get_user_inventory(callback.from_user.id)
    total_value = sum(item[4] for item in items)
    
    text = (f"💰 <b>Твой баланс</b>\n\n"
            f"💵 Наличные: {balance}₽\n"
            f"🚗 Номеров: {len(items)}\n"
            f"📊 Стоимость коллекции: {total_value}₽\n"
            f"💎 Общий капитал: {balance + total_value}₽")
    
    keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="back")]]
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

# ===== БОНУС =====
@dp.callback_query(F.data == "bonus")
async def bonus_menu(callback: CallbackQuery):
    bonus = random.randint(100, 500)
    db.add_balance(callback.from_user.id, bonus)
    new_balance = db.get_balance(callback.from_user.id)
    
    text = f"🎁 Бонус <b>{bonus}₽</b>!\nБаланс: {new_balance}₽"
    keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="back")]]
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

# ===== ПОМОЩЬ =====
@dp.callback_query(F.data == "help")
async def help_menu(callback: CallbackQuery):
    text = ("ℹ️ <b>Как играть:</b>\n\n"
            "1️⃣ Магазин — покупай номера\n"
            "2️⃣ Инвентарь — продавай за 80%\n"
            "3️⃣ Бонус — получай деньги\n\n"
            "🏆 Редкость:\n"
            "⚪ Обычный — 100-500₽\n"
            "🟢 Необычный — 500-1000₽\n"
            "🔵 Редкий — 1000-3000₽\n"
            "🟣 Эпический — 3000-8000₽\n"
            "🟡 Легендарный — 10000-50000₽")
    keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="back")]]
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

# ===== НАЗАД =====
@dp.callback_query(F.data == "back")
async def back_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        f"🚗 <b>Numbers Bot</b>\n\n"
        f"👤 @{callback.from_user.username}\n"
        f"💰 Баланс: {db.get_balance(callback.from_user.id)}₽",
        parse_mode="HTML",
        reply_markup=get_main_menu(callback.from_user.id)
    )

# =====================================================
# ⚙️ АДМИН-ПАНЕЛЬ
# =====================================================

@dp.callback_query(F.data == "admin")
async def admin_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    
    text = (
        "⚙️ <b>Админ-панель</b>\n\n"
        "👥 <b>Пользователи:</b>\n"
        "• Выдать деньги\n"
        "• Списать деньги\n"
        "• Установить баланс\n"
        "• Посмотреть инфо\n"
        "• Посмотреть инвентарь\n"
        "• Удалить номер из инвентаря\n\n"
        "🚗 <b>Номера:</b>\n"
        "• Выдать номер\n\n"
        "📢 <b>Другое:</b>\n"
        "• Рассылка всем\n"
        "• Статистика бота"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="💰 Выдать деньги", callback_data="admin_give_money")],
        [InlineKeyboardButton(text="📉 Списать деньги", callback_data="admin_take_money")],
        [InlineKeyboardButton(text="⚖️ Установить баланс", callback_data="admin_set_balance")],
        [InlineKeyboardButton(text="👤 Инфо о пользователе", callback_data="admin_user_info")],
        [InlineKeyboardButton(text="🎒 Инвентарь пользователя", callback_data="admin_user_inv")],
        [InlineKeyboardButton(text="❌ Удалить номер", callback_data="admin_remove_number")],
        [InlineKeyboardButton(text="🚗 Выдать номер", callback_data="admin_give_number")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ]
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

# --- ВЫДАТЬ ДЕНЬГИ ---
@dp.callback_query(F.data == "admin_give_money")
async def admin_give_money_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("💰 <b>Выдача денег</b>\n\nВведите ID пользователя:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="give_money")

# --- СПИСАТЬ ДЕНЬГИ ---
@dp.callback_query(F.data == "admin_take_money")
async def admin_take_money_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("📉 <b>Списание денег</b>\n\nВведите ID пользователя:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="take_money")

# --- УСТАНОВИТЬ БАЛАНС ---
@dp.callback_query(F.data == "admin_set_balance")
async def admin_set_balance_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("⚖️ <b>Установка баланса</b>\n\nВведите ID пользователя:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="set_balance")

# --- ИНФО О ПОЛЬЗОВАТЕЛЕ ---
@dp.callback_query(F.data == "admin_user_info")
async def admin_user_info_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("👤 <b>Инфо о пользователе</b>\n\nВведите ID пользователя:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="user_info")

# --- ИНВЕНТАРЬ ПОЛЬЗОВАТЕЛЯ ---
@dp.callback_query(F.data == "admin_user_inv")
async def admin_user_inv_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🎒 <b>Инвентарь пользователя</b>\n\nВведите ID пользователя:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="user_inv")

# --- УДАЛИТЬ НОМЕР ---
@dp.callback_query(F.data == "admin_remove_number")
async def admin_remove_number_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("❌ <b>Удалить номер</b>\n\nВведите ID пользователя:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="remove_number")

# --- ВЫДАТЬ НОМЕР ---
@dp.callback_query(F.data == "admin_give_number")
async def admin_give_number_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🚗 <b>Выдать номер</b>\n\nВведите ID пользователя:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="give_number")

# --- РАССЫЛКА ---
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("📢 <b>Рассылка всем</b>\n\nВведите текст сообщения:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_message)

# --- СТАТИСТИКА ---
@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    users = db.get_all_users()
    total_users = len(users)
    total_balance = sum(u[2] for u in users)
    
    # Считаем номера в магазине
    conn = __import__('sqlite3').connect(db.DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM shop_numbers WHERE is_sold = 0")
    shop_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM inventory")
    total_inventory = c.fetchone()[0]
    conn.close()
    
    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"💰 Общий баланс всех: <b>{total_balance}₽</b>\n"
        f"🛒 Номеров в магазине: <b>{shop_count}</b>\n"
        f"🎒 Всего номеров в инвентарях: <b>{total_inventory}</b>"
    )
    
    keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="admin")]]
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

# =====================================================
# ОБРАБОТКА ВВОДА ДАННЫХ (FSM)
# =====================================================

@dp.message(AdminStates.waiting_for_user_id)
async def process_user_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ID должен быть числом! Попробуйте ещё раз:")
        return
    
    data = await state.get_data()
    action = data.get("action")
    await state.update_data(user_id=user_id)
    
    if action == "give_money":
        await message.answer("💰 Введите сумму для выдачи:")
        await state.set_state(AdminStates.waiting_for_amount)
    elif action == "take_money":
        await message.answer("📉 Введите сумму для списания:")
        await state.set_state(AdminStates.waiting_for_amount)
    elif action == "set_balance":
        await message.answer("⚖️ Введите новый баланс:")
        await state.set_state(AdminStates.waiting_for_amount)
    elif action == "user_info":
        user, items_count = db.get_user_info(user_id)
        if user:
            uid, username, balance, created = user
            text = (
                f"👤 <b>Информация о пользователе</b>\n\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"👤 Username: @{username or 'нет'}\n"
                f"💰 Баланс: {balance}₽\n"
                f"🎒 Номеров в инвентаре: {items_count}\n"
                f"📅 Регистрация: {created[:10]}"
            )
        else:
            text = f"❌ Пользователь с ID {user_id} не найден!"
        
        keyboard = [[InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin")]]
        await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await state.clear()
        
    elif action == "user_inv":
        items = db.get_user_inventory_full(user_id)
        if not items:
            text = f"🎒 Инвентарь пользователя {user_id} пуст!"
        else:
            text = f"🎒 <b>Инвентарь пользователя {user_id}</b>\n\n"
            keyboard = []
            for item in items:
                item_id, _, number, rarity, buy_price, _ = item
                text += f"🔸 <b>{number}</b> ({rarity}) — {buy_price}₽\n   ID: {item_id}\n\n"
                keyboard.append([InlineKeyboardButton(text=f"❌ Удалить {number}", callback_data=f"admin_del_{item_id}_{user_id}")])
            keyboard.append([InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin")])
            await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
            await state.clear()
            return
        
        keyboard = [[InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin")]]
        await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await state.clear()
        
    elif action == "remove_number":
        items = db.get_user_inventory_full(user_id)
        if not items:
            await message.answer(f"🎒 Инвентарь пользователя {user_id} пуст!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin")]]))
            await state.clear()
            return
        
        text = f"🎒 Выберите номер для удаления (ID пользователя: {user_id}):\n\n"
        keyboard = []
        for item in items:
            item_id, _, number, rarity, _, _ = item
            text += f"• <b>{number}</b> ({rarity}) — ID: {item_id}\n"
            keyboard.append([InlineKeyboardButton(text=f"❌ {number}", callback_data=f"admin_del_{item_id}_{user_id}")])
        keyboard.append([InlineKeyboardButton(text="◀️ Отмена", callback_data="admin")])
        
        await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await state.clear()
        
    elif action == "give_number":
        await message.answer("🚗 Введите номер (например, А777АА77):")
        await state.set_state(AdminStates.waiting_for_number)

@dp.message(AdminStates.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число! Попробуйте ещё раз:")
        return
    
    data = await state.get_data()
    user_id = data.get("user_id")
    action = data.get("action")
    
    if action == "give_money":
        db.add_balance(user_id, amount)
        new_balance = db.get_balance(user_id)
        text = f"✅ Выдано {amount}₽ пользователю {user_id}\nНовый баланс: {new_balance}₽"
    elif action == "take_money":
        current = db.get_balance(user_id)
        if current < amount:
            text = f"❌ У пользователя только {current}₽, нельзя списать {amount}₽!"
        else:
            db.add_balance(user_id, -amount)
            new_balance = db.get_balance(user_id)
            text = f"✅ Списано {amount}₽ у пользователя {user_id}\nНовый баланс: {new_balance}₽"
    elif action == "set_balance":
        db.set_balance(user_id, amount)
        text = f"✅ Баланс пользователя {user_id} установлен на {amount}₽"
    
    keyboard = [[InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin")]]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.clear()

@dp.message(AdminStates.waiting_for_number)
async def process_number(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    number = message.text.strip().upper()
    await state.update_data(number=number)
    await message.answer("🎨 Введите редкость (Обычный/Необычный/Редкий/Эпический/Легендарный):")
    await state.set_state(AdminStates.waiting_for_rarity)

@dp.message(AdminStates.waiting_for_rarity)
async def process_rarity(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    rarity = message.text.strip().capitalize()
    valid_rarities = ["Обычный", "Необычный", "Редкий", "Эпический", "Легендарный"]
    
    if rarity not in valid_rarities:
        await message.answer(f"❌ Недопустимая редкость! Варианты: {', '.join(valid_rarities)}")
        return
    
    await state.update_data(rarity=rarity)
    await message.answer("💰 Введите цену номера:")
    await state.set_state(AdminStates.waiting_for_price)

@dp.message(AdminStates.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    try:
        price = float(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число!")
        return
    
    data = await state.get_data()
    user_id = data.get("user_id")
    number = data.get("number")
    rarity = data.get("rarity")
    
    db.give_number_to_user(user_id, number, rarity, price)
    
    text = f"✅ Номер <b>{number}</b> ({rarity}, {price}₽) выдан пользователю {user_id}!"
    keyboard = [[InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin")]]
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.clear()

@dp.message(AdminStates.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    text = message.text
    users = db.send_message_to_all(text)
    
    sent = 0
    failed = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, f"📢 <b>Рассылка от админа:</b>\n\n{text}", parse_mode="HTML")
            sent += 1
        except:
            failed += 1
    
    result = f"📢 Рассылка завершена!\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}"
    keyboard = [[InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin")]]
    await message.answer(result, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.clear()

# Удаление номера из инвентаря (кнопка)
@dp.callback_query(F.data.startswith("admin_del_"))
async def admin_delete_number(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    parts = callback.data.split("_")
    inventory_id = int(parts[2])
    user_id = int(parts[3])
    
    db.remove_from_inventory(inventory_id, user_id)
    
    await callback.answer(f"✅ Номер удалён у пользователя {user_id}!", show_alert=True)
    await admin_menu(callback)

# ===== ЗАПУСК =====
async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Веб-сервер запущен")
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
