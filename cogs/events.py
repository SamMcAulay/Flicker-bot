import discord
import random
import asyncio
import aiohttp
import html
import time
from discord.ext import commands
from database import update_balance, get_allowed_channels # <--- Added Import

SCRAMBLE_WORDS = [
    "nebula", "galaxy", "cosmos", "pulsar", "quasar", "meteor", "comet",
    "planet", "stellar", "aurora", "eclipse", "photon", "neutron", "orbit",
    "zenith", "cosmic", "solaris", "astral", "radiant", "vortex",
]

SPACE_EMOJIS = ["🌙", "⭐", "🪐", "💫", "✨", "🌟", "☄️", "🚀", "🛸", "🌌"]

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_event_active = False 
        self.last_event_time = 0
        self.cooldown_seconds = 180 

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or self.is_event_active:
            return

        allowed_ids = await get_allowed_channels()
        
        if message.channel.id not in allowed_ids:
            return

        if time.time() - self.last_event_time < self.cooldown_seconds:
            return

        chance = random.random()

        if chance < 0.05: # 5% Drop
            await self.trigger_event(message.channel, "drop")
        elif chance < 0.06: # 1% Trivia
            await self.trigger_event(message.channel, "trivia")
        elif chance < 0.07: # 1% Math
            await self.trigger_event(message.channel, "math")
        elif chance < 0.08: # 1% Fast Type
            await self.trigger_event(message.channel, "fast_type")
        elif chance < 0.09: # 1% Word Scramble
            await self.trigger_event(message.channel, "word_scramble")
        elif chance < 0.10: # 1% Emoji Sequence
            await self.trigger_event(message.channel, "emoji_sequence")

    # --- DEV TOOL ---
    @commands.command(name="simulate", hidden=True)
    @commands.has_permissions(administrator=True)
    async def simulate_event(self, ctx, game_type: str = None):
        """Dev Tool: Bypass cooldowns and force an event."""
        
        if self.is_event_active:
            await ctx.send("⚠️ I'm already playing a game!")
            return

        target_game = game_type if game_type else random.choice(["drop", "trivia", "math", "fast_type", "word_scramble", "emoji_sequence"])
        await ctx.send(f"🪄 **Poof!** Summoning a {target_game} event... (Cooldown bypassed)")
        await self.trigger_event(ctx.channel, target_game)

    # --- EVENT MANAGER ---
    async def trigger_event(self, channel, game_type):
        self.is_event_active = True
        self.last_event_time = time.time() 
        
        try:
            if game_type == "trivia": await self.event_trivia(channel)
            elif game_type == "fast_type": await self.event_fast_type(channel)
            elif game_type == "math": await self.event_math(channel)
            elif game_type == "drop": await self.event_drop(channel)
            elif game_type == "word_scramble": await self.event_word_scramble(channel)
            elif game_type == "emoji_sequence": await self.event_emoji_sequence(channel)
        except Exception as e:
            print(f"Event Error: {e}")
        finally:
            self.is_event_active = False

    # --- GAMES ---

    async def event_drop(self, channel):
        reward = random.randint(1, 10)
        embed = discord.Embed(title="✨ Ooh! Shiny!", description=f"Someone dropped a pouch of Stardust!\nType **catch** to pick it up!", color=discord.Color.magenta())
        await channel.send(embed=embed)
        def check(m): return m.channel == channel and not m.author.bot and m.content.lower().strip() == "catch"
        try:
            winner = await self.bot.wait_for('message', check=check, timeout=15.0)
            await update_balance(winner.author.id, reward)
            await channel.send(f"🤲 **Gotcha!** {winner.author.mention} caught **{reward} Stardust**!")
        except asyncio.TimeoutError:
            await channel.send("💨 **Poof!** The Stardust blew away in the cosmic wind.")

    async def event_fast_type(self, channel):
        reward = random.randint(10, 20)
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        target_code = f"{''.join(random.choices(chars, k=3))}-{''.join(random.choices(chars, k=3))}"
        embed = discord.Embed(title="💫 Catch the Falling Star!", description=f"Quick! Type this magic spell before it disappears:\n\n`{target_code}`", color=discord.Color.gold())
        await channel.send(embed=embed)
        def check(m): return m.channel == channel and not m.author.bot and m.content == target_code
        try:
            winner = await self.bot.wait_for('message', check=check, timeout=10.0)
            await update_balance(winner.author.id, reward)
            await channel.send(f"🌟 **Caught it!** {winner.author.mention} snagged **{reward} Stardust**!")
        except asyncio.TimeoutError:
            await channel.send(f"💨 **Whoosh!** It flew away. The spell was `{target_code}`.")

    async def event_math(self, channel):
        reward = random.randint(20, 40)
        a, b, c = random.randint(2, 9), random.randint(10, 20), random.randint(1, 50)
        op_type = random.choice(["mul_add", "sub_add"])
        if op_type == "mul_add": equation, answer = f"{a} × {b} + {c}", (a * b) + c
        else: equation, answer = f"{b} + {c} - {a}", b + c - a
        embed = discord.Embed(title="🧩 Starship Puzzle!", description=f"Help me count the moons! What is:\n\n**{equation}**", color=discord.Color.teal())
        await channel.send(embed=embed)
        def check(m): return m.channel == channel and not m.author.bot and m.content == str(answer)
        try:
            winner = await self.bot.wait_for('message', check=check, timeout=12.0)
            await update_balance(winner.author.id, reward)
            await channel.send(f"🤖 **Thank you!** {winner.author.mention} solved the puzzle! **{reward} Stardust** for you!")
        except asyncio.TimeoutError:
            await channel.send(f"💤 **I fell asleep counting...** The answer was **{answer}**.")

    async def event_trivia(self, channel):
        reward = random.randint(50, 100)
        url = "https://opentdb.com/api.php?amount=1&category=17&type=multiple"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    q_data = data["results"][0]
                    question, correct = html.unescape(q_data["question"]).strip(), html.unescape(q_data["correct_answer"]).strip()
                    incorrect = [html.unescape(a).strip() for a in q_data["incorrect_answers"]]
                    all_opts = incorrect + [correct]
                    random.shuffle(all_opts)
                    correct_idx = all_opts.index(correct)
                    correct_let = ["A", "B", "C", "D"][correct_idx]
                    opts_text = "".join([f"**{['A','B','C','D'][i]}.** {o}\n" for i, o in enumerate(all_opts)])
                    
                    embed = discord.Embed(title="✨ A Little Star Told Me...", description=f"{question}\n\n{opts_text}\n*Make a wish and pick an answer!*", color=discord.Color.purple())
                    await channel.send(embed=embed)
                    valid_inputs = [x.lower() for x in ["A", "B", "C", "D"] + all_opts]
                    def check(m): return m.channel == channel and not m.author.bot and m.content.lower().strip() in valid_inputs
                    try:
                        msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                        if msg.content.lower().strip() in [correct_let.lower(), correct.lower()]:
                            await update_balance(msg.author.id, reward)
                            await channel.send(f"🎉 **Woohoo!** That's right! The answer was **{correct}**. {msg.author.mention} caught **{reward} Stardust**!")
                        else: await channel.send(f"☁️ **Oh no!** That wasn't quite right. The answer was **{correct}**.")
                    except asyncio.TimeoutError: await channel.send(f"🌙 **The stars have faded.** The answer was **{correct}**.")

    async def event_word_scramble(self, channel):
        reward = random.randint(15, 30)
        word = random.choice(SCRAMBLE_WORDS)

        # Scramble until different from original
        chars = list(word)
        scrambled = word
        while scrambled == word:
            random.shuffle(chars)
            scrambled = "".join(chars)

        embed = discord.Embed(
            title="🔤 Galactic Scramble!",
            description=f"Flicker's star charts got all mixed up!\n\nUnscramble this cosmic word:\n\n**`{scrambled.upper()}`**",
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"You have 20 seconds! Reward: {reward} Stardust")
        await channel.send(embed=embed)

        def check(m):
            return m.channel == channel and not m.author.bot and m.content.lower().strip() == word

        try:
            winner = await self.bot.wait_for("message", check=check, timeout=20.0)
            await update_balance(winner.author.id, reward)
            await channel.send(f"🌟 **Brilliant!** {winner.author.mention} unscrambled **{word}** and earned **{reward} Stardust**!")
        except asyncio.TimeoutError:
            await channel.send(f"💨 **Time's up!** The word was **{word}**.")


    async def event_emoji_sequence(self, channel):
        reward = random.randint(10, 25)
        sequence = random.choices(SPACE_EMOJIS, k=4)
        sequence_str = " ".join(sequence)

        embed = discord.Embed(
            title="🌌 Star Pattern!",
            description=f"Flicker spotted a cosmic pattern in the stars!\n\nRepeat this sequence exactly:\n\n**{sequence_str}**",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"You have 15 seconds! Reward: {reward} Stardust")
        await channel.send(embed=embed)

        def check(m):
            return m.channel == channel and not m.author.bot and m.content.strip() == sequence_str

        try:
            winner = await self.bot.wait_for("message", check=check, timeout=15.0)
            await update_balance(winner.author.id, reward)
            await channel.send(f"✨ **Perfect!** {winner.author.mention} matched the pattern and earned **{reward} Stardust**!")
        except asyncio.TimeoutError:
            await channel.send(f"🌠 **Gone!** The pattern faded. It was: {sequence_str}")

async def setup(bot):
    await bot.add_cog(Events(bot))
