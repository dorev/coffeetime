# Accès TRN — service d'aiguillage

Service de la Fondation des Gardiens virtuels pour relier les communautés Twitch partenaires aux
Travailleuses et travailleurs de rue numériques (TRN).

- **Les TRN** changent leur statut (🟢 disponible / 🟡 occupé·e / 🔴 absent·e) d'un clic dans **Discord**,
  et reçoivent les demandes des chaînes dans un salon Discord, avec un bouton « Je m'en occupe ».
- **Les streamers et leurs mods** demandent un·e TRN de deux façons :
  1. **Commande chat** `!trn [message]` : le bot efface la commande et répond par chuchotement ;
  2. **Extension Twitch** : panneau sous le stream, le rôle de mod est fourni par Twitch.
- **Les viewers** voient si des TRN sont disponibles (page, widget, incrustation OBS, badge, panneau d'extension)
  et peuvent eux-mêmes rejoindre les TRN.
- **Tout est enregistré** dans un Google Sheets : statuts, demandes, demandes bloquées (délai de 10 minutes),
  demandes sans TRN disponible, prises en charge, chuchotements échoués.

📋 Plan : [`docs/PLAN.md`](docs/PLAN.md) · 🧪 Test manuel : [`docs/TEST_MANUEL.md`](docs/TEST_MANUEL.md) · 🧩 Extension : [`docs/EXTENSION.md`](docs/EXTENSION.md) ·
📊 Google Sheets : [`integrations/google-sheets/`](integrations/google-sheets/) · 🚀 Version sans serveur : [`livrable1/`](livrable1/)

## Ce que reçoivent les TRN

Dans le salon Discord des demandes :

> **📣 Demande de la chaîne machaine** — Heure : 21 h 42 · Via : commande !trn · lea_mod
> Message : « un viewer parle de se faire du mal » — [Je m'en occupe]

Le rôle TRN est mentionné seulement si l'équipe est en service. Quand personne n'est en service,
la demande est publiée sans mention, enregistrée, et le mod est prévenu avec les ressources d'urgence.

## Adresses du service

| Adresse | Pour qui | Rôle |
|---|---|---|
| `/` | Viewers | Page d'accès (statut, bouton vers les TRN, ressources) |
| `/status.json`, `/widget`, `/badge.svg`, `/qr.svg` | Tout le monde | Signal public de disponibilité |
| `/trousse?src=<chaîne>` | Streamers | Extraits prêts à copier (widget, OBS, badge, QR) |
| `/ext/info`, `/ext/demande` | Extension Twitch | Backend du panneau (jeton Twitch vérifié) |
| `/bot/autoriser?cle=…` | FGV (une fois) | Autoriser le compte Twitch du bot |
| `/admin` | TRN | Page de secours pour le statut et les statistiques |

## Démarrage rapide (local)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # remplir au minimum SECRET_KEY, DESTINATION_URL, ADMIN_PASSWORD
pytest
python -m acces_trn                # → http://127.0.0.1:8000
```

Sans les variables Discord/Twitch, seules les pages publiques et `/admin` fonctionnent.
Pour un test complet sur ton ordinateur, voir [`docs/TEST_MANUEL.md`](docs/TEST_MANUEL.md).

## Mise en place des intégrations

### 1. Discord (serveur des TRN)
1. <https://discord.com/developers/applications> → *New Application* → onglet **Bot** → *Reset Token* → `DISCORD_BOT_TOKEN`.
   Aucun *Privileged Gateway Intent* n'est nécessaire.
2. **OAuth2 → URL Generator** : portées `bot` + `applications.commands` ; permissions *View Channels,
   Send Messages, Embed Links, Read Message History, Mention Everyone* (pour mentionner le rôle TRN).
   Ouvrir l'URL pour inviter le bot.
3. Identifiants (Mode développeur → clic droit → *Copier l'identifiant*) : serveur → `DISCORD_GUILD_ID`,
   rôle TRN → `DISCORD_ROLE_ID`, salon des demandes → `DISCORD_REQUESTS_CHANNEL_ID`.
4. Dans un salon privé des TRN : `/panneau-statut`, puis épingler le message.
5. Inscrire les chaînes du pilote : `/chaine ajouter nom`.

Commandes : `/panneau-statut`, `/statut`, `/chaine ajouter|retirer|liste` (réservées au rôle TRN).

### 2. Twitch (bot de chat)
1. <https://dev.twitch.tv/console/apps> → *Register Your Application* :
   redirection `<BASE_URL>/auth/twitch/callback`, catégorie *Chat Bot*, client *Confidential*.
   → `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`.
2. **Compte du bot** (créé par les TRN) : un compte Twitch dédié, **avec numéro de téléphone vérifié**
   (obligatoire pour les chuchotements).
3. Choisir une `BOT_SETUP_KEY`, redémarrer, puis ouvrir `<BASE_URL>/bot/autoriser?cle=<BOT_SETUP_KEY>`
   et **se connecter avec le compte du bot**. Les jetons sont chiffrés dans la base.
4. Chaque streamer tape une fois `/mod NomDuBot` dans son chat (pour que le bot puisse effacer la commande).

Le bot ne parle **jamais** dans le chat : il efface `!trn` et chuchote la réponse. Si le chuchotement
échoue (quota Twitch, réglages de la personne), l'échec est enregistré dans le Google Sheets.

### 3. Extension Twitch
Voir [`docs/EXTENSION.md`](docs/EXTENSION.md) (création, pilote sans approbation, approbation, installation par le streamer).

### 4. Google Sheets
Voir [`integrations/google-sheets/README.md`](integrations/google-sheets/README.md) (Apps Script, 5 minutes).

## Déploiement (Docker)

```bash
cp .env.example .env               # BASE_URL=https://aide.exemple.org, etc.
docker compose up -d
```

Le conteneur écoute sur `127.0.0.1:8000` ; il faut un proxy HTTPS devant, par exemple
[Caddy](https://caddyserver.com/) :

```
aide.exemple.org {
    reverse_proxy 127.0.0.1:8000
    log {
        output discard   # pas de journal des visites (confidentialité)
    }
}
```

Données : `./data/acces_trn.sqlite3` (statut, chaînes, demandes, journal, jetons chiffrés) — à sauvegarder.

## Confidentialité et sécurité

- Viewers : aucune donnée collectée (ni IP ni journal des visites ; compteurs agrégés par jour).
- Demande : chaîne, heure, source, pseudo du mod, message facultatif (Discord + Google Sheets).
- Rôle vérifié par Twitch à chaque demande : badge du chat (commande) ou jeton signé (extension).
- Jetons du bot Twitch chiffrés dans la base. Jeton CSRF sur tous les formulaires.
- Extension : jeton JWT signé par Twitch vérifié par le serveur ; CORS limité à l'origine de l'extension.

## Structure

```
src/acces_trn/
  app.py           routes Web : public, autorisation du bot, extension, /admin
  dispatch.py      traitement d'une demande (délai, journal, Discord) — commun aux 2 options
  discord_bot.py   bot Discord des TRN (statut, demandes, chaînes)
  twitch_bot.py    bot de chat Twitch (!trn, effacement, chuchotement)
  twitch_api.py    API Twitch pour le Web (autorisation du bot, recherche de chaînes)
  extension.py     vérification des jetons de l'extension
  events.py        journal d'événements + envoi au Google Sheets
  store.py         SQLite
  texts.py         textes publics et ressources d'urgence (à valider par la FGV)
extension/         panneau de l'extension Twitch (à téléverser chez Twitch)
integrations/      script Google Apps Script
tests/             tests pytest (Twitch, Discord et Google Sheets simulés)
```

> ⚠️ Ce service n'est **pas** un service d'urgence. Les ressources affichées (911, 988, 1 866 APPELLE,
> 811, Jeunesse, J'écoute) sont à valider par la FGV.
