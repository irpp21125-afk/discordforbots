"""Ког «User Info»: /userinfo, /help, /serverinfo."""

import discord
from discord import app_commands
from discord.ext import commands

from db import DB

from utils import privilege_icon, get_guild_settings, is_staff


class UserInfo(commands.Cog):
    """Информация о пользователях и командах."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="userinfo",
                          description="Информация о пользователе")
    @app_commands.describe(user="Кого посмотреть (по умолчанию ваш)")
    async def userinfo(self, interaction: discord.Interaction,
                       user: discord.User = None):
        user = user or interaction.user

        with DB() as db:
            row = db.fetchone(
                "SELECT points, level, messages_count, voice_seconds, "
                "privilege, registration_date, last_activity "
                "FROM dc_users WHERE id = %s",
                (user.id,),
            )
        # Привилегия
        priv = row["privilege"] if row else "none"
        icon = privilege_icon(priv)

        # Роли
        roles = ", ".join(
            r.mention for r in user.roles[-5:]
        ) or "—"

        embed = discord.Embed(
            title=f"👤 {user.display_name}",
            color=user.accent_color or discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(name="ID", value=str(user.id), inline=True)
        embed.add_field(name="Привилегия", value=f"{icon} {priv}",
                        inline=True)
        embed.add_field(name="Дата вступления",
                        value=str(user.joined_at)[:16] if user.joined_at
                        else "—", inline=True)

        if row:
            embed.add_field(
                name="Уровень",
                value=f"{row['level']} ({row['points']} XP)",
                inline=True,
            )
            embed.add_field(name="Сообщений",
                            value=str(row["messages_count"]), inline=True)
            embed.add_field(name="Голос. секунд",
                            value=str(row["voice_seconds"]), inline=True)
            if row["last_activity"]:
                embed.add_field(
                    name="Последняя активность",
                    value=str(row["last_activity"])[:16], inline=True,
                )
        else:
            embed.add_field(name="Статистика", value="Нет данных",
                            inline=True)

        embed.add_field(name="Роли", value=roles, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help",
                          description="Список команд бота")
    @app_commands.describe(command="Название команды")
    async def help_cmd(self, interaction: discord.Interaction,
                       command: str = ""):
        commands_info = {
            "clear": "Удалить сообщения в канале",
            "slowmode": "Замедлить чат",
            "say": "Отправить сообщение от имени бота",
            "embed": "Отправить embed-сообщение",
            "kick": "Выгнать пользователя",
            "ban": "Забанить пользователя",
            "unban": "Снять бан по ID",
            "warn": "Выдать предупреждение",
            "mute": "Заблокировать ввод текста",
            "punishments": "История наказаний",
            "audit": "Журнал действий",
            "top": "Топ по активности",
            "balance": "Ваш баланс (alias: /rank)",
            "transfer": "Передать XP",
            "daily": "Ежедневная награда",
            "shop": "Посмотреть магазин",
            "buy": "Купить товар",
            "shop_add": "Добавить товар (админ)",
            "shop_remove": "Удалить товар (админ)",
            "addmoney": "Выдать XP (админ)",
            "removemoney": "Снять XP (админ)",
            "setmoney": "Установить XP (админ)",
            "premium": "Управление привилегиями",
            "addword": "Добавить слово в фильтр",
            "removeword": "Убрать слово из фильтра",
            "filterlist": "Список запрещённых слов",
            "filtertoggle": "Вкл/выкл фильтр",
            "antispam": "Настроить антиспам",
            "antiflood": "Настроить антифлуд",
            "blackjack": "Играть в 21",
            "dice": "Бросить кубик",
            "slots": "Слот-машина",
            "card": "Угадай карту",
            "gamestats": "Статистика игр",
            "monopoly": "Монополия",
            "monopoly_roll": "Бросить кубик в монополии",
            "logchannel": "Канал для логов",
            "logtoggle": "Вкл/выкл логи",
            "logstatus": "Статус логов",
            "welcomemsg": "Текст приветствия",
            "welcomechannel": "Канал приветствий",
            "welcometoggle": "Вкл/выкл приветствия",
            "welcomeautorole": "Авто-роль при входе",
            "ping": "Пинг бота",
            "reminder": "Напоминание",
            "suggest": "Отправить предложение",
            "avatar": "Аватар пользователя",
            "roll": "Бросить кубик 1-N",
            "config": "Настройки сервера",
            "config_set": "Изменить настройку",
            "server_banner": "Баннер сервера",
            "botinfo": "Информация о боте",
            "ticket": "Создать обращение",
            "alert_add": "Подписаться на слово",
            "alert_remove": "Убрать подписку",
            "autorole_set": "Назначить автороль",
            "levelrole": "Роль за уровень",
            "giverole": "Выдать роль",
        }

        if command:
            cmd = command.lower().strip()
            info = commands_info.get(cmd)
            if info:
                await interaction.response.send_message(
                    f"**/{cmd}** — {info}", ephemeral=True
                )
                return
            await interaction.response.send_message(
                f"❌ Команда «/{command}» не найдена в справке.",
                ephemeral=True,
            )
            return

        # Общий список
        sections = {
            "🛡️ Модерация": [
                "clear", "slowmode", "kick", "ban", "unban",
                "warn", "mute", "punishments", "audit",
            ],
            "💰 Экономика": [
                "top", "balance", "transfer", "daily", "shop", "buy",
                "premium",
            ],
            "🔒 Безопасность": [
                "addword", "removeword", "filterlist", "filtertoggle",
                "antispam", "antiflood",
            ],
            "🎮 Развлечения": [
                "blackjack", "dice", "slots", "card", "gamestats",
                "monopoly",
            ],
            "📋 Логи": ["logchannel", "logtoggle", "logstatus"],
            "👋 Приветствия": [
                "welcomemsg", "welcomechannel",
                "welcometoggle", "welcomeautorole",
            ],
            "🔧 Утилиты": [
                "ping", "reminder", "suggest", "avatar", "roll",
            ],
            "⚙️ Настройки": [
                "config", "server_banner", "botinfo",
            ],
        }
        lines = []
        for section, cmds in sections.items():
            lines.append(f"**{section}**\n" + "\n".join(f"/{c}" for c in cmds))
        embed = discord.Embed(
            title="📖 Справка /help",
            description="Используйте /help <команда> для деталей",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Команды", value="\n".join(lines),
                        inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo",
                          description="Информация о сервере")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(
            title=guild.name,
            description=guild.description or "—",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Владелец", value=str(guild.owner),
                        inline=True)
        embed.add_field(name="Участников", value=str(guild.member_count),
                        inline=True)
        embed.add_field(name="Каналов", value=str(len(guild.channels)),
                        inline=True)
        embed.add_field(name="Ролей", value=str(len(guild.roles) - 1),
                        inline=True)
        embed.add_field(name="Эмодзи", value=f"{guild.emoji_count}",
                        inline=True)
        embed.set_footer(text=f"ID: {guild.id}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(UserInfo(bot))
