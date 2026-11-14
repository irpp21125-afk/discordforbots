"""Менеджер пользователей Telegram (MySQL).

API совместим со старым JSON-вариантом, чтобы Telegram-бот продолжил
работать без изменений.
"""

from db import DB, init_db


class UserManager:
    """Менеджер пользователей Telegram (таблица tg_users)."""

    def __init__(self, filepath: str | None = None):
        init_db()

    # --- запись ---

    def register_user(self, user_id: int, username: str = "Не указан"):
        with DB() as db:
            db.execute(
                "INSERT INTO tg_users(id, username, registration_date, last_activity)"
                " VALUES (%s, %s, NOW(), NOW())"
                " ON DUPLICATE KEY UPDATE last_activity = NOW()",
                (int(user_id), username),
            )

    def update_activity(self, user_id: int):
        with DB() as db:
            db.execute(
                "UPDATE tg_users SET last_activity = NOW() WHERE id = %s",
                (int(user_id),),
            )

    def set_flag(self, user_id: int, flag: str, value: bool):
        allowed = {"is_admin", "is_moderator", "notify"}
        if flag not in allowed:
            raise ValueError(f"Недопустимый флаг: {flag}")
        with DB() as db:
            db.execute(
                f"UPDATE tg_users SET {flag} = %s WHERE id = %s",
                (1 if value else 0, int(user_id)),
            )

    # --- чтение ---

    def is_admin(self, user_id: int) -> bool:
        with DB() as db:
            row = db.fetchone(
                "SELECT is_admin FROM tg_users WHERE id = %s", (int(user_id),)
            )
        return bool(row and row["is_admin"])

    def is_modertor(self, user_id: int) -> bool:
        # старое написание имени метода сохранено для совместимости с ботом
        with DB() as db:
            row = db.fetchone(
                "SELECT is_moderator FROM tg_users WHERE id = %s",
                (int(user_id),),
            )
        return bool(row and row["is_moderator"])

    def get_user(self, user_id: int) -> dict:
        with DB() as db:
            row = db.fetchone(
                "SELECT * FROM tg_users WHERE id = %s", (int(user_id),)
            )
        if not row:
            return {}
        return {
            "username": row["username"],
            "name": row["name"],
            "registration_date": str(row["registration_date"] or ""),
            "last_activity": str(row["last_activity"] or ""),
            "Admin": bool(row["is_admin"]),
            "modertor": bool(row["is_moderator"]),
            "notify": bool(row["notify"]),
        }

    def get_user_count(self) -> int:
        with DB() as db:
            row = db.fetchone("SELECT COUNT(*) AS c FROM tg_users")
        return int(row["c"])

    def get_active_users(self, days: int = 7) -> int:
        with DB() as db:
            row = db.fetchone(
                "SELECT COUNT(*) AS c FROM tg_users "
                "WHERE last_activity >= DATE_SUB(NOW(), INTERVAL %s DAY)",
                (days,),
            )
        return int(row["c"])

    def get_all_users(self) -> dict:
        """Словарь {str(id): {...}} — формат старого JSON."""
        with DB() as db:
            rows = db.fetchall(
                "SELECT * FROM tg_users ORDER BY registration_date"
            )
        result = {}
        for row in rows:
            result[str(row["id"])] = {
                "username": row["username"],
                "name": row["name"],
                "registration_date": str(row["registration_date"] or ""),
                "last_activity": str(row["last_activity"] or ""),
                "Admin": bool(row["is_admin"]),
                "modertor": bool(row["is_moderator"]),
                "notify": bool(row["notify"]),
            }
        return result

    def get_admin_ids(self) -> list:
        with DB() as db:
            rows = db.fetchall(
                "SELECT id FROM tg_users WHERE is_admin = 1 OR is_moderator = 1"
            )
        return [int(r["id"]) for r in rows]

    def search_users(self, query: str) -> list:
        q = f"%{query.strip()}%"
        with DB() as db:
            rows = db.fetchall(
                "SELECT * FROM tg_users "
                "WHERE id LIKE %s OR username LIKE %s OR name LIKE %s "
                "ORDER BY last_activity DESC LIMIT 200",
                (q, q, q),
            )
        return list(rows)
