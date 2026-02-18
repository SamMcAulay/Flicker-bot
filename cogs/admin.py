import discord
from discord.ext import commands
from database import add_allowed_channel, remove_allowed_channel, get_allowed_channels

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author) or ctx.author.guild_permissions.administrator

    @commands.command(name="trackC")
    async def track_channels(self, ctx, *channels: discord.TextChannel):
        """Adds one or more channels to the allowlist. Usage: !trackC #general #games"""
        if not channels:
            channels = [ctx.channel]

        added_count = 0
        for channel in channels:
            await add_allowed_channel(channel.id)
            added_count += 1
        
        await ctx.send(f"✅ **Configuration Updated:** Flicker is now active in {added_count} channel(s).")

    @commands.command(name="RmC")
    async def remove_channels(self, ctx, *channels: discord.TextChannel):
        """Removes one or more channels. Usage: !RmC #general"""
        if not channels:
            channels = [ctx.channel]

        removed_count = 0
        for channel in channels:
            await remove_allowed_channel(channel.id)
            removed_count += 1
            
        await ctx.send(f"🚫 **Configuration Updated:** Flicker has stopped tracking {removed_count} channel(s).")

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
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Admin(bot))
