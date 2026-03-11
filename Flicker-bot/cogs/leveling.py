import math
import random
import time
import discord
from discord.ext import commands
from database import (
    get_user_xp,
    set_user_xp,
    get_xp_leaderboard,
    get_server_settings,
    update_balance,
    update_chips,
)


def xp_for_level(level: int, xp_per_level: int = 100) -> int:
    """Total XP required to have reached exactly this level from 0.
    Formula: xp_per_level * level * (level + 1) / 2
    (cost to go from level n→n+1 is xp_per_level*(n+1))
    """
    return xp_per_level * level * (level + 1) // 2


def level_from_xp(total_xp: int, xp_per_level: int = 100) -> int:
    """Compute the floor level given total XP accumulated."""
    if xp_per_level <= 0 or total_xp <= 0:
        return 0
    discriminant = 1 + 8 * total_xp / xp_per_level
    return int((-1 + math.sqrt(discriminant)) / 2)


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # In-memory cooldown: (user_id, guild_id) -> last XP award timestamp
        self._xp_cooldowns: dict = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        settings = await get_server_settings(message.guild.id)
        lc = settings.get("leveling_config", {})
        if not lc.get("enabled", False):
            return

        user_id = message.author.id
        guild_id = message.guild.id
        key = (user_id, guild_id)

        # XP cooldown
        cooldown = lc.get("xp_cooldown_seconds", 60)
        now = time.time()
        if now - self._xp_cooldowns.get(key, 0) < cooldown:
            return
        self._xp_cooldowns[key] = now

        # Award XP
        xp_min = max(1, lc.get("xp_per_message_min", 5))
        xp_max = max(xp_min, lc.get("xp_per_message_max", 15))
        xp_gained = random.randint(xp_min, xp_max)

        old_xp, old_level = await get_user_xp(user_id, guild_id)
        new_xp = old_xp + xp_gained
        xp_per_level = max(1, lc.get("xp_per_level", 100))
        new_level = level_from_xp(new_xp, xp_per_level)

        await set_user_xp(user_id, guild_id, new_xp, new_level)

        if new_level > old_level:
            await self._handle_levelup(message, lc, new_level, old_level)

    async def _handle_levelup(
        self,
        message: discord.Message,
        lc: dict,
        new_level: int,
        old_level: int,
    ):
        guild = message.guild
        member = message.author

        # Apply any milestones crossed
        for milestone in lc.get("milestones", []):
            m_level = milestone.get("level", 0)
            if old_level < m_level <= new_level:
                await self._apply_milestone(guild, member, milestone)

        if not lc.get("announce_levelup", True):
            return

        channel_id = lc.get("channel_id")
        channel = guild.get_channel(int(channel_id)) if channel_id else message.channel

        if not channel:
            return

        msg_template = lc.get("levelup_message", "🎉 {user} just reached **Level {level}**!")
        content = (
            msg_template
            .replace("{user}", member.mention)
            .replace("{level}", str(new_level))
        )
        try:
            await channel.send(content)
        except discord.Forbidden:
            pass

    async def _apply_milestone(self, guild: discord.Guild, member: discord.Member, milestone: dict):
        # Grant Discord role
        role_id = milestone.get("role_id")
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                try:
                    await member.add_roles(role, reason="Flicker level milestone")
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # Grant Stardust
        stardust = milestone.get("stardust", 0)
        if stardust:
            await update_balance(member.id, guild.id, stardust)

        # Grant Chips
        chips = milestone.get("chips", 0)
        if chips:
            await update_chips(member.id, guild.id, chips)

    @commands.command(name="rank", aliases=["level", "xp"])
    async def rank(self, ctx: commands.Context, member: discord.Member = None):
        """Show your current level and XP progress."""
        settings = await get_server_settings(ctx.guild.id)
        lc = settings.get("leveling_config", {})
        if not lc.get("enabled", False):
            await ctx.send("❌ Leveling is not enabled on this server.")
            return

        target = member or ctx.author
        total_xp, level = await get_user_xp(target.id, ctx.guild.id)
        xp_per_level = max(1, lc.get("xp_per_level", 100))

        current_level_xp = xp_for_level(level, xp_per_level)
        next_level_xp = xp_for_level(level + 1, xp_per_level)
        xp_into_level = total_xp - current_level_xp
        xp_needed = next_level_xp - current_level_xp

        progress = xp_into_level / xp_needed if xp_needed > 0 else 1.0
        bar_len = 20
        filled = int(progress * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        embed = discord.Embed(
            title=f"⭐ {target.display_name}",
            color=discord.Color.from_rgb(91, 142, 247),
        )
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="Total XP", value=f"{total_xp:,}", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(
            name=f"Progress to Level {level + 1}",
            value=f"`{bar}` {xp_into_level:,} / {xp_needed:,} XP",
            inline=False,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="xplb", aliases=["xpleaderboard", "levellb"])
    async def xp_leaderboard(self, ctx: commands.Context):
        """Show the XP leaderboard for this server."""
        settings = await get_server_settings(ctx.guild.id)
        lc = settings.get("leveling_config", {})
        if not lc.get("enabled", False):
            await ctx.send("❌ Leveling is not enabled on this server.")
            return

        rows = await get_xp_leaderboard(ctx.guild.id, limit=10)
        if not rows:
            await ctx.send("No one has earned XP yet!")
            return

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, xp, level) in enumerate(rows):
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else str(uid)
            prefix = medals[i] if i < 3 else f"**#{i + 1}**"
            lines.append(f"{prefix} **{name}** — Level {level} ({xp:,} XP)")

        embed = discord.Embed(
            title="⭐ XP Leaderboard",
            description="\n".join(lines),
            color=discord.Color.from_rgb(91, 142, 247),
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Leveling(bot))
