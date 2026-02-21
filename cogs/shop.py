import discord
import asyncio
import io
from discord.ext import commands
from database import (
    get_balance, update_balance, is_listing_locked, lock_listing, unlock_listing, 
    get_lock_details, create_shop_item, get_shop_item, decrement_stock
)

# --- VIEW: ADMIN DECISION ---
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
        except Exception as e:
            pass # Message might already be deleted

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

# --- VIEW: TICKET CONTROLS ---
class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Order", style=discord.ButtonStyle.red, custom_id="shop:close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer() 
        
        transcript_text = f"--- TRANSCRIPT FOR {interaction.channel.name} ---\n\n"
        async for msg in interaction.channel.history(limit=None, oldest_first=True):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = f"{msg.author.name}#{msg.author.discriminator}" if msg.author.discriminator != "0" else msg.author.name
            transcript_text += f"[{timestamp}] {author}: {msg.content}\n"
            if msg.attachments:
                for attachment in msg.attachments:
                    transcript_text += f"    [ATTACHMENT]: {attachment.url}\n"
        
        transcript_file = discord.File(
            io.BytesIO(transcript_text.encode("utf-8")), 
            filename=f"transcript-{interaction.channel.name}.txt"
        )

        log_channel_id = 1473785756219871463
        log_channel = interaction.guild.get_channel(log_channel_id)
        
        if log_channel:
            embed = discord.Embed(
                title="🔒 Ticket Closed",
                description=f"**Channel:** {interaction.channel.name}\n**Closed By:** {interaction.user.mention}",
                color=discord.Color.red()
            )
            await log_channel.send(embed=embed, file=transcript_file)
        
        # Remove Buyer
        details = await get_lock_details(interaction.channel.id)
        if details:
            message_id, buyer_id, shop_channel_id = details
            buyer = interaction.guild.get_member(buyer_id)
            if buyer:
                await interaction.channel.set_permissions(buyer, overwrite=None)
                await interaction.followup.send(f"🚫 Removed {buyer.mention} from the ticket.")
        else:
            message_id, shop_channel_id = 0, 0

        # Admin Panel
        admin_embed = discord.Embed(
            title="🛑 Ticket Closed",
            description="The buyer has been removed.\n\n**Delete original listing?**\n(Yes = Sold Out, No = Cancelled/Restock)",
            color=discord.Color.gold()
        )
        view = AdminCloseView(message_id, shop_channel_id)
        await interaction.channel.send(embed=admin_embed, view=view)

