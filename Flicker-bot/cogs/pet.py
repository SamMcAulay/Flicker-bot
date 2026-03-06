import math
import time
import discord
import random
from discord.ext import commands
from database import update_balance, increment_stat, get_pet_data, update_pet_data

STREAK_CAP = 30
STREAK_WINDOW = 4500       # 1h15m in seconds — upper bound for "on time"
DECAY_INTERVAL = 720       # lose 5 streak levels per hour past the window

MILESTONES = {
    7:  (25,  "🌙 **Streak Milestone!**", "You've been visiting regularly! Flicker saved something special for you."),
    14: (50,  "⭐ **Dedicated Visitor!**", "Consistent visits — Flicker has fully imprinted on you."),
    30: (100, "🌟 **Devoted Companion!**", "Flicker's eternal favourite. This level of dedication deserves a mega reward."),
}

class Pet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="pet")
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def pet_flicker(self, ctx):
        """Give Flicker a pet once an hour for Stardust — keep your streak up for bigger rewards!"""
        now = time.time()
        base_reward = random.randint(1, 10)

        streak, last_pet_time = await get_pet_data(ctx.author.id)

        # Ensure the user row exists before we UPDATE it
        await update_balance(ctx.author.id, 0)

        if last_pet_time == 0:
            # First ever pet
            new_streak = 1
        else:
            elapsed = now - last_pet_time
            if elapsed <= STREAK_WINDOW:
                # On time — build streak
                new_streak = min(streak + 1, STREAK_CAP)
            else:
                # Late — decay then don't add
                hours_late = (elapsed - STREAK_WINDOW) / DECAY_INTERVAL
                decay = math.floor(hours_late)
                new_streak = max(0, streak - decay)

        streak_bonus = new_streak  # +1 Stardust per streak level
        total_reward = base_reward + streak_bonus

        # Check for milestone (fires each time streak reaches the threshold)
        milestone = MILESTONES.get(new_streak)
        milestone_reward = 0
        if milestone:
            milestone_reward = milestone[0]
            total_reward += milestone_reward

        await update_balance(ctx.author.id, total_reward)
        await update_pet_data(ctx.author.id, new_streak, now)
        await increment_stat("pet_count")

        # Build embed
        if milestone:
            _, title, flavour = milestone
            embed = discord.Embed(
                title=title,
                description=(
                    f"{flavour}\n\n"
                    f"**+{base_reward} Stardust** (base)\n"
                    f"**+{streak_bonus} Stardust** (streak bonus)\n"
                    f"**+{milestone_reward} Stardust** (milestone burst!)\n\n"
                    f"🔥 Streak: **{new_streak}**"
                ),
                color=discord.Color.gold(),
            )
        elif new_streak > 1:
            responses = [
                f"aww thank you, {ctx.author.mention}! I found this bit of Stardust for you! 🌟",
                f"*happy noises* you're sweet, {ctx.author.mention}! Take this! ✨",
                f"you are my favorite space traveler, {ctx.author.mention}! Have some shiny Stardust! 💫",
                f"thank you for the head pats! I gathered this for you! 💖",
            ]
            embed = discord.Embed(
                description=(
                    f"{random.choice(responses)}\n\n"
                    f"**+{base_reward} Stardust** (base) + **+{streak_bonus} Stardust** (streak bonus)\n"
                    f"🔥 Streak: **{new_streak}** — keep it up!"
                ),
                color=discord.Color.gold(),
            )
        else:
            responses = [
                f"aww thank you, {ctx.author.mention}! I found this bit of Stardust for you! 🌟",
                f"*happy noises* you're sweet, {ctx.author.mention}! Take this! ✨",
                f"hehe, that tickles! here is some Stardust I was saving!",
                f"you are my favorite space traveler, {ctx.author.mention}! Have some shiny Stardust! 💫",
                f"thank you for the head pats! I gathered this for you! 💖",
            ]
            embed = discord.Embed(
                description=f"{random.choice(responses)}\n\n**+{total_reward} Stardust**",
                color=discord.Color.gold(),
            )

        await ctx.send(embed=embed)

    @pet_flicker.error
    async def pet_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutes, seconds = divmod(int(error.retry_after), 60)
            cooldown_responses = [
                f"my happiness sensors are still full! try again in **{minutes}m {seconds}s**, {ctx.author.mention}! ✨",
                f"I'm still processing your last pet, {ctx.author.mention}! come back in **{minutes}m {seconds}s**! 🤖",
                f"*sleepy beep* I need a little nap before more pets. check back in **{minutes}m {seconds}s**! 💤",
            ]
            await ctx.send(random.choice(cooldown_responses))
        else:
            print(f"Error in !pet: {error}")

async def setup(bot):
    await bot.add_cog(Pet(bot))
