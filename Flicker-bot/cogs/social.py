import discord
import asyncio
import random
import time
import re
from discord.ext import commands
from database import (
    get_balance, update_balance, get_chips, update_chips,
    get_server_settings,
    create_giveaway, set_giveaway_message, enter_giveaway,
    get_giveaway_entries, end_giveaway, get_active_giveaways,
    create_poll, end_poll,
)

POLL_EMOJIS = ["🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭"]


def parse_duration(s: str) -> int | None:
    """Parse a duration string like '10m', '2h', '1d'. Returns seconds or None."""
    m = re.fullmatch(r"(\d+)(s|m|h|d)", s.strip().lower())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def fmt_duration(secs: int) -> str:
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    if secs < 86400:
        return f"{secs // 3600}h {(secs % 3600) // 60}m"
    return f"{secs // 86400}d {(secs % 86400) // 3600}h"


# ── Giveaway View ─────────────────────────────────────────────────────────────

class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id: int, entry_cost: int, entry_currency: str, guild_id: int):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.entry_cost = entry_cost
        self.entry_currency = entry_currency
        self.guild_id = guild_id
        self.enter_btn.custom_id = f"gv_{giveaway_id}"

    @discord.ui.button(label="🎉 Enter", style=discord.ButtonStyle.green, custom_id="gv_placeholder")
    async def enter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.entry_cost > 0:
            currency = self.entry_currency
            if currency == "chips":
                bal = await get_chips(interaction.user.id, self.guild_id)
                if bal < self.entry_cost:
                    return await interaction.response.send_message(
                        f"❌ You need **{self.entry_cost:,} Chips** to enter.", ephemeral=True
                    )
                await update_chips(interaction.user.id, self.guild_id, -self.entry_cost)
            else:
                bal = await get_balance(interaction.user.id, self.guild_id)
                if bal < self.entry_cost:
                    return await interaction.response.send_message(
                        f"❌ You need **{self.entry_cost:,} Stardust** to enter.", ephemeral=True
                    )
                await update_balance(interaction.user.id, self.guild_id, -self.entry_cost)

        entered = await enter_giveaway(self.giveaway_id, interaction.user.id)
        if not entered:
            return await interaction.response.send_message("✅ You're already entered!", ephemeral=True)

        await interaction.response.send_message("🎉 You've been entered into the giveaway!", ephemeral=True)


