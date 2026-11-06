"""Journal d'événements : copie locale (SQLite) + envoi au Google Sheets de la FGV.

Chaque événement est d'abord écrit dans SQLite, puis envoyé par lots au webhook
Apps Script. Si le Google Sheets est injoignable, les événements restent en attente
et sont renvoyés plus tard : rien n'est perdu.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from .store import Store

log = logging.getLogger(__name__)

# Types d'événements (lisibles directement dans la feuille)
STATUT_CHANGE = "statut_change"
DEMANDE_ENVOYEE = "demande_envoyee"
DEMANDE_SANS_TRN = "demande_sans_trn"
DEMANDE_BLOQUEE_DELAI = "demande_bloquee_delai"
DEMANDE_REFUSEE = "demande_refusee"            # pas mod, chaîne inconnue…
DEMANDE_PRISE_EN_CHARGE = "demande_prise_en_charge"
CHUCHOTEMENT_ECHOUE = "chuchotement_echoue"
SUPPRESSION_ECHOUEE = "suppression_message_echouee"
CHAINE_AJOUTEE = "chaine_ajoutee"
CHAINE_RETIREE = "chaine_retiree"
BOT_TWITCH_AUTORISE = "bot_twitch_autorise"

COLUMNS = ("at", "type", "channel", "source", "actor", "message", "trn_status", "detail")


class EventLog:
    def __init__(
        self,
        store: Store,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_seconds: float = 60,
    ) -> None:
        self.store = store
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret or ""
        self._transport = transport
        self._retry_seconds = retry_seconds
        self._wakeup: asyncio.Event | None = None
        self._task: asyncio.Task | None = None

    def record(
        self,
        type: str,
        *,
        channel: str = "",
        source: str = "",
        actor: str = "",
        message: str = "",
        trn_status: str = "",
        detail: str = "",
    ) -> None:
        event = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "type": type,
            "channel": channel,
            "source": source,
            "actor": actor,
            "message": message,
            "trn_status": trn_status,
            "detail": detail,
        }
        self.store.add_event(event)
        log.info("Événement %s %s", type, channel)
        if self._wakeup is not None:
            self._wakeup.set()

    # --- Synchronisation avec Google Sheets --------------------------------------

    def start(self) -> None:
        if self.webhook_url and self._task is None:
            self._wakeup = asyncio.Event()
            self._task = asyncio.create_task(self._run(), name="sheets-sync")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        assert self._wakeup is not None
        while True:
            try:
                await self.flush()
            except Exception:
                log.exception("Envoi au Google Sheets impossible ; nouvel essai plus tard")
            try:
                await asyncio.wait_for(self._wakeup.wait(), timeout=self._retry_seconds)
            except asyncio.TimeoutError:
                pass
            self._wakeup.clear()

    async def flush(self) -> int:
        """Envoie les événements en attente. Retourne le nombre envoyé."""
        if not self.webhook_url:
            return 0
        sent = 0
        async with httpx.AsyncClient(
            timeout=15, follow_redirects=True, transport=self._transport
        ) as client:
            while batch := self.store.unsynced_events():
                rows = [[e[c] for c in COLUMNS] for e in batch]
                resp = await client.post(
                    self.webhook_url, json={"secret": self.webhook_secret, "rows": rows}
                )
                if resp.status_code != 200 or '"ok":true' not in resp.text.replace(" ", ""):
                    raise RuntimeError(f"Réponse du Google Sheets : {resp.status_code} {resp.text[:200]}")
                self.store.mark_events_synced([e["id"] for e in batch])
                sent += len(batch)
        return sent
