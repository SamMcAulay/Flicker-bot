import discord
import random
import re
import json
from discord.ext import commands
from database import get_custom_responses, get_response_groups


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        content = message.content.lower()

        words = set(re.findall(r"\w+", content))

        if "flicker" not in words:
            return

        guild_id = message.guild.id if message.guild else None

        # Check custom response groups
        if guild_id:
            groups = await get_response_groups(guild_id)
            for (_, name, triggers_json, responses_json, enabled) in groups:
                if not enabled:
                    continue
                triggers = set(json.loads(triggers_json))
                responses = json.loads(responses_json)
                if words & triggers and responses:
                    response = random.choice(responses).replace("@user", message.author.mention)
                    await message.channel.send(response)
                    return

        # Check legacy custom responses
        if guild_id:
            custom_responses = await get_custom_responses(guild_id)
            for (_, trigger_words_str, response_text) in custom_responses:
                triggers = {t.strip().lower() for t in trigger_words_str.split(",") if t.strip()}
                if words & triggers:
                    await message.channel.send(response_text.replace("@user", message.author.mention))
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

    @commands.command(name="help")
    async def help_command(self, ctx):
        await ctx.send("Need help? Check out the Flicker guide here: https://flicker-bot.com/guide")


async def setup(bot):
    await bot.add_cog(Chat(bot))
