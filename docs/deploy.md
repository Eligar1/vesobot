# Server Deploy

Инструкция для переноса `vesobot` на Ubuntu VPS.

## Что важно сохранить

- `.env` - токен бота и личный Telegram ID.
- `data/vesobot.sqlite3` - основная база данных.
- `veso.xlsx` - Excel-отчет, который обновляется из базы.

## Установка

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip

sudo mkdir -p /opt/vesobot
sudo chown "$USER":"$USER" /opt/vesobot
git clone https://github.com/Eligar1/vesobot.git /opt/vesobot

cd /opt/vesobot
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

После этого заполнить `.env` реальными значениями.

## Перенос данных

С локального компьютера перенести на сервер:

```text
D:\botstg\vesobot\.env
D:\botstg\vesobot\data\vesobot.sqlite3
D:\botstg\vesobot\veso.xlsx
```

На сервере они должны лежать так:

```text
/opt/vesobot/.env
/opt/vesobot/data/vesobot.sqlite3
/opt/vesobot/veso.xlsx
```

## Systemd

```bash
sudo cp /opt/vesobot/deploy/vesobot.service.example /etc/systemd/system/vesobot.service
sudo systemctl daemon-reload
sudo systemctl enable vesobot
sudo systemctl start vesobot
sudo systemctl status vesobot
```

Логи:

```bash
journalctl -u vesobot -f
```

## Бэкапы

Ручной бэкап:

```bash
cd /opt/vesobot
.venv/bin/python scripts/backup_vesobot.py
```

Cron на ежедневный бэкап в 04:20:

```bash
crontab -e
```

```cron
20 4 * * * cd /opt/vesobot && /opt/vesobot/.venv/bin/python scripts/backup_vesobot.py >> /opt/vesobot/backups/backup.log 2>&1
```

Скрипт хранит до 30 последних архивов и удаляет архивы старше 30 дней.

## Проверка после переноса

1. `systemctl status vesobot` показывает `active (running)`.
2. `/start` отвечает только владельцу.
3. `/profile` показывает текущие данные.
4. Новая запись веса или воды сохраняется в `data/vesobot.sqlite3`.
5. `veso.xlsx` обновляется после записи.
6. Ручной запуск `scripts/backup_vesobot.py` создает zip-архив в `backups/`.
