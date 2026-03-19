import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
from core.config import settings
from handlers import client, admin
from middlewares.db import DbSessionMiddleware
from middlewares.admin import AdminMiddleware
from database.database import engine, Base
from utils.commands import set_bot_commands
from services.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO)

async def on_startup(bot: Bot):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await set_bot_commands(bot)

async def main():
    # Настройка хранилища (Redis для Docker/Сервера, Memory для локалки)
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        logging.info("Using Redis storage")
        redis = Redis.from_url(redis_url)
        storage = RedisStorage(redis=redis)
    else:
        logging.info("Using Memory storage")
        storage = MemoryStorage()

    bot = Bot(token=settings.bot_token.get_secret_value())
    dp = Dispatcher(storage=storage)

    # Middlewares
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(AdminMiddleware())

    # Routers
    dp.include_router(admin.router)
    dp.include_router(client.router)

    dp.startup.register(on_startup)
    setup_scheduler(bot)
    
    try:
        await dp.start_polling(bot)
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
