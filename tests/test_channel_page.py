import re
from urllib.parse import parse_qs, urlparse

from acces_trn.store import Status


def csrf_from(html):
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def login_as(client, code):
    r = client.get("/auth/twitch/login?chaine=chaine")
    assert r.status_code == 303
    url = urlparse(r.headers["location"])
    assert url.netloc == "id.twitch.tv"
    q = parse_qs(url.query)
    assert q["scope"] == ["user:read:moderated_channels"]
    assert q["redirect_uri"] == ["https://aide.example.org/auth/twitch/callback"]
    return client.get(f"/auth/twitch/callback?code={code}&state={q['state'][0]}")


def test_unknown_channel_shows_info_only(twitch_client):
    html = twitch_client.get("/c/inconnue").text
    assert "pas encore inscrite" in html and "Se connecter avec Twitch" not in html


def test_anonymous_sees_info_and_login_button(twitch_client):
    html = twitch_client.get("/c/chaine").text
    assert "Travailleuses et travailleurs de rue numériques" in html
    assert "Se connecter avec Twitch" in html and "Demander un·e TRN" not in html


def test_mod_flow_end_to_end(twitch_client, store):
    r = login_as(twitch_client, "code-lea")
    assert r.status_code == 303 and r.headers["location"] == "/c/chaine"
    cookie = r.headers["set-cookie"]
    assert "trn_mod=" in cookie and "HttpOnly" in cookie and "Max-Age=2592000" in cookie
    assert "acc-7" not in cookie  # jeton chiffré, pas lisible
    page = twitch_client.get("/c/chaine")
    assert "Connecté·e en tant que <strong>Léa_Mod</strong>" in page.text
    store.set_status(Status.AVAILABLE, "TRN", "", 2)
    r = twitch_client.post("/c/chaine/demande", data={"csrf": csrf_from(page.text), "message": "un viewer va mal"})
    assert r.status_code == 200 and "✅ Demande transmise" in r.text
    req = store.last_counted_request("chaine")
    assert (req.source, req.requested_by, req.message) == ("page", "lea_mod", "un viewer va mal")
    r = twitch_client.post("/c/chaine/demande", data={"csrf": csrf_from(page.text)})
    assert "Attends 10 minutes" in r.text


def test_mod_status_rechecked_on_each_request(twitch_client, fake_twitch, store):
    login_as(twitch_client, "code-lea")
    page = twitch_client.get("/c/chaine")
    fake_twitch.moderated["7"] = set()          # Léa n'est plus mod
    r = twitch_client.post("/c/chaine/demande", data={"csrf": csrf_from(page.text)})
    assert r.status_code == 403 and "Seuls le streamer et les mods" in r.text
    assert store.last_counted_request("chaine") is None
    assert store.recent_events(1)[0]["type"] == "demande_refusee"


def test_revoked_twitch_access_requires_new_login(twitch_client, fake_twitch):
    login_as(twitch_client, "code-lea")
    fake_twitch.revoked.add("7")
    html = twitch_client.get("/c/chaine").text
    assert "Ta connexion a expiré" in html and "Se connecter avec Twitch" in html


def test_viewer_cannot_request(twitch_client):
    login_as(twitch_client, "code-viewer")
    page = twitch_client.get("/c/chaine")
    assert "pas modérateur·rice" in page.text
    r = twitch_client.post("/c/chaine/demande", data={"csrf": csrf_from(page.text)})
    assert r.status_code == 403


def test_csrf_and_state_checks(twitch_client):
    login_as(twitch_client, "code-lea")
    assert twitch_client.post("/c/chaine/demande", data={"csrf": "faux"}).status_code == 400
    assert twitch_client.get("/auth/twitch/callback?code=code-lea&state=faux").status_code == 400


def test_logout(twitch_client):
    login_as(twitch_client, "code-lea")
    page = twitch_client.get("/c/chaine")
    r = twitch_client.post("/auth/twitch/logout", data={"csrf": csrf_from(page.text), "chaine": "chaine"})
    assert r.status_code == 303 and 'trn_mod=""' in r.headers["set-cookie"]


def test_expired_access_token_is_refreshed(twitch_client, fake_twitch):
    from acces_trn.twitch_api import Tokens, TwitchUser

    modauth = twitch_client.app.state.modauth
    fake_twitch.refresh_tokens["ref-old"] = "7"
    cookie = modauth.make_cookie(TwitchUser("7", "lea_mod", "Léa_Mod"), Tokens("acc-dead", "ref-old", 0))
    twitch_client.cookies.set("trn_mod", cookie)
    r = twitch_client.get("/c/chaine")
    assert "Connecté·e en tant que" in r.text and "trn_mod=" in r.headers.get("set-cookie", "")


def test_bot_authorization(twitch_client, monkeypatch):
    assert twitch_client.get("/bot/autoriser?cle=mauvaise").status_code == 404
    r = twitch_client.get("/bot/autoriser?cle=cle-installation-bot-123")
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["force_verify"] == ["true"]
    assert "user:manage:whispers" in q["scope"][0] and "moderator:manage:chat_messages" in q["scope"][0]
    seen = {}

    async def fake_authorize(tokens, login):
        seen["login"] = login

    monkeypatch.setattr(twitch_client.app.state.chat_bot, "authorize", fake_authorize)
    r = twitch_client.get(f"/auth/twitch/callback?code=code-bot&state={q['state'][0]}")
    assert r.status_code == 200 and "Bot Twitch autorisé" in r.text and seen["login"] == "trn_bot"


def test_bot_tokens_are_encrypted_at_rest(twitch_client, store):
    from acces_trn.twitch_api import Tokens

    twitch_client.app.state.chat_bot.save_tokens(Tokens("acc-secret", "ref-secret", 0))
    raw = store.get_secret("twitch_bot_tokens")
    assert "secret" not in raw
    assert twitch_client.app.state.chat_bot._load_tokens()["refresh"] == "ref-secret"
