"""Ког «Обращения»: тикет-каналы в Discord + общая база тикетов."""

import discord
from discord import app_commands
from discord.ext import commands

from db import DB
from support import SupportManager
from utils import is_staff, send_mod_log

support = SupportManager()


class Tickets(commands.Cog):
    """Создание и обработка обращений."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- пользователь: создать обращение ----------

    @app_commands.command(name="ticket", description="Создать обращение")
    @app_commands.describe(
        message="Опишите вашу проблему или вопрос",
        category="Категория обращения",
        priority="Насколько срочно?",
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="Вопрос", value="Вопрос"),
        app_commands.Choice(name="Жалоба", value="Жалоба"),
        app_commands.Choice(name="Тех. проблема", value="Тех. проблема"),
        app_commands.Choice(name="Другое", value="Другое"),
    ])
    @app_commands.choices(priority=[
        app_commands.Choice(name="Низкий", value="low"),
        app_commands.Choice(name="Обычный", value="normal"),
        app_commands.Choice(name="Срочный", value="high"),
    ])
    async def ticket_cmd(self, interaction: discord.Interaction,
                         message: str, category: str = "Другое",
                         priority: str = "normal"):
        guild = interaction.guild
        user = interaction.user
        settings = _guild_settings(guild.id)

        # один открытый тикет на пользователя
        open_rows = support.get_tickets_for_author("dc", user.id)
        if any(t["status"] != "closed" for t in open_rows):
            await interaction.response.send_message(
                "⚠️ У вас уже есть открытое обращение. "
                "Сначала закройте его: `/ticket_close`",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # канал тикета в категории
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True
            ),
        }
        support_role = settings.get("ticket_support_role")
        if support_role:
            role = guild.get_role(int(support_role))
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True
                )
        category_obj = None
        if settings.get("ticket_category"):
            category_obj = guild.get_channel(int(settings["ticket_category"]))

        channel = await guild.create_text_channel(
            name=f"ticket-{user.display_name[:20]}".lower().replace(" ", "-"),
            overwrites=overwrites,
            category=category_obj,
            topic=f"Обращение от {user} ({user.id})",
        )

        ticket_id = support.create_ticket_dc(
            guild.id, user.id, message, category, priority, channel.id
        )

        embed = discord.Embed(
            title=f"🎫 Обращение #{ticket_id}",
            description=message,
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Автор", value=f"{user.mention} (`{user.id}`)")
        embed.add_field(name="Категория", value=category)
        embed.add_field(name="Приоритет", value=priority)
        await channel.send(
            content=f"{user.mention} "
                    + (f"<@&{support_role}>" if support_role else ""),
            embed=embed,
        )

        await send_mod_log(
            self.bot, guild,
            f"🎫 Новое обращение **#{ticket_id}** от {user.mention} "
            f"в {channel.mention}",
        )
        await interaction.followup.send(
            f"✅ Обращение #{ticket_id} создано: {channel.mention}",
            ephemeral=True,
        )

    # ---------- пользователь: закрыть ----------

    @app_commands.command(name="ticket_close", description="Закрыть своё обращение")
    async def ticket_close(self, interaction: discord.Interaction):
        rows = support.get_tickets_for_author("dc", interaction.user.id)
        own = [t for t in rows
               if t["status"] != "closed"
               and t.get("channel_id") == interaction.channel_id]
        if not own:
            await interaction.response.send_message(
                "В этом канале нет вашего открытого обращения.", ephemeral=True
            )
            return
        ticket = own[0]
        support.close_ticket(ticket["id"])
        await interaction.response.send_message("🔴 Обращение закрывается через 10 сек…")
        await _close_channel(self.bot, interaction.channel, ticket["id"])

    # ---------- персонал: ответить ----------

    @app_commands.command(name="ticket_answer", description="Ответить на обращение")
    @app_commands.describe(ticket_id="Номер обращения", text="Текст ответа")
    @is_staff()
    async def ticket_answer(self, interaction: discord.Interaction,
                            ticket_id: int, text: str):
        ticket = support.get_ticket_by_id(ticket_id)
        if not ticket:
            await interaction.response.send_message("❌ Обращение не найдено",
                                                    ephemeral=True)
            return
        support.add_reply(ticket_id, text, is_admin=True,
                          author_name=str(interaction.user))
        # в канал тикета
        chan = interaction.guild.get_channel(int(ticket["channel_id"] or 0))
        if chan:
            embed = discord.Embed(
                title=f"📨 Ответ на обращение #{ticket_id}",
                description=text, color=discord.Color.green(),
            )
            embed.set_footer(text=f"Ответил: {interaction.user}")
            await chan.send(embed=embed)
        # уведомить автора в ЛС
        try:
            member = interaction.guild.get_member(int(ticket["author_ref"]))
            if member:
                await member.send(f"📨 **Ответ на обращение #{ticket_id}**:\n{text}")
        except discord.Forbidden:
            pass
        await interaction.response.send_message(
            f"✅ Ответ отправлен в обращение #{ticket_id}"
        )

    @app_commands.command(name="ticket_close_id",
                          description="Закрыть обращение по номеру")
    @app_commands.describe(ticket_id="Номер обращения")
    @is_staff()
    async def ticket_close_id(self, interaction: discord.Interaction,
                              ticket_id: int):
        ticket = support.get_ticket_by_id(ticket_id)
        if not ticket or ticket.get("guild_id") != interaction.guild.id:
            await interaction.response.send_message("❌ Не найдено", ephemeral=True)
            return
        support.close_ticket(ticket_id)
        await interaction.response.send_message(f"🔴 #{ticket_id} закрыто")
        chan = interaction.guild.get_channel(int(ticket["channel_id"] or 0))
        if chan:
            await _close_channel(self.bot, chan, ticket_id)

    # ---------- персонал: список ----------

    @app_commands.command(name="tickets", description="Список открытых обращений")
    @is_staff()
    async def tickets_list(self, interaction: discord.Interaction):
        rows = [t for t in support.get_open_tickets()
                if t.get("guild_id") == interaction.guild.id]
        if not rows:
            await interaction.response.send_message("✅ Открытых обращений нет",
                                                    ephemeral=True)
            return
        lines = [
            f"**#{t['id']}** [{t['priority']}] {t['category']} — "
            f"<@{t['author_ref']}>: {t['message'][:60]}"
            for t in rows[:15]
        ]
        await interaction.response.send_message(
            "🎫 **Открытые обращения:**\n" + "\n".join(lines), ephemeral=True
        )

    # ---------- статистика обращений ----------

    @app_commands.command(name="ticket_stats", description="Статистика обращений")
    @is_staff()
    async def ticket_stats(self, interaction: discord.Interaction):
        counts = support.get_counts_by_status()
        avg_h = support.get_avg_response_hours()
        avg_r = support.get_avg_rating()
        embed = discord.Embed(title="📊 Обращения", color=discord.Color.gold())
        embed.add_field(name="🟢 Открытые", value=counts["open"])
        embed.add_field(name="🟡 Отвеченные", value=counts["answered"])
        embed.add_field(name="🔴 Закрытые", value=counts["closed"])
        embed.add_field(name="Всего", value=counts["total"])
        embed.add_field(name="Ср. время ответа",
                        value=f"{avg_h} ч" if avg_h else "—")
        embed.add_field(name="Ср. оценка",
                        value=f"{avg_r} ⭐" if avg_r else "—")
        await interaction.response.send_message(embed=embed)


async def _close_channel(bot, channel, ticket_id: int):
    import asyncio
    await asyncio.sleep(10)
    try:
        await channel.send(f"🔒 Обращение #{ticket_id} закрыто. Канал удалён.")
        await asyncio.sleep(3)
        await channel.delete()
    except Exception:
        pass


def _guild_settings(guild_id: int) -> dict:
    from utils import get_guild_settings
    return get_guild_settings(guild_id)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
