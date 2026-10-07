"""Point d'entrée : `python -m acces_trn` (ou `acces-trn`)."""

from __future__ import annotations

import logging
import os
import sys

import uvicorn

from .app import create_app
from .config import ConfigError, load_config


def run() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        sys.exit(f"Erreur de configuration : {exc}\nVoir le fichier .env.example.")
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-7s %(name)s : %(message)s",
    )
    uvicorn.run(
        create_app(config),
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        proxy_headers=True,          # derrière Caddy / nginx / Cloudflare
        forwarded_allow_ips="*",
        access_log=False,            # pas de journal des visites (IP) : confidentialité
    )


if __name__ == "__main__":
    run()
