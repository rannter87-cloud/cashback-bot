import asyncio
import os
import threading
import uvicorn
from server import app, init_db
from bot import main as bot_main


def run_bot():
    asyncio.run(bot_main())


if __name__ == "__main__":
    init_db()
    # Бот в фоновом потоке
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    print("Бот запущен в фоне.")
    # Сервер в главном потоке (Render требует это)
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
