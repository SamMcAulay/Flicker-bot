import discord
import random
from discord.ext import commands

class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        content = message.content.lower()
        
        if "flicker" not in content:
            return

        # GREETINGS
        if any(word in content for word in ["hi", "hello", "hey"]):
            if random.random() < 0.01:
                response = f"I've been thinking about you, {message.author.mention}!"
            else:
                responses = [
                    f"hey there {message.author.mention}!",
                    f"hi {message.author.mention}!",
                    f"good to see you, {message.author.mention}!"
                ]
                response = random.choice(responses)
            
            await message.channel.send(response)
            return

        # GRATITUDE
        if any(word in content for word in ["thank", "thanks"]):
            responses = [
                f"no problem, {message.author.mention}!",
                "anytime!",
                "of course!",
                f"happy to help, {message.author.mention}!"
            ]
            await message.channel.send(random.choice(responses))
            return

        # GOODBYES
        if any(word in content for word in ["bye", "goodbye"]):
            responses = [
                f"goodbye, {message.author.mention}!",
                "later!",
                f"have a good day, {message.author.mention}!",
                "toodles!"
            ]
            await message.channel.send(random.choice(responses))
            return

        if random.random() < 0.01:
            responses = [
                "huh?",
                f"are you talking about me, {message.author.mention}?",
                "what?",
                "that's me!"
            ]
            await message.channel.send(random.choice(responses))

async def setup(bot):
    await bot.add_cog(Chat(bot))
