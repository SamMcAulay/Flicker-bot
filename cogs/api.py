import os
import time
import subprocess
from aiohttp import web
from discord.ext import commands
from database import get_all_stats

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET",
}

class Api(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = None
        self.runner = None

    async def cog_load(self):
        app = web.Application()
        app.router.add_get("/stats", self.handle_stats)
        app.router.add_get("/health", self.handle_health)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        port = int(os.getenv("PORT", 8080))
        site = web.TCPSite(self.runner, "0.0.0.0", port)
        await site.start()
        print(f"[API] Stats server running on port {port}")

    async def cog_unload(self):
        if self.runner:
            await self.runner.cleanup()

    @commands.Cog.listener()
    async def on_ready(self):
        if self.start_time is None:
            self.start_time = time.time()

    def _last_commit(self) -> dict:
        try:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            out = subprocess.check_output(
                ["git", "log", "-1", "--format=%h||%s||%cd", "--date=short"],
                cwd=root, stderr=subprocess.DEVNULL
            ).decode().strip()
            parts = out.split("||", 2)
            return {"hash": parts[0], "message": parts[1], "date": parts[2]}
        except Exception:
            return {"hash": "unknown", "message": "unknown", "date": "unknown"}

    async def handle_stats(self, request):
        stats = await get_all_stats()
        uptime = int(time.time() - self.start_time) if self.start_time else 0
        data = {
            "uptime_seconds": uptime,
            "last_commit": self._last_commit(),
            "pet_count":       stats.get("pet_count", 0),
            "stardust_earned": stats.get("stardust_earned", 0),
            "games_correct":   stats.get("games_correct", 0),
            "games_wrong":     stats.get("games_wrong", 0),
            "chips_wagered":   stats.get("chips_wagered", 0),
            "chips_earnt":     stats.get("chips_earnt", 0),
            "chips_lost":      stats.get("chips_lost", 0),
        }
        return web.json_response(data, headers=CORS_HEADERS)

    async def handle_health(self, request):
        return web.Response(text="OK", headers=CORS_HEADERS)


async def setup(bot):
    await bot.add_cog(Api(bot))
