# Livrable 1 — « Lien officiel » (sans serveur)

Mise en place en quelques jours, **sans programmation ni hébergement payant**.
Le statut n'est pas en direct : on affiche les heures habituelles. Le livrable 2
(le service d'aiguillage, à la racine du dépôt) prend ensuite le relais **à la même adresse**.

## Étapes

1. **Page** : modifier les 2 valeurs marquées `À MODIFIER` dans [`index.html`](index.html)
   (invitation Discord, heures de présence) et faire valider les ressources d'urgence.
2. **Hébergement gratuit** (au choix) : GitHub Pages, Cloudflare Pages ou Netlify,
   ou simplement une page du site actuel de la FGV.
3. **Adresse officielle** : un sous-domaine comme `aide.gardiensvirtuels.org` pointant vers cette page.
   C'est **cette adresse** qu'on diffuse partout : elle ne changera plus, même au livrable 2.
4. **Invitation Discord** : créer une invitation **permanente** (« N'expire jamais », usages illimités),
   idéalement vers le salon des tickets. Activer l'*Onboarding* du serveur pour que les nouvelles
   personnes arrivent directement sur ce salon.
5. **Trousse diffuseurs** (version simple) :
   - commande Twitch statique, ex. Nightbot :
     `!addcom !trn 💬 Besoin de parler à quelqu'un ? Les TRN sont là pour toi : https://aide.gardiensvirtuels.org — Urgence : 911 · Détresse : 988`
   - le même texte à épingler dans leur Discord et à mettre dans leur bio Twitch ;
   - un code QR vers l'adresse officielle (n'importe quel générateur, ou `/qr.svg` du livrable 2) ;
   - une image de panneau Twitch « Parler à un TRN » avec le lien.

## Passage au livrable 2

On déploie le service d'aiguillage et on fait pointer **la même adresse** vers lui.
Les diffuseurs remplacent ensuite leur commande statique par la commande dynamique
(une ligne, fournie sur la page `/trousse`).
