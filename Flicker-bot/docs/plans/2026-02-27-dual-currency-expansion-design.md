# Design: Dual Currency Expansion

**Date:** 2026-02-27
**Scope:** Chips currency, shop refactor, new gambling games, new events, leaderboard

---

## 1. Dual Currency System

### Exchange Rate
- **1 Stardust → 50 Chips** (one-way only — Chips cannot be converted back)
- Chips are the dedicated gambling currency; Stardust remains the primary economy currency

### Database Changes (`database.py`)
- Add `chips INTEGER DEFAULT 0` to `users` table via safe `ALTER TABLE` in `init_db()`
- Add `chips_price INTEGER DEFAULT 0` to `shop_items` table via safe `ALTER TABLE`
- New functions: `get_chips(user_id)`, `update_chips(user_id, amount)`, `get_top_users(limit)` (returns list of `(user_id, balance, chips)` sorted by balance desc, plus a chips-sorted variant)

### Economy Cog (`economy.py`)
- `!buychips <amount>` — spends `amount` Stardust, grants `amount × 50` Chips. Validates user has enough Stardust.
- `!balance` (aliases: `!bal`, `!wallet`, `!b`) — updated embed shows both Stardust and Chips
- `!top` — single embed with two fields: **Top Stardust** (sorted by stardust desc) and **Top Chips** (sorted by chips desc), each showing top 10

---

## 2. Shop Refactor (`shop.py`)

### Command Interface
- **Remove** `!shopPost` and `!shopStock`
- **Add** single `!shop #channel` command (admin only)
  - Admin optionally attaches an image to the `!shop` message
  - A `discord.ui.Modal` opens with fields: Title, Description, Stock (`number` or `inf`), Stardust Price, Chips Price, USD Price, Role ID (optional, leave blank for manual ticket)

### Code Changes
- Add `"Buy with Chips"` button to `ShopView` (`custom_id="shop:btn_chips"`) — blurple, chip emoji
- Refactor `btn_stardust` and `btn_usd` duplicate logic into shared `_handle_purchase(interaction, currency, price)` helper
- `btn_chips` uses same `_handle_purchase` flow, deducting from chips balance
- `shop_items` DB record now stores `chips_price` alongside existing fields

### Button Visibility Logic
- Buttons with price `<= 0` are removed from the view before posting (existing pattern, extended to chips button)

---

## 3. Gambling Refactor (`gamble.py`)

### Currency Migration
- All gambling commands use **Chips** only
- `get_bet_amount` updated to call `get_chips` / `update_chips` instead of `get_balance` / `update_balance`
- Error messages updated to reference "Chips" instead of "Stardust"

### Existing Games
- `!coinflip` / `!cf` — unchanged logic, now uses Chips
- `!slots` / `!s` — unchanged logic, now uses Chips

### New Games

#### `!bj` — Blackjack
- Standard 52-card deck (suits cosmetically themed: ✨🌙⭐💫)
- Dealer hits to soft 17
- Interactive: Hit / Stand / Double Down buttons (30s timeout per action)
- Payouts: 2× win, 2.5× blackjack (natural 21), push on tie, 0 on bust/loss
- Boss rigged odds: dealer "busts" more often

#### `!hilo` — Higher or Lower
- Draw one card face-up; player guesses if next card is Higher or Lower
- Chain correct guesses for a multiplier (1 correct = 1.5×, 2 = 2×, 3 = 3×, max 8×)
- Player can "Cash Out" at any time using a button
- Wrong guess = lose bet

#### `!dice` — Cosmic Dice Duel
- Player and Flicker each roll 2d6 (animated)
- Higher total wins 2× bet; tie = push (refund); loss = 0
- Fast game, 15s cooldown
- Boss: Flicker rolls with disadvantage (re-rolls highest die, takes lower)

#### `!roulette` — Starwheel Roulette
- Bet types: Red/Black (1.9×), Odd/Even (1.9×), Single number 0–36 (35×)
- Animated spinning wheel embed
- Command: `!roulette <amount> <bet>` where bet is `red`, `black`, `odd`, `even`, or a number
- Boss: number bets land one slot "toward" the boss's pick

### Cooldowns
- `!bj`, `!hilo`, `!roulette`: 15s per user
- `!dice`: 15s per user
- Boss bypasses all cooldowns (existing behaviour preserved)

---

## 4. New Events (`events.py`)

Two new passive event types, each ~1% chance per eligible message:

### Word Scramble
- Flicker scrambles a space/cosmic-themed word (pool of ~20 words)
- First user to type the correct unscrambled word wins 15–30 Stardust
- Timeout: 20s

### Emoji Sequence
- Flicker displays a sequence of 4 space-themed emojis (e.g. `🌙 ⭐ 🪐 💫`)
- First user to type the sequence exactly wins 10–25 Stardust
- Timeout: 15s

Both events added as `elif` branches in `on_message`, keeping total event probability similar.
`!simulate` updated to accept `word_scramble` and `emoji_sequence` as valid game types.

---

## 5. Leaderboard (`!top`)

Single embed, two inline fields:

```
┌─────────────────────────────────────┐
│  🏆 Flicker Leaderboard             │
├──────────────────┬──────────────────┤
│ ✨ Top Stardust  │ 🎰 Top Chips     │
│ 1. User — 1200   │ 1. User — 85000  │
│ 2. User — 980    │ 2. User — 62000  │
│ ...              │ ...              │
└──────────────────┴──────────────────┘
```

- Fetches top 10 for each currency in a single DB query
- Mentions users by display name (fetched via `bot.get_user` or falls back to user ID)
- Purple embed colour, consistent with bot theme
