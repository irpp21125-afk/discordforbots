"""Ког «Развлечения»: blackjack, dice, slots, card, monopoly."""

import random
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from db import DB

from utils import is_staff, audit

# ---------- простейшая память для игр ----------
_games: dict = {}  # guild_id -> {user_id: state}


def _get_game(guild_id: int, user_id: int) -> Optional[dict]:
    g = _games.get(guild_id)
    if g:
        return g.get(user_id)
    return None


def _set_game(guild_id: int, user_id: int, state: dict):
    _games.setdefault(guild_id, {})[user_id] = state


def _del_game(guild_id: int, user_id: int):
    g = _games.get(guild_id)
    if g:
        g.pop(user_id, None)


def _record_game(guild_id: int, user_id: int, game: str, result: str):
    with DB() as db:
        db.execute(
            "INSERT INTO game_stats(guild_id, user_id, game, "
            "wins, losses, draws, last_played) "
            "VALUES (%s, %s, %s, "
            "CASE WHEN %s='win' THEN wins+1 WHEN %s='lose' THEN losses+1 "
            "ELSE draws END, "
            "CASE WHEN %s='lose' THEN losses+1 WHEN %s='win' THEN wins+1 "
            "ELSE draws END, "
            "CASE WHEN %s='draw' THEN draws+1 ELSE draws END, NOW()) "
            "ON DUPLICATE KEY UPDATE last_played = NOW(), "
            "wins = CASE WHEN %s='win' THEN wins+1 ELSE wins END, "
            "losses = CASE WHEN %s='lose' THEN losses+1 ELSE losses END, "
            "draws = CASE WHEN %s='draw' THEN draws+1 ELSE draws END",
            (guild_id, user_id, game, result, result,
             result, result, result, result, result, result),
        )


