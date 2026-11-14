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
from discord.ext import commands
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db  # noqa: E402

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


async def main():
    init_db()
    token = os.getenv("DISCORD_TOKEN", "")
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
