# Hilfe

## Verwendung

1. Starten Sie `PythonPackageDownloader`

1. Geben Sie die Download-Informationen ein

    Die Bildschirmelemente sind wie folgt:

    | Bildschirmelement | Beschreibung |
    | ---- | ---- |
    | Download-Methode | Erforderlich<br>Wenn PyPISimple und requests nicht installiert sind, wird pip zwangsweise verwendet.<br>pip verwenden: Pakete mit pip download aus der pip-Umgebung herunterladen<br>pip nicht verwenden: Pakete über HTTP herunterladen |
    | Betriebssystem auswählen | Wählen Sie Windows, Linux oder macOS |
    | Python-Version | Erforderlich, Mehrfachauswahl möglich<br>Wählen Sie die Ziel-Python-Version |
    | Paketliste | Erforderlich<br>Geben Sie den Pfad zur Paketliste (Textdatei) an<br>Das Format ist dasselbe wie `requirements.txt` in `pip install -r requirements.txt` |
    | Download-Ziel | Erforderlich<br>Geben Sie den Zielordner für den Download an.<br>Standard ist der downloads-Ordner am Skriptstandort |
    | pip-Pfad | Erforderlich bei Verwendung von pip<br>Sucht nach pip in der Download-Umgebung und zeigt es initial an |
    | Proxy verwenden<br>Benutzer ~ Port | Optional<br>Eingeben, wenn ein Proxy verwendet wird |
    | Quellformat einbeziehen | Optional<br>Wenn der Download fehlschlägt, wird versucht, das tar.gz-Format herunterzuladen |  
    | Abhängigkeiten herunterladen | Prüft Abhängigkeiten der heruntergeladenen Pakete und lädt sie rekursiv herunter<br>Beachten Sie, dass die Verarbeitungszeit je nach Paket zunehmen kann |

    > Drücken Sie die Schaltfläche "Einstellungen speichern", um die Eingaben zu speichern

1. Drücken Sie die Schaltfläche "Download starten"
