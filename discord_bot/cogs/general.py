"""Ког «Общие настройки»: конфигурация бота на сервере, баннер, аудит настроек."""

import random

import discord
from discord import app_commands
from discord.ext import commands

from db import DB
from utils import (
    get_guild_settings, set_guild_setting, is_head_admin, audit,
)


class General(commands.Cog):
    """Общие настройки и информация."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Приветствие в welcome-канале."""
        settings = get_guild_settings(member.guild.id)
        chan_id = settings.get("welcome_channel")
        if not chan_id:
            return
        channel = member.guild.get_channel(int(chan_id))
        if channel:
            text = settings.get("welcome_text") or "Добро пожаловать!"
            await channel.send(text.replace("{user}", member.mention))
        audit(member.guild.id, member.id, "join")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        audit(member.guild.id, member.id, "leave")

    # ---------- конфигурация ----------

    @app_commands.command(name="config", description="Текущие настройки сервера")
    @is_head_admin()
    async def config_show(self, interaction: discord.Interaction):
        s = get_guild_settings(interaction.guild.id)
        embed = discord.Embed(
            title=f"⚙️ Настройки {interaction.guild.name}",
            color=discord.Color.blurple(),
        )
        for key in ["prefix", "mod_log_channel", "ticket_category",
                    "ticket_support_role", "welcome_channel",
                    "levelup_channel", "economy_enabled",
                    "autorole_enabled", "autorole_id", "anti_raid"]:
            val = s.get(key)
            if isinstance(val, int) and val and key.endswith("channel"):
                val = f"<#{val}>"
            elif isinstance(val, int) and val and key.endswith("role"):
                val = f"<@&{val}>"
            embed.add_field(name=key, value=str(val or "—"), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    config_set = app_commands.Group(
        name="config_set", description="Изменить настройку"
    )

    @config_set.command(name="modlog", description="Канал журнала модерации")
    @is_head_admin()
    async def set_modlog(self, interaction: discord.Interaction,
                         channel: discord.TextChannel):
        set_guild_setting(interaction.guild.id, "mod_log_channel", channel.id)
        await interaction.response.send_message(
            f"✅ Журнал модерации: {channel.mention}"
        )

    @config_set.command(name="tickets", description="Категория для тикетов")
    @is_head_admin()
    async def set_tickets(self, interaction: discord.Interaction,
                          category: discord.CategoryChannel):
        set_guild_setting(interaction.guild.id, "ticket_category", category.id)
        await interaction.response.send_message(
            f"✅ Тикеты будут создаваться в категории «{category.name}»"
        )

    @config_set.command(name="support_role",
                        description="Роль, которая видит тикеты")
    @is_head_admin()
    async def set_support_role(self, interaction: discord.Interaction,
                               role: discord.Role):
        set_guild_setting(interaction.guild.id, "ticket_support_role", role.id)
        await interaction.response.send_message(
            f"✅ Роль {role.mention} будет получать тикеты"
        )

    @config_set.command(name="welcome", description="Канал приветствий")
    @is_head_admin()
    async def set_welcome(self, interaction: discord.Interaction,
                          channel: discord.TextChannel,
                          text: str = "Добро пожаловать, {user}!"):
        set_guild_setting(interaction.guild.id, "welcome_channel", channel.id)
        set_guild_setting(interaction.guild.id, "welcome_text", text)
        await interaction.response.send_message(
            f"✅ Приветствия: {channel.mention}"
        )

    @config_set.command(name="levelup", description="Канал повышения уровня")
    @is_head_admin()
    async def set_levelup(self, interaction: discord.Interaction,
                          channel: discord.TextChannel):
        set_guild_setting(interaction.guild.id, "levelup_channel", channel.id)
        await interaction.response.send_message(
            f"✅ Уровни: {channel.mention}"
        )

    # ---------- баннер сервера ----------

    @app_commands.command(name="server_banner", description="Показать баннер сервера")
    async def banner(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild.banner:
            await interaction.response.send_message("Баннер не установлен.",
                                                    ephemeral=True)
            return
        embed = discord.Embed(title=f"Баннер: {guild.name}",
                              color=discord.Color.blurple())
        embed.set_image(url=guild.banner.url)
        await interaction.response.send_message(embed=embed)

    # ---------- информация о боте ----------

    @app_commands.command(name="botinfo", description="Информация о боте")
    async def botinfo(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 Support Bot",
            description=(
                "Поддержка через обращения, модерация, экономика,\n"
                "розыгрыши и автоматизация. Данные — в MySQL."
            ),
            color=discord.Color.green(),
        )
        embed.add_field(name="Серверов", value=len(self.bot.guilds))
        embed.add_field(name="Модулей", value="10")
        await interaction.response.send_message(embed=embed)

    # ---------- ПРИВЕТСТВИЯ ----------

    @app_commands.command(name="welcomemsg",
                          description="Настроить текст приветствия (админ)")
    @app_commands.describe(text="Текст (используйте {user} для упоминания)")
    @app_commands.rename(text="message")
    @is_head_admin()
    async def welcomemsg(self, interaction: discord.Interaction, text: str):
        set_guild_setting(interaction.guild.id, "welcome_text",
                          text[:500])
        await interaction.response.send_message(
            f"✅ Текст приветствия обновлён.\n"
            f"📝 {text[:200]}", ephemeral=True
        )

    @app_commands.command(name="welcomechannel",
                          description="Канал для приветствий (админ)")
    @is_head_admin()
    async def welcomechannel(self, interaction: discord.Interaction,
                             channel: discord.TextChannel):
        set_guild_setting(interaction.guild.id, "welcome_channel", channel.id)
        await interaction.response.send_message(
            f"✅ Приветствия отправляются в {channel.mention}"
        )

    @app_commands.command(name="welcometoggle",
                          description="Вкл/выкл приветствия (админ)")
    @app_commands.describe(enabled="Включить?")
    @is_head_admin()
    async def welcometoggle(self, interaction: discord.Interaction,
                            enabled: bool):
        set_guild_setting(interaction.guild.id, "welcome_enabled",
                          1 if enabled else 0)
        await interaction.response.send_message(
            f"✅ Приветствия **{'включены' if enabled else 'выключены'}**."
        )

    @app_commands.command(name="welcomeautorole",
                          description="Авто-роль при входе (админ)")
    @app_commands.describe(role="Роль для автовыдачи")
    @is_head_admin()
    async def welcomeautorole(self, interaction: discord.Interaction,
                              role: discord.Role):
        set_guild_setting(interaction.guild.id, "welcome_autorole", role.id)
        set_guild_setting(interaction.guild.id, "autorole_enabled", 1)
        await interaction.response.send_message(
            f"✅ Автосдача роли {role.mention} при входе включена."
        )

    # ---------- УТИЛИТЫ ----------

    @app_commands.command(name="ping", description="Пинг бота")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        ws = self.bot.ws and self.bot.ws.latency * 1000
        ws_str = f"{ws:.0f}ms" if ws else "—"
        await interaction.response.send_message(
            f"🏓 Пинг: **{latency}ms** (WS: {ws_str})"
        )

    @app_commands.command(name="avatar",
                          description="Показать аватар пользователя")
    @app_commands.describe(user="Кого (по умолчанию ваш)")
    async def avatar(self, interaction: discord.Interaction,
                     user: discord.User = None):
        user = user or interaction.user
        embed = discord.Embed(title=f"Аватар: {user.display_name}")
        embed.set_image(url=user.display_avatar.with_size(256).url)
        embed.set_footer(text=f"ID: {user.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roll",
                          description="Бросить кубик (1-N)")
    @app_commands.describe(max="Максимальное значение (1-1000)")
    async def roll(self, interaction: discord.Interaction, max: int = 100):
        max = max(1, min(max, 1000))
        result = random.randint(1, max)
        embed = discord.Embed(
            title="🎲 Бросок кубика",
            description=f"Выпало: **{result}** / {max}",
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reminder",
                          description="Напоминание через N минут")
    @app_commands.describe(minutes="Через сколько минут", text="Текст напоминания")
    @app_commands.rename(minutes="mins")
    async def reminder(self, interaction: discord.Interaction,
                       mins: int, text: str):
        if mins <= 0 or mins > 1440:
            await interaction.response.send_message(
                "❌ Минуты: от 1 до 1440 (1 день)", ephemeral=True)
            return
        with DB() as db:
            db.execute(
                "INSERT INTO reminders(guild_id, user_id, channel_id, "
                "message, remind_at, created_at) VALUES "
                "(%s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL %s MINUTE), NOW())",
                (interaction.guild.id, interaction.user.id,
                 interaction.channel.id, text[:500], mins),
            )
        await interaction.response.send_message(
            f"⏰ Напоминание через **{mins} мин**: «{text[:100]}»"
        )
        audit(interaction.guild.id, interaction.user.id,
              f"reminder:{mins}m")

    @app_commands.command(name="suggest",
                          description="Отправить предложение на сервер")
    @app_commands.describe(text="Текст предложения")
    async def suggest(self, interaction: discord.Interaction, text: str):
        with DB() as db:
            db.execute(
                "INSERT INTO suggestions(guild_id, user_id, channel_id, "
                "text, created_at) VALUES (%s, %s, %s, %s, NOW())",
                (interaction.guild.id, interaction.user.id,
                 interaction.channel.id, text[:500]),
            )
        await interaction.response.send_message(
            "💡 Предложение отправлено модераторам!", ephemeral=True
        )
        audit(interaction.guild.id, interaction.user.id, "suggest")

    @app_commands.command(name="urban",
                          description="Показать аватар (alias)")
    @app_commands.describe(user="Кого")
    async def urban(self, interaction: discord.Interaction,
                    user: discord.User = None):
        await self.avatar(interaction, user)


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
