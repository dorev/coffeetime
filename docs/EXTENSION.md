# Extension Twitch « Accès TRN » (option 2)

Un panneau interactif sous le stream :
- **tout le monde** voit le statut des TRN en direct (🟢 / 🟡 / 🔴) et un bouton « Parler à un·e TRN » ;
- **le streamer et ses mods** voient en plus un champ de message et un bouton « Demander un·e TRN ».
  Twitch indique lui-même le rôle de la personne à l'extension : **aucune connexion n'est demandée**
  et rien n'apparaît dans le chat.

Le code du panneau est dans [`extension/`](../extension/). Le serveur vérifie le jeton signé par Twitch
(`/ext/info`, `/ext/demande`) : un viewer ne peut pas faire de demande, même en trafiquant le panneau.

## Côté FGV : créer et publier l'extension

1. <https://dev.twitch.tv/console/extensions> → **Create Extension** (nom : « Accès TRN »), type **Panel**.
2. **Version settings**
   - *Panel height* : 500.
   - *Capabilities → Allowlist for URL Fetching Domains* : l'adresse du service (`BASE_URL`).
   - *Identity* : facultatif. Sans partage d'identité, la demande est enregistrée « mod (identité non partagée) ».
3. **Extension settings** : copier le *Client ID* et l'*Extension Secret* dans `.env`
   (`EXTENSION_CLIENT_ID`, `EXTENSION_SECRET`).
4. Modifier `extension/config.js` (adresse du service), puis compresser **le contenu** du dossier
   `extension/` en `.zip` et le téléverser (*Files → Upload Version Assets*).
5. **Access → Testing Account Allowlist** : ajouter les comptes Twitch des streamers du pilote.
6. **Move to Hosted Test** : l'extension fonctionne alors sur les chaînes de la liste, **sans approbation**.

### L'approbation (review) par Twitch

Nécessaire seulement pour que **n'importe quel** streamer puisse l'installer (hors liste de test).

- Les étapes : local test → **hosted test** (pilote, sans approbation) → **review** → release.
- À fournir : nom, descriptions, icône, captures d'écran, **une chaîne de démonstration** et un mode
  d'emploi pour l'équipe de révision. Seul le code du panneau est examiné, pas le serveur.
- Twitch vérifie le respect des règles, le fonctionnement et le code. Il est possible de revenir en test,
  corriger et resoumettre.
- **Délai** : Twitch ne publie pas de délai officiel ; prévoir de quelques jours à quelques semaines.
- Attention : après l'approbation, modifier la liste d'accès oblige à resoumettre.

**Recommandation** : faire tout le pilote en *hosted test* (liste de streamers), et soumettre à la review
seulement si l'extension est retenue après le pilote.

## Côté streamer : installer le panneau (environ 5 clics)

1. Ouvrir le lien d'installation fourni par la FGV (page de l'extension) — ou
   *Tableau de bord des créateurs → Extensions → Découvrir* et chercher « Accès TRN ».
2. **Installer**.
3. Aller dans **Mes extensions**.
4. **Activer**.
5. Choisir **Activer en tant que panneau** (Panneau 1, 2 ou 3).

Aucune configuration. Le panneau apparaît sous le stream, dans la section « À propos ».
Twitch permet 3 panneaux d'extension actifs par chaîne.

À vérifier pendant le pilote : l'affichage des panneaux d'extension dans l'application mobile Twitch.

## Explorer des extensions existantes

- Catalogue (connexion Twitch requise) : <https://dashboard.twitch.tv/extensions>
- Guide officiel : <https://link.twitch.tv/HowToUseExtensions>
- Documentation développeur : <https://dev.twitch.tv/docs/extensions/> ·
  cycle de vie et review : <https://dev.twitch.tv/docs/extensions/life-cycle/> ·
  bonnes pratiques de soumission : <https://dev.twitch.tv/docs/extensions/submission-best-practices/>
