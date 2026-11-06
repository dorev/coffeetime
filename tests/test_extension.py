from acces_trn.store import Status

from .conftest import ext_token

ORIGIN = "https://extid.ext-twitch.tv"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_preflight_cors(twitch_client):
    r = twitch_client.options("/ext/demande")
    assert r.status_code == 204 and r.headers["access-control-allow-origin"] == ORIGIN
    assert "Authorization" in r.headers["access-control-allow-headers"]


def test_info_by_role(twitch_client, store):
    store.set_status(Status.AVAILABLE, "TRN", "", 2)
    viewer = twitch_client.get("/ext/info", headers=auth(ext_token("viewer"))).json()
    assert viewer["status"] == "available" and viewer["can_request"] is False and viewer["registered"]
    mod = twitch_client.get("/ext/info", headers=auth(ext_token("moderator"))).json()
    assert mod["can_request"] is True
    other = twitch_client.get("/ext/info", headers=auth(ext_token("moderator", channel_id="999"))).json()
    assert other["registered"] is False and other["can_request"] is False


def test_invalid_or_expired_token(twitch_client):
    assert twitch_client.get("/ext/info", headers=auth("abc")).status_code == 401
    assert twitch_client.get("/ext/info", headers=auth(ext_token(exp_in=-10))).status_code == 401
    assert twitch_client.get("/ext/info").status_code == 401


def test_mod_request_with_shared_identity(twitch_client, store):
    r = twitch_client.post("/ext/demande", headers=auth(ext_token("moderator", user_id="7")),
                           json={"message": "ça chauffe"})
    assert r.status_code == 200 and r.json()["outcome"] == "sans_trn"
    assert r.headers["access-control-allow-origin"] == ORIGIN
    req = store.last_counted_request("chaine")
    assert (req.source, req.requested_by, req.message) == ("extension", "lea_mod", "ça chauffe")


def test_mod_without_shared_identity_and_broadcaster(twitch_client, store):
    twitch_client.post("/ext/demande", headers=auth(ext_token("moderator")), json={})
    assert store.last_counted_request("chaine").requested_by == "mod (identité non partagée)"
    r = twitch_client.post("/ext/demande", headers=auth(ext_token("broadcaster")), json={})
    assert r.json()["outcome"] == "delai" and "Attends" in r.json()["text"]


def test_viewer_cannot_request(twitch_client, store):
    r = twitch_client.post("/ext/demande", headers=auth(ext_token("viewer")), json={})
    assert r.status_code == 403 and store.last_counted_request("chaine") is None
    assert store.recent_events(1)[0]["type"] == "demande_refusee"


def test_extension_disabled(client):
    assert client.get("/ext/info", headers=auth(ext_token())).status_code == 404
