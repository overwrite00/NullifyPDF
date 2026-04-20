# 🛡️ NullifyPDF

![Version](https://img.shields.io/badge/version-1.2.5-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-windows%20%7C%20macos%20%7C%20linux-lightgrey)
![Python](https://img.shields.io/badge/python-3.8+-yellow)

**NullifyPDF** è un tool open-source cross-platform progettato per l'anonimizzazione **irreversibile** di documenti PDF. A differenza dei comuni editor che si limitano a coprire il testo con rettangoli neri, NullifyPDF elimina fisicamente i dati sensibili dal flusso interno del file, rendendo il recupero impossibile anche tramite strumenti forensi.

![NullifyPDF Promo](/images/NullifyPDF.png)

## ✨ Caratteristiche Principali

* **Processo Irreversibile:** Utilizza il motore PyMuPDF con `apply_redactions()` per rimuovere i dati dal codice sorgente del PDF.
* **Automazione Intelligente:** Rilevamento automatico tramite Regex di Email, Codici Fiscali e dati sensibili comuni.
* **Selezione Manuale:** Interfaccia intuitiva con cursore di precisione per selezionare aree specifiche da censurare.
* **UI Professionale:** Interfaccia moderna in Dark Mode ispirata al design di *Speedtest.net*.
* **Cross-Platform:** Funziona nativamente su Windows, macOS e Linux.
* **Ottimizzazione Finale:** Durante l'esportazione, pulisce i metadati e comprime il file (Garbage Collection livello 4).

## 🚀 Installazione Rapida

Il progetto include uno script di setup automatizzato che configura l'ambiente virtuale (`venv`) e installa tutte le dipendenze necessarie.

1. **Clona il repository:**

    ```bash
    git clone [https://github.com/TuoNomeUtente/NullifyPDF.git](https://github.com/TuoNomeUtente/NullifyPDF.git)
    cd NullifyPDF
    ```

2. **Configura l'ambiente:**

    ```bash
    python setup_env.py
    ```

3. **Attiva l'ambiente:**
    * **Windows:** `.\.venv\Scripts\Activate.ps1`
    * **macOS/Linux:** `source .venv/bin/activate`

4. **Avvia l'applicazione:**

    ```bash
    python NullifyPDF.py
    ```

## 🛠️ Come Funziona la Sicurezza

NullifyPDF non è un semplice editor grafico. Quando viene applicata una censura:

1. Le coordinate del testo o dell'area vengono identificate.
2. Il contenuto viene rimosso dal "Content Stream" della pagina.
3. Viene iniettato un blocco di colore solido (nero) nel livello grafico.
4. In fase di salvataggio, viene eseguita una **Garbage Collection** profonda che elimina gli oggetti orfani e i riferimenti incrociati ai dati originali.

## 🔍 Verifica Forense

Il repository include uno script `PDF_Checker.py` per analizzare i file esportati. Lo script esegue:

* Scansione dei metadati.
* Analisi dei livelli di testo decompressi.
* Ricerca binaria raw (Data Carving) nel codice sorgente del file.

## 📦 Dipendenze

* [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - UI Moderna
* [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/) - Motore PDF
* [Pillow](https://python-pillow.org/) - Gestione immagini

## ⚖️ Disclaimer e Licenza

Questo tool è fornito "così com'è". Sebbene utilizzi tecniche di anonimizzazione professionale, si consiglia sempre di verificare i documenti sensibili con lo script di ispezione incluso prima della condivisione pubblica.

Sviluppato da © 2026 Graziano Mariella — Distribuito sotto licenza MIT. Consulta il file [LICENSE](LICENSE) per i dettagli.
