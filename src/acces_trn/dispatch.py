"""Traitement d'une demande de TRN, commun aux trois options
(commande chat, page Web, extension Twitch).

Règles :
- la chaîne doit être inscrite (ajoutée par les TRN via Discord) ;
- une demande par chaîne toutes les REQUEST_COOLDOWN_MINUTES minutes ;
- tout est enregistré, même les demandes bloquées ou faites sans TRN disponible ;
- Discord : mention du rôle TRN seulement si l'équipe est en service.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Awaitable, Callable

from . import events as ev
from .events import EventLog
from .store import HelpRequest, Status, Store

log = logging.getLogger(__name__)

MESSAGE_MAX = 300


class Outcome(str, Enum):
    SENT = "envoyee"           # un·e TRN est disponible ou occupé·e : la demande est dans la file
    NO_TRN = "sans_trn"        # personne en service : enregistrée, sans mention
    COOLDOWN = "delai"         # une demande récente existe déjà pour cette chaîne
    UNKNOWN_CHANNEL = "chaine_inconnue"


@dataclass(frozen=True)
class RequestResult:
    outcome: Outcome
    channel: str
    trn_status: Status
    request: HelpRequest | None = None
    retry_after_minutes: int | None = None


Notifier = Callable[[HelpRequest, bool], Awaitable[str | None]]
"""notify(demande, mentionner_les_trn) -> identifiant du message Discord"""


class RequestService:
    def __init__(self, store: Store, events: EventLog, cooldown_minutes: int) -> None:
        self.store = store
        self.events = events
        self.cooldown = timedelta(minutes=cooldown_minutes)
        self.notifier: Notifier | None = None  # branché par le bot Discord

    async def submit(
        self,
        channel_login: str,
        *,
        source: str,
        requested_by: str,
        message: str = "",
        now: datetime | None = None,
    ) -> RequestResult:
        now = now or datetime.now(timezone.utc)
        login = channel_login.lower()
        message = " ".join(message.split())[:MESSAGE_MAX]
        status = self.store.current(now).status

        channel = self.store.get_channel(login)
        if channel is None:
            self.events.record(
                ev.DEMANDE_REFUSEE, channel=login, source=source, actor=requested_by,
                message=message, trn_status=status.value, detail="chaîne non inscrite",
            )
            return RequestResult(Outcome.UNKNOWN_CHANNEL, login, status)

        last = self.store.last_counted_request(login)
        if last is not None and now - last.created_at < self.cooldown:
            remaining = self.cooldown - (now - last.created_at)
            minutes = max(1, math.ceil(remaining.total_seconds() / 60))
            self.store.add_request(
                channel=login, source=source, requested_by=requested_by, message=message,
                outcome=Outcome.COOLDOWN.value, trn_status=status.value, now=now,
            )
            self.events.record(
                ev.DEMANDE_BLOQUEE_DELAI, channel=login, source=source, actor=requested_by,
                message=message, trn_status=status.value,
                detail=f"demande #{last.id} il y a moins de {int(self.cooldown.total_seconds() // 60)} min",
            )
            return RequestResult(Outcome.COOLDOWN, login, status, retry_after_minutes=minutes)

        outcome = Outcome.NO_TRN if status is Status.OFFLINE else Outcome.SENT
        request = self.store.add_request(
            channel=login, source=source, requested_by=requested_by, message=message,
            outcome=outcome.value, trn_status=status.value, now=now,
        )
        self.events.record(
            ev.DEMANDE_ENVOYEE if outcome is Outcome.SENT else ev.DEMANDE_SANS_TRN,
            channel=login, source=source, actor=requested_by, message=message,
            trn_status=status.value, detail=f"demande #{request.id}",
        )
        if self.notifier is not None:
            try:
                message_id = await self.notifier(request, outcome is Outcome.SENT)
                if message_id:
                    self.store.set_request_discord_message(request.id, message_id)
            except Exception:
                log.exception("Impossible de publier la demande #%s dans Discord", request.id)
        else:
            log.warning("Bot Discord inactif : la demande #%s n'est pas publiée", request.id)
        return RequestResult(outcome, login, status, request=request)

    def claim(self, request_id: int, trn: str) -> HelpRequest | None:
        request = self.store.claim_request(request_id, trn)
        if request is not None:
            self.events.record(
                ev.DEMANDE_PRISE_EN_CHARGE, channel=request.channel, source="discord",
                actor=trn, trn_status=self.store.current().status.value,
                detail=f"demande #{request.id}",
            )
        return request
