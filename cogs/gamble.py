import discord
import random
import asyncio
from discord.ext import commands
from database import get_balance, update_balance

class Gamble(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.slot_emojis = ["🍒", "🍋", "🍉", "⭐", "💎", "🔔", "🍇"]

    async def get_bet_amount(self, ctx, amount_str: str) -> int:
        balance = await get_balance(ctx.author.id)
        if amount_str.lower() in ["all", "max"]:
            if balance <= 0:
                await ctx.send("❌ Your wallet is empty!")
                return -1
            return balance
        
        try:
            amount = int(amount_str)
            if amount <= 0:
                await ctx.send("❌ You must bet a positive amount of Stardust!")
                return -1
            return amount
        except ValueError:
            await ctx.send("❌ Please enter a valid number or 'all'.")
            return -1

    @commands.command(name="coinflip", aliases=["cf"])
    @commands.cooldown(1, 15, commands.BucketType.user) 
    async def coinflip(self, ctx, amount: str, choice: str = "h"):
        """Gamble Stardust on a coinflip! Default choice is heads."""
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1: 
            ctx.command.reset_cooldown(ctx) 
            return
        
        balance = await get_balance(ctx.author.id)
        if balance < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"❌ You don't have enough Stardust! (Balance: {balance})")

        choice = choice.lower()
        if choice in ["h", "heads", "head"]:
            user_guess = "heads"
        elif choice in ["t", "tails", "tail"]:
            user_guess = "tails"
        else:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("❌ Please choose Heads (h) or Tails (t).")

        await update_balance(ctx.author.id, -bet)

        embed = discord.Embed(title="🪙 Coinflip", description=f"{ctx.author.mention} bet **{bet}** Stardust...\n\n🪙", color=discord.Color.gold())
        msg = await ctx.send(embed=embed)

        animation_frames = ["📀", "➖", "💿", "➖", "📀", "🪙"]
        
        for frame in animation_frames:
            await asyncio.sleep(0.5)
            embed.description = f"{ctx.author.mention} bet **{bet}** Stardust...\n\n{frame}"
            await msg.edit(embed=embed)

        if random.random() < 0.45:
            result = user_guess 
        else:
            result = "tails" if user_guess == "heads" else "heads" 
            
        await asyncio.sleep(0.6)

        if user_guess == result:
            winnings = bet * 2
            await update_balance(ctx.author.id, winnings)
            embed.color = discord.Color.green()
            embed.description = f"**{result.capitalize()}!** 🎉\n\nYou doubled your money to **{winnings} Stardust**!"
        else:
            embed.color = discord.Color.red()
            embed.description = f"**{result.capitalize()}!** ❌\n\nYou lost **{bet} Stardust**."

        await msg.edit(embed=embed)


    @commands.command(name="slots", aliases=["s"])
    @commands.cooldown(1, 15, commands.BucketType.user) 
    async def slots(self, ctx, amount: str):
        """Play the slot machines!"""
        bet = await self.get_bet_amount(ctx, amount)
        if bet == -1: 
            ctx.command.reset_cooldown(ctx)
            return
        
        balance = await get_balance(ctx.author.id)
        if balance < bet:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"❌ You don't have enough Stardust! (Balance: {balance})")

        await update_balance(ctx.author.id, -bet)

        chance = random.random()
        if chance < 0.01:   
            final_reels = ["💎", "💎", "💎"]
            multiplier = 10
        elif chance < 0.03: 
            final_reels = ["⭐", "⭐", "⭐"]
            multiplier = 5
        elif chance < 0.10: 
            emoji = random.choice(["🍋", "🍉"])
            final_reels = [emoji, emoji, emoji]
            multiplier = 3
        elif chance < 0.30: 
            final_reels = ["🍒", "🍒", "🍒"]
            multiplier = 2
        else:               
            final_reels = [random.choice(self.slot_emojis) for _ in range(3)]
            if final_reels[0] == final_reels[1] == final_reels[2]:
                final_reels[2] = "🍒" if final_reels[0] != "🍒" else "🍋"
            multiplier = 0

        embed = discord.Embed(title="🎰 Stardust Slots 🎰", color=discord.Color.purple())
        
        r1, r2, r3 = random.choice(self.slot_emojis), random.choice(self.slot_emojis), random.choice(self.slot_emojis)
        embed.description = f"{ctx.author.mention} bet **{bet}** Stardust...\n\n**[ {r1} | {r2} | {r3} ]**\n\n*Spinning...*"
        msg = await ctx.send(embed=embed)

        await asyncio.sleep(0.7)
        r1, r2, r3 = random.choice(self.slot_emojis), random.choice(self.slot_emojis), random.choice(self.slot_emojis)
        embed.description = f"{ctx.author.mention} bet **{bet}** Stardust...\n\n**[ {r1} | {r2} | {r3} ]**\n\n*Spinning...*"
        await msg.edit(embed=embed)

        await asyncio.sleep(0.7)
        r2, r3 = random.choice(self.slot_emojis), random.choice(self.slot_emojis)
        embed.description = f"{ctx.author.mention} bet **{bet}** Stardust...\n\n**[ {final_reels[0]} | {r2} | {r3} ]**\n\n*Reel 1 locked!*"
        await msg.edit(embed=embed)

        await asyncio.sleep(0.7)
        r3 = random.choice(self.slot_emojis)
        embed.description = f"{ctx.author.mention} bet **{bet}** Stardust...\n\n**[ {final_reels[0]} | {final_reels[1]} | {r3} ]**\n\n*Reel 2 locked!*"
        await msg.edit(embed=embed)

        await asyncio.sleep(1.0) 
        result_text = f"**[ {final_reels[0]} | {final_reels[1]} | {final_reels[2]} ]**\n\n"
        
        if multiplier > 0:
            winnings = bet * multiplier
            await update_balance(ctx.author.id, winnings)
            embed.color = discord.Color.green()
            result_text += f"🎉 **WINNER!** 🎉\nYou won **{winnings}** Stardust! ({multiplier}x)"
        else:
            embed.color = discord.Color.red()
            result_text += f"❌ **Lost!** ❌\nBetter luck next time."

        embed.description = f"{ctx.author.mention} bet **{bet}** Stardust...\n\n{result_text}"
        await msg.edit(embed=embed)


    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            time_left = round(error.retry_after, 1)
            await ctx.send(f"⏳ Whoa there, {ctx.author.mention}! The dealer needs a second. Try again in **{time_left}s**.")
        else:
            print(f"Gambling Error: {error}")

async def setup(bot):
    await bot.add_cog(Gamble(bot))