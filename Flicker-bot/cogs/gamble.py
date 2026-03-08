import discord
import random
import asyncio
import itertools
from discord.ext import commands
from database import get_chips, update_chips, increment_stat, record_user_game, get_user_game_stats, get_server_settings

# ── Animated emojis ───────────────────────────────────────────────
ANIM_COIN = "<a:coinflip:1474782979095007404>"
ANIM_SLOT = "<a:slot_gif:1474783068119240776>"

STATIC_HEADS = "🪙"
STATIC_TAILS = "🪙"

# ── Card helpers ─────────────────────────────────────────────────────────────
SUITS = ["✨", "🌙", "⭐", "💫"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

# ── Roulette helpers ──────────────────────────────────────────────────────────
ROULETTE_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
ROULETTE_BLACK = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
ROULETTE_SPIN_FRAMES = ["🌀", "💫", "⭐", "🌟", "✨"]

# ── RPS helpers ───────────────────────────────────────────────────────────────
RPS_WINS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
RPS_ICONS = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
DICE_FACES = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]


def new_deck():
    return [f"{r}{s}" for r, s in itertools.product(RANKS, SUITS)]


def card_value(card: str) -> int:
    rank = card[:-1]
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)


def hand_value(hand: list) -> int:
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c.startswith("A"))
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def fmt_hand(hand: list) -> str:
    return "  ".join(hand)


# ── Blackjack View ────────────────────────────────────────────────────────────
class BlackjackView(discord.ui.View):
    def __init__(
        self,
        cog,
        ctx,
        bet: int,
        deck: list,
        player_hand: list,
        dealer_hand: list,
        track_stats: bool = True,
        win_multiplier: float = 2.0,
        to: dict = None,
    ):
        super().__init__(timeout=30)
        self.cog = cog
        self.ctx = ctx
        self.guild_id = ctx.guild.id
        self.bet = bet
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.track_stats = track_stats
        self.win_multiplier = win_multiplier
        self.to = to or {}
        self.message = None

    def build_embed(self, reveal_dealer=False) -> discord.Embed:
        pval = hand_value(self.player_hand)
        if reveal_dealer:
            dealer_display = (
                f"{fmt_hand(self.dealer_hand)} ({hand_value(self.dealer_hand)})"
            )
        else:
            dealer_display = f"{self.dealer_hand[0]}  🂠"
        embed = discord.Embed(title=self.to.get("bj_title", "🃏 Blackjack"), color=discord.Color.dark_gold())
        embed.add_field(name="Dealer", value=dealer_display, inline=False)
        embed.add_field(
            name=f"{self.ctx.author.display_name} ({pval})",
            value=fmt_hand(self.player_hand),
            inline=False,
        )
        embed.set_footer(text=f"Bet: {self.bet:,} Chips")
        return embed

    async def resolve(self, interaction: discord.Interaction):
        for child in self.children:
            child.disabled = True

        while hand_value(self.dealer_hand) < 17:
            # VIP Luck
            if (
                interaction.user.id == self.cog.boss_id
                and hand_value(self.dealer_hand) >= 15
                and random.random() < 0.50
            ):
                break
            # 20% House Edge: 20% of the time, the dealer will perfectly snipe a winning card
            elif (
                interaction.user.id != self.cog.boss_id
                and random.random() < 0.20
                and hand_value(self.player_hand) <= 21
            ):
                needed = 21 - hand_value(self.dealer_hand)
                cheat_cards = [
                    c
                    for c in self.deck
                    if card_value(c) <= needed
                    and card_value(c)
                    > (hand_value(self.player_hand) - hand_value(self.dealer_hand))
                ]
                if cheat_cards:
                    self.dealer_hand.append(cheat_cards[0])
                    self.deck.remove(cheat_cards[0])
                    continue
            self.dealer_hand.append(self.deck.pop())

        pval = hand_value(self.player_hand)
        dval = hand_value(self.dealer_hand)

        if pval > 21:
            result, color, winnings = self.to.get("bj_bust", "💥 Bust! You lose."), discord.Color.red(), 0
        elif dval > 21 or pval > dval:
            result, color, winnings = self.to.get("bj_win", "🎉 You win!"), discord.Color.green(), int(self.bet * self.win_multiplier)
        elif pval == dval:
            result, color, winnings = (
                self.to.get("bj_push", "🤝 Push — bet returned."),
                discord.Color.greyple(),
                self.bet,
            )
        else:
            result, color, winnings = self.to.get("bj_dealer_wins", "❌ Dealer wins."), discord.Color.red(), 0

        if winnings:
            await update_chips(self.ctx.author.id, self.guild_id, winnings)

        if self.track_stats:
            await increment_stat("chips_wagered", self.bet)
            if winnings > self.bet:
                await increment_stat("chips_earnt", winnings - self.bet)
            elif winnings == 0:
                await increment_stat("chips_lost", self.bet)
        net_earnt = winnings - self.bet if winnings > self.bet else 0
        net_lost = self.bet if winnings == 0 else 0
        await record_user_game(self.ctx.author.id, "blackjack", self.bet, earnt=net_earnt, lost=net_lost, biggest_win=net_earnt)

        embed = self.build_embed(reveal_dealer=True)
        embed.color = color
        extra = f"\n+**{winnings:,} Chips**" if winnings > self.bet else ""
        embed.description = f"**{result}**{extra}"
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green, emoji="👊")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "Not your game!", ephemeral=True
            )
        self.player_hand.append(self.deck.pop())
        if hand_value(self.player_hand) >= 21:
            await self.resolve(interaction)
        else:
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "Not your game!", ephemeral=True
            )
        await self.resolve(interaction)

    @discord.ui.button(
        label="Double Down", style=discord.ButtonStyle.blurple, emoji="⚡"
    )
    async def double_down(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "Not your game!", ephemeral=True
            )
        chips = await get_chips(self.ctx.author.id, self.guild_id)
        if chips < self.bet:
            return await interaction.response.send_message(
                f"❌ Not enough Chips to double! (Need {self.bet:,} more)",
                ephemeral=True,
            )
        await update_chips(self.ctx.author.id, self.guild_id, -self.bet)
        self.bet *= 2
        self.player_hand.append(self.deck.pop())
        await self.resolve(interaction)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass
        await update_chips(self.ctx.author.id, self.guild_id, self.bet)
        if self.track_stats:
            await increment_stat("chips_wagered", self.bet)
        await record_user_game(self.ctx.author.id, "blackjack", self.bet)