class Social(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Re-register active giveaway views and restart tasks on startup."""
        active = await get_active_giveaways()
        for gaw in active:
            view = GiveawayView(gaw["id"], gaw["entry_cost"], gaw["entry_currency"], gaw["guild_id"])
            self.bot.add_view(view)
            now = time.time()
            if now >= gaw["end_time"]:
                asyncio.create_task(self._end_giveaway(gaw))
            else:
                asyncio.create_task(self._giveaway_task(gaw))

    # ── !giveaway ─────────────────────────────────────────────────────────────

    @commands.command(name="giveaway", aliases=["gaw"])
    @commands.has_permissions(manage_guild=True)
    async def giveaway(self, ctx, duration: str, winners: str = "1", *, prize: str = None):
        """Start a giveaway. Usage: !giveaway <duration> [winners] [entry_cost:stardust/chips] <prize>
        Examples: !giveaway 1h 1 500:stardust Free Chips
                  !giveaway 30m 3 A Cool Prize"""
        settings = await get_server_settings(ctx.guild.id)
        if not settings["command_toggles"].get("giveaway", True):
            return await ctx.send("❌ Giveaways are disabled in this server.")

        secs = parse_duration(duration)
        if not secs or secs < 30 or secs > 7 * 86400:
            return await ctx.send("❌ Invalid duration. Use e.g. `30m`, `2h`, `1d`. Max 7 days.")

        # Parse winners count
        try:
            winner_count = max(1, min(int(winners), 20))
        except ValueError:
            # winners might actually be the prize if it's not a number
            prize = f"{winners} {prize or ''}".strip()
            winner_count = 1

        # Parse optional entry cost from prize: "500:stardust My Prize"
        entry_cost = 0
        entry_currency = "stardust"
        if prize and re.match(r"^\d+:(stardust|chips)\s", prize):
            parts = prize.split(None, 1)
            cost_str, entry_currency = parts[0].split(":")
            entry_cost = int(cost_str)
            prize = parts[1] if len(parts) > 1 else "Mystery Prize"

        if not prize:
            prize = "Mystery Prize"

        end_time = time.time() + secs
        giveaway_id = await create_giveaway(
            ctx.guild.id, ctx.channel.id, prize, end_time,
            winner_count, entry_cost, entry_currency, ctx.author.id,
        )

        gaw_data = {
            "id": giveaway_id, "guild_id": ctx.guild.id, "channel_id": ctx.channel.id,
            "message_id": None, "prize_desc": prize, "end_time": end_time,
            "winner_count": winner_count, "entry_cost": entry_cost,
            "entry_currency": entry_currency, "creator_id": ctx.author.id,
        }

        view = GiveawayView(giveaway_id, entry_cost, entry_currency, ctx.guild.id)
        embed = self._giveaway_embed(gaw_data, ended=False)
        msg = await ctx.send(embed=embed, view=view)
        await set_giveaway_message(giveaway_id, msg.id)
        self.bot.add_view(view)
        asyncio.create_task(self._giveaway_task(gaw_data, message=msg))

    def _giveaway_embed(self, gaw: dict, ended: bool = False, winners: list = None) -> discord.Embed:
        color = discord.Color.gold() if not ended else discord.Color.greyple()
        embed = discord.Embed(
            title=f"🎉 GIVEAWAY — {gaw['prize_desc']}",
            color=color,
        )
        embed.add_field(name="Winners", value=str(gaw["winner_count"]), inline=True)
        if gaw["entry_cost"] > 0:
            currency_label = "Stardust" if gaw["entry_currency"] == "stardust" else "Chips"
            embed.add_field(name="Entry Cost", value=f"{gaw['entry_cost']:,} {currency_label}", inline=True)
        if not ended:
            time_left = max(0, gaw["end_time"] - time.time())
            embed.add_field(name="Ends In", value=fmt_duration(int(time_left)), inline=True)
            embed.set_footer(text="Click 🎉 Enter to participate!")
        else:
            if winners:
                embed.add_field(
                    name="🏆 Winners",
                    value="\n".join(f"<@{uid}>" for uid in winners),
                    inline=False,
                )
            else:
                embed.add_field(name="Result", value="No entries.", inline=False)
            embed.set_footer(text="Giveaway ended.")
        return embed

    async def _giveaway_task(self, gaw: dict, message: discord.Message = None):
        now = time.time()
        delay = max(0, gaw["end_time"] - now)
        await asyncio.sleep(delay)
        await self._end_giveaway(gaw, message=message)

    async def _end_giveaway(self, gaw: dict, message: discord.Message = None):
        await end_giveaway(gaw["id"])
        entries = await get_giveaway_entries(gaw["id"])
        winners = random.sample(entries, min(gaw["winner_count"], len(entries))) if entries else []

        channel = self.bot.get_channel(gaw["channel_id"])
        if not channel:
            return

        # Try to edit the original giveaway message
        if message is None and gaw.get("message_id"):
            try:
                message = await channel.fetch_message(gaw["message_id"])
            except Exception:
                message = None

        ended_embed = self._giveaway_embed(gaw, ended=True, winners=winners)

        if message:
            try:
                await message.edit(embed=ended_embed, view=None)
            except Exception:
                pass

        if winners:
            mentions = " ".join(f"<@{uid}>" for uid in winners)
            await channel.send(f"🎉 Congratulations {mentions}! You won **{gaw['prize_desc']}**!")
        else:
            await channel.send(f"😔 The giveaway for **{gaw['prize_desc']}** ended with no entries.")

    @giveaway.error
    async def giveaway_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need Manage Server permission to start a giveaway.")

    # ── !poll ─────────────────────────────────────────────────────────────────

    @commands.command(name="poll")
    async def poll(self, ctx, duration: str, *, rest: str):
        """Create a timed poll. Usage: !poll <duration> <question> | <opt1> | <opt2> [| opt3...]"""
        settings = await get_server_settings(ctx.guild.id)
        if not settings["command_toggles"].get("poll", True):
            return await ctx.send("❌ Polls are disabled in this server.")

        secs = parse_duration(duration)
        if not secs or secs < 30 or secs > 7 * 86400:
            return await ctx.send("❌ Invalid duration. Use e.g. `5m`, `2h`.")

        parts = [p.strip() for p in rest.split("|")]
        if len(parts) < 3:
            return await ctx.send("❌ Provide a question and at least 2 options separated by `|`.\nUsage: `!poll 10m Question | Option A | Option B`")
        if len(parts) > 9:
            return await ctx.send("❌ Maximum 8 options.")

        question = parts[0]
        options = parts[1:]

        desc = "\n".join(f"{POLL_EMOJIS[i]} {opt}" for i, opt in enumerate(options))
        embed = discord.Embed(
            title=f"📊 {question}",
            description=desc,
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Poll · Ends in {fmt_duration(secs)} · React to vote!")

        msg = await ctx.send(embed=embed)
        for i in range(len(options)):
            await msg.add_reaction(POLL_EMOJIS[i])

        poll_id = await create_poll(ctx.guild.id, ctx.channel.id, msg.id, question, options)
        asyncio.create_task(self._close_poll(poll_id, msg, question, options, secs))

    async def _close_poll(self, poll_id: int, message: discord.Message, question: str, options: list, secs: int):
        await asyncio.sleep(secs)
        await end_poll(poll_id)

        try:
            message = await message.channel.fetch_message(message.id)
        except Exception:
            return

        counts = []
        for i, opt in enumerate(options):
            reaction = discord.utils.get(message.reactions, emoji=POLL_EMOJIS[i])
            counts.append((opt, (reaction.count - 1) if reaction else 0))

        total = sum(c for _, c in counts)
        results = []
        for opt, c in sorted(counts, key=lambda x: x[1], reverse=True):
            pct = int(c / total * 100) if total else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            results.append(f"`{bar}` {pct}% — {opt} ({c})")

        embed = discord.Embed(
            title=f"📊 {question} — Results",
            description="\n".join(results) if results else "No votes.",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Poll closed · {total} total vote(s)")

        try:
            await message.edit(embed=embed)
            await message.clear_reactions()
        except Exception:
            pass

    @poll.error
    async def poll_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!poll <duration> <question> | <option1> | <option2>`")


async def setup(bot):
    await bot.add_cog(Social(bot))
