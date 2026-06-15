from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
TIMEZONE_NAME = os.getenv("TIMEZONE", "Europe/Moscow").strip()
TIMEZONE = ZoneInfo(TIMEZONE_NAME)

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "vesobot.sqlite3"
EXCEL_PATH = BASE_DIR / os.getenv("EXCEL_FILE", "veso.xlsx")

DAILY_WATER_NORM_ML = int(os.getenv("DAILY_WATER_NORM_ML", "3000"))

personal_user_id = os.getenv("PERSONAL_USER_ID", "").strip()
PERSONAL_USER_ID = int(personal_user_id) if personal_user_id else None

