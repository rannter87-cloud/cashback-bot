"""
Запускает сервер (FastAPI) и бота одновременно.
"""
import asyncio
import os
import threading
import uvicorn
from server import app, init_db
from bot import main as bot_main


def run_server():
    init_db()
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    # Запускаем сервер в отдельном потоке
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    print("Сервер запущен.")
    # Запускаем бота в главном потоке
    asyncio.run(bot_main())
