# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flicker-bot is a Discord bot built with discord.py. It provides a dual-currency economy system (Stardust and Chips), gambling games, random in-chat events, a shop with ticket support, server verification, and custom voice channels. The bot's persona is a cute robot named "Flicker."

## Running the Bot

```bash
pip install -r requirements.txt
# Create .env with: DISCORD_TOKEN=your_token_here
python main.py
```

There is no test suite or linter configured. Testing is done manually on a live Discord server. The `!simulate` command in the events cog can trigger a specific or random event for testing (e.g. `!simulate word_scramble`).

## Currency System

Flicker-bot uses two distinct currencies with a deliberate one-way flow:

**Stardust** is the primary currency. It is earned exclusively by participating in random in-chat events (drop, trivia, math, fast_type, word_scramble). It can be transferred between users via `!pay` and spent in the shop. It cannot be earned through gambling.

**Chips** are the gambling currency. They are purchased from Stardust at a fixed rate of **1 Stardust = 50 Chips** using the `!buychips` command. The conversion is one-way — Chips cannot be converted back into Stardust. All gambling commands (`!coinflip`, `!slots`, `!blackjack`, `!hilo`, `!roulette`, `!warp`) exclusively use Chips as stakes. Chips can also be spent in the shop if the admin sets a chips price on a listing.

This design separates the economy (Stardust earned through participation) from gambling risk (Chips bought voluntarily), preventing gambling losses from directly depleting event-earned wealth.

## Architecture

### Entry Point & Startup

`main.py` creates `FlickerBot(commands.Bot)` with prefix `!`. On startup, `setup_hook()` calls `init_db()` then auto-loads every `.py` file in `./cogs/` as a discord.py extension.

### Database Layer (`database.py`)

All SQL lives in `database.py`. Cogs never write raw SQL — they call async functions from this module. The DB file is `flicker.db` locally or `/data/flicker.db` on Railway (detected via `RAILWAY_ENVIRONMENT` env var).

Tables: `users` (economy balances, including a `chips` column added via safe migration), `allowed_channels` (where events can fire), `active_tickets` (open shop tickets), `shop_items` (listings, including a `chips_price` column added via safe migration), `verification_config`, `vc_config`.

Key functions:
- `get_balance(user_id)` / `update_balance(user_id, amount)` — read/write Stardust; used by events and economy cogs
- `get_chips(user_id)` / `update_chips(user_id, amount)` — read/write Chips; used by gamble, economy, and shop cogs
- `get_top_users(limit)` — returns `(top_stardust, top_chips)` as two lists of `(user_id, value)` for the leaderboard
- `lock_listing` / `unlock_listing` — prevent concurrent shop purchases via active ticket tracking
- `create_shop_item(message_id, stock, role_id, stardust, chips, usd)` — registers a new listing with all three prices
- `get_shop_item(message_id)` — returns `(stock, role_id, stardust_price, chips_price, usd_price)`

### Cog Responsibilities

| Cog | Responsibility |
|-----|---------------|
| `economy.py` | `!balance`/`!bal`/`!b`/`!wallet` (shows both Stardust and Chips); `!add` (admin, awards Stardust); `!buychips`/`!bc` (converts Stardust to Chips at 1:50); `!top`/`!leaderboard`/`!lb` (dual leaderboard); `!pay`/`!transfer`/`!give` (Stardust transfer with confirmation View) |
| `events.py` | `on_message` hook; 5–10% chance to fire a random event (drop, trivia, math, fast_type, word_scramble) in allowed channels; 180s cooldown; all events reward Stardust |
| `gamble.py` | All games use Chips as stakes. `!coinflip`/`!cf` and `!slots`/`!s` (existing); `!blackjack`/`!bj` (Hit/Stand/Double Down with interactive View); `!hilo`/`!hl` (Higher or Lower with escalating multipliers); `!roulette`/`!rt` (red/black/odd/even/straight-up, 1.9× or 35×); `!warp`/`!rr`/`!russianroulette` (Hyperwarp Drive — pull trigger for exponential multipliers, 53.3% survival rate). Boss user ID `838827787174543380` gets rigged odds across all games. |
| `shop.py` | Admin posts listings via `!shop #channel` (opens a Discord Modal for title, description, stock, prices, and optional role ID); listings have three optional buy buttons: Stardust, Chips, USD; role-based items auto-deliver on Stardust/Chips purchase; manual items open a private ticket channel under an "Orders" category |
| `chat.py` | Responds conversationally when "flicker" is mentioned; keyword buckets drive probabilistic reply selection |
| `verify.py` | Verification embed with a trap-door quiz for users who admit they haven't read the rules |
| `voice.py` | Auto-creates private VCs when users join the generator channel; persistent control panel |
| `pet.py` | `!pet` — hourly command that awards 1–10 Stardust |
| `admin.py` | `!trackC` / `!RmC` / `!ListC` to manage which channels events can fire in |

### Discord.py UI Pattern

Interactive components (buttons, modals, selects) are implemented as `discord.ui.View` / `discord.ui.Modal` subclasses defined within the cog file that owns them.

The shop uses a two-step modal flow: `!shop #channel` sends a temporary `_ShopTriggerView` with a single button; clicking it opens a `ShopPostModal` (a `discord.ui.Modal`) where the admin fills in all listing details in one form. On submit the modal posts the listing embed and attaches the persistent `ShopView` (three buy buttons). This avoids the old multi-command `!shopPost` / `!shopStock` workflow.

The `ShopView` and `TicketCloseView` survive bot restarts because they are registered as persistent views in `on_ready()` via `bot.add_view()`. Gambling views (`BlackjackView`, `HiloView`, `WarpView`) are ephemeral — they time out after 30 seconds and auto-resolve (refund or pay out earned multiplier) if the player does not respond.

### Adding a New Cog

1. Create `cogs/newcog.py` with a class extending `commands.Cog` and an async `setup(bot)` function at the bottom.
2. It will be auto-loaded on next bot startup — no registration needed in `main.py`.
3. Import database functions at the top of the cog file as needed.
