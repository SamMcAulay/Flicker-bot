import discord
import random
import asyncio
import aiohttp
import html
import re
import time
from discord.ext import commands
from database import update_balance, get_allowed_channels, increment_stat, get_server_settings


def normalize_answer(text):
    return re.sub(r'[^\w\s]', '', text.lower()).strip()

SCRAMBLE_WORDS = [
    "nebula", "galaxy", "cosmos", "pulsar", "quasar", "meteor", "comet",
    "planet", "stellar", "aurora", "eclipse", "photon", "neutron", "orbit",
    "zenith", "cosmic", "solaris", "astral", "radiant", "vortex",
]


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_event_active = False
        self.last_event_time = 0
        self.cooldown_seconds = 180
        self.drop_queue = None
        self.drop_channel = None
        self.drop_caught_ids = set()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Feed active drop events before the is_event_active guard
        if (self.drop_queue is not None
                and message.channel == self.drop_channel
                and message.content.lower().strip() == "catch"
                and message.author.id not in self.drop_caught_ids):
            self.drop_caught_ids.add(message.author.id)
            await self.drop_queue.put(message.author)
            return

        if self.is_event_active:
            return

        allowed_ids = await get_allowed_channels()
        
        if message.channel.id not in allowed_ids:
            return

        if time.time() - self.last_event_time < self.cooldown_seconds:
            return

        guild_id = message.guild.id if message.guild else None
        event_toggles = {}
        if guild_id:
            settings = await get_server_settings(guild_id)
            event_toggles = settings["event_toggles"]

        chance = random.random()

        if chance < 0.05 and event_toggles.get("chat_drops", True):
            await self.trigger_event(message.channel, "drop")
        elif chance < 0.06 and event_toggles.get("trivia", True):
            await self.trigger_event(message.channel, "trivia")
        elif chance < 0.07 and event_toggles.get("math", True):
            await self.trigger_event(message.channel, "math")
        elif chance < 0.08 and event_toggles.get("fast_type", True):
            await self.trigger_event(message.channel, "fast_type")
        elif chance < 0.09 and event_toggles.get("word_scramble", True):
            await self.trigger_event(message.channel, "word_scramble")

    # --- DEV TOOL ---
    @commands.command(name="simulate", hidden=True)
    @commands.has_permissions(administrator=True)
    async def simulate_event(self, ctx, game_type: str = None):
        """Dev Tool: Bypass cooldowns and force an event."""
        
        if self.is_event_active:
            await ctx.send("⚠️ I'm already playing a game!")
            return

        target_game = game_type if game_type else random.choice(["drop", "trivia", "math", "fast_type", "word_scramble"])
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
        except Exception as e:
            print(f"Event Error: {e}")
        finally:
            self.is_event_active = False

    # --- GAMES ---

    async def event_drop(self, channel):
        guild_id = channel.guild.id if channel.guild else None
        po = {}
        if guild_id:
            settings = await get_server_settings(guild_id)
            po = settings["payout_overrides"]
        reward_ranges = [
            (int(po.get("drop_1_min", 10)), int(po.get("drop_1_max", 12))),
            (int(po.get("drop_2_min", 8)),  int(po.get("drop_2_max", 10))),
            (int(po.get("drop_3_min", 6)),  int(po.get("drop_3_max", 8))),
            (int(po.get("drop_4_min", 4)),  int(po.get("drop_4_max", 6))),
            (int(po.get("drop_5_min", 1)),  int(po.get("drop_5_max", 4))),
        ]
        rewards = [random.randint(lo, hi) for lo, hi in reward_ranges]

        def build_embed(catchers):
            slots = []
            next_idx = len(catchers)
            for i in range(5):
                if i < len(catchers):
                    slots.append(f"**#{i + 1}** {catchers[i].mention} — **{rewards[i]} ✨**")
                elif i == next_idx:
                    slots.append(f"**#{i + 1}** **{rewards[i]} ✨** — type **catch**!")
                else:
                    slots.append(f"**#{i + 1}** *???*")
            embed = discord.Embed(
                title="✨ Ooh! Shiny!",
                description="Someone dropped a pouch of Stardust!\n\n" + "\n".join(slots),
                color=discord.Color.magenta()
            )
            embed.set_footer(text="15 seconds to catch!")
            return embed

        catchers = []
        msg = await channel.send(embed=build_embed(catchers))

        self.drop_queue = asyncio.Queue()
        self.drop_channel = channel
        self.drop_caught_ids = set()

        try:
            deadline = asyncio.get_event_loop().time() + 15.0
            while len(catchers) < 5:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    user = await asyncio.wait_for(self.drop_queue.get(), timeout=remaining)
                    catchers.append(user)
                    await msg.edit(embed=build_embed(catchers))
                except asyncio.TimeoutError:
                    break
        finally:
            self.drop_queue = None
            self.drop_channel = None
            self.drop_caught_ids = set()

        guild_id = channel.guild.id if channel.guild else 0
        if catchers:
            for i, user in enumerate(catchers):
                reward = rewards[i]
                await update_balance(user.id, guild_id, reward)
                await increment_stat("stardust_earned", reward)
                await increment_stat("games_correct")
            await channel.send("🤲 **The dust has settled!**")
        else:
            await increment_stat("games_wrong")
            await channel.send("💨 **Poof!** The Stardust blew away in the cosmic wind.")

    async def event_fast_type(self, channel):
        guild_id = channel.guild.id if channel.guild else None
        po = (await get_server_settings(guild_id))["payout_overrides"] if guild_id else {}
        reward = random.randint(int(po.get("fast_type_min", 10)), int(po.get("fast_type_max", 20)))
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        target_code = f"{''.join(random.choices(chars, k=3))}-{''.join(random.choices(chars, k=3))}"
        display_code = "\u200b".join(target_code)  # zero-width spaces prevent copy-paste on mobile
        embed = discord.Embed(title="💫 Catch the Falling Star!", description=f"Quick! Type this magic spell before it disappears:\n\n**{display_code}**", color=discord.Color.gold())
        embed.set_footer(text=f"You have 10 seconds! Reward: {reward} Stardust")
        await channel.send(embed=embed)
        def check(m): return m.channel == channel and not m.author.bot and m.content == target_code
        guild_id = channel.guild.id if channel.guild else 0
        try:
            winner = await self.bot.wait_for('message', check=check, timeout=10.0)
            await update_balance(winner.author.id, guild_id, reward)
            await increment_stat("stardust_earned", reward)
            await increment_stat("games_correct")
            await channel.send(f"🌟 **Caught it!** {winner.author.mention} snagged **{reward} Stardust**!")
        except asyncio.TimeoutError:
            await increment_stat("games_wrong")
            await channel.send(f"💨 **Whoosh!** It flew away. The spell was `{target_code}`.")

    async def event_math(self, channel):
        guild_id = channel.guild.id if channel.guild else None
        po = (await get_server_settings(guild_id))["payout_overrides"] if guild_id else {}
        reward = random.randint(int(po.get("math_min", 20)), int(po.get("math_max", 40)))
        a, b, c = random.randint(2, 9), random.randint(10, 20), random.randint(1, 50)
        op_type = random.choice(["mul_add", "sub_add"])
        if op_type == "mul_add": equation, answer = f"{a} × {b} + {c}", (a * b) + c
        else: equation, answer = f"{b} + {c} - {a}", b + c - a
        embed = discord.Embed(title="🧩 Starship Puzzle!", description=f"Help me count the moons! What is:\n\n**{equation}**", color=discord.Color.teal())
        embed.set_footer(text=f"You have 12 seconds! Reward: {reward} Stardust")
        await channel.send(embed=embed)
        def check(m): return m.channel == channel and not m.author.bot and m.content == str(answer)
        guild_id = channel.guild.id if channel.guild else 0
        try:
            winner = await self.bot.wait_for('message', check=check, timeout=12.0)
            await update_balance(winner.author.id, guild_id, reward)
            await increment_stat("stardust_earned", reward)
            await increment_stat("games_correct")
            await channel.send(f"🤖 **Thank you!** {winner.author.mention} solved the puzzle! **{reward} Stardust** for you!")
        except asyncio.TimeoutError:
            await increment_stat("games_wrong")
            await channel.send(f"💤 **I fell asleep counting...** The answer was **{answer}**.")

    async def event_trivia(self, channel):
        guild_id = channel.guild.id if channel.guild else None
        po = (await get_server_settings(guild_id))["payout_overrides"] if guild_id else {}
        reward = random.randint(int(po.get("trivia_min", 50)), int(po.get("trivia_max", 100)))
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
                    embed.set_footer(text=f"You have 30 seconds! Reward: {reward} Stardust")
                    await channel.send(embed=embed)
                    valid_letters = ["a", "b", "c", "d"]
                    normalized_opts = [normalize_answer(o) for o in all_opts]
                    def check(m):
                        t = m.content.lower().strip()
                        return m.channel == channel and not m.author.bot and (t in valid_letters or normalize_answer(t) in normalized_opts)
                    guild_id = channel.guild.id if channel.guild else 0
                    try:
                        msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                        if msg.content.lower().strip() == correct_let.lower() or normalize_answer(msg.content) == normalize_answer(correct):
                            await update_balance(msg.author.id, guild_id, reward)
                            await increment_stat("stardust_earned", reward)
                            await increment_stat("games_correct")
                            await channel.send(f"🎉 **Woohoo!** That's right! The answer was **{correct}**. {msg.author.mention} caught **{reward} Stardust**!")
                        else:
                            await increment_stat("games_wrong")
                            await channel.send(f"☁️ **Oh no!** That wasn't quite right. The answer was **{correct}**.")
                    except asyncio.TimeoutError:
                        await increment_stat("games_wrong")
                        await channel.send(f"🌙 **The stars have faded.** The answer was **{correct}**.")

    async def event_word_scramble(self, channel):
        guild_id = channel.guild.id if channel.guild else None
        po = (await get_server_settings(guild_id))["payout_overrides"] if guild_id else {}
        reward = random.randint(int(po.get("word_scramble_min", 15)), int(po.get("word_scramble_max", 30)))
        word = random.choice(SCRAMBLE_WORDS)

        # Scramble until different from original
        chars = list(word)
        scrambled = word
        for _ in range(100):
            random.shuffle(chars)
            scrambled = "".join(chars)
            if scrambled != word:
                break
        # If still equal (e.g. all-identical-character word), just reverse it
        if scrambled == word:
            scrambled = word[::-1]

        embed = discord.Embed(
            title="🔤 Galactic Scramble!",
            description=f"Flicker's star charts got all mixed up!\n\nUnscramble this cosmic word:\n\n**`{scrambled.upper()}`**",
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"You have 20 seconds! Reward: {reward} Stardust")
        await channel.send(embed=embed)

        def check(m):
            return m.channel == channel and not m.author.bot and m.content.lower().strip() == word

        guild_id = channel.guild.id if channel.guild else 0
        try:
            winner = await self.bot.wait_for("message", check=check, timeout=20.0)
            await update_balance(winner.author.id, guild_id, reward)
            await increment_stat("stardust_earned", reward)
            await increment_stat("games_correct")
            await channel.send(f"🌟 **Brilliant!** {winner.author.mention} unscrambled **{word}** and earned **{reward} Stardust**!")
        except asyncio.TimeoutError:
            await increment_stat("games_wrong")
            await channel.send(f"💨 **Time's up!** The word was **{word}**.")


async def setup(bot):
    await bot.add_cog(Events(bot))
