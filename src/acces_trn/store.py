"""Stockage SQLite : statut courant, journal des changements, compteurs anonymes.

Aucune donnée sur les personnes qui demandent de l'aide n'est enregistrée :
ni adresse IP, ni navigateur, ni identifiant. Seuls des compteurs par jour.
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
