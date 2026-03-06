import discord
from discord.ext import commands
import aiosqlite
import database
from database import (
    add_allowed_channel,
    remove_allowed_channel,
    get_allowed_channels,
    reset_chip_stats,
    get_all_stats,
    record_user_game,
    get_user_game_stats,
)


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return (
            await self.bot.is_owner(ctx.author)
            or ctx.author.guild_permissions.administrator
        )

    @commands.command(name="trackC")
    async def track_channels(self, ctx, *channels: discord.TextChannel):
        """Adds one or more channels to the allowlist. Usage: !trackC #general #games"""
        if not channels:
            channels = [ctx.channel]

        added_count = 0
        for channel in channels:
            await add_allowed_channel(channel.id)
            added_count += 1

        await ctx.send(
            f"✅ **Configuration Updated:** Flicker is now active in {added_count} channel(s)."
        )

    @commands.command(name="RmC")
    async def remove_channels(self, ctx, *channels: discord.TextChannel):
        """Removes one or more channels. Usage: !RmC #general"""
        if not channels:
            channels = [ctx.channel]

        removed_count = 0
        for channel in channels:
            await remove_allowed_channel(channel.id)
            removed_count += 1

        await ctx.send(
            f"🚫 **Configuration Updated:** Flicker has stopped tracking {removed_count} channel(s)."
        )

    @commands.command(name="ListC")
    async def list_channels(self, ctx):
        """Lists all channels where Flicker is active."""
        allowed_ids = await get_allowed_channels()

        if not allowed_ids:
            await ctx.send("❌ Flicker is currently **inactive** in all channels.")
            return

        mentions = [f"<#{cid}>" for cid in allowed_ids]
        channel_list = "\n".join(mentions)

        embed = discord.Embed(
            title="📡 Active Frequencies",
            description=f"Flicker will drop games in the following channels:\n\n{channel_list}",
            color=discord.Color.blue(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="resetgamblestats")
    async def reset_gamble_stats(self, ctx):
        """Resets chips_wagered, chips_earnt, and chips_lost to 0. Does not touch user balances."""
        stats_before = await get_all_stats()
        wagered = stats_before.get("chips_wagered", 0)
        earnt = stats_before.get("chips_earnt", 0)
        lost = stats_before.get("chips_lost", 0)

        await reset_chip_stats()

        embed = discord.Embed(
            title="🗑️ Gambling Stats Reset",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="chips_wagered", value=f"~~{wagered:,}~~ → 0", inline=False
        )
        embed.add_field(name="chips_earnt", value=f"~~{earnt:,}~~ → 0", inline=False)
        embed.add_field(name="chips_lost", value=f"~~{lost:,}~~ → 0", inline=False)
        embed.set_footer(text="User Stardust and Chips balances were not affected.")
        await ctx.send(embed=embed)

    @commands.command(name="migrateeconomy")
    async def migrate_economy(self, ctx):
        """One-time migration: merges old global balances into this server's economy."""
        import aiosqlite
        async with aiosqlite.connect(database.DB_NAME) as db:
            # Tracking table so re-runs never double-count anyone
            await db.execute("""
                CREATE TABLE IF NOT EXISTS economy_migration_log (
                    user_id  INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)

            # Fetch old rows not yet migrated for this guild
            async with db.execute("""
                SELECT u.user_id, u.balance, u.chips,
                       COALESCE(u.pet_streak, 0), COALESCE(u.last_pet_time, 0)
                FROM users u
                WHERE (u.balance > 0 OR u.chips > 0)
                  AND NOT EXISTS (
                      SELECT 1 FROM economy_migration_log m
                      WHERE m.user_id = u.user_id AND m.guild_id = ?
                  )
            """, (ctx.guild.id,)) as cur:
                rows = await cur.fetchall()

            if not rows:
                return await ctx.send("ℹ️ Nothing left to migrate — all users are already up to date.")

            # For each user: ADD their old balance/chips onto whatever they may already have
            # (handles users who earned currency in the window between deploy and migration)
            for user_id, balance, chips, pet_streak, last_pet_time in rows:
                await db.execute("""
                    INSERT INTO user_balances (user_id, guild_id, balance, chips, pet_streak, last_pet_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, guild_id) DO UPDATE SET
                        balance      = user_balances.balance      + excluded.balance,
                        chips        = user_balances.chips        + excluded.chips,
                        pet_streak   = MAX(user_balances.pet_streak,   excluded.pet_streak),
                        last_pet_time = MAX(user_balances.last_pet_time, excluded.last_pet_time)
                """, (user_id, ctx.guild.id, balance, chips, pet_streak, last_pet_time))
                await db.execute(
                    "INSERT OR IGNORE INTO economy_migration_log (user_id, guild_id) VALUES (?, ?)",
                    (user_id, ctx.guild.id)
                )

            await db.commit()

        await ctx.send(
            f"✅ Migration complete! **{len(rows)}** user records merged into this server's economy. "
            f"Users who earned currency recently had their old balance added on top."
        )

    @commands.command(name="dbcheck")
    async def dbcheck(self, ctx):
        """Debug: test whether user_game_stats table works end-to-end."""
        lines = []
        lines.append(f"DB path: `{database.DB_NAME}`")

        try:
            async with aiosqlite.connect(database.DB_NAME) as db:
                async with db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='user_game_stats'"
                ) as cur:
                    row = await cur.fetchone()
            lines.append(f"Table exists: `{bool(row)}`")
        except Exception as e:
            lines.append(f"Table check error: `{e}`")

        try:
            async with aiosqlite.connect(database.DB_NAME) as db:
                async with db.execute("SELECT COUNT(*) FROM user_game_stats") as cur:
                    row = await cur.fetchone()
            lines.append(f"Total rows in table: `{row[0]}`")
        except Exception as e:
            lines.append(f"Row count error: `{e}`")

        try:
            await record_user_game(ctx.author.id, "_test_", 1)
            lines.append("Write test row: ✅ succeeded")
        except Exception as e:
            lines.append(f"Write test row error: `{e}`")

        try:
            stats = await get_user_game_stats(ctx.author.id)
            lines.append(f"Read back stats keys: `{list(stats.keys())}`")
        except Exception as e:
            lines.append(f"Read back error: `{e}`")

        try:
            async with aiosqlite.connect(database.DB_NAME) as db:
                await db.execute(
                    "DELETE FROM user_game_stats WHERE user_id = ? AND game = '_test_'",
                    (ctx.author.id,),
                )
                await db.commit()
            lines.append("Cleanup: ✅")
        except Exception as e:
            lines.append(f"Cleanup error: `{e}`")

        await ctx.send("\n".join(lines))


async def setup(bot):
    await bot.add_cog(Admin(bot))
