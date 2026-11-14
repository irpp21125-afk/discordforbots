"""Миграция данных из старых JSON-файлов в MySQL.

Запуск: python migrate_to_mysql.py
Старые файлы: handlers.py/users.json, profiles.json, tickets.json
(если ещё существуют)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import DB, init_db


def migrate():
    init_db()

    # ── users.json (Telegram) ──
    users_path = os.path.join("users.json")
    if os.path.exists(users_path):
        with open(users_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        count = 0
        with DB() as db:
            for uid, info in data.items():
                db.execute(
                    "INSERT INTO tg_users(id, username, name, registration_date,"
                    " last_activity, is_admin, is_moderator)"
                    " VALUES (%s, %s, 'Не указано', %s, %s, %s, %s)"
                    " ON DUPLICATE KEY UPDATE username = VALUES(username)",
                    (int(uid), info.get("username", "Не указан"),
                     info.get("registration_date"),
                     info.get("last_activity"),
                     1 if info.get("Admin") else 0,
                     1 if info.get("modertor") else 0),
                )
                count += 1
        print(f"  [OK] tg_users: {count} записей")

    # ── profiles.json ──
    profiles_path = os.path.join("profiles.json")
    if os.path.exists(profiles_path):
        with open(profiles_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with DB() as db:
            for uid, info in data.items():
                db.execute(
                    "UPDATE tg_users SET name = %s WHERE id = %s",
                    (info.get("name", "Не указано"), int(uid)),
                )
        print(f"  [OK] profiles: {len(data)} обновлено")

    # ── tickets.json ──
    tickets_path = os.path.join("tickets.json")
    if os.path.exists(tickets_path):
        with open(tickets_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        count = 0
        with DB() as db:
            for t in data:
                db.execute(
                    "INSERT INTO tickets(id, author_type, author_ref, category,"
                    " priority, status, message, created_at, updated_at)"
                    " VALUES (%s, 'tg', %s, 'Вопрос по боту', 'normal', %s, %s,"
                    " %s, %s) ON DUPLICATE KEY UPDATE message = VALUES(message)",
                    (t.get("id"), t.get("user_id", "0"),
                     t.get("status", "open"), t.get("message", ""),
                     t.get("created_at"), t.get("updated_at")),
                )
                for r in t.get("replies", []):
                    db.execute(
                        "INSERT INTO replies(ticket_id, author_name, is_admin,"
                        " text, created_at) VALUES (%s, 'Админ', %s, %s, %s)",
                        (t["id"], 1 if r.get("is_admin") else 0,
                         r.get("text", ""), r.get("created_at")),
                    )
                count += 1
        print(f"  [OK] tickets: {count} тикетов")

    print("Миграция завершена. Данные в MySQL (support_bot).")


if __name__ == "__main__":
    print("Миграция JSON → MySQL...")
    migrate()

