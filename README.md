# Vesobot

Личный Telegram-бот для записи веса и воды с обновлением `veso.xlsx`.

## Установка

```powershell
cd x:\xxx\vesobot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Заполни `.env`:

```env
BOT_TOKEN=токен_от_BotFather
PERSONAL_USER_ID=твой_telegram_id
DAILY_WATER_NORM_ML=3000
```

`PERSONAL_USER_ID` можно оставить пустым на первый запуск, написать боту `/start`, а потом вписать свой id для защиты.

## Запуск

```powershell
python bot.py
```

## Команды и ввод

- `/start` - регистрация и подсказка.
- `/profile` - профиль: вес, динамика, вода за сегодня.
- `/weight 82.4` - записать вес.
- `/water 300` - записать воду.
- `82.4` - быстрый ввод веса.
- `вода 300`, `+250 мл`, `+500 мл` - быстрый ввод воды.

Бот напоминает: `Впиши данные` в 00:00, потом каждые 3 часа с 09:00 до 21:00 включительно.

Данные хранятся в `data/vesobot.sqlite3`, а Excel обновляется в `veso.xlsx`.
