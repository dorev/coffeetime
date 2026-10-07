import pytest
from fastapi.testclient import TestClient

from acces_trn.app import create_app
from acces_trn.config import load_config
from acces_trn.store import Store

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


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


def make_client(env, store):
    app = create_app(load_config(dict(env)), store)
    # base_url https : les cookies « secure » doivent circuler pendant les tests
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


@pytest.fixture
def client(store):
    return make_client(BASE_ENV, store)


@pytest.fixture
def discord_client(store):
    return make_client(DISCORD_ENV, store)
