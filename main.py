import discord
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from database import init_db

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class FlickerBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None)

    async def setup_hook(self):
        """This runs when the bot starts up."""
        await init_db()
        print("Database initialized.")

        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and filename != "__init__.py":
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f"⚙️  Loaded extension: {filename}")

bot = FlickerBot()

@bot.event
async def on_ready():
    print(f'{bot.user} is online and ready!')
    print('--------------------------------------')

if __name__ == '__main__':
    bot.run(TOKEN)
