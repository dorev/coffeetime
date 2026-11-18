"""Configuration lue depuis les variables d'environnement (fichier .env).

Les intégrations sont facultatives : chacune s'active quand ses variables sont remplies.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import find_dotenv, load_dotenv


class ConfigError(Exception):
    """Configuration manquante ou invalide."""


AUTH_MODES = ("discord", "password")


@dataclass(frozen=True)
class Config:
    base_url: str
    destination_url: str
    secret_key: str
    auth_mode: str
    admin_password: str | None
    # Discord : connexion à /admin (OAuth) et bot des TRN
    discord_client_id: str | None
    discord_client_secret: str | None
    discord_guild_id: str | None
    discord_role_id: str | None
    discord_bot_token: str | None
    discord_requests_channel_id: str | None
    # Twitch : bot de chat (commande !trn) et recherche des chaînes
    twitch_client_id: str | None
    twitch_client_secret: str | None
    bot_setup_key: str | None
    # Extension Twitch
    extension_client_id: str | None
    extension_secret: str | None
    # Google Sheets (webhook Apps Script)
    sheets_webhook_url: str | None
    sheets_webhook_secret: str | None
    # Règles
    request_cooldown_minutes: int
    default_duration_hours: int
    # Contenu
    org_name: str
    hours_text: str
    timezone: ZoneInfo
    database_path: Path
    secure_cookies: bool

    @property
    def discord_redirect_uri(self) -> str:
        return f"{self.base_url}/admin/callback"

    @property
    def twitch_redirect_uri(self) -> str:
        return f"{self.base_url}/auth/twitch/callback"

    @property
    def discord_bot_enabled(self) -> bool:
        return bool(self.discord_bot_token)

    @property
    def twitch_enabled(self) -> bool:
        return bool(self.twitch_client_id and self.twitch_client_secret)

    @property
    def extension_enabled(self) -> bool:
        return bool(self.extension_client_id and self.extension_secret)

    @property
    def sheets_enabled(self) -> bool:
        return bool(self.sheets_webhook_url)


def _get(env: dict[str, str], key: str, default: str | None = None) -> str | None:
    value = env.get(key, "").strip()
    return value or default


def _require(env: dict[str, str], key: str) -> str:
    value = _get(env, key)
    if value is None:
        raise ConfigError(f"Variable obligatoire manquante : {key}")
    return value


def _int(env: dict[str, str], key: str, default: int, low: int, high: int) -> int:
    raw = _get(env, key, str(default)) or str(default)
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} doit être un nombre entier") from exc
    if not low <= value <= high:
        raise ConfigError(f"{key} doit être entre {low} et {high}")
    return value


def _all_or_none(env: dict[str, str], keys: tuple[str, ...], what: str) -> None:
    filled = [k for k in keys if _get(env, k)]
    if filled and len(filled) != len(keys):
        missing = ", ".join(k for k in keys if k not in filled)
        raise ConfigError(f"{what} : variable(s) manquante(s) : {missing}")


def load_config(env: dict[str, str] | None = None) -> Config:
    """Construit la configuration. Sans `env`, lit le fichier .env puis os.environ."""
    if env is None:
        load_dotenv(find_dotenv(usecwd=True))  # le .env du dossier courant
        env = dict(os.environ)

    base_url = _require(env, "BASE_URL").rstrip("/")
    secret_key = _require(env, "SECRET_KEY")
    if len(secret_key) < 32:
        raise ConfigError("SECRET_KEY doit contenir au moins 32 caractères aléatoires")

    auth_mode = (_get(env, "AUTH_MODE", "discord") or "").lower()
    if auth_mode not in AUTH_MODES:
        raise ConfigError(f"AUTH_MODE doit valoir {' ou '.join(AUTH_MODES)}")

    admin_password = _get(env, "ADMIN_PASSWORD")
    if auth_mode == "discord":
        for key in ("DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "DISCORD_GUILD_ID", "DISCORD_ROLE_ID"):
            _require(env, key)
    elif admin_password is None or len(admin_password) < 12:
        raise ConfigError("ADMIN_PASSWORD (12 caractères minimum) est requis en mode password")

    if _get(env, "DISCORD_BOT_TOKEN"):
        for key in ("DISCORD_GUILD_ID", "DISCORD_ROLE_ID", "DISCORD_REQUESTS_CHANNEL_ID"):
            _require(env, key)
    _all_or_none(env, ("TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"), "Twitch")
    _all_or_none(env, ("EXTENSION_CLIENT_ID", "EXTENSION_SECRET"), "Extension Twitch")
    if _get(env, "EXTENSION_CLIENT_ID") and not _get(env, "TWITCH_CLIENT_ID"):
        raise ConfigError("L'extension Twitch nécessite aussi TWITCH_CLIENT_ID et TWITCH_CLIENT_SECRET")
    bot_setup_key = _get(env, "BOT_SETUP_KEY")
    if bot_setup_key and len(bot_setup_key) < 16:
        raise ConfigError("BOT_SETUP_KEY doit contenir au moins 16 caractères")

    tz_name = _get(env, "TIMEZONE", "America/Toronto") or "America/Toronto"
    try:
        timezone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"Fuseau horaire inconnu : {tz_name}") from exc

    return Config(
        base_url=base_url,
        destination_url=_require(env, "DESTINATION_URL"),
        secret_key=secret_key,
        auth_mode=auth_mode,
        admin_password=admin_password,
        discord_client_id=_get(env, "DISCORD_CLIENT_ID"),
        discord_client_secret=_get(env, "DISCORD_CLIENT_SECRET"),
        discord_guild_id=_get(env, "DISCORD_GUILD_ID"),
        discord_role_id=_get(env, "DISCORD_ROLE_ID"),
        discord_bot_token=_get(env, "DISCORD_BOT_TOKEN"),
        discord_requests_channel_id=_get(env, "DISCORD_REQUESTS_CHANNEL_ID"),
        twitch_client_id=_get(env, "TWITCH_CLIENT_ID"),
        twitch_client_secret=_get(env, "TWITCH_CLIENT_SECRET"),
        bot_setup_key=bot_setup_key,
        extension_client_id=_get(env, "EXTENSION_CLIENT_ID"),
        extension_secret=_get(env, "EXTENSION_SECRET"),
        sheets_webhook_url=_get(env, "SHEETS_WEBHOOK_URL"),
        sheets_webhook_secret=_get(env, "SHEETS_WEBHOOK_SECRET"),
        request_cooldown_minutes=_int(env, "REQUEST_COOLDOWN_MINUTES", 10, 1, 240),
        default_duration_hours=_int(env, "DEFAULT_DURATION_HOURS", 4, 1, 24),
        org_name=_get(env, "ORG_NAME", "Fondation des Gardiens virtuels") or "",
        hours_text=_get(env, "HOURS_TEXT", "") or "",
        timezone=timezone,
        database_path=Path(_get(env, "DATABASE_PATH", "data/acces_trn.sqlite3") or ""),
        secure_cookies=base_url.startswith("https://"),
    )
