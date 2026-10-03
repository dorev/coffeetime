"""Côté Twitch : écoute le chat (EventSub WebSocket) et répond à !aide / !signaler.

Le chat Twitch est public : le bot n'y tient jamais de conversation sensible,
il renvoie vers le canal privé (PUBLIC_HELP_URL) et prévient l'équipe sur Discord.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Iterable

from . import messages
from .db import Kind, Report, ReportStore, Source
from .ratelimit import RateLimiter

log = logging.getLogger(__name__)

HELP_COMMANDS = {"aide", "help"}
REPORT_COMMANDS = {"signaler", "report"}
MOD_BADGES = {"broadcaster", "moderator"}
TWITCH_MAX_MESSAGE = 500

SendFn = Callable[[str, str, str | None], Awaitable[None]]
"""send(broadcaster_id, text, reply_to_message_id)"""
NotifyFn = Callable[[Report], Awaitable[None]]


@dataclass(frozen=True)
class ChatMessage:
    """Sous-ensemble utile d'un événement channel.chat.message."""

    message_id: str
    broadcaster_id: str
    channel_login: str
    chatter_id: str
    chatter_login: str
    text: str
    badges: frozenset[str]

    @property
    def is_mod(self) -> bool:
        return bool(self.badges & MOD_BADGES)


def parse_command(text: str) -> tuple[str, str] | None:
    """'!Signaler @bob propos haineux' -> ('signaler', '@bob propos haineux')."""
    text = text.strip()
    if not text.startswith("!") or len(text) < 2:
        return None
    name, _, args = text[1:].partition(" ")
    return name.lower(), args.strip()


def split_target(args: str) -> tuple[str | None, str]:
    """'@bob propos haineux' -> ('bob', 'propos haineux')."""
    first, _, rest = args.partition(" ")
    if first.startswith("@") and len(first) > 1:
        return first[1:].lower(), rest.strip()
    return None, args


class TwitchCommandHandler:
    """Logique des commandes, indépendante de la librairie Twitch (testable)."""

    def __init__(
        self,
        store: ReportStore,
        limiter: RateLimiter,
        send: SendFn,
        notify_staff: NotifyFn,
        public_help_url: str,
        bot_user_id: str,
    ) -> None:
        self.store = store
        self.limiter = limiter
        self.send = send
        self.notify_staff = notify_staff
        self.url = public_help_url
        self.bot_user_id = bot_user_id

    async def handle(self, msg: ChatMessage) -> None:
        if msg.chatter_id == self.bot_user_id:
            return
        parsed = parse_command(msg.text)
        if parsed is None:
            return
        name, args = parsed
        if name in HELP_COMMANDS:
            await self._help(msg)
        elif name in REPORT_COMMANDS:
            await self._report(msg, args)

    async def _reply(self, msg: ChatMessage, text: str) -> None:
        await self.send(msg.broadcaster_id, text[:TWITCH_MAX_MESSAGE], msg.message_id)

    async def _help(self, msg: ChatMessage) -> None:
        if not self.limiter.allow(f"twitch:{msg.chatter_id}"):
            return  # silencieux pour ne pas inonder le chat
        await self._reply(msg, messages.TWITCH_HELP.format(user=msg.chatter_login, url=self.url))
        report = self.store.create(
            source=Source.TWITCH,
            kind=Kind.HELP,
            reporter=msg.chatter_login,
            location=f"twitch.tv/{msg.channel_login}",
            description="A tapé !aide dans le chat (lien privé envoyé).",
        )
        await self.notify_staff(report)

    async def _report(self, msg: ChatMessage, args: str) -> None:
        if not args:
            await self._reply(
                msg, messages.TWITCH_REPORT_USAGE.format(user=msg.chatter_login, url=self.url)
            )
            return
        if not self.limiter.allow(f"twitch:{msg.chatter_id}"):
            await self._reply(msg, messages.TWITCH_RATE_LIMITED.format(user=msg.chatter_login))
            return
        target, reason = split_target(args)
        reporter = msg.chatter_login + (" (modérateur)" if msg.is_mod else "")
        report = self.store.create(
            source=Source.TWITCH,
            kind=Kind.REPORT,
            reporter=reporter,
            target=target,
            location=f"twitch.tv/{msg.channel_login}",
            description=reason or "(aucune raison donnée)",
        )
        await self._reply(
            msg,
            messages.TWITCH_REPORT_ACK.format(user=msg.chatter_login, id=report.id, url=self.url),
        )
        await self.notify_staff(report)


async def run_twitch(
    client_id: str,
    client_secret: str,
    channels: Iterable[str],
    token_path: Path,
    make_handler: Callable[[SendFn, str], TwitchCommandHandler],
) -> Callable[[], Awaitable[None]]:
    """Connecte le bot Twitch et retourne une coroutine d'arrêt.

    Au premier lancement, un navigateur s'ouvre pour autoriser le compte du bot
    (connecte-toi avec le compte Twitch *du bot*, pas le tien). Le jeton est
    ensuite sauvegardé dans `token_path` et renouvelé automatiquement.
    """
    # Imports locaux : le bot Discord fonctionne même si Twitch est désactivé.
    from twitchAPI.eventsub.websocket import EventSubWebsocket
    from twitchAPI.helper import first
    from twitchAPI.oauth import UserAuthenticationStorageHelper
    from twitchAPI.object.eventsub import ChannelChatMessageEvent
    from twitchAPI.twitch import Twitch
    from twitchAPI.type import AuthScope

    scopes = [AuthScope.USER_READ_CHAT, AuthScope.USER_WRITE_CHAT]
    twitch = await Twitch(client_id, client_secret)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    await UserAuthenticationStorageHelper(twitch, scopes, storage_path=token_path).bind()

    bot_user = await first(twitch.get_users())
    if bot_user is None:
        raise RuntimeError("Impossible de récupérer le compte Twitch du bot")
    log.info("Twitch : connecté en tant que %s", bot_user.login)

    async def send(broadcaster_id: str, text: str, reply_to: str | None) -> None:
        resp = await twitch.send_chat_message(broadcaster_id, bot_user.id, text, reply_to)
        if not resp.is_sent:
            log.warning("Message Twitch refusé : %s", resp.drop_reason)

    handler = make_handler(send, bot_user.id)

    async def on_message(event: ChannelChatMessageEvent) -> None:
        e = event.event
        msg = ChatMessage(
            message_id=e.message_id,
            broadcaster_id=e.broadcaster_user_id,
            channel_login=e.broadcaster_user_login,
            chatter_id=e.chatter_user_id,
            chatter_login=e.chatter_user_login,
            text=e.message.text,
            badges=frozenset(b.set_id for b in e.badges),
        )
        try:
            await handler.handle(msg)
        except Exception:
            log.exception("Erreur en traitant un message Twitch")

    # Les callbacks EventSub s'exécutent sur la boucle principale (celle de discord.py).
    eventsub = EventSubWebsocket(twitch, callback_loop=asyncio.get_running_loop())
    eventsub.start()

    async for user in twitch.get_users(logins=list(channels)):
        await eventsub.listen_channel_chat_message(user.id, bot_user.id, on_message)
        log.info("Twitch : écoute du chat de %s", user.login)

    async def stop() -> None:
        await eventsub.stop()
        await twitch.close()

    return stop
