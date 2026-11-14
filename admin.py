"""Менеджер администрирования (MySQL).

Наследуется от UserManager — тот же слой базы, тот же API.
Добавлены методы для управления правами.
"""

from user import UserManager


class AdminManager(UserManager):
    """Расширенный менеджер для админ-панели (Telegram-бот + C++ app)."""

    def grant_admin(self, user_id: int):
        self.set_flag(int(user_id), "is_admin", True)

    def revoke_admin(self, user_id: int):
        self.set_flag(int(user_id), "is_admin", False)

    def grant_modertor(self, user_id: int):
        self.set_flag(int(user_id), "is_moderator", True)

    def revoke_modertor(self, user_id: int):
        self.set_flag(int(user_id), "is_moderator", False)

    def toggle_notify(self, user_id: int):
        self.set_flag(int(user_id), "notify", True)
