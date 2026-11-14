"""Ког «Модерация»: предупреждения, мут, кик, бан, заявки на разбан, аудит."""

import discord
from discord import app_commands
from discord.ext import commands

from db import DB

from support import SupportManager

from utils import (
    is_staff, is_head_admin, audit, now_str, send_mod_log,
)

support = SupportManager()


class Moderation(commands.Cog):
    """Модерация и наказания."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- ПРЕДУПРЕЖДЕНИЕ ----------

    @app_commands.command(name="warn", description="Выдать предупреждение")
    @app_commands.describe(
        user="Кого предупредить", reason="Причина"
    )
    @is_staff()
    async def warn(self, interaction: discord.Interaction,
                   user: discord.User, reason: str):
        guild = interaction.guild
        moderator = interaction.user

        with DB() as db:
            db.execute(
                "INSERT INTO punishments(guild_id, user_id, moderator_id, "
                "type, reason, created_at, expires_at) "
                "VALUES (%s, %s, %s, 'warn', %s, NOW(), NULL)",
                (guild.id, user.id, moderator.id, reason),
            )

        audit(guild.id, user.id, "warn")
        await send_mod_log(
            self.bot, guild,
            f"⚠️ **Предупреждение**\n"
            f"👤 {user.mention} (`{user.id}`)\n"
            f"🛡️ Модератор: {moderator.mention}\n"
            f"📝 {reason}\n"
            f"🕐 {now_str()}",
        )
        await interaction.response.send_message(
            f"✅ {user.mention} получил предупреждение", ephemeral=True
        )

    # ---------- MUTED ----------

    @app_commands.command(name="mute", description="Заблокировать ввод текста")
    @app_commands.describe(
        user="Кого замутить",
        duration="Длительность (минуты, 0 = навсегда)",
        reason="Причина",
    )
    @is_staff()
    async def mute(self, interaction: discord.Interaction,
                   user: discord.User, duration: int = 60, reason: str = ""):
        guild = interaction.guild
        moderator = interaction.user
        role = discord.utils.get(guild.roles, name="Muted")
        if not role:
            role = await guild.create_role(
                name="Muted",
                permissions=discord.Permissions(
                    view_channel=True,
                    send_messages=False,
                    connect=False,
                    speak=False,
                ),
                reason="Создано ботом модерации",
            )

        with DB() as db:
            db.execute(
                "INSERT INTO punishments(guild_id, user_id, moderator_id, "
                "type, reason, duration_minutes, created_at, expires_at) "
                "VALUES (%s, %s, %s, 'mute', %s, %s, NOW(), "
                "DATE_ADD(NOW(), INTERVAL %s MINUTE))",
                (guild.id, user.id, moderator.id, reason,
                 duration, duration),
            )

        audit(guild.id, user.id, "mute")
        if user not in guild.members:
            await interaction.response.send_message(
                "⚠️ Пользователь не на сервере — мут применится при входе.",
                ephemeral=True,
            )
            return
        if role in user.roles:
            await interaction.response.send_message(
                f"⚠️ {user.mention} уже замучен.", ephemeral=True
            )
            return
        try:
            await user.add_roles(role, reason=f"Мут: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Не хватает прав для mute.", ephemeral=True
            )
            return
        await send_mod_log(
            self.bot, guild,
            f"🔇 **Мут**\n👤 {user.mention}\n🛡️ {moderator.mention}\n"
            f"⏱ {duration} мин\n📝 {reason}",
        )
        await interaction.response.send_message(
            f"✅ {user.mention} замучен на {duration or '∞'} минут",
            ephemeral=True,
        )

    async def expire_mutes(self):
        """Фоновая задача: снять мут по истечении срока."""
        try:
            with DB() as db:
                rows = db.fetchall(
                    "SELECT * FROM punishments WHERE type = 'mute' "
                    "AND active = 1 AND expires_at IS NOT NULL "
                    "AND expires_at <= NOW()"
                )
            for row in rows:
                guild = self.bot.get_guild(row["guild_id"])
                if not guild:
                    continue
                user = guild.get_member(int(row["user_id"]))
                if not user:
                    continue
                role = discord.utils.get(guild.roles, name="Muted")
                if role:
                    try:
                        await user.remove_roles(role)
                    except Exception:
                        pass
                with DB() as db2:
                    db2.execute(
                        "UPDATE punishments SET active = 0 WHERE id = %s",
                        (row["id"],),
                    )
        except Exception as e:
            print(f"mute expiry error: {e}")

    # ---------- KICK ----------

    @app_commands.command(name="kick", description="Выгнать пользователя с сервера")
    @app_commands.describe(user="Кого кикнуть", reason="Причина")
    @is_staff()
    async def kick(self, interaction: discord.Interaction,
                   user: discord.User, reason: str):
        guild = interaction.guild
        moderator = interaction.user
        try:
            await user.kick(reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Нет прав для кика.", ephemeral=True
            )
            return
        with DB() as db:
            db.execute(
                "INSERT INTO punishments(guild_id, user_id, moderator_id, "
                "type, reason, created_at) VALUES (%s, %s, %s, 'kick', %s, NOW())",
                (guild.id, user.id, moderator.id, reason),
            )
        audit(guild.id, user.id, "kick")
        await send_mod_log(
            self.bot, guild,
            f"🚪 **Кик**\n👤 {user.mention}\n🛡️ {moderator.mention}\n📝 {reason}",
        )
        await interaction.response.send_message(
            f"✅ {user.mention} кикнут", ephemeral=True
        )

    # ---------- BAN ----------

    @app_commands.command(name="ban", description="Забанить пользователя")
    @app_commands.describe(user="Кого забанить", reason="Причина")
    @is_staff()
    async def ban(self, interaction: discord.Interaction,
                  user: discord.User, reason: str):
        guild = interaction.guild
        moderator = interaction.user
        try:
            await guild.ban(user, reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Нет прав для бана.", ephemeral=True
            )
            return
        with DB() as db:
            db.execute(
                "INSERT INTO punishments(guild_id, user_id, moderator_id, "
                "type, reason, created_at) VALUES (%s, %s, %s, 'ban', %s, NOW())",
                (guild.id, user.id, moderator.id, reason),
            )
        audit(guild.id, user.id, "ban")
        await send_mod_log(
            self.bot, guild,
            f"🔨 **Бан**\n👤 {user.mention}\n🛡️ {moderator.mention}\n📝 {reason}",
        )
        await interaction.response.send_message(
            f"✅ {user.mention} забанен", ephemeral=True
        )

    # ---------- UNBAN ----------

    @app_commands.command(name="unban", description="Снять бан")
    @app_commands.describe(user_id="ID забаненного", reason="Причина")
    @is_head_admin()
    async def unban(self, interaction: discord.Interaction,
                    user_id: int, reason: str = ""):
        guild = interaction.guild
        try:
            await guild.unban(discord.Object(id=user_id), reason=reason)
        except discord.NotFound:
            await interaction.response.send_message(
                "❌ Пользователь не забанен.", ephemeral=True
            )
            return
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Нет прав для разбана.", ephemeral=True
            )
            return
        await interaction.response.send_message("✅ Бан снят")

    # ---------- ЗАЯВКИ НА РАЗБАН ----------

    @app_commands.command(name="unban_request", description="Заявка на разбан")
    @app_commands.describe(reason="Почему вас нужно разбанить")
    async def unban_request(self, interaction: discord.Interaction,
                            reason: str):
        settings = _guild_settings(interaction.guild.id)
        await interaction.response.send_message(
            "📝 Заявка отправлена модераторам.", ephemeral=True,
        )
        await send_mod_log(
            self.bot, interaction.guild,
            f"📨 **Заявка на разбан**\n"
            f"👤 {interaction.user.mention} (`{interaction.user.id}`)\n"
            f"📝 {reason}\n"
            f"🕐 {now_str()}",
        )

    # ---------- ИСТОРИЯ НАКАЗАНИЙ ----------

    @app_commands.command(name="punishments", description="История наказаний")
    @app_commands.describe(user="Проверить пользователя")
    @is_staff()
    async def punishments_list(self, interaction: discord.Interaction,
                               user: discord.User):
        with DB() as db:
            rows = db.fetchall(
                "SELECT * FROM punishments WHERE guild_id = %s AND user_id = %s "
                "ORDER BY created_at DESC LIMIT 20",
                (interaction.guild.id, user.id),
            )
        if not rows:
            await interaction.response.send_message(
                f"✅ {user.mention} не имеет наказаний", ephemeral=True
            )
            return
        lines = [
            f"**[{r['type'].upper()}]** {r['reason'][:50]} — "
            f"🛡️ {r['moderator_id']} | {str(r['created_at'])[:16]}"
            for r in rows
        ]
        await interaction.response.send_message(
            f"📋 Наказания {user.mention}:\n" + "\n".join(lines),
            ephemeral=True,
        )

    # ---------- ОЧИСТКА КАНАЛА ----------

    @app_commands.command(name="clear",
                          description="Удалить последние сообщения в канале")
    @app_commands.describe(
        count="Сколько сообщений удалить (1-200)",
        user="Удалять только сообщения этого пользователя",
    )
    @is_staff()
    async def clear(self, interaction: discord.Interaction,
                    count: int,
                    user: discord.User = None):
        channel = interaction.channel
        await interaction.response.defer(ephemeral=True)

        if count < 1 or count > 200:
            await interaction.followup.send(
                "❌ Количество должно быть от 1 до 200.", ephemeral=True
            )
            return

        def check(msg: discord.Message) -> bool:
            if user is not None:
                return msg.author.id == user.id
            return True

        try:
            deleted = await channel.purge(
                limit=count, check=check, bulk=True,
                reason=f"clear by {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Нет права Manage Messages.", ephemeral=True
            )
            return

        audit(interaction.guild.id, interaction.user.id,
              f"clear:{len(deleted)}")
        await send_mod_log(
            self.bot, interaction.guild,
            f"🧹 **Очистка** в {channel.mention}\n"
            f"🗑 Удалено: **{len(deleted)}**\n"
            f"🛡️ {interaction.user.mention}"
            + (f"\n👤 Только от: {user.mention}" if user else ""),
        )
        await interaction.followup.send(
            f"✅ Удалено сообщений: **{len(deleted)}**", ephemeral=True
        )

    # ---------- SLOWMODE ----------

    @app_commands.command(name="slowmode",
                          description="Замедлить чат (задержка между сообщениями)")
    @app_commands.describe(
        delay="Задержка в секундах (0 = выключить, макс. 21600)",
        channel="Канал (по умолчанию текущий)",
    )
    @is_staff()
    async def slowmode(self, interaction: discord.Interaction,
                       delay: int,
                       channel: discord.TextChannel = None):
        channel = channel or interaction.channel
        if delay < 0 or delay > 21600:
            await interaction.response.send_message(
                "❌ Задержка должна быть от 0 до 21600 секунд.",
                ephemeral=True,
            )
            return
        try:
            await channel.edit(
                slowmode_delay=delay,
                reason=f"slowmode by {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Нет права Manage Channels.", ephemeral=True
            )
            return
        audit(interaction.guild.id, interaction.user.id,
              f"slowmode:{seconds}")
        text = (
            f"🐢 Slowmode в **{channel.mention}**: **{seconds} сек**"
            if seconds else
            f"🐇 Slowmode в {channel.mention} **выключен**"
        )
        await send_mod_log(self.bot, interaction.guild,
                           f"{text}\n🛡️ {interaction.user.mention}")
        await interaction.response.send_message(text)

    # ---------- SAY ----------

    @app_commands.command(name="say",
                          description="Отправить сообщение от имени бота")
    @app_commands.describe(
        text="Текст сообщения",
        channel="Куда отправить (по умолчанию текущий канал)",
    )
    @app_commands.rename(text="message")
    @is_staff()
    async def say(self, interaction: discord.Interaction, text: str,
                  channel: discord.TextChannel = None):
        channel = channel or interaction.channel
        try:
            await channel.send(text[:2000])
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Нет прав для отправки в этот канал.", ephemeral=True
            )
            return
        audit(interaction.guild.id, interaction.user.id, "say")
        await interaction.response.send_message(
            "✅ Сообщение отправлено.", ephemeral=True
        )

    # ---------- EMBED ----------

    @app_commands.command(name="embed",
                          description="Отправить embed-сообщение от имени бота")
    @app_commands.describe(
        title="Заголовок",
        description="Основной текст",
        color="Цвет (hex, например ff0000)",
        channel="Куда отправить",
        footer="Текст в футере",
    )
    @is_head_admin()
    async def embed_cmd(self, interaction: discord.Interaction,
                        title: str, description: str,
                        color: str = "5865F2",
                        channel: discord.TextChannel = None,
                        footer: str = ""):
        channel = channel or interaction.channel
        try:
            embed_color = discord.Color(int(color.lstrip("#"), 16))
        except ValueError:
            await interaction.response.send_message(
                "❌ Цвет должен быть в hex-формате, например `ff0000`.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=title[:256], description=description[:4000],
            color=embed_color, timestamp=discord.utils.utcnow(),
        )
        if footer:
            embed.set_footer(text=footer[:2048])

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Нет прав для отправки в этот канал.", ephemeral=True
            )
            return
        audit(interaction.guild.id, interaction.user.id, "embed")
        await interaction.response.send_message(
            "✅ Embed отправлен.", ephemeral=True
        )

    # ---------- СЕРВЕРНЫЙ АУДИТ ----------

    @app_commands.command(name="audit", description="Последние события сервера")
    @app_commands.describe(count="Количество событий")
    @is_staff()
    async def audit_log(self, interaction: discord.Interaction,
                        count: int = 20):
        with DB() as db:
            rows = db.fetchall(
                "SELECT * FROM activity_log WHERE guild_id = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (interaction.guild.id, count),
            )
        if not rows:
            await interaction.response.send_message(
                "Нет записей в журнале.", ephemeral=True
            )
            return
        lines = [
            f"**{r['event']}** — user_id={r['user_id']} "
            f"| {str(r['created_at'])[:16]}"
            for r in rows
        ]
        embed = discord.Embed(
            title="📜 Журнал действий",
            description="\n".join(lines),
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


def _guild_settings(guild_id: int) -> dict:
    from utils import get_guild_settings
    return get_guild_settings(guild_id)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
