from __future__ import annotations
from .discord_app.bot import create_bot

def main() -> None:
    bot = create_bot()
    bot.run(bot.cfg.discord_token)

if __name__ == "__main__":
    main()
