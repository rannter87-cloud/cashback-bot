import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn
 
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.types import Update
 
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
WEBHOOK_PATH = "/webhook"
 
app = FastAPI()
DB_PATH = "data/db.sqlite"
 
# --- Bot setup ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
 
WELCOME_TEXT = (
    "Что может делать этот бот?\n\n"
    "Бот для получения бесплатной косметики с Wildberries и Ozon.\n"
    "🎁 Выбирайте товары из каталога.\n"
    "📦 Получайте их бесплатно.\n"
    "✍️ Оставляйте отзывы.\n"
    "💰 Получайте кешбэк на карту по СБП\n"
    "❤️ Уже 10000+ покупателей"
)
 
RULES_TEXT = (
    "📋 Правила программы лояльности\n\n"
    "Как это работает:\n"
    "1️⃣ Выберите товар в каталоге\n"
    "2️⃣ Забронируйте товар (2 часа на оформление)\n"
    "3️⃣ Закажите товар на маркетплейсе\n"
    "4️⃣ Загрузите скриншот заказа\n"
    "5️⃣ Получите товар и нажмите «Товар получен»\n"
    "6️⃣ Загрузите фото чека и укажите сумму покупки\n"
    "7️⃣ Дождитесь текста отзыва и разместите его\n"
    "8️⃣ Загрузите скриншот отзыва\n"
    "9️⃣ Запросите выплату\n\n"
    "💰 Кешбэк:\n"
    "• Кешбэк 100% от суммы по чеку\n"
    "• Выплата в течение 10 рабочих дней\n"
    "• Если отзыв не пройдёт — кешбэк всё равно 100%\n\n"
    "⚠️ Ограничения:\n"
    "• Не оплачивайте бонусами, ягодками и баллами!\n"
    "• 1 товар в неделю на каждом маркетплейсе\n"
    "• Каждый товар можно выкупить только один раз\n"
    "• Нельзя выкупить с 2-х аккаунтов одного маркетплейса\n"
    "• Аккаунт маркетплейса НЕ должен быть заблокирован\n"
    "• Переводы в Беларусь невозможны"
)
 
 
@dp.message(CommandStart())
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять условия", callback_data="accept")]
    ])
    await message.answer(WELCOME_TEXT)
    await message.answer("Нажмите кнопку ниже, чтобы начать:", reply_markup=kb)
 
 
@dp.callback_query(F.data == "accept")
async def accept_terms(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await callback.message.answer("✅ Спасибо! Условия приняты.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Мужской", callback_data="gender_male")],
        [InlineKeyboardButton(text="👩 Женский", callback_data="gender_female")],
    ])
    await callback.message.answer(
        "Для начала работы выберите ваш пол.\nЭто нужно для подбора подходящих отзывов.",
        reply_markup=kb
    )
 
 
@dp.callback_query(F.data.in_({"gender_male", "gender_female"}))
async def choose_gender(callback: types.CallbackQuery):
    gender = "male" if callback.data == "gender_male" else "female"
    user_id = callback.from_user.id
 
    conn = get_db()
    c = conn.cursor()
    import random, string
    ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    c.execute("""INSERT OR IGNORE INTO users (telegram_id, username, first_name, gender, referral_code)
                 VALUES (?, ?, ?, ?, ?)""",
              (user_id, callback.from_user.username or "", callback.from_user.first_name or "", gender, ref_code))
    conn.commit()
    conn.close()
 
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await callback.message.answer("✅ Отлично! Теперь вы можете пользоваться каталогом.")
    await callback.message.answer(RULES_TEXT)
 
    kb = ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(
                text="🛍 Каталог",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/app")
            )
        ]],
        resize_keyboard=True
    )
    await callback.message.answer("Выберите действие:", reply_markup=kb)
 
 
# --- Webhook endpoint ---
@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}
 
 
@app.on_event("startup")
async def on_startup():
    init_db()
    webhook_url = f"{WEBAPP_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(webhook_url)
    print(f"Webhook set: {webhook_url}")
 
 
@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()
    await bot.session.close()
 
 
