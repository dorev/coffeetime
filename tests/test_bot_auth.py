from urllib.parse import parse_qs, urlparse

from acces_trn.twitch_api import Tokens


def test_bot_authorization(twitch_client, monkeypatch):
    assert twitch_client.get("/bot/autoriser?cle=mauvaise").status_code == 404
    r = twitch_client.get("/bot/autoriser?cle=cle-installation-bot-123")
    url = urlparse(r.headers["location"])
    q = parse_qs(url.query)
    assert url.netloc == "id.twitch.tv" and q["force_verify"] == ["true"]
    assert q["redirect_uri"] == ["https://aide.example.org/auth/twitch/callback"]
    assert "user:manage:whispers" in q["scope"][0] and "moderator:manage:chat_messages" in q["scope"][0]
    seen = {}

    async def fake_authorize(tokens, login):
        seen["login"] = login

    monkeypatch.setattr(twitch_client.app.state.chat_bot, "authorize", fake_authorize)
    assert twitch_client.get("/auth/twitch/callback?code=code-bot&state=faux").status_code == 400
    r = twitch_client.get("/bot/autoriser?cle=cle-installation-bot-123")
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    r = twitch_client.get(f"/auth/twitch/callback?code=code-bot&state={state}")
    assert r.status_code == 200 and "Bot Twitch autorisé" in r.text and seen["login"] == "trn_bot"


def test_bot_setup_disabled_without_key(store):
    from .conftest import TWITCH_ENV, make_client

    env = {k: v for k, v in TWITCH_ENV.items() if k != "BOT_SETUP_KEY"}
    assert make_client(env, store).get("/bot/autoriser?cle=").status_code == 404


def test_removed_mod_page_routes(twitch_client):
    assert twitch_client.get("/c/chaine").status_code == 404
    assert twitch_client.get("/auth/twitch/login?chaine=chaine").status_code == 404


def test_bot_tokens_are_encrypted_at_rest(twitch_client, store):
    twitch_client.app.state.chat_bot.save_tokens(Tokens("acc-secret", "ref-secret", 0))
    raw = store.get_secret("twitch_bot_tokens")
    assert "secret" not in raw
    assert twitch_client.app.state.chat_bot._load_tokens()["refresh"] == "ref-secret"
