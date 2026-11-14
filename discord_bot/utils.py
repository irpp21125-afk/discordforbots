"""Общие утилиты Discord-бота: права, настройки гильдий, аудит."""

from datetime import datetime

import discord
from discord.ext import commands

from db import DB

# ---------- права ----------

def is_staff():
    """Модератор из таблицы dc_users или роль/разрешение Manage Messages."""
    def predicate(ctx):
        return ctx.author.guild_permissions.manage_messages or \
            _flag(ctx, "is_moderator") or _flag(ctx, "is_admin")
    return commands.check(predicate)


def is_head_admin():
    """Администратор: владелец сервера или флаг is_admin."""
    def predicate(ctx):
        return ctx.author.guild_permissions.administrator or \
            _flag(ctx, "is_admin")
    return commands.check(predicate)


def _flag(ctx, flag: str) -> bool:
    """Проверка флага пользователя в MySQL (dc_users)."""
    try:
        with DB() as db:
            row = db.fetchone(
                f"SELECT {flag} AS v FROM dc_users WHERE id = %s",  # noqa: S608
                (ctx.author.id,),
            )
        return bool(row and row["v"])
    except Exception:
        return False


# ---------- настройки гильдии ----------

DEFAULTS = {
    "prefix": "!",
    "mod_log_channel": None,
    "ticket_category": None,
    "ticket_support_role": None,
    "welcome_channel": None,
    "welcome_text": "Добро пожаловать, {user}!",
    "welcome_enabled": 1,
    "welcome_autorole": None,
    "levelup_channel": None,
    "economy_enabled": 1,
    "autorole_enabled": 0,
    "autorole_id": None,
    "anti_raid": 0,
    "log_channel": None,
    "log_enabled": 0,
    "filter_enabled": 1,
    "antispam_enabled": 0,
    "antispam_limit": 5,
    "antiflood_enabled": 0,
    "antiflood_seconds": 5,
}


def get_guild_settings(guild_id: int) -> dict:
    with DB() as db:
        row = db.fetchone(
            "SELECT * FROM guild_settings WHERE guild_id = %s", (guild_id,)
        )
    settings = dict(DEFAULTS)
    if row:
        settings.update({k: v for k, v in row.items() if k != "guild_id"})
    return settings


def set_guild_setting(guild_id: int, key: str, value):
    if key not in DEFAULTS:
        raise ValueError(f"Неизвестная настройка: {key}")
    with DB() as db:
        db.execute(
            "INSERT INTO guild_settings(guild_id, `updated_at`) VALUES (%s, NOW())"
            " ON DUPLICATE KEY UPDATE updated_at = NOW()",
            (guild_id,),
        )
        db.execute(
            f"UPDATE guild_settings SET `{key}` = %s WHERE guild_id = %s",
            (value, guild_id),
        )


# ---------- аудит ----------

def audit(guild_id: int, user_id: int, event: str):
    """Запись события в activity_log."""
    try:
        with DB() as db:
            db.execute(
                "INSERT INTO activity_log(guild_id, user_id, event, created_at)"
                " VALUES (%s, %s, %s, NOW())",
                (guild_id, user_id, event),
            )
    except Exception:
        pass


async def send_mod_log(ctx_or_bot, guild, text: str):
    """Отправка в канал модерации (если настроен)."""
    settings = get_guild_settings(guild.id)
    chan_id = settings.get("mod_log_channel")
    if not chan_id:
        return
    channel = guild.get_channel(int(chan_id))
    if channel:
        try:
            await channel.send(text)
        except discord.Forbidden:
            pass


async def send_log(guild, text: str):
    """Отправка в канал логов (если log_enabled + log_channel настроены)."""
    settings = get_guild_settings(guild.id)
    if not settings.get("log_enabled"):
        return
    chan_id = settings.get("log_channel")
    if not chan_id:
        return
    channel = guild.get_channel(int(chan_id))
    if channel:
        try:
            await channel.send(text)
        except discord.Forbidden:
            pass


async def send_log_embed(guild, title: str, description: str, color: int,
                         fields: list = None, footer: str = ""):
    """Отправка embed в канал логов."""
    settings = get_guild_settings(guild.id)
    if not settings.get("log_enabled"):
        return
    chan_id = settings.get("log_channel")
    if not chan_id:
        return
    channel = guild.get_channel(int(chan_id))
    if not channel:
        return
    embed = discord.Embed(title=title, description=description, color=color,
                          timestamp=datetime.now())
    if fields:
        for f in fields:
            name, value = f[0], f[1]
            inline = f[2] if len(f) > 2 else True
            embed.add_field(name=name, value=value, inline=inline)
    if footer:
        embed.set_footer(text=footer)
    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        pass


def now_str() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M")


# ---------- привилегии ----------

PRIVILEGE_ICONS = {
    "starvision": "⭐",
    "viaglobal": "🌍",
    "gectoring": "🏆",
    "none": "",
}

PRIVILEGE_ORDER = {"gectoring": 3, "viaglobal": 2, "starvision": 1, "none": 0}


def privilege_icon(priv: str) -> str:
    return PRIVILEGE_ICONS.get(priv, "")


def privilege_rank(priv: str) -> int:
    return PRIVILEGE_ORDER.get(priv, 0)


def privilege_icon_for_name(name: str) -> str:
    """Получить значок по имени (звёздочки уже внутри)."""
    icon = PRIVILEGE_ICONS.get(name, "")
    return icon


async def set_privilege(user_id: int, privilege: str):
    """Установить привилегию пользователю в dc_users."""
    priv = privilege if privilege in PRIVILEGE_ICONS else "none"
    with DB() as db:
        db.execute(
            "INSERT INTO dc_users(id, privilege) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE privilege = VALUES(privilege)",
            (user_id, priv),
        )


async def get_privilege(user_id: int) -> str:
    """Получить привилегию пользователя."""
    with DB() as db:
        row = db.fetchone("SELECT privilege FROM dc_users WHERE id = %s",
                          (user_id,))
    return row["privilege"] if row else "none"


# ---------- фильтры слов ----------

def filter_add_word(guild_id: int, word: str):
    with DB() as db:
        db.execute(
            "INSERT INTO filter_words(guild_id, word) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE word = VALUES(word)",
            (guild_id, word.lower().strip()),
        )


def filter_remove_word(guild_id: int, word: str):
    with DB() as db:
        db.execute(
            "DELETE FROM filter_words WHERE guild_id = %s AND word = %s",
            (guild_id, word.lower().strip()),
        )


def filter_list_words(guild_id: int) -> list:
    with DB() as db:
        rows = db.fetchall(
            "SELECT word FROM filter_words WHERE guild_id = %s ORDER BY word",
            (guild_id,),
        )
    return [r["word"] for r in rows]


# ---------- модерация-лог ----------

def mod_log(guild_id: int, user_id: int, moderator_id: int,
            action: str, reason: str = ""):
    """Запись в moderation_log (дублирует punishments для чистоты)."""
    try:
        with DB() as db:
            db.execute(
                "INSERT INTO moderation_log(guild_id, user_id, moderator_id, "
                "action, reason, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
                (guild_id, user_id, moderator_id, action, reason),
            )
    except Exception:
        pass
