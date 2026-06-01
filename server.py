import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI()

DB_PATH = "data/db.sqlite"


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
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        status TEXT DEFAULT 'open',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # Тестовые данные
    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO categories (name, marketplace, image_url) VALUES (?, ?, ?)",
                  ("ЛУКАС", "wb", "https://via.placeholder.com/100x100?text=LUCAS"))
        c.execute("INSERT INTO categories (name, marketplace, image_url) VALUES (?, ?, ?)",
                  ("БАНИСУ", "wb", "https://via.placeholder.com/100x100?text=BANISU"))
        cat_id = c.lastrowid

        c.execute("""INSERT INTO products (category_id, name, image_url, price, marketplace_url, total_quantity, available_today)
                     VALUES (1, 'LV.COS / Шампунь глубокой очистки', 'https://via.placeholder.com/300x300?text=Shampoo', 890, 'https://www.wildberries.ru', 296, 5)""")
        c.execute("""INSERT INTO products (category_id, name, image_url, price, marketplace_url, total_quantity, available_today)
                     VALUES (1, 'SOPHIE BONTE / Спрей для волос текстурирующий', 'https://via.placeholder.com/300x300?text=Spray', 650, 'https://www.wildberries.ru', 150, 3)""")
        c.execute("""INSERT INTO products (category_id, name, image_url, price, marketplace_url, total_quantity, available_today)
                     VALUES (1, 'LV.COS / Масло ципируса для замедления роста волос', 'https://via.placeholder.com/300x300?text=Oil', 1200, 'https://www.wildberries.ru', 100, 6)""")

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
    order_screenshot: Optional[str] = None
    receipt_photo: Optional[str] = None
    receipt_amount: Optional[float] = None
    review_text: Optional[str] = None
    review_screenshot: Optional[str] = None
    payment_requested: Optional[int] = None

class SupportTicket(BaseModel):
    user_telegram_id: int
    message: str


# --- Users ---
@app.post("/api/users")
def create_user(user: UserCreate):
    conn = get_db()
    c = conn.cursor()
    import random, string
    ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    try:
        c.execute("""INSERT OR IGNORE INTO users (telegram_id, username, first_name, gender, referral_code)
                     VALUES (?, ?, ?, ?, ?)""",
                  (user.telegram_id, user.username, user.first_name, user.gender, ref_code))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


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


# --- Categories ---
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


# --- Products ---
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


# --- Orders ---
@app.post("/api/orders")
def create_order(order: OrderCreate):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE telegram_id = ?", (order.user_telegram_id,))
    user = c.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Проверка: не забронирован ли уже этот товар
    c.execute("""SELECT id FROM orders WHERE user_id = ? AND product_id = ?
                 AND status IN ('booked', 'ordered', 'received')""",
              (user["id"], order.product_id))
    if c.fetchone():
        raise HTTPException(status_code=400, detail="Already booked")

    c.execute("INSERT INTO orders (user_id, product_id, status) VALUES (?, ?, 'booked')",
              (user["id"], order.product_id))
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


@app.patch("/api/orders/{order_id}")
def update_order(order_id: int, data: OrderUpdate):
    conn = get_db()
    c = conn.cursor()
    fields = {k: v for k, v in data.dict().items() if v is not None}
    if fields:
        fields["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        c.execute(f"UPDATE orders SET {set_clause} WHERE id = ?",
                  list(fields.values()) + [order_id])
        conn.commit()
    conn.close()
    return {"ok": True}


# --- Support ---
@app.post("/api/support")
def create_ticket(ticket: SupportTicket):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE telegram_id = ?", (ticket.user_telegram_id,))
    user = c.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    c.execute("INSERT INTO support_tickets (user_id, message) VALUES (?, ?)",
              (user["id"], ticket.message))
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


# --- Static files (Mini App) ---
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/app")
def serve_app():
    return FileResponse("static/index.html")

@app.get("/")
def root():
    return {"status": "ok", "message": "Cashback Bot API"}


if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
