from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "vesobot.sqlite3"
EXCEL_PATH = BASE_DIR / os.getenv("EXCEL_FILE", "veso.xlsx")

BACKUP_DIR = BASE_DIR / os.getenv("VESOBOT_BACKUP_DIR", "backups")
KEEP_DAYS = int(os.getenv("VESOBOT_BACKUP_KEEP_DAYS", "30"))
KEEP_LAST = int(os.getenv("VESOBOT_BACKUP_KEEP_LAST", "30"))


def backup_sqlite(source_path: Path, target_path: Path) -> None:
    if not source_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {source_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(target_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def prune_old_backups(backup_dir: Path) -> None:
    backups = sorted(
        backup_dir.glob("vesobot_*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    cutoff = datetime.now().timestamp() - timedelta(days=KEEP_DAYS).total_seconds()

    for index, path in enumerate(backups):
        too_many = index >= KEEP_LAST
        too_old = path.stat().st_mtime < cutoff
        if too_many or too_old:
            path.unlink(missing_ok=True)


def create_backup() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    archive_path = BACKUP_DIR / f"vesobot_{timestamp}.zip"

    with tempfile.TemporaryDirectory(prefix="vesobot_backup_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_copy = tmp_path / "vesobot.sqlite3"
        backup_sqlite(DB_PATH, db_copy)

        manifest = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "database": str(DB_PATH),
            "excel": str(EXCEL_PATH) if EXCEL_PATH.exists() else None,
        }

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(db_copy, "data/vesobot.sqlite3")
            if EXCEL_PATH.exists():
                archive.write(EXCEL_PATH, EXCEL_PATH.name)
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )

    prune_old_backups(BACKUP_DIR)
    return archive_path


def main() -> None:
    archive_path = create_backup()
    print(archive_path)


if __name__ == "__main__":
    main()
