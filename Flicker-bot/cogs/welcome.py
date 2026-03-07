import discord
from discord.ext import commands
from database import get_server_settings


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings = await get_server_settings(member.guild.id)
        wc = settings.get("welcome_config", {})

        if not wc.get("enabled", False):
            return

        channel_id = wc.get("channel_id")
        if not channel_id:
            return

        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return

        message = wc.get("message", "Welcome to **{server}**, {user}! 🎉")
        message = (
            message
            .replace("{user}", member.mention)
            .replace("{username}", member.display_name)
            .replace("{server}", member.guild.name)
            .replace("{count}", str(member.guild.member_count))
        )

        if wc.get("use_embed", False):
            color_hex = wc.get("embed_color", "#5865F2")
            try:
                color = discord.Color(int(color_hex.lstrip("#"), 16))
            except Exception:
                color = discord.Color.blurple()

            title = wc.get("embed_title", "")
            if title:
                title = (
                    title
                    .replace("{username}", member.display_name)
                    .replace("{server}", member.guild.name)
                )

            embed = discord.Embed(
                title=title or None,
                description=message,
                color=color,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)
        else:
            await channel.send(message)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
