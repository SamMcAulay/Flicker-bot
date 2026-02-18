import discord
import asyncio
import io
from discord.ext import commands
from database import get_balance, update_balance, is_listing_locked, lock_listing, unlock_listing, get_lock_details

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
            await interaction.followup.send("⚠️ Could not find database record for this ticket.")

        admin_embed = discord.Embed(
            title="🛑 Ticket Closed",
            description="The buyer has been removed.\n\n**Would you like to remove the original shop listing?**\n(Click 'Yes' if the item was sold. Click 'No' if the deal was cancelled).",
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

        if await is_listing_locked(message_id):
            await interaction.response.send_message("❌ **Sold Out!** Someone else is currently buying this item.", ephemeral=True)
            return

        balance = await get_balance(user.id)
        if balance < self.price:
            await interaction.response.send_message(f"❌ You need **{self.price} Stardust** (You have {balance}).", ephemeral=True)
            return

        await update_balance(user.id, -self.price)
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
        user = interaction.user

        if await is_listing_locked(message_id):
            await interaction.response.send_message("❌ **Busy!** Someone else is inquiring about this item.", ephemeral=True)
            return

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

async def setup(bot):
    await bot.add_cog(Shop(bot))
