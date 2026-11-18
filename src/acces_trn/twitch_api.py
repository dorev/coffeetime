"""Petit client de l'API Twitch (httpx) pour le côté Web :
autorisation du compte bot, recherche de chaînes et de pseudos.
Le bot de chat utilise la librairie twitchAPI (voir twitch_bot.py).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

AUTH_BASE = "https://id.twitch.tv/oauth2"
HELIX = "https://api.twitch.tv/helix"

BOT_SCOPES = (
    "user:read:chat",                    # lire le chat (EventSub)
    "user:bot",                          # agir comme bot de chat
    "user:manage:whispers",              # chuchoter la réponse au mod
    "moderator:manage:chat_messages",    # effacer la commande !trn
)


class TwitchError(Exception):
    """Erreur de l'API Twitch."""


class TwitchAuthError(TwitchError):
    """Jeton invalide, expiré ou révoqué : il faut se reconnecter."""


@dataclass(frozen=True)
class Tokens:
    access_token: str
    refresh_token: str
    expires_at: float  # horodatage Unix

    @classmethod
    def from_response(cls, data: dict, now: float | None = None) -> "Tokens":
        now = now or time.time()
        return cls(data["access_token"], data["refresh_token"], now + int(data.get("expires_in", 3600)))

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at - 60


@dataclass(frozen=True)
class TwitchUser:
    id: str
    login: str
    display_name: str


class TwitchClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._transport = transport
        self._app_token: str | None = None
        self._app_token_expires = 0.0

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=10, transport=self._transport)

    def authorize_url(
        self, redirect_uri: str, scopes: tuple[str, ...], state: str, force_verify: bool = False
    ) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
        }
        if force_verify:
            params["force_verify"] = "true"
        return f"{AUTH_BASE}/authorize?{urlencode(params)}"

    async def _token_request(self, data: dict) -> Tokens:
        async with self._client() as client:
            resp = await client.post(
                f"{AUTH_BASE}/token",
                data={"client_id": self.client_id, "client_secret": self.client_secret, **data},
            )
        if resp.status_code in (400, 401):
            raise TwitchAuthError(resp.text[:200])
        if resp.status_code != 200:
            raise TwitchError(f"{resp.status_code} {resp.text[:200]}")
        return Tokens.from_response(resp.json())

    async def exchange_code(self, code: str, redirect_uri: str) -> Tokens:
        return await self._token_request(
            {"code": code, "grant_type": "authorization_code", "redirect_uri": redirect_uri}
        )

    async def refresh(self, refresh_token: str) -> Tokens:
        return await self._token_request({"grant_type": "refresh_token", "refresh_token": refresh_token})

    async def _helix(self, path: str, token: str, params: dict | None = None) -> dict:
        async with self._client() as client:
            resp = await client.get(
                f"{HELIX}{path}",
                params=params,
                headers={"Authorization": f"Bearer {token}", "Client-Id": self.client_id},
            )
        if resp.status_code == 401:
            raise TwitchAuthError(resp.text[:200])
        if resp.status_code != 200:
            raise TwitchError(f"{resp.status_code} {resp.text[:200]}")
        return resp.json()

    async def get_me(self, access_token: str) -> TwitchUser:
        data = (await self._helix("/users", access_token))["data"]
        if not data:
            raise TwitchError("Utilisateur introuvable")
        u = data[0]
        return TwitchUser(u["id"], u["login"], u["display_name"])

    async def _get_app_token(self) -> str:
        if self._app_token and time.time() < self._app_token_expires - 60:
            return self._app_token
        async with self._client() as client:
            resp = await client.post(
                f"{AUTH_BASE}/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            )
        if resp.status_code != 200:
            raise TwitchError(f"Jeton d'application refusé : {resp.status_code}")
        data = resp.json()
        self._app_token = data["access_token"]
        self._app_token_expires = time.time() + int(data.get("expires_in", 3600))
        return self._app_token

    async def _get_users(self, **params: str) -> TwitchUser | None:
        data = (await self._helix("/users", await self._get_app_token(), params))["data"]
        if not data:
            return None
        u = data[0]
        return TwitchUser(u["id"], u["login"], u["display_name"])

    async def get_user_by_login(self, login: str) -> TwitchUser | None:
        return await self._get_users(login=login.lower().lstrip("@"))

    async def get_user_by_id(self, user_id: str) -> TwitchUser | None:
        return await self._get_users(id=user_id)
