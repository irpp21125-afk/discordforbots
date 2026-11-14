"""Ког «Экономика»: активность, уровни, рейтинг, баланс, магазин, привилегии."""

import random

import discord
from discord import app_commands
from discord.ext import commands

from db import DB

from utils import (
    audit, get_guild_settings, privilege_icon, is_head_admin,
)


class Economy(commands.Cog):
    """Экономика и вовлечённость."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Начисление XP за сообщения."""
        if message.author.bot or not message.guild:
            return
        settings = get_guild_settings(message.guild.id)
        if not settings.get("economy_enabled"):
            return
        await self._add_activity(message.guild.id, message.author.id, 5)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Учёт голосовой активности."""
        if member.bot or not member.guild:
            return
        if after.channel and not before.channel:
            await self._add_activity(member.guild.id, member.id, 10)

    async def _add_activity(self, guild_id: int, user_id: int, xp: int):
        with DB() as db:
            db.execute(
                "INSERT INTO dc_users(id, registration_date, last_activity)"
                " VALUES (%s, NOW(), NOW())"
                " ON DUPLICATE KEY UPDATE last_activity = NOW(),"
                " points = points + %s, messages_count = messages_count + 1",
                (user_id, xp),
            )
            row = db.fetchone(
                "SELECT points, level FROM dc_users WHERE id = %s", (user_id,)
            )
        if not row:
            return
        new_level = int(row["points"] // 100) + 1
        if new_level > int(row["level"]):
            with DB() as db:
                db.execute(
                    "UPDATE dc_users SET level = %s WHERE id = %s",
                    (new_level, user_id),
                )
            await self._announce_levelup(guild_id, user_id, new_level)
            await self._apply_level_roles(guild_id, user_id, new_level)

    async def _announce_levelup(self, guild_id, user_id, level):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        settings = get_guild_settings(guild_id)
        chan_id = settings.get("levelup_channel")
        member = guild.get_member(int(user_id))
        if chan_id and member:
            channel = guild.get_channel(int(chan_id))
            if channel:
                await channel.send(
                    f"🎉 **{member.mention}** достиг **{level} уровня!**"
                )

    async def _apply_level_roles(self, guild_id, user_id, level):
        """Выдача ролей по уровню (таблица level_roles)."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        member = guild.get_member(int(user_id))
        if not member:
            return
        with DB() as db:
            rows = db.fetchall(
                "SELECT role_id FROM level_roles WHERE guild_id = %s "
                "AND level_required <= %s",
                (guild_id, level),
            )
        for row in rows:
            role = guild.get_role(int(row["role_id"]))
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Level role")
                except Exception:
                    pass

    # ---------- команды ----------

    @app_commands.command(name="rank", description="Ваш профиль и уровень")
    @app_commands.describe(user="Кого посмотреть")
    async def rank(self, interaction: discord.Interaction,
                   user: discord.User = None):
        user = user or interaction.user
        with DB() as db:
            row = db.fetchone(
                "SELECT points, level, messages_count FROM dc_users "
                "WHERE id = %s", (user.id,)
            )
        if not row:
            await interaction.response.send_message(
                f"{user.mention} ещё не накопил статистику.", ephemeral=True
            )
            return
        points = int(row["points"])
        level = int(row["level"])
        progress = points % 100
        embed = discord.Embed(title=f"📊 {user.display_name}",
                              color=discord.Color.green())
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Уровень", value=f"{level}")
        embed.add_field(name="Опыт", value=f"{points} XP")
        embed.add_field(name="Сообщений", value=row["messages_count"])
        embed.add_field(name="До следующего", value=f"{100 - progress} XP")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Топ по активности")
    @app_commands.describe(limit="Сколько мест показать")
    async def leaderboard(self, interaction: discord.Interaction,
                          limit: int = 10):
        with DB() as db:
            rows = db.fetchall(
                "SELECT id, points, level FROM dc_users "
                "WHERE guild_id = %s OR guild_id IS NULL "
                "ORDER BY points DESC LIMIT %s",
                (interaction.guild.id, min(limit, 20)),
            )
        if not rows:
            await interaction.response.send_message(
                "Статистика пуста.", ephemeral=True
            )
            return
        lines = []
        for i, r in enumerate(rows, 1):
            member = interaction.guild.get_member(int(r["id"]))
            name = member.display_name if member else f"ID {r['id']}"
            lines.append(f"**{i}.** {name} — {r['points']} XP "
                         f"(ур. {r['level']})")
        embed = discord.Embed(title="🏆 Рейтинг сервера",
                              description="\n".join(lines),
                              color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Забрать ежедневную награду")
    async def daily(self, interaction: discord.Interaction):
        with DB() as db:
            last = db.fetchone(
                "SELECT created_at FROM economy_log WHERE guild_id = %s "
                "AND user_id = %s AND reason = 'daily' "
                "ORDER BY created_at DESC LIMIT 1",
                (interaction.guild.id, interaction.user.id),
            )
        if last:
            from datetime import datetime, timedelta
            if datetime.now() - last["created_at"] < timedelta(hours=20):
                await interaction.response.send_message(
                    "⏳ Награда уже получена. Возвращайтесь завтра!",
                    ephemeral=True,
                )
                return
        amount = random.randint(50, 150)
        with DB() as db:
            db.execute(
                "INSERT INTO economy_log(guild_id, user_id, amount, reason,"
                " created_at) VALUES (%s, %s, %s, 'daily', NOW())",
                (interaction.guild.id, interaction.user.id, amount),
            )
            db.execute(
                "UPDATE dc_users SET points = points + %s WHERE id = %s",
                (amount, interaction.user.id),
            )
        audit(interaction.guild.id, interaction.user.id, "daily_reward")
        await interaction.response.send_message(
            f"💰 Вы получили **{amount} XP** ежедневную награду!"
        )

    @app_commands.command(name="transfer", description="Передать опыт другу")
    @app_commands.describe(user="Кому", amount="Сколько XP")
    async def transfer(self, interaction: discord.Interaction,
                       user: discord.User, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Сумма должна быть > 0",
                                                    ephemeral=True)
            return
        with DB() as db:
            sender = db.fetchone(
                "SELECT points FROM dc_users WHERE id = %s",
                (interaction.user.id,),
            )
        if not sender or int(sender["points"]) < amount:
            await interaction.response.send_message("❌ Недостаточно XP",
                                                    ephemeral=True)
            return
        # налог на перевод
        sender_priv = db.fetchone(
            "SELECT privilege FROM dc_users WHERE id = %s",
            (interaction.user.id,),
        )
        receiver_priv = db.fetchone(
            "SELECT privilege FROM dc_users WHERE id = %s",
            (user.id,),
        )
        sender_rank = _priv_rank(
            sender_priv["privilege"] if sender_priv else "none"
        )
        receiver_rank = _priv_rank(
            receiver_priv["privilege"] if receiver_priv else "none"
        )
        tax = 0
        if receiver_rank > sender_rank:
            tax = int(amount * 0.1)
            amount_after_tax = amount - tax
        else:
            amount_after_tax = amount

        with DB() as db:
            db.execute(
                "UPDATE dc_users SET points = points - %s WHERE id = %s",
                (amount, interaction.user.id),
            )
            db.execute(
                "INSERT INTO dc_users(id, points, registration_date,"
                " last_activity) VALUES (%s, %s, NOW(), NOW())"
                " ON DUPLICATE KEY UPDATE points = points + %s",
                (user.id, amount_after_tax, amount_after_tax),
            )
            db.execute(
                "INSERT INTO economy_log(guild_id, user_id, amount, reason,"
                " created_at) VALUES (%s, %s, %s, %s, NOW())",
                (interaction.guild.id, user.id, amount_after_tax,
                 f"transfer from {interaction.user.id}"
                 + (f" (tax {tax})" if tax else "")),
            )
        tax_msg = f"\n🏦 Налог: **{tax} XP**" if tax else ""
        await interaction.response.send_message(
            f"✅ Передали **{amount_after_tax} XP** пользователю {user.mention}"
            + tax_msg
        )

    # ---------- МАГАЗИН ----------

    @app_commands.command(name="shop", description="Посмотреть магазин")
    async def shop(self, interaction: discord.Interaction):
        with DB() as db:
            items = db.fetchall(
                "SELECT * FROM shop_items WHERE guild_id = %s "
                "ORDER BY name",
                (interaction.guild.id,),
            )
        if not items:
            await interaction.response.send_message("🏪 Магазин пуст.",
                                                    ephemeral=True)
            return
        lines = [f"**{i['name']}** — {i['price']} XP"
                 + (f" — {i['description']}" if i['description'] else "")
                 for i in items]
        embed = discord.Embed(title="🏪 Магазин",
                              description="\n".join(lines),
                              color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Купить товар в магазине")
    @app_commands.describe(item="Название товара")
    async def buy(self, interaction: discord.Interaction, item: str):
        with DB() as db:
            row = db.fetchone(
                "SELECT * FROM shop_items WHERE guild_id = %s AND name = %s",
                (interaction.guild.id, item.lower().strip()),
            )
        if not row:
            await interaction.response.send_message(
                f"❌ Товар «{item}» не найден.", ephemeral=True
            )
            return
        if int(row["price"]) <= 0:
            await interaction.response.send_message(
                "Этот товар бесплатный!", ephemeral=True
            )
            return
        with DB() as db:
            bal = db.fetchone(
                "SELECT points FROM dc_users WHERE id = %s",
                (interaction.user.id,),
            )
        if not bal or int(bal["points"]) < int(row["price"]):
            need = row["price"]
            have = bal["points"] if bal else 0
            await interaction.response.send_message(
                f"❌ Недостаточно XP. Нужно {need}, "
                f"у вас {have}.",
                ephemeral=True,
            )
            return
        with DB() as db:
            db.execute(
                "UPDATE dc_users SET points = points - %s WHERE id = %s",
                (int(row["price"]), interaction.user.id),
            )
            db.execute(
                "INSERT INTO inventory(guild_id, user_id, item_name) "
                "VALUES (%s, %s, %s)",
                (interaction.guild.id, interaction.user.id, row["name"]),
            )
            db.execute(
                "INSERT INTO economy_log(guild_id, user_id, amount, reason,"
                " created_at) VALUES (%s, %s, %s, %s, NOW())",
                (interaction.guild.id, interaction.user.id,
                 int(row["price"]), f"buy: {row['name']}"),
            )
        await interaction.response.send_message(
            f"🎉 Вы купили **{row['name']}** за {row['price']} XP!"
        )

    @app_commands.command(name="inventory",
                          description="Посмотреть свой инвентарь")
    async def inventory(self, interaction: discord.Interaction):
        with DB() as db:
            items = db.fetchall(
                "SELECT item_name, purchased_at FROM inventory "
                "WHERE guild_id = %s AND user_id = %s ORDER BY purchased_at DESC",
                (interaction.guild.id, interaction.user.id),
            )
        if not items:
            await interaction.response.send_message("🎒 Инвентарь пуст.",
                                                    ephemeral=True)
            return
        lines = [f"**{i['item_name']}** — {str(i['purchased_at'])[:16]}"
                 for i in items]
        embed = discord.Embed(title="🎒 Ваш инвентарь",
                              description="\n".join(lines),
                              color=discord.Color.purple())
        await interaction.response.send_message(embed=embed)

    # ---------- ТОП С ПРИВИЛЕГИЯМИ ----------

    @app_commands.command(name="top", description="Топ с привилегиями")
    @app_commands.describe(limit="Сколько мест показать")
    async def top(self, interaction: discord.Interaction,
                  limit: int = 10):
        with DB() as db:
            rows = db.fetchall(
                "SELECT id, points, level, privilege FROM dc_users "
                "WHERE guild_id = %s OR guild_id IS NULL "
                "ORDER BY points DESC LIMIT %s",
                (interaction.guild.id, min(limit, 20)),
            )
        if not rows:
            await interaction.response.send_message(
                "Статистика пуста.", ephemeral=True
            )
            return
        lines = []
        for i, r in enumerate(rows, 1):
            member = interaction.guild.get_member(int(r["id"]))
            name = member.display_name if member else f"ID {r['id']}"
            icon = privilege_icon(r.get("privilege", "none"))
            lines.append(
                f"**{i}.** {icon} {name} — {r['points']} XP (ур. {r['level']})"
            )
        embed = discord.Embed(
            title="🏆 Рейтинг сервера",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)

    # ---------- АДМИН-КОМАНДЫ ----------

    @app_commands.command(name="addmoney",
                          description="Выдать XP пользователю (админ)")
    @app_commands.describe(user="Кому", amount="Сколько XP")
    @is_head_admin()
    async def addmoney(self, interaction: discord.Interaction,
                       user: discord.User, amount: int):
        if amount <= 0:
            await interaction.response.send_message(
                "Сумма должна быть > 0", ephemeral=True)
            return
        with DB() as db:
            db.execute(
                "INSERT INTO dc_users(id, points, registration_date,"
                " last_activity) VALUES (%s, %s, NOW(), NOW())"
                " ON DUPLICATE KEY UPDATE points = points + %s",
                (user.id, amount, amount),
            )
        audit(interaction.guild.id, interaction.user.id, f"addmoney:{amount}")
        await interaction.response.send_message(
            f"✅ Выдано **{amount} XP** пользователю {user.mention}"
        )

    @app_commands.command(name="removemoney",
                          description="Снять XP у пользователя (админ)")
    @app_commands.describe(user="У кого", amount="Сколько XP")
    @is_head_admin()
    async def removemoney(self, interaction: discord.Interaction,
                          user: discord.User, amount: int):
        if amount <= 0:
            await interaction.response.send_message(
                "Сумма должна быть > 0", ephemeral=True)
            return
        with DB() as db:
            db.execute(
                "UPDATE dc_users SET points = GREATEST(0, points - %s) "
                "WHERE id = %s",
                (amount, user.id),
            )
        audit(interaction.guild.id, interaction.user.id,
              f"removemoney:{amount}")
        await interaction.response.send_message(
            f"✅ Снято **{amount} XP** у {user.mention}"
        )

    @app_commands.command(name="setmoney",
                          description="Установить XP пользователю (админ)")
    @app_commands.describe(user="Кому", amount="Сколько XP")
    @is_head_admin()
    async def setmoney(self, interaction: discord.Interaction,
                       user: discord.User, amount: int):
        if amount < 0:
            await interaction.response.send_message(
                "Сумма не может быть отрицательной", ephemeral=True)
            return
        with DB() as db:
            db.execute(
                "INSERT INTO dc_users(id, points, registration_date,"
                " last_activity) VALUES (%s, %s, NOW(), NOW())"
                " ON DUPLICATE KEY UPDATE points = VALUES(points)",
                (user.id, amount),
            )
        audit(interaction.guild.id, interaction.user.id, f"setmoney:{amount}")
        await interaction.response.send_message(
            f"✅ У {user.mention} теперь **{amount} XP**"
        )

    # ---------- МАГАЗИН-АДМИН ----------

    @app_commands.command(name="shop_add",
                          description="Добавить товар в магазин (админ)")
    @app_commands.describe(
        item="Название",
        price="Цена в XP",
        description="Описание (необязательно)",
    )
    @is_head_admin()
    async def shop_add(self, interaction: discord.Interaction,
                       item: str, price: int, description: str = ""):
        with DB() as db:
            db.execute(
                "INSERT INTO shop_items(guild_id, name, price, description) "
                "VALUES (%s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE price = VALUES(price), "
                "description = VALUES(description)",
                (interaction.guild.id, item.lower().strip(), price, description),
            )
        await interaction.response.send_message(
            f"✅ Товар **{item}** за {price} XP добавлен в магазин."
        )

    @app_commands.command(name="shop_remove",
                          description="Удалить товар из магазина (админ)")
    @app_commands.describe(item="Название")
    @is_head_admin()
    async def shop_remove(self, interaction: discord.Interaction,
                          item: str):
        with DB() as db:
            cur = db.execute(
                "DELETE FROM shop_items WHERE guild_id = %s AND name = %s",
                (interaction.guild.id, item.lower().strip()),
            )
        if cur.rowcount:
            await interaction.response.send_message(
                f"✅ Товар «{item}» удалён из магазина."
            )
        else:
            await interaction.response.send_message(
                "❌ Товар не найден.", ephemeral=True
            )

    # ---------- ПРИВИЛЕГИИ ----------

    @app_commands.command(name="premium",
                          description="Посмотреть / изменить привилегию")
    @app_commands.describe(
        action="view|set",
        privilege="starvision|viaglobal|gectoring",
    )
    @is_head_admin()
    async def premium(self, interaction: discord.Interaction,
                      action: str = "view",
                      privilege: str = "none"):
        if action == "view":
            with DB() as db:
                row = db.fetchone(
                    "SELECT privilege FROM dc_users WHERE id = %s",
                    (interaction.user.id,),
                )
            priv = row["privilege"] if row else "none"
            icon = privilege_icon(priv)
            await interaction.response.send_message(
                f"👑 Ваша привилегия: **{icon} {priv}**",
                ephemeral=True,
            )
        else:
            valid = {"starvision", "viaglobal", "gectoring", "none"}
            if privilege not in valid:
                await interaction.response.send_message(
                    "❌ Доступные: starvision, viaglobal, gectoring, none",
                    ephemeral=True,
                )
                return
            with DB() as db:
                db.execute(
                    "INSERT INTO dc_users(id, privilege) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE privilege = VALUES(privilege)",
                    (interaction.user.id, privilege),
                )
            icon = privilege_icon(privilege)
            audit(interaction.guild.id, interaction.user.id,
                  f"privilege:{privilege}")
            await interaction.response.send_message(
                f"✅ Ваша привилегия: **{icon} {privilege}**"
            )


def _priv_rank(priv: str) -> int:
    return {"gectoring": 3, "viaglobal": 2, "starvision": 1, "none": 0}.get(priv, 0)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
