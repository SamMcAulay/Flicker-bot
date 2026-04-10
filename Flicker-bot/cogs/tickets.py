import discord
import asyncio
import io
import json
import re
import time
from datetime import datetime, timezone
from discord.ext import commands
from database import (
    get_ticket_config,
    upsert_ticket_config,
    increment_ticket_number,
    get_ticket_panels,
    get_ticket_panel,
    get_all_ticket_panel_ids,
    get_ticket_categories,
    create_support_ticket,
    get_support_ticket_by_channel,
    claim_support_ticket,
    close_support_ticket,
    get_open_ticket_count,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BUTTON_STYLES = {
    1: discord.ButtonStyle.blurple,
    2: discord.ButtonStyle.grey,
    3: discord.ButtonStyle.green,
    4: discord.ButtonStyle.red,
}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:20]


def _build_panel_embed(panel: dict, categories: list) -> discord.Embed:
    embed = discord.Embed(
        title=panel["title"],
        description=panel["description"],
        color=panel["color"],
    )
    if categories:
        lines = []
        for cat in categories:
            lines.append(f"{cat['emoji']} **{cat['name']}**" + (f" — {cat['description']}" if cat["description"] else ""))
        embed.add_field(name="Categories", value="\n".join(lines), inline=False)
    embed.set_footer(text="Click the button below to open a ticket.")
    return embed


