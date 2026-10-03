# Bot d'aide et de signalement — Discord + Twitch

Prototype (MVP) en Python qui permet :

- de **demander de l'aide** et d'ouvrir un **fil privé** avec un·e intervenant·e (Discord) ;
- de **signaler un comportement**, anonymement si on le souhaite (Discord et Twitch) ;
- à l'équipe de **prendre en charge et fermer** chaque dossier depuis un salon `#signalements`.

📋 **Plan de développement complet : [`docs/PLAN.md`](docs/PLAN.md)**

## Démarrage rapide

Prérequis : Python 3.11 ou plus récent.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # Windows : copy .env.example .env
# → remplir .env (voir ci-dessous)
pytest                             # tests automatisés
python -m bot_aide                 # lancer le bot (Ctrl+C pour arrêter)
```

## Configuration Discord

1. **Serveur** (Paramètres du serveur) :
   - Créer un rôle **Intervenant·e**.
   - `#signalements` : salon **privé**, visible seulement par Intervenant·e et le bot.
   - `#aide` : salon visible par tout le monde, où **personne** ne peut écrire, mais où l'on peut
     *Envoyer des messages dans les fils*. Donner au rôle Intervenant·e la permission
     **Gérer les fils** sur ce salon : c'est ce qui lui permet de voir les fils privés.
2. **Application** : <https://discord.com/developers/applications> → *New Application*.
   - Onglet **Bot** : *Reset Token* → copier dans `DISCORD_TOKEN`. Aucun *Privileged Gateway Intent* n'est nécessaire.
   - Onglet **OAuth2 → URL Generator** : portées `bot` et `applications.commands` ; permissions :
     *View Channels, Send Messages, Send Messages in Threads, Create Private Threads,
     Embed Links, Read Message History, Mention Everyone* (pour mentionner le rôle).
     Ouvrir l'URL générée pour inviter le bot sur le serveur.
3. **Identifiants** : Paramètres Discord → *Avancés* → activer le **Mode développeur**, puis
   clic droit → *Copier l'identifiant* sur le serveur, les deux salons et le rôle.
4. Lancer le bot, puis taper `/panneau` dans `#aide` pour publier le panneau à boutons.

## Configuration Twitch (facultatif)

1. Créer un **compte Twitch pour le bot** (ex. `AideBot_Org`).
2. <https://dev.twitch.tv/console/apps> → *Register Your Application* :
   - OAuth Redirect URL : `http://localhost:17563`
   - Catégorie : *Chat Bot* ; type de client : *Confidential*.
   - Copier le *Client ID* et générer un *Client Secret*.
3. Dans `.env` : `TWITCH_ENABLED=true`, l'ID, le secret et `TWITCH_CHANNELS=chaine1,chaine2`.
4. Au premier lancement, un navigateur s'ouvre : **se connecter avec le compte du bot** et autoriser.
   Le jeton est ensuite enregistré dans `data/twitch_token.json` (à ne jamais partager).
5. Sur chaque chaîne, la personne qui diffuse tape `/mod NomDuBot` pour que les messages du bot ne soient pas bloqués.

## Commandes

| Où | Commande | Qui |
|---|---|---|
| Discord | `/aide` | Tout le monde |
| Discord | `/signaler` | Tout le monde |
| Discord | Clic droit sur un message → *Applications* → *Signaler ce message* | Tout le monde |
| Discord | `/panneau`, `/stats` | Personnes ayant la permission *Gérer le serveur* |
| Twitch | `!aide`, `!signaler @pseudo raison` | Tout le monde |

## Structure

```
src/bot_aide/
  __main__.py      point d'entrée (Discord + Twitch dans un seul processus)
  config.py        lecture du .env
  db.py            SQLite : dossiers, statuts, purge
  discord_bot.py   commandes, formulaire, fils privés, boutons de suivi
  twitch_bot.py    commandes du chat Twitch
  messages.py      tous les textes publics (à faire relire par l'organisme)
  ratelimit.py     anti-abus
tests/             tests pytest
deploy/            service systemd (démarrage automatique sous Linux)
docs/PLAN.md       plan de développement
```

> ⚠️ Ce bot n'est **pas** un service d'urgence. Les ressources affichées (911, 988, 1 866 APPELLE,
> 811, Jeunesse, J'écoute) sont à valider par l'organisme dans `src/bot_aide/messages.py`.
