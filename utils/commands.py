from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.exceptions import TelegramAPIError
import logging

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Главное меню / Регистрация"),
        BotCommand(command="book", description="Записаться на услугу"),
        BotCommand(command="profile", description="Мои записи"),
        BotCommand(command="bonuses", description="Баланс бонусов"),
        BotCommand(command="help", description="Помощь и контакты"),
    ]
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    except TelegramAPIError as e:
        logging.error(f"Failed to set bot commands: {e}")
