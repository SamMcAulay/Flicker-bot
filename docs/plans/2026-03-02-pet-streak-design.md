# Pet Streak System — Design Doc
**Date:** 2026-03-02

## Overview
Add a streak mechanic to the `!pet` command that rewards users who pet Flicker consistently every hour with an additive Stardust bonus, milestone bursts, and a time-decay system for missed windows.

## Streak Logic
- **On time:** `elapsed` between 3600s and 4500s (1h–1h15m) → `streak += 1`, capped at 30
- **Late:** `elapsed > 4500s` → `decay = floor((elapsed - 4500) / 3600)`, `streak = max(0, streak - decay)`. No +1 awarded.
- **First pet:** streak initialises to 1.

## Reward
`base (1–10 Stardust) + streak bonus (= streak level, up to +30 Stardust)`

## Milestones
Trigger once per streak run when streak reaches the threshold exactly:

| Streak | Burst | Message |
|--------|-------|---------|
| 7  | +25 Stardust | "One week of hourly visits!" |
| 14 | +50 Stardust | "Two weeks — Flicker has imprinted on you." |
| 30 | +100 Stardust | "Monthly devotee. Flicker's eternal favourite." |

Milestones re-fire if the streak decays below the threshold and rebuilds back up.

## Data
Two new columns on `users` table via safe ALTER TABLE migration:
- `pet_streak INTEGER DEFAULT 0`
- `last_pet_time REAL DEFAULT 0` (unix timestamp)

Two new DB functions:
- `get_pet_data(user_id) → (streak, last_pet_time)`
- `update_pet_data(user_id, streak, last_pet_time)`

## Files Changed
- `database.py` — migrations + two new functions
- `cogs/pet.py` — streak calculation, milestone detection, updated embeds
