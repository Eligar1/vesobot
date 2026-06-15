from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import (
    BOT_TOKEN,
    DAILY_WATER_NORM_ML,
    EXCEL_PATH,
    PERSONAL_USER_ID,
    TIMEZONE,
    TIMEZONE_NAME,
    DB_PATH,
)
from excel_book import sync_excel
from storage import Storage


storage = Storage(DB_PATH)


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Вписать вес"), KeyboardButton(text="Профиль")],
        [KeyboardButton(text="+250 мл"), KeyboardButton(text="+500 мл"), KeyboardButton(text="Вода")],
    ],
    resize_keyboard=True,
)


def now_local() -> datetime:
    return datetime.now(TIMEZONE)


def is_allowed(user_id: int) -> bool:
    return PERSONAL_USER_ID is None or user_id == PERSONAL_USER_ID


def parse_number(text: str) -> float | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)", text)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def trend_text(latest: list) -> str:
    if not latest:
        return "Вес пока не записан."
    current = latest[0]["weight_kg"]
    if len(latest) == 1:
        return f"Текущий вес: {current:g} кг. Нужна еще одна запись для динамики."
    previous = latest[1]["weight_kg"]
    delta = round(current - previous, 2)
    if delta > 0:
        return f"Вес идет вверх: +{delta:g} кг. Сейчас {current:g} кг."
    if delta < 0:
        return f"Вес идет вниз: {delta:g} кг. Сейчас {current:g} кг."
    return f"Вес без изменений. Сейчас {current:g} кг."


def sync_user_excel(user_id: int) -> bool:
    user = storage.get_user(user_id)
    norm = int(user["water_norm_ml"]) if user else DAILY_WATER_NORM_ML
    try:
        sync_excel(storage, user_id, EXCEL_PATH, norm)
    except PermissionError:
        logging.warning("Excel file is locked: %s", EXCEL_PATH)
        return False
    return True


async def ensure_user(message: Message) -> bool:
    if not message.from_user:
        return False
    if not is_allowed(message.from_user.id):
        await message.answer("Это личный бот, доступ закрыт.")
        return False
    storage.upsert_user(
        user_id=message.from_user.id,
        first_name=message.from_user.first_name,
        water_norm_ml=DAILY_WATER_NORM_ML,
        now=now_local(),
    )
    return True


async def send_profile(message: Message) -> None:
    assert message.from_user is not None
    today = now_local().date()
    user = storage.get_user(message.from_user.id)
    norm = int(user["water_norm_ml"]) if user else DAILY_WATER_NORM_ML
    water_total = storage.today_water_total(message.from_user.id, today)
    latest = storage.latest_weights(message.from_user.id)

    await message.answer(
        "\n".join(
            [
                "Профиль",
                trend_text(latest),
                f"Вода сегодня: {water_total} мл / {norm} мл.",
                f"Excel: {EXCEL_PATH.name}",
            ]
        ),
        reply_markup=main_keyboard,
    )


async def record_weight(message: Message, weight: float) -> None:
    assert message.from_user is not None
    if weight < 20 or weight > 400:
        await message.answer("Похоже, вес вне нормального диапазона. Напиши значение в кг, например 82.4.")
        return
    storage.add_weight(message.from_user.id, weight, now_local())
    excel_synced = sync_user_excel(message.from_user.id)
    extra = "" if excel_synced else "\nExcel сейчас открыт, поэтому таблица обновится после закрытия файла."
    await message.answer(f"Записал вес: {weight:g} кг.{extra}", reply_markup=main_keyboard)
    await send_profile(message)


async def record_water(message: Message, amount_ml: int) -> None:
    assert message.from_user is not None
    if amount_ml <= 0 or amount_ml > 5000:
        await message.answer("Напиши количество воды в мл, например 300.")
        return
    storage.add_water(message.from_user.id, amount_ml, now_local())
    excel_synced = sync_user_excel(message.from_user.id)
    user = storage.get_user(message.from_user.id)
    norm = int(user["water_norm_ml"]) if user else DAILY_WATER_NORM_ML
    total = storage.today_water_total(message.from_user.id, now_local().date())
    extra = "" if excel_synced else "\nExcel сейчас открыт, поэтому таблица обновится после закрытия файла."
    await message.answer(f"Выпито: {total} мл / {norm} мл.{extra}", reply_markup=main_keyboard)


async def remind(bot: Bot) -> None:
    for user in storage.users():
        if is_allowed(int(user["user_id"])):
            await bot.send_message(int(user["user_id"]), "Впиши данные", reply_markup=main_keyboard)


async def cmd_start(message: Message) -> None:
    if not await ensure_user(message):
        return
    await message.answer(
        "Готов. Я буду вести вес, воду и обновлять Excel.\n"
        "Вес можно писать как `82.4` или через кнопку. Воду: `вода 300`, `+250 мл` или кнопками.",
        reply_markup=main_keyboard,
        parse_mode="Markdown",
    )


async def cmd_weight(message: Message) -> None:
    if not await ensure_user(message):
        return
    value = parse_number(message.text or "")
    if value is None:
        storage.set_state(message.from_user.id, "awaiting_weight", now_local())
        await message.answer("Напиши вес в кг, например 82.4.", reply_markup=main_keyboard)
        return
    await record_weight(message, value)


async def cmd_water(message: Message) -> None:
    if not await ensure_user(message):
        return
    value = parse_number(message.text or "")
    if value is None:
        storage.set_state(message.from_user.id, "awaiting_water", now_local())
        await message.answer("Сколько воды выпил? Напиши в мл, например 300.", reply_markup=main_keyboard)
        return
    await record_water(message, int(value))


async def cmd_profile(message: Message) -> None:
    if not await ensure_user(message):
        return
    await send_profile(message)


async def on_text(message: Message) -> None:
    if not await ensure_user(message):
        return
    assert message.from_user is not None
    text = (message.text or "").strip().lower()

    if text == "профиль":
        await send_profile(message)
        return
    if text == "вписать вес":
        storage.set_state(message.from_user.id, "awaiting_weight", now_local())
        await message.answer("Напиши вес в кг, например 82.4.", reply_markup=main_keyboard)
        return
    if text == "вода":
        storage.set_state(message.from_user.id, "awaiting_water", now_local())
        await message.answer("Сколько воды выпил? Напиши в мл, например 300.", reply_markup=main_keyboard)
        return

    state = storage.pop_state(message.from_user.id)
    value = parse_number(text)

    if state == "awaiting_weight" and value is not None:
        await record_weight(message, value)
        return
    if state == "awaiting_water" and value is not None:
        await record_water(message, int(value))
        return

    if text.startswith("+") or "мл" in text or text.startswith("вода"):
        if value is not None:
            await record_water(message, int(value))
            return

    if value is not None:
        await record_weight(message, value)
        return

    await message.answer("Не понял. Нажми кнопку или напиши вес `82.4`, воду `вода 300`.", reply_markup=main_keyboard)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Заполни BOT_TOKEN в .env")

    logging.basicConfig(level=logging.INFO)
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_profile, Command("profile"))
    dp.message.register(cmd_weight, Command("weight"))
    dp.message.register(cmd_water, Command("water"))
    dp.message.register(on_text, F.text)

    scheduler = AsyncIOScheduler(timezone=TIMEZONE_NAME)
    scheduler.add_job(
        remind,
        CronTrigger(hour="0,9-23/3", minute=0, timezone=TIMEZONE_NAME),
        args=[bot],
        id="data_reminder",
        replace_existing=True,
    )
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
