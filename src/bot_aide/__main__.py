"""Point d'entrée : `python -m bot_aide`."""

from __future__ import annotations

import asyncio
import logging
import sys

from .config import ConfigError, load_config
from .db import Report, ReportStore
from .discord_bot import AideBot
from .twitch_bot import SendFn, TwitchCommandHandler, run_twitch

log = logging.getLogger("bot_aide")


async def main() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        sys.exit(f"Erreur de configuration : {exc}\nVoir le fichier .env.example.")

    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s : %(message)s",
    )
    store = ReportStore(config.database_path)
    bot = AideBot(config, store)

    async def notify_staff(report: Report) -> None:
        await bot.wait_until_ready()
        await bot.post_to_staff(report)

    stop_twitch = None
    async with bot:
        try:
            if config.twitch:
                tw = config.twitch

                def make_handler(send: SendFn, bot_user_id: str) -> TwitchCommandHandler:
                    return TwitchCommandHandler(
                        store, bot.limiter, send, notify_staff, config.public_help_url, bot_user_id
                    )

                stop_twitch = await run_twitch(
                    tw.client_id, tw.client_secret, tw.channels, tw.token_path, make_handler
                )
            else:
                log.info("Twitch désactivé (TWITCH_ENABLED=false)")
            await bot.start(config.discord.token)
        finally:
            if stop_twitch is not None:
                await stop_twitch()
            store.close()


def run() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
