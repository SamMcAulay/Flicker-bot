import os
import time
import json
import jwt
from aiohttp import web, ClientSession
from discord.ext import commands
from database import (
    get_all_stats,
    get_server_settings,
    update_server_settings,
    get_custom_responses,
    add_custom_response,
    delete_custom_response,
)

DISCORD_API = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20
ADMINISTRATOR = 0x8


def _get_cors_headers(request) -> dict:
    allowed_origin = os.getenv("DASHBOARD_ORIGIN", "*")
    return {
        "Access-Control-Allow-Origin": allowed_origin,
        "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
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


def _issue_token(user_id: int, guilds: list[int]) -> str:
    secret = os.getenv("DASHBOARD_SECRET_KEY", "changeme")
    payload = {
        "user_id": user_id,
        "guilds": guilds,
        "exp": int(time.time()) + 3600 * 8,  # 8-hour session
    }
    return jwt.encode(payload, secret, algorithm="HS256")


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

        # Guild list for the server selector
        app.router.add_route("OPTIONS", "/api/guilds", self.handle_preflight)
        app.router.add_get("/api/guilds", self.handle_get_guilds)

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

        token = _issue_token(user_id, allowed_guilds)
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

        data = {
            **settings,
            "custom_responses": [
                {"id": r[0], "trigger_words": r[1], "response_text": r[2]}
                for r in custom_responses
            ],
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


async def setup(bot):
    await bot.add_cog(Api(bot))
