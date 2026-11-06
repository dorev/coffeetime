"""Connexion des mods sur la page /c/<chaîne> (option 2).

- Le cookie `trn_mod` (chiffré, HttpOnly) garde la CONNEXION Twitch pendant
  MOD_SESSION_DAYS jours : la personne n'a pas à se reconnecter à chaque fois.
- Le statut de modérateur·rice est REVÉRIFIÉ auprès de Twitch à chaque affichage
  du formulaire et à chaque demande : une personne retirée de la modération
  perd l'accès immédiatement, même si son cookie est encore valide.
"""

from __future__ import annotations

from dataclasses import dataclass

from .crypto import Box
from .store import Channel
from .twitch_api import Tokens, TwitchAuthError, TwitchClient, TwitchUser

COOKIE_NAME = "trn_mod"


@dataclass(frozen=True)
class ModCheck:
    user: TwitchUser
    is_mod: bool                 # mod de la chaîne, ou la chaîne elle-même
    cookie_value: str | None     # nouveau contenu du cookie si les jetons ont été renouvelés


class ModAuth:
    def __init__(self, twitch: TwitchClient, secret_key: str, session_days: int) -> None:
        self.twitch = twitch
        self.box = Box(secret_key, "mod-session")
        self.max_age = session_days * 86400

    def make_cookie(self, user: TwitchUser, tokens: Tokens) -> str:
        return self.box.seal(
            {
                "id": user.id,
                "login": user.login,
                "name": user.display_name,
                "access": tokens.access_token,
                "refresh": tokens.refresh_token,
                "exp": tokens.expires_at,
            }
        )

    def read_user(self, cookie: str | None) -> TwitchUser | None:
        data = self.box.open(cookie, max_age=self.max_age)
        return TwitchUser(data["id"], data["login"], data["name"]) if data else None

    async def check(self, cookie: str | None, channel: Channel) -> ModCheck | None:
        """Vérifie en direct auprès de Twitch. None = pas connecté ou connexion révoquée."""
        data = self.box.open(cookie, max_age=self.max_age)
        if not data:
            return None
        user = TwitchUser(data["id"], data["login"], data["name"])
        tokens = Tokens(data["access"], data["refresh"], data["exp"])
        renewed = False
        try:
            if tokens.expired:
                tokens, renewed = await self.twitch.refresh(tokens.refresh_token), True
            try:
                ids = await self.twitch.moderated_channel_ids(tokens.access_token, user.id)
            except TwitchAuthError:
                if renewed:
                    raise
                tokens, renewed = await self.twitch.refresh(tokens.refresh_token), True
                ids = await self.twitch.moderated_channel_ids(tokens.access_token, user.id)
        except TwitchAuthError:
            return None  # accès révoqué côté Twitch : il faut se reconnecter
        is_mod = user.id == channel.twitch_id or channel.twitch_id in ids
        return ModCheck(user, is_mod, self.make_cookie(user, tokens) if renewed else None)
