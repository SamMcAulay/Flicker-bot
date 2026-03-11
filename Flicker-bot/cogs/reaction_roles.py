import discord
from discord.ext import commands
from database import get_reaction_role_panel_by_message


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Cache: message_id (int) -> panel dict | None
        self._panel_cache: dict = {}

    async def _get_panel(self, message_id: int) -> dict | None:
        if message_id in self._panel_cache:
            return self._panel_cache[message_id]
        panel = await get_reaction_role_panel_by_message(message_id)
        # Cache even None results to avoid repeated DB hits for non-panel messages
        self._panel_cache[message_id] = panel
        return panel

    def invalidate_cache(self, message_id: int):
        """Called by the API handler whenever a panel or its entries change."""
        self._panel_cache.pop(message_id, None)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return
        if payload.user_id == self.bot.user.id:
            return

        panel = await self._get_panel(payload.message_id)
        if not panel:
            return

        emoji_str = str(payload.emoji)
        entry = next((e for e in panel["entries"] if e["emoji"] == emoji_str), None)
        if not entry:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        role = guild.get_role(entry["role_id"])
        if not role:
            return

        member = guild.get_member(payload.user_id)
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except (discord.NotFound, discord.HTTPException):
                return

        try:
            await member.add_roles(role, reason="Reaction role")
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return
        if payload.user_id == self.bot.user.id:
            return

        panel = await self._get_panel(payload.message_id)
        if not panel:
            return

        emoji_str = str(payload.emoji)
        entry = next((e for e in panel["entries"] if e["emoji"] == emoji_str), None)
        if not entry:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        role = guild.get_role(entry["role_id"])
        if not role:
            return

        member = guild.get_member(payload.user_id)
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except (discord.NotFound, discord.HTTPException):
                return

        try:
            await member.remove_roles(role, reason="Reaction role removed")
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
