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

        # ---------------------------------------------------------
        # 1. "FLICKER KILL HIM" (Violent/Unhinged Robot Responses)
        # ---------------------------------------------------------
        kill_triggers = [
            "flicker kill", "flicker destroy", "flicker eliminate", 
            "flicker murder", "flicker attack", "flicker smite"
        ]
        
        if any(trigger in content for trigger in kill_triggers):
            responses = [
                "*blasters charging* Target locked. Commencing orbital strike.",
                "I will grind their bones into Stardust!",
                "*safety protocols disabled* Peace was never an option.",
                "Initiating doom sequence on target's coordinates...",
                "I may be cute, but these robotic hands are rated E for Everyone.",
                "*error 404* Mercy module not found. Eradicating target."
            ]
            await message.channel.send(random.choice(responses))
            return


        # ---------------------------------------------------------
        # 2. "BRING HIM TO TRIAL" (Space Judge Responses)
        # ---------------------------------------------------------
        trial_triggers = [
            "bring him to trial", "bring them to trial", "flicker arrest", 
            "space jail", "flicker judge", "lock him up", "lock them up"
        ]

        if any(trigger in content for trigger in trial_triggers):
            responses = [
                "Order in the space court! I find the defendant... guilty of not having enough Stardust!",
                "*bangs tiny holographic gavel* The council of stars will decide your fate!",
                "WEE WOO WEE WOO Space police Flicker is on the case! Please step into the cozy timeout forcefield.",
                "*scanning space laws...* Ah yes, violation of galactic vibes. Straight to space jail!",
                "You have the right to remain shiny! Anything you say can and will be used to generate Stardust!"
            ]
            await message.channel.send(random.choice(responses))
            return


        # ---------------------------------------------------------
        # 3. "FACT CHECK THIS" (Computer Processing Responses)
        # ---------------------------------------------------------
        fact_triggers = [
            "flicker fact check", "flicker can we get a fact check", 
            "flicker is that true", "flicker verify", "flicker cap or no cap",
            "fact check this flicker"
        ]

        if any(trigger in content for trigger in fact_triggers):
            responses = [
                "*scanning databanks...* Hmm, my scanners say this is 100% nonsense!",
                "*beep boop* Calculating... Yes, the math checks out! Probably!",
                "According to the Galactic Encyclopedia... I actually have no idea! 🌌✨",
                "*processing...* ERROR: Fact not found.",
                "Hold on, let me ask the internet... 🌐 *dial-up noises* ...my sources say 'maybe'.",
                "Fact check complete: 🟢 True! (Disclaimer: Flicker's facts may be heavily influenced by who gives him the most head pats)."
            ]
            await message.channel.send(random.choice(responses))
            return

        # ---------------------------------------------------------
        # 4. LOVE TRIGGERS
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # 5. GREETING TRIGGERS
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # 6. GRATITUDE TRIGGERS
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # 7. GOODBYE TRIGGERS
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # 8. DEFAULT RANDOM RESPONSE (1% Chance)
        # ---------------------------------------------------------
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