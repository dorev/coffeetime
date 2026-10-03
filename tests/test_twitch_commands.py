import pytest

from bot_aide.db import Kind, ReportStore, Source
from bot_aide.ratelimit import RateLimiter
from bot_aide.twitch_bot import ChatMessage, TwitchCommandHandler, parse_command, split_target


def msg(text, chatter="viewer", badges=()):
    return ChatMessage(
        message_id="m1",
        broadcaster_id="100",
        channel_login="chaine",
        chatter_id=f"id-{chatter}",
        chatter_login=chatter,
        text=text,
        badges=frozenset(badges),
    )


@pytest.fixture
def env():
    sent, notified = [], []

    async def send(broadcaster_id, text, reply_to):
        sent.append((broadcaster_id, text, reply_to))

    async def notify(report):
        notified.append(report)

    store = ReportStore(":memory:")
    handler = TwitchCommandHandler(
        store, RateLimiter(2), send, notify, "https://discord.gg/abc", bot_user_id="id-bot"
    )
    yield handler, store, sent, notified
    store.close()


def test_parse_command():
    assert parse_command("!Signaler @bob raison") == ("signaler", "@bob raison")
    assert parse_command("  !aide ") == ("aide", "")
    assert parse_command("salut !aide") is None
    assert parse_command("!") is None


def test_split_target():
    assert split_target("@Bob propos haineux") == ("bob", "propos haineux")
    assert split_target("propos haineux") == (None, "propos haineux")
    assert split_target("@ seul") == (None, "@ seul")


async def test_help_replies_with_link_and_notifies(env):
    handler, store, sent, notified = env
    await handler.handle(msg("!aide"))
    assert len(sent) == 1
    assert "https://discord.gg/abc" in sent[0][1] and "988" in sent[0][1]
    assert sent[0][2] == "m1"
    assert notified[0].kind is Kind.HELP and notified[0].source is Source.TWITCH


async def test_report_creates_dossier(env):
    handler, store, sent, notified = env
    await handler.handle(msg("!signaler @Troll insultes répétées", chatter="mod1", badges={"moderator"}))
    report = notified[0]
    assert report.target == "troll"
    assert report.description == "insultes répétées"
    assert report.reporter == "mod1 (modérateur)"
    assert report.location == "twitch.tv/chaine"
    assert f"#{report.id}" in sent[0][1]


async def test_report_without_args_shows_usage_only(env):
    handler, store, sent, notified = env
    await handler.handle(msg("!signaler"))
    assert "Utilisation" in sent[0][1]
    assert notified == [] and store.list_open() == []


async def test_rate_limit(env):
    handler, store, sent, notified = env
    for _ in range(3):
        await handler.handle(msg("!signaler spam"))
    assert len(notified) == 2
    assert "Réessaie plus tard" in sent[-1][1]


async def test_ignores_own_messages_and_chatter(env):
    handler, store, sent, notified = env
    await handler.handle(msg("!aide", chatter="bot"))
    await handler.handle(msg("bonjour"))
    await handler.handle(msg("!inconnu"))
    assert sent == [] and notified == []
