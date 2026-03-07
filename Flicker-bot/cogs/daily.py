import discord
import time
import random
from discord.ext import commands
from database import (
    get_balance, update_balance, get_server_settings,
    get_user_social, update_daily, update_rep_cooldown,
    unlock_achievement, ACHIEVEMENTS,
)


def fmt_cooldown(remaining_secs: float) -> tuple[int, int]:
    h = int(remaining_secs // 3600)
    m = int((remaining_secs % 3600) // 60)
    return h, m


async def check_balance_achievements(user_id: int, guild_id: int) -> list[str]:
    """Check and unlock balance-based achievements. Returns list of newly unlocked keys."""
    from database import get_balance, get_chips
    unlocked = []
    balance = await get_balance(user_id, guild_id)
    chips = await get_chips(user_id, guild_id)
    if balance > 0 and await unlock_achievement(user_id, guild_id, "first_stardust"):
        unlocked.append("first_stardust")
    if balance >= 1000 and await unlock_achievement(user_id, guild_id, "rich_1000"):
        unlocked.append("rich_1000")
    if balance >= 10000 and await unlock_achievement(user_id, guild_id, "rich_10000"):
        unlocked.append("rich_10000")
    if chips >= 10000 and await unlock_achievement(user_id, guild_id, "chips_10000"):
        unlocked.append("chips_10000")
    return unlocked


def achievement_msg(keys: list) -> str:
    if not keys:
        return ""
    parts = [f"{ACHIEVEMENTS[k]['icon']} **{ACHIEVEMENTS[k]['name']}**" for k in keys if k in ACHIEVEMENTS]
    return "\n🏆 Achievement unlocked: " + ", ".join(parts) if parts else ""


class Daily(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── !daily ────────────────────────────────────────────────────────────────

    @commands.command(name="daily")
    async def daily(self, ctx):
        """Claim your daily Stardust reward. Streak bonuses apply!"""
        settings = await get_server_settings(ctx.guild.id)
        if not settings["command_toggles"].get("daily", True):
            return await ctx.send("❌ Daily rewards are disabled in this server.")

        po = settings["payout_overrides"]
        to = settings["text_overrides"]
        social = await get_user_social(ctx.author.id, ctx.guild.id)
        now = time.time()

        cooldown_secs = po.get("daily_cooldown_hours", 22) * 3600
        elapsed = now - social["last_daily"]

        if elapsed < cooldown_secs:
            remaining = cooldown_secs - elapsed
            h, m = fmt_cooldown(remaining)
            return await ctx.send(to.get("daily_cooldown", "⏰ You already claimed your daily! Come back in **{hours}h {mins}m**.").format(hours=h, mins=m))

        # Determine streak: if more than (cooldown + 26h) has passed, reset
        streak = social["daily_streak"]
        streak_reset = elapsed > cooldown_secs + (26 * 3600)
        if streak_reset:
            streak = 0
        streak += 1

        base_min = int(po.get("daily_base_min", 20))
        base_max = int(po.get("daily_base_max", 50))
        streak_bonus_per = int(po.get("daily_streak_bonus", 5))
        streak_max = int(po.get("daily_streak_max", 30))
        bonus = min(streak - 1, streak_max) * streak_bonus_per
        reward = random.randint(base_min, base_max) + bonus

        await update_balance(ctx.author.id, ctx.guild.id, reward)
        await update_daily(ctx.author.id, ctx.guild.id, streak, now)

        # Achievements
        ach = await check_balance_achievements(ctx.author.id, ctx.guild.id)
        if streak >= 3:
            if await unlock_achievement(ctx.author.id, ctx.guild.id, "daily_3"):
                ach.append("daily_3")
        if streak >= 7:
            if await unlock_achievement(ctx.author.id, ctx.guild.id, "daily_7"):
                ach.append("daily_7")
        if streak >= 30:
            if await unlock_achievement(ctx.author.id, ctx.guild.id, "daily_30"):
                ach.append("daily_30")

        key = "daily_streak_lost" if streak_reset else "daily_claim"
        msg = to.get(key, "✅ **Daily claimed!** You received **{reward} Stardust**. (Streak: {streak} 🔥)").format(
            reward=f"{reward:,}", streak=streak
        )
        await ctx.send(msg + achievement_msg(ach))

    # ── !rob ──────────────────────────────────────────────────────────────────

    @commands.command(name="rob")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def rob(self, ctx, target: discord.Member):
        """Attempt to steal Stardust from another user. Risk and reward."""
        settings = await get_server_settings(ctx.guild.id)
        if not settings["command_toggles"].get("rob", True):
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("❌ Rob is disabled in this server.")

        po = settings["payout_overrides"]
        to = settings["text_overrides"]

        if target.id == ctx.author.id:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("❌ You can't rob yourself.")
        if target.bot:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("❌ Bots don't carry Stardust.")

        victim_balance = await get_balance(target.id, ctx.guild.id)
        min_balance = int(po.get("rob_min_victim_balance", 50))
        if victim_balance < min_balance:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(to.get("rob_poor", "💸 {victim} doesn't have enough Stardust to rob.").format(victim=target.display_name))

        success_chance = po.get("rob_success_chance", 0.40)
        if random.random() < success_chance:
            # Success
            steal_pct = random.uniform(po.get("rob_steal_min_pct", 0.10), po.get("rob_steal_max_pct", 0.30))
            amount = max(1, int(victim_balance * steal_pct))
            await update_balance(target.id, ctx.guild.id, -amount)
            await update_balance(ctx.author.id, ctx.guild.id, amount)

            ach = await check_balance_achievements(ctx.author.id, ctx.guild.id)
            if await unlock_achievement(ctx.author.id, ctx.guild.id, "robber"):
                ach.append("robber")
            await unlock_achievement(target.id, ctx.guild.id, "robbed")

            msg = to.get("rob_success", "🦝 You snuck **{amount} Stardust** from {victim}!").format(
                amount=f"{amount:,}", victim=target.display_name
            )
            await ctx.send(msg + achievement_msg(ach))
        else:
            # Caught — pay a fine
            robber_balance = await get_balance(ctx.author.id, ctx.guild.id)
            fine_pct = po.get("rob_fine_pct", 0.15)
            fine = max(1, int(robber_balance * fine_pct))
            await update_balance(ctx.author.id, ctx.guild.id, -fine)
            await update_balance(target.id, ctx.guild.id, fine)
            msg = to.get("rob_caught", "🚔 You were caught robbing {victim} and fined **{fine} Stardust**!").format(
                victim=target.display_name, fine=f"{fine:,}"
            )
            await ctx.send(msg)

    @rob.error
    async def rob_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ You need to specify a target. Usage: `!rob @user`")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ User not found.")


async def setup(bot):
    await bot.add_cog(Daily(bot))
