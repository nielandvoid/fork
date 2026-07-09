import socket

orig_getaddrinfo = socket.getaddrinfo
def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = patched_getaddrinfo

import discord
from discord.ext import commands
import sys
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
import database

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass

def run_health_check_server(port: int):
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        server.serve_forever()
    except Exception:
        pass

class ForkBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="fork!", intents=intents)

    async def setup_hook(self):
        database.init_db()
        await self.load_extension("session_cog")
        try:
            await self.tree.sync()
        except Exception:
            pass

    async def on_ready(self):
        pass

def main():
    if not Config.validate():
        sys.exit(1)

    if Config.PORT:
        web_thread = threading.Thread(target=run_health_check_server, args=(Config.PORT,), daemon=True)
        web_thread.start()

    bot = ForkBot()
    bot.run(Config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()
