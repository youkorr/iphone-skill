# Place Nette pour Pythonista

Version « app » de Place Nette, qui tourne dans [Pythonista 3](https://apps.apple.com/app/id1085978097) (9,99 €, App Store). Sans compte développeur ni ordinateur, elle lit directement :

- l'espace libre et la capacité de l'iPhone ;
- toutes les photos et vidéos avec leur taille réelle ;
- les vidéos les plus lourdes, les captures d'écran et les doublons probables (mêmes dimensions, même taille au octet près).

Elle guide aussi le nettoyage de WhatsApp, TikTok, Instagram, Snapchat, Telegram, Facebook, Spotify, YouTube, Netflix, Notes et Messages (avec un bouton pour ouvrir chaque app), et peut lister les fichiers les plus lourds d'un dossier de l'app Fichiers.

On coche ce qu'on veut supprimer ; iOS demande confirmation et les éléments passent par « Supprimés récemment ».

## Installer ou mettre à jour

Dans Pythonista, ouvre la **console** et colle cette ligne :

```python
import requests,os;open(os.path.expanduser('~/Documents/Place Nette.py'),'wb').write(requests.get('https://raw.githubusercontent.com/youkorr/iphone-skill/claude/place-nette-pwa/pythonista/place_nette.py').content)
```

Puis ouvre **Place Nette.py** dans la bibliothèque et touche ▶. La même ligne installe la dernière version.

## Limites

Aucune app ne peut vider le cache des autres apps ni les Données système, ni lire la santé de la batterie. Si iOS ne fournit pas la taille d'un fichier, elle est estimée (3 Mo par photo, 1,5 Mo par seconde de vidéo) et l'écran le signale.
