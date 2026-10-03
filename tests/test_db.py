from datetime import datetime, timedelta, timezone

import pytest

from bot_aide.db import Kind, ReportStore, Source, Status


@pytest.fixture
def store():
    s = ReportStore(":memory:")
    yield s
    s.close()


def _report(store, **kw):
    defaults = dict(source=Source.DISCORD, kind=Kind.REPORT, description="propos haineux")
    return store.create(**(defaults | kw))


def test_create_and_get(store):
    r = _report(store, reporter="alice", target="bob", evidence="https://x")
    assert r.id == 1
    assert r.status is Status.OPEN
    assert store.get(r.id) == r


def test_anonymous_report_keeps_no_reporter(store):
    assert _report(store, reporter=None).reporter is None


def test_claim_only_once(store):
    r = _report(store)
    claimed = store.claim(r.id, "intervenant1")
    assert claimed.status is Status.CLAIMED and claimed.claimed_by == "intervenant1"
    assert store.claim(r.id, "intervenant2") is None


def test_close_from_open_records_staff(store):
    r = _report(store)
    closed = store.close_report(r.id, "intervenant1")
    assert closed.status is Status.CLOSED
    assert closed.claimed_by == "intervenant1"
    assert closed.closed_at is not None
    assert store.close_report(r.id, "intervenant1") is None
    assert store.claim(r.id, "x") is None


def test_close_keeps_original_claimer(store):
    r = _report(store)
    store.claim(r.id, "a")
    assert store.close_report(r.id, "b").claimed_by == "a"


def test_set_location(store):
    r = _report(store, kind=Kind.HELP)
    updated = store.set_location(r.id, "Fil privé", "https://discord.com/x")
    assert (updated.location, updated.evidence) == ("Fil privé", "https://discord.com/x")


def test_purge_only_old_closed(store):
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    old = _report(store)
    recent = _report(store)
    still_open = _report(store)
    store.close_report(old.id, "a", now=now - timedelta(days=100))
    store.close_report(recent.id, "a", now=now - timedelta(days=10))
    assert store.purge_closed(90, now=now) == 1
    assert store.get(old.id) is None
    assert store.get(recent.id) is not None
    assert store.get(still_open.id) is not None


def test_list_open_and_stats(store):
    a = _report(store)
    _report(store, kind=Kind.HELP)
    store.close_report(a.id, "x")
    assert [r.kind for r in store.list_open()] == [Kind.HELP]
    assert store.stats() == {"help:open": 1, "report:closed": 1}


def test_file_database_creates_parent_dir(tmp_path):
    path = tmp_path / "sub" / "bot.sqlite3"
    s = ReportStore(path)
    _report(s)
    s.close()
    assert ReportStore(path).get(1) is not None