# --- VIEW: GLOBAL SHOP BUTTONS ---
class ShopView(discord.ui.View):
    # We default these to 1 so that when the bot restarts, it registers BOTH buttons globally.
    # But when a user runs the command, we pass the real prices to hide the empty ones!
    def __init__(self, stardust_price: int = 1, usd_price: float = 1.0):
        super().__init__(timeout=None)
        
        # Look at the buttons before posting and remove the ones that cost 0
        for child in self.children.copy():
            if getattr(child, "custom_id", None) == "shop:btn_stardust" and stardust_price <= 0:
                self.remove_item(child)
            elif getattr(child, "custom_id", None) == "shop:btn_usd" and usd_price <= 0:
                self.remove_item(child)

    @discord.ui.button(label="Buy with Stardust", style=discord.ButtonStyle.blurple, emoji="✨", custom_id="shop:btn_stardust")
    async def btn_stardust(self, interaction: discord.Interaction, button: discord.ui.Button):
        message_id = interaction.message.id
        user = interaction.user

        item = await get_shop_item(message_id)
        if not item:
            return await interaction.response.send_message("⚠️ **Error:** This shop post is outdated. Please ask staff to repost it.", ephemeral=True)
        
        stock, role_id, stardust_price, usd_price = item

        if stardust_price <= 0:
            return await interaction.response.send_message("❌ This item cannot be bought with Stardust.", ephemeral=True)
        if stock == 0:
            return await interaction.response.send_message("❌ **Sold Out!** This item is out of stock.", ephemeral=True)
        if role_id is None and await is_listing_locked(message_id) and stock == 1:
            return await interaction.response.send_message("❌ **Busy!** Someone else is currently buying this.", ephemeral=True)

        balance = await get_balance(user.id)
        if balance < stardust_price:
            return await interaction.response.send_message(f"❌ You need **{stardust_price} Stardust** (You have {balance}).", ephemeral=True)

        # Process Payment & Stock
        await update_balance(user.id, -stardust_price)
        await decrement_stock(message_id)

        # Role Delivery vs Ticket
        if role_id:
            role = interaction.guild.get_role(role_id)
            if role:
                await user.add_roles(role)
                await interaction.response.send_message(f"✅ **Purchase Successful!** You have been given the **{role.name}** role.", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ **Error:** The role for this item no longer exists. Please contact staff.", ephemeral=True)
        else:
            await self.create_ticket(interaction, user, message_id, stardust_price, "Stardust")

    @discord.ui.button(label="Buy with USD", style=discord.ButtonStyle.green, emoji="💵", custom_id="shop:btn_usd")
    async def btn_usd(self, interaction: discord.Interaction, button: discord.ui.Button):
        message_id = interaction.message.id
        user = interaction.user
        
        item = await get_shop_item(message_id)
        if not item:
            return await interaction.response.send_message("⚠️ **Error:** This shop post is outdated. Please ask staff to repost it.", ephemeral=True)
        
        stock, role_id, stardust_price, usd_price = item

        if usd_price <= 0:
            return await interaction.response.send_message("❌ This item cannot be bought with USD.", ephemeral=True)
        if stock == 0:
            return await interaction.response.send_message("❌ **Sold Out!** This item is out of stock.", ephemeral=True)
        if role_id is None and await is_listing_locked(message_id) and stock == 1:
            return await interaction.response.send_message("❌ **Busy!** Someone else is currently buying this.", ephemeral=True)

        await self.create_ticket(interaction, user, message_id, usd_price, "USD")

    async def create_ticket(self, interaction, user, message_id, price, currency):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Orders")
        if not category: category = await guild.create_category("Orders")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }

        channel_type = "order" if currency == "Stardust" else "inquiry"
        ticket_channel = await guild.create_text_channel(f"{channel_type}-{user.name}", category=category, overwrites=overwrites)
        
        await lock_listing(message_id, ticket_channel.id, user.id, interaction.channel.id)

        symbol = "✨" if currency == "Stardust" else "💵"
        paid_text = f"{price} Stardust" if currency == "Stardust" else f"${price} USD"

        embed = discord.Embed(
            title=f"{symbol} Order {channel_type.capitalize()}",
            description=f"**Buyer:** {user.mention}\n**Price:** {paid_text}\n**Item:** [View Listing]({interaction.message.jump_url})",
            color=discord.Color.green()
        )
        footer_text = "Staff will process your order shortly." if currency == "Stardust" else "Please wait for staff to provide payment details."
        embed.set_footer(text=footer_text)
        
        await ticket_channel.send(f"{user.mention} Ticket created!", embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ Ticket opened: {ticket_channel.mention}", ephemeral=True)


# --- THE SHOP COG ---
class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Registers the default view globally so all existing buttons work
        self.bot.add_view(ShopView())
        self.bot.add_view(TicketCloseView())
        print("🛒 Shop System Loaded.")

    @commands.command(name="shopPost")
    @commands.has_permissions(administrator=True)
    async def shop_post(self, ctx, channel: discord.TextChannel, stardust_price: int, usd_price: float, title: str, *, description: str):
        if ctx.message.attachments:
            image_url = ctx.message.attachments[0].url
        else:
            return await ctx.send("❌ **Missing Image!** Please attach an image to your command message.")

        embed = discord.Embed(title=title, description=description, color=discord.Color.purple())
        embed.set_image(url=image_url)
        if stardust_price > 0: embed.add_field(name="✨ Stardust Price", value=f"{stardust_price} Stardust", inline=True)
        if usd_price > 0: embed.add_field(name="💵 USD Price", value=f"${usd_price} USD", inline=True)

        # Pass the prices to remove 0-cost buttons visually before posting
        view = ShopView(stardust_price, usd_price)
        msg = await channel.send(embed=embed, view=view)
        
        await create_shop_item(msg.id, 1, None, stardust_price, usd_price)
        await ctx.send(f"✅ Listing posted in {channel.mention}!")

    @commands.command(name="shopStock")
    @commands.has_permissions(administrator=True)
    async def shop_stock(self, ctx, channel: discord.TextChannel, stock_input: str, stardust_price: int, usd_price: float, title: str, *, description: str):
        if stock_input.lower() in ["inf", "infinity", "unlimited"]:
            stock, stock_text = -1, "♾️ Unlimited"
        else:
            try:
                stock = int(stock_input)
                stock_text = f"{stock}"
            except ValueError:
                return await ctx.send("❌ Stock must be a number or 'inf'.")

        role_id, image_url = None, None

        if ctx.message.attachments:
            image_url = ctx.message.attachments[0].url

        if ctx.message.role_mentions:
            role = ctx.message.role_mentions[0]
            role_id = role.id
            description = description.replace(role.mention, "").strip()

        if not image_url and not role_id:
            return await ctx.send("❌ **Error:** You must attach an image OR mention a role (or both).")

        embed = discord.Embed(title=title, description=description, color=discord.Color.purple())
        if image_url: embed.set_image(url=image_url)
        
        embed.add_field(name="📦 Stock", value=stock_text, inline=True)
        if stardust_price > 0: embed.add_field(name="✨ Stardust Price", value=f"{stardust_price} Stardust", inline=True)
        if usd_price > 0: embed.add_field(name="💵 USD Price", value=f"${usd_price} USD", inline=True)
        if role_id: embed.set_footer(text="✨ Instant Role Delivery")

        # Pass the prices to remove 0-cost buttons visually before posting
        view = ShopView(stardust_price, usd_price)
        msg = await channel.send(embed=embed, view=view)

        await create_shop_item(msg.id, stock, role_id, stardust_price, usd_price)
        await ctx.send(f"✅ Stocked Item Posted in {channel.mention}")

async def setup(bot):
    await bot.add_cog(Shop(bot))