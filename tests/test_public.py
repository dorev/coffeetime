from acces_trn.store import Status


def test_index_offline_shows_resources_first(client, store):
    r = client.get("/?src=chaineA")
    assert r.status_code == 200
    html = r.text
    assert "TRN hors ligne" in html
    assert html.index("Besoin d'aide immédiate") < html.index("C'est quoi")
    assert 'href="/go?src=chainea"' in html
    assert "lun-ven, 18 h à 23 h" in html
    assert {(row["kind"], row["source"]) for row in store.totals()} == {("page", "chainea")}


def test_index_available(client, store):
    store.set_status(Status.AVAILABLE, "Léa", "Jusqu'à 23 h", 2)
    html = client.get("/").text
    assert "Un·e TRN est disponible maintenant" in html
    assert "Jusqu&#39;à 23 h" in html
    assert html.index("C'est quoi") < html.index("Besoin d'aide immédiate")


def test_go_redirects_and_counts(client, store):
    r = client.get("/go?src=chaine")
    assert r.status_code == 302
    assert r.headers["location"] == "https://discord.gg/trn-test"
    assert [tuple(row) for row in store.totals()] == [("go", "chaine", 1)]


def test_status_json(client, store):
    store.set_status(Status.BUSY, "Léa", "", 2)
    r = client.get("/status.json")
    assert r.headers["access-control-allow-origin"] == "*"
    data = r.json()
    assert data["status"] == "busy" and data["label"] == "Équipe occupée"
    assert data["url"] == "https://aide.example.org"


def test_status_txt_for_chatbots(client, store):
    r = client.get("/status.txt?src=chaine")
    assert r.headers["content-type"].startswith("text/plain")
    assert "988" in r.text and "https://aide.example.org/?src=chaine" in r.text
    assert len(r.text) <= 400
    store.set_status(Status.AVAILABLE, "Léa", "", 2)
    assert client.get("/status.txt").text.startswith("🟢")
    assert {row["kind"] for row in store.totals()} == {"chat"}


def test_widget_badge_qr(client):
    assert "TRN hors ligne" in client.get("/widget?theme=overlay").text
    badge = client.get("/badge.svg")
    assert badge.headers["content-type"] == "image/svg+xml" and "hors ligne" in badge.text
    assert client.get("/qr.svg?src=chaine").text.startswith("<svg")


def test_embedding_rules(client):
    assert "frame-ancestors *" in client.get("/widget").headers["content-security-policy"]
    assert "frame-ancestors none" in client.get("/").headers["content-security-policy"]
    assert client.get("/").headers["referrer-policy"] == "no-referrer"


def test_trousse_uses_base_url_and_source(client):
    html = client.get("/trousse?src=MaChaine").text
    assert "$(urlfetch https://aide.example.org/status.txt?src=machaine)" in html
    assert "${customapi.https://aide.example.org/status.txt?src=machaine}" in html


def test_no_personal_data_stored(client, store):
    client.get("/go?src=x", headers={"user-agent": "secret-ua", "x-forwarded-for": "1.2.3.4"})
    dump = "\n".join(store._conn.iterdump())
    assert "1.2.3.4" not in dump and "secret-ua" not in dump
