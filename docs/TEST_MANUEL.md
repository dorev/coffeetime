# Test manuel sur ton ordinateur, avec ton propre Discord

But : valider tout le parcours avec de vrais comptes, sans hébergement.

- **Phase A, 100 % local (environ 1 h)** : bot Discord, statut, commande `!trn` sur ta propre chaîne, journal.
- **Phase B, avec un tunnel HTTPS (environ 45 min)** : l'extension Twitch. Twitch doit pouvoir joindre ton
  ordinateur en HTTPS.

Ce qu'il te faut :
- Python 3.11 ou plus, Git ;
- ton compte Discord et un serveur de test (créé pour l'occasion) ;
- ta chaîne Twitch (tu joues le streamer) ;
- **un 2ᵉ compte Twitch pour le bot**, avec un numéro de téléphone vérifié (obligatoire pour les chuchotements) ;
- facultatif : un 3ᵉ compte Twitch pour jouer un viewer, ou un·e ami·e.

---

## Phase A — Discord + commande chat (local)

### A1. Installer le projet
```bash
git clone <dépôt> acces-trn && cd acces-trn
git checkout claude/twitch-discord-moderation-bot-c1zyk7
python -m venv .venv
source .venv/bin/activate            # Windows : .venv\Scripts\activate
pip install -e ".[dev]"
pytest                               # doit afficher « passed »
cp .env.example .env                 # Windows : copy .env.example .env
```

Dans `.env`, remplir d'abord :
```
BASE_URL=http://localhost:8000
DESTINATION_URL=https://discord.gg/<une invitation vers ton serveur de test>
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
AUTH_MODE=password
ADMIN_PASSWORD=<12 caractères ou plus>
```

### A2. Préparer ton serveur Discord de test
1. Créer un serveur (« TRN test »).
2. Activer le **Mode développeur** : Paramètres utilisateur → Avancés.
3. Créer un rôle **TRN** et te l'attribuer.
4. Créer deux salons **privés** (visibles par le rôle TRN seulement) :
   `#statut-trn` (pour le panneau) et `#demandes-trn` (pour les demandes).

### A3. Créer le bot Discord
1. <https://discord.com/developers/applications> → **New Application** (« Accès TRN test »).
2. Onglet **Bot** → **Reset Token** → copier dans `DISCORD_BOT_TOKEN`.
   Pas besoin d'activer les *Privileged Gateway Intents*.
3. Onglet **OAuth2 → URL Generator** :
   - Scopes : `bot` et `applications.commands`.
   - Permissions : *View Channels*, *Send Messages*, *Embed Links*, *Read Message History*, *Mention Everyone*.
   - Ouvrir l'URL générée → choisir ton serveur de test → **Autoriser**.
4. Dans les deux salons privés : *Modifier le salon → Permissions* → ajouter le **bot** (voir le salon et y écrire).
5. Copier les identifiants (clic droit → *Copier l'identifiant*) :
   ```
   DISCORD_GUILD_ID=<le serveur>
   DISCORD_ROLE_ID=<le rôle TRN>        (Paramètres du serveur → Rôles → clic droit sur TRN)
   DISCORD_REQUESTS_CHANNEL_ID=<#demandes-trn>
   ```

### A4. Créer l'application Twitch
1. <https://dev.twitch.tv/console/apps> → **Register Your Application** (connecté avec **ton** compte).
   - Nom : « Acces TRN test » (doit être unique sur Twitch)
   - OAuth Redirect URL : `http://localhost:8000/auth/twitch/callback`
   - Catégorie : *Chat Bot* · Type de client : **Confidential**
2. **Manage** → copier le *Client ID* et cliquer sur **New Secret** :
   ```
   TWITCH_CLIENT_ID=...
   TWITCH_CLIENT_SECRET=...
   BOT_SETUP_KEY=<une chaîne de 16 caractères ou plus>
   ```

### A5. Lancer le service
```bash
python -m acces_trn
```
Tu devrais voir `Bot Discord connecté en tant que …` et un avertissement « Bot Twitch pas encore autorisé »
(c'est normal, c'est l'étape suivante). Laisse ce terminal ouvert.

### A6. Autoriser le compte bot Twitch
1. Ouvrir une **fenêtre de navigation privée** (pour ne pas utiliser ta session Twitch).
2. Aller sur `http://localhost:8000/bot/autoriser?cle=<BOT_SETUP_KEY>`.
3. Se connecter avec le **compte du bot** → **Autoriser**.
4. La page « Bot Twitch autorisé » s'affiche ; le terminal indique `Bot Twitch connecté en tant que …`.

### A7. Brancher ta chaîne
1. Dans Discord, `#statut-trn` : taper `/panneau-statut`, puis épingler le message.
2. Taper `/chaine ajouter <ta chaîne Twitch>`.
3. Dans **ton** chat Twitch : `/mod <nom du bot>`.
4. Sur le compte qui recevra les chuchotements (ton compte), vérifier dans Twitch :
   *Paramètres → Sécurité et confidentialité → « Bloquer les chuchotements d'inconnus »* **désactivé**.

### A8. Scénarios à valider (phase A)

| # | Action | Résultat attendu |
|---|---|---|
| 1 | Discord : clic **🔴 Hors ligne**, puis ouvrir `http://localhost:8000` | Page « TRN hors ligne », ressources d'urgence en premier |
| 2 | Discord : clic **🟢 Disponible** | Le panneau devient vert avec l'heure de fin ; la page passe au vert après rechargement |
| 3 | Twitch, sur ta chaîne : `!trn test 1` | La commande disparaît du chat ; tu reçois un chuchotement « ✅ Demande transmise » ; une fiche apparaît dans `#demandes-trn` **avec mention @TRN** |
| 4 | Discord : clic **Je m'en occupe** sur la fiche | La fiche devient verte avec ton nom ; un 2ᵉ clic répond « déjà prise en charge » |
| 5 | Twitch : `!trn test 2` tout de suite après | Chuchotement « ⏳ … Attends 10 minutes » ; **aucune** nouvelle fiche dans Discord |
| 6 | Discord : **🔴 Hors ligne**, attendre 10 min, puis `!trn test 3` | Chuchotement « ⚠️ Aucun·e TRN n'est disponible » ; fiche « (aucun TRN en service) » **sans mention** |
| 7 | Avec un compte viewer (non mod) : `!trn` | Rien : la commande reste visible, pas de chuchotement, pas de fiche |
| 8 | Retirer le bot des mods (`/unmod <bot>`), attendre 10 min, puis `!trn test 4` | La commande **reste** dans le chat (le bot ne peut plus l'effacer) mais la demande passe ; événement `suppression_message_echouee` |
| 9 | Activer « Bloquer les chuchotements d'inconnus », puis `!trn` (après le délai) | Pas de chuchotement, **aucun message public** ; événement `chuchotement_echoue` |
| 10 | Arrêter le service (Ctrl+C), le relancer, cliquer sur un bouton d'une ancienne fiche ou du panneau | Les boutons fonctionnent encore |

Pour voir le journal sans Google Sheets : la page `http://localhost:8000/admin` (mot de passe `ADMIN_PASSWORD`)
montre les changements de statut et les compteurs. Tous les événements sont aussi dans la table `events`
du fichier `data/acces_trn.sqlite3`.

Astuce pour ne pas attendre 10 minutes : mettre `REQUEST_COOLDOWN_MINUTES=1` dans `.env` pendant les tests.

### A9. Google Sheets (facultatif, 10 min)
Suivre [`integrations/google-sheets/README.md`](../integrations/google-sheets/README.md), remplir
`SHEETS_WEBHOOK_URL` et `SHEETS_WEBHOOK_SECRET`, relancer. Les événements des scénarios ci-dessus
apparaissent dans l'onglet « Événements » en quelques secondes. Ceux d'avant sont aussi envoyés :
rien n'est perdu.

---

## Phase B — Extension Twitch (tunnel HTTPS)

Le panneau de l'extension est servi par Twitch en HTTPS et doit joindre ton service en **HTTPS** :
il faut un tunnel. Prends un tunnel avec une **adresse fixe**, pour ne pas devoir tout reconfigurer à
chaque relance : par exemple **ngrok**, dont le compte gratuit offre un domaine fixe.

### B1. Tunnel
1. Installer ngrok, créer un compte et réserver ton domaine gratuit (ex. `ton-nom.ngrok-free.app`).
2. `ngrok http --url=ton-nom.ngrok-free.app 8000`
3. Dans `.env` : `BASE_URL=https://ton-nom.ngrok-free.app`
4. Dans l'application Twitch (étape A4) : **ajouter** la redirection
   `https://ton-nom.ngrok-free.app/auth/twitch/callback` (garder celle de localhost).
5. Relancer le service. Vérifier `https://ton-nom.ngrok-free.app` dans le navigateur.

### B2. Créer l'extension (connecté avec **ton** compte)
1. <https://dev.twitch.tv/console/extensions> → **Create Extension** → nom « Acces TRN test » →
   type **Panel** → **Create Extension Version**.
2. **Asset Hosting** : *Panel Viewer Path* : `panel.html` · *Panel Height* : 500.
3. **Capabilities** → *Allowlist for URL Fetching Domains* : `https://ton-nom.ngrok-free.app` → **Save**.
4. **Extension Settings** (en haut) : copier le *Client ID* et l'**Extension Secret** (*Show* / *Create*) :
   ```
   EXTENSION_CLIENT_ID=...
   EXTENSION_SECRET=...
   ```
   Relancer le service.
5. Dans `extension/config.js` : `window.TRN_BASE_URL = "https://ton-nom.ngrok-free.app";`
6. Compresser **le contenu** du dossier `extension/` (les 4 fichiers à la racine du zip, pas le dossier) :
   ```bash
   cd extension && zip ../extension.zip panel.html panel.js panel.css config.js && cd ..
   ```
7. **Files** → *Upload Version Assets* → `extension.zip`.
8. **Access** → *Testing Account Allowlist* : ajouter **ta chaîne**, et le compte viewer si tu en as un.
9. **Status** → **Move to Hosted Test**.

### B3. Installer le panneau sur ta chaîne (environ 5 clics)
Console → ton extension → **View on Twitch and Install** → **Installer** → **Configurer** ou **Mes extensions**
→ **Activer** → **Panneau 1**. Le panneau apparaît sous ton stream, dans « À propos ».

### B4. Scénarios à valider (phase B)

| # | Action | Résultat attendu |
|---|---|---|
| 11 | Ouvrir ta chaîne (toi = streamer) | Panneau : statut en direct + champ de message et bouton « Demander un·e TRN » |
| 12 | Discord : changer le statut | Le panneau suit en moins de 1 min (ou au rechargement) |
| 13 | Panneau : message + **Demander un·e TRN** | Réponse dans le panneau ; fiche « Via : extension Twitch · <ta chaîne> » dans `#demandes-trn` ; **rien dans le chat** |
| 14 | Redemander tout de suite (panneau ou `!trn`) | « Attends X minutes » : le délai est commun aux deux options |
| 15 | Ouvrir ta chaîne avec le compte viewer | Statut visible, **pas** de formulaire de demande |
| 16 | Nommer le compte viewer mod (`/mod <viewer>`), recharger | Le formulaire apparaît ; la fiche indique « mod (identité non partagée) » ou son pseudo |

---

## En cas de problème

| Symptôme | Piste |
|---|---|
| Les commandes `/panneau-statut` n'apparaissent pas | Le bot a-t-il la portée `applications.commands` ? Relancer le service, attendre 1 min, recharger Discord (Ctrl+R) |
| « Réservé aux TRN » | Le rôle TRN n'est pas attribué, ou `DISCORD_ROLE_ID` ne correspond pas |
| Rien n'arrive dans `#demandes-trn` | Le bot voit-il le salon (permissions du salon privé) ? Bon `DISCORD_REQUESTS_CHANNEL_ID` ? |
| Pas de mention @TRN | Permission *Mention Everyone* pour le bot, ou rendre le rôle mentionnable |
| `!trn` ne fait rien | Le bot est-il autorisé (A6) ? La chaîne est-elle inscrite (`/chaine liste`) ? Message du terminal ? |
| Pas de chuchotement | Téléphone vérifié sur le compte bot ; « Bloquer les chuchotements d'inconnus » désactivé ; voir l'événement `chuchotement_echoue` (le détail donne la raison) |
| Erreur `redirect_mismatch` chez Twitch | L'adresse de redirection de l'application doit être **exactement** `<BASE_URL>/auth/twitch/callback` |
| Panneau d'extension vide ou « Chargement… » | `config.js` pointe-t-il vers le tunnel ? Domaine dans l'*Allowlist* ? Tunnel démarré ? Console du navigateur (F12) |
| Panneau : « jeton invalide » | `EXTENSION_SECRET` / `EXTENSION_CLIENT_ID` ne correspondent pas à l'extension ; relancer après modification |
| Page d'avertissement ngrok dans le navigateur | Normal avec le compte gratuit : cliquer sur « Visit Site ». Le panneau d'extension envoie l'en-tête qui l'évite |
