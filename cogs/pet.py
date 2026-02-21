import discord
import random
from discord.ext import commands
from database import update_balance

class Pet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="pet")
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def pet_flicker(self, ctx):
        """Give Flicker a pet once an hour for a little Stardust!"""
        reward = random.randint(1, 10)
        
        await update_balance(ctx.author.id, reward)

        responses = [
            f"aww thank you, {ctx.author.mention}! I found this bit of Stardust for you! 🌟",
            f"*happy noises* you're sweet, {ctx.author.mention}! Take this! ✨",
            f"hehe, that tickles! here is some Stardust I was saving!",
            f"you are my favorite space traveler, {ctx.author.mention}! Have some shiny Stardust! 💫",
            f"thank you for the head pats! I gathered this for you! 💖"
        ]

        embed = discord.Embed(
            description=f"{random.choice(responses)}\n\n**+{reward} Stardust**",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    @pet_flicker.error
    async def pet_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutes, seconds = divmod(int(error.retry_after), 60)
            
            cooldown_responses = [
                f"my happiness sensors are still full! try again in **{minutes}m {seconds}s**, {ctx.author.mention}! ✨",
                f"I'm still processing your last pet, {ctx.author.mention}! come back in **{minutes}m {seconds}s**! 🤖",
                f"*sleepy beep* I need a little nap before more pets. check back in **{minutes}m {seconds}s**! 💤"
            ]
            await ctx.send(random.choice(cooldown_responses))
        else:
            print(f"Error in !pet: {error}")

async def setup(bot):
    await bot.add_cog(Pet(bot))
