import discord
import time
from discord.ext import commands
from database import (
    get_balance, get_chips, get_server_settings,
    get_user_social, add_rep, update_rep_cooldown,
    get_achievements, unlock_achievement, get_user_game_stats,
    ACHIEVEMENTS,
)


def fmt_cooldown(remaining: float) -> tuple[int, int]:
    h = int(remaining // 3600)
    m = int((remaining % 3600) // 60)
    return h, m


class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── !profile ──────────────────────────────────────────────────────────────

    @commands.command(name="profile", aliases=["card"])
    async def profile(self, ctx, member: discord.Member = None):
        """View your profile or another member's profile."""
        settings = await get_server_settings(ctx.guild.id)
        if not settings["command_toggles"].get("profile", True):
            return await ctx.send("❌ Profile is disabled in this server.")

        target = member or ctx.author

        balance = await get_balance(target.id, ctx.guild.id)
        chips = await get_chips(target.id, ctx.guild.id)
        social = await get_user_social(target.id, ctx.guild.id)
        unlocked = await get_achievements(target.id, ctx.guild.id)
        game_stats = await get_user_game_stats(target.id)

        # Economy summary
        total_wagered = sum(v[1] for v in game_stats.values())
        total_played = sum(v[0] for v in game_stats.values())
        biggest_win = max((v[4] for v in game_stats.values()), default=0)

        embed = discord.Embed(
            title=f"⚡ {target.display_name}",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(name="✨ Stardust",     value=f"{balance:,}",                     inline=True)
        embed.add_field(name="🎰 Chips",        value=f"{chips:,}",                       inline=True)
        embed.add_field(name="❤️ Reputation",   value=str(social["rep_count"]),           inline=True)
        embed.add_field(name="🔥 Daily Streak", value=f"{social['daily_streak']} days",   inline=True)
        embed.add_field(name="🎲 Games Played", value=str(total_played),                  inline=True)

        if total_played:
            embed.add_field(name="💸 Total Wagered",  value=f"{total_wagered:,} Chips",   inline=True)
            embed.add_field(name="🏆 Biggest Win",    value=f"{biggest_win:,} Chips",     inline=True)

        if unlocked:
            icons = " ".join(ACHIEVEMENTS[k]["icon"] for k in unlocked if k in ACHIEVEMENTS)
            names = ", ".join(f"**{ACHIEVEMENTS[k]['name']}**" for k in unlocked if k in ACHIEVEMENTS)
            embed.add_field(
                name=f"🏅 Achievements ({len(unlocked)}/{len(ACHIEVEMENTS)})",
                value=f"{icons}\n{names}" if icons else "—",
                inline=False,
            )
        else:
            embed.add_field(name="🏅 Achievements", value="None yet — keep playing!", inline=False)

        await ctx.send(embed=embed)

    # ── !rep ──────────────────────────────────────────────────────────────────

    @commands.command(name="rep", aliases=["reputation"])
    async def rep(self, ctx, member: discord.Member = None):
        """Give a daily reputation point to another member."""
        settings = await get_server_settings(ctx.guild.id)
        if not settings["command_toggles"].get("rep", True):
            return await ctx.send("❌ Rep is disabled in this server.")

        to = settings["text_overrides"]

        if member is None:
            return await ctx.send("❌ Mention a user to give them rep. Usage: `!rep @user`")
        if member.id == ctx.author.id:
            return await ctx.send(to.get("rep_self", "❌ You can't give reputation to yourself."))
        if member.bot:
            return await ctx.send("❌ Bots don't accept reputation.")

        social = await get_user_social(ctx.author.id, ctx.guild.id)
        now = time.time()
        cooldown_secs = 22 * 3600

        if now - social["last_rep_given"] < cooldown_secs:
            remaining = cooldown_secs - (now - social["last_rep_given"])
            h, m = fmt_cooldown(remaining)
            return await ctx.send(
                to.get("rep_cooldown", "❤️ You already gave rep today. Come back in **{hours}h {mins}m**.").format(hours=h, mins=m)
            )

        new_total = await add_rep(member.id, ctx.guild.id)
        await update_rep_cooldown(ctx.author.id, ctx.guild.id, now)

        # Achievement for receiver
        if new_total >= 5:
            await unlock_achievement(member.id, ctx.guild.id, "well_loved")

        msg = to.get("rep_given", "❤️ You gave a reputation point to **{user}**! They now have **{total}** rep.").format(
            user=member.display_name, total=new_total
        )
        await ctx.send(msg)

    @rep.error
    async def rep_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ User not found.")


async def setup(bot):
    await bot.add_cog(Profile(bot))
