"""Stockage SQLite des signalements et demandes d'aide.

Volontairement synchrone : les requêtes sont minuscules et locales, elles ne
bloquent pas la boucle asyncio de façon perceptible pour un MVP.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at         TEXT NOT NULL,
    source             TEXT NOT NULL CHECK (source IN ('discord', 'twitch')),
    kind               TEXT NOT NULL CHECK (kind IN ('report', 'help')),
    reporter           TEXT,            -- NULL si anonyme
    target             TEXT,            -- personne concernée (facultatif)
    location           TEXT,            -- salon Discord, chaîne Twitch, etc.
    description        TEXT NOT NULL,
    evidence           TEXT,            -- lien, extrait de message
    status             TEXT NOT NULL DEFAULT 'open'
                       CHECK (status IN ('open', 'claimed', 'closed')),
    claimed_by         TEXT,
    closed_at          TEXT,
    staff_message_id   INTEGER          -- message dans #signalements
);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports (status);
"""


class Source(str, Enum):
    DISCORD = "discord"
    TWITCH = "twitch"


class Kind(str, Enum):
    REPORT = "report"
    HELP = "help"


class Status(str, Enum):
    OPEN = "open"
    CLAIMED = "claimed"
    CLOSED = "closed"


@dataclass(frozen=True)
class Report:
    id: int
    created_at: datetime
    source: Source
    kind: Kind
    reporter: str | None
    target: str | None
    location: str | None
    description: str
    evidence: str | None
    status: Status
    claimed_by: str | None
    closed_at: datetime | None
    staff_message_id: int | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_report(row: sqlite3.Row) -> Report:
    return Report(
        id=row["id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        source=Source(row["source"]),
        kind=Kind(row["kind"]),
        reporter=row["reporter"],
        target=row["target"],
        location=row["location"],
        description=row["description"],
        evidence=row["evidence"],
        status=Status(row["status"]),
        claimed_by=row["claimed_by"],
        closed_at=datetime.fromisoformat(row["closed_at"]) if row["closed_at"] else None,
        staff_message_id=row["staff_message_id"],
    )


class ReportStore:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def create(
        self,
        *,
        source: Source,
        kind: Kind,
        description: str,
        reporter: str | None = None,
        target: str | None = None,
        location: str | None = None,
        evidence: str | None = None,
        now: datetime | None = None,
    ) -> Report:
        with self._conn:
            cur = self._conn.execute(
                """INSERT INTO reports
                   (created_at, source, kind, reporter, target, location, description, evidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    (now or _now()).isoformat(),
                    source.value,
                    kind.value,
                    reporter,
                    target,
                    location,
                    description,
                    evidence,
                ),
            )
        report = self.get(cur.lastrowid)
        assert report is not None
        return report

    def get(self, report_id: int) -> Report | None:
        row = self._conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        return _row_to_report(row) if row else None

    def set_staff_message(self, report_id: int, message_id: int) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE reports SET staff_message_id = ? WHERE id = ?", (message_id, report_id)
            )

    def set_location(self, report_id: int, location: str, evidence: str | None) -> Report:
        with self._conn:
            self._conn.execute(
                "UPDATE reports SET location = ?, evidence = ? WHERE id = ?",
                (location, evidence, report_id),
            )
        report = self.get(report_id)
        assert report is not None
        return report

    def claim(self, report_id: int, staff: str) -> Report | None:
        """Prise en charge. Échoue (None) si déjà pris par quelqu'un d'autre ou fermé."""
        with self._conn:
            cur = self._conn.execute(
                """UPDATE reports SET status = 'claimed', claimed_by = ?
                   WHERE id = ? AND status = 'open'""",
                (staff, report_id),
            )
        return self.get(report_id) if cur.rowcount else None

    def close_report(self, report_id: int, staff: str, now: datetime | None = None) -> Report | None:
        """Fermeture. Échoue (None) si déjà fermé."""
        with self._conn:
            cur = self._conn.execute(
                """UPDATE reports
                   SET status = 'closed', closed_at = ?, claimed_by = COALESCE(claimed_by, ?)
                   WHERE id = ? AND status != 'closed'""",
                ((now or _now()).isoformat(), staff, report_id),
            )
        return self.get(report_id) if cur.rowcount else None

    def list_open(self) -> list[Report]:
        rows = self._conn.execute(
            "SELECT * FROM reports WHERE status != 'closed' ORDER BY id"
        ).fetchall()
        return [_row_to_report(r) for r in rows]

    def purge_closed(self, retention_days: int, now: datetime | None = None) -> int:
        """Supprime les dossiers fermés depuis plus de `retention_days` jours (Loi 25)."""
        cutoff = ((now or _now()) - timedelta(days=retention_days)).isoformat()
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM reports WHERE status = 'closed' AND closed_at < ?", (cutoff,)
            )
        return cur.rowcount

    def stats(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT kind, status, COUNT(*) AS n FROM reports GROUP BY kind, status"
        ).fetchall()
        return {f"{r['kind']}:{r['status']}": r["n"] for r in rows}
