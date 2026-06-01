import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
)
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = os.getenv("BOT_TOKEN", "8602960145:AAHYCvPB4-_gCTQhf3npNp90_n3y8wNtv0c")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.railway.app")

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
    await message.answer_photo(
        photo="https://i.imgur.com/placeholder.jpg",  # замените на свою картинку
        caption=WELCOME_TEXT
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять условия", callback_data="accept")]
    ])
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

    # Сохраняем пол пользователя через API
    import aiohttp
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(f"{WEBAPP_URL}/api/users", json={
                "telegram_id": user_id,
                "username": callback.from_user.username or "",
                "first_name": callback.from_user.first_name or "",
                "gender": gender
            })
        except Exception:
            pass

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await callback.message.answer("✅ Отлично! Теперь вы можете пользоваться каталогом.")
    await callback.message.answer(RULES_TEXT)

    # Кнопка открытия Mini App
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


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