class Games(commands.Cog):
    """Развлечения: карточные, кубики, слоты, monopoly."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ==================== BLACKJACK ====================

    @app_commands.command(name="blackjack",
                          description="Играть в 21 (blackjack)")
    @app_commands.describe(wager="Ставка XP")
    async def blackjack(self, interaction: discord.Interaction, wager: int):
        if wager <= 0:
            await interaction.response.send_message(
                "❌ Ставка должна быть > 0", ephemeral=True)
            return
        player = interaction.user
        with DB() as db:
            bal = db.fetchone(
                "SELECT points FROM dc_users WHERE id = %s", (player.id,))
        if not bal or int(bal["points"]) < wager:
            await interaction.response.send_message(
                f"❌ Недостаточно XP. Нужно {wager}.", ephemeral=True)
            return

        deck = self._make_deck()
        player_hand = [deck.pop(0), deck.pop(0)]
        dealer_hand = [deck.pop(0), deck.pop(0)]

        def _total(hand: list) -> int:
            t = sum(self._card_val(c) for c in hand)
            aces = sum(1 for c in hand if c[1] == "A")
            while t <= 11 and aces:
                t += 10
                aces -= 1
            return t

        def _render(hand: list, hide_first: bool = False) -> str:
            if hide_first:
                return f"🂠 + [?]"
            return " + ".join(f"[{c[0]}{c[1]}]" for c in hand)

        embed = discord.Embed(
            title="🃏 Blackjack",
            description=(
                f"Ставка: **{wager} XP**\n\n"
                f"Дилер: {_render(dealer_hand, hide_first=True)}\n"
                f"Вы: {_render(player_hand)} ({_total(player_hand)})"
            ),
            color=discord.Color.green(),
        )

        msg = await interaction.response.send_message(embed=embed)

        # Игрок ходит
        while _total(player_hand) < 17:
            await discord.Embed(
                title="🃏 Blackjack",
                description=(
                    f"Ставка: **{wager} XP**\n\n"
                    f"Дилер: {_render(dealer_hand, hide_first=True)}\n"
                    f"Вы: {_render(player_hand)} ({_total(player_hand)})"
                ),
                color=discord.Color.green(),
            )
            if _total(player_hand) >= 21:
                break
            player_hand.append(deck.pop(0))

        # Дилер ходит
        while _total(dealer_hand) < 17:
            dealer_hand.append(deck.pop(0))

        p_total = _total(player_hand)
        d_total = _total(dealer_hand)

        if p_total > 21:
            result = "lose"
            status = "Перебор! Вы проиграли."
        elif d_total > 21 or p_total > d_total:
            result = "win"
            status = f"Вы выиграли! ({p_total} vs {d_total})"
        elif p_total < d_total:
            result = "lose"
            status = f"Вы проиграли ({p_total} vs {d_total})."
        else:
            result = "draw"
            status = f"Ничья! ({p_total})"

        if result == "win":
            with DB() as db:
                db.execute(
                    "UPDATE dc_users SET points = points + %s WHERE id = %s",
                    (wager, player.id),
                )
        elif result == "lose":
            with DB() as db:
                db.execute(
                    "UPDATE dc_users SET points = points - %s WHERE id = %s",
                    (wager, player.id),
                )

        embed = discord.Embed(
            title="🃏 Blackjack — Итог",
            description=(
                f"Ставка: **{wager} XP**\n\n"
                f"Дилер: {_render(dealer_hand)} ({d_total})\n"
                f"Вы: {_render(player_hand)} ({p_total})\n\n"
                f"**{status}**"
            ),
            color=discord.Color.green() if result == "win" else
            discord.Color.red() if result == "lose" else
            discord.Color.greyple(),
        )
        await msg.edit(embed=embed)

        _record_game(interaction.guild.id, player.id, "blackjack", result)
        audit(interaction.guild.id, player.id,
              f"blackjack:{result}:{wager}")
        _del_game(interaction.guild.id, player.id)

    def _make_deck(self) -> list:
        suits = ["♠", "♥", "♦", "♣"]
        ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10",
                 "J", "Q", "K"]
        deck = [(s, r) for s in suits for r in ranks]
        random.shuffle(deck)
        return deck

    @staticmethod
    def _card_val(card: tuple) -> int:
        r = card[1]
        if r in ("J", "Q", "K"):
            return 10
        if r == "A":
            return 11
        return int(r)

    # ==================== DICE ====================

    @app_commands.command(name="dice",
                          description="Бросить кубик (1-6)")
    @app_commands.describe(opponent="Соперник для PvP")
    async def dice(self, interaction: discord.Interaction,
                   opponent: discord.User = None):
        d1 = random.randint(1, 6)
        if opponent:
            d2 = random.randint(1, 6)
            if d1 > d2:
                res = "win"
                status = f"Выпало {d1} vs {d2} — вы выиграли!"
            elif d1 < d2:
                res = "lose"
                status = f"Выпало {d1} vs {d2} — вы проиграли."
            else:
                res = "draw"
                status = f"Выпало {d1} vs {d2} — ничья!"
            _record_game(interaction.guild.id, interaction.user.id,
                         "dice", res)
        else:
            status = f"Выпало: **{d1}**"
            res = "win" if d1 >= 4 else "lose"
        embed = discord.Embed(
            title="🎲 Кубик",
            description=status,
            color=discord.Color.blue(),
        )
        embed.set_footer(text="Бросок генерируется случайно")
        await interaction.response.send_message(embed=embed)
        audit(interaction.guild.id, interaction.user.id,
              f"dice:{d1}:{res}")

    # ==================== SLOTS ====================

    @app_commands.command(name="slots",
                          description="Слот-машина! Ставка XP")
    @app_commands.describe(wager="Ставка XP (10, 50, 100, 500)")
    async def slots(self, interaction: discord.Interaction, wager: int):
        if wager not in (10, 50, 100, 500):
            await interaction.response.send_message(
                "❌ Доступные ставки: 10, 50, 100, 500 XP", ephemeral=True)
            return
        player = interaction.user
        with DB() as db:
            bal = db.fetchone(
                "SELECT points FROM dc_users WHERE id = %s", (player.id,))
        if not bal or int(bal["points"]) < wager:
            await interaction.response.send_message(
                f"❌ Недостаточно XP. Нужно {wager}.", ephemeral=True)
            return

        symbols = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣"]
        reels = [random.choice(symbols) for _ in range(3)]
        result_str = " | ".join(reels)

        if reels[0] == reels[1] == reels[2]:
            if reels[0] == "7️⃣":
                mult = 10
            elif reels[0] == "💎":
                mult = 7
            else:
                mult = 5
            win = wager * mult
            status = f"🎉 ДЖЕКПОТ! Выигрыш: **{win} XP**!"
            res = "win"
            with DB() as db:
                db.execute(
                    "UPDATE dc_users SET points = points + %s WHERE id = %s",
                    (win, player.id),
                )
        elif reels[0] == reels[1] or reels[1] == reels[2]:
            mult = 2
            win = wager * mult
            status = f"✨ Пара! Выигрыш: **{win} XP**"
            res = "win"
            with DB() as db:
                db.execute(
                    "UPDATE dc_users SET points = points + %s WHERE id = %s",
                    (win, player.id),
                )
        else:
            status = f"😔 Не повезло. Потеряно {wager} XP"
            res = "lose"
            with DB() as db:
                db.execute(
                    "UPDATE dc_users SET points = points - %s WHERE id = %s",
                    (wager, player.id),
                )

        embed = discord.Embed(
            title="🎰 Slots",
            description=f"Ставка: {wager} XP\n\n"
                        f"**{result_str}**\n\n{status}",
            color=discord.Color.gold() if res == "win" else
            discord.Color.red(),
        )
        embed.set_thumbnail(url=player.display_avatar.url)
        await interaction.response.send_message(embed=embed)

        _record_game(interaction.guild.id, player.id, "slots", res)
        audit(interaction.guild.id, player.id, f"slots:{res}:{wager}")

    # ==================== CARD (Угадай карту) ====================

    @app_commands.command(name="card",
                          description="Угадай карту из колоды")
    async def card(self, interaction: discord.Interaction):
        suits = ["♠", "♥", "♦", "♣"]
        ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10",
                 "J", "Q", "K"]
        deck = [(s, r) for s in suits for r in ranks]
        random.shuffle(deck)

        target = deck[0]
        choices = [target]
        while len(choices) < 5:
            pick = random.choice(deck)
            if pick not in choices:
                choices.append(pick)
        random.shuffle(choices)

        correct = f"{target[0]}{target[1]}"
        choices_str = ", ".join(f"[{c[0]}{c[1]}]" for c in choices)

        embed = discord.Embed(
            title="🂡 Угадай карту",
            description=(
                f"Угадай одну из: {choices_str}\n\n"
                f"Ваш ответ: угадайте номер от 1 до 5\n"
                f"(Это мгновенная игра — правильный ответ: "
                f"**{correct}**)"
            ),
            color=discord.Color.purple(),
        )
        await interaction.response.send_message(embed=embed)
        # Угадано — нет механизма подтверждения, считаем win/lose
        # для статистики
        is_win = random.random() < 0.2  # 20%
        _record_game(interaction.guild.id, interaction.user.id,
                     "card", "win" if is_win else "lose")

    # ==================== GAME STATS ====================

    @app_commands.command(name="gamestats",
                          description="Статистика ваших игр")
    @app_commands.describe(game="blackjack|slots|dice|card")
    async def gamestats(self, interaction: discord.Interaction,
                        game: str = ""):
        games_list = ["blackjack", "slots", "dice", "card"]
        if game and game not in games_list:
            await interaction.response.send_message(
                f"❌ Доступно: {', '.join(games_list)}", ephemeral=True)
            return

        with DB() as db:
            if game:
                rows = db.fetchall(
                    "SELECT * FROM game_stats WHERE guild_id = %s "
                    "AND user_id = %s AND game = %s",
                    (interaction.guild.id, interaction.user.id, game),
                )
            else:
                rows = db.fetchall(
                    "SELECT * FROM game_stats WHERE guild_id = %s "
                    "AND user_id = %s ORDER BY wins DESC LIMIT 5",
                    (interaction.guild.id, interaction.user.id),
                )
        if not rows:
            await interaction.response.send_message(
                "📊 Статистика пуста. Попробуйте поиграть!", ephemeral=True)
            return
        lines = []
        for r in rows:
            g = r["game"]
            w, l, d = r["wins"], r["losses"], r["draws"]
            total = w + l + d
            winrate = f"{w / total:.0%}" if total > 0 else "—"
            lines.append(
                f"**{g}**: {w}W / {l}L / {d}D "
                f"(всего {total}, винрейт {winrate})"
            )
        embed = discord.Embed(
            title=f"📊 {interaction.user.display_name}",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== URBAN PLAY / JOIN ====================

    @app_commands.command(name="urbanjoin",
                          description="Присоединиться к городской игре")
    @app_commands.describe(
        game="Название: urban или monopoly",
    )
    async def urbanjoin(self, interaction: discord.Interaction, game: str):
        await interaction.response.send_message(
            f"🏙️ Вы присоединились к игре **{game}**!\n"
            f"Ожидайте начала...", ephemeral=True
        )
        audit(interaction.guild.id, interaction.user.id, f"urbanjoin:{game}")

    @app_commands.command(name="urbanplay",
                          description="Начать быструю городскую игру")
    async def urbanplay(self, interaction: discord.Interaction):
        cards = [
            "🏠 Построй дом — получи 20 XP",
            "🏭 Завод — получи 50 XP",
            "✈️ Самолёт — потеряй 30 XP",
            "🎲 Бонус — получи 10 XP",
            "🏦 Банк — получи 5 XP",
        ]
        card = random.choice(cards)
        xp = int(card.split("—")[1].strip())
        player = interaction.user
        with DB() as db:
            db.execute(
                "UPDATE dc_users SET points = points + %s WHERE id = %s",
                (xp, player.id),
            )
        embed = discord.Embed(
            title="🏙️ Городская игра",
            description=card,
            color=discord.Color.green() if xp > 0 else discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed)
        audit(interaction.guild.id, player.id, f"urbanplay:{xp}")

    # ==================== MONOPOLY (упрощённая) ====================

    @app_commands.command(name="monopoly",
                          description="Управление монополией")
    @app_commands.describe(command="roll|info|buy")
    async def monopoly(self, interaction: discord.Interaction,
                       command: str):
        if command == "roll":
            await self._monopoly_roll(interaction)
            return
        elif command == "info":
            state = _get_game(interaction.guild.id, interaction.user.id)
            if not state:
                await interaction.response.send_message(
                    "❌ Вы не начали партию. Используйте /monopoly_roll.",
                    ephemeral=True,
                )
                return
            embed = discord.Embed(
                title="🎩 Монополия",
                description=(
                    f"Игрок: {interaction.user.display_name}\n"
                    f"Деньги: **{state.get('money', 1500)} XP**\n"
                    f"Позиция: **{state.get('pos', 0)}**\n"
                    f"Недвижимость: {len(state.get('props', []))} шт."
                ),
                color=discord.Color.blurple(),
            )
            await interaction.response.send_message(embed=embed,
                                                    ephemeral=True)
            return
        elif command == "buy":
            state = _get_game(interaction.guild.id, interaction.user.id)
            if not state:
                await interaction.response.send_message(
                    "❌ Начните партию: /monopoly_roll", ephemeral=True)
                return
            props = state.get("props", [])
            if len(props) >= 5:
                await interaction.response.send_message(
                    "❌ Максимум 5 объектов. Используйте /monopoly_roll "
                    "для продажи.", ephemeral=True)
                return
            cost = random.randint(50, 200)
            pos = state.get("pos", 0)
            pos += 1
            state["pos"] = pos % 40
            if state["money"] >= cost:
                state["money"] -= cost
                props.append(f"Объект #{len(props)+1} ({cost} XP)")
                state["props"] = props
                embed = discord.Embed(
                    title="🏠 Куплена недвижимость",
                    description=f"За {cost} XP. Всего: {len(props)}",
                    color=discord.Color.green(),
                )
            else:
                embed = discord.Embed(
                    title="💸 Недостаточно средств",
                    description=f"Нужно {cost}, у вас {state['money']}",
                    color=discord.Color.red(),
                )
            _set_game(interaction.guild.id, interaction.user.id, state)
            await interaction.response.send_message(embed=embed,
                                                    ephemeral=True)
            return
        else:
            await interaction.response.send_message(
                "❌ Команды: /monopoly_roll, /monopoly info",
                ephemeral=True,
            )

    @app_commands.command(name="monopoly_roll",
                          description="Бросить кубик в монополии")
    async def monopoly_roll(self, interaction: discord.Interaction):
        await self._monopoly_roll(interaction)

    async def _monopoly_roll(self, interaction: discord.Interaction):
        player = interaction.user
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        total = d1 + d2

        # Начало игры или обновление
        state = _get_game(interaction.guild.id, player.id)
        if not state:
            state = {
                "money": 1500,
                "pos": 0,
                "props": [],
                "jail": False,
            }
        state["pos"] = (state["pos"] + total) % 40

        # Бонус за круг
        old_pos = (state["pos"] - total) % 40
        if state["pos"] <= old_pos and state["pos"] != old_pos:
            state["money"] += 200

        # Случайные события
        events = [
            (50, "💰 Найдели деньги! +50 XP"),
            (30, "🚗 Штраф за парковку —30 XP"),
            (20, "🎁 Бонус от банка — +20 XP"),
        ]
        for chance, event_text in events:
            if random.randint(1, 100) <= chance:
                amount = int(event_text.split("—")[0].strip().replace(
                    "+", "").replace("XP", "").strip())
                state["money"] += amount
                state["last_event"] = event_text
                break

        _set_game(interaction.guild.id, player.id, state)

        embed = discord.Embed(
            title="🎩 Монополия",
            description=(
                f"🎲 {d1} + {d2} = **{total}**\n"
                f"Позиция: **{state['pos']}**\n"
                f"Деньги: **{state['money']} XP**\n"
                f"Недвижимость: {len(state.get('props', []))} шт."
                + (f"\n\n{state.get('last_event', '')}"
                   if 'last_event' in state else "")
            ),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        audit(interaction.guild.id, player.id,
              f"monopoly_roll:{d1}+{d2}:{total}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Games(bot))
