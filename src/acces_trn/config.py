"""Configuration lue depuis les variables d'environnement (fichier .env)."""

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
    discord_client_id: str | None
    discord_client_secret: str | None
    discord_guild_id: str | None
    discord_role_id: str | None
    default_duration_hours: int
    org_name: str
    hours_text: str
    timezone: ZoneInfo
    database_path: Path
    secure_cookies: bool

    @property
    def discord_redirect_uri(self) -> str:
        return f"{self.base_url}/admin/callback"


def _get(env: dict[str, str], key: str, default: str | None = None) -> str | None:
    value = env.get(key, "").strip()
    return value or default


def _require(env: dict[str, str], key: str) -> str:
    value = _get(env, key)
    if value is None:
        raise ConfigError(f"Variable obligatoire manquante : {key}")
    return value


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
    discord_keys = ("DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "DISCORD_GUILD_ID", "DISCORD_ROLE_ID")
    if auth_mode == "discord":
        for key in discord_keys:
            _require(env, key)
    elif admin_password is None or len(admin_password) < 12:
        raise ConfigError("ADMIN_PASSWORD (12 caractères minimum) est requis en mode password")

    try:
        duration = int(_get(env, "DEFAULT_DURATION_HOURS", "4") or "4")
    except ValueError as exc:
        raise ConfigError("DEFAULT_DURATION_HOURS doit être un nombre entier") from exc
    if not 1 <= duration <= 24:
        raise ConfigError("DEFAULT_DURATION_HOURS doit être entre 1 et 24")

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
        default_duration_hours=duration,
        org_name=_get(env, "ORG_NAME", "Fondation des Gardiens virtuels") or "",
        hours_text=_get(env, "HOURS_TEXT", "") or "",
        timezone=timezone,
        database_path=Path(_get(env, "DATABASE_PATH", "data/acces_trn.sqlite3") or ""),
        secure_cookies=base_url.startswith("https://"),
    )
