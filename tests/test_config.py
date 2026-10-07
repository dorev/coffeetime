import pytest

from acces_trn.config import ConfigError, load_config

from .conftest import BASE_ENV, DISCORD_ENV


def test_password_mode():
    cfg = load_config(dict(BASE_ENV))
    assert cfg.base_url == "https://aide.example.org"
    assert cfg.secure_cookies
    assert cfg.default_duration_hours == 4


def test_discord_mode_redirect_uri():
    assert load_config(dict(DISCORD_ENV)).discord_redirect_uri == "https://aide.example.org/admin/callback"


@pytest.mark.parametrize(
    "env",
    [
        {k: v for k, v in BASE_ENV.items() if k != "DESTINATION_URL"},
        BASE_ENV | {"SECRET_KEY": "court"},
        BASE_ENV | {"ADMIN_PASSWORD": "court"},
        BASE_ENV | {"AUTH_MODE": "magie"},
        BASE_ENV | {"DEFAULT_DURATION_HOURS": "48"},
        BASE_ENV | {"TIMEZONE": "Mars/Olympus"},
        {k: v for k, v in DISCORD_ENV.items() if k != "DISCORD_ROLE_ID"},
    ],
)
def test_invalid(env):
    with pytest.raises(ConfigError):
        load_config(env)
