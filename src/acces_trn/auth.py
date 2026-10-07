"""Authentification du côté privé (TRN).

Deux modes :
- `discord` (recommandé) : « Se connecter avec Discord ». Seules les personnes
  ayant le rôle TRN dans le serveur Discord de la FGV peuvent entrer. Aucun mot
  de passe à gérer ; retirer le rôle retire l'accès.
- `password` : un mot de passe partagé, pratique pour les essais locaux.
"""

from __future__ import annotations

import hmac
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from .config import Config

DISCORD_API = "https://discord.com/api/v10"
DISCORD_AUTHORIZE = "https://discord.com/oauth2/authorize"
SCOPES = "identify guilds.members.read"


class AuthError(Exception):
    """Connexion refusée ; le message est affichable."""


@dataclass(frozen=True)
class StaffUser:
    id: str
    name: str


class DiscordOAuth:
    def __init__(self, config: Config) -> None:
        self.config = config

    def authorize_url(self, state: str) -> str:
        params = {
            "client_id": self.config.discord_client_id,
            "redirect_uri": self.config.discord_redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
            "prompt": "none",
        }
        return f"{DISCORD_AUTHORIZE}?{urlencode(params)}"

    async def login(self, code: str) -> StaffUser:
        """Échange le code contre un jeton, puis vérifie le rôle TRN. Le jeton n'est pas conservé."""
        cfg = self.config
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                f"{DISCORD_API}/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": cfg.discord_redirect_uri,
                },
                auth=(cfg.discord_client_id or "", cfg.discord_client_secret or ""),
            )
            if token_resp.status_code != 200:
                raise AuthError("Discord a refusé la connexion. Réessaie.")
            token = token_resp.json()["access_token"]
            member_resp = await client.get(
                f"{DISCORD_API}/users/@me/guilds/{cfg.discord_guild_id}/member",
                headers={"Authorization": f"Bearer {token}"},
            )
        if member_resp.status_code == 404:
            raise AuthError("Ton compte Discord n'est pas membre du serveur des TRN.")
        if member_resp.status_code != 200:
            raise AuthError("Impossible de vérifier ton rôle sur Discord. Réessaie.")
        return member_to_user(member_resp.json(), cfg.discord_role_id or "")


def member_to_user(member: dict, role_id: str) -> StaffUser:
    if role_id not in member.get("roles", []):
        raise AuthError("Ton compte n'a pas le rôle TRN.")
    user = member.get("user", {})
    name = member.get("nick") or user.get("global_name") or user.get("username") or "TRN"
    return StaffUser(id=str(user.get("id", "")), name=name)


class PasswordLogin:
    """Mot de passe partagé, avec blocage temporaire après plusieurs échecs."""

    MAX_FAILURES = 5
    LOCKOUT_SECONDS = 300

    def __init__(self, password: str, clock=time.monotonic) -> None:
        self._password = password.encode()
        self._clock = clock
        self._failures: list[float] = []

    def check(self, password: str, name: str) -> StaffUser:
        now = self._clock()
        self._failures = [t for t in self._failures if now - t < self.LOCKOUT_SECONDS]
        if len(self._failures) >= self.MAX_FAILURES:
            raise AuthError("Trop d'essais. Réessaie dans quelques minutes.")
        if not hmac.compare_digest(password.encode(), self._password):
            self._failures.append(now)
            raise AuthError("Mot de passe incorrect.")
        name = name.strip()[:40] or "TRN"
        return StaffUser(id=f"pw:{name}", name=name)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def tokens_match(expected: str | None, received: str | None) -> bool:
    return bool(expected and received) and hmac.compare_digest(expected, received)
