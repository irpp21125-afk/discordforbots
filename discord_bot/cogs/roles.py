"""Ког «Управление ролями»: автороль, роли по уровню, выдача ролей."""

import discord
from discord import app_commands
from discord.ext import commands

from db import DB
from utils import get_guild_settings, is_head_admin, set_guild_setting


class Roles(commands.Cog):
    """Управление ролями."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Выдача автороли при входе."""
        if member.bot:
            return
        settings = get_guild_settings(member.guild.id)
        if settings.get("autorole_enabled") and settings.get("autorole_id"):
            role = member.guild.get_role(int(settings["autorole_id"]))
            if role:
                try:
                    await member.add_roles(role, reason="Autorole")
                except Exception:
                    pass
        with DB() as db:
            db.execute(
                "INSERT INTO dc_users(id, username, display_name, guild_id,"
                " registration_date, last_activity) VALUES (%s, %s, %s, %s,"
                " NOW(), NOW()) ON DUPLICATE KEY UPDATE last_activity = NOW(),"
                " guild_id = VALUES(guild_id)",
                (member.id, member.name, member.display_name, member.guild.id),
            )

    # ---------- настройки автороли ----------

    @app_commands.command(name="autorole_set",
                          description="Назначить автороль для новых участников")
    @app_commands.describe(role="Роль, которая выдаётся автоматически")
    @is_head_admin()
    async def autorole_set(self, interaction: discord.Interaction,
                           role: discord.Role):
        set_guild_setting(interaction.guild.id, "autorole_id", role.id)
        set_guild_setting(interaction.guild.id, "autorole_enabled", 1)
        await interaction.response.send_message(
            f"✅ Автороль {role.mention} будет выдаваться новым участникам."
        )

    # ---------- роль по уровню ----------

    @app_commands.command(name="levelrole",
                          description="Добавить роль за уровень")
    @app_commands.describe(role="Какая роль", level="На каком уровне")
    @is_head_admin()
    async def levelrole(self, interaction: discord.Interaction,
                        role: discord.Role, level: int):
        with DB() as db:
            db.execute(
                "INSERT INTO level_roles(guild_id, role_id, level_required)"
                " VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE"
                " level_required = VALUES(level_required)",
                (interaction.guild.id, role.id, level),
            )
        await interaction.response.send_message(
            f"✅ Роль {role.mention} будет выдаваться на **{level} уровне**."
        )

    @app_commands.command(name="levelrole_list",
                          description="Список ролей по уровням")
    @is_head_admin()
    async def levelrole_list(self, interaction: discord.Interaction):
        with DB() as db:
            rows = db.fetchall(
                "SELECT role_id, level_required FROM level_roles "
                "WHERE guild_id = %s ORDER BY level_required",
                (interaction.guild.id,),
            )
        if not rows:
            await interaction.response.send_message("Список пуст.",
                                                    ephemeral=True)
            return
        lines = [
            f"Уровень {r['level_required']} — "
            f"{interaction.guild.get_role(int(r['role_id'])).mention}"
            for r in rows if interaction.guild.get_role(int(r["role_id"]))
        ]
        await interaction.response.send_message(
            "🎭 **Роли по уровням:**\n" + "\n".join(lines), ephemeral=True
        )

    @app_commands.command(name="giverole", description="Выдать роль пользователю")
    @app_commands.describe(user="Кому", role="Какую роль")
    @is_head_admin()
    async def giverole(self, interaction: discord.Interaction,
                       user: discord.Member, role: discord.Role):
        if role >= interaction.user.top_role:
            await interaction.response.send_message(
                "❌ Нельзя выдать роль выше вашей.", ephemeral=True
            )
            return
        try:
            await user.add_roles(role, reason=f"Выдано {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message("❌ Нет прав.",
                                                    ephemeral=True)
            return
        await interaction.response.send_message(
            f"✅ {user.mention} получил роль {role.mention}"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Roles(bot))
