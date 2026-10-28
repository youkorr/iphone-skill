# Place Nette

Web app pour iPhone qui aide à **libérer du stockage** et à **donner une seconde vie** à un vieil iPhone. Tout se fait depuis l'iPhone, sans ordinateur.

## Ce qu'elle fait

- **Diagnostic** : tu ajoutes des captures d'écran de *Réglages › Général › Stockage iPhone* (ou tu recopies les chiffres), l'app affiche la barre de stockage et l'espace récupérable.
- **Plan de nettoyage** : actions triées par gain estimé, avec le chemin exact dans les Réglages, le niveau de risque et les étapes. Mesure avant/après.
- **Raccourcis** : recettes pas-à-pas pour l'app Raccourcis. « Analyser mon iPhone » compte photos et vidéos et copie un résultat (`PLACENETTE photos=… videos=…`, les clés `captures=`, `vieilles=` et `ios=` sont aussi lues si présentes) à coller dans le Diagnostic ; la version installée accepte aussi `?r=<résultat>` dans l'adresse. Les autres recettes : ménage des captures, vidéos lourdes, rappel mensuel, économie d'énergie.
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
| `vendor/ocr/` | Lecture des captures : [Tesseract.js](https://github.com/naptha/tesseract.js) 5.1.1 (licence Apache 2.0), données de langue française en base64 et `worker-wrapper.js` qui les sert au worker |

Après une modification de `src/app.html`, lance `./build.sh`.

## Lecture des captures d'écran

La reconnaissance de texte tourne dans Safari, avec des fichiers servis depuis `vendor/ocr/` : les captures ne quittent pas l'iPhone. Environ 5 Mo sont téléchargés la première fois. Les captures en mode sombre sont inversées avant lecture. Les valeurs lues sont affichées pour vérification avant d'être appliquées ; les apps absentes des captures sont déduites de l'espace utilisé indiqué en haut de l'écran. La lecture peut confondre une virgule (1,1 lu 11) : le détail des lignes lues permet de le repérer.

## Limites

iOS isole chaque app : aucune web app ni app de l'App Store ne peut vider le cache des autres apps ou les Données système à ta place. Place Nette te guide vers les bons réglages et estime les gains ; les chiffres affichés sont des estimations.
