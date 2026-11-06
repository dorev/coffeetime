"""Bot de chat Twitch (option 1) : commande `!trn [message]` réservée au streamer et aux mods.

- Le bot efface aussitôt la commande (il doit être modérateur de la chaîne : `/mod NomDuBot`).
- Il répond UNIQUEMENT par chuchotement à la personne qui a fait la demande.
  Jamais de message public. Si le chuchotement échoue (quota, réglages de la personne),
  l'échec est enregistré dans le journal (Google Sheets) et c'est tout.
- Les commandes des autres viewers sont ignorées.

Le compte du bot est autorisé une fois via /bot/autoriser (voir README).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

from . import events as ev
from . import texts
from .crypto import Box
from .dispatch import RequestService
from .events import EventLog
from .store import Channel, Store
from .twitch_api import BOT_SCOPES, Tokens

log = logging.getLogger(__name__)

COMMANDS = {"trn"}
MOD_BADGES = {"broadcaster", "moderator"}
WHISPER_MAX = 500
SECRET_KEY_NAME = "twitch_bot_tokens"


@dataclass(frozen=True)
class ChatMessage:
    message_id: str
    broadcaster_id: str
    channel_login: str
    chatter_id: str
    chatter_login: str
    text: str
    badges: frozenset[str]

    @property
    def is_mod(self) -> bool:
        return bool(self.badges & MOD_BADGES) or self.chatter_id == self.broadcaster_id


def parse_command(text: str) -> tuple[str, str] | None:
    """'!TRN ça dérape' -> ('trn', 'ça dérape')."""
    text = text.strip()
    if not text.startswith("!") or len(text) < 2:
        return None
    name, _, args = text[1:].partition(" ")
    return name.lower(), args.strip()


class ChatActions(Protocol):
    async def delete(self, broadcaster_id: str, message_id: str) -> None: ...
    async def whisper(self, to_user_id: str, text: str) -> None: ...


class ChatCommandHandler:
    """Logique de la commande, indépendante de la librairie Twitch (testable)."""

    def __init__(self, service: RequestService, events: EventLog, actions: ChatActions, bot_user_id: str) -> None:
        self.service = service
        self.events = events
        self.actions = actions
        self.bot_user_id = bot_user_id

    async def handle(self, msg: ChatMessage) -> None:
        if msg.chatter_id == self.bot_user_id:
            return
        parsed = parse_command(msg.text)
        if parsed is None or parsed[0] not in COMMANDS or not msg.is_mod:
            return

        try:
            await self.actions.delete(msg.broadcaster_id, msg.message_id)
        except Exception as exc:  # le bot n'est probablement pas mod de la chaîne
            self.events.record(
                ev.SUPPRESSION_ECHOUEE, channel=msg.channel_login, source="chat",
                actor=msg.chatter_login, detail=str(exc)[:200],
            )

        result = await self.service.submit(
            msg.channel_login, source="chat", requested_by=msg.chatter_login, message=parsed[1]
        )
        reply = texts.request_result_text(result.outcome.value, result.trn_status, result.retry_after_minutes)
        try:
            await self.actions.whisper(msg.chatter_id, reply[:WHISPER_MAX])
        except Exception as exc:
            self.events.record(
                ev.CHUCHOTEMENT_ECHOUE, channel=msg.channel_login, source="chat",
                actor=msg.chatter_login, trn_status=result.trn_status.value,
                detail=f"{type(exc).__name__}: {str(exc)[:200]}",
            )


class TwitchChatBot:
    """Connexion EventSub du compte bot ; s'abonne au chat de chaque chaîne inscrite."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        store: Store,
        service: RequestService,
        events: EventLog,
        secret_key: str,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.store = store
        self.service = service
        self.events = events
        self.box = Box(secret_key, "twitch-bot")
        self._twitch = None
        self._eventsub = None
        self._bot_user = None
        self._topics: dict[str, str] = {}   # login de la chaîne -> id d'abonnement
        self._handler: ChatCommandHandler | None = None
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._eventsub is not None

    @property
    def bot_login(self) -> str | None:
        return self._bot_user.login if self._bot_user else None

    def save_tokens(self, tokens: Tokens) -> None:
        self.store.set_secret(
            SECRET_KEY_NAME, self.box.seal({"access": tokens.access_token, "refresh": tokens.refresh_token})
        )

    def _load_tokens(self) -> dict | None:
        return self.box.open(self.store.get_secret(SECRET_KEY_NAME))

    async def start(self) -> None:
        async with self._lock:
            await self._stop_unlocked()
            tokens = self._load_tokens()
            if not tokens:
                log.warning("Bot Twitch pas encore autorisé : ouvrir /bot/autoriser?cle=… (voir README)")
                return
            await self._start_unlocked(tokens)

    async def _start_unlocked(self, tokens: dict) -> None:
        from twitchAPI.eventsub.websocket import EventSubWebsocket
        from twitchAPI.helper import first
        from twitchAPI.twitch import Twitch
        from twitchAPI.type import AuthScope

        scopes = [AuthScope(s) for s in BOT_SCOPES]
        twitch = await Twitch(self.client_id, self.client_secret)

        async def on_refresh(access: str, refresh: str) -> None:
            self.store.set_secret(SECRET_KEY_NAME, self.box.seal({"access": access, "refresh": refresh}))

        twitch.user_auth_refresh_callback = on_refresh
        await twitch.set_user_authentication(tokens["access"], scopes, tokens["refresh"])
        bot_user = await first(twitch.get_users())
        if bot_user is None:
            raise RuntimeError("Compte Twitch du bot introuvable")

        class Actions:
            async def delete(self, broadcaster_id: str, message_id: str) -> None:
                await twitch.delete_chat_message(broadcaster_id, bot_user.id, message_id)

            async def whisper(self, to_user_id: str, text: str) -> None:
                await twitch.send_whisper(bot_user.id, to_user_id, text)

        self._handler = ChatCommandHandler(self.service, self.events, Actions(), bot_user.id)
        eventsub = EventSubWebsocket(twitch, callback_loop=asyncio.get_running_loop())
        eventsub.start()
        self._twitch, self._eventsub, self._bot_user = twitch, eventsub, bot_user
        log.info("Bot Twitch connecté en tant que %s", bot_user.login)
        for channel in self.store.list_channels():
            await self._subscribe(channel)

    async def _on_message(self, event) -> None:
        e = event.event
        msg = ChatMessage(
            message_id=e.message_id,
            broadcaster_id=e.broadcaster_user_id,
            channel_login=e.broadcaster_user_login,
            chatter_id=e.chatter_user_id,
            chatter_login=e.chatter_user_login,
            text=e.message.text,
            badges=frozenset(b.set_id for b in (e.badges or [])),
        )
        if self._handler is None:
            return
        try:
            await self._handler.handle(msg)
        except Exception:
            log.exception("Erreur en traitant un message Twitch")

    async def _subscribe(self, channel: Channel) -> None:
        if self._eventsub is None or channel.login in self._topics:
            return
        try:
            topic = await self._eventsub.listen_channel_chat_message(
                channel.twitch_id, self._bot_user.id, self._on_message
            )
            self._topics[channel.login] = topic
            log.info("Bot Twitch : écoute du chat de %s", channel.login)
        except Exception:
            log.exception("Impossible d'écouter le chat de %s", channel.login)

    async def add_channel(self, channel: Channel) -> None:
        async with self._lock:
            await self._subscribe(channel)

    async def remove_channel(self, login: str) -> None:
        async with self._lock:
            topic = self._topics.pop(login, None)
            if topic and self._eventsub is not None:
                try:
                    await self._eventsub.unsubscribe_topic(topic)
                except Exception:
                    log.exception("Désabonnement impossible pour %s", login)

    async def authorize(self, tokens: Tokens, login: str) -> None:
        """Appelé après /bot/autoriser : enregistre les jetons et (re)démarre le bot."""
        self.save_tokens(tokens)
        self.events.record(ev.BOT_TWITCH_AUTORISE, source="web", actor=login)
        await self.start()

    async def stop(self) -> None:
        async with self._lock:
            await self._stop_unlocked()

    async def _stop_unlocked(self) -> None:
        if self._eventsub is not None:
            try:
                await self._eventsub.stop()
            except Exception:
                log.exception("Arrêt EventSub")
        if self._twitch is not None:
            await self._twitch.close()
        self._twitch = self._eventsub = self._bot_user = None
        self._topics.clear()
