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
            CREATE TABLE IF NOT EXISTS shop_locks (
                message_id INTEGER PRIMARY KEY,
                ticket_channel_id INTEGER,
                buyer_id INTEGER,
                shop_channel_id INTEGER
            )
        """)
        
        # Migration: Attempt to add the column if it's missing (for existing dbs)
        try:
            await db.execute("ALTER TABLE shop_locks ADD COLUMN shop_channel_id INTEGER")
        except:
            pass
            
        await db.commit()

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

# --- CHANNELS ---
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

# --- SHOP LOCKS ---
async def is_listing_locked(message_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT ticket_channel_id FROM shop_locks WHERE message_id = ?", (message_id,)) as cursor:
            return await cursor.fetchone() is not None

async def lock_listing(message_id: int, ticket_channel_id: int, buyer_id: int, shop_channel_id: int):
    """Locks the listing and stores location data."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO shop_locks (message_id, ticket_channel_id, buyer_id, shop_channel_id) VALUES (?, ?, ?, ?)", 
                         (message_id, ticket_channel_id, buyer_id, shop_channel_id))
        await db.commit()

async def unlock_listing(ticket_channel_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM shop_locks WHERE ticket_channel_id = ?", (ticket_channel_id,))
        await db.commit()

async def get_lock_details(ticket_channel_id: int):
    """Retrieves info about the locked item using the ticket ID."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT message_id, buyer_id, shop_channel_id FROM shop_locks WHERE ticket_channel_id = ?", (ticket_channel_id,)) as cursor:
            return await cursor.fetchone()
