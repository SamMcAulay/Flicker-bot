import os
import time
import json
import jwt
from aiohttp import web, ClientSession
from discord.ext import commands
from discord.http import Route
from database import (
    get_all_stats,
    get_server_settings,
    update_server_settings,
    get_custom_responses,
    add_custom_response,
    delete_custom_response,
    get_response_groups,
    add_response_group,
    set_response_group_enabled,
    delete_response_group,
    set_guild_disabled,
    get_guild_users,
    set_user_balance_admin,
    block_user,
    unblock_user,
    get_blocked_users,
    log_admin_action,
    get_audit_log,
    reset_guild_economy,
    bulk_reward_guild,
    get_user_all_guilds,
    add_allowed_channel,
    remove_allowed_channel,
    get_allowed_channels,
)

BUILTIN_GROUPS = [
    {"key": "greet", "name": "Greetings", "icon": "👋",
     "triggers": ["hi", "hello", "hey", "heyy", "yo", "sup", "greetings", "howdy", "hiya", "hola", "bonjour", "heya"],
     "responses": ["hey there @user!", "hi @user!", "good to see you, @user!", "hello!", "greetings, friend!"]},
    {"key": "bye", "name": "Farewells", "icon": "✈️",
     "triggers": ["bye", "goodbye", "cya", "later", "night", "gn", "peace", "adios", "farewell", "sleep"],
     "responses": ["goodbye, @user!", "later!", "have a good day, @user!", "take care!", "catch you on the flip side!", "sleep well!"]},
    {"key": "thanks", "name": "Thanks", "icon": "🙏",
     "triggers": ["thank", "thanks", "thx", "ty", "tysm", "appreciate", "cheers", "gracias"],
     "responses": ["no problem, @user!", "anytime!", "of course!", "happy to help, @user!", "you are very welcome!"]},
    {"key": "love", "name": "Love & Compliments", "icon": "❤️",
     "triggers": ["ily", "love", "luv", "heart", "adore", "wub", "cute", "sweet"],
     "responses": ["aww thank you, @user!", "you're sweet, @user!", "right back at you! ❤️", "aww, thanks! ❤️"]},
    {"key": "kill", "name": "Threats", "icon": "⚔️",
     "triggers": ["kill", "destroy", "eliminate", "murder", "attack", "smite", "stab", "shoot", "beat", "fight"],
     "responses": ["*charging up* Target locked.", "oh, it's on!", "*error 404* Mercy module not found."]},
    {"key": "trial", "name": "Legal / Police", "icon": "⚖️",
     "triggers": ["trial", "arrest", "jail", "judge", "court", "prison", "sue", "lawyer", "cop", "police", "guilty"],
     "responses": ["Order in the court!", "*bangs gavel* The council will decide your fate!", "WEE WOO WEE WOO — Flicker is on the case!"]},
    {"key": "fact", "name": "Fact Check", "icon": "🔍",
     "triggers": ["fact", "verify", "true", "false", "real", "fake", "source"],
     "responses": ["*scanning databanks...* 100% cap.", "*calculating...* The math checks out! Probably!", "My sources say 'maybe'."]},
]

