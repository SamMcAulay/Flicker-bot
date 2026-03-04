import discord
import random
from discord.ext import commands
from database import set_verify_role, get_verify_role

locked_users = set()

class VerifyModal(discord.ui.Modal):
    def __init__(self, question: str, answer: str, role_id: int):
        super().__init__(title="Rule Verification")
        self.expected_answer = answer.lower()
        self.role_id = role_id
        
        self.user_answer = discord.ui.TextInput(
            label=question[:45],
            style=discord.TextStyle.short,
            placeholder="Type your answer here...",
            required=True
        )
        self.add_item(self.user_answer)

    async def on_submit(self, interaction: discord.Interaction):
        if self.expected_answer in self.user_answer.value.lower():
            role = interaction.guild.get_role(self.role_id)
            if role:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("✅ **Correct!** Welcome to the galaxy!", ephemeral=True)
                locked_users.discard(interaction.user.id) 
            else:
                await interaction.response.send_message("⚠️ Error: Verified role missing. Please ping staff.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ **Incorrect.** Please read the rules carefully and click the green button to try again.", ephemeral=True)


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="no I have not read the rules", style=discord.ButtonStyle.green, custom_id="verify:no")
    async def btn_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        locked_users.add(interaction.user.id)
        
        role_id = await get_verify_role(interaction.guild.id)
        if not role_id:
            return await interaction.response.send_message("⚠️ System not set up. An admin needs to run !verify.", ephemeral=True)

        questions = [
            ("What is the minimum age for this server?", "13"),
            ("Are AI generated or traced artworks allowed?", "no"),
            ("Can you post pictures/videos of yourself?", "no"),
            ("Can you use a slur if you can reclaim it?", "no"),
            ("If a rule is broken, what should you open?", "ticket"),
            ("How many warnings do you get before a ban?", "3"),
            ("What must be used for light/candy gore?", "spoiler"),
            ("Can you post a selfie if you are over 13?", "no"),
            ("Should you correct rule-breakers yourself?", "no"),
            ("What should you use to clarify a joke?", "tone")
        ]
        q_text, expected_ans = random.choice(questions)
        
        modal = VerifyModal(q_text, expected_ans, role_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Yes I have read the rules", style=discord.ButtonStyle.red, custom_id="verify:yes")
    async def btn_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in locked_users:
            await interaction.response.send_message("❌ Aha! You already admitted you haven't read the rules! You must click the **green button** and pass the quiz.", ephemeral=True)
            return

        role_id = await get_verify_role(interaction.guild.id)
        if not role_id:
            return await interaction.response.send_message("⚠️ System not set up. An admin needs to run !verify.", ephemeral=True)

        role = interaction.guild.get_role(role_id)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ Thank you for reading the rules! You have been verified.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Error: Verified role missing. Please ping staff.", ephemeral=True)

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(VerifyView())
        print("🛡️ Verification System Loaded.")

    @commands.command(name="verify")
    @commands.has_permissions(administrator=True)
    async def setup_verify(self, ctx, channel: discord.TextChannel, role: discord.Role):
        """
        Sets up the verification embed.
        Usage: !verify #channel @VerifiedRole
        """
        await set_verify_role(ctx.guild.id, role.id)

        embed = discord.Embed(
            title="👋 Welcome to the Galaxy!",
            description=(
                "We are so glad to have you here! ✨\n\n"
                "Before you can chat, we need to make sure you understand how things work around here.\n\n"
                "**Please read the rules above carefully**, then click the button below to gain access to the rest of the server."
            ),
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)

        await channel.send(embed=embed, view=VerifyView())
        await ctx.send(f"✅ Verification gate has been set up in {channel.mention} using the **{role.name}** role!")

async def setup(bot):
    await bot.add_cog(Verification(bot))
