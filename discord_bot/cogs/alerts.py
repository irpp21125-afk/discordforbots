"""Ког «Оповещения»: подписки на ключевые слова с упоминанием роли."""

import discord
from discord import app_commands
from discord.ext import commands

from db import DB
from utils import is_staff


class Alerts(commands.Cog):
    """Уведомления при появлении ключевого слова."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        try:
            with DB() as db:
                subs = db.fetchall(
                    "SELECT * FROM alert_subscriptions WHERE guild_id = %s",
                    (message.guild.id,),
                )
        except Exception:
            return
        text = message.content.lower()
        for sub in subs:
            if sub["keyword"].lower() in text:
                role = message.guild.get_role(int(sub["role_id"]))
                if role and sub["channel_id"] == message.channel.id:
                    await message.reply(
                        f"🔔 {role.mention} — сработало слово "
                        f"**{sub['keyword']}**",
                        allowed_mentions=discord.AllowedMentions(roles=True),
                    )

    @app_commands.command(name="alert_add",
                          description="Подписаться ролью на ключевое слово")
    @app_commands.describe(keyword="Слово", role="Роль для упоминания")
    @is_staff()
    async def alert_add(self, interaction: discord.Interaction,
                        keyword: str, role: discord.Role):
        with DB() as db:
            db.execute(
                "INSERT INTO alert_subscriptions(guild_id, channel_id,"
                " keyword, role_id) VALUES (%s, %s, %s, %s)"
                " ON DUPLICATE KEY UPDATE role_id = VALUES(role_id)",
                (interaction.guild.id, interaction.channel.id,
                 keyword, role.id),
            )
        await interaction.response.send_message(
            f"🔔 Роль {role.mention} теперь получает уведомление "
            f"при слове **{keyword}** в этом канале."
        )

    @app_commands.command(name="alert_remove",
                          description="Удалить подписку на слово")
    @app_commands.describe(keyword="Какое слово")
    @is_staff()
    async def alert_remove(self, interaction: discord.Interaction,
                           keyword: str):
        with DB() as db:
            cur = db.execute(
                "DELETE FROM alert_subscriptions WHERE guild_id = %s "
                "AND channel_id = %s AND keyword = %s",
                (interaction.guild.id, interaction.channel.id, keyword),
            )
        if cur.rowcount:
            await interaction.response.send_message("✅ Подписка удалена.")
        else:
            await interaction.response.send_message(
                "❌ Подписка не найдена.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Alerts(bot))