BUILTIN_TEXT_OVERRIDES = {
    "drop_title":        "✨ Ooh! Shiny!",
    "drop_desc":         "Someone dropped a pouch of Stardust!",
    "drop_catch_prompt": "type **catch**!",
    "drop_win":          "🤲 **The dust has settled!**",
    "drop_lose":         "💨 **Poof!** The Stardust blew away in the cosmic wind.",
    "fast_type_title":   "💫 Catch the Falling Star!",
    "fast_type_desc":    "Quick! Type this magic spell before it disappears:",
    "fast_type_win":     "🌟 **Caught it!** {winner} snagged **{reward} Stardust**!",
    "fast_type_lose":    "💨 **Whoosh!** It flew away. The spell was `{code}`.",
    "math_title":        "🧩 Starship Puzzle!",
    "math_desc":         "Help me count the moons! What is:",
    "math_win":          "🤖 **Thank you!** {winner} solved the puzzle! **{reward} Stardust** for you!",
    "math_lose":         "💤 **I fell asleep counting...** The answer was **{answer}**.",
    "trivia_title":      "✨ A Little Star Told Me...",
    "trivia_tagline":    "*Make a wish and pick an answer!*",
    "trivia_correct":    "🎉 **Woohoo!** That's right! The answer was **{answer}**. {winner} caught **{reward} Stardust**!",
    "trivia_wrong":      "☁️ **Oh no!** That wasn't quite right. The answer was **{answer}**.",
    "trivia_timeout":    "🌙 **The stars have faded.** The answer was **{answer}**.",
    "scramble_title":    "🔤 Galactic Scramble!",
    "scramble_desc":     "Flicker's star charts got all mixed up!\n\nUnscramble this cosmic word:",
    "scramble_win":      "🌟 **Brilliant!** {winner} unscrambled **{word}** and earned **{reward} Stardust**!",
    "scramble_lose":     "💨 **Time's up!** The word was **{word}**.",
    # Coinflip
    "cf_spinning":       "The coin spins...",
    "cf_win":            "It landed on **{result}**! {icon}\n🎉 You won **{winnings}** Chips!",
    "cf_lose":           "It landed on **{result}**! {icon}\n❌ You lost **{bet}** Chips.",
    # Slots
    "slots_title":       "🎰 Cosmic Chip Slots 🎰",
    "slots_win":         "🎉 **WINNER!** 🎉\nYou won **{winnings}** Chips! ({multiplier}×)",
    "slots_lose":        "❌ **Lost!** ❌\nBetter luck next time.",
    # Blackjack
    "bj_title":          "🃏 Blackjack",
    "bj_natural_win":    "🎉 **Blackjack! You win {payout} Chips!** (2.5×)",
    "bj_bust":           "💥 Bust! You lose.",
    "bj_win":            "🎉 You win!",
    "bj_push":           "🤝 Push — bet returned.",
    "bj_dealer_wins":    "❌ Dealer wins.",
    # Higher or Lower
    "hilo_title":        "🃏 Higher or Lower",
    "hilo_tie":          "🤝 **Tie!** Next card was also **{card}** ({value}). Keep going!",
    "hilo_correct":      "✅ **Correct!** Next card was **{card}** ({value}).",
    "hilo_wrong":        "❌ **Wrong!** Next card was **{card}** ({value}). You lost **{bet}** Chips.",
    "hilo_cashout":      "💰 **Cashed out!** You won **{payout}** Chips ({mult}×)!",
    # Warp
    "warp_title":        "🚀 Hyperwarp Drive",
    "warp_start":        "The engines are humming... Dare to initiate warp?",
    "warp_overload":     "💥 **OVERLOAD!** You pushed the engines too far. You lost **{bet}** Chips.",
    "warp_jump":         "🌌 *ZOOOOM...* You safely navigated jump {jumps}!",
    "warp_dock":         "🛸 **Safely docked!** You returned to base with **{payout}** Chips ({mult}×)!",
    # Roulette
    "rt_title":          "🎡 Starwheel Roulette",
    "rt_spinning":       "Spinning the cosmic wheel...",
    "rt_win":            "🎉 **You win {winnings} Chips!** ({multiplier}×)",
    "rt_lose":           "❌ **You lost {bet} Chips.**",
}

DISCORD_API = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20
ADMINISTRATOR = 0x8


