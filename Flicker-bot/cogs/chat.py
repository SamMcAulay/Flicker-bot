import discord
import random
import re
from discord.ext import commands
from database import get_custom_responses


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.kill_words = {
            "kill",
            "destroy",
            "eliminate",
            "murder",
            "attack",
            "smite",
            "stab",
            "shoot",
            "beat",
            "fight",
        }
        self.trial_words = {
            "trial",
            "arrest",
            "jail",
            "judge",
            "court",
            "prison",
            "sue",
            "lawyer",
            "cop",
            "police",
            "guilty",
        }
        self.fact_words = {
            "fact",
            "verify",
            "true",
            "false",
            "real",
            "fake",
            "source",
        }
        self.love_words = {
            "ily",
            "love",
            "luv",
            "heart",
            "adore",
            "wub",
            "cute",
            "sweet",
        }
        self.greet_words = {
            "hi",
            "hello",
            "hey",
            "heyy",
            "yo",
            "sup",
            "greetings",
            "howdy",
            "hiya",
            "hola",
            "bonjour",
            "heya",
        }
        self.thanks_words = {
            "thank",
            "thanks",
            "thx",
            "ty",
            "tysm",
            "appreciate",
            "cheers",
            "gracias",
        }
        self.bye_words = {
            "bye",
            "goodbye",
            "cya",
            "later",
            "night",
            "gn",
            "peace",
            "adios",
            "farewell",
            "sleep",
        }

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        content = message.content.lower()

        words = set(re.findall(r"\w+", content))

        if "flicker" not in words:
            return

        if words & self.kill_words:
            responses = [
                "*blasters charging* Target locked. Commencing orbital strike. ",
                "I will grind their bones into Stardust! ",
                "*safety protocols disabled* Peace was never an option. ",
                "Initiating doom sequence on target's coordinates... ",
                "I may be cute, but these robotic hands are rated E for Everyone. ",
                "*error 404* Mercy module not found. Eradicating target. ",
            ]
            await message.channel.send(random.choice(responses))
            return

        if words & self.trial_words:
            responses = [
                "Order in the space court! I find the defendant... guilty of not having enough Stardust!",
                "*bangs tiny holographic gavel* The council of stars will decide your fate! ",
                "WEE WOO WEE WOO Space police Flicker is on the case! Please step into the cozy timeout forcefield.",
                "*scanning space laws...* Ah yes, violation of galactic vibes. Straight to space jail!",
                "You have the right to remain shiny! Anything you say can and will be used to generate Stardust! ",
            ]
            await message.channel.send(random.choice(responses))
            return

        if words & self.fact_words:
            responses = [
                "*scanning databanks...* Hmm, my scanners say this is 100% cap.",
                "*beep boop* Calculating... Yes, the math checks out! Probably!",
                "According to the Galactic Encyclopedia... I actually have no idea!",
                "*processing...*ERROR: Fact not found. Proceeding with vibes instead.",
                "Hold on, let me ask the internet...*dial-up noises* ...my sources say 'maybe'.",
                "Fact check complete: True! (Disclaimer: Flicker's facts may be heavily influenced by who gives him the most head pats).",
            ]
            await message.channel.send(random.choice(responses))
            return

        if words & self.love_words or "<3" in content:
            responses = [
                f"aww thank you, {message.author.mention}!",
                "no problem!",
                f"you're sweet, {message.author.mention}!",
                "right back at you! ❤️",
                "aww shucks! ❤️",
            ]
            await message.channel.send(random.choice(responses))
            return

        if words & self.thanks_words:
            responses = [
                f"no problem, {message.author.mention}!",
                "anytime!",
                "of course!",
                f"happy to help, {message.author.mention}!",
                "you are very welcome!",
            ]
            await message.channel.send(random.choice(responses))
            return

        if words & self.bye_words or "see ya" in content:
            responses = [
                f"goodbye, {message.author.mention}!",
                "later!",
                f"have a good day, {message.author.mention}!",
                "toodles!",
                "catch you on the flip side!",
                "sleep well!",
            ]
            await message.channel.send(random.choice(responses))
            return

        if words & self.greet_words:
            if random.random() < 0.01:
                response = f"I've been thinking about you, {message.author.mention}!"
            else:
                responses = [
                    f"hey there {message.author.mention}!",
                    f"hi {message.author.mention}!",
                    f"good to see you, {message.author.mention}!",
                    "beep boop! hello!",
                    "greetings, friend!",
                ]
                response = random.choice(responses)
            await message.channel.send(response)
            return

        # Check server-specific custom responses
        if message.guild:
            custom_responses = await get_custom_responses(message.guild.id)
            for (_, trigger_words_str, response_text) in custom_responses:
                triggers = {t.strip().lower() for t in trigger_words_str.split(",") if t.strip()}
                if words & triggers:
                    await message.channel.send(response_text)
                    return

        if random.random() < 0.01:
            responses = [
                "huh?",
                f"are you talking about me, {message.author.mention}?",
                "what?",
                "that's me!",
                "did someone say my name?",
            ]
            await message.channel.send(random.choice(responses))


async def setup(bot):
    await bot.add_cog(Chat(bot))
