# Aide

## Utilisation

1. Lancez `PythonPackageDownloader`

1. Saisissez les informations de téléchargement

    Les éléments de l'écran sont les suivants :

    | Élément d'écran | Description |
    | ---- | ---- |
    | Méthode de téléchargement | Obligatoire<br>Si PyPISimple et requests ne sont pas installés, pip sera utilisé de force.<br>Utiliser pip : Télécharger les paquets en utilisant pip download avec le pip de l'environnement de téléchargement<br>Ne pas utiliser pip : Télécharger les paquets en utilisant HTTP |
    | Sélectionner le système d'exploitation | Sélectionnez Windows, Linux ou macOS |
    | Version Python | Obligatoire, sélection multiple autorisée<br>Sélectionnez la version Python cible |
    | Liste des paquets | Obligatoire<br>Spécifiez le chemin vers la liste des paquets (fichier texte)<br>Le format est le même que `requirements.txt` utilisé dans `pip install -r requirements.txt` |
    | Destination de téléchargement | Obligatoire<br>Spécifiez le dossier de destination du téléchargement.<br>Par défaut, c'est le dossier downloads à l'emplacement du script |
    | Chemin de pip | Obligatoire lors de l'utilisation de pip<br>Recherche pip dans l'environnement de téléchargement et l'affiche initialement |
    | Utiliser un proxy<br>Utilisateur ~ Port | Optionnel<br>Saisissez si vous utilisez un proxy |
    | Inclure le format source | Optionnel<br>Si le téléchargement échoue, tentez de télécharger le format tar.gz |  
    | Télécharger les dépendances | Vérifie les dépendances des paquets téléchargés et télécharge récursivement<br>Notez que le temps de traitement peut augmenter selon le paquet |

    > Appuyez sur le bouton « Enregistrer les paramètres » pour sauvegarder les éléments saisis

1. Appuyez sur le bouton « Démarrer le téléchargement »
