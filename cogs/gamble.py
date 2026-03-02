import discord
import random
import asyncio
import itertools
from discord.ext import commands
from database import get_chips, update_chips, increment_stat, record_user_game, get_user_game_stats

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
    ):
        super().__init__(timeout=30)
        self.cog = cog
        self.ctx = ctx
        self.bet = bet
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.track_stats = track_stats
        self.message = None

    def build_embed(self, reveal_dealer=False) -> discord.Embed:
        pval = hand_value(self.player_hand)
        if reveal_dealer:
            dealer_display = (
                f"{fmt_hand(self.dealer_hand)} ({hand_value(self.dealer_hand)})"
            )
        else:
            dealer_display = f"{self.dealer_hand[0]}  🂠"
        embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.dark_gold())
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
            result, color, winnings = "💥 Bust! You lose.", discord.Color.red(), 0
        elif dval > 21 or pval > dval:
            result, color, winnings = "🎉 You win!", discord.Color.green(), self.bet * 2
        elif pval == dval:
            result, color, winnings = (
                "🤝 Push — bet returned.",
                discord.Color.greyple(),
                self.bet,
            )
        else:
            result, color, winnings = "❌ Dealer wins.", discord.Color.red(), 0

        if winnings:
            await update_chips(self.ctx.author.id, winnings)

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
        chips = await get_chips(self.ctx.author.id)
        if chips < self.bet:
            return await interaction.response.send_message(
                f"❌ Not enough Chips to double! (Need {self.bet:,} more)",
                ephemeral=True,
            )
        await update_chips(self.ctx.author.id, -self.bet)
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
        await update_chips(self.ctx.author.id, self.bet)
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
    ):
        super().__init__(timeout=30)
        self.cog = cog
        self.ctx = ctx
        self.bet = bet
        self.deck = deck
        self.current_card = current_card
        self.streak = 0
        self.track_stats = track_stats
        self.message = None

    def multiplier(self) -> float:
        # Adds 0.2x endlessly per correct guess
        return round(1.0 + (self.streak * 0.2), 2)

    def build_embed(self) -> discord.Embed:
        mult = self.multiplier()
        potential = int(self.bet * mult)
        embed = discord.Embed(title="🃏 Higher or Lower", color=discord.Color.teal())
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
            embed.description = f"🤝 **Tie!** Next card was also **{next_card}** ({next_val}). Keep going!"
            return await interaction.response.edit_message(embed=embed, view=self)

        correct = (guess == "higher" and next_val > curr_val) or (
            guess == "lower" and next_val < curr_val
        )

        if correct:
            self.streak += 1
            self.current_card = next_card
            embed = self.build_embed()
            embed.description = (
                f"✅ **Correct!** Next card was **{next_card}** ({next_val})."
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            for child in self.children:
                child.disabled = True
            if self.track_stats:
                await increment_stat("chips_wagered", self.bet)
                await increment_stat("chips_lost", self.bet)
                await record_user_game(self.ctx.author.id, "hilo", self.bet, lost=self.bet)
            embed = discord.Embed(
                title="🃏 Higher or Lower",
                description=f"❌ **Wrong!** Next card was **{next_card}** ({next_val}). You lost **{self.bet:,} Chips**.",
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()

    async def _cash_out(self, interaction: discord.Interaction):
        for child in self.children:
            child.disabled = True
        payout = int(self.bet * self.multiplier())
        await update_chips(self.ctx.author.id, payout)
        if self.track_stats:
            await increment_stat("chips_wagered", self.bet)
            await increment_stat("chips_earnt", payout - self.bet)
            await record_user_game(self.ctx.author.id, "hilo", self.bet, earnt=payout - self.bet, biggest_win=payout - self.bet)
        embed = discord.Embed(
            title="🃏 Higher or Lower",
            description=f"💰 **Cashed out!** You won **{payout:,} Chips** ({self.multiplier()}×)!",
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
            await update_chips(self.ctx.author.id, payout)
            if self.track_stats:
                await increment_stat("chips_wagered", self.bet)
                await increment_stat("chips_earnt", payout - self.bet)
                await record_user_game(self.ctx.author.id, "hilo", self.bet, earnt=payout - self.bet, biggest_win=payout - self.bet)
        else:
            await update_chips(self.ctx.author.id, self.bet)
            if self.track_stats:
                await increment_stat("chips_wagered", self.bet)
                await record_user_game(self.ctx.author.id, "hilo", self.bet)


# ── Russian Roulette View ─────────────────────────────────────────────────────
class WarpView(discord.ui.View):
    def __init__(self, cog, ctx, bet: int, track_stats: bool = True):
        super().__init__(timeout=30)
        self.cog = cog
        self.ctx = ctx
        self.bet = bet
        self.track_stats = track_stats
        self.jumps = 0
        self.multiplier = 1.0
        self.message = None

    def build_embed(self) -> discord.Embed:
        potential = int(self.bet * self.multiplier)
        embed = discord.Embed(title="🚀 Hyperwarp Drive", color=discord.Color.blue())
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
                title="🚀 Hyperwarp Drive",
                description=f"💥 **OVERLOAD!** You pushed the engines too far. You lost **{self.bet:,} Chips**.",
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
        else:
            # SUCCESSFUL JUMP
            self.jumps += 1
            if self.jumps == 1:
                self.multiplier = 1.5
            else:
                self.multiplier *= 1.5  # Exponential multiplier

            embed = self.build_embed()
            embed.description = (
                f"🌌 *ZOOOOM...* You safely navigated jump {self.jumps}!"
            )
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
        await update_chips(self.ctx.author.id, payout)
        if self.track_stats:
            await increment_stat("chips_wagered", self.bet)
            await increment_stat("chips_earnt", payout - self.bet)
            await record_user_game(self.ctx.author.id, "warp", self.bet, earnt=payout - self.bet, biggest_win=payout - self.bet)

        embed = discord.Embed(
            title="🚀 Hyperwarp Drive",
            description=f"🛸 **Safely docked!** You returned to base with **{payout:,} Chips** ({self.multiplier:.2f}×)!",
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
            await update_chips(self.ctx.author.id, payout)
            if self.track_stats:
                await increment_stat("chips_wagered", self.bet)
                await increment_stat("chips_earnt", payout - self.bet)
                await record_user_game(self.ctx.author.id, "warp", self.bet, earnt=payout - self.bet, biggest_win=payout - self.bet)
        else:
            await update_chips(self.ctx.author.id, self.bet)
            if self.track_stats:
                await increment_stat("chips_wagered", self.bet)
                await record_user_game(self.ctx.author.id, "warp", self.bet)


# ── Gamble Cog ────────────────────────────────────────────────────────────────
class Gamble(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.slot_emojis = ["🍒", "🍋", "🍉", "⭐", "💎", "🔔", "🍇"]
        self.boss_id = 838827787174543380

    async def get_bet_amount(self, ctx, amount_str: str) -> int:
        chips = await get_chips(ctx.author.id)
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
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"❌ You don't have enough Chips! (Balance: {chips:,})"
            )

        await update_chips(ctx.author.id, -bet)
        view = WarpView(self, ctx, bet, track_stats=(ctx.author.id != self.boss_id))
        embed = discord.Embed(
            title="🚀 Hyperwarp Drive",
            description="The engines are humming... Dare to initiate warp?",
            color=discord.Color.blue(),
        )
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

    # ── Coinflip ──────────────────────────────────────────────────────────────
    @commands.command(name="coinflip", aliases=["cf"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def coinflip(self, ctx, amount: str, choice: str = "h"):
        """Gamble Chips on a coinflip! Default choice is heads."""
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id)
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

        await update_chips(ctx.author.id, -bet)

        embed = discord.Embed(color=discord.Color.gold())
        embed.description = f"**{ctx.author.display_name}** spent **{bet:,}** Chips and chose **{user_guess}**.\n\nThe coin spins... {ANIM_COIN}"
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
            winnings = bet * 2
            await update_chips(ctx.author.id, winnings)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_earnt", winnings - bet)
                await record_user_game(ctx.author.id, "coinflip", bet, earnt=winnings - bet, biggest_win=winnings - bet)
            embed.color = discord.Color.green()
            embed.description = f"**{ctx.author.display_name}** spent **{bet:,}** Chips and chose **{user_guess}**.\n\nIt landed on **{result}**! {result_icon}\n🎉 You won **{winnings:,}** Chips!"
        else:
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_lost", bet)
                await record_user_game(ctx.author.id, "coinflip", bet, lost=bet)
            embed.color = discord.Color.red()
            embed.description = f"**{ctx.author.display_name}** spent **{bet:,}** Chips and chose **{user_guess}**.\n\nIt landed on **{result}**! {result_icon}\n❌ You lost **{bet:,}** Chips."
        await msg.edit(embed=embed)

    # ── Slots ─────────────────────────────────────────────────────────────────
    @commands.command(name="slots", aliases=["s"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def slots(self, ctx, amount: str):
        """Play the Cosmic Chip Slots!"""
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"❌ You don't have enough Chips! (Balance: {chips:,})"
            )

        await update_chips(ctx.author.id, -bet)
        chance = random.random()

        if ctx.author.id == self.boss_id:
            if chance < 0.05:
                final_reels, multiplier = ["💎", "💎", "💎"], 10
            elif chance < 0.15:
                final_reels, multiplier = ["⭐", "⭐", "⭐"], 5
            elif chance < 0.35:
                e = random.choice(["🍋", "🍉"])
                final_reels, multiplier = [e, e, e], 3
            elif chance < 0.70:
                final_reels, multiplier = ["🍒", "🍒", "🍒"], 2
            else:
                final_reels, multiplier = (
                    [random.choice(self.slot_emojis) for _ in range(3)],
                    0,
                )
                if final_reels[0] == final_reels[1] == final_reels[2]:
                    final_reels[2] = "🍒" if final_reels[0] != "🍒" else "🍋"
        else:
            # Mathematical 80% Expected Value (RTP) Setup:
            # (0.02*10) + (0.04*5) + (0.08*3) + (0.08*2) = 0.80 EV
            if chance < 0.02:
                final_reels, multiplier = ["💎", "💎", "💎"], 10  # 2%
            elif chance < 0.06:
                final_reels, multiplier = ["⭐", "⭐", "⭐"], 5  # 4%
            elif chance < 0.14:  # 8%
                e = random.choice(["🍋", "🍉"])
                final_reels, multiplier = [e, e, e], 3
            elif chance < 0.22:
                final_reels, multiplier = ["🍒", "🍒", "🍒"], 2  # 8%
            else:  # 78% Loss
                final_reels, multiplier = (
                    [random.choice(self.slot_emojis) for _ in range(3)],
                    0,
                )
                if final_reels[0] == final_reels[1] == final_reels[2]:
                    final_reels[2] = "🍒" if final_reels[0] != "🍒" else "🍋"

        embed = discord.Embed(
            title="🎰 Cosmic Chip Slots 🎰", color=discord.Color.purple()
        )
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
            await update_chips(ctx.author.id, winnings)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_earnt", winnings - bet)
                await record_user_game(ctx.author.id, "slots", bet, earnt=winnings - bet, biggest_win=winnings - bet)
            embed.color = discord.Color.green()
            result_text += (
                f"🎉 **WINNER!** 🎉\nYou won **{winnings:,}** Chips! ({multiplier}×)"
            )
        else:
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_lost", bet)
                await record_user_game(ctx.author.id, "slots", bet, lost=bet)
            embed.color = discord.Color.red()
            result_text += "❌ **Lost!** ❌\nBetter luck next time."

        embed.description = (
            f"{ctx.author.mention} bet **{bet:,}** Chips...\n\n{result_text}"
        )
        await msg.edit(embed=embed)

    # ── Blackjack ─────────────────────────────────────────────────────────────
    @commands.command(name="blackjack", aliases=["bj"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def blackjack(self, ctx, amount: str):
        """Play Blackjack against the dealer using Chips!"""
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"❌ You don't have enough Chips! (Balance: {chips:,})"
            )

        await update_chips(ctx.author.id, -bet)
        deck = new_deck()
        random.shuffle(deck)
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]

        if hand_value(player_hand) == 21:
            payout = int(bet * 2.5)
            await update_chips(ctx.author.id, payout)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_earnt", payout - bet)
                await record_user_game(ctx.author.id, "blackjack", bet, earnt=payout - bet, biggest_win=payout - bet)
            embed = discord.Embed(
                title="🃏 Blackjack — Natural 21!",
                description=f"**{fmt_hand(player_hand)}**\n\n🎉 **Blackjack! You win {payout:,} Chips!** (2.5×)",
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
        )
        msg = await ctx.send(embed=view.build_embed(), view=view)
        view.message = msg

    # ── Higher or Lower ───────────────────────────────────────────────────────
    @commands.command(name="hilo", aliases=["hl"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def hilo(self, ctx, amount: str):
        """Guess Higher or Lower for escalating Chip multipliers!"""
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"❌ You don't have enough Chips! (Balance: {chips:,})"
            )

        await update_chips(ctx.author.id, -bet)
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
        )
        msg = await ctx.send(embed=view.build_embed(), view=view)
        view.message = msg

    # ── Roulette ──────────────────────────────────────────────────────────────
    @commands.command(name="roulette", aliases=["rt"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def roulette(self, ctx, amount: str, *, bet_input: str):
        """Bet on the Starwheel! Usage: !roulette <chips> <red|black|odd|even|0-36>"""
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            return ctx.command.reset_cooldown(ctx)

        chips = await get_chips(ctx.author.id)
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

        await update_chips(ctx.author.id, -bet)

        result = random.randint(0, 36)
        if ctx.author.id == self.boss_id and bet_type.isdigit():
            target = int(bet_type)
            if random.random() < 0.40:
                result = max(0, min(36, target + random.randint(-2, 2)))

        result_color = (
            "🟢" if result == 0 else ("🔴" if result in ROULETTE_RED else "⚫")
        )

        embed = discord.Embed(title="🎡 Starwheel Roulette", color=discord.Color.purple())
        embed.description = f"Spinning the cosmic wheel... {ROULETTE_SPIN_FRAMES[0]}"
        msg = await ctx.send(embed=embed)
        for frame in ROULETTE_SPIN_FRAMES[1:]:
            await asyncio.sleep(0.6)
            embed.description = f"Spinning the cosmic wheel... {frame}"
            await msg.edit(embed=embed)
        await asyncio.sleep(0.8)

        if bet_type == "red":
            won, multiplier = result in ROULETTE_RED, 1.9
        elif bet_type == "black":
            won, multiplier = result in ROULETTE_BLACK, 1.9
        elif bet_type == "odd":
            won, multiplier = result != 0 and result % 2 == 1, 1.9
        elif bet_type == "even":
            won, multiplier = result != 0 and result % 2 == 0, 1.9
        else:
            won, multiplier = result == int(bet_type), 35.0

        result_line = f"The wheel landed on **{result_color} {result}**!"
        if won:
            winnings = int(bet * multiplier)
            await update_chips(ctx.author.id, winnings)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_earnt", winnings - bet)
                await record_user_game(ctx.author.id, "roulette", bet, earnt=winnings - bet, biggest_win=winnings - bet)
            embed.color = discord.Color.green()
            embed.description = (
                f"{result_line}\n\n🎉 **You win {winnings:,} Chips!** ({multiplier}×)"
            )
        else:
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_lost", bet)
                await record_user_game(ctx.author.id, "roulette", bet, lost=bet)
            embed.color = discord.Color.red()
            embed.description = f"{result_line}\n\n❌ **You lost {bet:,} Chips.**"

        embed.set_footer(text=f"Bet: {bet_input} · {bet:,} Chips wagered")
        await msg.edit(embed=embed)

    # ── My Stats ──────────────────────────────────────────────────────────────
    @commands.command(name="me")
    async def me(self, ctx, user: discord.Member = None):
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
            "hilo":      "🃏 Higher/Lower",
            "warp":      "🚀 Warp",
            "roulette":  "🎡 Roulette",
        }

        total_played = total_wagered = total_earnt = total_lost = total_best = 0
        fields = []
        for game_key in ("coinflip", "slots", "blackjack", "hilo", "warp", "roulette"):
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
        else:
            print(f"Gambling Error: {error}")


async def setup(bot):
    await bot.add_cog(Gamble(bot))
