"""Точка входа Discord-бота поддержки.

Модули (по меню панели):
  Обращения, Модерация, Наказания, Роли, Экономика, Розыгрыши,
  Автоматизация, Оповещения, Общие настройки.
"""

import asyncio
import logging
import os
import sys

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import DB, init_db  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("dcbot")

COGS = [
    "cogs.general",     # Общие настройки, Команды, Баннер, Аудит
    "cogs.tickets",     # Обращения
    "cogs.moderation",  # Модерация, Наказания, Заявки на разбан
    "cogs.roles",       # Управление ролями
    "cogs.economy",     # Экономика, Рейтинг, Магазин, Привилегии
    "cogs.giveaway",    # Розыгрыши
    "cogs.automod",     # Автоматизация / Безопасность
    "cogs.alerts",      # Оповещения
    "cogs.games",       # Развлечения
    "cogs.logging_cog", # Логи
    "cogs.user_info",   # /userinfo, /help, /serverinfo
]

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info("Бот запущен как %s (id=%s)", bot.user, bot.user.id)
    try:
        synced = await bot.tree.sync()
        log.info("Синхронизировано %s слэш-команд", len(synced))
    except Exception as e:
        log.error("tree.sync: %s", e)
    # фоновые задачи
    bot.loop.create_task(check_giveaways())
    bot.loop.create_task(check_mute_expiry())
    bot.loop.create_task(check_reminders())


@bot.event
async def on_error(event_method, *args, **kwargs):
    """Логируем ошибку вместо падения бота."""
    log.exception("Необработанная ошибка в %s", event_method)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction,
                               error: app_commands.AppCommandError):
    """Ошибка в слэш-команде не должна ронять бота."""
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ Недостаточно прав для этой команды."
    elif isinstance(error, app_commands.CommandNotFound):
        msg = "❌ Команда не найдена. Используйте /help"
    else:
        log.exception("Ошибка команды", exc_info=error)
        msg = f"⚠️ Ошибка: {error}"

    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


async def check_giveaways():
    """Завершение розыгрышей по истечении времени."""
    await bot.wait_until_ready()
    cog = bot.get_cog("Giveaway")
    if cog:
        while True:
            try:
                await cog.check_finished()
            except Exception as e:
                log.error("giveaway check: %s", e)
            await asyncio.sleep(30)


async def check_mute_expiry():
    """Снятие мутов по истечении срока."""
    await bot.wait_until_ready()
    cog = bot.get_cog("Moderation")
    if cog:
        while True:
            try:
                await cog.expire_mutes()
            except Exception as e:
                log.error("mute expiry: %s", e)
            await asyncio.sleep(60)


async def check_reminders():
    """Доставка напоминаний из таблицы reminders."""
    await bot.wait_until_ready()
    while True:
        try:
            with DB() as db:
                rows = db.fetchall(
                    "SELECT * FROM reminders WHERE delivered = 0 "
                    "AND remind_at <= NOW() LIMIT 20"
                )
            for row in rows:
                delivered = False
                channel = bot.get_channel(int(row["channel_id"] or 0))
                if channel:
                    user = channel.guild.get_member(int(row["user_id"])) \
                        if getattr(channel, "guild", None) else None
                    mention = user.mention if user else \
                        f"<@{row['user_id']}>"
                    try:
                        await channel.send(
                            f"⏰ **Напоминание** {mention}: "
                            f"{row['message']}"
                        )
                        delivered = True
                    except discord.Forbidden:
                        delivered = True  # не долбить повторно
                else:
                    delivered = True
                with DB() as db:
                    db.execute(
                        "UPDATE reminders SET delivered = %s WHERE id = %s",
                        (1 if delivered else 0, row["id"]),
                    )
        except Exception as e:
            log.error("reminders check: %s", e)
        await asyncio.sleep(30)


async def main():
    # MySQL может стартовать дольше бота (особенно в docker) — ждём базу
    for attempt in range(1, 11):
        try:
            init_db()
            break
        except Exception as e:
            log.warning("База недоступна (попытка %s/10): %s", attempt, e)
            if attempt == 10:
                raise
            await asyncio.sleep(5)

    token = (
        os.getenv("DISCORD_TOKEN")
        or os.getenv("DISCORD_BOT_TOKEN")
        or os.getenv("BOT_TOKEN")
        or os.getenv("TOKEN")
        or ""
    ).strip("'\"")
    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN не задан. Скопируйте .env.example в .env "
            "и укажите токен из discord.com/developers"
        )
    for cog in COGS:
        await bot.load_extension(cog)
        log.info("Ког загружен: %s", cog)
    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
