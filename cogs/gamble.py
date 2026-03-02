import discord
import random
import asyncio
import itertools
from discord.ext import commands
from database import get_chips, update_chips, increment_stat

# ── Animated emojis (existing) ───────────────────────────────────────────────
ANIM_COIN = "<a:coinflip:1474782979095007404>"
ANIM_SLOT = "<a:slot_gif:1474783068119240776>"

STATIC_HEADS = "🪙"
STATIC_TAILS = "🪙"

# ── Card helpers ─────────────────────────────────────────────────────────────
SUITS = ["✨", "🌙", "⭐", "💫"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def new_deck():
    return [f"{r}{s}" for r, s in itertools.product(RANKS, SUITS)]

def card_value(card: str) -> int:
    # Suits are single Unicode chars; rank is everything before the last char
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

# ── Roulette constants ────────────────────────────────────────────────────────
ROULETTE_RED = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
ROULETTE_BLACK = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}
ROULETTE_SPIN_FRAMES = ["🌀", "💫", "⭐", "🌟", "✨"]

# ── Higher-or-Lower multipliers ───────────────────────────────────────────────
HILO_MULTIPLIERS = [1.5, 2.0, 3.0, 5.0, 8.0]

# ── Blackjack View ────────────────────────────────────────────────────────────
class BlackjackView(discord.ui.View):
    def __init__(self, cog, ctx, bet: int, deck: list, player_hand: list, dealer_hand: list, track_stats: bool = True):
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
            dealer_display = f"{fmt_hand(self.dealer_hand)} ({hand_value(self.dealer_hand)})"
        else:
            dealer_display = f"{self.dealer_hand[0]}  🂠"
        embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.dark_gold())
        embed.add_field(name="Dealer", value=dealer_display, inline=False)
        embed.add_field(name=f"{self.ctx.author.display_name} ({pval})", value=fmt_hand(self.player_hand), inline=False)
        embed.set_footer(text=f"Bet: {self.bet:,} Chips")
        return embed

    async def resolve(self, interaction: discord.Interaction):
        for child in self.children:
            child.disabled = True

        # Dealer hits to soft 17; boss mode makes dealer bust more
        while hand_value(self.dealer_hand) < 17:
            if interaction.user.id == self.cog.boss_id and hand_value(self.dealer_hand) == 16 and random.random() < 0.30:
                break
            self.dealer_hand.append(self.deck.pop())

        pval = hand_value(self.player_hand)
        dval = hand_value(self.dealer_hand)

        if pval > 21:
            result, color, winnings = "💥 Bust! You lose.", discord.Color.red(), 0
        elif dval > 21 or pval > dval:
            result, color, winnings = "🎉 You win!", discord.Color.green(), self.bet * 2
        elif pval == dval:
            result, color, winnings = "🤝 Push — bet returned.", discord.Color.greyple(), self.bet
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

        embed = self.build_embed(reveal_dealer=True)
        embed.color = color
        extra = f"\n+**{winnings:,} Chips**" if winnings > self.bet else ""
        embed.description = f"**{result}**{extra}"
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green, emoji="👊")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        self.player_hand.append(self.deck.pop())
        if hand_value(self.player_hand) >= 21:
            await self.resolve(interaction)
        else:
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        await self.resolve(interaction)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.blurple, emoji="⚡")
    async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        chips = await get_chips(self.ctx.author.id)
        if chips < self.bet:
            return await interaction.response.send_message(
                f"❌ Not enough Chips to double! (Need {self.bet:,} more)", ephemeral=True
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
        # Refund bet on timeout
        await update_chips(self.ctx.author.id, self.bet)


# ── Higher or Lower View ──────────────────────────────────────────────────────
class HiloView(discord.ui.View):
    def __init__(self, cog, ctx, bet: int, deck: list, current_card: str, track_stats: bool = True):
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
        return HILO_MULTIPLIERS[min(self.streak, len(HILO_MULTIPLIERS) - 1)]

    def build_embed(self) -> discord.Embed:
        mult = self.multiplier()
        potential = int(self.bet * mult)
        embed = discord.Embed(title="🃏 Higher or Lower", color=discord.Color.teal())
        embed.add_field(name="Current Card", value=f"**{self.current_card}** ({card_value(self.current_card)})", inline=True)
        embed.add_field(name="Streak", value=f"{self.streak} correct", inline=True)
        embed.add_field(name="Cash Out Value", value=f"{potential:,} Chips ({mult}×)", inline=True)
        embed.set_footer(text=f"Bet: {self.bet:,} Chips — Is the next card higher or lower?")
        return embed

    async def _guess(self, interaction: discord.Interaction, guess: str):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)

        next_card = self.deck.pop()
        curr_val = card_value(self.current_card)
        next_val = card_value(next_card)

        if next_val == curr_val:
            self.current_card = next_card
            embed = self.build_embed()
            embed.description = f"🤝 **Tie!** Next card was also **{next_card}** ({next_val}). Keep going!"
            return await interaction.response.edit_message(embed=embed, view=self)

        correct = (guess == "higher" and next_val > curr_val) or \
                  (guess == "lower"  and next_val < curr_val)

        if correct:
            self.streak += 1
            self.current_card = next_card
            if self.streak >= 5 or not self.deck:
                await self._cash_out(interaction, auto=True)
            else:
                embed = self.build_embed()
                embed.description = f"✅ **Correct!** Next card was **{next_card}** ({next_val})."
                await interaction.response.edit_message(embed=embed, view=self)
        else:
            for child in self.children:
                child.disabled = True
            if self.track_stats:
                await increment_stat("chips_wagered", self.bet)
                await increment_stat("chips_lost", self.bet)
            embed = discord.Embed(
                title="🃏 Higher or Lower",
                description=f"❌ **Wrong!** Next card was **{next_card}** ({next_val}). You lost **{self.bet:,} Chips**.",
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()

    async def _cash_out(self, interaction: discord.Interaction, auto=False):
        for child in self.children:
            child.disabled = True
        payout = int(self.bet * self.multiplier())
        await update_chips(self.ctx.author.id, payout)
        if self.track_stats:
            await increment_stat("chips_wagered", self.bet)
            await increment_stat("chips_earnt", payout - self.bet)
        embed = discord.Embed(
            title="🃏 Higher or Lower",
            description=f"{'🏆 Max streak!' if auto else '💰 Cashed out!'} You won **{payout:,} Chips** ({self.multiplier()}×)!",
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
    async def cash_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        if self.streak == 0:
            return await interaction.response.send_message("❌ Make at least one correct guess first!", ephemeral=True)
        await self._cash_out(interaction)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass
        # Auto cash out if streak > 0, else refund bet
        if self.streak > 0:
            payout = int(self.bet * self.multiplier())
            await update_chips(self.ctx.author.id, payout)
            if self.track_stats:
                await increment_stat("chips_wagered", self.bet)
                await increment_stat("chips_earnt", payout - self.bet)
        else:
            await update_chips(self.ctx.author.id, self.bet)


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

    # ── Coinflip ──────────────────────────────────────────────────────────────
    @commands.command(name="coinflip", aliases=["cf"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def coinflip(self, ctx, amount: str, choice: str = "h"):
        """Gamble Chips on a coinflip! Default choice is heads."""
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            ctx.command.reset_cooldown(ctx)
            return

        chips = await get_chips(ctx.author.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"❌ You don't have enough Chips! (Balance: {chips:,})")

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

        win_chance = 0.70 if ctx.author.id == self.boss_id else 0.45
        result = user_guess if random.random() < win_chance else ("tails" if user_guess == "heads" else "heads")

        await asyncio.sleep(2.5)

        result_icon = STATIC_HEADS if result == "heads" else STATIC_TAILS
        if user_guess == result:
            winnings = bet * 2
            await update_chips(ctx.author.id, winnings)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_earnt", bet)
            embed.color = discord.Color.green()
            embed.description = f"**{ctx.author.display_name}** spent **{bet:,}** Chips and chose **{user_guess}**.\n\nIt landed on **{result}**! {result_icon}\n🎉 You won **{winnings:,}** Chips!"
        else:
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_lost", bet)
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
            ctx.command.reset_cooldown(ctx)
            return

        chips = await get_chips(ctx.author.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"❌ You don't have enough Chips! (Balance: {chips:,})")

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
                final_reels = [random.choice(self.slot_emojis) for _ in range(3)]
                if final_reels[0] == final_reels[1] == final_reels[2]:
                    final_reels[2] = "🍒" if final_reels[0] != "🍒" else "🍋"
                multiplier = 0
        else:
            if chance < 0.01:
                final_reels, multiplier = ["💎", "💎", "💎"], 10
            elif chance < 0.03:
                final_reels, multiplier = ["⭐", "⭐", "⭐"], 5
            elif chance < 0.10:
                e = random.choice(["🍋", "🍉"])
                final_reels, multiplier = [e, e, e], 3
            elif chance < 0.30:
                final_reels, multiplier = ["🍒", "🍒", "🍒"], 2
            else:
                final_reels = [random.choice(self.slot_emojis) for _ in range(3)]
                if final_reels[0] == final_reels[1] == final_reels[2]:
                    final_reels[2] = "🍒" if final_reels[0] != "🍒" else "🍋"
                multiplier = 0

        embed = discord.Embed(title="🎰 Cosmic Chip Slots 🎰", color=discord.Color.purple())
        embed.description = f"{ctx.author.mention} bet **{bet:,}** Chips...\n\n**[ {ANIM_SLOT} | {ANIM_SLOT} | {ANIM_SLOT} ]**"
        msg = await ctx.send(embed=embed)

        await asyncio.sleep(1.0)
        embed.description = f"{ctx.author.mention} bet **{bet:,}** Chips...\n\n**[ {final_reels[0]} | {ANIM_SLOT} | {ANIM_SLOT} ]**"
        await msg.edit(embed=embed)

        await asyncio.sleep(1.0)
        embed.description = f"{ctx.author.mention} bet **{bet:,}** Chips...\n\n**[ {final_reels[0]} | {final_reels[1]} | {ANIM_SLOT} ]**"
        await msg.edit(embed=embed)

        await asyncio.sleep(1.2)
        result_text = f"**[ {final_reels[0]} | {final_reels[1]} | {final_reels[2]} ]**\n\n"
        if multiplier > 0:
            winnings = bet * multiplier
            await update_chips(ctx.author.id, winnings)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_earnt", winnings - bet)
            embed.color = discord.Color.green()
            result_text += f"🎉 **WINNER!** 🎉\nYou won **{winnings:,}** Chips! ({multiplier}×)"
        else:
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_lost", bet)
            embed.color = discord.Color.red()
            result_text += "❌ **Lost!** ❌\nBetter luck next time."

        embed.description = f"{ctx.author.mention} bet **{bet:,}** Chips...\n\n{result_text}"
        await msg.edit(embed=embed)

    # ── Blackjack ─────────────────────────────────────────────────────────────
    @commands.command(name="blackjack", aliases=["bj"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def blackjack(self, ctx, amount: str):
        """Play Blackjack against the dealer using Chips!"""
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            ctx.command.reset_cooldown(ctx)
            return

        chips = await get_chips(ctx.author.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"❌ You don't have enough Chips! (Balance: {chips:,})")

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
            embed = discord.Embed(
                title="🃏 Blackjack — Natural 21!",
                description=f"**{fmt_hand(player_hand)}**\n\n🎉 **Blackjack! You win {payout:,} Chips!** (2.5×)",
                color=discord.Color.gold(),
            )
            return await ctx.send(embed=embed)

        view = BlackjackView(self, ctx, bet, deck, player_hand, dealer_hand, track_stats=(ctx.author.id != self.boss_id))
        msg = await ctx.send(embed=view.build_embed(), view=view)
        view.message = msg

    # ── Higher or Lower ───────────────────────────────────────────────────────
    @commands.command(name="hilo", aliases=["hl"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def hilo(self, ctx, amount: str):
        """Guess Higher or Lower for escalating Chip multipliers!"""
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            ctx.command.reset_cooldown(ctx)
            return

        chips = await get_chips(ctx.author.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"❌ You don't have enough Chips! (Balance: {chips:,})")

        await update_chips(ctx.author.id, -bet)

        deck = new_deck()
        random.shuffle(deck)
        current_card = deck.pop()

        view = HiloView(self, ctx, bet, deck, current_card, track_stats=(ctx.author.id != self.boss_id))
        msg = await ctx.send(embed=view.build_embed(), view=view)
        view.message = msg

    # ── Dice Duel ─────────────────────────────────────────────────────────────
    @commands.command(name="dice", aliases=["roll"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def dice_duel(self, ctx, amount: str):
        """Roll 2d6 against Flicker! Higher total wins 2× your Chips."""
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            ctx.command.reset_cooldown(ctx)
            return

        chips = await get_chips(ctx.author.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"❌ You don't have enough Chips! (Balance: {chips:,})")

        await update_chips(ctx.author.id, -bet)

        p1, p2 = random.randint(1, 6), random.randint(1, 6)
        player_total = p1 + p2

        f1, f2 = random.randint(1, 6), random.randint(1, 6)
        if ctx.author.id == self.boss_id:
            if f1 >= f2:
                f1 = min(f1, random.randint(1, 6))
            else:
                f2 = min(f2, random.randint(1, 6))
        flicker_total = f1 + f2

        embed = discord.Embed(title="🎲 Cosmic Dice Duel", color=discord.Color.blue())
        embed.description = f"**{ctx.author.display_name}** rolls their dice... 🎲🎲"
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(1.5)

        embed.description = (
            f"**{ctx.author.display_name}:** 🎲 {p1} + {p2} = **{player_total}**\n"
            f"**Flicker:** 🎲 {f1} + {f2} = **{flicker_total}**"
        )
        await msg.edit(embed=embed)
        await asyncio.sleep(1.0)

        if player_total > flicker_total:
            winnings = bet * 2
            await update_chips(ctx.author.id, winnings)
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_earnt", bet)
            embed.color = discord.Color.green()
            embed.description += f"\n\n🎉 **You win {winnings:,} Chips!**"
        elif player_total == flicker_total:
            await update_chips(ctx.author.id, bet)
            embed.color = discord.Color.greyple()
            embed.description += "\n\n🤝 **Tie! Bet refunded.**"
        else:
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_lost", bet)
            embed.color = discord.Color.red()
            embed.description += "\n\n❌ **Flicker wins. Better luck next time.**"

        await msg.edit(embed=embed)

    # ── Roulette ──────────────────────────────────────────────────────────────
    @commands.command(name="roulette", aliases=["rt"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def roulette(self, ctx, amount: str, *, bet_input: str):
        """Bet on the Starwheel! Usage: !roulette <chips> <red|black|odd|even|0-36>"""
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1:
            ctx.command.reset_cooldown(ctx)
            return

        chips = await get_chips(ctx.author.id)
        if chips < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"❌ You don't have enough Chips! (Balance: {chips:,})")

        bet_type = bet_input.strip().lower()
        valid_types = {"red", "black", "odd", "even"} | {str(n) for n in range(37)}
        if bet_type not in valid_types:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("❌ Bet must be `red`, `black`, `odd`, `even`, or a number 0–36.")

        await update_chips(ctx.author.id, -bet)

        result = random.randint(0, 36)
        if ctx.author.id == self.boss_id and bet_type.isdigit():
            target = int(bet_type)
            if random.random() < 0.40:
                result = max(0, min(36, target + random.randint(-2, 2)))

        result_color = "🟢" if result == 0 else ("🔴" if result in ROULETTE_RED else "⚫")

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
            embed.color = discord.Color.green()
            embed.description = f"{result_line}\n\n🎉 **You win {winnings:,} Chips!** ({multiplier}×)"
        else:
            if ctx.author.id != self.boss_id:
                await increment_stat("chips_wagered", bet)
                await increment_stat("chips_lost", bet)
            embed.color = discord.Color.red()
            embed.description = f"{result_line}\n\n❌ **You lost {bet:,} Chips.**"

        embed.set_footer(text=f"Bet: {bet_input} · {bet:,} Chips wagered")
        await msg.edit(embed=embed)

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
