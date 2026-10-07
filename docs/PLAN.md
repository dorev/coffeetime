# Plan — Outil d'accès direct aux TRN

> Réponse au document de requis « Projet – Outil d'accès direct aux TRN » (FGV, version de travail).
> Option retenue : **A — aiguillage seulement**. Le service affiche la disponibilité et dirige vers
> le système de tickets Discord existant ; il ne reçoit aucune demande lui-même.

Légende : ✅ fait dans ce dépôt · 🧪 à valider en conditions réelles · ⬜ à faire

---

## 1. Ce qu'on livre

### Livrable 1 — « Lien officiel » (sans serveur, en quelques jours)
Répond à l'**étape 2** et à l'**option 1** du document.

| Élément | État |
|---|---|
| Page statique : explication, bouton vers le Discord, heures habituelles, ressources d'urgence (`livrable1/index.html`) | ✅ |
| Guide de mise en ligne gratuite + invitation Discord permanente (`livrable1/README.md`) | ✅ |
| Adresse officielle, ex. `aide.gardiensvirtuels.org` | ⬜ FGV |
| Commande `!trn` statique, texte à épingler, QR, image de panneau Twitch | ✅ textes · ⬜ image |

### Livrable 2 — Service d'aiguillage (prototype pour le pilote)
Répond aux **options 2, 3 et 4** et à l'**étape 4** du document.

**Public**
- ✅ Page d'accès avec statut en direct (🟢 / 🟡 / 🔴), message de l'équipe, bouton adapté au statut.
- ✅ Ressources d'urgence, affichées **en premier** quand l'équipe est hors ligne.
- ✅ Lien universel `/go` → Discord des TRN (compteur anonyme par provenance).

**Diffuseurs** (intégration unique, mise à jour automatique)
- ✅ `!trn` pour Nightbot, StreamElements, Fossabot via `/status.txt`.
- ✅ Widget Web (`/widget`), incrustation OBS (`/widget?theme=overlay`), badge (`/badge.svg`), QR (`/qr.svg`).
- ✅ Page `/trousse` qui génère tous les extraits pour une chaîne donnée.

**TRN (privé)**
- ✅ Connexion « Se connecter avec Discord » réservée au rôle TRN (ou mot de passe pour les essais).
- ✅ Trois boutons de statut, message public facultatif, durée de validité.
- ✅ Retour automatique à « hors ligne » à échéance (un « disponible » oublié est pire que rien).
- ✅ Journal des changements (qui, quand) et statistiques anonymes sur 30 jours.

**Exploitation**
- ✅ Conteneur Docker + `docker-compose.yml`, configuration par `.env`, données dans un seul fichier SQLite.
- ✅ Tests automatisés (35) : statut et échéance, compteurs, pages, intégrations, connexion, CSRF.

---

## 2. Correspondance avec les critères du document (§6)

| Critère | Réponse |
|---|---|
| Simplicité pour les jeunes | Une page, un bouton, statut en couleur et en mots |
| Nombre d'étapes | Voir l'annonce → clic → page TRN → clic → Discord (le ticket reste dans Discord) |
| Intégration diffuseurs | Une ligne à coller dans le chatbot ; widget/OBS/QR prêts sur `/trousse` |
| Twitch, Discord, Web | Chat Twitch (chatbot), Discord (lien épinglé), Web (page, widget, badge) |
| Afficher la disponibilité | Oui, partout, mis à jour par les TRN |
| Confidentialité | Aucune donnée sur le public : pas d'IP, pas de journal, compteurs agrégés par jour |
| Sécurité des communications | HTTPS ; la conversation se fait dans Discord (inchangé) |
| Coûts | Livrable 1 : 0 $ · Livrable 2 : 0 à ~7 $/mois (VPS) + domaine |
| Maintenance | ~800 lignes Python, 3 dépendances principales, un conteneur |
| Évolutivité | Le statut et les compteurs sont la base d'un futur portail (option 5) |
| Contrôle FGV | Code et données chez la FGV, hébergement au choix |
| Dépendance externe | Discord reste le canal d'intervention ; le point d'entrée, lui, appartient à la FGV |

---

## 3. Parcours

**Personne qui cherche de l'aide** : voit `!trn`, le widget ou le QR → arrive sur la page →
lit le statut → clique « Parler à un·e TRN » / « Laisser une demande » → serveur Discord des TRN →
ouvre un ticket.

**Diffuseur** : reçoit le lien `/trousse?src=sa_chaine` → copie la commande dans son chatbot,
ajoute le widget OBS ou le QR → terminé.

