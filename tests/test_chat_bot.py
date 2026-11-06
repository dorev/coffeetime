import pytest

from acces_trn.dispatch import RequestService
from acces_trn.events import EventLog
from acces_trn.store import Status
from acces_trn.twitch_bot import ChatCommandHandler, ChatMessage, parse_command


class FakeActions:
    def __init__(self, whisper_error=None, delete_error=None):
        self.deleted, self.whispers = [], []
        self.whisper_error, self.delete_error = whisper_error, delete_error

    async def delete(self, broadcaster_id, message_id):
        if self.delete_error:
            raise self.delete_error
        self.deleted.append((broadcaster_id, message_id))

    async def whisper(self, to_user_id, text):
        if self.whisper_error:
            raise self.whisper_error
        self.whispers.append((to_user_id, text))


def msg(text, chatter="mod1", badges=("moderator",), chatter_id=None):
    return ChatMessage("m-1", "100", "chaine", chatter_id or f"id-{chatter}", chatter, text, frozenset(badges))


@pytest.fixture
def setup(store):
    store.add_channel("chaine", "100", "Chaine", "test")
    service = RequestService(store, EventLog(store), 10)
    return store, service


def event_types(store):
    return [e["type"] for e in reversed(store.recent_events(50))]


def test_parse_command():
    assert parse_command("!TRN ça dérape") == ("trn", "ça dérape")
    assert parse_command("salut !trn") is None


async def test_mod_command_deletes_and_whispers_only(setup):
    store, service = setup
    store.set_status(Status.AVAILABLE, "Léa", "", 2)
    actions = FakeActions()
    await ChatCommandHandler(service, service.events, actions, "bot").handle(msg("!trn un viewer va mal"))
    assert actions.deleted == [("100", "m-1")]
    assert actions.whispers[0][0] == "id-mod1" and actions.whispers[0][1].startswith("✅")
    req = store.last_counted_request("chaine")
    assert (req.source, req.requested_by, req.message) == ("chat", "mod1", "un viewer va mal")


async def test_broadcaster_can_use_it(setup):
    store, service = setup
    actions = FakeActions()
    await ChatCommandHandler(service, service.events, actions, "bot").handle(
        msg("!trn", chatter="chaine", badges=(), chatter_id="100"))
    assert actions.whispers and "Aucun·e TRN" in actions.whispers[0][1]


async def test_viewers_are_ignored(setup):
    store, service = setup
    actions = FakeActions()
    await ChatCommandHandler(service, service.events, actions, "bot").handle(msg("!trn", chatter="v", badges=("subscriber",)))
    assert actions.deleted == [] and actions.whispers == [] and store.recent_events() == []


async def test_whisper_failure_is_logged_without_public_reply(setup):
    store, service = setup
    actions = FakeActions(whisper_error=RuntimeError("429 quota"))
    await ChatCommandHandler(service, service.events, actions, "bot").handle(msg("!trn"))
    assert event_types(store)[-2:] == ["demande_sans_trn", "chuchotement_echoue"]
    assert "quota" in store.recent_events(1)[0]["detail"]


async def test_delete_failure_is_logged_but_request_still_sent(setup):
    store, service = setup
    actions = FakeActions(delete_error=RuntimeError("bot pas mod"))
    await ChatCommandHandler(service, service.events, actions, "bot").handle(msg("!trn"))
    assert event_types(store)[0] == "suppression_message_echouee"
    assert store.last_counted_request("chaine") is not None and actions.whispers


async def test_cooldown_whisper(setup):
    store, service = setup
    actions = FakeActions()
    handler = ChatCommandHandler(service, service.events, actions, "bot")
    await handler.handle(msg("!trn"))
    await handler.handle(msg("!trn encore"))
    assert "Attends 10 minutes" in actions.whispers[-1][1]
