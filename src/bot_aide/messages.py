"""Textes affichés par le bot.

Tout le contenu destiné au public est regroupé ici pour que l'organisme puisse
le relire et le modifier sans toucher au reste du code.
⚠️ Ressources à valider par l'organisme avant la mise en ligne.
"""

from __future__ import annotations

CRISIS_RESOURCES = (
    "**Danger immédiat :** compose le **911**.\n"
    "**Idées suicidaires :** appelle ou texte le **988** (24/7), "
    "ou le **1 866 APPELLE** (277-3553), texto **535353**.\n"
    "**Besoin de parler :** Info-Social **811** (option 2).\n"
    "**Moins de 20 ans :** Jeunesse, J'écoute **1 800 668-6868**, texto **686868**."
)

# Version courte pour le chat Twitch (500 caractères max, pas de Markdown).
CRISIS_SHORT = "Danger immédiat : 911. Détresse ou idées suicidaires : 988 (appel ou texto, 24/7)."

NOT_AN_EMERGENCY = (
    "Ce bot n'est **pas** un service d'urgence. "
    "L'équipe répond dès que possible pendant ses heures de présence."
)

HELP_INTRO = (
    "Tu n'es pas seul·e. Tu peux parler en privé à un·e intervenant·e "
    "en cliquant sur le bouton ci-dessous."
)

HELP_BUTTON_LABEL = "Parler à un·e intervenant·e"
HELP_THREAD_CREATED = "Un fil privé a été créé : {thread}. Un·e intervenant·e va t'y rejoindre."
HELP_THREAD_WELCOME = (
    "Bonjour {user}, merci d'avoir écrit. Ce fil est privé : seules toi et l'équipe "
    "d'intervention peuvent le voir. Explique-nous ce qui se passe quand tu es prêt·e.\n\n"
    + NOT_AN_EMERGENCY
)

REPORT_THANKS = (
    "Merci, ton signalement **#{id}** a été transmis à l'équipe. "
    "Tu ne recevras pas forcément de suivi, mais il sera traité."
)
REPORT_THANKS_ANONYMOUS = REPORT_THANKS + " Ton identité n'a pas été conservée."

RATE_LIMITED = "Tu as envoyé beaucoup de demandes récemment. Réessaie un peu plus tard."
STAFF_ONLY = "Cette action est réservée à l'équipe d'intervention."
ALREADY_HANDLED = "Ce dossier est déjà pris en charge ou fermé."

# --- Twitch (texte brut) ---------------------------------------------------
TWITCH_HELP = (
    "@{user} Pour parler en privé à un·e intervenant·e : {url} . " + CRISIS_SHORT
)
TWITCH_REPORT_ACK = (
    "@{user} Merci, l'équipe est avisée (dossier #{id}). "
    "Pour ajouter des détails en privé : {url}"
)
TWITCH_REPORT_USAGE = (
    "@{user} Utilisation : !signaler @pseudo raison — ou écris-nous en privé : {url}"
)
TWITCH_RATE_LIMITED = "@{user} Tu as déjà envoyé plusieurs signalements. Réessaie plus tard."
