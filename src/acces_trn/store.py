"""Stockage SQLite : statut, chaînes inscrites, demandes, journal d'événements, compteurs.

Aucune donnée sur les viewers n'est enregistrée (ni IP, ni navigateur, ni identifiant).
Une demande contient seulement : chaîne, heure, source, pseudo du mod, message facultatif.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS state (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    status      TEXT NOT NULL,
    message     TEXT NOT NULL DEFAULT '',
    set_by      TEXT NOT NULL DEFAULT '',
    set_at      TEXT NOT NULL,
    expires_at  TEXT
);
CREATE TABLE IF NOT EXISTS status_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    at      TEXT NOT NULL,
    status  TEXT NOT NULL,
    set_by  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS channels (
    login         TEXT PRIMARY KEY,
    twitch_id     TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    added_by      TEXT NOT NULL,
    added_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at          TEXT NOT NULL,
    channel             TEXT NOT NULL,
    source              TEXT NOT NULL,     -- chat, page, extension
    requested_by        TEXT NOT NULL,
    message             TEXT NOT NULL DEFAULT '',
    outcome             TEXT NOT NULL,     -- envoyee, sans_trn, delai
    trn_status          TEXT NOT NULL,
    claimed_by          TEXT,
    claimed_at          TEXT,
    discord_message_id  TEXT
);
CREATE INDEX IF NOT EXISTS idx_requests_channel ON requests (channel, created_at);
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL,
    type        TEXT NOT NULL,
    channel     TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT '',
    actor       TEXT NOT NULL DEFAULT '',
    message     TEXT NOT NULL DEFAULT '',
    trn_status  TEXT NOT NULL DEFAULT '',
    detail      TEXT NOT NULL DEFAULT '',
    synced      INTEGER NOT NULL DEFAULT 0   -- envoyé au Google Sheets
);
CREATE INDEX IF NOT EXISTS idx_events_synced ON events (synced, id);
CREATE TABLE IF NOT EXISTS secrets (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL                     -- chiffré par l'application
);
CREATE TABLE IF NOT EXISTS counters (
    day     TEXT NOT NULL,
    kind    TEXT NOT NULL,
    source  TEXT NOT NULL,
    n       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, kind, source)
);
"""

LOG_KEEP = 200
_SOURCE_RE = re.compile(r"^[a-z0-9_-]{1,40}$")


