import aiosqlite
import json
import os

if os.getenv("RAILWAY_ENVIRONMENT"):
    DB_NAME = "/data/flicker.db"
else:
    DB_NAME = "flicker.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)")
        # Per-server economy table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_balances (
                user_id  INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                balance  INTEGER DEFAULT 0,
                chips    INTEGER DEFAULT 0,
                pet_streak    INTEGER DEFAULT 0,
                last_pet_time REAL    DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_game_stats (
                user_id INTEGER NOT NULL,
                game    TEXT NOT NULL,
                played  INTEGER DEFAULT 0,
                wagered INTEGER DEFAULT 0,
                earnt   INTEGER DEFAULT 0,
                lost    INTEGER DEFAULT 0,
                biggest_win INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, game)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id INTEGER PRIMARY KEY,
                command_toggles TEXT DEFAULT '{}',
                game_toggles TEXT DEFAULT '{}',
                event_toggles TEXT DEFAULT '{}',
                payout_overrides TEXT DEFAULT '{}'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS custom_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                trigger_words TEXT NOT NULL,
                response_text TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS response_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                triggers TEXT NOT NULL,
                responses TEXT NOT NULL,
                enabled INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                user_id     INTEGER NOT NULL,
                guild_id    INTEGER NOT NULL,
                key         TEXT    NOT NULL,
                unlocked_at INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, guild_id, key)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id        INTEGER NOT NULL,
                channel_id      INTEGER NOT NULL,
                message_id      INTEGER,
                prize_desc      TEXT    NOT NULL,
                end_time        REAL    NOT NULL,
                winner_count    INTEGER DEFAULT 1,
                entry_cost      INTEGER DEFAULT 0,
                entry_currency  TEXT    DEFAULT 'stardust',
                ended           INTEGER DEFAULT 0,
                creator_id      INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_entries (
                giveaway_id INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                PRIMARY KEY (giveaway_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS polls (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                question   TEXT    NOT NULL,
                options    TEXT    NOT NULL,
                ended      INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blocked_users (
                user_id    INTEGER PRIMARY KEY,
                reason     TEXT DEFAULT '',
                blocked_at INTEGER DEFAULT 0,
                blocked_by INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_audit_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id  INTEGER NOT NULL,
                action    TEXT NOT NULL,
                guild_id  INTEGER,
                target_id INTEGER,
                details   TEXT DEFAULT '',
                timestamp INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_xp (
                user_id  INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                xp       INTEGER DEFAULT 0,
                level    INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reaction_role_panels (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                message_id  INTEGER NOT NULL,
                title       TEXT DEFAULT '',
                description TEXT DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reaction_role_entries (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                panel_id INTEGER NOT NULL,
                emoji    TEXT NOT NULL,
                role_id  INTEGER NOT NULL,
                label    TEXT DEFAULT ''
            )
        """)

        # ── Support Ticket System ──
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_config (
                guild_id           INTEGER PRIMARY KEY,
                enabled            INTEGER DEFAULT 0,
                log_channel_id     INTEGER DEFAULT 0,
                category_id        INTEGER DEFAULT 0,
                naming_format      TEXT    DEFAULT 'ticket-{number}',
                next_ticket_number INTEGER DEFAULT 1,
                dm_transcript      INTEGER DEFAULT 0,
                claim_lock         INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_panels (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id     INTEGER NOT NULL,
                channel_id   INTEGER NOT NULL,
                message_id   INTEGER NOT NULL,
                title        TEXT    DEFAULT 'Support Tickets',
                description  TEXT    DEFAULT 'Click below to open a ticket.',
                color        INTEGER DEFAULT 5865207,
                button_label TEXT    DEFAULT 'Open Ticket',
                button_emoji TEXT    DEFAULT '🎫',
                button_style INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_categories (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                panel_id        INTEGER NOT NULL,
                name            TEXT    NOT NULL,
                emoji           TEXT    DEFAULT '📩',
                description     TEXT    DEFAULT '',
                opening_message TEXT    DEFAULT '',
                staff_roles     TEXT    DEFAULT '[]',
                ticket_limit    INTEGER DEFAULT 1,
                form_fields     TEXT    DEFAULT '[]'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id       INTEGER NOT NULL,
                channel_id     INTEGER NOT NULL,
                user_id        INTEGER NOT NULL,
                category_id    INTEGER NOT NULL,
                panel_id       INTEGER NOT NULL,
                ticket_number  INTEGER NOT NULL,
                claimed_by     INTEGER DEFAULT 0,
                status         TEXT    DEFAULT 'open',
                created_at     REAL    NOT NULL,
                closed_at      REAL    DEFAULT 0,
                closed_by      INTEGER DEFAULT 0,
                transcript_url TEXT    DEFAULT ''
            )
        """)

        await db.commit()

        # Safe migration: add pet streak columns
        try:
            await db.execute("ALTER TABLE users ADD COLUMN pet_streak INTEGER DEFAULT 0")
            await db.commit()
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN last_pet_time REAL DEFAULT 0")
            await db.commit()
        except aiosqlite.OperationalError:
            pass

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

        # Safe migration: add chat_toggles column to server_settings
        try:
            await db.execute("ALTER TABLE server_settings ADD COLUMN chat_toggles TEXT DEFAULT '{}'")
            await db.commit()
        except aiosqlite.OperationalError:
            pass

        # Safe migration: add prefix column to server_settings
        try:
            await db.execute("ALTER TABLE server_settings ADD COLUMN prefix TEXT DEFAULT '!'")
            await db.commit()
        except aiosqlite.OperationalError:
            pass

        # Safe migration: add text_overrides column to server_settings
        try:
            await db.execute("ALTER TABLE server_settings ADD COLUMN text_overrides TEXT DEFAULT '{}'")
            await db.commit()
        except aiosqlite.OperationalError:
            pass

        # Safe migration: add bot_disabled column to server_settings
        try:
            await db.execute("ALTER TABLE server_settings ADD COLUMN bot_disabled INTEGER DEFAULT 0")
            await db.commit()
        except aiosqlite.OperationalError:
            pass

        # Safe migration: add welcome_config column to server_settings
        try:
            await db.execute("ALTER TABLE server_settings ADD COLUMN welcome_config TEXT DEFAULT '{}'")
            await db.commit()
        except aiosqlite.OperationalError:
            pass

        # Safe migration: add bias_settings column to server_settings
        try:
            await db.execute("ALTER TABLE server_settings ADD COLUMN bias_settings TEXT DEFAULT '{}'")
            await db.commit()
        except aiosqlite.OperationalError:
            pass

        # Safe migration: add leveling_config column to server_settings
        try:
            await db.execute("ALTER TABLE server_settings ADD COLUMN leveling_config TEXT DEFAULT '{}'")
            await db.commit()
        except aiosqlite.OperationalError:
            pass

        # Safe migrations: add social columns to user_balances
        for col_sql in [
            "ALTER TABLE user_balances ADD COLUMN daily_streak INTEGER DEFAULT 0",
            "ALTER TABLE user_balances ADD COLUMN last_daily REAL DEFAULT 0",
            "ALTER TABLE user_balances ADD COLUMN last_work REAL DEFAULT 0",
            "ALTER TABLE user_balances ADD COLUMN rep_count INTEGER DEFAULT 0",
            "ALTER TABLE user_balances ADD COLUMN last_rep_given REAL DEFAULT 0",
            "ALTER TABLE user_balances ADD COLUMN work_count INTEGER DEFAULT 0",
        ]:
            try:
                await db.execute(col_sql)
                await db.commit()
            except aiosqlite.OperationalError:
                pass

# --- ECONOMY (per-server) ---

async def _ensure_user(db, user_id: int, guild_id: int) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO user_balances (user_id, guild_id) VALUES (?, ?)",
        (user_id, guild_id)
    )

async def get_balance(user_id: int, guild_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.commit()
        async with db.execute(
            "SELECT balance FROM user_balances WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def update_balance(user_id: int, guild_id: int, amount: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.execute(
            "UPDATE user_balances SET balance = MAX(0, balance + ?) WHERE user_id = ? AND guild_id = ?",
            (amount, user_id, guild_id)
        )
        await db.commit()
        async with db.execute(
            "SELECT balance FROM user_balances WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_chips(user_id: int, guild_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.commit()
        async with db.execute(
            "SELECT chips FROM user_balances WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def update_chips(user_id: int, guild_id: int, amount: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.execute(
            "UPDATE user_balances SET chips = MAX(0, chips + ?) WHERE user_id = ? AND guild_id = ?",
            (amount, user_id, guild_id)
        )
        await db.commit()
        async with db.execute(
            "SELECT chips FROM user_balances WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_top_users(guild_id: int, limit: int = 10):
    """Returns (top_stardust, top_chips) as two lists of (user_id, value) for a specific guild."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT user_id, balance FROM user_balances WHERE guild_id = ? AND balance > 0 ORDER BY balance DESC LIMIT ?",
            (guild_id, limit)
        ) as cursor:
            top_stardust = await cursor.fetchall()
        async with db.execute(
            "SELECT user_id, chips FROM user_balances WHERE guild_id = ? AND chips > 0 ORDER BY chips DESC LIMIT ?",
            (guild_id, limit)
        ) as cursor:
            top_chips = await cursor.fetchall()
    return top_stardust, top_chips

# --- PET STREAK (per-server) ---
async def get_pet_data(user_id: int, guild_id: int) -> tuple:
    """Returns (pet_streak, last_pet_time)."""
    async with aiosqlite.connect(DB_NAME) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.commit()
        async with db.execute(
            "SELECT pet_streak, last_pet_time FROM user_balances WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row if row else (0, 0.0)

async def update_pet_data(user_id: int, guild_id: int, streak: int, last_pet_time: float) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.execute(
            "UPDATE user_balances SET pet_streak = ?, last_pet_time = ? WHERE user_id = ? AND guild_id = ?",
            (streak, last_pet_time, user_id, guild_id)
        )
        await db.commit()

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

async def reset_chip_stats() -> None:
    """Resets chips_wagered, chips_earnt, and chips_lost to 0. Does not touch user balances."""
    async with aiosqlite.connect(DB_NAME) as db:
        for key in ("chips_wagered", "chips_earnt", "chips_lost"):
            await db.execute(
                "INSERT INTO stats (key, value) VALUES (?, 0) ON CONFLICT(key) DO UPDATE SET value = 0",
                (key,)
            )
        await db.commit()

# --- PER-USER GAME STATS ---
async def record_user_game(user_id: int, game: str, wagered: int, earnt: int = 0, lost: int = 0, biggest_win: int = 0) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO user_game_stats (user_id, game, played, wagered, earnt, lost, biggest_win)
            VALUES (?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(user_id, game) DO UPDATE SET
                played      = played + 1,
                wagered     = wagered + excluded.wagered,
                earnt       = earnt + excluded.earnt,
                lost        = lost + excluded.lost,
                biggest_win = MAX(biggest_win, excluded.biggest_win)
            """,
            (user_id, game, wagered, earnt, lost, biggest_win)
        )
        await db.commit()

async def get_user_game_stats(user_id: int) -> dict:
    """Returns a dict keyed by game name → (played, wagered, earnt, lost, biggest_win)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT game, played, wagered, earnt, lost, biggest_win FROM user_game_stats WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
    return {row[0]: row[1:] for row in rows}

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

# --- SERVER SETTINGS ---
_DEFAULT_GAME_TOGGLES = {
    "coinflip": True, "slots": True, "blackjack": True, "hilo": True,
    "roulette": True, "warp": True, "dice": True, "crash": True, "rps": True,
}
_DEFAULT_EVENT_TOGGLES = {"chat_drops": True, "trivia": True, "math": True, "fast_type": True, "word_scramble": True}
_DEFAULT_COMMAND_TOGGLES = {
    "balance": True, "pay": True, "buychips": True, "top": True,
    "daily": True, "rob": True,
    "profile": True, "rep": True, "poll": True, "giveaway": True,
}
_DEFAULT_CHAT_TOGGLES = {"greet": True, "bye": True, "thanks": True, "love": True, "kill": True, "trial": True, "fact": True}

ACHIEVEMENTS = {
    "first_stardust": {"name": "First Light",            "desc": "Earn your first Stardust",        "icon": "⭐"},
    "daily_3":        {"name": "Consistent",             "desc": "Reach a 3-day daily streak",      "icon": "📅"},
    "daily_7":        {"name": "Habit Formed",           "desc": "Reach a 7-day daily streak",      "icon": "🗓️"},
    "daily_30":       {"name": "Dedicated",              "desc": "Reach a 30-day daily streak",     "icon": "💪"},
    "rich_1000":      {"name": "Star Rich",              "desc": "Hold 1,000 Stardust at once",     "icon": "💰"},
    "rich_10000":     {"name": "Galaxy Brain",           "desc": "Hold 10,000 Stardust at once",    "icon": "🌌"},
    "chips_10000":    {"name": "High Roller",            "desc": "Hold 10,000 Chips at once",       "icon": "🎰"},
    "well_loved":     {"name": "Well Loved",             "desc": "Receive 5 reputation points",     "icon": "❤️"},
    "robber":         {"name": "Five Finger Discount",   "desc": "Successfully rob someone",        "icon": "🦝"},
    "gambler":        {"name": "Risk Taker",             "desc": "Wager Chips for the first time",  "icon": "🎲"},
}

_DEFAULT_WELCOME_CONFIG = {
    "enabled": False,
    "channel_id": None,
    "message": "Welcome {user} to **{server}**!",
    "embed_title": "Welcome!",
    "embed_color": "#5b8ef7",
    "use_embed": True,
    "embed_footer": "",
    "embed_image_url": "",
    "embed_thumbnail": True,
}
_DEFAULT_LEVELING_CONFIG = {
    "enabled": False,
    "channel_id": None,
    "xp_per_message_min": 5,
    "xp_per_message_max": 15,
    "xp_cooldown_seconds": 60,
    "xp_per_level": 100,
    "announce_levelup": True,
    "levelup_message": "🎉 {user} just reached **Level {level}**!",
    "milestones": [],
}
_DEFAULT_TEXT_OVERRIDES = {
    # Drop
    "drop_title":        "A reward dropped!",
    "drop_desc":         "Grab it before it's gone!",
    "drop_catch_prompt": "type **catch**!",
    "drop_win":          "**All done!**",
    "drop_lose":         "**Too slow!** The reward disappeared.",
    # Fast Type
    "fast_type_title":   "⌨️ Type it Quick!",
    "fast_type_desc":    "Quick! Type this code before time runs out:",
    "fast_type_win":     "✅ **Got it!** {winner} earned **{reward} Stardust**!",
    "fast_type_lose":    "⏰ **Time's up!** The code was `{code}`.",
    # Math
    "math_title":        "🧮 Math Challenge!",
    "math_desc":         "Solve this to earn a reward. What is:",
    "math_win":          "✅ **Correct!** {winner} solved it and earned **{reward} Stardust**!",
    "math_lose":         "⏰ **Time's up!** The answer was **{answer}**.",
    # Trivia
    "trivia_title":      "❓ Trivia Time!",
    "trivia_tagline":    "*Pick your answer!*",
    "trivia_correct":    "🎉 **Correct!** The answer was **{answer}**. {winner} earned **{reward} Stardust**!",
    "trivia_wrong":      "❌ **Wrong!** The answer was **{answer}**.",
    "trivia_timeout":    "⏰ **Time's up!** The answer was **{answer}**.",
    # Word Scramble
    "scramble_title":    "🔤 Word Scramble!",
    "scramble_desc":     "Unscramble this word:",
    "scramble_win":      "✅ **Nice work!** {winner} unscrambled **{word}** and earned **{reward} Stardust**!",
    "scramble_lose":     "⏰ **Time's up!** The word was **{word}**.",
    # Coinflip
    "cf_spinning":       "The coin is spinning...",
    "cf_win":            "It landed on **{result}**! {icon}\n🎉 You won **{winnings}** Chips!",
    "cf_lose":           "It landed on **{result}**! {icon}\n❌ You lost **{bet}** Chips.",
    # Slots
    "slots_title":       "🎰 Slots",
    "slots_win":         "🎉 **WINNER!**\nYou won **{winnings}** Chips! ({multiplier}×)",
    "slots_lose":        "❌ **No match!**\nBetter luck next time.",
    # Blackjack
    "bj_title":          "🃏 Blackjack",
    "bj_natural_win":    "🎉 **Blackjack! You win {payout} Chips!** (2.5×)",
    "bj_bust":           "💥 Bust! You lose.",
    "bj_win":            "🎉 You win!",
    "bj_push":           "🤝 Push — bet returned.",
    "bj_dealer_wins":    "❌ Dealer wins.",
    # Higher or Lower
    "hilo_title":        "🃏 Higher or Lower",
    "hilo_tie":          "🤝 **Tie!** Next card was **{card}** ({value}). Keep going!",
    "hilo_correct":      "✅ **Correct!** Next card was **{card}** ({value}).",
    "hilo_wrong":        "❌ **Wrong!** Next card was **{card}** ({value}). You lost **{bet}** Chips.",
    "hilo_cashout":      "💰 **Cashed out!** You won **{payout}** Chips ({mult}×)!",
    # Warp
    "warp_title":        "🚀 Warp Drive",
    "warp_start":        "Push your luck for escalating multipliers. Do you dare?",
    "warp_overload":     "💥 **OVERLOAD!** You lost **{bet}** Chips.",
    "warp_jump":         "✅ **Jump {jumps} successful!**",
    "warp_dock":         "🛸 **Docked!** You returned with **{payout}** Chips ({mult}×)!",
    # Roulette
    "rt_title":          "🎡 Roulette",
    "rt_spinning":       "Spinning the wheel...",
    "rt_win":            "🎉 **You win {winnings} Chips!** ({multiplier}×)",
    "rt_lose":           "❌ **You lost {bet} Chips.**",
    # Dice
    "dice_title":        "🎲 Dice Roll",
    "dice_win":          "🎉 **You win {winnings} Chips!** ({multiplier}×)",
    "dice_lose":         "❌ **You lost {bet} Chips.**",
    # Crash
    "crash_title":       "📈 Crash",
    "crash_cashed_out":  "💰 **Cashed out at {mult}×!** You won **{payout}** Chips!",
    "crash_crashed":     "💥 **CRASHED at {mult}×!** You lost **{bet}** Chips.",
    # RPS
    "rps_title":         "✊ Rock Paper Scissors",
    "rps_win":           "🎉 **You win {winnings} Chips!** ({multiplier}×)",
    "rps_lose":          "❌ **You lost {bet} Chips.**",
    "rps_tie":           "🤝 **It's a tie!** Your bet was returned.",
    # Daily
    "daily_claim":       "✅ **Daily claimed!** You received **{reward} Stardust**. (Streak: {streak} 🔥)",
    "daily_cooldown":    "⏰ You already claimed your daily! Come back in **{hours}h {mins}m**.",
    "daily_streak_lost": "📅 Your streak was reset. You received **{reward} Stardust**. (New streak: 1 🔥)",
    # Rob
    "rob_success":       "🦝 You snuck **{amount} Stardust** from {victim}!",
    "rob_caught":        "🚔 You were caught robbing {victim} and fined **{fine} Stardust**!",
    "rob_poor":          "💸 {victim} doesn't have enough Stardust to rob.",
    # Rep
    "rep_given":         "❤️ You gave a reputation point to **{user}**! They now have **{total}** rep.",
    "rep_cooldown":      "❤️ You already gave rep today. Come back in **{hours}h {mins}m**.",
    "rep_self":          "❌ You can't give reputation to yourself.",
}

_DEFAULT_PAYOUT_OVERRIDES = {
    # Slots
    "slots_jackpot":          10,
    "slots_star_multiplier":  5,
    "slots_fruit_multiplier": 3,
    "slots_cherry_multiplier": 2,
    # Other games
    "hilo_step": 0.2,
    "coinflip_multiplier": 2.0,
    "blackjack_win_multiplier": 2.0,
    "blackjack_natural_multiplier": 2.5,
    "roulette_color_multiplier": 1.9,
    "roulette_number_multiplier": 35.0,
    "warp_multiplier_step": 1.5,
    # Dice
    "dice_win_multiplier": 5.0,
    # Crash
    "crash_house_edge": 0.04,
    # RPS
    "rps_win_multiplier": 1.9,
    # Daily
    "daily_base_min": 20, "daily_base_max": 50,
    "daily_streak_bonus": 5,
    "daily_streak_max": 30,
    "daily_cooldown_hours": 22,
    # Rob
    "rob_success_chance": 0.40,
    "rob_steal_min_pct": 0.10,
    "rob_steal_max_pct": 0.30,
    "rob_fine_pct": 0.15,
    "rob_min_victim_balance": 50,
    # Event reward ranges
    "drop_1_min": 10, "drop_1_max": 12,
    "drop_2_min": 8,  "drop_2_max": 10,
    "drop_3_min": 6,  "drop_3_max": 8,
    "drop_4_min": 4,  "drop_4_max": 6,
    "drop_5_min": 1,  "drop_5_max": 4,
    "fast_type_min": 10,     "fast_type_max": 20,
    "math_min": 20,          "math_max": 40,
    "trivia_min": 50,        "trivia_max": 100,
    "word_scramble_min": 15, "word_scramble_max": 30,
}

_DEFAULT_BIAS_SETTINGS = {
    "enabled":           True,
    "user_id":           "838827787174543380",
    # Per-game boss advantage
    "cf_win_chance":     0.95,   # coinflip win probability (vs 0.40 normal)
    "slots_jackpot_t":   0.05,   # slots jackpot threshold (vs 0.02 normal)
    "slots_win_t":       0.70,   # slots total win threshold (vs 0.22 normal)
    "bj_dealer_stop":    0.50,   # blackjack: dealer stops early at 15+ with this chance
    "hilo_survival":     0.95,   # hi-lo: boss survival chance per card
    "warp_survival":     0.95,   # warp: boss survival chance per jump
    "rt_rig_chance":     0.40,   # roulette: near-target rig chance
    "dice_exact":        0.60,   # dice: exact pick rig chance
    "crash_min":         3.0,    # crash: minimum crash point for boss
    "crash_max":         20.0,   # crash: maximum crash point for boss
    "rps_win_chance":    0.90,   # rps: chance bot picks what boss beats
    # House edge (applies to ALL non-boss users)
    "bj_house_edge":     0.20,   # blackjack: chance dealer snipes a winning card
    "hilo_house_edge":   0.20,   # hi-lo: chance bad card is forced
}


async def get_server_settings(guild_id: int) -> dict:
    """Returns merged settings dict with defaults for any missing keys."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT command_toggles, game_toggles, event_toggles, payout_overrides, chat_toggles, prefix, text_overrides, bot_disabled, welcome_config, bias_settings, leveling_config FROM server_settings WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row is None:
        return {
            "command_toggles": dict(_DEFAULT_COMMAND_TOGGLES),
            "game_toggles": dict(_DEFAULT_GAME_TOGGLES),
            "event_toggles": dict(_DEFAULT_EVENT_TOGGLES),
            "payout_overrides": dict(_DEFAULT_PAYOUT_OVERRIDES),
            "chat_toggles": dict(_DEFAULT_CHAT_TOGGLES),
            "prefix": "!",
            "text_overrides": dict(_DEFAULT_TEXT_OVERRIDES),
            "bot_disabled": False,
            "welcome_config": dict(_DEFAULT_WELCOME_CONFIG),
            "bias_settings": dict(_DEFAULT_BIAS_SETTINGS),
            "leveling_config": dict(_DEFAULT_LEVELING_CONFIG),
        }
    return {
        "command_toggles":  {**_DEFAULT_COMMAND_TOGGLES,  **json.loads(row[0] or "{}")},
        "game_toggles":     {**_DEFAULT_GAME_TOGGLES,     **json.loads(row[1] or "{}")},
        "event_toggles":    {**_DEFAULT_EVENT_TOGGLES,    **json.loads(row[2] or "{}")},
        "payout_overrides": {**_DEFAULT_PAYOUT_OVERRIDES, **json.loads(row[3] or "{}")},
        "chat_toggles":     {**_DEFAULT_CHAT_TOGGLES,     **json.loads(row[4] or "{}")},
        "prefix": row[5] or "!",
        "text_overrides":   {**_DEFAULT_TEXT_OVERRIDES,   **json.loads(row[6] or "{}")},
        "bot_disabled": bool(row[7]) if row[7] is not None else False,
        "welcome_config":   {**_DEFAULT_WELCOME_CONFIG,   **json.loads(row[8] or "{}")},
        "bias_settings":    {**_DEFAULT_BIAS_SETTINGS,    **json.loads(row[9] or "{}")},
        "leveling_config":  {**_DEFAULT_LEVELING_CONFIG,  **json.loads(row[10] or "{}")},
    }


async def update_server_settings(
    guild_id: int,
    command_toggles: dict = None,
    game_toggles: dict = None,
    event_toggles: dict = None,
    payout_overrides: dict = None,
    chat_toggles: dict = None,
    prefix: str = None,
    text_overrides: dict = None,
    welcome_config: dict = None,
    bias_settings: dict = None,
    leveling_config: dict = None,
) -> None:
    """Upsert server settings, merging provided fields over existing values."""
    current = await get_server_settings(guild_id)
    new_ct  = json.dumps({**current["command_toggles"],  **(command_toggles  or {})})
    new_gt  = json.dumps({**current["game_toggles"],     **(game_toggles     or {})})
    new_et  = json.dumps({**current["event_toggles"],    **(event_toggles    or {})})
    new_po  = json.dumps({**current["payout_overrides"], **(payout_overrides or {})})
    new_cht = json.dumps({**current["chat_toggles"],     **(chat_toggles     or {})})
    new_pfx = prefix if prefix is not None else current["prefix"]
    new_to  = json.dumps({**current["text_overrides"],   **(text_overrides   or {})})
    new_wc  = json.dumps({**current["welcome_config"],   **(welcome_config   or {})})
    new_bs  = json.dumps({**current["bias_settings"],    **(bias_settings    or {})})
    # leveling_config is always fully replaced (milestones array must not be merged)
    new_lc  = json.dumps(leveling_config if leveling_config is not None else current["leveling_config"])
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO server_settings
                (guild_id, command_toggles, game_toggles, event_toggles, payout_overrides, chat_toggles, prefix, text_overrides, welcome_config, bias_settings, leveling_config)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                command_toggles  = excluded.command_toggles,
                game_toggles     = excluded.game_toggles,
                event_toggles    = excluded.event_toggles,
                payout_overrides = excluded.payout_overrides,
                chat_toggles     = excluded.chat_toggles,
                prefix           = excluded.prefix,
                text_overrides   = excluded.text_overrides,
                welcome_config   = excluded.welcome_config,
                bias_settings    = excluded.bias_settings,
                leveling_config  = excluded.leveling_config
            """,
            (guild_id, new_ct, new_gt, new_et, new_po, new_cht, new_pfx, new_to, new_wc, new_bs, new_lc)
        )
        await db.commit()


# --- ADMIN ---

async def set_guild_disabled(guild_id: int, disabled: bool) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """INSERT INTO server_settings (guild_id, bot_disabled)
               VALUES (?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET bot_disabled = excluded.bot_disabled""",
            (guild_id, 1 if disabled else 0),
        )
        await db.commit()


async def get_guild_users(guild_id: int) -> list:
    """Returns list of (user_id, balance, chips) for all users with any balance in a guild."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT user_id, balance, chips FROM user_balances WHERE guild_id = ? ORDER BY balance DESC",
            (guild_id,),
        ) as cursor:
            return await cursor.fetchall()


async def set_user_balance_admin(user_id: int, guild_id: int, balance: int, chips: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """INSERT INTO user_balances (user_id, guild_id, balance, chips)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, guild_id) DO UPDATE SET
                   balance = excluded.balance,
                   chips   = excluded.chips""",
            (user_id, guild_id, balance, chips),
        )
        await db.commit()


# --- CUSTOM RESPONSES ---
async def get_custom_responses(guild_id: int) -> list:
    """Returns list of (id, trigger_words, response_text) for the guild."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, trigger_words, response_text FROM custom_responses WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            return await cursor.fetchall()


async def add_custom_response(guild_id: int, trigger_words: str, response_text: str) -> int:
    """Adds a custom response. Returns the new row ID."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO custom_responses (guild_id, trigger_words, response_text) VALUES (?, ?, ?)",
            (guild_id, trigger_words, response_text)
        )
        await db.commit()
        return cursor.lastrowid


async def delete_custom_response(response_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM custom_responses WHERE id = ?", (response_id,))
        await db.commit()


# --- RESPONSE GROUPS ---
async def get_response_groups(guild_id: int) -> list:
    """Returns list of (id, name, triggers_json, responses_json, enabled) for the guild."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, name, triggers, responses, enabled FROM response_groups WHERE guild_id = ? ORDER BY id",
            (guild_id,)
        ) as cursor:
            return await cursor.fetchall()


async def add_response_group(guild_id: int, name: str, triggers: list, responses: list) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO response_groups (guild_id, name, triggers, responses, enabled) VALUES (?, ?, ?, ?, 1)",
            (guild_id, name, json.dumps(triggers), json.dumps(responses))
        )
        await db.commit()
        return cursor.lastrowid


async def set_response_group_enabled(group_id: int, enabled: bool) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE response_groups SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, group_id)
        )
        await db.commit()


async def delete_response_group(group_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM response_groups WHERE id = ?", (group_id,))
        await db.commit()


# --- BLOCKED USERS ---

async def block_user(user_id: int, reason: str, blocked_by: int) -> None:
    import time
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO blocked_users (user_id, reason, blocked_at, blocked_by) VALUES (?, ?, ?, ?)",
            (user_id, reason, int(time.time()), blocked_by),
        )
        await db.commit()


async def unblock_user(user_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM blocked_users WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_blocked_users() -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT user_id, reason, blocked_at, blocked_by FROM blocked_users ORDER BY blocked_at DESC"
        ) as cursor:
            return await cursor.fetchall()


async def is_user_blocked(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT 1 FROM blocked_users WHERE user_id = ?", (user_id,)
        ) as cursor:
            return await cursor.fetchone() is not None


# --- AUDIT LOG ---

async def log_admin_action(
    admin_id: int,
    action: str,
    guild_id: int = None,
    target_id: int = None,
    details: str = "",
) -> None:
    import time
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO admin_audit_log (admin_id, action, guild_id, target_id, details, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (admin_id, action, guild_id, target_id, details, int(time.time())),
        )
        await db.commit()


async def get_audit_log(limit: int = 100) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, admin_id, action, guild_id, target_id, details, timestamp FROM admin_audit_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ) as cursor:
            return await cursor.fetchall()


# --- ECONOMY ADMIN ---

async def reset_guild_economy(guild_id: int) -> int:
    """Delete all user_balances rows for a guild. Returns count removed."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM user_balances WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            count = (await cursor.fetchone())[0]
        await db.execute("DELETE FROM user_balances WHERE guild_id = ?", (guild_id,))
        await db.commit()
    return count


async def bulk_reward_guild(guild_id: int, balance_delta: int = 0, chips_delta: int = 0) -> int:
    """Add balance/chips to all users in a guild. Returns number of users affected."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM user_balances WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            count = (await cursor.fetchone())[0]
        if balance_delta:
            await db.execute(
                "UPDATE user_balances SET balance = MAX(0, balance + ?) WHERE guild_id = ?",
                (balance_delta, guild_id),
            )
        if chips_delta:
            await db.execute(
                "UPDATE user_balances SET chips = MAX(0, chips + ?) WHERE guild_id = ?",
                (chips_delta, guild_id),
            )
        await db.commit()
    return count


# --- SOCIAL (daily / work / rob / rep) ---

async def get_user_social(user_id: int, guild_id: int) -> dict:
    """Returns daily_streak, last_daily, rep_count, last_rep_given."""
    async with aiosqlite.connect(DB_NAME) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.commit()
        async with db.execute(
            "SELECT daily_streak, last_daily, rep_count, last_rep_given FROM user_balances WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        ) as cursor:
            row = await cursor.fetchone()
    if row:
        return {"daily_streak": row[0], "last_daily": row[1],
                "rep_count": row[2], "last_rep_given": row[3]}
    return {"daily_streak": 0, "last_daily": 0.0,
            "rep_count": 0, "last_rep_given": 0.0}


async def update_daily(user_id: int, guild_id: int, streak: int, last_daily: float) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.execute(
            "UPDATE user_balances SET daily_streak = ?, last_daily = ? WHERE user_id = ? AND guild_id = ?",
            (streak, last_daily, user_id, guild_id),
        )
        await db.commit()


async def add_rep(receiver_id: int, guild_id: int, amount: int = 1) -> int:
    """Increment rep_count for receiver. Returns new total."""
    async with aiosqlite.connect(DB_NAME) as db:
        await _ensure_user(db, receiver_id, guild_id)
        await db.execute(
            "UPDATE user_balances SET rep_count = rep_count + ? WHERE user_id = ? AND guild_id = ?",
            (amount, receiver_id, guild_id),
        )
        await db.commit()
        async with db.execute(
            "SELECT rep_count FROM user_balances WHERE user_id = ? AND guild_id = ?",
            (receiver_id, guild_id),
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else 0


async def update_rep_cooldown(giver_id: int, guild_id: int, last_rep_given: float) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await _ensure_user(db, giver_id, guild_id)
        await db.execute(
            "UPDATE user_balances SET last_rep_given = ? WHERE user_id = ? AND guild_id = ?",
            (last_rep_given, giver_id, guild_id),
        )
        await db.commit()


# --- ACHIEVEMENTS ---

async def unlock_achievement(user_id: int, guild_id: int, key: str) -> bool:
    """Unlock an achievement. Returns True if it was newly unlocked."""
    import time
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT 1 FROM achievements WHERE user_id = ? AND guild_id = ? AND key = ?",
            (user_id, guild_id, key),
        ) as cursor:
            if await cursor.fetchone():
                return False
        await db.execute(
            "INSERT OR IGNORE INTO achievements (user_id, guild_id, key, unlocked_at) VALUES (?, ?, ?, ?)",
            (user_id, guild_id, key, int(time.time())),
        )
        await db.commit()
    return True


async def get_achievements(user_id: int, guild_id: int) -> list:
    """Returns list of unlocked achievement keys."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT key FROM achievements WHERE user_id = ? AND guild_id = ? ORDER BY unlocked_at",
            (user_id, guild_id),
        ) as cursor:
            rows = await cursor.fetchall()
    return [row[0] for row in rows]


# --- GIVEAWAYS ---

async def create_giveaway(
    guild_id: int, channel_id: int, prize_desc: str, end_time: float,
    winner_count: int, entry_cost: int, entry_currency: str, creator_id: int,
) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """INSERT INTO giveaways
               (guild_id, channel_id, prize_desc, end_time, winner_count, entry_cost, entry_currency, creator_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (guild_id, channel_id, prize_desc, end_time, winner_count, entry_cost, entry_currency, creator_id),
        )
        await db.commit()
        return cursor.lastrowid


async def set_giveaway_message(giveaway_id: int, message_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE giveaways SET message_id = ? WHERE id = ?", (message_id, giveaway_id))
        await db.commit()


async def enter_giveaway(giveaway_id: int, user_id: int) -> bool:
    """Add entry. Returns True if newly entered, False if already in."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT 1 FROM giveaway_entries WHERE giveaway_id = ? AND user_id = ?",
            (giveaway_id, user_id),
        ) as cursor:
            if await cursor.fetchone():
                return False
        await db.execute(
            "INSERT INTO giveaway_entries (giveaway_id, user_id) VALUES (?, ?)",
            (giveaway_id, user_id),
        )
        await db.commit()
    return True


async def get_giveaway_entries(giveaway_id: int) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT user_id FROM giveaway_entries WHERE giveaway_id = ?", (giveaway_id,)
        ) as cursor:
            rows = await cursor.fetchall()
    return [row[0] for row in rows]


async def end_giveaway(giveaway_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE giveaways SET ended = 1 WHERE id = ?", (giveaway_id,))
        await db.commit()


async def get_active_giveaways(guild_id: int = None) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        if guild_id:
            async with db.execute(
                "SELECT id, guild_id, channel_id, message_id, prize_desc, end_time, winner_count, entry_cost, entry_currency, creator_id FROM giveaways WHERE ended = 0 AND guild_id = ?",
                (guild_id,),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT id, guild_id, channel_id, message_id, prize_desc, end_time, winner_count, entry_cost, entry_currency, creator_id FROM giveaways WHERE ended = 0"
            ) as cursor:
                rows = await cursor.fetchall()
    keys = ["id", "guild_id", "channel_id", "message_id", "prize_desc", "end_time", "winner_count", "entry_cost", "entry_currency", "creator_id"]
    return [dict(zip(keys, row)) for row in rows]


async def get_active_giveaways_with_counts(guild_id: int = None) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        if guild_id:
            async with db.execute(
                """SELECT g.id, g.guild_id, g.channel_id, g.message_id, g.prize_desc, g.end_time,
                          g.winner_count, g.entry_cost, g.entry_currency, g.creator_id,
                          COUNT(e.user_id) AS entry_count
                   FROM giveaways g
                   LEFT JOIN giveaway_entries e ON e.giveaway_id = g.id
                   WHERE g.ended = 0 AND g.guild_id = ?
                   GROUP BY g.id""",
                (guild_id,),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                """SELECT g.id, g.guild_id, g.channel_id, g.message_id, g.prize_desc, g.end_time,
                          g.winner_count, g.entry_cost, g.entry_currency, g.creator_id,
                          COUNT(e.user_id) AS entry_count
                   FROM giveaways g
                   LEFT JOIN giveaway_entries e ON e.giveaway_id = g.id
                   WHERE g.ended = 0
                   GROUP BY g.id"""
            ) as cursor:
                rows = await cursor.fetchall()
    keys = ["id", "guild_id", "channel_id", "message_id", "prize_desc", "end_time", "winner_count", "entry_cost", "entry_currency", "creator_id", "entry_count"]
    return [dict(zip(keys, row)) for row in rows]


# --- POLLS ---

async def create_poll(guild_id: int, channel_id: int, message_id: int, question: str, options: list) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO polls (guild_id, channel_id, message_id, question, options) VALUES (?, ?, ?, ?, ?)",
            (guild_id, channel_id, message_id, question, json.dumps(options)),
        )
        await db.commit()
        return cursor.lastrowid


async def end_poll(poll_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE polls SET ended = 1 WHERE id = ?", (poll_id,))
        await db.commit()


async def get_active_polls() -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, guild_id, channel_id, message_id, question, options FROM polls WHERE ended = 0"
        ) as cursor:
            rows = await cursor.fetchall()
    return [{"id": r[0], "guild_id": r[1], "channel_id": r[2], "message_id": r[3],
             "question": r[4], "options": json.loads(r[5])} for r in rows]


async def get_user_all_guilds(user_id: int) -> list:
    """Returns list of (guild_id, balance, chips) for a user across all guilds."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT guild_id, balance, chips FROM user_balances WHERE user_id = ? ORDER BY balance DESC",
            (user_id,),
        ) as cursor:
            return await cursor.fetchall()


# --- LEVELING ---

async def get_user_xp(user_id: int, guild_id: int) -> tuple:
    """Returns (xp, level)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT xp, level FROM user_xp WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        ) as cursor:
            row = await cursor.fetchone()
    return row if row else (0, 0)


async def set_user_xp(user_id: int, guild_id: int, xp: int, level: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """INSERT INTO user_xp (user_id, guild_id, xp, level) VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, guild_id) DO UPDATE SET xp = excluded.xp, level = excluded.level""",
            (user_id, guild_id, xp, level),
        )
        await db.commit()


async def get_xp_leaderboard(guild_id: int, limit: int = 10) -> list:
    """Returns list of (user_id, xp, level)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT user_id, xp, level FROM user_xp WHERE guild_id = ? ORDER BY xp DESC LIMIT ?",
            (guild_id, limit),
        ) as cursor:
            return await cursor.fetchall()


# --- REACTION ROLES ---

async def get_reaction_role_panels(guild_id: int) -> list:
    """Returns list of panel dicts with their entries."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, channel_id, message_id, title, description FROM reaction_role_panels WHERE guild_id = ? ORDER BY id",
            (guild_id,),
        ) as cursor:
            panels = await cursor.fetchall()
        result = []
        for panel_id, channel_id, message_id, title, description in panels:
            async with db.execute(
                "SELECT id, emoji, role_id, label FROM reaction_role_entries WHERE panel_id = ? ORDER BY id",
                (panel_id,),
            ) as cursor:
                entries = await cursor.fetchall()
            result.append({
                "id": panel_id,
                "channel_id": channel_id,
                "message_id": message_id,
                "title": title,
                "description": description,
                "entries": [{"id": e[0], "emoji": e[1], "role_id": e[2], "label": e[3]} for e in entries],
            })
    return result


async def get_reaction_role_panel_by_message(message_id: int) -> dict | None:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, guild_id, channel_id, title, description FROM reaction_role_panels WHERE message_id = ?",
            (message_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        panel_id, guild_id, channel_id, title, description = row
        async with db.execute(
            "SELECT id, emoji, role_id, label FROM reaction_role_entries WHERE panel_id = ? ORDER BY id",
            (panel_id,),
        ) as cursor:
            entries = await cursor.fetchall()
    return {
        "id": panel_id,
        "guild_id": guild_id,
        "channel_id": channel_id,
        "message_id": message_id,
        "title": title,
        "description": description,
        "entries": [{"id": e[0], "emoji": e[1], "role_id": e[2], "label": e[3]} for e in entries],
    }


async def create_reaction_role_panel(guild_id: int, channel_id: int, message_id: int, title: str, description: str) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO reaction_role_panels (guild_id, channel_id, message_id, title, description) VALUES (?, ?, ?, ?, ?)",
            (guild_id, channel_id, message_id, title, description),
        )
        await db.commit()
        return cursor.lastrowid


async def delete_reaction_role_panel(panel_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM reaction_role_entries WHERE panel_id = ?", (panel_id,))
        await db.execute("DELETE FROM reaction_role_panels WHERE id = ?", (panel_id,))
        await db.commit()


async def add_panel_entry(panel_id: int, emoji: str, role_id: int, label: str) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO reaction_role_entries (panel_id, emoji, role_id, label) VALUES (?, ?, ?, ?)",
            (panel_id, emoji, role_id, label),
        )
        await db.commit()
        return cursor.lastrowid


async def remove_panel_entry(entry_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM reaction_role_entries WHERE id = ?", (entry_id,))
        await db.commit()


# ── SUPPORT TICKET SYSTEM ──

async def get_ticket_config(guild_id: int) -> dict:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM ticket_config WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return {
                    "guild_id": guild_id, "enabled": 0, "log_channel_id": 0,
                    "category_id": 0, "naming_format": "ticket-{number}",
                    "next_ticket_number": 1, "dm_transcript": 0, "claim_lock": 0,
                }
            return {
                "guild_id": row[0], "enabled": row[1], "log_channel_id": row[2],
                "category_id": row[3], "naming_format": row[4],
                "next_ticket_number": row[5], "dm_transcript": row[6], "claim_lock": row[7],
            }


async def upsert_ticket_config(guild_id: int, **kwargs) -> None:
    cfg = await get_ticket_config(guild_id)
    cfg.update(kwargs)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """INSERT INTO ticket_config
               (guild_id, enabled, log_channel_id, category_id, naming_format, next_ticket_number, dm_transcript, claim_lock)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET
               enabled=excluded.enabled, log_channel_id=excluded.log_channel_id,
               category_id=excluded.category_id, naming_format=excluded.naming_format,
               next_ticket_number=excluded.next_ticket_number, dm_transcript=excluded.dm_transcript,
               claim_lock=excluded.claim_lock""",
            (guild_id, cfg["enabled"], cfg["log_channel_id"], cfg["category_id"],
             cfg["naming_format"], cfg["next_ticket_number"], cfg["dm_transcript"], cfg["claim_lock"]),
        )
        await db.commit()


async def increment_ticket_number(guild_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        # Ensure row exists
        await db.execute(
            "INSERT OR IGNORE INTO ticket_config (guild_id) VALUES (?)", (guild_id,)
        )
        async with db.execute(
            "SELECT next_ticket_number FROM ticket_config WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            num = row[0]
        await db.execute(
            "UPDATE ticket_config SET next_ticket_number = next_ticket_number + 1 WHERE guild_id = ?",
            (guild_id,),
        )
        await db.commit()
        return num


# ── Ticket Panels ──

async def get_ticket_panels(guild_id: int) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, guild_id, channel_id, message_id, title, description, color, button_label, button_emoji, button_style FROM ticket_panels WHERE guild_id = ?",
            (guild_id,),
        ) as cursor:
            panels = []
            for row in await cursor.fetchall():
                panel = {
                    "id": row[0], "guild_id": row[1], "channel_id": row[2],
                    "message_id": row[3], "title": row[4], "description": row[5],
                    "color": row[6], "button_label": row[7], "button_emoji": row[8],
                    "button_style": row[9],
                }
                async with db.execute(
                    "SELECT id, panel_id, name, emoji, description, opening_message, staff_roles, ticket_limit, form_fields FROM ticket_categories WHERE panel_id = ?",
                    (panel["id"],),
                ) as cat_cur:
                    panel["categories"] = [
                        {
                            "id": c[0], "panel_id": c[1], "name": c[2], "emoji": c[3],
                            "description": c[4], "opening_message": c[5],
                            "staff_roles": json.loads(c[6]), "ticket_limit": c[7],
                            "form_fields": json.loads(c[8]),
                        }
                        for c in await cat_cur.fetchall()
                    ]
                panels.append(panel)
            return panels


async def get_ticket_panel(panel_id: int) -> dict | None:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, guild_id, channel_id, message_id, title, description, color, button_label, button_emoji, button_style FROM ticket_panels WHERE id = ?",
            (panel_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            panel = {
                "id": row[0], "guild_id": row[1], "channel_id": row[2],
                "message_id": row[3], "title": row[4], "description": row[5],
                "color": row[6], "button_label": row[7], "button_emoji": row[8],
                "button_style": row[9],
            }
        async with db.execute(
            "SELECT id, panel_id, name, emoji, description, opening_message, staff_roles, ticket_limit, form_fields FROM ticket_categories WHERE panel_id = ?",
            (panel_id,),
        ) as cat_cur:
            panel["categories"] = [
                {
                    "id": c[0], "panel_id": c[1], "name": c[2], "emoji": c[3],
                    "description": c[4], "opening_message": c[5],
                    "staff_roles": json.loads(c[6]), "ticket_limit": c[7],
                    "form_fields": json.loads(c[8]),
                }
                for c in await cat_cur.fetchall()
            ]
        return panel


async def get_all_ticket_panel_ids() -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM ticket_panels") as cursor:
            return [row[0] for row in await cursor.fetchall()]


async def create_ticket_panel(guild_id: int, channel_id: int, message_id: int,
                              title: str, description: str, color: int,
                              button_label: str, button_emoji: str, button_style: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """INSERT INTO ticket_panels
               (guild_id, channel_id, message_id, title, description, color, button_label, button_emoji, button_style)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (guild_id, channel_id, message_id, title, description, color, button_label, button_emoji, button_style),
        )
        await db.commit()
        return cursor.lastrowid


async def update_ticket_panel(panel_id: int, **kwargs) -> None:
    allowed = {"title", "description", "color", "button_label", "button_emoji", "button_style", "channel_id", "message_id"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(f"UPDATE ticket_panels SET {set_clause} WHERE id = ?",
                         (*updates.values(), panel_id))
        await db.commit()


async def delete_ticket_panel(panel_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM ticket_categories WHERE panel_id = ?", (panel_id,))
        await db.execute("DELETE FROM ticket_panels WHERE id = ?", (panel_id,))
        await db.commit()


# ── Ticket Categories ──

async def get_ticket_categories(panel_id: int) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, panel_id, name, emoji, description, opening_message, staff_roles, ticket_limit, form_fields FROM ticket_categories WHERE panel_id = ?",
            (panel_id,),
        ) as cursor:
            return [
                {
                    "id": c[0], "panel_id": c[1], "name": c[2], "emoji": c[3],
                    "description": c[4], "opening_message": c[5],
                    "staff_roles": json.loads(c[6]), "ticket_limit": c[7],
                    "form_fields": json.loads(c[8]),
                }
                for c in await cursor.fetchall()
            ]


async def create_ticket_category(panel_id: int, name: str, emoji: str = "📩",
                                 description: str = "", opening_message: str = "",
                                 staff_roles: list = None, ticket_limit: int = 1,
                                 form_fields: list = None) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """INSERT INTO ticket_categories
               (panel_id, name, emoji, description, opening_message, staff_roles, ticket_limit, form_fields)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (panel_id, name, emoji, description, opening_message,
             json.dumps(staff_roles or []), ticket_limit, json.dumps(form_fields or [])),
        )
        await db.commit()
        return cursor.lastrowid


async def update_ticket_category(category_id: int, **kwargs) -> None:
    allowed = {"name", "emoji", "description", "opening_message", "staff_roles", "ticket_limit", "form_fields"}
    updates = {}
    for k, v in kwargs.items():
        if k not in allowed:
            continue
        if k in ("staff_roles", "form_fields"):
            updates[k] = json.dumps(v)
        else:
            updates[k] = v
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(f"UPDATE ticket_categories SET {set_clause} WHERE id = ?",
                         (*updates.values(), category_id))
        await db.commit()


async def delete_ticket_category(category_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM ticket_categories WHERE id = ?", (category_id,))
        await db.commit()


# ── Support Tickets ──

async def create_support_ticket(guild_id: int, channel_id: int, user_id: int,
                                category_id: int, panel_id: int, ticket_number: int) -> int:
    import time
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """INSERT INTO support_tickets
               (guild_id, channel_id, user_id, category_id, panel_id, ticket_number, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (guild_id, channel_id, user_id, category_id, panel_id, ticket_number, time.time()),
        )
        await db.commit()
        return cursor.lastrowid


async def get_support_ticket_by_channel(channel_id: int) -> dict | None:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, guild_id, channel_id, user_id, category_id, panel_id, ticket_number, claimed_by, status, created_at, closed_at, closed_by, transcript_url FROM support_tickets WHERE channel_id = ?",
            (channel_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0], "guild_id": row[1], "channel_id": row[2],
                "user_id": row[3], "category_id": row[4], "panel_id": row[5],
                "ticket_number": row[6], "claimed_by": row[7], "status": row[8],
                "created_at": row[9], "closed_at": row[10], "closed_by": row[11],
                "transcript_url": row[12],
            }


async def claim_support_ticket(channel_id: int, claimed_by: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE support_tickets SET claimed_by = ?, status = 'claimed' WHERE channel_id = ?",
            (claimed_by, channel_id),
        )
        await db.commit()


async def close_support_ticket(channel_id: int, closed_by: int, transcript_url: str = "") -> None:
    import time
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE support_tickets SET status = 'closed', closed_at = ?, closed_by = ?, transcript_url = ? WHERE channel_id = ?",
            (time.time(), closed_by, transcript_url, channel_id),
        )
        await db.commit()


async def get_open_ticket_count(user_id: int, category_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM support_tickets WHERE user_id = ? AND category_id = ? AND status != 'closed'",
            (user_id, category_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0]


async def get_guild_tickets(guild_id: int, status: str = None) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        if status:
            sql = "SELECT id, channel_id, user_id, category_id, ticket_number, claimed_by, status, created_at FROM support_tickets WHERE guild_id = ? AND status = ? ORDER BY created_at DESC"
            params = (guild_id, status)
        else:
            sql = "SELECT id, channel_id, user_id, category_id, ticket_number, claimed_by, status, created_at FROM support_tickets WHERE guild_id = ? ORDER BY created_at DESC"
            params = (guild_id,)
        async with db.execute(sql, params) as cursor:
            return [
                {"id": r[0], "channel_id": r[1], "user_id": r[2], "category_id": r[3],
                 "ticket_number": r[4], "claimed_by": r[5], "status": r[6], "created_at": r[7]}
                for r in await cursor.fetchall()
            ]