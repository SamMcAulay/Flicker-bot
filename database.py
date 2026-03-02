import aiosqlite
import os

if os.getenv("RAILWAY_ENVIRONMENT"):
    DB_NAME = "/data/flicker.db"
else:
    DB_NAME = "flicker.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)")
        await db.execute("CREATE TABLE IF NOT EXISTS allowed_channels (channel_id INTEGER PRIMARY KEY)")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS active_tickets (
                ticket_channel_id INTEGER PRIMARY KEY,
                message_id INTEGER,
                buyer_id INTEGER,
                shop_channel_id INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                message_id INTEGER PRIMARY KEY,
                stock INTEGER,
                role_id INTEGER,
                stardust_price INTEGER,
                usd_price REAL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS verification_config (
                guild_id INTEGER PRIMARY KEY,
                role_id INTEGER
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS vc_config (
                guild_id INTEGER PRIMARY KEY,
                generator_vc_id INTEGER,
                verified_role_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.commit()

        # Safe migration: add chips column if it doesn't exist yet
        try:
            await db.execute("ALTER TABLE users ADD COLUMN chips INTEGER DEFAULT 0")
            await db.commit()
        except aiosqlite.OperationalError:
            pass  # Column already exists

        # Safe migration: add chips_price column to shop_items
        try:
            await db.execute("ALTER TABLE shop_items ADD COLUMN chips_price INTEGER DEFAULT 0")
            await db.commit()
        except aiosqlite.OperationalError:
            pass  # Column already exists

# --- ECONOMY ---
async def get_balance(user_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row: return row[0]
            else:
                await db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 0))
                await db.commit()
                return 0

async def update_balance(user_id: int, amount: int) -> int:
    current = await get_balance(user_id)
    new_balance = current + amount
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        await db.commit()
    return new_balance

async def get_chips(user_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT chips FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            else:
                await db.execute("INSERT OR IGNORE INTO users (user_id, balance, chips) VALUES (?, 0, 0)", (user_id,))
                await db.commit()
                return 0

async def update_chips(user_id: int, amount: int) -> int:
    current = await get_chips(user_id)
    new_chips = current + amount
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET chips = ? WHERE user_id = ?", (new_chips, user_id))
        await db.commit()
    return new_chips

async def get_top_users(limit: int = 10):
    """Returns (top_stardust, top_chips) as two lists of (user_id, value)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT user_id, balance FROM users WHERE balance > 0 ORDER BY balance DESC LIMIT ?", (limit,)
        ) as cursor:
            top_stardust = await cursor.fetchall()
        async with db.execute(
            "SELECT user_id, chips FROM users WHERE chips > 0 ORDER BY chips DESC LIMIT ?", (limit,)
        ) as cursor:
            top_chips = await cursor.fetchall()
    return top_stardust, top_chips

# --- STATS ---
async def increment_stat(key: str, amount: int = 1) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO stats (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = value + excluded.value",
            (key, amount)
        )
        await db.commit()

async def get_all_stats() -> dict:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT key, value FROM stats") as cursor:
            rows = await cursor.fetchall()
    return {row[0]: row[1] for row in rows}

# --- ALLOWED CHANNELS ---
async def add_allowed_channel(channel_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO allowed_channels (channel_id) VALUES (?)", (channel_id,))
        await db.commit()

async def remove_allowed_channel(channel_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM allowed_channels WHERE channel_id = ?", (channel_id,))
        await db.commit()

async def get_allowed_channels():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT channel_id FROM allowed_channels") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

# --- TICKET LOCKS (UPDATED) ---
async def is_listing_locked(message_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT ticket_channel_id FROM active_tickets WHERE message_id = ?", (message_id,)) as cursor:
            return await cursor.fetchone() is not None

async def lock_listing(message_id: int, ticket_channel_id: int, buyer_id: int, shop_channel_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO active_tickets (ticket_channel_id, message_id, buyer_id, shop_channel_id) VALUES (?, ?, ?, ?)", 
                         (ticket_channel_id, message_id, buyer_id, shop_channel_id))
        await db.commit()

async def unlock_listing(ticket_channel_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM active_tickets WHERE ticket_channel_id = ?", (ticket_channel_id,))
        await db.commit()

async def get_lock_details(ticket_channel_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT message_id, buyer_id, shop_channel_id FROM active_tickets WHERE ticket_channel_id = ?", (ticket_channel_id,)) as cursor:
            return await cursor.fetchone()

# --- SHOP ITEMS ---
async def create_shop_item(message_id, stock, role_id, stardust, chips, usd):
    """Registers a new shop item in the DB."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO shop_items (message_id, stock, role_id, stardust_price, chips_price, usd_price) VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, stock, role_id, stardust, chips, usd)
        )
        await db.commit()

async def get_shop_item(message_id):
    """Returns (stock, role_id, stardust_price, chips_price, usd_price)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT stock, role_id, stardust_price, chips_price, usd_price FROM shop_items WHERE message_id = ?",
            (message_id,)
        ) as cursor:
            return await cursor.fetchone()

async def decrement_stock(message_id):
    """Lowers stock by 1. If stock is -1 (infinite), it stays -1."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT stock FROM shop_items WHERE message_id = ?", (message_id,)) as cursor:
            row = await cursor.fetchone()
            if not row: return
            current_stock = row[0]
        
        if current_stock == -1:
            return
        
        if current_stock > 0:
            await db.execute("UPDATE shop_items SET stock = stock - 1 WHERE message_id = ?", (message_id,))
            await db.commit()

# --- VERIFICATION SYSTEM ---
async def set_verify_role(guild_id: int, role_id: int):
    """Saves the verified role for the server."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO verification_config (guild_id, role_id) VALUES (?, ?)", (guild_id, role_id))
        await db.commit()

async def get_verify_role(guild_id: int):
    """Gets the verified role for the server."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT role_id FROM verification_config WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

# --- VOICE CHANNEL SYSTEM ---
async def set_vc_config(guild_id: int, generator_vc_id: int, verified_role_id: int):
    """Saves the VC generator configuration."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO vc_config (guild_id, generator_vc_id, verified_role_id) VALUES (?, ?, ?)", 
                         (guild_id, generator_vc_id, verified_role_id))
        await db.commit()

async def get_vc_config(guild_id: int):
    """Gets the VC config: Returns (generator_vc_id, verified_role_id)"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT generator_vc_id, verified_role_id FROM vc_config WHERE guild_id = ?", (guild_id,)) as cursor:
            return await cursor.fetchone()