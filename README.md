# Accès TRN — service d'aiguillage

Un petit service Web qui sert de **porte d'entrée unique** vers les Travailleuses et travailleurs
de rue numériques (TRN) de la Fondation des Gardiens virtuels.

- **Côté public** : une page qui affiche si l'équipe est 🟢 disponible, 🟡 occupée ou 🔴 hors ligne,
  avec un gros bouton « Parler à un·e TRN » qui mène au système de tickets Discord des TRN,
  et les ressources d'urgence.
- **Côté diffuseurs** : commande `!trn` pour Nightbot / StreamElements / Fossabot, widget Web,
  incrustation OBS, badge, code QR — tout se met à jour seul. Page `/trousse` prête à partager.
- **Côté privé (TRN)** : connexion avec Discord (rôle TRN), trois boutons pour changer le statut,
  retour automatique à « hors ligne » après X heures, statistiques anonymes.

Le service **ne recueille aucun renseignement personnel** sur les gens qui cherchent de l'aide
(pas d'IP, pas de journal de visites) et **ne remplace pas** les tickets Discord : il y amène les gens.

📋 Plan complet : [`docs/PLAN.md`](docs/PLAN.md) · 🚀 Version sans serveur : [`livrable1/`](livrable1/)

## Adresses du service

| Adresse | Pour qui | Rôle |
|---|---|---|
| `/` | Public | Page d'accès (statut, bouton, ressources) |
| `/go` | Public | Redirige vers le Discord des TRN (compte les clics) |
| `/status.txt` | Chatbots Twitch | Une ligne de texte selon le statut |
| `/status.json` | Sites Web | Statut en JSON (CORS ouvert) |
| `/widget` | Sites Web, OBS | Bouton intégrable (`?theme=overlay` pour OBS) |
| `/badge.svg`, `/qr.svg` | Diffuseurs | Badge de statut, code QR |
| `/trousse` | Diffuseurs | Trousse d'intégration personnalisée (`?src=ma_chaine`) |
| `/admin` | TRN | Espace privé : changer le statut, statistiques |

Le paramètre `?src=nom_de_chaine` sur n'importe quelle adresse publique permet de compter
les utilisations par diffuseur, sans aucune donnée personnelle.

## Démarrage rapide (local)

Prérequis : Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # puis remplir : SECRET_KEY, DESTINATION_URL, ADMIN_PASSWORD
pytest
python -m acces_trn                # → http://127.0.0.1:8000  (espace TRN : /admin)
```

Pour essayer sans Discord, garde `AUTH_MODE=password`.

## Déploiement (Docker)

```bash
cp .env.example .env               # BASE_URL=https://aide.exemple.org, AUTH_MODE=discord, etc.
docker compose up -d
```

Le conteneur écoute sur `127.0.0.1:8000` ; il faut un proxy HTTPS devant. Le plus simple est
[Caddy](https://caddyserver.com/) (certificat automatique) :

```
aide.exemple.org {
    reverse_proxy 127.0.0.1:8000
    log {
        output discard   # pas de journal des visites (confidentialité)
    }
}
```

Les données (statut, compteurs) sont dans `./data/acces_trn.sqlite3` — un seul fichier à sauvegarder.
N'importe quel hébergeur de conteneurs fonctionne aussi (VPS, Oracle Cloud Free, serveur de la FGV).

## Connexion des TRN avec Discord

1. <https://discord.com/developers/applications> → *New Application* (ex. « Accès TRN »).
2. **OAuth2** → copier *Client ID* et *Client Secret* dans `.env` ;
   ajouter le *Redirect* `https://aide.exemple.org/admin/callback` (= `BASE_URL` + `/admin/callback`).
3. Dans Discord (Mode développeur activé) : clic droit sur le serveur des TRN → *Copier l'identifiant*
   → `DISCORD_GUILD_ID` ; Paramètres du serveur → Rôles → clic droit sur le rôle TRN → `DISCORD_ROLE_ID`.
4. `AUTH_MODE=discord`. Aucun bot à inviter : le service lit seulement, au moment de la connexion,
   si la personne a le rôle. Retirer le rôle retire l'accès.

## Personnaliser

- **Textes et ressources d'urgence** : `src/acces_trn/texts.py` (à faire valider par la FGV).
- **Mise en page** : `src/acces_trn/templates/` (HTML) et `src/acces_trn/static/style.css`.

## Structure

```
src/acces_trn/
  app.py         routes publiques, intégrations, espace TRN
  store.py       SQLite : statut, journal des changements, compteurs anonymes
  auth.py        connexion Discord (rôle TRN) ou mot de passe
  texts.py       textes publics et ressources d'urgence
  config.py      lecture du .env
  templates/     pages HTML
  static/        CSS, script du widget
tests/           tests pytest
livrable1/       page statique « lien officiel » (sans serveur)
docs/PLAN.md     plan de développement
```

> ⚠️ Ce service n'est **pas** un service d'urgence. Les ressources affichées (911, 988, 1 866 APPELLE,
> 811, Jeunesse, J'écoute) sont à valider par la FGV.
