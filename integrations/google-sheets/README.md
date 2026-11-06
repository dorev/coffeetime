# Journal des événements dans Google Sheets

Chaque événement du service (changement de statut, demande d'une chaîne, demande bloquée par le
délai de 10 minutes, demande sans TRN disponible, prise en charge, chuchotement échoué, chaîne
ajoutée…) est ajouté comme une ligne dans une feuille Google Sheets de la FGV.

Les événements sont aussi conservés dans la base locale : si la feuille est injoignable,
ils sont renvoyés automatiquement plus tard (rien n'est perdu).

## Installation (environ 5 minutes)

1. Créer une feuille Google Sheets (ex. « Accès TRN — journal »).
2. Menu **Extensions → Apps Script**. Remplacer le contenu de `Code.gs` par celui de ce dossier. Enregistrer.
3. **Paramètres du projet** (roue dentée) → **Propriétés du script** → ajouter
   `WEBHOOK_SECRET` = une longue chaîne aléatoire.
4. **Déployer → Nouveau déploiement** → type **Application Web** :
   - Exécuter en tant que : **Moi**
   - Qui a accès : **Tout le monde** (le secret protège l'accès)
   - Autoriser l'accès quand Google le demande.
5. Copier l'**URL de l'application Web** dans `.env` :
   ```
   SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/…/exec
   SHEETS_WEBHOOK_SECRET=<la même chaîne qu'à l'étape 3>
   ```

Un onglet « Événements » est créé automatiquement à la première ligne reçue.

## Colonnes

| Colonne | Exemple |
|---|---|
| Horodatage (UTC) | 2026-11-06T02:41:07+00:00 |
| Événement | `demande_envoyee`, `demande_sans_trn`, `demande_bloquee_delai`, `demande_refusee`, `demande_prise_en_charge`, `statut_change`, `chuchotement_echoue`, `suppression_message_echouee`, `chaine_ajoutee`, `chaine_retiree`, `bot_twitch_autorise` |
| Chaîne | machaine |
| Source | `chat` (commande !trn), `page` (page /c/…), `extension`, `discord`, `web` |
| Personne | pseudo du mod, ou nom du TRN |
| Message | message facultatif du mod |
| Statut TRN | `available`, `busy`, `offline` au moment de l'événement |
| Détail | numéro de demande, raison d'un échec… |

Astuce : un tableau croisé dynamique sur « Chaîne » × « Événement » donne directement les
statistiques du pilote.
