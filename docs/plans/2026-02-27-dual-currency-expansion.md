# Dual Currency Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Chips gambling currency, refactor the shop with a modal interface, migrate all gambling to Chips, add four new casino games, add two new passive events, and add a `!top` leaderboard.

**Architecture:** Chips live as a second column on the existing `users` table; all gambling deducts/awards Chips; Stardust→Chips conversion is one-way at 1:50. The shop is rebuilt around a single `!shop` command that triggers a Discord Modal, eliminating the two duplicated existing commands.

**Tech Stack:** Python 3, discord.py 2.6.4, aiosqlite 0.22.1, SQLite

---

## Task 1: Database — add Chips column and new functions

**Files:**
- Modify: `database.py`

**Context:**
SQLite does not support `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. Use a `try/except` to safely add the column on every `init_db()` call without crashing on re-runs.

**Step 1: Add chips column migration to `init_db()`**

In `database.py`, inside `init_db()`, after the existing `await db.commit()` add:

```python
        # Safe migration: add chips column if it doesn't exist yet
        try:
            await db.execute("ALTER TABLE users ADD COLUMN chips INTEGER DEFAULT 0")
            await db.commit()
        except Exception:
            pass  # Column already exists

        # Safe migration: add chips_price column to shop_items
        try:
            await db.execute("ALTER TABLE shop_items ADD COLUMN chips_price INTEGER DEFAULT 0")
            await db.commit()
        except Exception:
            pass  # Column already exists
```

**Step 2: Add `get_chips` and `update_chips`**

Add after the existing `update_balance` function:

```python
async def get_chips(user_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT chips FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            else:
                await db.execute("INSERT INTO users (user_id, balance, chips) VALUES (?, 0, 0)", (user_id,))
                await db.commit()
                return 0

async def update_chips(user_id: int, amount: int) -> int:
    current = await get_chips(user_id)
    new_chips = current + amount
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET chips = ? WHERE user_id = ?", (new_chips, user_id))
        await db.commit()
    return new_chips
```

**Step 3: Add `get_top_users`**

Add after `update_chips`:

```python
async def get_top_users(limit: int = 10):
    """Returns (top_stardust, top_chips) as two lists of (user_id, value)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,)
        ) as cursor:
            top_stardust = await cursor.fetchall()
        async with db.execute(
            "SELECT user_id, chips FROM users ORDER BY chips DESC LIMIT ?", (limit,)
        ) as cursor:
            top_chips = await cursor.fetchall()
    return top_stardust, top_chips
```

**Step 4: Update `create_shop_item` signature to include `chips_price`**

Change the existing function signature and INSERT:

```python
async def create_shop_item(message_id, stock, role_id, stardust, chips, usd):
    """Registers a new shop item in the DB."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO shop_items (message_id, stock, role_id, stardust_price, chips_price, usd_price) VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, stock, role_id, stardust, chips, usd)
        )
        await db.commit()
