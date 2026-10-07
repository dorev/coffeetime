"""Textes affichés au public. À faire relire et valider par la FGV.

Les gabarits HTML (templates/) contiennent la mise en page ; tout ce qui dépend
du statut est ici pour rester cohérent entre la page, le widget et le chat.
"""

from __future__ import annotations

from dataclasses import dataclass

from .store import Status


@dataclass(frozen=True)
class StatusText:
    emoji: str
    label: str           # court : badge, widget
    headline: str        # titre de la page d'accès
    action: str          # texte du bouton
    explanation: str     # phrase sous le bouton
    color: str           # couleur du badge


STATUS_TEXTS = {
    Status.AVAILABLE: StatusText(
        emoji="🟢",
        label="TRN disponible",
        headline="Un·e TRN est disponible maintenant",
        action="Parler à un·e TRN",
        explanation="Tu seras dirigé·e vers notre Discord pour ouvrir une conversation privée.",
        color="#1f8a4c",
    ),
    Status.BUSY: StatusText(
        emoji="🟡",
        label="Équipe occupée",
        headline="L'équipe est là, mais occupée",
        action="Laisser une demande",
        explanation="Ouvre une demande privée sur notre Discord : on te répond dès que possible.",
        color="#a86b00",
    ),
    Status.OFFLINE: StatusText(
        emoji="🔴",
        label="TRN hors ligne",
        headline="L'équipe n'est pas en ligne présentement",
        action="Laisser une demande",
        explanation="Tu peux laisser une demande privée sur notre Discord ; on te répondra à notre retour.",
        color="#b3261e",
    ),
}

# Ressources d'aide immédiate (Québec / Canada) — à valider par la FGV.
EMERGENCY_RESOURCES = [
    ("Danger immédiat", "911", "tel:911"),
    ("Idées suicidaires — appel ou texto, 24/7", "988", "tel:988"),
    ("Prévention du suicide Québec", "1 866 APPELLE (277-3553)", "tel:18662773553"),
    ("Info-Social", "811, option 2", "tel:811"),
    ("Jeunesse, J'écoute — texto", "686868", "sms:686868"),
]

CHAT_MAX = 400  # les chatbots Twitch coupent souvent autour de 400-500 caractères


def chat_line(status: Status, message: str, url: str) -> str:
    """Une ligne pour la commande !trn des chatbots (Nightbot, StreamElements…)."""
    t = STATUS_TEXTS[status]
    if status is Status.AVAILABLE:
        line = f"{t.emoji} Un·e TRN est disponible maintenant pour jaser en privé : {url}"
    elif status is Status.BUSY:
        line = f"{t.emoji} Les TRN sont occupé·e·s, mais tu peux laisser une demande : {url}"
    else:
        line = (
            f"{t.emoji} Les TRN sont hors ligne. Laisse une demande : {url} "
            "— Urgence : 911 · Détresse : 988 (appel/texto 24/7)"
        )
    if message:
        line += f" ({message})"
    return line[:CHAT_MAX]
