import re

import pytest

from acces_trn.auth import AuthError, PasswordLogin, member_to_user
from acces_trn.store import Status


def csrf_from(html):
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def login(client, password="motdepasse-tres-long", name="Léa"):
    page = client.get("/admin/login")
    return client.post(
        "/admin/login", data={"password": password, "name": name, "csrf": csrf_from(page.text)}
    )


def test_admin_requires_login(client):
    r = client.get("/admin")
    assert r.status_code == 303 and r.headers["location"] == "/admin/login"
    assert client.post("/admin/status", data={"status": "available"}).status_code == 303


def test_wrong_password(client):
    r = login(client, password="mauvais")
    assert r.status_code == 401 and "Mot de passe incorrect" in r.text


def test_set_status_flow(client, store):
    assert login(client).status_code == 303
    page = client.get("/admin")
    assert page.status_code == 200 and page.headers["cache-control"] == "no-store"
    r = client.post(
        "/admin/status",
        data={"status": "available", "message": "Jusqu'à 23 h", "duration": "2", "csrf": csrf_from(page.text)},
    )
    assert r.status_code == 303
    cur = store.current()
    assert cur.status is Status.AVAILABLE and cur.set_by == "Léa" and cur.message == "Jusqu'à 23 h"
    assert "Léa" in client.get("/admin").text


def test_csrf_required(client, store):
    login(client)
    r = client.post("/admin/status", data={"status": "available", "csrf": "faux"})
    assert r.status_code == 400 and store.current().status is Status.OFFLINE


def test_unknown_status_and_duration(client, store):
    login(client)
    csrf = csrf_from(client.get("/admin").text)
    assert client.post("/admin/status", data={"status": "party", "csrf": csrf}).status_code == 400
    client.post("/admin/status", data={"status": "busy", "duration": "999", "csrf": csrf})
    cur = store.current()
    assert (cur.expires_at - cur.set_at).total_seconds() == 4 * 3600


def test_logout(client):
    login(client)
    csrf = csrf_from(client.get("/admin").text)
    client.post("/admin/logout", data={"csrf": csrf})
    assert client.get("/admin").status_code == 303


def test_password_lockout():
    clock = [0.0]
    pw = PasswordLogin("bon-mot-de-passe", clock=lambda: clock[0])
    for _ in range(5):
        with pytest.raises(AuthError):
            pw.check("x", "a")
    with pytest.raises(AuthError, match="Trop d'essais"):
        pw.check("bon-mot-de-passe", "a")
    clock[0] = 301
    assert pw.check("bon-mot-de-passe", " Léa ").name == "Léa"


# --- Discord ------------------------------------------------------------------


def test_member_to_user():
    member = {"nick": None, "roles": ["222"], "user": {"id": "9", "username": "lea", "global_name": "Léa"}}
    assert member_to_user(member, "222").name == "Léa"
    with pytest.raises(AuthError, match="rôle TRN"):
        member_to_user(member | {"roles": []}, "222")


def test_discord_login_flow(discord_client, monkeypatch):
    app = discord_client.app
    r = discord_client.get("/admin/login?go=1")
    assert r.status_code == 303
    location = r.headers["location"]
    assert location.startswith("https://discord.com/oauth2/authorize?")
    assert "guilds.members.read" in location
    state = re.search(r"state=([^&]+)", location).group(1)

    async def fake_login(code):
        assert code == "abc"
        return member_to_user({"roles": ["222"], "user": {"id": "9", "username": "lea"}}, "222")

    monkeypatch.setattr(app.state.discord, "login", fake_login)
    assert discord_client.get("/admin/callback?code=abc&state=wrong").status_code == 400
    # l'état est à usage unique : on recommence
    state = re.search(r"state=([^&]+)", discord_client.get("/admin/login?go=1").headers["location"]).group(1)
    r = discord_client.get(f"/admin/callback?code=abc&state={state}")
    assert r.status_code == 303 and r.headers["location"] == "/admin"
    assert "Espace TRN · lea" in discord_client.get("/admin").text


def test_discord_login_rejected(discord_client, monkeypatch):
    async def fake_login(code):
        raise AuthError("Ton compte n'a pas le rôle TRN.")

    monkeypatch.setattr(discord_client.app.state.discord, "login", fake_login)
    loc = discord_client.get("/admin/login?go=1").headers["location"]
    state = re.search(r"state=([^&]+)", loc).group(1)
    r = discord_client.get(f"/admin/callback?code=abc&state={state}")
    assert r.status_code == 403 and "rôle TRN" in r.text
    assert discord_client.get("/admin").status_code == 303