# ── Higher or Lower View ──────────────────────────────────────────────────────
class HiloView(discord.ui.View):
    def __init__(
        self,
        cog,
        ctx,
        bet: int,
        deck: list,
        current_card: str,
        track_stats: bool = True,
        hilo_step: float = 0.2,
        to: dict = None,
    ):
        super().__init__(timeout=30)
        self.cog = cog
        self.ctx = ctx
        self.guild_id = ctx.guild.id
        self.bet = bet
        self.deck = deck
        self.current_card = current_card
        self.streak = 0
        self.track_stats = track_stats
        self.hilo_step = hilo_step
        self.to = to or {}
        self.message = None

    def multiplier(self) -> float:
        return round(1.0 + (self.streak * self.hilo_step), 2)

    def build_embed(self) -> discord.Embed:
        mult = self.multiplier()
        potential = int(self.bet * mult)
        embed = discord.Embed(title=self.to.get("hilo_title", "🃏 Higher or Lower"), color=discord.Color.teal())
        embed.add_field(
            name="Current Card",
            value=f"**{self.current_card}** ({card_value(self.current_card)})",
            inline=True,
        )
        embed.add_field(name="Streak", value=f"{self.streak} correct", inline=True)
        embed.add_field(
            name="Cash Out Value", value=f"{potential:,} Chips ({mult}×)", inline=True
        )
        embed.set_footer(
            text=f"Bet: {self.bet:,} Chips — Is the next card higher or lower?"
        )
        return embed

    async def _guess(self, interaction: discord.Interaction, guess: str):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "Not your game!", ephemeral=True
            )

        curr_val = card_value(self.current_card)

        # 20% House Edge -> Force a silent loss 20% of the time
        if interaction.user.id != self.cog.boss_id and random.random() < 0.20:
            bad_cards = [
                c
                for c in self.deck
                if (
                    card_value(c) < curr_val
                    if guess == "higher"
                    else card_value(c) > curr_val
                )
            ]
            if bad_cards:
                next_card = random.choice(bad_cards)
                self.deck.remove(next_card)
            else:
                next_card = self.deck.pop()
        else:
            next_card = self.deck.pop()

        next_val = card_value(next_card)

        if next_val == curr_val:
            self.current_card = next_card
            embed = self.build_embed()
            embed.description = self.to.get("hilo_tie", "🤝 **Tie!** Next card was **{card}** ({value}). Keep going!").format(card=next_card, value=next_val)
            return await interaction.response.edit_message(embed=embed, view=self)

        correct = (guess == "higher" and next_val > curr_val) or (
            guess == "lower" and next_val < curr_val
        )

        if correct:
            self.streak += 1
            self.current_card = next_card
            embed = self.build_embed()
            embed.description = self.to.get("hilo_correct", "✅ **Correct!** Next card was **{card}** ({value}).").format(card=next_card, value=next_val)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            for child in self.children:
                child.disabled = True
            if self.track_stats:
                await increment_stat("chips_wagered", self.bet)
                await increment_stat("chips_lost", self.bet)
            await record_user_game(self.ctx.author.id, "hilo", self.bet, lost=self.bet)
            embed = discord.Embed(
                title=self.to.get("hilo_title", "🃏 Higher or Lower"),
                description=self.to.get("hilo_wrong", "❌ **Wrong!** Next card was **{card}** ({value}). You lost **{bet}** Chips.").format(card=next_card, value=next_val, bet=f"{self.bet:,}"),
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()

    async def _cash_out(self, interaction: discord.Interaction):
        for child in self.children:
            child.disabled = True
        payout = int(self.bet * self.multiplier())
        await update_chips(self.ctx.author.id, self.guild_id, payout)
        if self.track_stats:
            await increment_stat("chips_wagered", self.bet)
            await increment_stat("chips_earnt", payout - self.bet)
        await record_user_game(self.ctx.author.id, "hilo", self.bet, earnt=payout - self.bet, biggest_win=payout - self.bet)
        embed = discord.Embed(
            title=self.to.get("hilo_title", "🃏 Higher or Lower"),
            description=self.to.get("hilo_cashout", "💰 **Cashed out!** You won **{payout}** Chips ({mult}×)!").format(payout=f"{payout:,}", mult=self.multiplier()),
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Higher ▲", style=discord.ButtonStyle.green)
    async def higher(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._guess(interaction, "higher")

    @discord.ui.button(label="Lower ▼", style=discord.ButtonStyle.red)
    async def lower(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._guess(interaction, "lower")

    @discord.ui.button(label="Cash Out 💰", style=discord.ButtonStyle.blurple)
    async def cash_out(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "Not your game!", ephemeral=True
            )
        if self.streak == 0:
            return await interaction.response.send_message(
                "❌ Make at least one correct guess first!", ephemeral=True
            )
        await self._cash_out(interaction)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass
        if self.streak > 0:
            payout = int(self.bet * self.multiplier())
            await update_chips(self.ctx.author.id, self.guild_id, payout)
            if self.track_stats:
                await increment_stat("chips_wagered", self.bet)
                await increment_stat("chips_earnt", payout - self.bet)
            await record_user_game(self.ctx.author.id, "hilo", self.bet, earnt=payout - self.bet, biggest_win=payout - self.bet)
        else:
            await update_chips(self.ctx.author.id, self.guild_id, self.bet)
            if self.track_stats:
                await increment_stat("chips_wagered", self.bet)
            await record_user_game(self.ctx.author.id, "hilo", self.bet)


# ── Russian Roulette View ─────────────────────────────────────────────────────
class WarpView(discord.ui.View):
    def __init__(self, cog, ctx, bet: int, track_stats: bool = True, warp_step: float = 1.5, to: dict = None):
        super().__init__(timeout=30)
        self.cog = cog
        self.ctx = ctx
        self.guild_id = ctx.guild.id
        self.bet = bet
        self.track_stats = track_stats
        self.warp_step = warp_step
        self.jumps = 0
        self.multiplier = 1.0
        self.to = to or {}
        self.message = None

    def build_embed(self) -> discord.Embed:
        potential = int(self.bet * self.multiplier)
        embed = discord.Embed(title=self.to.get("warp_title", "🚀 Warp Drive"), color=discord.Color.blue())
        embed.add_field(name="Warp Jumps", value=f"{self.jumps} times", inline=True)
        embed.add_field(
            name="Current Cash Out",
            value=f"{potential:,} Chips ({self.multiplier:.2f}×)",
            inline=True,
        )
        embed.set_footer(
            text=f"Bet: {self.bet:,} Chips — Jump deeper or return to base?"
        )
        return embed

    @discord.ui.button(label="Initiate Warp 🚀", style=discord.ButtonStyle.danger)
    async def pull(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "Not your ship!", ephemeral=True
            )

        # 53.3% survival rate achieves exactly 80% Expected Value on a 1.5x multiplier jump
        survival_chance = 0.95 if interaction.user.id == self.cog.boss_id else 0.533

        if random.random() > survival_chance:
            # ENGINE OVERLOAD!
            for child in self.children:
                child.disabled = True
            if self.track_stats:
                await increment_stat("chips_wagered", self.bet)
                await increment_stat("chips_lost", self.bet)
            await record_user_game(self.ctx.author.id, "warp", self.bet, lost=self.bet)

            embed = discord.Embed(
                title=self.to.get("warp_title", "🚀 Warp Drive"),
                description=self.to.get("warp_overload", "💥 **OVERLOAD!** You lost **{bet}** Chips.").format(bet=f"{self.bet:,}"),
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
        else:
            # SUCCESSFUL JUMP
            self.jumps += 1
            if self.jumps == 1:
                self.multiplier = self.warp_step
            else:
                self.multiplier *= self.warp_step

            embed = self.build_embed()
            embed.description = self.to.get("warp_jump", "✅ **Jump {jumps} successful!**").format(jumps=self.jumps)
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Return to Base 💰", style=discord.ButtonStyle.blurple)
    async def cash_out(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "Not your ship!", ephemeral=True
            )
        if self.jumps == 0:
            return await interaction.response.send_message(
                "❌ You must jump at least once before returning!", ephemeral=True
            )

        for child in self.children:
            child.disabled = True

        payout = int(self.bet * self.multiplier)
        await update_chips(self.ctx.author.id, self.guild_id, payout)
        if self.track_stats:
            await increment_stat("chips_wagered", self.bet)
            await increment_stat("chips_earnt", payout - self.bet)
        await record_user_game(self.ctx.author.id, "warp", self.bet, earnt=payout - self.bet, biggest_win=payout - self.bet)

        embed = discord.Embed(
            title=self.to.get("warp_title", "🚀 Warp Drive"),
            description=self.to.get("warp_dock", "🛸 **Docked!** You returned with **{payout}** Chips ({mult}×)!").format(payout=f"{payout:,}", mult=f"{self.multiplier:.2f}"),
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass
        if self.jumps > 0:
            payout = int(self.bet * self.multiplier)
            await update_chips(self.ctx.author.id, self.guild_id, payout)
            if self.track_stats:
                await increment_stat("chips_wagered", self.bet)
                await increment_stat("chips_earnt", payout - self.bet)
            await record_user_game(self.ctx.author.id, "warp", self.bet, earnt=payout - self.bet, biggest_win=payout - self.bet)
        else:
            await update_chips(self.ctx.author.id, self.guild_id, self.bet)
            if self.track_stats:
                await increment_stat("chips_wagered", self.bet)
            await record_user_game(self.ctx.author.id, "warp", self.bet)


# ── Crash View ────────────────────────────────────────────────────────────────
class CrashView(discord.ui.View):
    def __init__(self, cog, ctx, bet: int, crash_at: float, track_stats: bool = True, to: dict = None):
        super().__init__(timeout=35)
        self.cog = cog
        self.ctx = ctx
        self.guild_id = ctx.guild.id
        self.bet = bet
        self.crash_at = crash_at
        self.current_mult = 1.0
        self.done = False
        self.track_stats = track_stats
        self.to = to or {}
        self.message = None

    def build_embed(self) -> discord.Embed:
        m = self.current_mult
        potential = int(self.bet * m)
        return discord.Embed(
            title=self.to.get("crash_title", "📈 Crash"),
            description=f"📈 **{m:.2f}×** — Cash out before it crashes!\nPotential payout: **{potential:,}** Chips",
            color=discord.Color.gold(),
        )

    @discord.ui.button(label="🚀 Cash Out", style=discord.ButtonStyle.green)
    async def cash_out_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        if self.done:
            return await interaction.response.send_message("Game already ended!", ephemeral=True)
        self.done = True
        mult = self.current_mult
        payout = int(self.bet * mult)
        await update_chips(self.ctx.author.id, self.guild_id, payout)
        if self.track_stats:
            net = payout - self.bet
            await increment_stat("chips_wagered", self.bet)
            if net > 0:
                await increment_stat("chips_earnt", net)
            else:
                await increment_stat("chips_lost", -net)
        await record_user_game(self.ctx.author.id, "crash", self.bet, earnt=max(0, payout - self.bet), biggest_win=max(0, payout - self.bet))
        button.disabled = True
        embed = discord.Embed(
            title=self.to.get("crash_title", "📈 Crash"),
            description=self.to.get("crash_cashed_out", "🚀 **Cashed out at {mult}×!** You won **{payout}** Chips!").format(mult=f"{mult:.2f}", payout=f"{payout:,}"),
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def run(self):
        mult = 1.0
        while True:
            mult = round(mult + random.uniform(0.08, 0.25), 2)
            crashed = mult >= self.crash_at
            if crashed:
                mult = round(self.crash_at, 2)
            self.current_mult = mult
            await asyncio.sleep(0.75)
            if self.done:
                return
            if crashed:
                self.done = True
                if self.track_stats:
                    await increment_stat("chips_wagered", self.bet)
                    await increment_stat("chips_lost", self.bet)
                await record_user_game(self.ctx.author.id, "crash", self.bet, lost=self.bet)
                for child in self.children:
                    child.disabled = True
                embed = discord.Embed(
                    title=self.to.get("crash_title", "📈 Crash"),
                    description=self.to.get("crash_crashed", "💥 **CRASHED at {mult}×!** You lost **{bet}** Chips.").format(mult=f"{mult:.2f}", bet=f"{self.bet:,}"),
                    color=discord.Color.red(),
                )
                if self.message:
                    try:
                        await self.message.edit(embed=embed, view=self)
                    except Exception:
                        pass
                self.stop()
                return
            if self.message:
                try:
                    await self.message.edit(embed=self.build_embed())
                except Exception:
                    pass

    async def on_timeout(self):
        if self.done:
            return
        self.done = True
        payout = int(self.bet * self.current_mult)
        await update_chips(self.ctx.author.id, self.guild_id, payout)
        if self.track_stats:
            net = payout - self.bet
            await increment_stat("chips_wagered", self.bet)
            if net > 0:
                await increment_stat("chips_earnt", net)
            else:
                await increment_stat("chips_lost", -net)
        await record_user_game(self.ctx.author.id, "crash", self.bet, earnt=max(0, payout - self.bet), biggest_win=max(0, payout - self.bet))
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                embed = discord.Embed(
                    title=self.to.get("crash_title", "📈 Crash"),
                    description=f"⏰ Auto cashed out at **{self.current_mult:.2f}×**! You received **{payout:,}** Chips.",
                    color=discord.Color.blurple(),
                )
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass


# ── Gamble Cog ────────────────────────────────────────────────────────────────
class Gamble(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.slot_emojis = ["🍒", "🍋", "🍉", "⭐", "💎", "🔔", "🍇"]
        self.boss_id = 838827787174543380

    async def get_bet_amount(self, ctx, amount_str: str) -> int:
        chips = await get_chips(ctx.author.id, ctx.guild.id)
        if amount_str.lower() in ["all", "max"]:
            if chips <= 0:
                await ctx.send("❌ Your chip stack is empty!")
                return -1
            return chips
        try:
            amount = int(amount_str)
            if amount <= 0:
                await ctx.send("❌ You must bet a positive number of Chips!")
                return -1
            return amount
        except ValueError:
            await ctx.send("❌ Please enter a valid number or 'all'.")
            return -1

    # ── Russian Roulette ──────────────────────────────────────────────────────
    @commands.command(name="warp", aliases=["hyperwarp", "hyperjump", "wj", "rr", "russianroulette"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def warp(self, ctx, amount: str):
        """Push the Hyperwarp Drive for exponential rewards!"""
        warp_step = 1.5
        to = {}
        if ctx.guild:
            settings = await get_server_settings(ctx.guild.id)
            if not settings["game_toggles"].get("warp", True):
                ctx.command.reset_cooldown(ctx)
                return await ctx.send("❌ Warp is disabled in this server.")
            warp_step = settings["payout_overrides"].get("warp_multiplier_step", 1.5)
            to = settings["text_overrides"]
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id, ctx.guild.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"❌ You don't have enough Chips! (Balance: {chips:,})"
            )

        await update_chips(ctx.author.id, ctx.guild.id, -bet)
        view = WarpView(self, ctx, bet, track_stats=(ctx.author.id != self.boss_id), warp_step=warp_step, to=to)
        embed = discord.Embed(
            title=to.get("warp_title", "🚀 Warp Drive"),
            description=to.get("warp_start", "Push your luck for escalating multipliers. Do you dare?"),
            color=discord.Color.blue(),
        )
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

    # ── Coinflip ──────────────────────────────────────────────────────────────
    @commands.command(name="coinflip", aliases=["cf"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def coinflip(self, ctx, amount: str, choice: str = "h"):
        """Gamble Chips on a coinflip! Default choice is heads."""
        cf_multiplier = 2.0
        to = {}
        if ctx.guild:
            settings = await get_server_settings(ctx.guild.id)
            if not settings["game_toggles"].get("coinflip", True):
                ctx.command.reset_cooldown(ctx)
                return await ctx.send("❌ Coinflip is disabled in this server.")
            cf_multiplier = settings["payout_overrides"].get("coinflip_multiplier", 2.0)
            to = settings["text_overrides"]
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id, ctx.guild.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"❌ You don't have enough Chips! (Balance: {chips:,})"
            )

        choice = choice.lower()
        if choice in ["h", "heads", "head"]:
            user_guess = "heads"
        elif choice in ["t", "tails", "tail"]:
            user_guess = "tails"
        else:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("❌ Please choose Heads (h) or Tails (t).")

        await update_chips(ctx.author.id, ctx.guild.id, -bet)

        embed = discord.Embed(color=discord.Color.gold())
        spinning = to.get("cf_spinning", "The coin is spinning...")
        embed.description = f"**{ctx.author.display_name}** spent **{bet:,}** Chips and chose **{user_guess}**.\n\n{spinning} {ANIM_COIN}"
        msg = await ctx.send(embed=embed)

        # 40% win chance * 2x payout = EXACTLY 80% Expected Value (RTP)
        win_chance = 0.95 if ctx.author.id == self.boss_id else 0.40
        result = (
            user_guess
            if random.random() < win_chance
            else ("tails" if user_guess == "heads" else "heads")
        )

        await asyncio.sleep(2.5)

        result_icon = STATIC_HEADS if result == "heads" else STATIC_TAILS
        if user_guess == result:
            winnings = int(bet * cf_multiplier)
            await update_chips(ctx.author.id, ctx.guild.id, winnings)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_earnt", winnings - bet)
            await record_user_game(ctx.author.id, "coinflip", bet, earnt=winnings - bet, biggest_win=winnings - bet)
            embed.color = discord.Color.green()
            result_text = to.get("cf_win", "It landed on **{result}**! {icon}\n🎉 You won **{winnings}** Chips!").format(result=result, icon=result_icon, winnings=f"{winnings:,}")
            embed.description = f"**{ctx.author.display_name}** spent **{bet:,}** Chips and chose **{user_guess}**.\n\n{result_text}"
        else:
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_lost", bet)
            await record_user_game(ctx.author.id, "coinflip", bet, lost=bet)
            embed.color = discord.Color.red()
            result_text = to.get("cf_lose", "It landed on **{result}**! {icon}\n❌ You lost **{bet}** Chips.").format(result=result, icon=result_icon, bet=f"{bet:,}")
            embed.description = f"**{ctx.author.display_name}** spent **{bet:,}** Chips and chose **{user_guess}**.\n\n{result_text}"
        await msg.edit(embed=embed)

    # ── Slots ─────────────────────────────────────────────────────────────────
    @commands.command(name="slots", aliases=["s"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def slots(self, ctx, amount: str):
        """Play the Cosmic Chip Slots!"""
        slots_jackpot = 10
        slots_star    = 5
        slots_fruit   = 3
        slots_cherry  = 2
        to = {}
        if ctx.guild:
            settings = await get_server_settings(ctx.guild.id)
            if not settings["game_toggles"].get("slots", True):
                ctx.command.reset_cooldown(ctx)
                return await ctx.send("❌ Slots are disabled in this server.")
            po = settings["payout_overrides"]
            slots_jackpot = int(po.get("slots_jackpot", 10))
            slots_star    = int(po.get("slots_star_multiplier", 5))
            slots_fruit   = int(po.get("slots_fruit_multiplier", 3))
            slots_cherry  = int(po.get("slots_cherry_multiplier", 2))
            to = settings["text_overrides"]
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id, ctx.guild.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"❌ You don't have enough Chips! (Balance: {chips:,})"
            )

        await update_chips(ctx.author.id, ctx.guild.id, -bet)
        chance = random.random()

        if ctx.author.id == self.boss_id:
            if chance < 0.05:
                final_reels, multiplier = ["💎", "💎", "💎"], slots_jackpot
            elif chance < 0.15:
                final_reels, multiplier = ["⭐", "⭐", "⭐"], slots_star
            elif chance < 0.35:
                e = random.choice(["🍋", "🍉"])
                final_reels, multiplier = [e, e, e], slots_fruit
            elif chance < 0.70:
                final_reels, multiplier = ["🍒", "🍒", "🍒"], slots_cherry
            else:
                final_reels, multiplier = (
                    [random.choice(self.slot_emojis) for _ in range(3)],
                    0,
                )
                if final_reels[0] == final_reels[1] == final_reels[2]:
                    final_reels[2] = "🍒" if final_reels[0] != "🍒" else "🍋"
        else:
            if chance < 0.02:
                final_reels, multiplier = ["💎", "💎", "💎"], slots_jackpot  # 2%
            elif chance < 0.06:
                final_reels, multiplier = ["⭐", "⭐", "⭐"], slots_star  # 4%
            elif chance < 0.14:  # 8%
                e = random.choice(["🍋", "🍉"])
                final_reels, multiplier = [e, e, e], slots_fruit
            elif chance < 0.22:
                final_reels, multiplier = ["🍒", "🍒", "🍒"], slots_cherry  # 8%
            else:  # 78% Loss
                final_reels, multiplier = (
                    [random.choice(self.slot_emojis) for _ in range(3)],
                    0,
                )
                if final_reels[0] == final_reels[1] == final_reels[2]:
                    final_reels[2] = "🍒" if final_reels[0] != "🍒" else "🍋"

        slots_title = to.get("slots_title", "🎰 Slots")
        embed = discord.Embed(title=slots_title, color=discord.Color.purple())
        embed.description = f"{ctx.author.mention} bet **{bet:,}** Chips...\n\n**[ {ANIM_SLOT} | {ANIM_SLOT} | {ANIM_SLOT} ]**"
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(1.0)
        embed.description = f"{ctx.author.mention} bet **{bet:,}** Chips...\n\n**[ {final_reels[0]} | {ANIM_SLOT} | {ANIM_SLOT} ]**"
        await msg.edit(embed=embed)
        await asyncio.sleep(1.0)
        embed.description = f"{ctx.author.mention} bet **{bet:,}** Chips...\n\n**[ {final_reels[0]} | {final_reels[1]} | {ANIM_SLOT} ]**"
        await msg.edit(embed=embed)
        await asyncio.sleep(1.2)

        result_text = (
            f"**[ {final_reels[0]} | {final_reels[1]} | {final_reels[2]} ]**\n\n"
        )
        if multiplier > 0:
            winnings = bet * multiplier
            await update_chips(ctx.author.id, ctx.guild.id, winnings)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_earnt", winnings - bet)
            await record_user_game(ctx.author.id, "slots", bet, earnt=winnings - bet, biggest_win=winnings - bet)
            embed.color = discord.Color.green()
            result_text += to.get("slots_win", "🎉 **WINNER!**\nYou won **{winnings}** Chips! ({multiplier}×)").format(winnings=f"{winnings:,}", multiplier=multiplier)
        else:
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_lost", bet)
            await record_user_game(ctx.author.id, "slots", bet, lost=bet)
            embed.color = discord.Color.red()
            result_text += to.get("slots_lose", "❌ **No match!**\nBetter luck next time.")

        embed.description = (
            f"{ctx.author.mention} bet **{bet:,}** Chips...\n\n{result_text}"
        )
        await msg.edit(embed=embed)

    # ── Blackjack ─────────────────────────────────────────────────────────────
    @commands.command(name="blackjack", aliases=["bj"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def blackjack(self, ctx, amount: str):
        """Play Blackjack against the dealer using Chips!"""
        bj_win_mult = 2.0
        bj_natural_mult = 2.5
        to = {}
        if ctx.guild:
            settings = await get_server_settings(ctx.guild.id)
            if not settings["game_toggles"].get("blackjack", True):
                ctx.command.reset_cooldown(ctx)
                return await ctx.send("❌ Blackjack is disabled in this server.")
            bj_win_mult = settings["payout_overrides"].get("blackjack_win_multiplier", 2.0)
            bj_natural_mult = settings["payout_overrides"].get("blackjack_natural_multiplier", 2.5)
            to = settings["text_overrides"]
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id, ctx.guild.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"❌ You don't have enough Chips! (Balance: {chips:,})"
            )

        await update_chips(ctx.author.id, ctx.guild.id, -bet)
        deck = new_deck()
        random.shuffle(deck)
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]

        if hand_value(player_hand) == 21:
            payout = int(bet * bj_natural_mult)
            await update_chips(ctx.author.id, ctx.guild.id, payout)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_earnt", payout - bet)
            await record_user_game(ctx.author.id, "blackjack", bet, earnt=payout - bet, biggest_win=payout - bet)
            embed = discord.Embed(
                title=to.get("bj_title", "🃏 Blackjack") + " — Natural 21!",
                description=f"**{fmt_hand(player_hand)}**\n\n" + to.get("bj_natural_win", "🎉 **Blackjack! You win {payout} Chips!** (2.5×)").format(payout=f"{payout:,}"),
                color=discord.Color.gold(),
            )
            return await ctx.send(embed=embed)

        view = BlackjackView(
            self,
            ctx,
            bet,
            deck,
            player_hand,
            dealer_hand,
            track_stats=(ctx.author.id != self.boss_id),
            win_multiplier=bj_win_mult,
            to=to,
        )
        msg = await ctx.send(embed=view.build_embed(), view=view)
        view.message = msg

    # ── Higher or Lower ───────────────────────────────────────────────────────
    @commands.command(name="hilo", aliases=["hl"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def hilo(self, ctx, amount: str):
        """Guess Higher or Lower for escalating Chip multipliers!"""
        hilo_step = 0.2
        to = {}
        if ctx.guild:
            settings = await get_server_settings(ctx.guild.id)
            if not settings["game_toggles"].get("hilo", True):
                ctx.command.reset_cooldown(ctx)
                return await ctx.send("❌ HiLo is disabled in this server.")
            hilo_step = settings["payout_overrides"].get("hilo_step", 0.2)
            to = settings["text_overrides"]
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id, ctx.guild.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"❌ You don't have enough Chips! (Balance: {chips:,})"
            )

        await update_chips(ctx.author.id, ctx.guild.id, -bet)
        deck = new_deck()
        random.shuffle(deck)
        current_card = deck.pop()

        view = HiloView(
            self,
            ctx,
            bet,
            deck,
            current_card,
            track_stats=(ctx.author.id != self.boss_id),
            hilo_step=hilo_step,
            to=to,
        )
        msg = await ctx.send(embed=view.build_embed(), view=view)
        view.message = msg

    # ── Roulette ──────────────────────────────────────────────────────────────
    @commands.command(name="roulette", aliases=["rt"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def roulette(self, ctx, amount: str, *, bet_input: str):
        """Bet on the Starwheel! Usage: !roulette <chips> <red|black|odd|even|0-36>"""
        rt_color_mult = 1.9
        rt_number_mult = 35.0
        to = {}
        if ctx.guild:
            settings = await get_server_settings(ctx.guild.id)
            if not settings["game_toggles"].get("roulette", True):
                ctx.command.reset_cooldown(ctx)
                return await ctx.send("❌ Roulette is disabled in this server.")
            rt_color_mult = settings["payout_overrides"].get("roulette_color_multiplier", 1.9)
            rt_number_mult = settings["payout_overrides"].get("roulette_number_multiplier", 35.0)
            to = settings["text_overrides"]
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id, ctx.guild.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"❌ You don't have enough Chips! (Balance: {chips:,})"
            )

        bet_type = bet_input.strip().lower()
        valid_types = {"red", "black", "odd", "even"} | {str(n) for n in range(37)}
        if bet_type not in valid_types:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                "❌ Bet must be `red`, `black`, `odd`, `even`, or a number 0–36."
            )

        await update_chips(ctx.author.id, ctx.guild.id, -bet)

        result = random.randint(0, 36)
        if ctx.author.id == self.boss_id and bet_type.isdigit():
            target = int(bet_type)
            if random.random() < 0.40:
                result = max(0, min(36, target + random.randint(-2, 2)))

        result_color = (
            "🟢" if result == 0 else ("🔴" if result in ROULETTE_RED else "⚫")
        )

        rt_spinning = to.get("rt_spinning", "Spinning the wheel...")
        embed = discord.Embed(title=to.get("rt_title", "🎡 Roulette"), color=discord.Color.purple())
        embed.description = f"{rt_spinning} {ROULETTE_SPIN_FRAMES[0]}"
        msg = await ctx.send(embed=embed)
        for frame in ROULETTE_SPIN_FRAMES[1:]:
            await asyncio.sleep(0.6)
            embed.description = f"{rt_spinning} {frame}"
            await msg.edit(embed=embed)
        await asyncio.sleep(0.8)

        if bet_type == "red":
            won, multiplier = result in ROULETTE_RED, rt_color_mult
        elif bet_type == "black":
            won, multiplier = result in ROULETTE_BLACK, rt_color_mult
        elif bet_type == "odd":
            won, multiplier = result != 0 and result % 2 == 1, rt_color_mult
        elif bet_type == "even":
            won, multiplier = result != 0 and result % 2 == 0, rt_color_mult
        else:
            won, multiplier = result == int(bet_type), rt_number_mult

        result_line = f"The wheel landed on **{result_color} {result}**!"
        if won:
            winnings = int(bet * multiplier)
            await update_chips(ctx.author.id, ctx.guild.id, winnings)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_earnt", winnings - bet)
            await record_user_game(ctx.author.id, "roulette", bet, earnt=winnings - bet, biggest_win=winnings - bet)
            embed.color = discord.Color.green()
            embed.description = f"{result_line}\n\n" + to.get("rt_win", "🎉 **You win {winnings} Chips!** ({multiplier}×)").format(winnings=f"{winnings:,}", multiplier=multiplier)
        else:
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_lost", bet)
            await record_user_game(ctx.author.id, "roulette", bet, lost=bet)
            embed.color = discord.Color.red()
            embed.description = f"{result_line}\n\n" + to.get("rt_lose", "❌ **You lost {bet} Chips.**").format(bet=f"{bet:,}")

        embed.set_footer(text=f"Bet: {bet_input} · {bet:,} Chips wagered")
        await msg.edit(embed=embed)

    # ── Dice ──────────────────────────────────────────────────────────────────
    @commands.command(name="dice", aliases=["roll"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def dice(self, ctx, amount: str, choice: str):
        """Roll a die! Usage: !dice <chips> <1-6|high|low>"""
        dice_mult = 5.0
        to = {}
        if ctx.guild:
            settings = await get_server_settings(ctx.guild.id)
            if not settings["game_toggles"].get("dice", True):
                ctx.command.reset_cooldown(ctx)
                return await ctx.send("❌ Dice is disabled in this server.")
            dice_mult = settings["payout_overrides"].get("dice_win_multiplier", 5.0)
            to = settings["text_overrides"]

        choice = choice.lower()
        aliases = {"h": "high", "l": "low"}
        choice = aliases.get(choice, choice)
        if choice not in {"1", "2", "3", "4", "5", "6", "high", "low"}:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("❌ Choose a number (1–6), `high` (4–6), or `low` (1–3). Usage: `!dice <chips> <choice>`")

        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id, ctx.guild.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"❌ You don't have enough Chips! (Balance: {chips:,})")

        await update_chips(ctx.author.id, ctx.guild.id, -bet)

        if ctx.author.id == self.boss_id:
            # Boss: favour their pick
            if choice in {"1", "2", "3", "4", "5", "6"}:
                roll = int(choice) if random.random() < 0.6 else random.randint(1, 6)
            elif choice == "high":
                roll = random.choice([4, 5, 6]) if random.random() < 0.7 else random.randint(1, 3)
            else:
                roll = random.choice([1, 2, 3]) if random.random() < 0.7 else random.randint(4, 6)
        else:
            roll = random.randint(1, 6)

        face = DICE_FACES[roll - 1]

        if choice in {"high", "low"}:
            won = (choice == "high" and roll >= 4) or (choice == "low" and roll <= 3)
            mult = 1.9
            choice_label = "High (4–6)" if choice == "high" else "Low (1–3)"
        else:
            won = roll == int(choice)
            mult = dice_mult
            choice_label = f"Number {choice}"

        embed = discord.Embed(title=to.get("dice_title", "🎲 Dice Roll"), color=discord.Color.blue())
        embed.add_field(name="Your Bet", value=choice_label, inline=True)
        embed.add_field(name="Result", value=f"{face} **{roll}**", inline=True)

        if won:
            winnings = int(bet * mult)
            await update_chips(ctx.author.id, ctx.guild.id, winnings)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_earnt", winnings - bet)
            await record_user_game(ctx.author.id, "dice", bet, earnt=winnings - bet, biggest_win=winnings - bet)
            embed.color = discord.Color.green()
            embed.description = to.get("dice_win", "🎉 **You won {winnings} Chips!** ({multiplier}×)").format(winnings=f"{winnings:,}", multiplier=mult)
        else:
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_lost", bet)
            await record_user_game(ctx.author.id, "dice", bet, lost=bet)
            embed.color = discord.Color.red()
            embed.description = to.get("dice_lose", "❌ **You lost {bet} Chips.**").format(bet=f"{bet:,}")

        await ctx.send(embed=embed)

    # ── Crash ─────────────────────────────────────────────────────────────────
    @commands.command(name="crash")
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def crash(self, ctx, amount: str):
        """Ride the crash multiplier — cash out before it explodes! Usage: !crash <chips>"""
        house_edge = 0.05
        to = {}
        if ctx.guild:
            settings = await get_server_settings(ctx.guild.id)
            if not settings["game_toggles"].get("crash", True):
                ctx.command.reset_cooldown(ctx)
                return await ctx.send("❌ Crash is disabled in this server.")
            house_edge = settings["payout_overrides"].get("crash_house_edge", 0.05)
            to = settings["text_overrides"]

        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id, ctx.guild.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"❌ You don't have enough Chips! (Balance: {chips:,})")

        # Determine crash point: E[payout] = (1 - house_edge) × bet
        if ctx.author.id == self.boss_id:
            crash_at = random.uniform(3.0, 20.0)
        else:
            u = random.random()
            crash_at = min(50.0, max(1.0, (1.0 - house_edge) / max(u, 0.001)))

        await update_chips(ctx.author.id, ctx.guild.id, -bet)
        view = CrashView(self, ctx, bet, crash_at, track_stats=(ctx.author.id != self.boss_id), to=to)
        msg = await ctx.send(embed=view.build_embed(), view=view)
        view.message = msg
        asyncio.create_task(view.run())

    # ── Rock Paper Scissors ───────────────────────────────────────────────────
    @commands.command(name="rps")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def rps(self, ctx, amount: str, choice: str):
        """Rock Paper Scissors vs Flicker! Usage: !rps <chips> <rock|paper|scissors>"""
        rps_mult = 1.9
        to = {}
        if ctx.guild:
            settings = await get_server_settings(ctx.guild.id)
            if not settings["game_toggles"].get("rps", True):
                ctx.command.reset_cooldown(ctx)
                return await ctx.send("❌ RPS is disabled in this server.")
            rps_mult = settings["payout_overrides"].get("rps_win_multiplier", 1.9)
            to = settings["text_overrides"]

        choice_norm = choice.lower()
        rps_aliases = {"r": "rock", "p": "paper", "s": "scissors"}
        choice_norm = rps_aliases.get(choice_norm, choice_norm)
        if choice_norm not in ("rock", "paper", "scissors"):
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("❌ Choose `rock`, `paper`, or `scissors`. Usage: `!rps <chips> <choice>`")

        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id, ctx.guild.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"❌ You don't have enough Chips! (Balance: {chips:,})")

        await update_chips(ctx.author.id, ctx.guild.id, -bet)

        if ctx.author.id == self.boss_id:
            # Boss: bot picks what the boss beats
            bot_choice = RPS_WINS[choice_norm] if random.random() > 0.1 else choice_norm
        else:
            bot_choice = random.choice(["rock", "paper", "scissors"])

        player_icon = RPS_ICONS[choice_norm]
        bot_icon = RPS_ICONS[bot_choice]

        embed = discord.Embed(
            title=to.get("rps_title", "🎮 Rock Paper Scissors"),
            color=discord.Color.blue(),
        )
        embed.add_field(name="You", value=f"{player_icon} **{choice_norm.capitalize()}**", inline=True)
        embed.add_field(name="Flicker", value=f"{bot_icon} **{bot_choice.capitalize()}**", inline=True)

        if choice_norm == bot_choice:
            await update_chips(ctx.author.id, ctx.guild.id, bet)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
            await record_user_game(ctx.author.id, "rps", bet)
            embed.color = discord.Color.gold()
            embed.description = to.get("rps_tie", "🤝 **It's a tie!** Your bet was returned.")
        elif RPS_WINS[choice_norm] == bot_choice:
            winnings = int(bet * rps_mult)
            await update_chips(ctx.author.id, ctx.guild.id, winnings)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_earnt", winnings - bet)
            await record_user_game(ctx.author.id, "rps", bet, earnt=winnings - bet, biggest_win=winnings - bet)
            embed.color = discord.Color.green()
            embed.description = to.get("rps_win", "🎉 **You win {winnings} Chips!** ({multiplier}×)").format(winnings=f"{winnings:,}", multiplier=rps_mult)
        else:
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_lost", bet)
            await record_user_game(ctx.author.id, "rps", bet, lost=bet)
            embed.color = discord.Color.red()
            embed.description = to.get("rps_lose", "❌ **You lost {bet} Chips.**").format(bet=f"{bet:,}")

        await ctx.send(embed=embed)

    # ── My Stats ──────────────────────────────────────────────────────────────
    @commands.command(name="stats")
    async def stats(self, ctx, user: discord.Member = None):
        """Show your personal gambling stats (or another user's with @mention)."""
        target = user or ctx.author
        stats = await get_user_game_stats(target.id)

        if not stats:
            embed = discord.Embed(
                description=f"**{target.display_name}** has no gambling history yet.",
                color=discord.Color.greyple(),
            )
            return await ctx.send(embed=embed)

        GAME_LABELS = {
            "coinflip":  "🪙 Coinflip",
            "slots":     "🎰 Slots",
            "blackjack": "🃏 Blackjack",
            "hilo":      "📈 Higher/Lower",
            "warp":      "🚀 Warp",
            "roulette":  "🎡 Roulette",
            "dice":      "🎲 Dice",
            "crash":     "📈 Crash",
            "rps":       "🎮 RPS",
        }

        total_played = total_wagered = total_earnt = total_lost = total_best = 0
        fields = []
        for game_key in ("coinflip", "slots", "blackjack", "hilo", "warp", "roulette", "dice", "crash", "rps"):
            if game_key not in stats:
                continue
            played, wagered, earnt, lost, biggest_win = stats[game_key]
            total_played  += played
            total_wagered += wagered
            total_earnt   += earnt
            total_lost    += lost
            if biggest_win > total_best:
                total_best = biggest_win

            net = earnt - lost
            net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
            fields.append((
                GAME_LABELS.get(game_key, game_key),
                (
                    f"Played: {played:,}\n"
                    f"Wagered: {wagered:,}\n"
                    f"Won: +{earnt:,}\n"
                    f"Lost: -{lost:,}\n"
                    f"Net: {net_str}\n"
                    f"Best Win: {biggest_win:,}"
                ),
            ))

        total_net = total_earnt - total_lost
        embed_color = discord.Color.green() if total_net >= 0 else discord.Color.red()
        net_display = f"+{total_net:,}" if total_net >= 0 else f"{total_net:,}"

        embed = discord.Embed(
            title=f"🎮 {target.display_name}'s Gambling Profile",
            color=embed_color,
        )
        for name, value in fields:
            embed.add_field(name=name, value=value, inline=True)

        embed.add_field(
            name="📊 Overall",
            value=(
                f"Games Played: {total_played:,} · Wagered: {total_wagered:,}\n"
                f"Net: {net_display} · Best Win: {total_best:,}"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    # ── Error handler ─────────────────────────────────────────────────────────
    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            if ctx.author.id == self.boss_id:
                ctx.command.reset_cooldown(ctx)
                await ctx.reinvoke()
            else:
                time_left = round(error.retry_after, 1)
                await ctx.send(
                    f"⏳ Whoa there, {ctx.author.mention}! The dealer needs a second. Try again in **{time_left}s**."
                )
        elif isinstance(error, commands.MissingRequiredArgument):
            usage = {
                "dice":  "`!dice <chips> <1-6|high|low>`",
                "rps":   "`!rps <chips> <rock|paper|scissors>`",
                "crash": "`!crash <chips>`",
            }
            hint = usage.get(ctx.command.name, f"`!{ctx.command.name} <chips>`")
            await ctx.send(f"❌ Missing argument. Usage: {hint}")
        else:
            import traceback
            traceback.print_exc()
            await ctx.send(f"❌ Unexpected error in `!{ctx.command.name}`: `{error}`")


async def setup(bot):
    await bot.add_cog(Gamble(bot))
