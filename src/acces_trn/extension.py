"""Backend de l'extension Twitch (option 3).

Le panneau de l'extension envoie le jeton JWT fourni par Twitch. Ce jeton est signé
avec le secret de l'extension et indique le rôle de la personne sur la chaîne
(broadcaster, moderator, viewer) : aucune connexion n'est demandée au mod.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

import jwt

ALLOWED_ROLES = {"broadcaster", "moderator"}


class ExtensionAuthError(Exception):
    pass


@dataclass(frozen=True)
class ExtensionViewer:
    channel_id: str
    role: str
    user_id: str | None        # présent seulement si la personne a partagé son identité
    opaque_user_id: str

    @property
    def can_request(self) -> bool:
        return self.role in ALLOWED_ROLES


class ExtensionVerifier:
    def __init__(self, client_id: str, secret_b64: str) -> None:
        self.client_id = client_id
        self._secret = base64.b64decode(secret_b64)

    @property
    def origin(self) -> str:
        """Origine des requêtes du panneau (hébergé par Twitch)."""
        return f"https://{self.client_id}.ext-twitch.tv"

    def verify(self, authorization: str | None) -> ExtensionViewer:
        if not authorization or not authorization.startswith("Bearer "):
            raise ExtensionAuthError("Jeton manquant")
        try:
            payload = jwt.decode(
                authorization.removeprefix("Bearer "),
                self._secret,
                algorithms=["HS256"],
                options={"require": ["exp", "channel_id", "role"]},
            )
        except jwt.PyJWTError as exc:
            raise ExtensionAuthError(f"Jeton invalide : {exc}") from exc
        return ExtensionViewer(
            channel_id=str(payload["channel_id"]),
            role=str(payload["role"]),
            user_id=str(payload["user_id"]) if payload.get("user_id") else None,
            opaque_user_id=str(payload.get("opaque_user_id", "")),
        )