```

**Step 5: Update `get_shop_item` to return chips_price**

```python
async def get_shop_item(message_id):
    """Returns (stock, role_id, stardust_price, chips_price, usd_price)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT stock, role_id, stardust_price, chips_price, usd_price FROM shop_items WHERE message_id = ?",
            (message_id,)
        ) as cursor:
            return await cursor.fetchone()
```

**Step 6: Verify and commit**

Start the bot (`python main.py`) and confirm it says "Database initialized." without errors. Then stop it.

```bash
git add database.py
git commit -m "feat: add chips column and DB functions for dual currency"
```

---

## Task 2: Economy — `!buychips`, updated `!balance`, `!top`

**Files:**
- Modify: `cogs/economy.py`

**Step 1: Update imports**

At the top of `cogs/economy.py`, replace the import line:

```python
from database import get_balance, update_balance
```

with:

```python
from database import get_balance, update_balance, get_chips, update_chips, get_top_users
```

**Step 2: Update `!balance` to show both currencies**

Replace the entire `balance` command with:

```python
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
```

**Step 3: Add `!buychips` command**

Add this method to the `Economy` class, after `add_money`:

```python
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
```

**Step 4: Add `!top` command**

Add this method to the `Economy` class, after `buy_chips`:

```python
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
```

**Step 5: Verify manually**

- Run the bot, use `!balance` — confirm two fields appear.
- Use `!buychips 10` — confirm Stardust decreases by 10 and Chips increases by 500.
- Use `!top` — confirm the embed renders with two columns.

**Step 6: Commit**

```bash
git add cogs/economy.py
git commit -m "feat: add !buychips conversion and !top leaderboard"
```

---

## Task 3: Shop refactor — modal interface + Chips button

**Files:**
- Modify: `cogs/shop.py`
- Note: `database.py` `create_shop_item` signature already updated in Task 1.

**Context:**
Discord modals support exactly **5 `TextInput` fields**. We'll use:
1. Title
2. Description
3. Stock (`1`, `inf`, etc.)
4. Prices — one field, format: `stardust:100 chips:5000 usd:9.99` (omit any to disable)
5. Role ID (optional — leave blank for ticket flow)

Image is attached to the `!shop` command message itself (not in the modal).

**Step 1: Rewrite `cogs/shop.py` entirely**

Replace the entire file with the following:

```python
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

def _parse_prices(raw: str) -> tuple[int, int, float]:
    """Parse 'stardust:100 chips:5000 usd:9.99' into (stardust, chips, usd)."""
    stardust = int(m.group(1)) if (m := re.search(r"stardust[:\s]+(\d+)", raw, re.I)) else 0
    chips    = int(m.group(1)) if (m := re.search(r"chips[:\s]+(\d+)",    raw, re.I)) else 0
    usd      = float(m.group(1)) if (m := re.search(r"usd[:\s]+([\d.]+)", raw, re.I)) else 0.0
    return stardust, chips, usd


# ---------------------------------------------------------------------------
# Modal
# ---------------------------------------------------------------------------

class ShopPostModal(discord.ui.Modal, title="Post Shop Listing"):
    item_title   = discord.ui.TextInput(label="Title",       placeholder="e.g. Cosmic Supporter Role", max_length=100)
    description  = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, max_length=1000)
    stock_input  = discord.ui.TextInput(label="Stock",       placeholder="1  |  inf  |  5", default="1", max_length=20)
    prices_input = discord.ui.TextInput(
        label="Prices (omit to disable)",
        placeholder="stardust:100  chips:5000  usd:9.99",
        max_length=100,
    )
    role_input   = discord.ui.TextInput(
        label="Role ID for instant delivery (optional)",
        placeholder="Leave blank for manual ticket",
        required=False,
        max_length=25,
    )

    def __init__(self, target_channel: discord.TextChannel, image_url: str | None):
        super().__init__()
        self.target_channel = target_channel
        self.image_url = image_url

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # --- Parse stock ---
        raw_stock = self.stock_input.value.strip().lower()
        if raw_stock in ("inf", "infinity", "unlimited", "∞"):
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

        # Balance check for automatic currencies
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
        category = discord.utils.get(guild.categories, name="Orders") or await guild.create_category("Orders")

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
        footer = "Staff will process your order shortly." if currency != "usd" else "Please wait for staff to provide payment details."

        embed = discord.Embed(
            title=f"{symbols[currency]} Order {label.capitalize()}",
            description=f"**Buyer:** {user.mention}\n**Price:** {paid_text}\n**Item:** [View Listing]({interaction.message.jump_url})",
            color=discord.Color.green(),
        )
        embed.set_footer(text=footer)
        await ticket_channel.send(f"{user.mention}", embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ Ticket opened: {ticket_channel.mention}", ephemeral=True)

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
# Ticket Views (unchanged logic, kept as-is)
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
        await interaction.channel.send(embed=admin_embed, view=AdminCloseView(message_id, shop_channel_id))


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
        modal = ShopPostModal(target_channel=channel, image_url=image_url)
        await ctx.interaction.response.send_modal(modal) if ctx.interaction else None
        # Prefix commands can't send modals directly — use a button to trigger
        # For slash-less bots, post a temporary "Click to post" message instead:
        if not ctx.interaction:
            view = _ShopTriggerView(channel, image_url)
            msg = await ctx.send("Click the button below to fill in the listing details:", view=view)
            view.origin_msg = msg


class _ShopTriggerView(discord.ui.View):
    """Ephemeral trigger: shows a button that opens the ShopPostModal."""
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
```

**Step 2: Verify manually**

- Run `!shop #some-channel` (with an optional image attachment).
- Confirm a button message appears, click it, fill the modal.
- Confirm the embed appears in the target channel with the correct buttons.
- Confirm old `!shopPost` / `!shopStock` no longer exist.

**Step 3: Commit**

```bash
git add cogs/shop.py
git commit -m "refactor: replace shopPost/shopStock with modal-driven !shop command and add Chips button"
```

---

## Task 4: Gamble — migrate existing games to Chips

**Files:**
- Modify: `cogs/gamble.py`

**Step 1: Update imports**

Replace:
```python
from database import get_balance, update_balance
```
with:
```python
from database import get_chips, update_chips
```

**Step 2: Update `get_bet_amount`**

Replace the entire method:
```python
async def get_bet_amount(self, ctx, amount_str: str) -> int:
    chips = await get_chips(ctx.author.id)
    if amount_str.lower() in ["all", "max"]:
        if chips <= 0:
            await ctx.send("❌ Your chip stack is empty!")
            return -1
        return chips
    try:
        amount = int(amount_str)
        if amount <= 0:
            await ctx.send("❌ You must bet a positive number of Chips!")
            return -1
        return amount
    except ValueError:
        await ctx.send("❌ Please enter a valid number or 'all'.")
        return -1
```

**Step 3: Update `coinflip` to use Chips**

In the `coinflip` command, replace every reference:

| Old | New |
|-----|-----|
| `await get_balance(ctx.author.id)` | `await get_chips(ctx.author.id)` |
| `await update_balance(ctx.author.id, -bet)` | `await update_chips(ctx.author.id, -bet)` |
| `await update_balance(ctx.author.id, winnings)` | `await update_chips(ctx.author.id, winnings)` |
| `"Stardust"` (in embed text) | `"Chips"` |
| `balance < bet` check variable | rename `balance` → `chips` |

**Step 4: Update `slots` to use Chips**

Same substitutions as Step 3 for the `slots` command.

**Step 5: Update embed titles**

- `slots`: change `"🎰 Stardust Slots 🎰"` → `"🎰 Cosmic Chip Slots 🎰"`

**Step 6: Verify manually**

Run `!cf 100 h` and `!slots 100` — confirm Chips are deducted/awarded, not Stardust.

**Step 7: Commit**

```bash
git add cogs/gamble.py
git commit -m "feat: migrate coinflip and slots to use Chips currency"
```

---

## Task 5: Gamble — Blackjack (`!bj`)

**Files:**
- Modify: `cogs/gamble.py`

**Step 1: Add card helpers at the top of `gamble.py`**

After the existing constants (ANIM_COIN etc.), add:

```python
import itertools

# Themed suits
SUITS = ["✨", "🌙", "⭐", "💫"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def new_deck():
    return [f"{r}{s}" for r, s in itertools.product(RANKS, SUITS)]

def card_value(card: str) -> int:
    rank = card[:-1]  # strip the suit emoji (last char is 1 emoji codepoint... careful with multi-char)
    # suits are 1-2 chars of emoji; rank is everything before the last emoji
    # Actually rank extraction: RANKS are 1-2 chars, suits are multi-byte but single char
    if rank in ("J", "Q", "K"): return 10
    if rank == "A": return 11
    return int(rank)

def hand_value(hand: list[str]) -> int:
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c.startswith("A"))
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def fmt_hand(hand: list[str]) -> str:
    return "  ".join(hand)
```

**Note on card parsing:** The suit emojis (✨🌙⭐💫) are each a single Unicode character but may be 2+ bytes. The rank is everything before the last character of the string. For `"10✨"`, `card[:-1]` gives `"10"` — this works correctly for all ranks because each suit emoji is one `str` character in Python.

**Step 2: Add Blackjack View**

Add this class before the `Gamble` cog class:

```python
class BlackjackView(discord.ui.View):
    def __init__(self, cog, ctx, bet: int, deck: list, player_hand: list, dealer_hand: list):
        super().__init__(timeout=30)
        self.cog = cog
        self.ctx = ctx
        self.bet = bet
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.message = None
        self.doubled = False

    def build_embed(self, reveal_dealer=False) -> discord.Embed:
        pval = hand_value(self.player_hand)
        if reveal_dealer:
            dealer_str = fmt_hand(self.dealer_hand)
            dval = hand_value(self.dealer_hand)
            dealer_display = f"{dealer_str} ({dval})"
        else:
            dealer_display = f"{self.dealer_hand[0]}  🂠"
        embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.dark_gold())
        embed.add_field(name=f"Dealer", value=dealer_display, inline=False)
        embed.add_field(name=f"{self.ctx.author.display_name} ({pval})", value=fmt_hand(self.player_hand), inline=False)
        embed.set_footer(text=f"Bet: {self.bet:,} Chips")
        return embed

    async def resolve(self, interaction: discord.Interaction):
        """Run dealer AI then determine winner."""
        for child in self.children:
            child.disabled = True

        # Dealer hits to soft 17
        boss_id = self.cog.boss_id
        while hand_value(self.dealer_hand) < 17:
            # Boss mode: dealer busts more (skip a hit 30% of the time when at 16)
            if interaction.user.id == boss_id and hand_value(self.dealer_hand) == 16 and random.random() < 0.30:
                break
            self.dealer_hand.append(self.deck.pop())

        pval = hand_value(self.player_hand)
        dval = hand_value(self.dealer_hand)

        if pval > 21:
            result, color, winnings = "💥 Bust! You lose.", discord.Color.red(), 0
        elif dval > 21 or pval > dval:
            result, color, winnings = "🎉 You win!", discord.Color.green(), self.bet * 2
        elif pval == dval:
            result, color, winnings = "🤝 Push — bet returned.", discord.Color.greyple(), self.bet
        else:
            result, color, winnings = "❌ Dealer wins.", discord.Color.red(), 0

        if winnings:
            await update_chips(interaction.user.id, winnings)

        embed = self.build_embed(reveal_dealer=True)
        embed.color = color
        embed.description = f"**{result}**" + (f"\n+**{winnings:,} Chips**" if winnings > self.bet else "")
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green, emoji="👊")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        self.player_hand.append(self.deck.pop())
        if hand_value(self.player_hand) >= 21:
            await self.resolve(interaction)
        else:
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        await self.resolve(interaction)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.blurple, emoji="⚡")
    async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        chips = await get_chips(self.ctx.author.id)
        if chips < self.bet:
            return await interaction.response.send_message(
                f"❌ Not enough Chips to double! (Need {self.bet:,} more)", ephemeral=True
            )
        await update_chips(self.ctx.author.id, -self.bet)
        self.bet *= 2
        self.player_hand.append(self.deck.pop())
        await self.resolve(interaction)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass
        # Refund on timeout
        await update_chips(self.ctx.author.id, self.bet)
```

**Step 3: Add the `!bj` command** to the `Gamble` class:

```python
@commands.command(name="blackjack", aliases=["bj"])
@commands.cooldown(1, 15, commands.BucketType.user)
async def blackjack(self, ctx, amount: str):
    """Play Blackjack against the dealer using Chips!"""
    bet = await self.get_bet_amount(ctx, amount)
    if bet == -1:
        ctx.command.reset_cooldown(ctx)
        return

    chips = await get_chips(ctx.author.id)
    if chips < bet:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(f"❌ You don't have enough Chips! (Balance: {chips:,})")

    await update_chips(ctx.author.id, -bet)

    deck = new_deck()
    random.shuffle(deck)
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    # Natural blackjack check
    if hand_value(player_hand) == 21:
        payout = int(bet * 2.5)
        await update_chips(ctx.author.id, payout)
        embed = discord.Embed(
            title="🃏 Blackjack — Natural 21!",
            description=f"**{fmt_hand(player_hand)}**\n\n🎉 **Blackjack! You win {payout:,} Chips!** (2.5×)",
            color=discord.Color.gold(),
        )
        return await ctx.send(embed=embed)

    view = BlackjackView(self, ctx, bet, deck, player_hand, dealer_hand)
    msg = await ctx.send(embed=view.build_embed(), view=view)
    view.message = msg
```

**Step 4: Verify manually**

Run `!bj 100` — confirm deal, hit/stand/double work, dealer resolves correctly.

**Step 5: Commit**

```bash
git add cogs/gamble.py
git commit -m "feat: add Blackjack (!bj) with interactive Hit/Stand/Double Down"
```

---

## Task 6: Gamble — Higher or Lower (`!hilo`)

**Files:**
- Modify: `cogs/gamble.py`

**Step 1: Add HiloView class** before the `Gamble` class:

```python
HILO_MULTIPLIERS = [1.5, 2.0, 3.0, 5.0, 8.0]  # multiplier after N correct guesses

class HiloView(discord.ui.View):
    def __init__(self, cog, ctx, bet: int, deck: list, current_card: str):
        super().__init__(timeout=30)
        self.cog = cog
        self.ctx = ctx
        self.bet = bet
        self.deck = deck
        self.current_card = current_card
        self.streak = 0
        self.message = None

    def multiplier(self) -> float:
        idx = min(self.streak, len(HILO_MULTIPLIERS) - 1)
        return HILO_MULTIPLIERS[idx]

    def build_embed(self) -> discord.Embed:
        mult = self.multiplier()
        potential = int(self.bet * mult)
        embed = discord.Embed(title="🃏 Higher or Lower", color=discord.Color.teal())
        embed.add_field(name="Current Card", value=f"**{self.current_card}** ({card_value(self.current_card)})", inline=True)
        embed.add_field(name="Streak", value=f"{self.streak} correct", inline=True)
        embed.add_field(name="Cash Out Value", value=f"{potential:,} Chips ({mult}×)", inline=True)
        embed.set_footer(text=f"Bet: {self.bet:,} Chips — Is the next card higher or lower?")
        return embed

    async def _guess(self, interaction: discord.Interaction, guess: str):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)

        next_card = self.deck.pop()
        curr_val = card_value(self.current_card)
        next_val = card_value(next_card)

        correct = (guess == "higher" and next_val > curr_val) or \
                  (guess == "lower"  and next_val < curr_val)

        if next_val == curr_val:
            # Tie = push on that guess (neither win nor lose streak)
            self.current_card = next_card
            embed = self.build_embed()
            embed.description = f"🤝 **Tie!** Next card was also **{next_card}** ({next_val}). Keep going!"
            return await interaction.response.edit_message(embed=embed, view=self)

        if correct:
            self.streak += 1
            self.current_card = next_card
            if self.streak >= 5 or not self.deck:
                # Auto cash out at max streak
                await self._cash_out(interaction, auto=True)
            else:
                embed = self.build_embed()
                embed.description = f"✅ **Correct!** Next card was **{next_card}** ({next_val})."
                await interaction.response.edit_message(embed=embed, view=self)
        else:
            for child in self.children:
                child.disabled = True
            embed = discord.Embed(
                title="🃏 Higher or Lower",
                description=f"❌ **Wrong!** Next card was **{next_card}** ({next_val}). You lost **{self.bet:,} Chips**.",
                color=discord.Color.red(),
            )
            embed.set_footer(text=f"Better luck next time!")
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()

    async def _cash_out(self, interaction: discord.Interaction, auto=False):
        for child in self.children:
            child.disabled = True
        payout = int(self.bet * self.multiplier())
        await update_chips(self.ctx.author.id, payout)
        embed = discord.Embed(
            title="🃏 Higher or Lower",
            description=f"{'🏆 Max streak!' if auto else '💰 Cashed out!'} You won **{payout:,} Chips** ({self.multiplier()}×)!",
            color=discord.Color.green(),
        )
        if auto:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Higher ▲", style=discord.ButtonStyle.green)
    async def higher(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._guess(interaction, "higher")

    @discord.ui.button(label="Lower ▼", style=discord.ButtonStyle.red)
    async def lower(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._guess(interaction, "lower")

    @discord.ui.button(label="Cash Out 💰", style=discord.ButtonStyle.blurple)
    async def cash_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        if self.streak == 0:
            return await interaction.response.send_message("❌ Make at least one correct guess first!", ephemeral=True)
        await self._cash_out(interaction)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass
        if self.streak > 0:
            payout = int(self.bet * self.multiplier())
            await update_chips(self.ctx.author.id, payout)
```

**Step 2: Add the `!hilo` command** to the `Gamble` class:

```python
@commands.command(name="hilo", aliases=["hl"])
@commands.cooldown(1, 15, commands.BucketType.user)
async def hilo(self, ctx, amount: str):
    """Guess Higher or Lower for escalating Chip multipliers!"""
    bet = await self.get_bet_amount(ctx, amount)
    if bet == -1:
        ctx.command.reset_cooldown(ctx)
        return

    chips = await get_chips(ctx.author.id)
    if chips < bet:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(f"❌ You don't have enough Chips! (Balance: {chips:,})")

    await update_chips(ctx.author.id, -bet)

    deck = new_deck()
    random.shuffle(deck)
    current_card = deck.pop()

    view = HiloView(self, ctx, bet, deck, current_card)
    msg = await ctx.send(embed=view.build_embed(), view=view)
    view.message = msg
```

**Step 3: Verify manually**

Run `!hilo 100` — confirm guessing works, streak increments, cash out pays correctly, wrong guess loses bet.

**Step 4: Commit**

```bash
git add cogs/gamble.py
git commit -m "feat: add Higher or Lower (!hilo) with streak multipliers"
```

---

## Task 7: Gamble — Cosmic Dice Duel (`!dice`)

**Files:**
- Modify: `cogs/gamble.py`

**Step 1: Add `!dice` command** to the `Gamble` class:

```python
@commands.command(name="dice", aliases=["roll"])
@commands.cooldown(1, 15, commands.BucketType.user)
async def dice_duel(self, ctx, amount: str):
    """Roll 2d6 against Flicker! Higher total wins 2× your Chips."""
    bet = await self.get_bet_amount(ctx, amount)
    if bet == -1:
        ctx.command.reset_cooldown(ctx)
        return

    chips = await get_chips(ctx.author.id)
    if chips < bet:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(f"❌ You don't have enough Chips! (Balance: {chips:,})")

    await update_chips(ctx.author.id, -bet)

    # Player rolls
    p1, p2 = random.randint(1, 6), random.randint(1, 6)
    player_total = p1 + p2

    # Flicker rolls — with disadvantage for boss
    f1, f2 = random.randint(1, 6), random.randint(1, 6)
    if ctx.author.id == self.boss_id:
        # Re-roll the highest die and take the lower result
        if f1 >= f2:
            f1 = min(f1, random.randint(1, 6))
        else:
            f2 = min(f2, random.randint(1, 6))
    flicker_total = f1 + f2

    # Animation
    embed = discord.Embed(title="🎲 Cosmic Dice Duel", color=discord.Color.blue())
    embed.description = f"**{ctx.author.display_name}** rolls their dice... 🎲🎲"
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(1.5)

    embed.description = (
        f"**{ctx.author.display_name}:** 🎲 {p1} + {p2} = **{player_total}**\n"
        f"**Flicker:** 🎲 {f1} + {f2} = **{flicker_total}**"
    )
    await msg.edit(embed=embed)
    await asyncio.sleep(1.0)

    if player_total > flicker_total:
        winnings = bet * 2
        await update_chips(ctx.author.id, winnings)
        embed.color = discord.Color.green()
        embed.description += f"\n\n🎉 **You win {winnings:,} Chips!**"
    elif player_total == flicker_total:
        await update_chips(ctx.author.id, bet)
        embed.color = discord.Color.greyple()
        embed.description += f"\n\n🤝 **Tie! Bet refunded.**"
    else:
        embed.color = discord.Color.red()
        embed.description += f"\n\n❌ **Flicker wins. Better luck next time.**"

    await msg.edit(embed=embed)
```

**Step 2: Verify manually**

Run `!dice 100` — confirm animation, correct winner determination, chip changes.

**Step 3: Commit**

```bash
git add cogs/gamble.py
git commit -m "feat: add Cosmic Dice Duel (!dice)"
```

---

## Task 8: Gamble — Starwheel Roulette (`!roulette`)

**Files:**
- Modify: `cogs/gamble.py`

**Step 1: Add roulette wheel data** near the top of `gamble.py` (with other constants):

```python
# Roulette: European single-zero wheel — 0 is green, alternating red/black
ROULETTE_RED = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
ROULETTE_BLACK = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}
ROULETTE_SPIN_FRAMES = ["🌀", "💫", "⭐", "🌟", "✨"]
```

**Step 2: Add `!roulette` command** to the `Gamble` class:

```python
@commands.command(name="roulette", aliases=["rt"])
@commands.cooldown(1, 15, commands.BucketType.user)
async def roulette(self, ctx, amount: str, *, bet_input: str):
    """Bet on the Starwheel! Usage: !roulette <chips> <red|black|odd|even|0-36>"""
    bet = await self.get_bet_amount(ctx, amount)
    if bet == -1:
        ctx.command.reset_cooldown(ctx)
        return

    chips = await get_chips(ctx.author.id)
    if chips < bet:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(f"❌ You don't have enough Chips! (Balance: {chips:,})")

    bet_type = bet_input.strip().lower()
    valid_types = {"red", "black", "odd", "even"} | {str(n) for n in range(37)}
    if bet_type not in valid_types:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Bet must be `red`, `black`, `odd`, `even`, or a number 0–36.")

    await update_chips(ctx.author.id, -bet)

    # Spin — boss nudges number bets
    result = random.randint(0, 36)
    if ctx.author.id == self.boss_id and bet_type.isdigit():
        target = int(bet_type)
        # 40% chance to land within 2 of the target
        if random.random() < 0.40:
            result = target + random.randint(-2, 2)
            result = max(0, min(36, result))

    result_color = "🟢" if result == 0 else ("🔴" if result in ROULETTE_RED else "⚫")

    # Spin animation
    embed = discord.Embed(title="🎡 Starwheel Roulette", color=discord.Color.purple())
    embed.description = f"Spinning the cosmic wheel... {ROULETTE_SPIN_FRAMES[0]}"
    msg = await ctx.send(embed=embed)
    for frame in ROULETTE_SPIN_FRAMES[1:]:
        await asyncio.sleep(0.6)
        embed.description = f"Spinning the cosmic wheel... {frame}"
        await msg.edit(embed=embed)
    await asyncio.sleep(0.8)

    # Determine win
    if bet_type == "red":
        won = result in ROULETTE_RED
        multiplier = 1.9
    elif bet_type == "black":
        won = result in ROULETTE_BLACK
        multiplier = 1.9
    elif bet_type == "odd":
        won = result != 0 and result % 2 == 1
        multiplier = 1.9
    elif bet_type == "even":
        won = result != 0 and result % 2 == 0
        multiplier = 1.9
    else:
        won = result == int(bet_type)
        multiplier = 35.0

    result_line = f"The wheel landed on **{result_color} {result}**!"

    if won:
        winnings = int(bet * multiplier)
        await update_chips(ctx.author.id, winnings)
        embed.color = discord.Color.green()
        embed.description = f"{result_line}\n\n🎉 **You win {winnings:,} Chips!** ({multiplier}×)"
    else:
        embed.color = discord.Color.red()
        embed.description = f"{result_line}\n\n❌ **You lost {bet:,} Chips.**"

    embed.set_footer(text=f"Bet: {bet_input} · {bet:,} Chips wagered")
    await msg.edit(embed=embed)
```

**Step 3: Verify manually**

Run `!roulette 100 red`, `!roulette 100 7` — confirm animation, payout math, correct color/number detection.

**Step 4: Commit**

```bash
git add cogs/gamble.py
git commit -m "feat: add Starwheel Roulette (!roulette)"
```

---

## Task 9: Events — Word Scramble and Emoji Sequence

**Files:**
- Modify: `cogs/events.py`

**Step 1: Add word and emoji pools** at the top of `events.py`, after imports:

```python
SCRAMBLE_WORDS = [
    "nebula", "galaxy", "cosmos", "pulsar", "quasar", "meteor", "comet",
    "planet", "stellar", "aurora", "eclipse", "photon", "neutron", "orbit",
    "zenith", "cosmic", "solaris", "astral", "radiant", "vortex",
]

SPACE_EMOJIS = ["🌙", "⭐", "🪐", "💫", "✨", "🌟", "☄️", "🚀", "🛸", "🌌"]
```

**Step 2: Add two new event methods** to the `Events` class:

```python
async def event_word_scramble(self, channel):
    reward = random.randint(15, 30)
    word = random.choice(SCRAMBLE_WORDS)

    # Scramble: shuffle until different from original
    chars = list(word)
    scrambled = word
    while scrambled == word:
        random.shuffle(chars)
        scrambled = "".join(chars)

    embed = discord.Embed(
        title="🔤 Galactic Scramble!",
        description=f"Flicker's star charts got all mixed up!\n\nUnscramble this cosmic word:\n\n**`{scrambled.upper()}`**",
        color=discord.Color.blue(),
    )
    embed.set_footer(text=f"You have 20 seconds! Reward: {reward} Stardust")
    await channel.send(embed=embed)

    def check(m):
        return m.channel == channel and not m.author.bot and m.content.lower().strip() == word

    try:
        winner = await self.bot.wait_for("message", check=check, timeout=20.0)
        await update_balance(winner.author.id, reward)
        await channel.send(f"🌟 **Brilliant!** {winner.author.mention} unscrambled **{word}** and earned **{reward} Stardust**!")
    except asyncio.TimeoutError:
        await channel.send(f"💨 **Time's up!** The word was **{word}**.")


async def event_emoji_sequence(self, channel):
    reward = random.randint(10, 25)
    sequence = random.choices(SPACE_EMOJIS, k=4)
    sequence_str = " ".join(sequence)

    embed = discord.Embed(
        title="🌌 Star Pattern!",
        description=f"Flicker spotted a cosmic pattern in the stars!\n\nRepeat this sequence exactly:\n\n**{sequence_str}**",
        color=discord.Color.og_blurple(),
    )
    embed.set_footer(text=f"You have 15 seconds! Reward: {reward} Stardust")
    await channel.send(embed=embed)

    def check(m):
        return m.channel == channel and not m.author.bot and m.content.strip() == sequence_str

    try:
        winner = await self.bot.wait_for("message", check=check, timeout=15.0)
        await update_balance(winner.author.id, reward)
        await channel.send(f"✨ **Perfect!** {winner.author.mention} matched the pattern and earned **{reward} Stardust**!")
    except asyncio.TimeoutError:
        await channel.send(f"🌠 **Gone!** The pattern faded. It was: {sequence_str}")
```

**Step 3: Register the new events in `trigger_event` and `on_message`**

In `trigger_event`, add two new `elif` branches:
```python
elif game_type == "word_scramble": await self.event_word_scramble(channel)
elif game_type == "emoji_sequence": await self.event_emoji_sequence(channel)
```

In `on_message`, extend the chance chain (keeping total rate similar):
```python
if chance < 0.05:
    await self.trigger_event(message.channel, "drop")
elif chance < 0.06:
    await self.trigger_event(message.channel, "trivia")
elif chance < 0.07:
    await self.trigger_event(message.channel, "math")
elif chance < 0.08:
    await self.trigger_event(message.channel, "fast_type")
elif chance < 0.09:
    await self.trigger_event(message.channel, "word_scramble")
elif chance < 0.10:
    await self.trigger_event(message.channel, "emoji_sequence")
```

In `simulate_event`, add the new types to the choices list:
```python
target_game = game_type if game_type else random.choice(
    ["drop", "trivia", "math", "fast_type", "word_scramble", "emoji_sequence"]
)
```

**Note:** `discord.Color.og_blurple()` is valid in discord.py 2.x. If it causes an error, substitute `discord.Color.blurple()`.

**Step 4: Verify manually**

Run `!simulate word_scramble` and `!simulate emoji_sequence` — confirm embeds appear and correct answers are accepted.

**Step 5: Commit**

```bash
git add cogs/events.py
git commit -m "feat: add Word Scramble and Emoji Sequence passive events"
```

---

## Task 10: Final check and CLAUDE.md update

**Step 1: Run the bot and smoke-test all features**

```
!balance          — shows Stardust + Chips
!buychips 10      — deducts 10 Stardust, adds 500 Chips
!top              — shows two-column leaderboard
!shop #channel    — triggers modal flow (attach image optionally)
!cf 100 h         — coinflip with Chips
!slots 100        — slots with Chips
!bj 100           — blackjack with Hit/Stand/Double
!hilo 100         — higher-or-lower with multipliers
!dice 100         — dice duel vs Flicker
!roulette 100 red — roulette colour bet
!roulette 100 7   — roulette number bet
!simulate word_scramble
!simulate emoji_sequence
```

**Step 2: Update CLAUDE.md** to reflect new commands table and dual-currency architecture.

**Step 3: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for dual currency expansion"
```
