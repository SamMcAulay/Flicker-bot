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

        def _replace(text: str) -> str:
            return (
                text
                .replace("{user}", member.mention)
                .replace("{username}", member.display_name)
                .replace("{server}", member.guild.name)
                .replace("{count}", str(member.guild.member_count))
            )

        message = _replace(wc.get("message", "Welcome {user} to **{server}**!"))

        if wc.get("use_embed", True):
            color_hex = wc.get("embed_color", "#5b8ef7")
            try:
                color = discord.Color(int(color_hex.lstrip("#"), 16))
            except Exception:
                color = discord.Color.blurple()

            title = wc.get("embed_title", "")
            if title:
                title = _replace(title)

            embed = discord.Embed(
                title=title or None,
                description=message,
                color=color,
            )

            # Avatar thumbnail (default on)
            if wc.get("embed_thumbnail", True):
                embed.set_thumbnail(url=member.display_avatar.url)

            # Optional footer
            footer = wc.get("embed_footer", "")
            if footer:
                embed.set_footer(text=_replace(footer))

            # Optional large image
            image_url = wc.get("embed_image_url", "")
            if image_url:
                embed.set_image(url=image_url)

            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass
        else:
            try:
                await channel.send(message)
            except discord.Forbidden:
                pass


async def setup(bot):
    await bot.add_cog(Welcome(bot))
