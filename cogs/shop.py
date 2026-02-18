import discord
import asyncio
import io
from discord.ext import commands
from database import (
    get_balance, update_balance, is_listing_locked, lock_listing, unlock_listing, 
    get_lock_details, create_shop_item, get_shop_item, decrement_stock
)

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
            print(f"Could not delete shop post: {e}")

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
            color=discord.Color.gold()
        )
        view = AdminCloseView(message_id, shop_channel_id)
        await interaction.channel.send(embed=admin_embed, view=view)


class StardustButton(discord.ui.Button):
    def __init__(self, price):
        super().__init__(label=f"Buy for {price} Stardust", style=discord.ButtonStyle.blurple, emoji="✨", custom_id=f"shop:stardust:{price}")
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        message_id = interaction.message.id
        user = interaction.user

        item = await get_shop_item(message_id)
        if item:
            stock, role_id, db_price, _ = item
        else:
            stock, role_id = -1, None 

        if stock == 0:
            await interaction.response.send_message("❌ **Sold Out!** This item is out of stock.", ephemeral=True)
            return

        if role_id is None and await is_listing_locked(message_id):
             if stock == 1:
                await interaction.response.send_message("❌ **Busy!** Someone else is currently buying this.", ephemeral=True)
                return

        balance = await get_balance(user.id)
        if balance < self.price:
            await interaction.response.send_message(f"❌ You need **{self.price} Stardust** (You have {balance}).", ephemeral=True)
            return

        await update_balance(user.id, -self.price)
        await decrement_stock(message_id)

        if role_id:
            role = interaction.guild.get_role(role_id)
            if role:
                await user.add_roles(role)
                await interaction.response.send_message(f"✅ **Purchase Successful!** You have been given the **{role.name}** role.", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ **Error:** The role for this item no longer exists. Please contact staff.", ephemeral=True)
        else:
            await self.create_ticket(interaction, user, message_id)

    async def create_ticket(self, interaction, user, message_id):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Orders")
        if not category: category = await guild.create_category("Orders")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }

        ticket_channel = await guild.create_text_channel(f"order-{user.name}", category=category, overwrites=overwrites)
        await lock_listing(message_id, ticket_channel.id, user.id, interaction.channel.id)

        embed = discord.Embed(
            title="✨ Order Created",
            description=f"**Buyer:** {user.mention}\n**Paid:** {self.price} Stardust\n**Item:** [View Listing]({interaction.message.jump_url})",
            color=discord.Color.green()
        )
        embed.set_footer(text="Staff will process your order shortly.")
        
        await ticket_channel.send(f"{user.mention} Thank you for your purchase!", embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ **Payment Successful!** Your ticket has been opened: {ticket_channel.mention}", ephemeral=True)


class USDButton(discord.ui.Button):
    def __init__(self, price):
        super().__init__(label=f"Buy for ${price} USD", style=discord.ButtonStyle.green, emoji="💵", custom_id=f"shop:usd:{price}")
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        message_id = interaction.message.id

        item = await get_shop_item(message_id)
        if item:
            stock = item[0]
            if stock == 0:
                await interaction.response.send_message("❌ **Sold Out!** This item is out of stock.", ephemeral=True)
                return

        await self.create_ticket(interaction, message_id)

    async def create_ticket(self, interaction, message_id):
        user = interaction.user
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Orders")
        if not category: category = await guild.create_category("Orders")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }

        ticket_channel = await guild.create_text_channel(f"inquiry-{user.name}", category=category, overwrites=overwrites)
        await lock_listing(message_id, ticket_channel.id, user.id, interaction.channel.id)

        embed = discord.Embed(
            title="💵 Order Inquiry",
            description=f"**Buyer:** {user.mention}\n**Price:** ${self.price} USD\n**Item:** [View Listing]({interaction.message.jump_url})",
            color=discord.Color.green()
        )
        embed.set_footer(text="Please wait for staff to provide payment details.")
        
        await ticket_channel.send(f"{user.mention} Ticket created!", embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ Ticket opened: {ticket_channel.mention}", ephemeral=True)


class ShopView(discord.ui.View):
    def __init__(self, stardust_price: int, usd_price: float):
        super().__init__(timeout=None)
        if stardust_price > 0: self.add_item(StardustButton(stardust_price))
        if usd_price > 0: self.add_item(USDButton(usd_price))


class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(TicketCloseView())
        print("🛒 Shop System Loaded.")

    @commands.command(name="shopPost")
    @commands.has_permissions(administrator=True)
    async def shop_post(self, ctx, channel: discord.TextChannel, stardust_price: int, usd_price: float, title: str, *, description: str):
        if ctx.message.attachments:
            image_url = ctx.message.attachments[0].url
        else:
            await ctx.send("❌ **Missing Image!** Please attach an image to your command message.")
            return

        embed = discord.Embed(title=title, description=description, color=discord.Color.purple())
        embed.set_image(url=image_url)
        if stardust_price > 0: embed.add_field(name="✨ Stardust Price", value=f"{stardust_price} Stardust", inline=True)
        if usd_price > 0: embed.add_field(name="💵 USD Price", value=f"${usd_price} USD", inline=True)

        view = ShopView(stardust_price, usd_price)
        await channel.send(embed=embed, view=view)
        await ctx.send(f"✅ Listing posted in {channel.mention}!")

    @commands.command(name="shopStock")
    @commands.has_permissions(administrator=True)
    async def shop_stock(self, ctx, channel: discord.TextChannel, stock_input: str, stardust_price: int, usd_price: float, title: str, *, description: str):
        """
        Post a shop item with Stock + Role + Image support.
        Usage: Attach Image AND/OR Mention Role -> !shopStock ...
        """
        
        if stock_input.lower() in ["inf", "infinity", "unlimited"]:
            stock = -1
            stock_text = "♾️ Unlimited"
        else:
            try:
                stock = int(stock_input)
                stock_text = f"{stock}"
            except ValueError:
                await ctx.send("❌ Stock must be a number or 'inf'.")
                return

        role_id = None
        image_url = None

        if ctx.message.attachments:
            image_url = ctx.message.attachments[0].url

        if ctx.message.role_mentions:
            role = ctx.message.role_mentions[0]
            role_id = role.id
            description = description.replace(role.mention, "").strip()

        if not image_url and not role_id:
            await ctx.send("❌ **Error:** You must attach an image OR mention a role (or both).")
            return

        embed = discord.Embed(title=title, description=description, color=discord.Color.purple())
        
        if image_url:
            embed.set_image(url=image_url)
        
        embed.add_field(name="📦 Stock", value=stock_text, inline=True)
        if stardust_price > 0: embed.add_field(name="✨ Stardust Price", value=f"{stardust_price} Stardust", inline=True)
        if usd_price > 0: embed.add_field(name="💵 USD Price", value=f"${usd_price} USD", inline=True)

        if role_id:
            embed.set_footer(text="✨ Instant Role Delivery")

        view = ShopView(stardust_price, usd_price)
        msg = await channel.send(embed=embed, view=view)

        await create_shop_item(msg.id, stock, role_id, stardust_price, usd_price)
        
        await ctx.send(f"✅ Stocked Item Posted in {channel.mention} (ID: {msg.id})")

async def setup(bot):
    await bot.add_cog(Shop(bot))