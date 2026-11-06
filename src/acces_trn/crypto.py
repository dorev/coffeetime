"""Chiffrement symétrique des jetons (cookie des mods, jetons du bot Twitch)."""

from __future__ import annotations

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken


class Box:
    """Chiffre et signe des petites données JSON avec une clé dérivée de SECRET_KEY."""

    def __init__(self, secret_key: str, purpose: str) -> None:
        digest = hashlib.sha256(f"{purpose}:{secret_key}".encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def seal(self, data: dict) -> str:
        return self._fernet.encrypt(json.dumps(data).encode()).decode()

    def open(self, token: str | None, max_age: int | None = None) -> dict | None:
        """Retourne les données, ou None si absentes, falsifiées ou expirées."""
        if not token:
            return None
        try:
            return json.loads(self._fernet.decrypt(token.encode(), ttl=max_age))
        except (InvalidToken, ValueError):
            return None
