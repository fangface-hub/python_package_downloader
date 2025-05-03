# Aiuto

## Utilizzo

1. Avviare `PythonPackageDownloader`

1. Inserire le informazioni di download

    Gli elementi dello schermo sono i seguenti:

    | Elemento dello schermo | Descrizione |
    | ---- | ---- |
    | Metodo di download | Obbligatorio<br>Se PyPISimple e requests non sono installati, pip verrà utilizzato forzatamente.<br>Usa pip: Scarica i pacchetti usando pip download con il pip nell'ambiente di download<br>Non usare pip: Scarica i pacchetti usando HTTP |
    | Seleziona sistema operativo | Selezionare Windows, Linux o macOS |
    | Versione Python | Obbligatorio, selezione multipla consentita<br>Selezionare la versione Python di destinazione |
    | Elenco pacchetti | Obbligatorio<br>Specificare il percorso dell'elenco dei pacchetti (file di testo)<br>Il formato è lo stesso di `requirements.txt` usato in `pip install -r requirements.txt` |
    | Destinazione download | Obbligatorio<br>Specificare la cartella di destinazione del download.<br>Il valore predefinito è la cartella downloads nella posizione dello script |
    | Percorso pip | Obbligatorio quando si usa pip<br>Cerca pip nell'ambiente di download e lo visualizza inizialmente |
    | Usa proxy<br>Utente ~ Porta | Opzionale<br>Inserire se si utilizza un proxy |
    | Includi formato sorgente | Opzionale<br>Se il download fallisce, tentare di scaricare il formato tar.gz |  
    | Scarica dipendenze | Controlla le dipendenze dei pacchetti scaricati e scarica ricorsivamente<br>Notare che il tempo di elaborazione può aumentare a seconda del pacchetto |

    > Premere il pulsante "Salva impostazioni" per salvare gli elementi inseriti

1. Premere il pulsante "Avvia download"
