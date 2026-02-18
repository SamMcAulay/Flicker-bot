import discord
from discord.ext import commands
from database import get_balance, update_balance

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print('✅ Economy Cog loaded.')

    @commands.command(name="balance", aliases=["bal", "wallet", "b"])
    async def balance(self, ctx):
        """Check your current Stardust balance."""
        amount = await get_balance(ctx.author.id)
        
        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Wallet",
            description=f"You currently possess **{amount} Stardust** ✨",
            color=discord.Color.purple()
        )
        await ctx.send(embed=embed)

    @commands.command(name="add")
    @commands.has_permissions(administrator=True)
    async def add_money(self, ctx, member: discord.Member, amount: int):
        """Admin only: Add money to a user."""
        new_bal = await update_balance(member.id, amount)
        await ctx.send(f"💰 Added **{amount}** Stardust to {member.mention}. New balance: **{new_bal}**")

async def setup(bot):
    await bot.add_cog(Economy(bot))