def _build_ticket_embed(ticket_number: int, user: discord.Member,
                        category: dict, claimed_by: discord.Member = None) -> discord.Embed:
    embed = discord.Embed(
        title=f"Ticket #{ticket_number:04d}",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Opened By", value=user.mention, inline=True)
    embed.add_field(name="Category", value=f"{category['emoji']} {category['name']}", inline=True)
    if claimed_by:
        embed.add_field(name="Claimed By", value=claimed_by.mention, inline=True)
    else:
        embed.add_field(name="Claimed By", value="*Unclaimed*", inline=True)
    if category.get("opening_message"):
        embed.add_field(name="Info", value=category["opening_message"], inline=False)
    embed.set_footer(text="Use the buttons below to claim or close this ticket.")
    return embed


async def _generate_html_transcript(channel: discord.TextChannel) -> str:
    guild_name = channel.guild.name if channel.guild else "Unknown"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    messages_html = []
    async for msg in channel.history(limit=None, oldest_first=True):
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        avatar = msg.author.display_avatar.url if msg.author.display_avatar else ""
        name = msg.author.display_name
        color = "#5b8ef7" if msg.author.bot else "#e2e8f8"

        content = msg.content or ""
        # Basic markdown: bold, italic, code
        content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
        content = re.sub(r"\*(.+?)\*", r"<em>\1</em>", content)
        content = re.sub(r"`(.+?)`", r"<code>\1</code>", content)
        content = content.replace("\n", "<br>")

        attachments = ""
        for att in msg.attachments:
            if att.content_type and att.content_type.startswith("image/"):
                attachments += f'<div style="margin-top:6px;"><img src="{att.url}" style="max-width:400px;max-height:300px;border-radius:6px;"></div>'
            else:
                attachments += f'<div style="margin-top:4px;"><a href="{att.url}" style="color:#82aeff;">{att.filename}</a></div>'

        embeds_html = ""
        for emb in msg.embeds:
            emb_color = f"#{emb.color.value:06x}" if emb.color else "#5b8ef7"
            emb_parts = []
            if emb.title:
                emb_parts.append(f'<div style="font-weight:700;">{emb.title}</div>')
            if emb.description:
                emb_parts.append(f'<div style="margin-top:4px;">{emb.description}</div>')
            for field in emb.fields:
                emb_parts.append(f'<div style="margin-top:6px;"><strong>{field.name}:</strong> {field.value}</div>')
            embeds_html += f'<div style="border-left:3px solid {emb_color};padding:8px 12px;margin-top:6px;background:#111425;border-radius:4px;">{"".join(emb_parts)}</div>'

        messages_html.append(f"""
        <div style="display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #1d2338;">
            <img src="{avatar}" style="width:40px;height:40px;border-radius:50%;flex-shrink:0;" onerror="this.style.display='none'">
            <div style="min-width:0;">
                <div>
                    <span style="font-weight:700;color:{color};">{name}</span>
                    <span style="color:#3f4d78;font-size:12px;margin-left:8px;">{ts}</span>
                </div>
                <div style="margin-top:4px;color:#c8d0e8;word-break:break-word;">{content}</div>
                {attachments}
                {embeds_html}
            </div>
        </div>""")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Transcript — {channel.name}</title>
<style>
    body {{ background:#0b0d1a; color:#e2e8f8; font-family:'Segoe UI',system-ui,sans-serif; margin:0; padding:24px; font-size:14px; }}
    a {{ color:#82aeff; }}
    code {{ background:#171c30; padding:2px 5px; border-radius:3px; font-size:13px; }}
    .header {{ border-bottom:2px solid #232847; padding-bottom:16px; margin-bottom:16px; }}
    .header h1 {{ margin:0 0 4px; color:#5b8ef7; font-size:20px; }}
    .header p {{ margin:2px 0; color:#7b8fc0; font-size:13px; }}
</style></head>
<body>
    <div class="header">
        <h1>#{channel.name}</h1>
        <p>{guild_name} &mdash; Transcript generated {now}</p>
        <p>{len(messages_html)} messages</p>
    </div>
    {"".join(messages_html)}
</body></html>"""


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class TicketPanelView(discord.ui.View):
    """Persistent view attached to panel embeds. One instance per panel."""

    def __init__(self, panel_id: int = 0, label: str = "Open Ticket",
                 emoji: str = "🎫", style: int = 1):
        super().__init__(timeout=None)
        btn = discord.ui.Button(
            label=label,
            emoji=emoji,
            style=BUTTON_STYLES.get(style, discord.ButtonStyle.blurple),
            custom_id=f"supportticket:open:{panel_id}",
        )
        btn.callback = self._open_ticket
        self.add_item(btn)

    async def _open_ticket(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        panel_id = int(custom_id.split(":")[2])

        panel = await get_ticket_panel(panel_id)
        if not panel:
            return await interaction.response.send_message("This ticket panel no longer exists.", ephemeral=True)

        config = await get_ticket_config(interaction.guild_id)
        if not config.get("enabled"):
            return await interaction.response.send_message("The ticket system is currently disabled.", ephemeral=True)

        categories = panel.get("categories", [])
        if not categories:
            return await interaction.response.send_message("No ticket categories have been configured for this panel.", ephemeral=True)

        if len(categories) == 1:
            cat = categories[0]
            # Check ticket limit
            if cat["ticket_limit"] > 0:
                open_count = await get_open_ticket_count(interaction.user.id, cat["id"])
                if open_count >= cat["ticket_limit"]:
                    return await interaction.response.send_message(
                        f"You already have {open_count} open ticket(s) in **{cat['name']}**. Close an existing ticket first.",
                        ephemeral=True,
                    )
            # If form fields, show modal
            if cat.get("form_fields") and len(cat["form_fields"]) > 0:
                modal = TicketFormModal(cat, config, panel_id)
                return await interaction.response.send_modal(modal)
            # Otherwise create ticket directly
            await interaction.response.defer(ephemeral=True)
            await _create_ticket(interaction, cat, config, panel_id)
        else:
            # Show category select
            view = TicketCategorySelect(categories, config, panel_id)
            await interaction.response.send_message(
                "Select a ticket category:", view=view, ephemeral=True,
            )


class TicketCategorySelect(discord.ui.View):
    """Ephemeral select menu for multi-category panels."""

    def __init__(self, categories: list, config: dict, panel_id: int):
        super().__init__(timeout=60)
        self.config = config
        self.panel_id = panel_id
        self.categories = {str(c["id"]): c for c in categories}

        options = []
        for cat in categories:
            options.append(discord.SelectOption(
                label=cat["name"],
                value=str(cat["id"]),
                emoji=cat["emoji"] or None,
                description=(cat["description"] or "")[:100] or None,
            ))

        select = discord.ui.Select(
            placeholder="Choose a category...",
            options=options,
            custom_id="supportticket:catselect",
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        cat_id = interaction.data["values"][0]
        cat = self.categories[cat_id]

        if cat["ticket_limit"] > 0:
            open_count = await get_open_ticket_count(interaction.user.id, cat["id"])
            if open_count >= cat["ticket_limit"]:
                return await interaction.response.send_message(
                    f"You already have {open_count} open ticket(s) in **{cat['name']}**. Close an existing ticket first.",
                    ephemeral=True,
                )

        if cat.get("form_fields") and len(cat["form_fields"]) > 0:
            modal = TicketFormModal(cat, self.config, self.panel_id)
            return await interaction.response.send_modal(modal)

        await interaction.response.defer(ephemeral=True)
        await _create_ticket(interaction, cat, self.config, self.panel_id)


class TicketFormModal(discord.ui.Modal):
    """Dynamic modal built from a category's form_fields JSON."""

    def __init__(self, category: dict, config: dict, panel_id: int):
        super().__init__(title=f"Open {category['name']} Ticket"[:45])
        self.category = category
        self.config = config
        self.panel_id = panel_id
        self._fields = []

        for field in (category.get("form_fields") or [])[:5]:
            style = discord.TextStyle.paragraph if field.get("style") == "paragraph" else discord.TextStyle.short
            ti = discord.ui.TextInput(
                label=field.get("label", "Question")[:45],
                style=style,
                required=field.get("required", True),
                placeholder=field.get("placeholder", "")[:100] or None,
                max_length=1024,
            )
            self._fields.append(ti)
            self.add_item(ti)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        answers = [(f.label, f.value) for f in self._fields]
        await _create_ticket(interaction, self.category, self.config, self.panel_id, answers)


class TicketControlView(discord.ui.View):
    """Persistent claim + close buttons on the opening message inside a ticket channel."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green, emoji="🙋",
                       custom_id="supportticket:claim")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = await get_support_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("Ticket not found.", ephemeral=True)

        if ticket["claimed_by"]:
            claimer = interaction.guild.get_member(ticket["claimed_by"])
            name = claimer.display_name if claimer else f"User {ticket['claimed_by']}"
            return await interaction.response.send_message(
                f"This ticket is already claimed by **{name}**.", ephemeral=True,
            )

        # Check if user is staff (has a staff role for the ticket's category)
        panel = await get_ticket_panel(ticket["panel_id"])
        cat = None
        if panel:
            for c in panel.get("categories", []):
                if c["id"] == ticket["category_id"]:
                    cat = c
                    break

        staff_roles = cat.get("staff_roles", []) if cat else []
        user_role_ids = {r.id for r in interaction.user.roles}
        is_staff = not staff_roles or any(r in user_role_ids for r in staff_roles) or interaction.user.guild_permissions.administrator

        if not is_staff:
            return await interaction.response.send_message("You don't have a staff role for this ticket category.", ephemeral=True)

        await claim_support_ticket(interaction.channel.id, interaction.user.id)

        config = await get_ticket_config(interaction.guild_id)

        # If claim_lock, remove send_messages from ticket creator
        if config.get("claim_lock"):
            creator = interaction.guild.get_member(ticket["user_id"])
            # Only lock out other staff, not the creator
            # Actually claim_lock means only claimer can respond
            # Set channel so only claimer + creator + bot can send
            overwrites = interaction.channel.overwrites
            for target, overwrite in list(overwrites.items()):
                if isinstance(target, discord.Role) and target.id in staff_roles:
                    overwrite.send_messages = False
                    await interaction.channel.set_permissions(target, overwrite=overwrite)
            await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=True)

        # Edit the opening embed
        if cat:
            new_embed = _build_ticket_embed(
                ticket["ticket_number"], interaction.guild.get_member(ticket["user_id"]) or interaction.user,
                cat, claimed_by=interaction.user,
            )
            try:
                msg = await interaction.channel.fetch_message(interaction.message.id)
                await msg.edit(embed=new_embed)
            except Exception:
                pass

        await interaction.response.send_message(
            f"🙋 **{interaction.user.display_name}** claimed this ticket.", ephemeral=False,
        )

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, emoji="🔒",
                       custom_id="supportticket:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = await get_support_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("Ticket not found.", ephemeral=True)

        view = TicketCloseConfirmView()
        await interaction.response.send_message(
            "Are you sure you want to close this ticket?", view=view, ephemeral=True,
        )


class TicketCloseConfirmView(discord.ui.View):
    """Ephemeral confirmation before closing."""

    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.red, emoji="🔒")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()

        ticket = await get_support_ticket_by_channel(interaction.channel.id)
        if not ticket or ticket["status"] == "closed":
            return

        config = await get_ticket_config(interaction.guild_id)

        # Generate HTML transcript
        transcript_html = await _generate_html_transcript(interaction.channel)
        transcript_file = discord.File(
            io.BytesIO(transcript_html.encode("utf-8")),
            filename=f"transcript-{interaction.channel.name}.html",
        )

        transcript_url = ""

        # Send to log channel
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title=f"Ticket #{ticket['ticket_number']:04d} Closed",
                    color=discord.Color.red(),
                )
                log_embed.add_field(name="Opened By", value=f"<@{ticket['user_id']}>", inline=True)
                log_embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
                if ticket["claimed_by"]:
                    log_embed.add_field(name="Claimed By", value=f"<@{ticket['claimed_by']}>", inline=True)
                log_embed.add_field(name="Channel", value=interaction.channel.name, inline=False)
                log_msg = await log_channel.send(embed=log_embed, file=transcript_file)
                if log_msg.attachments:
                    transcript_url = log_msg.attachments[0].url

        # DM transcript to creator
        if config.get("dm_transcript"):
            creator = interaction.guild.get_member(ticket["user_id"])
            if creator:
                try:
                    dm_file = discord.File(
                        io.BytesIO(transcript_html.encode("utf-8")),
                        filename=f"transcript-{interaction.channel.name}.html",
                    )
                    dm_embed = discord.Embed(
                        title=f"Ticket #{ticket['ticket_number']:04d} — Transcript",
                        description=f"Your ticket in **{interaction.guild.name}** has been closed.",
                        color=discord.Color.blurple(),
                    )
                    await creator.send(embed=dm_embed, file=dm_file)
                except discord.Forbidden:
                    pass

        await close_support_ticket(interaction.channel.id, interaction.user.id, transcript_url)

        await interaction.channel.send("🔒 This ticket has been closed. Channel will be deleted in 5 seconds...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except Exception:
            pass

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Close cancelled.", ephemeral=True)
        self.stop()


# ---------------------------------------------------------------------------
# Ticket creation helper
# ---------------------------------------------------------------------------

async def _create_ticket(interaction: discord.Interaction, category: dict,
                         config: dict, panel_id: int, form_answers: list = None):
    guild = interaction.guild

    # Get or create the ticket category (Discord channel category)
    category_channel = None
    if config.get("category_id"):
        category_channel = guild.get_channel(config["category_id"])

    if not category_channel:
        # Auto-create a "Tickets" category
        category_channel = discord.utils.get(guild.categories, name="Tickets")
        if not category_channel:
            category_channel = await guild.create_category("Tickets")
        await upsert_ticket_config(guild.id, category_id=category_channel.id)

    # Increment ticket number
    ticket_number = await increment_ticket_number(guild.id)

    # Build channel name
    fmt = config.get("naming_format", "ticket-{number}")
    channel_name = fmt.replace("{number}", f"{ticket_number:04d}")
    channel_name = channel_name.replace("{category}", _slugify(category["name"]))
    channel_name = channel_name.replace("{username}", _slugify(interaction.user.display_name))
    channel_name = _slugify(channel_name) or f"ticket-{ticket_number:04d}"

    # Build permission overwrites
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
    }
    for role_id in category.get("staff_roles", []):
        role = guild.get_role(role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)

    # Create channel
    ticket_channel = await category_channel.create_text_channel(
        name=channel_name,
        overwrites=overwrites,
        topic=f"Ticket #{ticket_number:04d} — {category['name']} — Opened by {interaction.user.display_name}",
    )

    # Insert ticket record
    await create_support_ticket(
        guild.id, ticket_channel.id, interaction.user.id,
        category["id"], panel_id, ticket_number,
    )

    # Send opening embed
    embed = _build_ticket_embed(ticket_number, interaction.user, category)
    await ticket_channel.send(
        content=f"{interaction.user.mention} welcome to your ticket!",
        embed=embed,
        view=TicketControlView(),
    )

    # Send form answers if any
    if form_answers:
        answers_embed = discord.Embed(
            title="Submitted Information",
            color=discord.Color.blurple(),
        )
        for label, value in form_answers:
            answers_embed.add_field(name=label, value=value or "*No response*", inline=False)
        await ticket_channel.send(embed=answers_embed)

    await interaction.followup.send(
        f"Your ticket has been opened: {ticket_channel.mention}", ephemeral=True,
    )


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class SupportTickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Register persistent control view (claim/close — shared custom_id)
        self.bot.add_view(TicketControlView())

        # Register a TicketPanelView per panel so buttons survive restarts
        panel_ids = await get_all_ticket_panel_ids()
        for pid in panel_ids:
            panel = await get_ticket_panel(pid)
            if panel:
                self.bot.add_view(TicketPanelView(
                    panel_id=panel["id"],
                    label=panel["button_label"],
                    emoji=panel["button_emoji"],
                    style=panel["button_style"],
                ))
        print(f"🎫 Support Ticket System Loaded. ({len(panel_ids)} panels registered)")

    @commands.command(name="ticket-setup")
    @commands.has_permissions(administrator=True)
    async def ticket_setup(self, ctx):
        """Quick setup: creates Tickets category + log channel, enables the system."""
        guild = ctx.guild
        config = await get_ticket_config(guild.id)

        # Category
        category_channel = guild.get_channel(config["category_id"]) if config["category_id"] else None
        if not category_channel:
            category_channel = discord.utils.get(guild.categories, name="Tickets")
            if not category_channel:
                category_channel = await guild.create_category("Tickets")

        # Log channel
        log_channel = guild.get_channel(config["log_channel_id"]) if config["log_channel_id"] else None
        if not log_channel:
            log_channel = discord.utils.get(guild.text_channels, name="ticket-logs")
            if not log_channel:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                }
                log_channel = await guild.create_text_channel("ticket-logs", overwrites=overwrites)

        await upsert_ticket_config(
            guild.id,
            enabled=1,
            category_id=category_channel.id,
            log_channel_id=log_channel.id,
        )

        embed = discord.Embed(
            title="🎫 Ticket System Setup Complete",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Category", value=category_channel.mention, inline=True)
        embed.add_field(name="Log Channel", value=log_channel.mention, inline=True)
        embed.add_field(name="Status", value="Enabled", inline=True)
        embed.set_footer(text="Use the dashboard to create ticket panels and categories.")
        await ctx.send(embed=embed)

    @commands.command(name="ticket-panel")
    @commands.has_permissions(administrator=True)
    async def ticket_panel_cmd(self, ctx, channel: discord.TextChannel = None):
        """Post a ticket panel in the specified channel (or current channel)."""
        channel = channel or ctx.channel

        config = await get_ticket_config(ctx.guild.id)
        if not config.get("enabled"):
            return await ctx.send("The ticket system is not enabled. Run `!ticket-setup` first.")

        panels = await get_ticket_panels(ctx.guild.id)
        # Find panels for this channel that have categories
        # If none, prompt user to use dashboard
        # For quick setup, create a default panel with one category

        view = _QuickPanelTriggerView(channel, self.bot)
        await ctx.send("Click the button below to set up a ticket panel:", view=view)


class _QuickPanelTriggerView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel, bot):
        super().__init__(timeout=120)
        self.channel = channel
        self.bot = bot

    @discord.ui.button(label="Create Panel", style=discord.ButtonStyle.blurple, emoji="🎫")
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = _QuickPanelModal(self.channel, self.bot)
        await interaction.response.send_modal(modal)
        self.stop()


class _QuickPanelModal(discord.ui.Modal, title="Create Ticket Panel"):
    panel_title = discord.ui.TextInput(label="Panel Title", default="Support Tickets", max_length=256)
    panel_desc = discord.ui.TextInput(label="Panel Description", style=discord.TextStyle.paragraph,
                                      default="Click the button below to open a ticket.", max_length=2048)
    cat_name = discord.ui.TextInput(label="Category Name", default="General Support", max_length=100)
    cat_desc = discord.ui.TextInput(label="Category Description", required=False, max_length=200,
                                    placeholder="Brief description shown in the select menu")

    def __init__(self, channel: discord.TextChannel, bot):
        super().__init__()
        self.channel = channel
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        from database import create_ticket_panel as db_create_panel, create_ticket_category as db_create_cat

        # Post the panel embed first with a placeholder message
        panel_data = {
            "title": self.panel_title.value,
            "description": self.panel_desc.value,
            "color": 5865207,
            "button_label": "Open Ticket",
            "button_emoji": "🎫",
            "button_style": 1,
        }

        # We need the panel_id for the view, so create DB entry with temp message_id
        panel_id = await db_create_panel(
            interaction.guild_id, self.channel.id, 0,
            panel_data["title"], panel_data["description"], panel_data["color"],
            panel_data["button_label"], panel_data["button_emoji"], panel_data["button_style"],
        )

        # Create the category
        await db_create_cat(
            panel_id, self.cat_name.value, "📩",
            self.cat_desc.value or "", "", [], 1, [],
        )

        # Build the embed and view
        panel = await get_ticket_panel(panel_id)
        embed = _build_panel_embed(panel, panel["categories"])
        view = TicketPanelView(
            panel_id=panel_id,
            label=panel_data["button_label"],
            emoji=panel_data["button_emoji"],
            style=panel_data["button_style"],
        )

        msg = await self.channel.send(embed=embed, view=view)

        # Update message_id in DB
        from database import update_ticket_panel as db_update_panel
        await db_update_panel(panel_id, message_id=msg.id)

        # Register persistent view
        self.bot.add_view(view)

        await interaction.followup.send(
            f"Ticket panel created in {self.channel.mention} with category **{self.cat_name.value}**.",
        )


async def setup(bot):
    await bot.add_cog(SupportTickets(bot))
