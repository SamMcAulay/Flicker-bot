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
        """Fetches a random Science question from OpenTDB."""
        url = "https://opentdb.com/api.php?amount=1&category=17&type=multiple"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract Data
                    q_data = data["results"][0]
                    question_text = html.unescape(q_data["question"])
                    correct_answer = html.unescape(q_data["correct_answer"])
                    incorrect_answers = [html.unescape(ans) for ans in q_data["incorrect_answers"]]
                    
                    # Mix answers together
                    all_options = incorrect_answers + [correct_answer]
                    random.shuffle(all_options)
                    
                    # Find which letter is the correct one
                    correct_index = all_options.index(correct_answer)
                    correct_letter = ["A", "B", "C", "D"][correct_index]

                    # Format the options for display
                    options_text = ""
                    labels = ["A", "B", "C", "D"]
                    for i, option in enumerate(all_options):
                        options_text += f"**{labels[i]}.** {option}\n"

                    reward = 50

                    embed = discord.Embed(
                        title="📡 Incoming Transmission: Trivia!!",
                        description=f"{question_text}\n\n{options_text}\n*Type the letter (A/B/C/D) or the full answer!*",
                        color=discord.Color.blue()
                    )
                    await channel.send(embed=embed)

                    def check(m):
                        if m.channel != channel or m.author.bot:
                            return False
                        
                        user_input = m.content.lower().strip()
                        return user_input == correct_letter.lower() or user_input == correct_answer.lower()

                    try:
                        winner_msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                        await update_balance(winner_msg.author.id, reward)
                        await channel.send(f"🎉 **Correct!** The answer was **{correct_answer}**. {winner_msg.author.mention} wins **{reward} Stardust**!")
                    except asyncio.TimeoutError:
                        await channel.send(f"❌ Signal lost. The correct answer was **{correct_answer}**.")
                else:
                    print("API Error")

    async def event_fast_type(self, channel):
        words = ["FLICKER", "HYPERDRIVE", "STARSHIP", "GALAXY", "METEOR", "ASTEROID", "NEBULA", "QUASAR"]
        target_word = random.choice(words)
        reward = 30

        embed = discord.Embed(
            title="⚡ Reflex Check",
            description=f"First to type: **{target_word}**",
            color=discord.Color.gold()
        )
        await channel.send(embed=embed)

        def check(m):
            return m.channel == channel and not m.author.bot and m.content == target_word

        try:
            winner_msg = await self.bot.wait_for('message', check=check, timeout=15.0)
            await update_balance(winner_msg.author.id, reward)
            await channel.send(f"⚡ **Fast!** {winner_msg.author.mention} grabbed **{reward} Stardust**!")
        except asyncio.TimeoutError:
            await channel.send(f"Too slow! The word was {target_word}.")

    async def event_math(self, channel):
        a = random.randint(1, 50)
        b = random.randint(1, 50)
        op = random.choice(["+", "-"])
        
        if op == "+":
            answer = a + b
        else:
            answer = a - b
            
        reward = 20

        embed = discord.Embed(
            title="🧮 Navigation Calculation",
            description=f"Solve: **{a} {op} {b}**",
            color=discord.Color.green()
        )
        await channel.send(embed=embed)

        def check(m):
            return m.channel == channel and not m.author.bot and m.content == str(answer)

        try:
            winner_msg = await self.bot.wait_for('message', check=check, timeout=15.0)
            await update_balance(winner_msg.author.id, reward)
            await channel.send(f"🧠 **Calculated!** {winner_msg.author.mention} earned **{reward} Stardust**!")
        except asyncio.TimeoutError:
            await channel.send(f"Time expired. Answer: {answer}")

async def setup(bot):
    await bot.add_cog(Events(bot))