def _get_cors_headers(request) -> dict:
    allowed_origin = os.getenv("DASHBOARD_ORIGIN", "*")
    return {
        "Access-Control-Allow-Origin": allowed_origin,
        "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }


def _last_commit() -> dict:
    sha = os.getenv("RAILWAY_GIT_COMMIT_SHA", "")
    msg = os.getenv("RAILWAY_GIT_COMMIT_MESSAGE", "unknown")
    return {
        "hash": sha[:7] if sha else "unknown",
        "message": msg.splitlines()[0] if msg else "unknown",
        "date": os.getenv("RAILWAY_GIT_AUTHOR_TIME", "unknown"),
    }


def _issue_token(user_id: int, guilds: list[int], is_admin: bool = False) -> str:
    secret = os.getenv("DASHBOARD_SECRET_KEY", "changeme")
    payload = {
        "user_id": user_id,
        "guilds": guilds,
        "is_admin": is_admin,
        "exp": int(time.time()) + 3600 * 8,  # 8-hour session
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _require_admin(request: web.Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise web.HTTPUnauthorized(reason="Missing token")
    try:
        payload = _decode_token(auth[7:])
    except jwt.ExpiredSignatureError:
        raise web.HTTPUnauthorized(reason="Token expired")
    except jwt.InvalidTokenError:
        raise web.HTTPUnauthorized(reason="Invalid token")
    if not payload.get("is_admin"):
        raise web.HTTPForbidden(reason="Admin access required")
    return payload


def _decode_token(token: str) -> dict:
    secret = os.getenv("DASHBOARD_SECRET_KEY", "changeme")
    return jwt.decode(token, secret, algorithms=["HS256"])


def _require_auth(request: web.Request, guild_id: int):
    """Decode JWT and verify the user has access to guild_id. Returns payload or raises HTTPForbidden."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise web.HTTPUnauthorized(reason="Missing token")
    token = auth[7:]
    try:
        payload = _decode_token(token)
    except jwt.ExpiredSignatureError:
        raise web.HTTPUnauthorized(reason="Token expired")
    except jwt.InvalidTokenError:
        raise web.HTTPUnauthorized(reason="Invalid token")
    if guild_id not in payload.get("guilds", []):
        raise web.HTTPForbidden(reason="No access to this guild")
    return payload


class Api(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = None
        self.runner = None

    async def cog_load(self):
        app = web.Application()

        # Public routes
        app.router.add_get("/health", self.handle_health)
        app.router.add_get("/stats", self.handle_stats)

        # OAuth2 routes
        app.router.add_get("/auth/login", self.handle_login)
        app.router.add_get("/auth/callback", self.handle_callback)

        # Dashboard API routes (protected)
        app.router.add_route("OPTIONS", "/api/settings/{guild_id}", self.handle_preflight)
        app.router.add_get("/api/settings/{guild_id}", self.handle_get_settings)
        app.router.add_post("/api/settings/{guild_id}", self.handle_post_settings)
        app.router.add_route("OPTIONS", "/api/custom-responses/{guild_id}", self.handle_preflight)
        app.router.add_post("/api/custom-responses/{guild_id}", self.handle_add_response)
        app.router.add_route("OPTIONS", "/api/custom-responses/{guild_id}/{response_id}", self.handle_preflight)
        app.router.add_delete("/api/custom-responses/{guild_id}/{response_id}", self.handle_delete_response)
        app.router.add_route("OPTIONS", "/api/response-groups/{guild_id}", self.handle_preflight)
        app.router.add_post("/api/response-groups/{guild_id}", self.handle_add_group)
        app.router.add_route("OPTIONS", "/api/response-groups/{guild_id}/{group_id}", self.handle_preflight)
        app.router.add_patch("/api/response-groups/{guild_id}/{group_id}", self.handle_toggle_group)
        app.router.add_delete("/api/response-groups/{guild_id}/{group_id}", self.handle_delete_group)

        # Bot profile API
        app.router.add_route("OPTIONS", "/api/profile/{guild_id}", self.handle_preflight)
        app.router.add_post("/api/profile/{guild_id}", self.handle_update_profile)

        # Guild list for the server selector
        app.router.add_route("OPTIONS", "/api/guilds", self.handle_preflight)
        app.router.add_get("/api/guilds", self.handle_get_guilds)

        # Admin routes (require is_admin JWT claim)
        app.router.add_route("OPTIONS", "/admin/guilds", self.handle_preflight)
        app.router.add_get("/admin/guilds", self.handle_admin_guilds)
        app.router.add_route("OPTIONS", "/admin/stats", self.handle_preflight)
        app.router.add_get("/admin/stats", self.handle_admin_stats)
        app.router.add_route("OPTIONS", "/admin/guild/{guild_id}/users", self.handle_preflight)
        app.router.add_get("/admin/guild/{guild_id}/users", self.handle_admin_users)
        app.router.add_route("OPTIONS", "/admin/guild/{guild_id}/users/{user_id}", self.handle_preflight)
        app.router.add_patch("/admin/guild/{guild_id}/users/{user_id}", self.handle_admin_set_balance)
        app.router.add_route("OPTIONS", "/admin/guild/{guild_id}/toggle", self.handle_preflight)
        app.router.add_patch("/admin/guild/{guild_id}/toggle", self.handle_admin_toggle)
        app.router.add_route("OPTIONS", "/admin/guild/{guild_id}/economy/reset", self.handle_preflight)
        app.router.add_post("/admin/guild/{guild_id}/economy/reset", self.handle_admin_economy_reset)
        app.router.add_route("OPTIONS", "/admin/guild/{guild_id}/economy/bulk-reward", self.handle_preflight)
        app.router.add_post("/admin/guild/{guild_id}/economy/bulk-reward", self.handle_admin_bulk_reward)
        app.router.add_route("OPTIONS", "/admin/guild/{guild_id}/channels", self.handle_preflight)
        app.router.add_get("/admin/guild/{guild_id}/channels", self.handle_admin_get_channels)
        app.router.add_post("/admin/guild/{guild_id}/channels", self.handle_admin_add_channel)
        app.router.add_route("OPTIONS", "/admin/guild/{guild_id}/channels/{channel_id}", self.handle_preflight)
        app.router.add_delete("/admin/guild/{guild_id}/channels/{channel_id}", self.handle_admin_remove_channel)
        app.router.add_route("OPTIONS", "/admin/guild/{guild_id}/broadcast", self.handle_preflight)
        app.router.add_post("/admin/guild/{guild_id}/broadcast", self.handle_admin_broadcast)
        app.router.add_route("OPTIONS", "/admin/guild/{guild_id}/leave", self.handle_preflight)
        app.router.add_post("/admin/guild/{guild_id}/leave", self.handle_admin_leave_guild)
        app.router.add_route("OPTIONS", "/admin/user/{user_id}", self.handle_preflight)
        app.router.add_get("/admin/user/{user_id}", self.handle_admin_user_lookup)
        app.router.add_route("OPTIONS", "/admin/blocks", self.handle_preflight)
        app.router.add_get("/admin/blocks", self.handle_admin_get_blocks)
        app.router.add_route("OPTIONS", "/admin/blocks/{user_id}", self.handle_preflight)
        app.router.add_post("/admin/blocks/{user_id}", self.handle_admin_block_user)
        app.router.add_delete("/admin/blocks/{user_id}", self.handle_admin_unblock_user)
        app.router.add_route("OPTIONS", "/admin/audit-log", self.handle_preflight)
        app.router.add_get("/admin/audit-log", self.handle_admin_audit_log)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        port = int(os.getenv("PORT", 8080))
        site = web.TCPSite(self.runner, "0.0.0.0", port)
        await site.start()
        print(f"[API] Dashboard API running on port {port}")

    async def cog_unload(self):
        if self.runner:
            await self.runner.cleanup()

    @commands.Cog.listener()
    async def on_ready(self):
        if self.start_time is None:
            self.start_time = time.time()

    # ── Public routes ──────────────────────────────────────────────────────────

    async def handle_health(self, request: web.Request):
        return web.Response(text="OK", headers=_get_cors_headers(request))

    async def handle_stats(self, request: web.Request):
        stats = await get_all_stats()
        uptime = int(time.time() - self.start_time) if self.start_time else 0
        data = {
            "uptime_seconds": uptime,
            "last_commit": _last_commit(),
            "pet_count":       stats.get("pet_count", 0),
            "stardust_earned": stats.get("stardust_earned", 0),
            "games_correct":   stats.get("games_correct", 0),
            "games_wrong":     stats.get("games_wrong", 0),
            "chips_wagered":   stats.get("chips_wagered", 0),
            "chips_earnt":     stats.get("chips_earnt", 0),
            "chips_lost":      stats.get("chips_lost", 0),
        }
        return web.json_response(data, headers=_get_cors_headers(request))

    async def handle_preflight(self, request: web.Request):
        return web.Response(status=204, headers=_get_cors_headers(request))

    # ── OAuth2 ────────────────────────────────────────────────────────────────

    async def handle_login(self, request: web.Request):
        client_id = os.getenv("DISCORD_CLIENT_ID", "")
        redirect_uri = os.getenv("DASHBOARD_REDIRECT_URI", "")
        scope = "identify guilds"
        discord_url = (
            f"https://discord.com/api/oauth2/authorize"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope={scope.replace(' ', '%20')}"
        )
        raise web.HTTPFound(location=discord_url)

    async def handle_callback(self, request: web.Request):
        code = request.rel_url.query.get("code")
        if not code:
            raise web.HTTPBadRequest(reason="Missing code parameter")

        client_id = os.getenv("DISCORD_CLIENT_ID", "")
        client_secret = os.getenv("DISCORD_CLIENT_SECRET", "")
        redirect_uri = os.getenv("DASHBOARD_REDIRECT_URI", "")
        dashboard_url = os.getenv("DASHBOARD_ORIGIN", "")

        async with ClientSession() as session:
            # Exchange code for access token
            token_res = await session.post(
                "https://discord.com/api/oauth2/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_res.status != 200:
                raise web.HTTPBadGateway(reason="Discord token exchange failed")
            token_data = await token_res.json()
            access_token = token_data["access_token"]

            auth_headers = {"Authorization": f"Bearer {access_token}"}

            # Get user info
            user_res = await session.get(f"{DISCORD_API}/users/@me", headers=auth_headers)
            user_data = await user_res.json()
            user_id = int(user_data["id"])

            # Get user's guilds
            guilds_res = await session.get(f"{DISCORD_API}/users/@me/guilds", headers=auth_headers)
            user_guilds = await guilds_res.json()

        # Filter: guilds where Flicker is present AND user has admin/manage-guild
        bot_guild_ids = {g.id for g in self.bot.guilds}
        allowed_guilds = []
        for g in user_guilds:
            perms = int(g.get("permissions", 0))
            has_admin = bool(perms & ADMINISTRATOR) or bool(perms & MANAGE_GUILD)
            if has_admin and int(g["id"]) in bot_guild_ids:
                allowed_guilds.append(int(g["id"]))

        admin_ids = {
            int(x.strip())
            for x in os.getenv("ADMIN_USER_IDS", "").split(",")
            if x.strip().isdigit()
        }
        is_admin = user_id in admin_ids
        token = _issue_token(user_id, allowed_guilds, is_admin=is_admin)
        # Redirect to the dashboard with the token in the URL fragment
        raise web.HTTPFound(location=f"{dashboard_url}#token={token}")

    # ── Guild list ────────────────────────────────────────────────────────────

    async def handle_get_guilds(self, request: web.Request):
        """Return the list of guilds the logged-in user can manage."""
        try:
            payload = _decode_token(request.headers.get("Authorization", "")[7:])
        except Exception:
            raise web.HTTPUnauthorized(reason="Invalid token")

        guild_ids = payload.get("guilds", [])
        guilds = []
        for gid in guild_ids:
            g = self.bot.get_guild(gid)
            if g:
                guilds.append({
                    "id": str(g.id),
                    "name": g.name,
                    "icon": str(g.icon) if g.icon else None,
                })
        return web.json_response(guilds, headers=_get_cors_headers(request))

    # ── Settings API ──────────────────────────────────────────────────────────

    async def handle_get_settings(self, request: web.Request):
        guild_id = int(request.match_info["guild_id"])
        _require_auth(request, guild_id)

        settings = await get_server_settings(guild_id)
        custom_responses = await get_custom_responses(guild_id)
        response_groups = await get_response_groups(guild_id)

        # Build bot profile from live guild data
        avatar_url = ""
        if self.bot.user:
            av = self.bot.user.display_avatar
            avatar_url = str(av.url) if av else ""
        bot_profile = {"nickname": "", "avatar_url": avatar_url}
        guild = self.bot.get_guild(guild_id)
        if guild and guild.me:
            me = guild.me
            bot_profile["nickname"] = me.nick or ""
            guild_av = getattr(me, "guild_avatar", None)
            if guild_av:
                bot_profile["avatar_url"] = str(guild_av.url)

        data = {
            **settings,
            "bot_profile": bot_profile,
            "custom_responses": [
                {"id": r[0], "trigger_words": r[1], "response_text": r[2]}
                for r in custom_responses
            ],
            "response_groups": [
                {"id": r[0], "name": r[1], "triggers": r[2], "responses": r[3], "enabled": bool(r[4])}
                for r in response_groups
            ],
            "builtin_groups": BUILTIN_GROUPS,
        }
        return web.json_response(data, headers=_get_cors_headers(request))

    async def handle_post_settings(self, request: web.Request):
        guild_id = int(request.match_info["guild_id"])
        _require_auth(request, guild_id)

        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(reason="Invalid JSON")

        await update_server_settings(
            guild_id,
            command_toggles=body.get("command_toggles"),
            game_toggles=body.get("game_toggles"),
            event_toggles=body.get("event_toggles"),
            payout_overrides=body.get("payout_overrides"),
            chat_toggles=body.get("chat_toggles"),
            text_overrides=body.get("text_overrides"),
            welcome_config=body.get("welcome_config"),
        )
        return web.json_response({"ok": True}, headers=_get_cors_headers(request))

    # ── Custom Responses API ──────────────────────────────────────────────────

    async def handle_add_response(self, request: web.Request):
        guild_id = int(request.match_info["guild_id"])
        _require_auth(request, guild_id)

        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(reason="Invalid JSON")

        trigger_words = body.get("trigger_words", "").strip()
        response_text = body.get("response_text", "").strip()
        if not trigger_words or not response_text:
            raise web.HTTPBadRequest(reason="trigger_words and response_text are required")

        new_id = await add_custom_response(guild_id, trigger_words, response_text)
        return web.json_response(
            {"ok": True, "id": new_id},
            status=201,
            headers=_get_cors_headers(request),
        )

    async def handle_delete_response(self, request: web.Request):
        guild_id = int(request.match_info["guild_id"])
        _require_auth(request, guild_id)
        response_id = int(request.match_info["response_id"])
        await delete_custom_response(response_id)
        return web.json_response({"ok": True}, headers=_get_cors_headers(request))

    # ── Response Groups API ───────────────────────────────────────────────────

    async def handle_add_group(self, request: web.Request):
        guild_id = int(request.match_info["guild_id"])
        _require_auth(request, guild_id)
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(reason="Invalid JSON")
        name = body.get("name", "").strip()
        triggers = [t.strip().lower() for t in body.get("triggers", []) if str(t).strip()]
        responses = [r.strip() for r in body.get("responses", []) if str(r).strip()]
        if not name or not triggers or not responses:
            raise web.HTTPBadRequest(reason="name, triggers, and responses are required")
        new_id = await add_response_group(guild_id, name, triggers, responses)
        return web.json_response({"ok": True, "id": new_id}, status=201, headers=_get_cors_headers(request))

    async def handle_toggle_group(self, request: web.Request):
        guild_id = int(request.match_info["guild_id"])
        _require_auth(request, guild_id)
        group_id = int(request.match_info["group_id"])
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(reason="Invalid JSON")
        enabled = bool(body.get("enabled", True))
        await set_response_group_enabled(group_id, enabled)
        return web.json_response({"ok": True}, headers=_get_cors_headers(request))

    async def handle_delete_group(self, request: web.Request):
        guild_id = int(request.match_info["guild_id"])
        _require_auth(request, guild_id)
        group_id = int(request.match_info["group_id"])
        await delete_response_group(group_id)
        return web.json_response({"ok": True}, headers=_get_cors_headers(request))

    # ── Bot Profile API ────────────────────────────────────────────────────────

    async def handle_update_profile(self, request: web.Request):
        guild_id = int(request.match_info["guild_id"])
        _require_auth(request, guild_id)

        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(reason="Invalid JSON")

        if not self.bot.get_guild(guild_id):
            raise web.HTTPNotFound(reason="Guild not found")

        errors = []
        http_fields = {}

        # Nickname — pass None to clear
        if "nickname" in body:
            nick = (body["nickname"] or "").strip()
            http_fields["nick"] = nick if nick else None

        # Avatar — frontend sends the full data URI ("data:image/png;base64,...")
        # Discord API accepts this directly; pass None to revert to global avatar
        if "avatar" in body:
            http_fields["avatar"] = body["avatar"] or None

        if http_fields:
            try:
                await self.bot.http.request(
                    Route("PATCH", "/guilds/{guild_id}/members/@me", guild_id=guild_id),
                    json=http_fields,
                )
            except Exception as e:
                errors.append(str(e))

        # Prefix — saved to DB
        if "prefix" in body:
            await update_server_settings(guild_id, prefix=(body["prefix"] or "!").strip() or "!")

        if errors:
            return web.json_response(
                {"ok": False, "errors": errors},
                status=207,
                headers=_get_cors_headers(request),
            )
        return web.json_response({"ok": True}, headers=_get_cors_headers(request))

    # ── Admin routes ───────────────────────────────────────────────────────────

    async def handle_admin_guilds(self, request: web.Request):
        _require_admin(request)
        guilds = []
        for g in self.bot.guilds:
            settings = await get_server_settings(g.id)
            users = await get_guild_users(g.id)
            guilds.append({
                "id": str(g.id),
                "name": g.name,
                "icon": str(g.icon) if g.icon else None,
                "member_count": g.member_count,
                "bot_disabled": settings.get("bot_disabled", False),
                "user_count": len(users),
            })
        guilds.sort(key=lambda x: x["name"].lower())
        return web.json_response({"guilds": guilds}, headers=_get_cors_headers(request))

    async def handle_admin_users(self, request: web.Request):
        _require_admin(request)
        guild_id = int(request.match_info["guild_id"])
        rows = await get_guild_users(guild_id)
        guild = self.bot.get_guild(guild_id)
        users = []
        for user_id, balance, chips in rows:
            member = guild.get_member(user_id) if guild else None
            users.append({
                "user_id": str(user_id),
                "username": member.name if member else str(user_id),
                "display_name": member.display_name if member else str(user_id),
                "avatar": str(member.display_avatar.url) if member else None,
                "balance": balance,
                "chips": chips,
            })
        return web.json_response({"users": users}, headers=_get_cors_headers(request))

    async def handle_admin_set_balance(self, request: web.Request):
        _require_admin(request)
        guild_id = int(request.match_info["guild_id"])
        user_id = int(request.match_info["user_id"])
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(reason="Invalid JSON")
        balance = int(body.get("balance", 0))
        chips = int(body.get("chips", 0))
        await set_user_balance_admin(user_id, guild_id, balance, chips)
        return web.json_response({"ok": True}, headers=_get_cors_headers(request))

    async def handle_admin_toggle(self, request: web.Request):
        payload = _require_admin(request)
        guild_id = int(request.match_info["guild_id"])
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(reason="Invalid JSON")
        disabled = bool(body.get("disabled", False))
        await set_guild_disabled(guild_id, disabled)
        await log_admin_action(payload["user_id"], "toggle_guild", guild_id=guild_id,
                               details=f"disabled={disabled}")
        return web.json_response({"ok": True}, headers=_get_cors_headers(request))

    async def handle_admin_stats(self, request: web.Request):
        _require_admin(request)
        stats = await get_all_stats()
        uptime = int(time.time() - self.start_time) if self.start_time else 0
        data = {
            "uptime_seconds": uptime,
            "last_commit": _last_commit(),
            "guild_count": len(self.bot.guilds),
            "latency_ms": round(self.bot.latency * 1000, 1),
            "pet_count":       stats.get("pet_count", 0),
            "stardust_earned": stats.get("stardust_earned", 0),
            "games_correct":   stats.get("games_correct", 0),
            "games_wrong":     stats.get("games_wrong", 0),
            "chips_wagered":   stats.get("chips_wagered", 0),
            "chips_earnt":     stats.get("chips_earnt", 0),
            "chips_lost":      stats.get("chips_lost", 0),
        }
        return web.json_response(data, headers=_get_cors_headers(request))

    async def handle_admin_economy_reset(self, request: web.Request):
        payload = _require_admin(request)
        guild_id = int(request.match_info["guild_id"])
        count = await reset_guild_economy(guild_id)
        await log_admin_action(payload["user_id"], "economy_reset", guild_id=guild_id,
                               details=f"removed {count} rows")
        return web.json_response({"ok": True, "removed": count}, headers=_get_cors_headers(request))

    async def handle_admin_bulk_reward(self, request: web.Request):
        payload = _require_admin(request)
        guild_id = int(request.match_info["guild_id"])
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(reason="Invalid JSON")
        balance_delta = int(body.get("balance", 0))
        chips_delta = int(body.get("chips", 0))
        count = await bulk_reward_guild(guild_id, balance_delta=balance_delta, chips_delta=chips_delta)
        await log_admin_action(payload["user_id"], "bulk_reward", guild_id=guild_id,
                               details=f"balance+{balance_delta} chips+{chips_delta} to {count} users")
        return web.json_response({"ok": True, "affected": count}, headers=_get_cors_headers(request))

    async def handle_admin_get_channels(self, request: web.Request):
        _require_admin(request)
        guild_id = int(request.match_info["guild_id"])
        all_channel_ids = await get_allowed_channels()
        guild = self.bot.get_guild(guild_id)
        channels = []
        for cid in all_channel_ids:
            ch = self.bot.get_channel(cid)
            if ch and ch.guild and ch.guild.id == guild_id:
                channels.append({"id": str(cid), "name": ch.name})
        # Also include any IDs that belong to the guild but channel not cached
        if guild:
            guild_channel_ids = {c.id for c in guild.text_channels}
            for cid in all_channel_ids:
                if cid in guild_channel_ids and not any(c["id"] == str(cid) for c in channels):
                    ch = guild.get_channel(cid)
                    channels.append({"id": str(cid), "name": ch.name if ch else str(cid)})
        return web.json_response({"channels": channels}, headers=_get_cors_headers(request))

    async def handle_admin_add_channel(self, request: web.Request):
        payload = _require_admin(request)
        guild_id = int(request.match_info["guild_id"])
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(reason="Invalid JSON")
        channel_id = int(body.get("channel_id", 0))
        if not channel_id:
            raise web.HTTPBadRequest(reason="Missing channel_id")
        await add_allowed_channel(channel_id)
        await log_admin_action(payload["user_id"], "add_channel", guild_id=guild_id, target_id=channel_id)
        return web.json_response({"ok": True}, headers=_get_cors_headers(request))

    async def handle_admin_remove_channel(self, request: web.Request):
        payload = _require_admin(request)
        guild_id = int(request.match_info["guild_id"])
        channel_id = int(request.match_info["channel_id"])
        await remove_allowed_channel(channel_id)
        await log_admin_action(payload["user_id"], "remove_channel", guild_id=guild_id, target_id=channel_id)
        return web.json_response({"ok": True}, headers=_get_cors_headers(request))

    async def handle_admin_broadcast(self, request: web.Request):
        payload = _require_admin(request)
        guild_id = int(request.match_info["guild_id"])
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(reason="Invalid JSON")
        message = str(body.get("message", "")).strip()
        if not message:
            raise web.HTTPBadRequest(reason="Empty message")
        guild = self.bot.get_guild(guild_id)
        if not guild:
            raise web.HTTPNotFound(reason="Guild not found")
        all_channel_ids = await get_allowed_channels()
        guild_channel_ids = {c.id for c in guild.text_channels}
        target_ids = [cid for cid in all_channel_ids if cid in guild_channel_ids]
        if not target_ids:
            raise web.HTTPBadRequest(reason="No allowed channels configured for this guild")
        sent = 0
        for cid in target_ids:
            ch = guild.get_channel(cid)
            if ch:
                try:
                    await ch.send(message)
                    sent += 1
                except Exception:
                    pass
        await log_admin_action(payload["user_id"], "broadcast", guild_id=guild_id,
                               details=f"sent to {sent} channel(s)")
        return web.json_response({"ok": True, "sent_to": sent}, headers=_get_cors_headers(request))

    async def handle_admin_leave_guild(self, request: web.Request):
        payload = _require_admin(request)
        guild_id = int(request.match_info["guild_id"])
        guild = self.bot.get_guild(guild_id)
        if not guild:
            raise web.HTTPNotFound(reason="Guild not found")
        await log_admin_action(payload["user_id"], "leave_guild", guild_id=guild_id,
                               details=guild.name)
        await guild.leave()
        return web.json_response({"ok": True}, headers=_get_cors_headers(request))

    async def handle_admin_user_lookup(self, request: web.Request):
        _require_admin(request)
        user_id = int(request.match_info["user_id"])
        rows = await get_user_all_guilds(user_id)
        guilds = []
        for guild_id, balance, chips in rows:
            g = self.bot.get_guild(guild_id)
            guilds.append({
                "guild_id": str(guild_id),
                "guild_name": g.name if g else str(guild_id),
                "guild_icon": str(g.icon) if g and g.icon else None,
                "balance": balance,
                "chips": chips,
            })
        # Try to get Discord user info
        user_info = {"id": str(user_id), "name": str(user_id), "avatar": None}
        try:
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            if user:
                user_info = {
                    "id": str(user.id),
                    "name": user.name,
                    "display_name": user.display_name,
                    "avatar": str(user.display_avatar.url) if user.display_avatar else None,
                }
        except Exception:
            pass
        return web.json_response({"user": user_info, "guilds": guilds}, headers=_get_cors_headers(request))

    async def handle_admin_get_blocks(self, request: web.Request):
        _require_admin(request)
        rows = await get_blocked_users()
        blocks = []
        for user_id, reason, blocked_at, blocked_by in rows:
            user = self.bot.get_user(user_id)
            admin = self.bot.get_user(blocked_by)
            blocks.append({
                "user_id": str(user_id),
                "username": user.name if user else str(user_id),
                "avatar": str(user.display_avatar.url) if user and user.display_avatar else None,
                "reason": reason,
                "blocked_at": blocked_at,
                "blocked_by_id": str(blocked_by),
                "blocked_by_name": admin.name if admin else str(blocked_by),
            })
        return web.json_response({"blocks": blocks}, headers=_get_cors_headers(request))

    async def handle_admin_block_user(self, request: web.Request):
        payload = _require_admin(request)
        user_id = int(request.match_info["user_id"])
        try:
            body = await request.json()
        except Exception:
            body = {}
        reason = str(body.get("reason", "")).strip()
        await block_user(user_id, reason, blocked_by=payload["user_id"])
        await log_admin_action(payload["user_id"], "block_user", target_id=user_id, details=reason)
        return web.json_response({"ok": True}, headers=_get_cors_headers(request))

    async def handle_admin_unblock_user(self, request: web.Request):
        payload = _require_admin(request)
        user_id = int(request.match_info["user_id"])
        await unblock_user(user_id)
        await log_admin_action(payload["user_id"], "unblock_user", target_id=user_id)
        return web.json_response({"ok": True}, headers=_get_cors_headers(request))

    async def handle_admin_audit_log(self, request: web.Request):
        _require_admin(request)
        limit = int(request.rel_url.query.get("limit", 100))
        rows = await get_audit_log(limit=min(limit, 500))
        entries = []
        for row_id, admin_id, action, guild_id, target_id, details, timestamp in rows:
            admin = self.bot.get_user(admin_id)
            entries.append({
                "id": row_id,
                "admin_id": str(admin_id),
                "admin_name": admin.name if admin else str(admin_id),
                "action": action,
                "guild_id": str(guild_id) if guild_id else None,
                "target_id": str(target_id) if target_id else None,
                "details": details,
                "timestamp": timestamp,
            })
        return web.json_response({"entries": entries}, headers=_get_cors_headers(request))


async def setup(bot):
    await bot.add_cog(Api(bot))
