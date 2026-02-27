import discord
import asyncio
import io
import re
from discord.ext import commands
from database import (
    get_balance, update_balance, get_chips, update_chips,
    is_listing_locked, lock_listing, unlock_listing,
    get_lock_details, create_shop_item, get_shop_item, decrement_stock
)

LOG_CHANNEL_ID = 1473785756219871463


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_prices(raw: str) -> tuple:
    """Parse 'stardust:100 chips:5000 usd:9.99' into (stardust, chips, usd)."""
    m = re.search(r"stardust[:\s]+(\d+)", raw, re.I)
    stardust = int(m.group(1)) if m else 0
    m = re.search(r"chips[:\s]+(\d+)", raw, re.I)
    chips = int(m.group(1)) if m else 0
    m = re.search(r"usd[:\s]+([\d.]+)", raw, re.I)
    usd = float(m.group(1)) if m else 0.0
    return stardust, chips, usd


# ---------------------------------------------------------------------------
# Modal
# ---------------------------------------------------------------------------

class ShopPostModal(discord.ui.Modal, title="Post Shop Listing"):
    item_title = discord.ui.TextInput(
        label="Title",
        placeholder="e.g. Cosmic Supporter Role",
        max_length=100,
    )
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )
    stock_input = discord.ui.TextInput(
        label="Stock",
        placeholder="1  |  inf  |  5",
        default="1",
        max_length=20,
    )
    prices_input = discord.ui.TextInput(
        label="Prices (omit any to disable)",
        placeholder="stardust:100  chips:5000  usd:9.99",
        max_length=100,
    )
    role_input = discord.ui.TextInput(
        label="Role ID for instant delivery (optional)",
        placeholder="Leave blank for manual ticket",
        required=False,
        max_length=25,
    )

    def __init__(self, target_channel: discord.TextChannel, image_url):
        super().__init__()
        self.target_channel = target_channel
        self.image_url = image_url

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # --- Parse stock ---
        raw_stock = self.stock_input.value.strip().lower()
        if raw_stock in ("inf", "infinity", "unlimited"):
            stock, stock_text = -1, "♾️ Unlimited"
        else:
            try:
                stock = int(raw_stock)
                stock_text = str(stock)
            except ValueError:
                return await interaction.followup.send("❌ Stock must be a number or 'inf'.", ephemeral=True)

        # --- Parse prices ---
        stardust_price, chips_price, usd_price = _parse_prices(self.prices_input.value)

        if stardust_price == 0 and chips_price == 0 and usd_price == 0.0:
            return await interaction.followup.send("❌ You must set at least one price.", ephemeral=True)

        # --- Parse role ---
        role_id = None
        if self.role_input.value.strip():
            try:
                role_id = int(self.role_input.value.strip())
            except ValueError:
                return await interaction.followup.send("❌ Role ID must be a number.", ephemeral=True)

        # --- Build embed ---
        embed = discord.Embed(
            title=self.item_title.value,
            description=self.description.value,
            color=discord.Color.purple(),
        )
        if self.image_url:
            embed.set_image(url=self.image_url)

        embed.add_field(name="📦 Stock", value=stock_text, inline=True)
        if stardust_price > 0:
            embed.add_field(name="✨ Stardust", value=f"{stardust_price:,}", inline=True)
        if chips_price > 0:
            embed.add_field(name="🎰 Chips", value=f"{chips_price:,}", inline=True)
        if usd_price > 0:
            embed.add_field(name="💵 USD", value=f"${usd_price:.2f}", inline=True)
        if role_id:
            embed.set_footer(text="✨ Instant Role Delivery")

        view = ShopView(stardust_price, chips_price, usd_price)
        msg = await self.target_channel.send(embed=embed, view=view)
        await create_shop_item(msg.id, stock, role_id, stardust_price, chips_price, usd_price)
        await interaction.followup.send(f"✅ Listing posted in {self.target_channel.mention}!", ephemeral=True)


# ---------------------------------------------------------------------------
# Shop View (persistent buttons)
# ---------------------------------------------------------------------------

