"""Менеджер профилей (MySQL).

Профиль — часть таблицы tg_users (колонка name).
API совместим со старым кодом Telegram-бота.
"""

from db import DB, init_db


class ProfileManager:
    """Менеджер профилей пользователей Telegram."""

    def __init__(self, filepath: str | None = None):
        init_db()

    def get_user_profile(self, user_id: int) -> str:
        with DB() as db:
            row = db.fetchone(
                "SELECT name, registration_date FROM tg_users WHERE id = %s",
                (int(user_id),),
            )
            count_row = db.fetchone(
                "SELECT COUNT(*) AS c FROM tickets "
                "WHERE author_type = 'tg' AND author_ref = %s",
                (str(int(user_id)),),
            )
        tickets_count = int(count_row["c"]) if count_row else 0
        if not row:
            return (
                "👤 Ваш профиль:\n\n"
                "📛 Имя: Не указано\n"
                "📅 Дата регистрации: Неизвестно\n"
                f"🎫 Обращений: {tickets_count}"
            )
        reg_date = str(row["registration_date"] or "Неизвестно")
        if "." in reg_date:
            reg_date = reg_date.split(".")[0]
        return (
            f"👤 Ваш профиль:\n\n"
            f"📛 Имя: {row['name'] or 'Не указано'}\n"
            f"📅 Дата регистрации: {reg_date}\n"
            f"🎫 Обращений: {tickets_count}"
        )

    def update_profile(self, user_id: int, name: str):
        with DB() as db:
            db.execute(
                "UPDATE tg_users SET name = %s WHERE id = %s",
                (name, int(user_id)),
            )

    def increment_tickets_count(self, user_id: int):
        """Совместимость со старым API: счётчик считается из tickets."""
        return None

    def get_all_profiles(self) -> dict:
        with DB() as db:
            rows = db.fetchall(
                "SELECT id, name, registration_date FROM tg_users"
            )
        return {
            str(r["id"]): {
                "name": r["name"],
                "registration_date": str(r["registration_date"] or ""),
            }
            for r in rows
        }
