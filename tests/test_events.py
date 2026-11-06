import httpx

from acces_trn.events import EventLog

from .conftest import FakeSheets


async def test_flush_sends_batches_and_marks_synced(store):
    sheets = FakeSheets()
    log = EventLog(store, "https://script.google.com/macros/s/x/exec", "s3cret",
                   transport=httpx.MockTransport(sheets.handler))
    log.record("demande_envoyee", channel="chaine", source="chat", actor="mod1", message="hé", trn_status="available")
    log.record("statut_change", actor="Léa", trn_status="offline")
    assert await log.flush() == 2
    assert sheets.batches[0][0][1:6] == ["demande_envoyee", "chaine", "chat", "mod1", "hé"]
    assert store.unsynced_events() == []
    assert await log.flush() == 0


async def test_failure_keeps_events_for_retry(store):
    sheets = FakeSheets()
    sheets.fail = True
    log = EventLog(store, "https://sheets", "s3cret", transport=httpx.MockTransport(sheets.handler))
    log.record("demande_sans_trn", channel="chaine")
    try:
        await log.flush()
    except RuntimeError:
        pass
    assert len(store.unsynced_events()) == 1
    sheets.fail = False
    assert await log.flush() == 1


async def test_wrong_secret_is_an_error(store):
    sheets = FakeSheets()
    log = EventLog(store, "https://sheets", "mauvais", transport=httpx.MockTransport(sheets.handler))
    log.record("x")
    try:
        await log.flush()
        raise AssertionError("aurait dû échouer")
    except RuntimeError:
        assert len(store.unsynced_events()) == 1


async def test_no_webhook_keeps_local_copy(store):
    log = EventLog(store)
    log.record("statut_change")
    assert await log.flush() == 0 and len(store.recent_events()) == 1