class ShopView(discord.ui.View):
    def __init__(self, stardust_price: int = 1, chips_price: int = 1, usd_price: float = 1.0):
        super().__init__(timeout=None)
        # Remove buttons whose price is 0
        for child in self.children.copy():
            cid = getattr(child, "custom_id", None)
            if cid == "shop:btn_stardust" and stardust_price <= 0:
                self.remove_item(child)
            elif cid == "shop:btn_chips" and chips_price <= 0:
                self.remove_item(child)
            elif cid == "shop:btn_usd" and usd_price <= 0:
                self.remove_item(child)

    async def _handle_purchase(self, interaction: discord.Interaction, currency: str):
        """Shared purchase logic for all three currencies."""
        message_id = interaction.message.id
        user = interaction.user

        item = await get_shop_item(message_id)
        if not item:
            return await interaction.response.send_message(
                "⚠️ This listing is outdated. Ask staff to repost it.", ephemeral=True
            )

        stock, role_id, stardust_price, chips_price, usd_price = item

        price_map = {"stardust": stardust_price, "chips": chips_price, "usd": usd_price}
        price = price_map[currency]

        if price <= 0:
            return await interaction.response.send_message(
                f"❌ This item cannot be bought with {currency.capitalize()}.", ephemeral=True
            )
        if stock == 0:
            return await interaction.response.send_message("❌ **Sold Out!**", ephemeral=True)
        if role_id is None and await is_listing_locked(message_id) and stock == 1:
            return await interaction.response.send_message(
                "❌ **Busy!** Someone else is buying this right now.", ephemeral=True
            )

        # Balance check and deduction for automatic currencies
        if currency == "stardust":
            bal = await get_balance(user.id)
            if bal < price:
                return await interaction.response.send_message(
                    f"❌ You need **{price:,} Stardust** (you have {bal:,}).", ephemeral=True
                )
            await update_balance(user.id, -price)
        elif currency == "chips":
            bal = await get_chips(user.id)
            if bal < price:
                return await interaction.response.send_message(
                    f"❌ You need **{price:,} Chips** (you have {bal:,}).", ephemeral=True
                )
            await update_chips(user.id, -price)
        # USD: no automatic deduction — goes straight to ticket

        await decrement_stock(message_id)

        if role_id and currency != "usd":
            role = interaction.guild.get_role(role_id)
            if role:
                await user.add_roles(role)
                return await interaction.response.send_message(
                    f"✅ **Purchase Successful!** You received the **{role.name}** role.", ephemeral=True
                )
            return await interaction.response.send_message(
                "⚠️ Role no longer exists. Contact staff.", ephemeral=True
            )

        await self._create_ticket(interaction, user, message_id, price, currency)

    async def _create_ticket(self, interaction, user, message_id, price, currency):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Orders")
        if not category:
            category = await guild.create_category("Orders")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True),
        }

        label = {"stardust": "order", "chips": "order", "usd": "inquiry"}[currency]
        ticket_channel = await guild.create_text_channel(
            f"{label}-{user.name}", category=category, overwrites=overwrites
        )
        await lock_listing(message_id, ticket_channel.id, user.id, interaction.channel.id)

        symbols = {"stardust": "✨", "chips": "🎰", "usd": "💵"}
        paid_text = {
            "stardust": f"{price:,} Stardust",
            "chips":    f"{price:,} Chips",
            "usd":      f"${price:.2f} USD",
        }[currency]
        footer = (
            "Staff will process your order shortly."
            if currency != "usd"
            else "Please wait for staff to provide payment details."
        )

        embed = discord.Embed(
            title=f"{symbols[currency]} Order {label.capitalize()}",
            description=f"**Buyer:** {user.mention}\n**Price:** {paid_text}\n**Item:** [View Listing]({interaction.message.jump_url})",
            color=discord.Color.green(),
        )
        embed.set_footer(text=footer)
        await ticket_channel.send(f"{user.mention}", embed=embed, view=TicketCloseView())
        await interaction.response.send_message(
            f"✅ Ticket opened: {ticket_channel.mention}", ephemeral=True
        )

    @discord.ui.button(label="Buy with Stardust", style=discord.ButtonStyle.blurple, emoji="✨", custom_id="shop:btn_stardust")
    async def btn_stardust(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_purchase(interaction, "stardust")

    @discord.ui.button(label="Buy with Chips", style=discord.ButtonStyle.blurple, emoji="🎰", custom_id="shop:btn_chips")
    async def btn_chips(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_purchase(interaction, "chips")

    @discord.ui.button(label="Buy with USD", style=discord.ButtonStyle.green, emoji="💵", custom_id="shop:btn_usd")
    async def btn_usd(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_purchase(interaction, "usd")


# ---------------------------------------------------------------------------
# Ticket Views
# ---------------------------------------------------------------------------

class AdminCloseView(discord.ui.View):
    def __init__(self, message_id, shop_channel_id):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.shop_channel_id = shop_channel_id

    @discord.ui.button(label="Yes! Delete Shop Post", style=discord.ButtonStyle.red, emoji="🗑️")
    async def delete_post(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            shop_channel = interaction.guild.get_channel(self.shop_channel_id)
            if shop_channel:
                msg = await shop_channel.fetch_message(self.message_id)
                await msg.delete()
        except Exception:
            pass
        await unlock_listing(interaction.channel.id)
        await interaction.followup.send("🗑️ Shop post deleted. Closing ticket now...")
        await asyncio.sleep(2)
        await interaction.channel.delete()

    @discord.ui.button(label="No thanks, just close ticket", style=discord.ButtonStyle.gray, emoji="🔒")
    async def keep_post(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await unlock_listing(interaction.channel.id)
        await interaction.followup.send("🔒 Listing kept. Closing ticket now...")
        await asyncio.sleep(2)
        await interaction.channel.delete()


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Order", style=discord.ButtonStyle.red, custom_id="shop:close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        transcript_text = f"--- TRANSCRIPT FOR {interaction.channel.name} ---\n\n"
        async for msg in interaction.channel.history(limit=None, oldest_first=True):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = msg.author.name
            transcript_text += f"[{timestamp}] {author}: {msg.content}\n"
            for att in msg.attachments:
                transcript_text += f"    [ATTACHMENT]: {att.url}\n"

        transcript_file = discord.File(
            io.BytesIO(transcript_text.encode("utf-8")),
            filename=f"transcript-{interaction.channel.name}.txt",
        )

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="🔒 Ticket Closed",
                description=f"**Channel:** {interaction.channel.name}\n**Closed By:** {interaction.user.mention}",
                color=discord.Color.red(),
            )
            await log_channel.send(embed=embed, file=transcript_file)

        details = await get_lock_details(interaction.channel.id)
        if details:
            message_id, buyer_id, shop_channel_id = details
            buyer = interaction.guild.get_member(buyer_id)
            if buyer:
                await interaction.channel.set_permissions(buyer, overwrite=None)
                await interaction.followup.send(f"🚫 Removed {buyer.mention} from the ticket.")
        else:
            message_id, shop_channel_id = 0, 0

        admin_embed = discord.Embed(
            title="🛑 Ticket Closed",
            description="The buyer has been removed.\n\n**Delete original listing?**\n(Yes = Sold Out, No = Cancelled/Restock)",
            color=discord.Color.gold(),
        )
        await interaction.channel.send(
            embed=admin_embed,
            view=AdminCloseView(message_id, shop_channel_id),
        )


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(ShopView())
        self.bot.add_view(TicketCloseView())
        print("🛒 Shop System Loaded.")

    @commands.command(name="shop")
    @commands.has_permissions(administrator=True)
    async def shop_post(self, ctx, channel: discord.TextChannel):
        """Post a new shop listing via modal. Optionally attach an image."""
        image_url = ctx.message.attachments[0].url if ctx.message.attachments else None
        view = _ShopTriggerView(channel, image_url)
        msg = await ctx.send("Click the button below to fill in the listing details:", view=view)
        view.origin_msg = msg


class _ShopTriggerView(discord.ui.View):
    """Temporary view that opens the ShopPostModal when clicked."""
    def __init__(self, channel, image_url):
        super().__init__(timeout=120)
        self.channel = channel
        self.image_url = image_url
        self.origin_msg = None

    @discord.ui.button(label="📋 Fill in Listing Details", style=discord.ButtonStyle.blurple)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ShopPostModal(self.channel, self.image_url))
        if self.origin_msg:
            await self.origin_msg.delete()
        self.stop()


async def setup(bot):
    await bot.add_cog(Shop(bot))
