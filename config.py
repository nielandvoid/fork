import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    MODERATOR_ROLE = os.getenv("MODERATOR_ROLE", "Moderator")
    raw_port = os.getenv("PORT")
    PORT = int(raw_port) if raw_port and raw_port.isdigit() else None

    @classmethod
    def validate(cls):
        if not cls.DISCORD_TOKEN or cls.DISCORD_TOKEN == "your_discord_bot_token_here":
            return False
        return True
