from pathlib import Path

import pytest

from bot_aide.config import ConfigError, load_config

BASE = {
    "DISCORD_TOKEN": "tok",
    "DISCORD_GUILD_ID": "1",
    "DISCORD_REPORTS_CHANNEL_ID": "2",
    "DISCORD_HELP_CHANNEL_ID": "3",
    "DISCORD_STAFF_ROLE_ID": "4",
    "PUBLIC_HELP_URL": "https://discord.gg/abc",
}


def test_minimal_config_without_twitch():
    cfg = load_config(dict(BASE))
    assert cfg.twitch is None
    assert cfg.discord.reports_channel_id == 2
    assert cfg.retention_days == 90
    assert cfg.database_path == Path("data/bot.sqlite3")


def test_twitch_channels_are_normalized():
    env = BASE | {
        "TWITCH_ENABLED": "oui",
        "TWITCH_CLIENT_ID": "id",
        "TWITCH_CLIENT_SECRET": "secret",
        "TWITCH_CHANNELS": " #ChaineA, chaineb ,",
    }
    assert load_config(env).twitch.channels == ("chainea", "chaineb")


@pytest.mark.parametrize(
    "env",
    [
        {k: v for k, v in BASE.items() if k != "DISCORD_TOKEN"},
        BASE | {"DISCORD_GUILD_ID": "abc"},
        BASE | {"TWITCH_ENABLED": "true", "TWITCH_CLIENT_ID": "x", "TWITCH_CLIENT_SECRET": "y"},
    ],
)
def test_invalid_config(env):
    with pytest.raises(ConfigError):
        load_config(env)