class Status(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


@dataclass(frozen=True)
class Channel:
    login: str
    twitch_id: str
    display_name: str


@dataclass(frozen=True)
class HelpRequest:
    id: int
    created_at: datetime
    channel: str
    source: str
    requested_by: str
    message: str
    outcome: str
    trn_status: str
    claimed_by: str | None
    claimed_at: datetime | None
    discord_message_id: str | None


def _request_from_row(row: sqlite3.Row) -> HelpRequest:
    return HelpRequest(
        id=row["id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        channel=row["channel"],
        source=row["source"],
        requested_by=row["requested_by"],
        message=row["message"],
        outcome=row["outcome"],
        trn_status=row["trn_status"],
        claimed_by=row["claimed_by"],
        claimed_at=datetime.fromisoformat(row["claimed_at"]) if row["claimed_at"] else None,
        discord_message_id=row["discord_message_id"],
    )


@dataclass(frozen=True)
class CurrentStatus:
    status: Status
    message: str
    set_by: str
    set_at: datetime
    expires_at: datetime | None
    expired: bool  # True si un statut « en service » est arrivé à échéance


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def clean_source(raw: str | None) -> str:
    """Normalise l'identifiant de provenance (?src=) pour les statistiques."""
    value = (raw or "").strip().lower()
    return value if _SOURCE_RE.fullmatch(value) else "direct" if not value else "autre"


class Store:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(SCHEMA)
            self._conn.execute(
                "INSERT OR IGNORE INTO state (id, status, set_at) VALUES (1, ?, ?)",
                (Status.OFFLINE.value, _utcnow().isoformat()),
            )

    def close(self) -> None:
        self._conn.close()

    # --- Statut --------------------------------------------------------------

    def current(self, now: datetime | None = None) -> CurrentStatus:
        now = now or _utcnow()
        with self._lock:
            row = self._conn.execute("SELECT * FROM state WHERE id = 1").fetchone()
        status = Status(row["status"])
        expires_at = datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
        expired = status is not Status.OFFLINE and expires_at is not None and now >= expires_at
        return CurrentStatus(
            status=Status.OFFLINE if expired else status,
            message="" if expired else row["message"],
            set_by=row["set_by"],
            set_at=datetime.fromisoformat(row["set_at"]),
            expires_at=expires_at,
            expired=expired,
        )

    def set_status(
        self,
        status: Status,
        set_by: str,
        message: str = "",
        duration_hours: int | None = None,
        now: datetime | None = None,
    ) -> CurrentStatus:
        """Change le statut. « Disponible » et « Occupé » expirent après `duration_hours`."""
        now = now or _utcnow()
        expires_at = None
        if status is not Status.OFFLINE and duration_hours:
            expires_at = (now + timedelta(hours=duration_hours)).isoformat()
        with self._lock, self._conn:
            self._conn.execute(
                """UPDATE state SET status = ?, message = ?, set_by = ?, set_at = ?, expires_at = ?
                   WHERE id = 1""",
                (status.value, message.strip()[:200], set_by, now.isoformat(), expires_at),
            )
            self._conn.execute(
                "INSERT INTO status_log (at, status, set_by) VALUES (?, ?, ?)",
                (now.isoformat(), status.value, set_by),
            )
            self._conn.execute(
                "DELETE FROM status_log WHERE id NOT IN "
                "(SELECT id FROM status_log ORDER BY id DESC LIMIT ?)",
                (LOG_KEEP,),
            )
        return self.current(now)

    def recent_changes(self, limit: int = 20) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT at, status, set_by FROM status_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()

    # --- Chaînes inscrites -----------------------------------------------------

    def add_channel(self, login: str, twitch_id: str, display_name: str, added_by: str) -> Channel:
        login = login.lower()
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO channels (login, twitch_id, display_name, added_by, added_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT (login) DO UPDATE SET twitch_id = excluded.twitch_id,
                       display_name = excluded.display_name""",
                (login, twitch_id, display_name, added_by, _utcnow().isoformat()),
            )
        return Channel(login, twitch_id, display_name)

    def remove_channel(self, login: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute("DELETE FROM channels WHERE login = ?", (login.lower(),))
        return cur.rowcount > 0

    def get_channel(self, login: str) -> Channel | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT login, twitch_id, display_name FROM channels WHERE login = ?", (login.lower(),)
            ).fetchone()
        return Channel(*row) if row else None

    def get_channel_by_id(self, twitch_id: str) -> Channel | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT login, twitch_id, display_name FROM channels WHERE twitch_id = ?", (twitch_id,)
            ).fetchone()
        return Channel(*row) if row else None

    def list_channels(self) -> list[Channel]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT login, twitch_id, display_name FROM channels ORDER BY login"
            ).fetchall()
        return [Channel(*r) for r in rows]

    # --- Demandes des chaînes ----------------------------------------------------

    def last_counted_request(self, channel: str) -> HelpRequest | None:
        """Dernière demande qui compte pour le délai (les demandes bloquées ne comptent pas)."""
        with self._lock:
            row = self._conn.execute(
                """SELECT * FROM requests WHERE channel = ? AND outcome != 'delai'
                   ORDER BY id DESC LIMIT 1""",
                (channel.lower(),),
            ).fetchone()
        return _request_from_row(row) if row else None

    def add_request(
        self,
        *,
        channel: str,
        source: str,
        requested_by: str,
        message: str,
        outcome: str,
        trn_status: str,
        now: datetime | None = None,
    ) -> HelpRequest:
        with self._lock, self._conn:
            cur = self._conn.execute(
                """INSERT INTO requests
                   (created_at, channel, source, requested_by, message, outcome, trn_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ((now or _utcnow()).isoformat(), channel.lower(), source, requested_by,
                 message, outcome, trn_status),
            )
        request = self.get_request(cur.lastrowid)
        assert request is not None
        return request

    def get_request(self, request_id: int) -> HelpRequest | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
        return _request_from_row(row) if row else None

    def set_request_discord_message(self, request_id: int, message_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE requests SET discord_message_id = ? WHERE id = ?", (message_id, request_id)
            )

    def claim_request(self, request_id: int, trn: str, now: datetime | None = None) -> HelpRequest | None:
        """Prise en charge ; None si déjà prise."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                """UPDATE requests SET claimed_by = ?, claimed_at = ?
                   WHERE id = ? AND claimed_by IS NULL""",
                (trn, (now or _utcnow()).isoformat(), request_id),
            )
        return self.get_request(request_id) if cur.rowcount else None

    # --- Journal d'événements (copie locale de ce qui va au Google Sheets) -----

    def add_event(self, event: dict) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                """INSERT INTO events (at, type, channel, source, actor, message, trn_status, detail)
                   VALUES (:at, :type, :channel, :source, :actor, :message, :trn_status, :detail)""",
                event,
            )
        return cur.lastrowid

    def unsynced_events(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE synced = 0 ORDER BY id LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_events_synced(self, ids: list[int]) -> None:
        if not ids:
            return
        with self._lock, self._conn:
            self._conn.executemany("UPDATE events SET synced = 1 WHERE id = ?", [(i,) for i in ids])

    def recent_events(self, limit: int = 20) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()

    # --- Secrets (jetons chiffrés) ------------------------------------------------

    def set_secret(self, key: str, value: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO secrets (key, value) VALUES (?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_secret(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM secrets WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    # --- Compteurs anonymes ---------------------------------------------------

    def count(self, kind: str, source: str | None, day: date | None = None) -> None:
        day = day or _utcnow().date()
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO counters (day, kind, source, n) VALUES (?, ?, ?, 1)
                   ON CONFLICT (day, kind, source) DO UPDATE SET n = n + 1""",
                (day.isoformat(), kind, clean_source(source)),
            )

    def totals(self, days: int = 30, today: date | None = None) -> list[sqlite3.Row]:
        """Totaux par type et provenance sur les `days` derniers jours."""
        since = ((today or _utcnow().date()) - timedelta(days=days - 1)).isoformat()
        with self._lock:
            return self._conn.execute(
                """SELECT kind, source, SUM(n) AS n FROM counters
                   WHERE day >= ? GROUP BY kind, source ORDER BY n DESC""",
                (since,),
            ).fetchall()
