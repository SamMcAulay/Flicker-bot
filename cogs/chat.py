import discord
import random
import re
from discord.ext import commands

class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        content = message.content.lower()
        words = set(re.findall(r'\w+', content))
        
        if "flicker" not in words:
            return
        
        love_triggers = ["ily", "love", "luv", "heart", "adore", "wub"]
        
        if any(w in words for w in love_triggers) or "i <3 you" in content:
            responses = [
                f"aww thank you, {message.author.mention}!",
                "no problem!",
                f"you're sweet, {message.author.mention}!",
                "right back at you! ❤️",
                "aww shucks! ❤️"
            ]
            await message.channel.send(random.choice(responses))
            return

        greeting_triggers = [
            "hi", "hello", "hey", "heyy", "heyyy", "yo", "sup", 
            "greetings", "howdy", "hiya", "hola", "bonjour", "wazzup", "oy", "heya", "heyo", "heller"
        ]
        
        if any(w in words for w in greeting_triggers):
            if random.random() < 0.01:
                response = f"I've been thinking about you, {message.author.mention}!"
            else:
                responses = [
                    f"hey there {message.author.mention}!",
                    f"hi {message.author.mention}!",
                    f"good to see you, {message.author.mention}!",
                    "beep boop! hello!",
                    "greetings, friend!"
                ]
                response = random.choice(responses)
            await message.channel.send(response)
            return

        gratitude_triggers = [
            "thank", "thanks", "thx", "ty", "tysm", "appreciate", 
            "cheers", "props", "gracias", "thnks"
        ]
        
        if any(w in words for w in gratitude_triggers):
            responses = [
                f"no problem, {message.author.mention}!",
                "anytime!",
                "of course!",
                f"happy to help, {message.author.mention}!",
                "you are very welcome!"
            ]
            await message.channel.send(random.choice(responses))
            return

        goodbye_triggers = [
            "bye", "goodbye", "byee", "cya", "later", "laters", 
            "night", "gn", "toodles", "peace", "adios", "farewell"
        ]
        
        if any(w in words for w in goodbye_triggers) or "see ya" in content:
            responses = [
                f"goodbye, {message.author.mention}!",
                "later!",
                f"have a good day, {message.author.mention}!",
                "toodles!",
                "catch you on the flip side!",
                "sleep well!"
            ]
            await message.channel.send(random.choice(responses))
            return

        if random.random() < 0.01:
            responses = [
                "huh?",
                f"are you talking about me, {message.author.mention}?",
                "what?",
                "that's me!",
                "did someone say my name?"
            ]
            await message.channel.send(random.choice(responses))

async def setup(bot):
    await bot.add_cog(Chat(bot))
