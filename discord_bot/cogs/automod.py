"""Ког «Автоматизация / Безопасность»: фильтр слов, антиспам, антифлуд,
анти-рейид."""

import time

from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

from db import DB

from utils import (
    is_head_admin, is_staff, set_guild_setting, get_guild_settings,
    audit, filter_add_word, filter_remove_word, filter_list_words,
    send_log,
)

# {user_id: [timestamps]} — антиспам / антифлуд
_msg_times: dict = defaultdict(list)
_last_msg: dict = {}


class Automod(commands.Cog):
    """Автоматическая модерация."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._words_cache: dict = {}
        self._cache_ts: dict = {}

    # ---------- кэш запрещённых слов ----------

    def _get_words(self, guild_id: int) -> list:
        now = time.time()
        if guild_id in self._words_cache and now - self._cache_ts.get(
            guild_id, 0
        ) < 30:
            return self._words_cache[guild_id]
        try:
            words = filter_list_words(guild_id)
        except Exception:
            words = []
        self._words_cache[guild_id] = words
        self._cache_ts[guild_id] = now
        return words

    def _invalidate(self, guild_id: int):
        self._cache_ts[guild_id] = 0

    # ---------- обработка сообщений ----------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        try:
            settings = get_guild_settings(message.guild.id)
        except Exception:
            return

        # 1) анти-рейид: 5 сообщений за 5 секунд
        if settings.get("anti_raid"):
            now = time.time()
            times = [t for t in _msg_times[message.author.id] if now - t < 5]
            times.append(now)
            _msg_times[message.author.id] = times
            if len(times) >= 5:
                await self._delete(message, "анти-рейид")
                return

        # 2) антиспам: лимит сообщений за скользящее окно
        if settings.get("antispam_enabled"):
            limit = int(settings.get("antispam_limit") or 5)
            now = time.time()
            times = [t for t in _msg_times[message.author.id]
                     if now - t < 10]
            times.append(now)
            _msg_times[message.author.id] = times
            if len(times) > limit:
                await self._delete(message, "антиспам")
                return

        # 3) антифлуд: одинаковые сообщения подряд
        if settings.get("antiflood_enabled"):
            window = int(settings.get("antiflood_seconds") or 5)
            key = (message.author.id, message.content.strip().lower())
            now = time.time()
            prev = _last_msg.get(key)
            _last_msg[key] = now
            if prev and now - prev < window:
                await self._delete(message, "антифлуд")
                return

        # 4) фильтр слов
        if settings.get("filter_enabled") and message.content:
            words = self._get_words(message.guild.id)
            if words:
                low = message.content.lower()
                hit = next((w for w in words if w in low), None)
                if hit:
                    await self._delete(message, f"фильтр: {hit}")
                    try:
                        await message.author.send(
                            f"🚫 Ваше сообщение удалено: запрещённое слово "
                            f"**{hit}** в сервере **{message.guild.name}**."
                        )
                    except discord.Forbidden:
                        pass
                    return

    async def _delete(self, message: discord.Message, why: str):
        try:
            await message.delete()
        except Exception:
            return
        audit(message.guild.id, message.author.id, f"msg_deleted:{why}")
        await send_log(
            message.guild,
            f"🗑 Сообщение удалено ({why}) — {message.author.mention} "
            f"в {message.channel.mention}",
        )

    # ---------- ФИЛЬТР СЛОВ ----------

    @app_commands.command(name="addword",
                          description="Добавить слово в фильтр (админ)")
    @app_commands.describe(word="Запрещённое слово")
    @is_head_admin()
    async def addword(self, interaction: discord.Interaction, word: str):
        word = word.lower().strip()
        if len(word) < 2:
            await interaction.response.send_message(
                "❌ Слово слишком короткое.", ephemeral=True
            )
            return
        filter_add_word(interaction.guild.id, word)
        self._invalidate(interaction.guild.id)
        audit(interaction.guild.id, interaction.user.id, f"addword:{word}")
        await interaction.response.send_message(
            f"✅ Слово **{word}** добавлено в фильтр."
        )

    @app_commands.command(name="removeword",
                          description="Убрать слово из фильтра (админ)")
    @app_commands.describe(word="Какое слово")
    @is_head_admin()
    async def removeword(self, interaction: discord.Interaction,
                         word: str):
        word = word.lower().strip()
        with DB() as db:
            cur = db.execute(
                "DELETE FROM filter_words WHERE guild_id = %s AND word = %s",
                (interaction.guild.id, word),
            )
        self._invalidate(interaction.guild.id)
        if cur.rowcount:
            await interaction.response.send_message(
                f"✅ Слово **{word}** убрано из фильтра."
            )
        else:
            await interaction.response.send_message(
                "❌ Такое слово не найдено в фильтре.", ephemeral=True
            )

    @app_commands.command(name="filterlist",
                          description="Список запрещённых слов")
    @is_staff()
    async def filterlist(self, interaction: discord.Interaction):
        words = filter_list_words(interaction.guild.id)
        if not words:
            await interaction.response.send_message(
                "Фильтр пуст.", ephemeral=True
            )
            return
        chunk = ", ".join(f"`{w}`" for w in words[:100])
        embed = discord.Embed(
            title=f"🚫 Фильтр слов ({len(words)})",
            description=chunk or "—",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="filtertoggle",
                          description="Вкл/выкл фильтр слов (админ)")
    @app_commands.describe(enabled="Включить?")
    @is_head_admin()
    async def filtertoggle(self, interaction: discord.Interaction,
                           enabled: bool):
        set_guild_setting(interaction.guild.id, "filter_enabled",
                          1 if enabled else 0)
        await interaction.response.send_message(
            f"✅ Фильтр слов **{'включён' if enabled else 'выключен'}**."
        )

    # ---------- АНТИСПАМ ----------

    @app_commands.command(name="antispam",
                          description="Настроить антиспам (админ)")
    @app_commands.describe(
        enabled="Включить?",
        limit="Максимум сообщений за 10 секунд",
    )
    @is_head_admin()
    async def antispam(self, interaction: discord.Interaction,
                       enabled: bool, limit: int = 5):
        limit = max(2, min(limit, 30))
        set_guild_setting(interaction.guild.id, "antispam_enabled",
                          1 if enabled else 0)
        set_guild_setting(interaction.guild.id, "antispam_limit", limit)
        await interaction.response.send_message(
            f"✅ Антиспам **{'включён' if enabled else 'выключен'}**\n"
            f"📊 Лимит: **{limit}** сообщений / 10 сек"
        )

    # ---------- АНТИФЛУД ----------

    @app_commands.command(name="antiflood",
                          description="Настроить антифлуд (админ)")
    @app_commands.describe(
        enabled="Включить?",
        seconds="Окно для повторов (секунды)",
    )
    @is_head_admin()
    async def antiflood(self, interaction: discord.Interaction,
                        enabled: bool, seconds: int = 5):
        seconds = max(1, min(seconds, 60))
        set_guild_setting(interaction.guild.id, "antiflood_enabled",
                          1 if enabled else 0)
        set_guild_setting(interaction.guild.id, "antiflood_seconds", seconds)
        await interaction.response.send_message(
            f"✅ Антифлуд **{'включён' if enabled else 'выключен'}**\n"
            f"⏱ Повторы в течение **{seconds} сек** удаляются"
        )

    # ---------- СТАТУС ----------

    @app_commands.command(name="automod",
                          description="Статус и настройки автоматизации")
    @is_staff()
    async def automod_status(self, interaction: discord.Interaction):
        s = get_guild_settings(interaction.guild.id)
        on = lambda v: "✅" if v else "❌"
        embed = discord.Embed(
            title="🛡️ Автоматизация",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Анти-рейид", value=on(s.get("anti_raid")),
                        inline=True)
        embed.add_field(name="Фильтр слов",
                        value=f"{on(s.get('filter_enabled'))} "
                              f"({len(filter_list_words(interaction.guild.id))})",
                        inline=True)
        embed.add_field(
            name="Антиспам",
            value=f"{on(s.get('antispam_enabled'))} "
                  f"({s.get('antispam_limit')}/10с)", inline=True,
        )
        embed.add_field(
            name="Антифлуд",
            value=f"{on(s.get('antiflood_enabled'))} "
                  f"({s.get('antiflood_seconds')}с)", inline=True,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Automod(bot))

