import discord
import random
import asyncio
import aiohttp
import html
import time
from discord.ext import commands
from database import update_balance

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_event_active = False 
        self.last_event_time = 0
        self.cooldown_seconds = 120

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or self.is_event_active:
            return

        if time.time() - self.last_event_time < self.cooldown_seconds:
            return

        chance = random.random()

        # Total Chance: 8% (5% Drop, 1% Trivia, 1% Math, 1% Fast Type)
        if chance < 0.05: # 0% - 5%
            await self.trigger_event(message.channel, "drop")
            
        elif chance < 0.06: # 5% - 6%
            await self.trigger_event(message.channel, "trivia")
            
        elif chance < 0.07: # 6% - 7%
            await self.trigger_event(message.channel, "math")
            
        elif chance < 0.08: # 7% - 8%
            await self.trigger_event(message.channel, "fast_type")

    # --- DEV TOOL ---
    @commands.command(name="simulate", hidden=True)
    @commands.is_owner()
    async def simulate_event(self, ctx, game_type: str = None):
        """Dev Tool: Bypass cooldowns and force an event."""
        if self.is_event_active:
            await ctx.send("⚠️ I'm already playing a game!")
            return

        target_game = game_type if game_type else random.choice(["drop", "trivia", "math", "fast_type"])
        await ctx.send(f"🪄 **Poof!** Summoning a {target_game} event... (Cooldown bypassed)")
        
        await self.trigger_event(ctx.channel, target_game)

    # --- EVENT MANAGER ---
    async def trigger_event(self, channel, game_type):
        self.is_event_active = True
        self.last_event_time = time.time()
        
        try:
            if game_type == "trivia":
                await self.event_trivia(channel)
            elif game_type == "fast_type":
                await self.event_fast_type(channel)
            elif game_type == "math":
                await self.event_math(channel)
            elif game_type == "drop":
                await self.event_drop(channel)
        except Exception as e:
            print(f"Event Error: {e}")
        finally:
            self.is_event_active = False

    # --- WHIMSICAL MINI GAMES ---

    async def event_drop(self, channel):
        """Tier 1: Simple Pickup. Reward: 1-10"""
        reward = random.randint(1, 10)
        
        embed = discord.Embed(
            title="✨ Ooh! Shiny!",
            description=f"Someone dropped a pouch of Stardust!\nType **catch** to pick it up!",
            color=discord.Color.magenta()
        )
        await channel.send(embed=embed)

        def check(m):
            return m.channel == channel and not m.author.bot and m.content.lower().strip() == "catch"

        try:
            winner_msg = await self.bot.wait_for('message', check=check, timeout=15.0)
            await update_balance(winner_msg.author.id, reward)
            await channel.send(f"🤲 **Gotcha!** {winner_msg.author.mention} caught **{reward} Stardust**!")
        except asyncio.TimeoutError:
            await channel.send(f"💨 **Poof!** The Stardust blew away in the cosmic wind.")

    async def event_fast_type(self, channel):
        """Tier 2: Fast Type. Reward: 10-20"""
        reward = random.randint(10, 20)
        
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        target_code = f"{''.join(random.choices(chars, k=3))}-{''.join(random.choices(chars, k=3))}"
        
        embed = discord.Embed(
            title="💫 Catch the Falling Star!",
            description=f"Quick! Type this magic spell before it disappears:\n\n`{target_code}`",
            color=discord.Color.gold()
        )
        await channel.send(embed=embed)

        def check(m):
            return m.channel == channel and not m.author.bot and m.content == target_code

        try:
            winner_msg = await self.bot.wait_for('message', check=check, timeout=10.0)
            await update_balance(winner_msg.author.id, reward)
            await channel.send(f"🌟 **Caught it!** {winner_msg.author.mention} snagged **{reward} Stardust**!")
        except asyncio.TimeoutError:
            await channel.send(f"💨 **Whoosh!** It flew away. The spell was `{target_code}`.")

    async def event_math(self, channel):
        """Tier 3: Math. Reward: 20-40"""
        reward = random.randint(20, 40)
        
        a = random.randint(2, 9)
        b = random.randint(10, 20)
        c = random.randint(1, 50)
        op_type = random.choice(["mul_add", "sub_add"])
        
        if op_type == "mul_add":
            equation = f"{a} × {b} + {c}"
            answer = (a * b) + c
        else:
            equation = f"{b} + {c} - {a}"
            answer = b + c - a

        embed = discord.Embed(
            title="🧩 Starship Puzzle!",
            description=f"Help me count the moons! What is:\n\n**{equation}**",
            color=discord.Color.teal()
        )
        await channel.send(embed=embed)

        def check(m):
            return m.channel == channel and not m.author.bot and m.content == str(answer)

        try:
            winner_msg = await self.bot.wait_for('message', check=check, timeout=12.0)
            await update_balance(winner_msg.author.id, reward)
            await channel.send(f"🤖 **Thank you!** {winner_msg.author.mention} solved the puzzle! **{reward} Stardust** for you!")
        except asyncio.TimeoutError:
            await channel.send(f"💤 **I fell asleep counting...** The answer was **{answer}**.")

    async def event_trivia(self, channel):
        """Tier 4: Trivia. Reward: 50-100"""
        reward = random.randint(50, 100)
        
        url = "https://opentdb.com/api.php?amount=1&category=17&type=multiple"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    q_data = data["results"][0]
                    question_text = html.unescape(q_data["question"]).strip()
                    correct_answer = html.unescape(q_data["correct_answer"]).strip()
                    incorrect_answers = [html.unescape(ans).strip() for ans in q_data["incorrect_answers"]]
                    
                    all_options = incorrect_answers + [correct_answer]
                    random.shuffle(all_options)
                    
                    correct_index = all_options.index(correct_answer)
                    correct_letter = ["A", "B", "C", "D"][correct_index]

                    options_text = ""
                    labels = ["A", "B", "C", "D"]
                    valid_inputs = []

                    for i, option in enumerate(all_options):
                        lbl = labels[i]
                        options_text += f"**{lbl}.** {option}\n"
                        valid_inputs.append(lbl.lower())
                        valid_inputs.append(option.lower())

                    embed = discord.Embed(
                        title="✨ A Little Star Told Me...",
                        description=f"{question_text}\n\n{options_text}\n*Make a wish and pick an answer!*",
                        color=discord.Color.purple()
                    )
                    await channel.send(embed=embed)
                    
                    def check(m):
                        if m.channel != channel or m.author.bot:
                            return False
                        return m.content.lower().strip() in valid_inputs

                    try:
                        msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                        user_input = msg.content.lower().strip()
                        
                        if user_input == correct_letter.lower() or user_input == correct_answer.lower():
                            await update_balance(msg.author.id, reward)
                            await channel.send(f"🎉 **Woohoo!** That's right! The answer was **{correct_answer}**. {msg.author.mention} caught **{reward} Stardust**!")
                        else:
                            await channel.send(f"☁️ **Oh no!** That wasn't quite right. The answer was **{correct_answer}**.")
                            
                    except asyncio.TimeoutError:
                        await channel.send(f"🌙 **The stars have faded.** The answer was **{correct_answer}**.")
                else:
                    print("API Error")

async def setup(bot):
    await bot.add_cog(Events(bot))
