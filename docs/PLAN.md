# Plan — Outil d'accès direct aux TRN

> Mis à jour après la rencontre avec la FGV. Principe : **le moins d'effort possible pour les TRN
> et pour les streamers**. Deux façons de faire une demande : la commande chat et l'extension Twitch
> (la page Web avec connexion Twitch a été retirée pour simplifier).

Légende : ✅ fait dans ce dépôt · 🧪 à valider en conditions réelles · ⬜ à faire

---

## 1. Décisions de la rencontre

| Question | Décision |
|---|---|
| Comment un TRN indique son statut ? | Dans **Discord**, le plus simplement possible → panneau à 3 boutons |
| Statistiques ? | Journal des événements dans un **Google Sheets** |
| Infos d'une demande ? | **Chaîne + heure** (+ message facultatif, + pseudo du mod) |
| Contact avec la personne ? | Géré par les TRN (pas à construire) |
| Qui fait la demande ? | **Streamer et mods**, avec anti-spam : **10 minutes** par chaîne |
| Aucun TRN disponible ? | La demande est **quand même enregistrée** ; le mod est prévenu |
| Message facultatif ? | Va dans **Discord et dans le Google Sheets** |
| Ajout des chaînes (pilote) ? | Par les TRN, **dans Discord** (`/chaine ajouter`) |
| Commande publique pour les viewers ? | **Non** |
| Compte Twitch du bot ? | Créé par les TRN (téléphone vérifié, pour les chuchotements) |
| Réponse au mod (commande chat) | **Chuchotement seulement**, commande effacée. Jamais de message public, même si le quota est atteint : l'échec est enregistré |

---

## 2. Ce qui est construit

### Côté TRN (Discord) ✅ · 🧪
- Panneau de statut épinglé : 🟢 Disponible / 🟡 Occupé·e / 🔴 Hors ligne, un clic. Retour automatique
  à « hors ligne » après `DEFAULT_DURATION_HOURS`. Le panneau se met à jour seul (échéance, page de secours).
- Salon des demandes : chaîne, heure, source, pseudo du mod, message ; bouton **Je m'en occupe**.
  Mention du rôle TRN seulement quand l'équipe est en service.
- `/chaine ajouter|retirer|liste` : inscription des chaînes ; le bot rappelle les étapes pour le streamer.

### Côté streamers et mods — deux options ✅ · 🧪
| | 1. Commande chat `!trn` | 2. Extension Twitch |
|---|---|---|
| Discrétion | commande visible ~1 s puis effacée | totale |
| Vérification du rôle | badge du chat | jeton signé par Twitch |
| Réponse au mod | chuchotement (jamais public) | dans le panneau |
| Effort du streamer | `/mod NomDuBot` | installer l'extension (~5 clics) |
| Pré-requis FGV | compte bot vérifié | extension en *hosted test* |

Règles communes (`dispatch.py`) : chaîne inscrite, **10 minutes** entre deux demandes d'une chaîne
(les demandes bloquées ne prolongent pas le délai), tout est enregistré.

### Côté viewers ✅
Signal public de disponibilité : page d'accès, widget, incrustation OBS, badge, panneau d'extension.
Bouton « Parler à un·e TRN » vers le Discord des TRN.

### Journal (Google Sheets) ✅ · 🧪
Événements : `statut_change`, `demande_envoyee`, `demande_sans_trn`, `demande_bloquee_delai`,
`demande_refusee`, `demande_prise_en_charge`, `chuchotement_echoue`, `suppression_message_echouee`,
`chaine_ajoutee`, `chaine_retiree`, `bot_twitch_autorise`. Copie locale + renvoi automatique si la feuille
est injoignable.

### Qualité ✅
73 tests automatisés (Twitch, Discord et Google Sheets simulés) : délai, enregistrement, chiffrement
des jetons du bot, extension (rôles, jetons expirés, CORS), commande chat (mods seulement, chuchotement échoué).

---

## 3. Étapes

### Étape 1 — Comptes et accès (FGV, ~1 h) ⬜
- [ ] Application Discord + bot invité dans le serveur des TRN ; rôle TRN ; salon des demandes.
- [ ] Application Twitch (redirection `<BASE_URL>/auth/twitch/callback`, pour autoriser le bot).
- [ ] Compte Twitch du bot, téléphone vérifié.
- [ ] Google Sheets + Apps Script (`integrations/google-sheets/`).
- [ ] Hébergement : à décider (VPS, serveur FGV, Oracle Free) + domaine + HTTPS.

### Étape 2 — Mise en service (1 journée) ⬜
- [ ] `.env` de production, `docker compose up -d`, Caddy.
- [ ] `/bot/autoriser?cle=…` avec le compte du bot.
- [ ] `/panneau-statut` dans Discord ; `/chaine ajouter` pour 2-3 chaînes test.
- [ ] Extension : création dans la console, *hosted test* avec les chaînes du pilote (voir `docs/EXTENSION.md`).

### Étape 3 — Recette 🧪 (½ journée, avec 1-2 TRN et 1 streamer)
| # | Vérification | Attendu |
|---|---|---|
| 1 | Clic 🟢 dans Discord | Page, widget, extension passent au vert en ≤ 1 min ; ligne `statut_change` |
| 2 | `!trn test` par un mod | Commande effacée, chuchotement reçu, demande dans Discord + Sheets |
| 3 | `!trn` par un viewer | Rien ne se passe |
| 4 | 2ᵉ demande < 10 min (n'importe quelle option) | « Attends X minutes » ; ligne `demande_bloquee_delai` |
| 5 | Demande avec 🔴 | Publiée sans mention ; mod prévenu avec les ressources ; `demande_sans_trn` |
| 6 | Extension : viewer vs mod | Le viewer voit le statut seulement ; le mod voit le formulaire |
| 7 | Chuchotement bloqué (réglages du mod) | Pas de message public ; `chuchotement_echoue` dans le Sheets |
| 8 | Couper Internet 2 min | Les lignes manquantes arrivent dans le Sheets au retour |

### Étape 4 — Pilote ⬜ (2-4 semaines, 3-5 chaînes)
Mesurer, par option : nombre de demandes, demandes bloquées, échecs de chuchotement, délai de prise en
charge (`demande_envoyee` → `demande_prise_en_charge`), retours des mods et des TRN.
**Décision de fin de pilote : quelles options garder.**

### Étape 5 — Après le pilote ⬜
- Si l'extension est retenue : soumission à la review Twitch (voir `docs/EXTENSION.md`).
- Trousse d'intégration finale ; inscription des chaînes en libre-service si le réseau grandit.

---

## 4. Limites connues

| Limite | Mitigation |
|---|---|
| Commande chat visible ~1 s | L'extension est totalement discrète |
| Chuchotements : téléphone vérifié + quotas Twitch | Échecs enregistrés ; l'extension n'en dépend pas |
| Extension : approbation Twitch pour une diffusion large | Pilote en *hosted test*, sans approbation |
| Extension : pseudo du mod seulement s'il partage son identité | Sinon « mod (identité non partagée) » ; la chaîne et l'heure suffisent |
| Panneaux d'extension sur mobile | À vérifier pendant le pilote ; la commande chat fonctionne partout |
| Statut oublié | Retour automatique à « hors ligne » |
