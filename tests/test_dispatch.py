from datetime import datetime, timedelta, timezone

import pytest

from acces_trn.dispatch import Outcome, RequestService
from acces_trn.events import EventLog
from acces_trn.store import Status

NOW = datetime(2026, 11, 6, 2, 0, tzinfo=timezone.utc)


@pytest.fixture
def service(store):
    store.add_channel("chaine", "100", "Chaine", "test")
    svc = RequestService(store, EventLog(store), cooldown_minutes=10)
    svc.notified = []

    async def notifier(request, mention):
        svc.notified.append((request.id, mention))
        return "discord-msg-1"

    svc.notifier = notifier
    return svc


def types(store):
    return [e["type"] for e in reversed(store.recent_events(50))]


async def test_sent_when_trn_available(service, store):
    store.set_status(Status.AVAILABLE, "Léa", "", 2, now=NOW)
    res = await service.submit("Chaine", source="chat", requested_by="mod1", message="  ça   dérape ", now=NOW)
    assert res.outcome is Outcome.SENT
    assert res.request.message == "ça dérape" and res.request.channel == "chaine"
    assert service.notified == [(res.request.id, True)]
    assert store.get_request(res.request.id).discord_message_id == "discord-msg-1"
    assert types(store)[-1] == "demande_envoyee"


async def test_no_trn_is_logged_and_posted_without_mention(service, store):
    res = await service.submit("chaine", source="page", requested_by="mod1", now=NOW)
    assert res.outcome is Outcome.NO_TRN
    assert service.notified == [(res.request.id, False)]
    assert types(store)[-1] == "demande_sans_trn"


async def test_cooldown_ten_minutes_and_logged(service, store):
    await service.submit("chaine", source="chat", requested_by="mod1", now=NOW)
    res = await service.submit("chaine", source="page", requested_by="mod2", message="encore",
                               now=NOW + timedelta(minutes=3))
    assert res.outcome is Outcome.COOLDOWN and res.retry_after_minutes == 7
    assert len(service.notified) == 1                         # pas republié dans Discord
    assert types(store)[-1] == "demande_bloquee_delai"
    # les demandes bloquées ne prolongent pas le délai
    res = await service.submit("chaine", source="chat", requested_by="mod1", now=NOW + timedelta(minutes=10))
    assert res.outcome is Outcome.NO_TRN


async def test_unknown_channel(service, store):
    res = await service.submit("inconnue", source="chat", requested_by="x", now=NOW)
    assert res.outcome is Outcome.UNKNOWN_CHANNEL and service.notified == []
    assert types(store)[-1] == "demande_refusee"


async def test_notifier_failure_does_not_lose_request(service, store):
    async def broken(request, mention):
        raise RuntimeError("Discord en panne")

    service.notifier = broken
    res = await service.submit("chaine", source="chat", requested_by="m", now=NOW)
    assert res.outcome is Outcome.NO_TRN and store.get_request(res.request.id) is not None


async def test_claim_once(service, store):
    res = await service.submit("chaine", source="chat", requested_by="m", now=NOW)
    assert service.claim(res.request.id, "Léa").claimed_by == "Léa"
    assert service.claim(res.request.id, "Max") is None
    assert types(store)[-1] == "demande_prise_en_charge"
