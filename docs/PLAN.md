# Plan de développement — MVP « Bot d'aide et de signalement »

> Prototype Python, hébergé localement (un ordinateur ou un mini-serveur de l'organisme),
> pour Discord et Twitch. Objectif : **simple, fiable, peu coûteux, respectueux de la vie privée.**

Légende de l'état : ✅ fait dans ce dépôt · 🧪 codé, à valider en conditions réelles · ⬜ à faire

---

## 1. Objectifs et périmètre

### Ce que le MVP doit permettre
1. À n'importe qui de **demander de l'aide** et d'être mis en contact **en privé** avec un·e intervenant·e.
2. À n'importe qui de **signaler un comportement**, éventuellement **anonymement**.
3. À l'équipe de **voir, prendre en charge et fermer** chaque dossier depuis un seul salon Discord.
4. Sur Twitch, d'offrir les mêmes portes d'entrée (`!aide`, `!signaler`) **sans jamais discuter de sujets sensibles dans le chat public**.

### Hors périmètre (volontairement)
- Modération automatique (bannir, supprimer des messages, détecter des mots-clés).
- Tableau de bord web, comptes utilisateurs, application mobile.
- Hébergement infonuagique : prévu **après** le pilote (voir §10).
- Chuchotements Twitch : API restrictive (compte vérifié par téléphone, quotas), peu fiable pour un MVP.

### Critères de réussite du MVP
- Une demande ou un signalement arrive dans `#signalements` en **moins de 5 secondes**.
- Aucune donnée personnelle n'est visible publiquement.
- Le bot redémarre seul après une panne ou un redémarrage de l'ordinateur.
- Une personne non technique de l'équipe peut traiter un dossier sans formation (2 boutons).

---

## 2. Architecture

```
┌──────────────── Ordinateur local (Windows / macOS / Linux) ────────────────┐
│  python -m bot_aide   (un seul processus asyncio)                          │
│                                                                            │
│  ┌──────────────┐   notify_staff()   ┌──────────────┐   ┌───────────────┐  │
│  │ twitch_bot   │ ─────────────────► │ discord_bot  │ ─►│ db (SQLite)   │  │
│  │ EventSub WS  │                    │ Gateway WS   │   │ data/*.sqlite3│  │
│  └──────┬───────┘                    └──────┬───────┘   └───────────────┘  │
└─────────┼───────────────────────────────────┼──────────────────────────────┘
          │ connexions SORTANTES uniquement   │
          ▼                                   ▼
   Twitch (chat public)              Discord (serveur de l'organisme)
   !aide / !signaler                 /aide, /signaler, clic droit,
                                     panneau à boutons, #signalements
```

**Pourquoi c'est simple à héberger localement :** Discord (Gateway) et Twitch (EventSub WebSocket)
fonctionnent par connexions **sortantes**. Il n'y a **aucun port à ouvrir**, aucun nom de domaine,
aucun certificat. Une connexion Internet ordinaire suffit.

### Modules

| Fichier | Rôle |
|---|---|
| `src/bot_aide/__main__.py` | Point d'entrée, démarre Discord + Twitch dans la même boucle asyncio |
| `src/bot_aide/config.py` | Lecture et validation du `.env` |
| `src/bot_aide/db.py` | Table `reports` (SQLite), transitions de statut, purge |
| `src/bot_aide/ratelimit.py` | Anti-abus : N actions / personne / heure |
| `src/bot_aide/messages.py` | **Tous les textes publics** (à faire relire par l'organisme) |
| `src/bot_aide/discord_bot.py` | Commandes, formulaire, fils privés, boutons de suivi |
| `src/bot_aide/twitch_bot.py` | Logique des commandes Twitch (testable) + connexion EventSub |
| `tests/` | Tests automatisés (pytest) |

### Choix techniques

| Besoin | Choix | Raison |
|---|---|---|
| Langage | Python 3.11+ | Lisible, nombreuses ressources pour débuter |
| Discord | `discord.py` ≥ 2.7 | Référence ; gère les boutons persistants et les cases à cocher dans les formulaires |
| Twitch | `twitchAPI` ≥ 4.5 | EventSub WebSocket et envoi de messages par l'API officielle (l'IRC est l'ancienne méthode) |
| Stockage | SQLite (fichier) | Rien à installer, sauvegarde = copier un fichier |
| Secrets | `.env` + `python-dotenv` | Hors du code, ignoré par git |
| Intents Discord | aucun privilégié | Moins de permissions = moins de risques ; le contenu des messages signalés arrive via l'interaction |

---

## 3. Modèle de données

Une seule table, `reports`, pour les **signalements** (`kind = report`) et les **demandes d'aide** (`kind = help`) :

| Colonne | Contenu |
|---|---|
| `id` | Numéro de dossier affiché partout (#12) |
| `created_at` | Date UTC |
| `source` | `discord` ou `twitch` |
| `kind` | `report` ou `help` |
| `reporter` | Pseudo + ID de la personne qui signale — **NULL si anonyme** |
| `target` | Personne concernée (facultatif) |
| `location` | Salon, chaîne Twitch, lien du fil privé |
| `description` | Texte libre |
| `evidence` | Lien vers un message, un extrait, un clip |
| `status` | `open` → `claimed` → `closed` (ou `open` → `closed`) |
| `claimed_by`, `closed_at` | Suivi par l'équipe |
| `staff_message_id` | Message correspondant dans `#signalements` |

**Rétention :** les dossiers **fermés** sont supprimés automatiquement après `RETENTION_DAYS` (90 jours par défaut), chaque jour à 4 h UTC.

---

## 4. Parcours utilisateurs

### Discord — demande d'aide
1. La personne tape `/aide`, ou clique sur **💬 Parler à un·e intervenant·e** dans le panneau public.
2. Le bot crée un **fil privé** `aide-<n°>` dans le salon d'aide, y ajoute la personne et y publie un message d'accueil avec les ressources de crise.
3. Un dossier « Demande d'aide » apparaît dans `#signalements`, avec mention du rôle Intervenant·e et un lien vers le fil.
4. Un·e intervenant·e clique sur **Je prends en charge**, rejoint le fil, puis clique sur **Fermer** à la fin.

### Discord — signalement
- `/signaler`, le bouton **🚩 Signaler**, ou **clic droit sur un message → Applications → Signaler ce message**. Avec le clic droit, l'auteur, le salon et le lien du message sont préremplis.
- Formulaire : personne concernée · où · que s'est-il passé · lien ou preuve · ☐ **Rester anonyme**.
- La personne reçoit une confirmation (visible par elle seule) avec le numéro du dossier.

### Twitch
| Message dans le chat | Réponse du bot | Effet côté équipe |
|---|---|---|
| `!aide` | Lien privé (PUBLIC_HELP_URL) + 911/988 | Dossier « Demande d'aide » |
| `!signaler @pseudo raison` | « Merci, dossier #n » + lien privé | Dossier « Signalement » (signalé « (modérateur) » si c'est un mod) |
| `!signaler` seul | Mode d'emploi + lien privé | Rien |

### Équipe
- `#signalements` : un message par dossier, couleur selon le statut (🔴 ouvert, 🟡 pris en charge, 🟢 fermé).
- Seules les personnes ayant le rôle Intervenant·e peuvent cliquer sur les boutons. Les boutons fonctionnent encore après un redémarrage du bot.
- `/stats` : nombre de dossiers par type et par statut. `/panneau` : publie le panneau d'aide dans le salon courant.

---

## 5. Étapes de développement

Durées indicatives pour une personne qui débute, à temps partiel.

### Étape 0 — Préparation (½ à 1 jour) ⬜
- [ ] Installer Python 3.11+ et Git.
- [ ] Créer un **serveur Discord de test** (copie de la structure réelle) : rôle `Intervenant·e`, `#signalements` (privé), `#aide`.
- [ ] Créer l'application Discord et le bot (voir le README, section *Configuration Discord*).
- [ ] Créer un **compte Twitch dédié au bot** et l'application dans la console développeur Twitch.
- [ ] Faire valider par l'organisme : textes de `messages.py`, ressources de crise, heures de présence, durée de conservation.

**Critère d'acceptation :** `.env` rempli et `pytest` vert.

### Étape 1 — Socle ✅
- [x] Structure du projet, configuration validée (`config.py`), journaux.
- [x] Base SQLite + transitions de statut + purge (`db.py`).
- [x] Anti-abus (`ratelimit.py`).
- [x] Tests automatisés : configuration, base de données, anti-abus.

### Étape 2 — Signalements Discord ✅ / 🧪
- [x] `/signaler` + formulaire (5 champs, dont la case « anonyme »).
- [x] Menu contextuel « Signaler ce message » prérempli.
- [x] Publication dans `#signalements` avec mention du rôle.
- [ ] 🧪 Vérifier sur le serveur de test : anonymat réel (aucun pseudo visible), limite de 5 par heure.

### Étape 3 — Aide Discord (fils privés) ✅ / 🧪
- [x] `/aide` (réponse visible par la personne seule) + bouton.
- [x] Création d'un fil privé, ajout de la personne, message d'accueil.
- [x] `/panneau` : panneau public permanent avec deux boutons.
- [ ] 🧪 Vérifier que les intervenant·e·s voient les fils (permission « Gérer les fils ») et que les autres membres ne les voient **pas**.

### Étape 4 — Suivi par l'équipe ✅ / 🧪
- [x] Boutons persistants « Je prends en charge » et « Fermer », réservés au rôle.
- [x] Mise à jour du message (couleur, intervenant·e).
- [x] `/stats`, purge quotidienne.
- [ ] 🧪 Redémarrer le bot et vérifier que les anciens boutons fonctionnent toujours.

### Étape 5 — Twitch ✅ / 🧪
- [x] Commandes `!aide` / `!signaler` (logique testée hors ligne).
- [x] Connexion EventSub WebSocket, envoi par l'API Send Chat Message.
- [x] Alerte vers `#signalements`.
- [ ] 🧪 Première autorisation OAuth (le navigateur s'ouvre) avec le **compte du bot**.
- [ ] 🧪 Nommer le bot modérateur sur la chaîne test (`/mod nomdubot`) pour éviter les restrictions du chat.

### Étape 6 — Recette (1 à 2 jours) ⬜
Dérouler la **liste de vérification** du §6 sur le serveur de test, avec au moins une personne de l'organisme.

### Étape 7 — Déploiement local (½ jour) ⬜
- [ ] Choisir la machine hôte (allumée en permanence, mises à jour automatiques **sans** redémarrage surprise).
- [ ] Démarrage automatique (§7).
- [ ] Sauvegarde quotidienne de `data/` (§7).
- [ ] Remplacer les identifiants du serveur de test par ceux du serveur réel.

### Étape 8 — Pilote (2 à 4 semaines) ⬜
- [ ] 1 serveur Discord + 1 ou 2 chaînes Twitch partenaires.
- [ ] Point hebdomadaire avec les intervenant·e·s : textes, faux signalements, délais.
- [ ] Décider : on garde l'hébergement local, ou on passe à un serveur (§10) ?

---

## 6. Stratégie de tests

### Automatisés (`pytest`, aucune connexion requise)
- Configuration : valeurs manquantes, nombres invalides, chaînes Twitch normalisées.
- Base de données : création, anonymat, prise en charge unique, fermeture, purge.
- Anti-abus : fenêtre glissante.
- Commandes Twitch : analyse des commandes, réponses, alertes, limites, messages du bot ignorés.
- Discord : contenu des fiches et boutons selon le statut.

### Liste de vérification manuelle (serveur de test)
| # | Action | Résultat attendu |
|---|---|---|
| 1 | `/aide` en tant que membre | Message visible par soi seul, bouton présent |
| 2 | Clic sur le bouton d'aide | Fil privé créé ; un autre membre ne le voit pas ; dossier dans `#signalements` |
| 3 | `/signaler` en cochant « anonyme » | Fiche « Signalé par : Anonyme » ; colonne `reporter` vide en base |
| 4 | Clic droit sur un message → Signaler | Champs préremplis, lien du message cliquable dans la fiche |
| 5 | 6 signalements en moins d'une heure | Le 6ᵉ est refusé poliment |
| 6 | Membre sans rôle clique sur « Je prends en charge » | Refus, la fiche ne change pas |
| 7 | Intervenant·e clique, puis un·e autre clique | Le second clic est refusé (« déjà pris en charge ») |
| 8 | Redémarrer le bot, cliquer sur « Fermer » | Fonctionne |
| 9 | `!aide` sur Twitch | Réponse avec lien + 988 ; dossier dans `#signalements` |
| 10 | `!signaler @x test` par un mod | Dossier marqué « (modérateur) », cible = x |
| 11 | Couper Internet 2 minutes | Reconnexion automatique, sans plantage |

---

## 7. Déploiement local

### Installation (toutes plateformes)
```bash
git clone <ce dépôt> bot-aide && cd bot-aide
python -m venv .venv
# Windows : .venv\Scripts\activate    macOS/Linux : source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # puis remplir .env
pytest                      # doit être vert
python -m bot_aide          # lancer le bot
```

### Démarrage automatique
- **Linux** : service systemd fourni dans `deploy/bot-aide.service` (instructions dans le fichier).
- **Windows** : Planificateur de tâches → *Créer une tâche* → déclencheur « Au démarrage » →
  action `C:\chemin\bot-aide\.venv\Scripts\python.exe`, arguments `-m bot_aide`,
  « Commencer dans » = `C:\chemin\bot-aide`. Cocher « Exécuter même si l'utilisateur n'est pas connecté »
  et, dans *Paramètres*, « Si la tâche échoue, redémarrer toutes les 1 minute ».
- **macOS** : un `LaunchAgent` (`~/Library/LaunchAgents`) avec `KeepAlive=true`.

> Avant le premier démarrage automatique, lance le bot **une fois à la main** si Twitch est activé :
> l'autorisation OAuth ouvre un navigateur. Le jeton est ensuite sauvegardé dans `data/`.

### Sauvegardes
- Copier `data/bot.sqlite3` chaque jour vers un emplacement **chiffré** (disque externe, dossier infonuagique de l'organisme).
- Le fichier `.env` doit être conservé à part (gestionnaire de mots de passe), jamais par courriel.

---

## 8. Sécurité, confidentialité et Loi 25

- **Minimisation** : on ne stocke que le contenu du formulaire. Pas d'historique de chat, pas d'adresse IP.
- **Anonymat** : si la case est cochée, l'identité n'est **ni affichée ni enregistrée**. L'anti-abus reste en mémoire seulement.
- **Conservation** : purge automatique des dossiers fermés (`RETENTION_DAYS`). Les messages dans `#signalements` et les fils sont à supprimer ou archiver selon la même politique (manuellement pour le MVP).
- **Accès** : `#signalements` et les fils d'aide sont visibles **uniquement** par le rôle Intervenant·e. Activer la double authentification (2FA) pour ce rôle.
- **Secrets** : `.env` et `data/` sont exclus de git. Si un jeton fuit, le régénérer immédiatement (portail Discord ou console Twitch).
- **Poste hôte** : session protégée par mot de passe, disque chiffré (BitLocker / FileVault / LUKS).
- **Transparence** : publier une courte politique de confidentialité (qui voit quoi, combien de temps), avec un lien dans le panneau.
- **Responsable** : nommer la personne responsable de la protection des renseignements personnels (obligation de la Loi 25).
- **Urgence** : le bot n'est pas un service d'urgence. Les ressources (911, 988, 1 866 APPELLE, 811) sont affichées à chaque demande d'aide.

---

## 9. Limites connues et risques

| Risque | Mitigation |
|---|---|
| L'ordinateur hôte s'éteint ou perd Internet | Redémarrage automatique ; passer à un VPS après le pilote |
| Le chat Twitch est public | Le bot ne fait que rediriger ; les détails passent par le canal privé |
| Faux signalements ou spam | Limite par personne et par heure ; fermer sans suite |
| Messages du bot bloqués sur Twitch (chat réservé aux abonnés, mode lent) | Nommer le bot modérateur sur chaque chaîne |
| Dossiers non traités hors des heures de présence | Message « pas un service d'urgence » + ressources 24/7 |
| La cible d'un signalement voit le bot répondre sur Twitch | Préférer le lien privé pour les cas sensibles (expliqué dans `!aide`) |

---

## 10. Après le MVP (idées, par priorité)

1. **Hébergement 24/7** : VPS canadien (~6 $/mois, OVHcloud Beauharnois) ou Oracle Cloud *Always Free* (région Montréal). Même code ; ajouter un `Dockerfile`.
2. Rappel automatique si un dossier reste ouvert plus de X heures.
3. Fermeture avec motif (catégories) → statistiques anonymisées pour les rapports de l'organisme.
4. Archivage et suppression automatiques des fils d'aide fermés.
5. Plusieurs serveurs Discord ou un formulaire web public, pour les personnes sans Discord.
6. Interface bilingue français / anglais.
