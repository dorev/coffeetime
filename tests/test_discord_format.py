from datetime import datetime, timezone

from acces_trn.config import load_config
from acces_trn.discord_bot import (
    ClaimButton, StatusButton, build_panel_view, build_request_embed, build_request_view, build_status_embed,
)
from acces_trn.store import Status

from .conftest import BASE_ENV

CONFIG = load_config(dict(BASE_ENV))


def test_request_embed_and_claim(store):
    req = store.add_request(channel="chaine", source="extension", requested_by="lea_mod", message="ça dérape",
                            outcome="envoyee", trn_status="available",
                            now=datetime(2026, 11, 6, 2, 41, tzinfo=timezone.utc))
    embed = build_request_embed(req, CONFIG)
    assert embed.title == "📣 Demande de la chaîne chaine"
    values = {f.name: f.value for f in embed.fields}
    assert values["Heure"] == "21 h 41"  # heure de Montréal
    assert values["Via"] == "extension Twitch · lea_mod" and values["Message"] == "ça dérape"
    assert [c.custom_id for c in build_request_view(req).children] == [f"demande:prendre:{req.id}"]
    claimed = store.claim_request(req.id, "Max")
    assert build_request_view(claimed).children == []
    assert "Pris en charge" in {f.name for f in build_request_embed(claimed, CONFIG).fields}


def test_no_trn_title(store):
    req = store.add_request(channel="chaine", source="chat", requested_by="m", message="",
                            outcome="sans_trn", trn_status="offline")
    assert "(aucun TRN en service)" in build_request_embed(req, CONFIG).title


def test_status_panel(store):
    store.set_status(Status.AVAILABLE, "Léa", "", 4)
    embed = build_status_embed(store, CONFIG)
    assert embed.title == "🟢 TRN disponible" and "Léa" in embed.description
    assert [c.custom_id for c in build_panel_view().children] == ["statut:available", "statut:busy", "statut:offline"]


def test_templates():
    assert StatusButton.__discord_ui_compiled_template__.fullmatch("statut:busy")
    assert ClaimButton.__discord_ui_compiled_template__.fullmatch("demande:prendre:12")["id"] == "12"
