import aiosqlite

DB_NAME = "flicker.db"

async def init_db():
    """Initializes the database tables."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        """)
        await db.commit()

async def get_balance(user_id: int) -> int:
    """Fetch user balance. Creates user if they don't exist."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            else:
                await db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 0))
                await db.commit()
                return 0

async def update_balance(user_id: int, amount: int) -> int:
    """Safely updates balance. Returns new balance."""
    current = await get_balance(user_id)
    new_balance = current + amount
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        await db.commit()
    return new_balance
