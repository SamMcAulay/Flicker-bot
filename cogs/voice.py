import discord
import asyncio
import random
from discord.ext import commands
from database import set_vc_config, get_vc_config

class RenameModal(discord.ui.Modal):
    def __init__(self, current_name: str):
        super().__init__(title="Rename Voice Channel")
        
        if " - " in current_name:
            self.prefix = current_name.split(" - ")[0]
        else:
            self.prefix = "⭐"
            
        self.new_name = discord.ui.TextInput(
            label="New Channel Name",
            style=discord.TextStyle.short,
            placeholder="My Cool Lounge",
            required=True,
            max_length=80
        )
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction):
        new_full_name = f"{self.prefix} - {self.new_name.value}"
        
        await interaction.channel.edit(name=new_full_name)
        await interaction.response.send_message(f"✅ Channel renamed to **{new_full_name}**", ephemeral=True)

class LimitModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set User Limit")
        self.limit = discord.ui.TextInput(
            label="Max Users (0 for unlimited, max 99)",
            style=discord.TextStyle.short,
            placeholder="0",
            required=True,
            max_length=2
        )
        self.add_item(self.limit)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit_val = int(self.limit.value)
            if limit_val < 0 or limit_val > 99:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Please enter a valid number between 0 and 99.", ephemeral=True)
            
        await interaction.channel.edit(user_limit=limit_val)
        await interaction.response.send_message(f"✅ User limit set to **{limit_val if limit_val > 0 else 'Unlimited'}**", ephemeral=True)

class BanUserSelectView(discord.ui.View):
    def __init__(self, vc_channel):
        super().__init__(timeout=60)
        self.vc_channel = vc_channel
        
        self.select = discord.ui.UserSelect(placeholder="Select a user to ban from your VC", max_values=1)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        target = self.select.values[0]
        
        await self.vc_channel.set_permissions(target, connect=False)
        
        if target in self.vc_channel.members:
            try:
                await target.move_to(None)
            except:
                pass
                
        await interaction.response.send_message(f"🔨 **{target.display_name}** has been banned from this voice channel.", ephemeral=True)

class VCControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def check_owner(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Voice")
        owner_id = cog.active_vcs.get(interaction.channel.id)
        if interaction.user.id != owner_id:
            await interaction.response.send_message("❌ Only the owner of this voice channel can use these controls!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.blurple, emoji="✏️", custom_id="vc:rename")
    async def btn_rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.check_owner(interaction):
            await interaction.response.send_modal(RenameModal(interaction.channel.name))

    @discord.ui.button(label="Limit", style=discord.ButtonStyle.gray, emoji="👥", custom_id="vc:limit")
    async def btn_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.check_owner(interaction):
            await interaction.response.send_modal(LimitModal())

    @discord.ui.button(label="Private", style=discord.ButtonStyle.red, emoji="🔒", custom_id="vc:private")
    async def btn_private(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_owner(interaction):
            return
            
        config = await get_vc_config(interaction.guild.id)
        if not config: 
            return await interaction.response.send_message("⚠️ Error: System config missing.", ephemeral=True)
            
        verified_role = interaction.guild.get_role(config[1])
        overwrites = interaction.channel.overwrites

        if button.label == "Private":
            if verified_role:
                if verified_role not in overwrites:
                    overwrites[verified_role] = discord.PermissionOverwrite()
                overwrites[verified_role].connect = False
                
            for member in interaction.channel.members:
                if member not in overwrites:
                    overwrites[member] = discord.PermissionOverwrite()
                overwrites[member].connect = True
            
            button.label = "Public"
            button.style = discord.ButtonStyle.green
            button.emoji = "🔓"
            
            await interaction.channel.edit(overwrites=overwrites)
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("🔒 **Channel is now Private.** Only people currently inside can leave and rejoin.", ephemeral=True)

        else:
            if verified_role:
                if verified_role in overwrites:
                    overwrites[verified_role].connect = None 
            
            button.label = "Private"
            button.style = discord.ButtonStyle.red
            button.emoji = "🔒"
            
            await interaction.channel.edit(overwrites=overwrites)
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("🔓 **Channel is now Public.** Verified members can join again.", ephemeral=True)

    @discord.ui.button(label="Ban User", style=discord.ButtonStyle.danger, emoji="🔨", custom_id="vc:ban")
    async def btn_ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.check_owner(interaction):
            await interaction.response.send_message("Select a user to block from your channel:", view=BanUserSelectView(interaction.channel), ephemeral=True)

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_vcs = {}
        self.empty_timers = {}
        self.owner_timers = {}

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(VCControlView())
        print("🎙️ Custom VC System Loaded.")

    @commands.command(name="VCsetup")
    @commands.has_permissions(administrator=True)
    async def setup_vc(self, ctx, channel: discord.VoiceChannel, role: discord.Role):
        await set_vc_config(ctx.guild.id, channel.id, role.id)
        await ctx.send(f"✅ Voice generator set to {channel.mention}. Channels will be visible to **{role.name}**.")

    async def start_empty_timer(self, channel):
        await asyncio.sleep(60)
        if channel in self.bot.get_all_channels() and len(channel.members) == 0:
            await channel.delete()
            self.active_vcs.pop(channel.id, None)
            self.empty_timers.pop(channel.id, None)

    async def start_owner_timer(self, channel, old_owner_id):
        await asyncio.sleep(60)
        if channel in self.bot.get_all_channels() and self.active_vcs.get(channel.id) == old_owner_id:
            if old_owner_id not in [m.id for m in channel.members]:
                if len(channel.members) > 0:
                    new_owner = channel.members[0]
                    self.active_vcs[channel.id] = new_owner.id
                    await channel.send(f"👑 {new_owner.mention} has been made the new owner of this channel due to inactivity.")
            self.owner_timers.pop(channel.id, None)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        config = await get_vc_config(member.guild.id)
        if not config:
            return
            
        generator_id, verified_role_id = config
        verified_role = member.guild.get_role(verified_role_id)

        if before.channel and before.channel.id in self.active_vcs:
            vc = before.channel
            if len(vc.members) == 0:
                task = asyncio.create_task(self.start_empty_timer(vc))
                self.empty_timers[vc.id] = task
            elif member.id == self.active_vcs.get(vc.id):
                task = asyncio.create_task(self.start_owner_timer(vc, member.id))
                self.owner_timers[vc.id] = task

        if after.channel and after.channel.id in self.active_vcs:
            vc = after.channel
            if vc.id in self.empty_timers:
                self.empty_timers[vc.id].cancel()
                self.empty_timers.pop(vc.id, None)
            if vc.id in self.owner_timers and member.id == self.active_vcs.get(vc.id):
                self.owner_timers[vc.id].cancel()
                self.owner_timers.pop(vc.id, None)

        if after.channel and after.channel.id == generator_id:
            star = random.choice(["⭐", "🌟", "✨", "☄️", "🌌"])
            channel_name = f"{star} - {member.display_name}'s VC"
            
            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                member: discord.PermissionOverwrite(view_channel=True, connect=True)
            }
            if verified_role:
                overwrites[verified_role] = discord.PermissionOverwrite(view_channel=True)

            try:
                new_vc = await member.guild.create_voice_channel(
                    name=channel_name,
                    category=after.channel.category,
                    overwrites=overwrites
                )
                
                await member.move_to(new_vc)
                self.active_vcs[new_vc.id] = member.id
                
                embed = discord.Embed(
                    title="🎙️ Voice Channel Controls",
                    description=(
                        "Welcome to your custom voice channel!\n\n"
                        "✏️ **Rename** - Change the channel name.\n"
                        "👥 **Limit** - Set a max user limit.\n"
                        "🔒 **Private** - Lock the channel to current members only.\n"
                        "🔨 **Ban User** - Block someone from joining."
                    ),
                    color=discord.Color.blue()
                )
                await new_vc.send(f"{member.mention} You are the owner!", embed=embed, view=VCControlView())
                
            except Exception as e:
                print(f"Failed to create VC: {e}")

async def setup(bot):
    await bot.add_cog(Voice(bot))