**TRN** : début de quart → `/admin` → « 🟢 Disponible » (4 h) → au besoin « 🟡 Occupée » →
fin de quart « 🔴 Hors ligne » (sinon retour automatique à échéance).

---

## 4. Étapes

### Étape 1 — Cadrage avec la FGV ⬜
- [ ] Définir **« disponible »** et **« occupée »** concrètement (ex. : occupée = tous les TRN en intervention).
- [ ] Heures de présence et durée par défaut d'un statut.
- [ ] Décrire le parcours actuel des tickets Discord : combien d'étapes après l'invitation ?
- [ ] Valider les textes (`texts.py`) et les ressources d'urgence.
- [ ] Choisir le nom de domaine et la personne responsable de l'hébergement.

### Étape 2 — Livrable 1 en ligne ⬜ (1 à 3 jours)
- [ ] Adapter et publier `livrable1/index.html`, brancher le domaine.
- [ ] Invitation Discord permanente + *Onboarding* vers le salon des tickets.
- [ ] Remettre la commande statique et le QR à 2 ou 3 diffuseurs.

### Étape 3 — Livrable 2 : mise en service ✅ code · ⬜ déploiement (1 à 2 jours)
- [ ] Application Discord OAuth (voir README), `.env` de production.
- [ ] Hébergement (VPS canadien ou serveur FGV) + Caddy (HTTPS).
- [ ] Faire pointer le domaine officiel vers le service.
- [ ] 🧪 Tester la connexion Discord avec un compte TRN et un compte sans le rôle.

### Étape 4 — Recette 🧪 (½ journée, avec 1 ou 2 TRN)
| # | Vérification | Attendu |
|---|---|---|
| 1 | Page d'accès sur téléphone, en mode clair et sombre | Lisible, bouton évident |
| 2 | TRN passe à 🟢 | Page, widget, badge, `!trn` changent en ≤ 1 min |
| 3 | Laisser expirer le statut | Retour à 🔴 et ressources en premier |
| 4 | `!trn` dans un vrai chat (Nightbot et StreamElements) | Une ligne, lien cliquable |
| 5 | Widget dans OBS | Fond transparent, mise à jour seule |
| 6 | Compte Discord sans le rôle TRN | Accès refusé |
| 7 | Clic « Parler à un·e TRN » sans compte Discord | Noter le parcours réel (création de compte) |

### Étape 5 — Pilote ⬜ (2 à 4 semaines, 3 à 5 diffuseurs)
Mesures (document §8, étape 5) : visites, clics, utilisations de `!trn` **par diffuseur** (tableau de
l'espace TRN) ; nombre de tickets ouverts (côté Discord) ; retours des TRN et des diffuseurs.

### Étape 6 — Déploiement au réseau ⬜
Trousse finalisée (images de panneau, guide d'une page), annonce aux diffuseurs, maintenance.

---

## 5. Confidentialité (Loi 25) et sécurité

- **Public** : aucune donnée personnelle collectée ni stockée. Uvicorn ne journalise pas les accès ;
  le proxy (Caddy) est configuré sans journal. Compteurs = (jour, type, provenance, nombre).
- **TRN** : seuls le nom d'affichage et l'heure des changements de statut sont conservés (200 derniers).
  Le jeton Discord n'est pas conservé ; la session expire après 12 h.
- **Protections** : cookies signés (HttpOnly, Secure en HTTPS), jeton CSRF sur chaque formulaire,
  blocage après 5 mots de passe erronés, en-têtes de sécurité (CSP, no-referrer), espace TRN non intégrable.
- **Urgence** : le service n'est pas un service d'urgence ; les ressources 24/7 sont toujours visibles.

---

## 6. Limites connues et suites possibles

| Limite | Piste |
|---|---|
| Il faut un compte Discord (13 ans et plus) pour parler à un TRN | Option B / portail (option 5) : formulaire ou clavardage Web — à évaluer après le pilote |
| Le statut dépend des TRN qui le mettent à jour | Échéance automatique ; plus tard : lecture du nombre de tickets ouverts |
| Les images dans Discord sont mises en cache | Pour Discord, utiliser le lien et le texte plutôt que le badge |
| Une seule équipe, un seul statut | Plusieurs files (langues, régions) si le besoin apparaît |

Pistes après le pilote : statut automatique selon l'horaire, rappel aux TRN si 🟢 depuis longtemps
sans ticket, page en anglais, image PNG du badge pour Discord.
