"""Ког «Розыгрыши»: запуск розыгрышей и определение победителей."""

import random

import discord
from discord import app_commands
from discord.ext import commands

from db import DB
from utils import is_staff, now_str


class Giveaway(commands.Cog):
    """Розыгрыши призов."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="giveaway", description="Запустить розыгрыш")
    @app_commands.describe(
        prize="Что разыгрываем",
        minutes="Длительность в минутах",
        winners="Сколько победителей",
    )
    @is_staff()
    async def giveaway(self, interaction: discord.Interaction,
                       prize: str, minutes: int = 10, winners: int = 1):
        from datetime import datetime, timedelta
        ends_at = datetime.now() + timedelta(minutes=minutes)

        embed = discord.Embed(
            title="🎉 РОЗЫГРЫШ 🎉",
            description=f"**Приз:** {prize}\n"
                        f"**Победителей:** {winners}\n"
                        f"**Закончится:** {ends_at.strftime('%d.%m.%Y %H:%M')}",
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Реакция 🎉 = участие")
        msg = await interaction.channel.send(embed=embed)
        await msg.add_reaction("🎉")

        with DB() as db:
            db.execute(
                "INSERT INTO giveaways(guild_id, channel_id, message_id, prize,"
                " winners_count, ends_at, created_at) VALUES (%s, %s, %s, %s,"
                " %s, %s, NOW())",
                (interaction.guild.id, interaction.channel.id, msg.id,
                 prize, winners, ends_at),
            )
        await interaction.response.send_message(
            f"🎲 Розыгрыш **{prize}** запущен на {minutes} мин!",
            ephemeral=True,
        )

    async def check_finished(self):
        """Фоновая задача: завершение истёкших розыгрышей."""
        with DB() as db:
            rows = db.fetchall(
                "SELECT * FROM giveaways WHERE ended = 0 AND ends_at <= NOW()"
            )
        for g in rows:
            await self._finish(g)

    async def _finish(self, g: dict):
        guild = self.bot.get_guild(g["guild_id"])
        if not guild:
            with DB() as db:
                db.execute(
                    "UPDATE giveaways SET ended = 1 WHERE id = %s",
                    (g["id"],),
                )
            return
        channel = guild.get_channel(g["channel_id"])
        if not channel:
            return
        try:
            msg = await channel.fetch_message(g["message_id"])
        except discord.NotFound:
            return

        participants = []
        for reaction in msg.reactions:
            if str(reaction.emoji) == "🎉":
                async for user in reaction.users():
                    if not user.bot:
                        participants.append(user)
        participants = list({u.id: u for u in participants}.values())

        winners_count = min(g["winners_count"], len(participants))
        if participants and winners_count:
            winners = random.sample(participants, winners_count)
            winner_text = " ".join(w.mention for w in winners)
            winner_ids = ",".join(str(w.id) for w in winners)
        else:
            winner_text = "😔 Никто не участвовал"
            winner_ids = ""

        embed = discord.Embed(
            title="🏁 Розыгрыш завершён",
            description=f"**Приз:** {g['prize']}\n"
                        f"**Победители:** {winner_text}",
            color=discord.Color.green(),
        )
        embed.set_footer(text=now_str())
        await channel.send(embed=embed)

        with DB() as db:
            db.execute(
                "UPDATE giveaways SET ended = 1, winner_ids = %s WHERE id = %s",
                (winner_ids, g["id"]),
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaway(bot))
