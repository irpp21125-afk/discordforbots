"""Ког «Логи»: настройка канала логов и управление журналированием."""

import discord
from discord import app_commands
from discord.ext import commands

from utils import (
    is_head_admin, get_guild_settings, set_guild_setting,
    send_log,
)


class Logging(commands.Cog):
    """Управление журналом сервера."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- команды ----------

    @app_commands.command(name="logchannel",
                          description="Указать канал для логов (админ)")
    @app_commands.describe(channel="Канал для логов")
    @is_head_admin()
    async def logchannel(self, interaction: discord.Interaction,
                         channel: discord.TextChannel):
        set_guild_setting(interaction.guild.id, "log_channel", channel.id)
        await interaction.response.send_message(
            f"✅ Канал логов: {channel.mention}"
        )

    @app_commands.command(name="logtoggle",
                          description="Вкл/выкл логирование (админ)")
    @app_commands.describe(enabled="Включить?")
    @is_head_admin()
    async def logtoggle(self, interaction: discord.Interaction,
                        enabled: bool):
        set_guild_setting(interaction.guild.id, "log_enabled",
                          1 if enabled else 0)
        await interaction.response.send_message(
            f"📝 Логирование **{'включено' if enabled else 'выключено'}**."
        )

    @app_commands.command(name="logstatus",
                          description="Статус логов (админ)")
    @is_head_admin()
    async def logstatus(self, interaction: discord.Interaction):
        s = get_guild_settings(interaction.guild.id)
        chan_id = s.get("log_channel")
        chan_str = (f"<#{chan_id}>" if chan_id else "❌ Не задан")
        enabled_str = "✅ Включено" if s.get("log_enabled") else "❌ Выключено"
        embed = discord.Embed(
            title="📋 Статус логирования",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Канал", value=chan_str, inline=True)
        embed.add_field(name="Статус", value=enabled_str, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Logging(bot))
