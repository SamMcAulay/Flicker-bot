import discord
from discord.ext import commands
from database import get_balance, update_balance, get_chips, update_chips, get_top_users


class PayConfirmView(discord.ui.View):
    def __init__(self, sender: discord.Member, receiver: discord.Member, amount: int):
        super().__init__(timeout=60)
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.receiver.id:
            await interaction.response.send_message(
                "❌ This payment is not for you!", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        await update_balance(self.sender.id, self.amount)

        for child in self.children:
            child.disabled = True

        if self.message:
            try:
                embed = self.message.embeds[0]
                embed.color = discord.Color.dark_gray()
                embed.title = "⌛ Payment Expired"
                embed.description = f"{self.receiver.mention} didn't respond in time.\n\n**{self.amount} Stardust** was safely refunded to {self.sender.mention}."
                await self.message.edit(embed=embed, view=self)
            except:
                pass

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="✅")
    async def btn_accept(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.stop()

        await update_balance(self.receiver.id, self.amount)

        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "💸 Payment Accepted!"
        embed.description = f"{self.receiver.mention} accepted the payment!\n\n**{self.amount} Stardust** has been successfully transferred from {self.sender.mention}."

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, emoji="❌")
    async def btn_deny(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.stop()

        await update_balance(self.sender.id, self.amount)

        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "🛑 Payment Denied"
        embed.description = f"{self.receiver.mention} politely declined the payment.\n\n**{self.amount} Stardust** has been refunded to {self.sender.mention}."

        await interaction.response.edit_message(embed=embed, view=self)


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Economy Cog loaded.")

    @commands.command(name="balance", aliases=["bal", "wallet", "b"])
    async def balance(self, ctx):
        """Check your Stardust and Chips balance."""
        stardust = await get_balance(ctx.author.id)
        chips = await get_chips(ctx.author.id)

        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Wallet",
            color=discord.Color.purple(),
        )
        embed.add_field(name="✨ Stardust", value=f"{stardust:,}", inline=True)
        embed.add_field(name="🎰 Chips", value=f"{chips:,}", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="add")
    @commands.has_permissions(administrator=True)
    async def add_money(self, ctx, member: discord.Member, amount: int):
        """Admin only: Add money to a user."""
        new_bal = await update_balance(member.id, amount)
        await ctx.send(
            f"💰 Added **{amount}** Stardust to {member.mention}. New balance: **{new_bal}**"
        )

    @commands.command(name="buychips", aliases=["bc"])
    async def buy_chips(self, ctx, amount_str: str):
        """Convert Stardust into Chips. Rate: 1 Stardust = 50 Chips."""
        balance = await get_balance(ctx.author.id)

        if amount_str.lower() in ["all", "max"]:
            if balance <= 0:
                return await ctx.send("❌ Your Stardust wallet is empty!")
            amount = balance
        else:
            try:
                amount = int(amount_str)
            except ValueError:
                return await ctx.send("❌ Please enter a valid number or 'all'.")

        if amount <= 0:
            return await ctx.send("❌ You must convert a positive amount of Stardust!")
        if balance < amount:
            return await ctx.send(f"❌ You don't have enough Stardust! (Balance: **{balance:,}**)")

        chips_gained = amount * 50
        await update_balance(ctx.author.id, -amount)
        new_chips = await update_chips(ctx.author.id, chips_gained)

        embed = discord.Embed(
            title="🎰 Chips Purchased!",
            description=(
                f"Converted **{amount:,} Stardust** into **{chips_gained:,} Chips**!\n"
                f"New Chips balance: **{new_chips:,}**"
            ),
            color=discord.Color.gold(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="top", aliases=["leaderboard", "lb"])
    async def top(self, ctx):
        """Display the richest users for both currencies."""
        top_stardust, top_chips = await get_top_users(10)

        def format_entries(entries):
            lines = []
            medals = ["🥇", "🥈", "🥉"]
            for i, (user_id, value) in enumerate(entries):
                prefix = medals[i] if i < 3 else f"**{i+1}.**"
                user = ctx.guild.get_member(user_id)
                name = user.display_name if user else f"User {user_id}"
                lines.append(f"{prefix} {name} — {value:,}")
            return "\n".join(lines) if lines else "*No data yet*"

        embed = discord.Embed(title="🏆 Flicker Leaderboard", color=discord.Color.purple())
        embed.add_field(name="✨ Top Stardust", value=format_entries(top_stardust), inline=True)
        embed.add_field(name="🎰 Top Chips", value=format_entries(top_chips), inline=True)
        embed.set_footer(text="Earn Stardust through events • Convert to Chips for gambling")
        await ctx.send(embed=embed)

    @commands.command(name="pay", aliases=["transfer", "give"])
    async def pay(self, ctx, member: discord.Member, amount_str: str):
        """Send Stardust to another user! (Usage: !pay @user 100)"""

        if member.bot:
            return await ctx.send(
                "❌ Flicker cannot accept Stardust! (Bots cannot have wallets)."
            )
        if member.id == ctx.author.id:
            return await ctx.send("❌ You cannot pay yourself!")

        balance = await get_balance(ctx.author.id)
        if amount_str.lower() in ["all", "max"]:
            if balance <= 0:
                return await ctx.send("❌ Your wallet is empty!")
            amount = balance
        else:
            try:
                amount = int(amount_str)
            except ValueError:
                return await ctx.send("❌ Please enter a valid number or 'all'.")

        if amount <= 0:
            return await ctx.send("❌ You must send a positive amount of Stardust!")

        if balance < amount:
            return await ctx.send(
                f"❌ You don't have enough Stardust! (Balance: **{balance}**)"
            )

        await update_balance(ctx.author.id, -amount)

        embed = discord.Embed(
            title="💸 Pending Payment...",
            description=f"{ctx.author.mention} wants to send you **{amount} Stardust**, {member.mention}!\n\nDo you accept this transfer?",
            color=discord.Color.gold(),
        )

        view = PayConfirmView(ctx.author, member, amount)
        msg = await ctx.send(content=member.mention, embed=embed, view=view)

        view.message = msg


async def setup(bot):
    await bot.add_cog(Economy(bot))
