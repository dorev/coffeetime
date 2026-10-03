"""Chargement de la configuration depuis les variables d'environnement (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """Configuration manquante ou invalide."""


def _require(env: dict[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise ConfigError(f"Variable obligatoire manquante : {key}")
    return value


def _int(env: dict[str, str], key: str, default: int | None = None) -> int:
    raw = env.get(key, "").strip()
    if not raw:
        if default is None:
            raise ConfigError(f"Variable obligatoire manquante : {key}")
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} doit être un nombre entier (reçu : {raw!r})") from exc


def _bool(env: dict[str, str], key: str, default: bool) -> bool:
    raw = env.get(key, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "oui", "yes", "on"}


@dataclass(frozen=True)
class DiscordConfig:
    token: str
    guild_id: int
    reports_channel_id: int
    help_channel_id: int
    staff_role_id: int


@dataclass(frozen=True)
class TwitchConfig:
    client_id: str
    client_secret: str
    channels: tuple[str, ...]
    token_path: Path


@dataclass(frozen=True)
class Config:
    discord: DiscordConfig
    twitch: TwitchConfig | None
    database_path: Path
    public_help_url: str
    retention_days: int
    reports_per_hour: int
    log_level: str = "INFO"


def load_config(env: dict[str, str] | None = None) -> Config:
    """Construit la configuration. Sans `env`, lit le fichier .env puis os.environ."""
    if env is None:
        load_dotenv()
        env = dict(os.environ)

    discord = DiscordConfig(
        token=_require(env, "DISCORD_TOKEN"),
        guild_id=_int(env, "DISCORD_GUILD_ID"),
        reports_channel_id=_int(env, "DISCORD_REPORTS_CHANNEL_ID"),
        help_channel_id=_int(env, "DISCORD_HELP_CHANNEL_ID"),
        staff_role_id=_int(env, "DISCORD_STAFF_ROLE_ID"),
    )

    twitch: TwitchConfig | None = None
    if _bool(env, "TWITCH_ENABLED", default=False):
        channels = tuple(
            c.strip().lower().lstrip("#")
            for c in env.get("TWITCH_CHANNELS", "").split(",")
            if c.strip()
        )
        if not channels:
            raise ConfigError("TWITCH_CHANNELS doit contenir au moins une chaîne")
        twitch = TwitchConfig(
            client_id=_require(env, "TWITCH_CLIENT_ID"),
            client_secret=_require(env, "TWITCH_CLIENT_SECRET"),
            channels=channels,
            token_path=Path(env.get("TWITCH_TOKEN_PATH", "data/twitch_token.json")),
        )

    return Config(
        discord=discord,
        twitch=twitch,
        database_path=Path(env.get("DATABASE_PATH", "data/bot.sqlite3")),
        public_help_url=_require(env, "PUBLIC_HELP_URL"),
        retention_days=_int(env, "RETENTION_DAYS", default=90),
        reports_per_hour=_int(env, "REPORTS_PER_HOUR", default=5),
        log_level=env.get("LOG_LEVEL", "INFO").upper(),
    )
