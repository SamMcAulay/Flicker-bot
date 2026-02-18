import discord
import random
import asyncio
import aiohttp
import html
from discord.ext import commands
from database import update_balance

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_event_active = False 

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or self.is_event_active:
            return

        if random.random() < 0.05:
            await self.trigger_random_event(message.channel)

    # --- DEV TOOL ---
    @commands.command(name="simulate", hidden=True)
    @commands.is_owner()
    async def simulate_event(self, ctx, game_type: str = None):
        """Force an event to start."""
        if self.is_event_active:
            await ctx.send("⚠️ An event is already active!")
            return

        await ctx.send(f"🛠️ **Dev Mode:** Forcing {game_type if game_type else 'random'} event...")
        
        self.is_event_active = True
        try:
            if game_type == "math":
                await self.event_math(ctx.channel)
            elif game_type == "trivia":
                await self.event_trivia(ctx.channel)
            elif game_type == "fast_type":
                await self.event_fast_type(ctx.channel)
            else:
                await self.trigger_random_event(ctx.channel)
        except Exception as e:
            await ctx.send(f"Error: {e}")
        finally:
            self.is_event_active = False

    async def trigger_random_event(self, channel):
        self.is_event_active = True
        game_type = random.choice(["trivia", "fast_type", "math"])
        
        try:
            if game_type == "trivia":
                await self.event_trivia(channel)
            elif game_type == "fast_type":
                await self.event_fast_type(channel)
            elif game_type == "math":
                await self.event_math(channel)
        except Exception as e:
            print(f"Error in event: {e}")
        finally:
            self.is_event_active = False

    # --- MINI GAMES ---

    async def event_trivia(self, channel):
        """Science Trivia. Reward: 10,000"""
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
                        title="📡 Incoming Transmission: Trivia!",
                        description=f"{question_text}\n\n{options_text}\n*You have ONE chance. Type the letter or answer!*",
                        color=discord.Color.blue()
                    )
                    await channel.send(embed=embed)
                    
                    def check(m):
                        if m.channel != channel or m.author.bot:
                            return False
                        user_input = m.content.lower().strip()
                        return user_input in valid_inputs

                    try:
                        msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                        user_input = msg.content.lower().strip()
                        
                        if user_input == correct_letter.lower() or user_input == correct_answer.lower():
                            await update_balance(msg.author.id, 10000)
                            await channel.send(f"🎉 **Correct!** The answer was **{correct_answer}**. {msg.author.mention} wins **10,000 Stardust**!")
                        else:
                            await channel.send(f"❌ **Incorrect!** {msg.author.mention} destabilized the signal. The correct answer was **{correct_answer}**.")
                            
                    except asyncio.TimeoutError:
                        await channel.send(f"❌ Signal lost. The correct answer was **{correct_answer}**.")
                else:
                    print("API Error")

    async def event_fast_type(self, channel):
        """Type a randomized alphanumeric code! Reward: 5,000"""
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        part1 = "".join(random.choices(chars, k=3))
        part2 = "".join(random.choices(chars, k=2))
        target_code = f"{part1}-{part2}"
        
        reward = 5000

        embed = discord.Embed(
            title="⚡ SECURITY BREACH DETECTED",
            description=f"Override code required! Type this exactly:\n\n`{target_code}`",
            color=discord.Color.red()
        )
        await channel.send(embed=embed)

        def check(m):
            return m.channel == channel and not m.author.bot and m.content == target_code

        try:
            winner_msg = await self.bot.wait_for('message', check=check, timeout=10.0)
            await update_balance(winner_msg.author.id, reward)
            await channel.send(f"✅ **Access Granted.** {winner_msg.author.mention} secured **{reward:,} Stardust**!")
        except asyncio.TimeoutError:
            await channel.send(f"⚠️ **Breach failed.** The code was `{target_code}`.")

    async def event_math(self, channel):
        """Two-step mental math. Reward: 3,000"""
        a = random.randint(2, 9)
        b = random.randint(10, 20)
        c = random.randint(1, 50)
        
        op_type = random.choice(["mul_add", "sub_add", "double_add"])
        
        if op_type == "mul_add":
            equation = f"{a} × {b} + {c}"
            answer = (a * b) + c
        elif op_type == "sub_add":
            equation = f"{b} + {c} - {a}"
            answer = b + c - a
        else:
            equation = f"{c} + {b} + {a}"
            answer = c + b + a
            
        reward = 3000

        embed = discord.Embed(
            title="🧮 Navigation Systems Offline",
            description=f"Calculate quickly to restore power:\n\n**{equation}**",
            color=discord.Color.orange()
        )
        await channel.send(embed=embed)

        def check(m):
            return m.channel == channel and not m.author.bot and m.content == str(answer)

        try:
            winner_msg = await self.bot.wait_for('message', check=check, timeout=12.0)
            await update_balance(winner_msg.author.id, reward)
            await channel.send(f"🔋 **Systems Online.** {winner_msg.author.mention} calculated the solution: **{reward:,} Stardust**!")
        except asyncio.TimeoutError:
            await channel.send(f"❌ **System Failure.** The answer was **{answer}**.")

async def setup(bot):
    await bot.add_cog(Events(bot))
