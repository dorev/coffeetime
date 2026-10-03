from bot_aide.db import Kind, ReportStore, Source
from bot_aide.discord_bot import ReportActionButton, build_report_embed, build_staff_view


def test_embed_and_buttons_follow_status():
    store = ReportStore(":memory:")
    r = store.create(source=Source.TWITCH, kind=Kind.REPORT, description="x" * 5000)
    embed = build_report_embed(r)
    assert embed.title == "Signalement #1 · Twitch"
    assert len(embed.description) <= 4000
    assert embed.fields[1].value == "Anonyme"
    ids = [c.custom_id for c in build_staff_view(r).children]
    assert ids == ["report:claim:1", "report:close:1"]

    claimed = store.claim(r.id, "Léa")
    assert [c.custom_id for c in build_staff_view(claimed).children] == ["report:close:1"]
    closed = store.close_report(r.id, "Léa")
    assert build_staff_view(closed).children == []
    assert any(f.value == "Léa" for f in build_report_embed(closed).fields)


def test_button_template_matches_custom_id():
    pattern = ReportActionButton.__discord_ui_compiled_template__
    m = pattern.fullmatch("report:close:42")
    assert m["action"] == "close" and m["id"] == "42"
    assert pattern.fullmatch("report:delete:42") is None
