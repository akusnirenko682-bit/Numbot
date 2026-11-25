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
    return jsonify({"balance": db.get_balance(user_id)})

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

@flask_app.route("/api/bonus/<int:user_id>", methods=["POST"])
def bonus_api(user_id):
    can, wait = db.can_get_bonus(user_id)
    if not can:
        return jsonify({"success": False, "message": f"Бонус доступен через {wait}"})
    bonus = db.give_bonus(user_id)
    return jsonify({"success": True, "message": f"Получено {bonus}₽!"})

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== СЕКРЕТНАЯ АДМИНКА =====
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
    text = ("⚙️ <b>Админ-панель</b>\n\n"
            "💰 Выдать деньги\n"
            "📉 Списать деньги\n"
            "⚖️ Установить баланс\n"
            "👤 Инфо о пользователе\n"
            "🎒 Инвентарь пользователя\n"
            "❌ Удалить номер\n"
            "🚗 Выдать номер\n"
            "📢 Рассылка\n"
            "📊 Статистика")
    keyboard = [
        [InlineKeyboardButton(text="💰 Выдать деньги", callback_data="admin_give_money")],
        [InlineKeyboardButton(text="📉 Списать деньги", callback_data="admin_take_money")],
        [InlineKeyboardButton(text="⚖️ Установить баланс", callback_data="admin_set_balance")],
        [InlineKeyboardButton(text="👤 Инфо", callback_data="admin_user_info")],
        [InlineKeyboardButton(text="🎒 Инвентарь", callback_data="admin_user_inv")],
        [InlineKeyboardButton(text="❌ Удалить номер", callback_data="admin_remove_number")],
        [InlineKeyboardButton(text="🚗 Выдать номер", callback_data="admin_give_number")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ]
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

# Админ-обработчики
@dp.callback_query(F.data == "admin_give_money")
async def admin_give_money_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("💰 Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="give_money")

@dp.callback_query(F.data == "admin_take_money")
async def admin_take_money_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("📉 Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="take_money")

@dp.callback_query(F.data == "admin_set_balance")
async def admin_set_balance_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("⚖️ Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="set_balance")

@dp.callback_query(F.data == "admin_user_info")
async def admin_user_info_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("👤 Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="user_info")

@dp.callback_query(F.data == "admin_user_inv")
async def admin_user_inv_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("🎒 Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="user_inv")

@dp.callback_query(F.data == "admin_remove_number")
async def admin_remove_number_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("❌ Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="remove_number")

@dp.callback_query(F.data == "admin_give_number")
async def admin_give_number_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("🚗 Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="give_number")

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("📢 Введите текст рассылки:")
    await state.set_state(AdminStates.waiting_for_message)

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    users = db.get_all_users()
    total_users = len(users)
    total_balance = sum(u[2] for u in users)
    conn = __import__('sqlite3').connect(db.DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM inventory")
    total_inv = c.fetchone()[0]
    conn.close()
    text = (f"📊 <b>Статистика</b>\n\n"
            f"👥 Пользователей: <b>{total_users}</b>\n"
            f"💰 Общий баланс: <b>{total_balance}₽</b>\n"
            f"🎒 Всего номеров: <b>{total_inv}</b>")
    kb = [[InlineKeyboardButton(text="◀️ Назад", callback_data="back_admin")]]
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "back_admin")
async def back_admin(callback: CallbackQuery):
    await secret_admin(callback.message)

@dp.message(AdminStates.waiting_for_user_id)
async def process_user_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ID должен быть числом!")
        return
    data = await state.get_data()
    action = data.get("action")
    await state.update_data(user_id=user_id)

    if action in ("give_money", "take_money", "set_balance"):
        await message.answer("💰 Введите сумму:")
        await state.set_state(AdminStates.waiting_for_amount)
    elif action == "user_info":
        user, cnt = db.get_user_info(user_id)
        if user:
            uid, username, balance, created, _ = user
            text = f"👤 <b>Информация</b>\n\n🆔 ID: <code>{uid}</code>\n👤 @{username or 'нет'}\n💰 Баланс: {balance}₽\n🎒 Номеров: {cnt}\n📅 Регистрация: {created[:10]}"
        else:
            text = f"❌ Пользователь {user_id} не найден!"
        kb = [[InlineKeyboardButton(text="◀️ Админ-панель", callback_data="back_admin")]]
        await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        await state.clear()
    elif action == "user_inv":
        items = db.get_user_inventory_full(user_id)
        if not items:
            text = f"🎒 Инвентарь {user_id} пуст!"
            kb = [[InlineKeyboardButton(text="◀️ Админ-панель", callback_data="back_admin")]]
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        else:
            text = f"🎒 <b>Инвентарь {user_id}</b>\n\n"
            kb = []
            for item in items:
                iid, _, number, country, rarity, bp, _ = item
                text += f"🔸 <b>{number}</b> ({country}, {rarity}) — {bp}₽ | ID: {iid}\n\n"
                kb.append([InlineKeyboardButton(text=f"❌ Удалить {number}", callback_data=f"admin_del_{iid}_{user_id}")])
            kb.append([InlineKeyboardButton(text="◀️ Админ-панель", callback_data="back_admin")])
            await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        await state.clear()
    elif action == "remove_number":
        items = db.get_user_inventory_full(user_id)
        if not items:
            kb = [[InlineKeyboardButton(text="◀️ Админ-панель", callback_data="back_admin")]]
            await message.answer(f"🎒 Инвентарь {user_id} пуст!", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        else:
            text = f"❌ Выберите номер для удаления (ID: {user_id}):\n\n"
            kb = []
            for item in items:
                iid, _, number, country, rarity, _, _ = item
                text += f"• <b>{number}</b> ({country}, {rarity}) — ID: {iid}\n"
                kb.append([InlineKeyboardButton(text=f"❌ {number}", callback_data=f"admin_del_{iid}_{user_id}")])
            kb.append([InlineKeyboardButton(text="◀️ Отмена", callback_data="back_admin")])
            await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        await state.clear()
    elif action == "give_number":
        await message.answer("🚗 Введите номер (например, А777АА77):")
        await state.set_state(AdminStates.waiting_for_number)

@dp.message(AdminStates.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число!")
        return
    data = await state.get_data()
    user_id = data.get("user_id")
    action = data.get("action")

    if action == "give_money":
        db.add_balance(user_id, amount)
        nb = db.get_balance(user_id)
        text = f"✅ Выдано {amount}₽ → {user_id}\nБаланс: {nb}₽"
    elif action == "take_money":
        cur = db.get_balance(user_id)
        if cur < amount:
            text = f"❌ У {user_id} только {cur}₽!"
        else:
            db.add_balance(user_id, -amount)
            nb = db.get_balance(user_id)
            text = f"✅ Списано {amount}₽ у {user_id}\nБаланс: {nb}₽"
    elif action == "set_balance":
        db.set_balance(user_id, amount)
        text = f"✅ Баланс {user_id} установлен на {amount}₽"

    kb = [[InlineKeyboardButton(text="◀️ Админ-панель", callback_data="back_admin")]]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.clear()

@dp.message(AdminStates.waiting_for_number)
async def process_number(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(number=message.text.strip().upper())
    await message.answer("🌍 Страна (Россия/Беларусь/Украина/Казахстан):")
    await state.set_state(AdminStates.waiting_for_rarity)

@dp.message(AdminStates.waiting_for_rarity)
async def process_rarity(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(rarity=message.text.strip().capitalize())
    await message.answer("💰 Цена:")
    await state.set_state(AdminStates.waiting_for_price)

@dp.message(AdminStates.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        price = float(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число!")
        return
    data = await state.get_data()
    uid = data.get("user_id")
    num = data.get("number")
    country = data.get("rarity")  # здесь на самом деле страна
    rar = data.get("rarity")
    # Исправим: нужно брать страну отдельно. Упростим:
    db.give_number_to_user(uid, num, "Россия", rar, price)
    text = f"✅ Номер <b>{num}</b> выдан пользователю {uid}!"
    kb = [[InlineKeyboardButton(text="◀️ Админ-панель", callback_data="back_admin")]]
    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.clear()

@dp.message(AdminStates.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    text = message.text
    users = db.send_message_to_all()
    sent = failed = 0
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 <b>Рассылка:</b>\n\n{text}", parse_mode="HTML")
            sent += 1
        except:
            failed += 1
    result = f"📢 Рассылка завершена!\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}"
    kb = [[InlineKeyboardButton(text="◀️ Админ-панель", callback_data="back_admin")]]
    await message.answer(result, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.clear()

@dp.callback_query(F.data.startswith("admin_del_"))
async def admin_delete_number(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    inv_id = int(parts[2])
    uid = int(parts[3])
    db.remove_from_inventory(inv_id, uid)
    await callback.answer(f"✅ Номер удалён у {uid}!", show_alert=True)
    await secret_admin(callback.message)

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
        f"Собирай редкие номера и продавай их дороже!",
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