# --- DB ---
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
 
 
def init_db():
    os.makedirs("data", exist_ok=True)
    conn = get_db()
    c = conn.cursor()
 
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        username TEXT,
        first_name TEXT,
        gender TEXT DEFAULT 'female',
        email TEXT,
        phone TEXT,
        full_name TEXT,
        bank TEXT,
        referral_code TEXT,
        referred_by TEXT,
        bonus_days INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
 
    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        marketplace TEXT DEFAULT 'wb',
        image_url TEXT,
        is_active INTEGER DEFAULT 1
    )""")
 
    c.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        name TEXT,
        image_url TEXT,
        price REAL,
        marketplace_url TEXT,
        marketplace TEXT DEFAULT 'wb',
        cashback_percent INTEGER DEFAULT 100,
        total_quantity INTEGER DEFAULT 100,
        available_today INTEGER DEFAULT 5,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )""")
 
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        status TEXT DEFAULT 'booked',
        order_screenshot TEXT,
        receipt_photo TEXT,
        receipt_amount REAL,
        review_text TEXT,
        review_screenshot TEXT,
        payment_requested INTEGER DEFAULT 0,
        booked_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
 
    c.execute("""CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        status TEXT DEFAULT 'open',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
 
    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO categories (name, marketplace, image_url) VALUES (?, ?, ?)",
                  ("ЛУКАС", "wb", "https://via.placeholder.com/100x100?text=LUCAS"))
        c.execute("INSERT INTO categories (name, marketplace, image_url) VALUES (?, ?, ?)",
                  ("БАНИСУ", "wb", "https://via.placeholder.com/100x100?text=BANISU"))
        c.execute("""INSERT INTO products (category_id, name, image_url, price, marketplace_url, total_quantity, available_today)
                     VALUES (1, 'LV.COS / Шампунь глубокой очистки', 'https://via.placeholder.com/300x300?text=Shampoo', 890, 'https://www.wildberries.ru', 296, 5)""")
        c.execute("""INSERT INTO products (category_id, name, image_url, price, marketplace_url, total_quantity, available_today)
                     VALUES (1, 'SOPHIE BONTE / Спрей для волос текстурирующий', 'https://via.placeholder.com/300x300?text=Spray', 650, 'https://www.wildberries.ru', 150, 3)""")
        c.execute("""INSERT INTO products (category_id, name, image_url, price, marketplace_url, total_quantity, available_today)
                     VALUES (1, 'LV.COS / Масло ципируса', 'https://via.placeholder.com/300x300?text=Oil', 1200, 'https://www.wildberries.ru', 100, 6)""")
 
    conn.commit()
    conn.close()
 
 
# --- Models ---
class UserCreate(BaseModel):
    telegram_id: int
    username: str = ""
    first_name: str = ""
    gender: str = "female"
 
class UserUpdate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None
    bank: Optional[str] = None
    gender: Optional[str] = None
 
class OrderCreate(BaseModel):
    user_telegram_id: int
    product_id: int
 
class OrderUpdate(BaseModel):
    status: Optional[str] = None
    receipt_amount: Optional[float] = None
    payment_requested: Optional[int] = None
 
class SupportTicket(BaseModel):
    user_telegram_id: int
    message: str
 
 
# --- API Routes ---
@app.get("/api/users/{telegram_id}")
def get_user(telegram_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)
 
 
@app.patch("/api/users/{telegram_id}")
def update_user(telegram_id: int, data: UserUpdate):
    conn = get_db()
    c = conn.cursor()
    fields = {k: v for k, v in data.dict().items() if v is not None}
    if fields:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        c.execute(f"UPDATE users SET {set_clause} WHERE telegram_id = ?",
                  list(fields.values()) + [telegram_id])
        conn.commit()
    conn.close()
    return {"ok": True}
 
 
@app.get("/api/categories")
def get_categories():
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT c.*, COUNT(p.id) as product_count
                 FROM categories c
                 LEFT JOIN products p ON p.category_id = c.id AND p.is_active = 1
                 WHERE c.is_active = 1
                 GROUP BY c.id""")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
 
 
@app.get("/api/products")
def get_products(category_id: Optional[int] = None):
    conn = get_db()
    c = conn.cursor()
    if category_id:
        c.execute("SELECT * FROM products WHERE category_id = ? AND is_active = 1", (category_id,))
    else:
        c.execute("SELECT * FROM products WHERE is_active = 1")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
 
 
@app.get("/api/products/{product_id}")
def get_product(product_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return dict(row)
 
 
@app.post("/api/orders")
def create_order(order: OrderCreate):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE telegram_id = ?", (order.user_telegram_id,))
    user = c.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    c.execute("""SELECT id FROM orders WHERE user_id = ? AND product_id = ?
                 AND status IN ('booked', 'ordered', 'received')""",
              (user["id"], order.product_id))
    if c.fetchone():
        raise HTTPException(status_code=400, detail="Already booked")
    c.execute("INSERT INTO orders (user_id, product_id) VALUES (?, ?)", (user["id"], order.product_id))
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return {"ok": True, "order_id": order_id}
 
 
@app.get("/api/orders/{telegram_id}")
def get_orders(telegram_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT o.*, p.name as product_name, p.image_url, p.price, p.marketplace
                 FROM orders o
                 JOIN users u ON o.user_id = u.id
                 JOIN products p ON o.product_id = p.id
                 WHERE u.telegram_id = ?
                 ORDER BY o.booked_at DESC""", (telegram_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
 
 
@app.post("/api/support")
def create_ticket(ticket: SupportTicket):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE telegram_id = ?", (ticket.user_telegram_id,))
    user = c.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    c.execute("INSERT INTO support_tickets (user_id, message) VALUES (?, ?)", (user["id"], ticket.message))
    conn.commit()
    conn.close()
    return {"ok": True}
 
 
@app.get("/api/support/{telegram_id}")
def get_tickets(telegram_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT t.* FROM support_tickets t
                 JOIN users u ON t.user_id = u.id
                 WHERE u.telegram_id = ?
                 ORDER BY t.created_at DESC""", (telegram_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
 
 
# --- Static ---
app.mount("/static", StaticFiles(directory="static"), name="static")
 
@app.get("/app")
def serve_app():
    return FileResponse("static/index.html")
 
@app.get("/")
def root():
    return {"status": "ok", "message": "Cashback Bot API"}
 
 
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
