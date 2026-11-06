import base64
import json
import time
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from acces_trn.app import create_app
from acces_trn.config import load_config
from acces_trn.store import Store
from acces_trn.twitch_api import TwitchClient

EXT_SECRET = base64.b64encode(b"secret-extension-de-test-assez-long-32").decode()

BASE_ENV = {
    "BASE_URL": "https://aide.example.org/",
    "DESTINATION_URL": "https://discord.gg/trn-test",
    "SECRET_KEY": "x" * 40,
    "AUTH_MODE": "password",
    "ADMIN_PASSWORD": "motdepasse-tres-long",
    "HOURS_TEXT": "lun-ven, 18 h à 23 h",
}

DISCORD_ENV = BASE_ENV | {
    "AUTH_MODE": "discord",
    "DISCORD_CLIENT_ID": "cid",
    "DISCORD_CLIENT_SECRET": "csecret",
    "DISCORD_GUILD_ID": "111",
    "DISCORD_ROLE_ID": "222",
}

TWITCH_ENV = BASE_ENV | {
    "TWITCH_CLIENT_ID": "tw-id",
    "TWITCH_CLIENT_SECRET": "tw-secret",
    "BOT_SETUP_KEY": "cle-installation-bot-123",
    "EXTENSION_CLIENT_ID": "extid",
    "EXTENSION_SECRET": EXT_SECRET,
}


class FakeTwitch:
    """Simule id.twitch.tv et l'API Helix (httpx.MockTransport)."""

    def __init__(self):
        self.users = {"100": ("100", "chaine", "Chaine"), "7": ("7", "lea_mod", "Léa_Mod"),
                      "8": ("8", "viewer", "Viewer")}
        self.code_user = {"code-lea": "7", "code-viewer": "8", "code-bot": "9"}
        self.users["9"] = ("9", "trn_bot", "TRN_Bot")
        self.moderated = {"7": {"100"}}
        self.tokens = {}          # access token -> user id
        self.refresh_tokens = {}  # refresh token -> user id
        self.revoked = set()      # user ids dont les jetons sont révoqués
        self.calls = []
        self.n = 0

    def _issue(self, uid):
        self.n += 1
        access, refresh = f"acc-{uid}-{self.n}", f"ref-{uid}-{self.n}"
        self.tokens[access] = uid
        self.refresh_tokens[refresh] = uid
        return {"access_token": access, "refresh_token": refresh, "expires_in": 14000}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        if request.url.path == "/oauth2/token":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            grant = form["grant_type"]
            if grant == "client_credentials":
                return httpx.Response(200, json={"access_token": "app-token", "expires_in": 5000000})
            if grant == "authorization_code":
                uid = self.code_user.get(form["code"])
                return httpx.Response(200, json=self._issue(uid)) if uid else httpx.Response(400, text="bad code")
            uid = self.refresh_tokens.pop(form.get("refresh_token"), None)
            if uid is None or uid in self.revoked:
                return httpx.Response(400, text="invalid refresh")
            return httpx.Response(200, json=self._issue(uid))
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        params = dict(request.url.params)
        if request.url.path == "/helix/users":
            if token == "app-token":
                key = params.get("id") or next((u for u, v in self.users.items() if v[1] == params.get("login")), None)
                found = [self.users[key]] if key in self.users else []
            elif token in self.tokens and self.tokens[token] not in self.revoked:
                found = [self.users[self.tokens[token]]]
            else:
                return httpx.Response(401)
            return httpx.Response(200, json={"data": [{"id": u[0], "login": u[1], "display_name": u[2]} for u in found]})
        if request.url.path == "/helix/moderation/channels":
            uid = self.tokens.get(token)
            if uid is None or uid in self.revoked:
                return httpx.Response(401)
            assert params["user_id"] == uid
            return httpx.Response(200, json={"data": [{"broadcaster_id": b} for b in self.moderated.get(uid, set())],
                                             "pagination": {}})
        return httpx.Response(404)


class FakeSheets:
    def __init__(self):
        self.batches = []
        self.fail = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            return httpx.Response(500, text="boom")
        body = json.loads(request.content)
        if body["secret"] != "s3cret":
            return httpx.Response(200, json={"ok": False})
        self.batches.append(body["rows"])
        return httpx.Response(200, json={"ok": True, "added": len(body["rows"])})


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


def make_client(env, store, **kwargs):
    app = create_app(load_config(dict(env)), store, start_bots=False, **kwargs)
    # base_url https : les cookies « secure » doivent circuler pendant les tests
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


@pytest.fixture
def client(store):
    return make_client(BASE_ENV, store)


@pytest.fixture
def discord_client(store):
    return make_client(DISCORD_ENV, store)


@pytest.fixture
def fake_twitch():
    return FakeTwitch()


@pytest.fixture
def twitch_client(store, fake_twitch):
    tw = TwitchClient("tw-id", "tw-secret", transport=httpx.MockTransport(fake_twitch.handler))
    store.add_channel("chaine", "100", "Chaine", "test")
    return make_client(TWITCH_ENV, store, twitch=tw)


def ext_token(role="moderator", channel_id="100", user_id=None, exp_in=300):
    import jwt

    payload = {"exp": int(time.time()) + exp_in, "channel_id": channel_id, "role": role,
               "opaque_user_id": "U123"}
    if user_id:
        payload["user_id"] = user_id
    return jwt.encode(payload, base64.b64decode(EXT_SECRET), algorithm="HS256")
