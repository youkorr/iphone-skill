# Place Nette

Web app pour iPhone qui aide à **libérer du stockage** et à **donner une seconde vie** à un vieil iPhone. Tout se fait depuis l'iPhone, sans ordinateur.

## Ce qu'elle fait

- **Diagnostic** : tu recopies les chiffres de *Réglages › Général › Stockage iPhone*, l'app affiche la barre de stockage et l'espace récupérable.
- **Plan de nettoyage** : actions triées par gain estimé, avec le chemin exact dans les Réglages, le niveau de risque et les étapes. Mesure avant/après.
- **Raccourcis** : recettes pas-à-pas pour l'app Raccourcis (captures d'écran, vidéos lourdes, rappel mensuel, économie d'énergie).
- **Seconde vie** : santé de la batterie, réglages de fluidité, idées de reconversion, checklist avant revente ou don.

Rien n'est envoyé : les données restent dans le navigateur de l'iPhone (`localStorage`). Une fois installée, l'app fonctionne hors ligne.

## Installer sur l'iPhone

1. Ouvre l'adresse GitHub Pages du dépôt dans **Safari**.
2. Touche **Partager › Sur l'écran d'accueil**.

## Structure

| Fichier | Rôle |
|---|---|
| `src/app.html` | Source de l'app (styles, contenu, logique) |
| `build.sh` | Génère `index.html` (ajoute l'en-tête PWA et le service worker) |
| `index.html` | Version publiée, générée — ne pas modifier à la main |
| `manifest.webmanifest`, `sw.js`, `icons/` | Installation et mode hors ligne |

Après une modification de `src/app.html`, lance `./build.sh`.

## Limites

iOS isole chaque app : aucune web app ni app de l'App Store ne peut vider le cache des autres apps ou les Données système à ta place. Place Nette te guide vers les bons réglages et estime les gains ; les chiffres affichés sont des estimations.
