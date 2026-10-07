from datetime import date, datetime, timedelta, timezone

from acces_trn.store import Status, clean_source

NOW = datetime(2026, 10, 7, 20, 0, tzinfo=timezone.utc)


def test_starts_offline(store):
    assert store.current().status is Status.OFFLINE


def test_available_expires_back_to_offline(store):
    store.set_status(Status.AVAILABLE, "Léa", "Jusqu'à 23 h", duration_hours=2, now=NOW)
    cur = store.current(NOW + timedelta(hours=1, minutes=59))
    assert cur.status is Status.AVAILABLE and cur.message == "Jusqu'à 23 h"
    cur = store.current(NOW + timedelta(hours=2))
    assert cur.status is Status.OFFLINE and cur.expired and cur.message == ""


def test_offline_never_expires(store):
    store.set_status(Status.OFFLINE, "Léa", duration_hours=1, now=NOW)
    cur = store.current(NOW + timedelta(days=3))
    assert cur.status is Status.OFFLINE and not cur.expired and cur.expires_at is None


def test_message_is_trimmed(store):
    cur = store.set_status(Status.BUSY, "Léa", "  " + "x" * 300, duration_hours=1)
    assert len(cur.message) == 200


def test_log_records_changes(store):
    store.set_status(Status.AVAILABLE, "A", duration_hours=1)
    store.set_status(Status.BUSY, "B", duration_hours=1)
    assert [(r["status"], r["set_by"]) for r in store.recent_changes()] == [("busy", "B"), ("available", "A")]


def test_counters_group_by_kind_and_source(store):
    today = date(2026, 10, 7)
    store.count("go", "ChaineA", day=today)
    store.count("go", "chainea", day=today)
    store.count("chat", None, day=today)
    store.count("go", "vieux", day=today - timedelta(days=40))
    rows = {(r["kind"], r["source"]): r["n"] for r in store.totals(30, today=today)}
    assert rows == {("go", "chainea"): 2, ("chat", "direct"): 1}


def test_clean_source():
    assert clean_source("Ma_Chaine-1") == "ma_chaine-1"
    assert clean_source(None) == "direct"
    assert clean_source("") == "direct"
    assert clean_source("<script>") == "autre"
    assert clean_source("x" * 41) == "autre"
