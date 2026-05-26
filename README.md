# NullifyPDF - AI Forensic Edition

![GitHub Release](https://img.shields.io/github/v/release/overwrite00/NullifyPDF?style=flat-square&color=1fb2e0)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/overwrite00/NullifyPDF/release.yml?style=flat-square&label=build)
![GitHub License](https://img.shields.io/github/license/overwrite00/NullifyPDF?style=flat-square&color=blue)
![Python Version](https://img.shields.io/badge/python-3.12-blue?style=flat-square&logo=python)

<p align="center">
  <img src="images/NullifyPDF.png" alt="NullifyPDF">
</p>

> **NullifyPDF** è uno strumento professionale per l'anonimizzazione forense dei PDF. Progettato per la privacy assoluta, opera interamente in locale utilizzando l'intelligenza artificiale per identificare e distruggere permanentemente dati sensibili senza mai caricare file nel cloud.

## 📖 Documentazione Rapida

Se è la prima volta che usi NullifyPDF, consulta la nostra [**Guida Utente Passo dopo Passo**](./GUIDA_UTENTE.md)

---

## 📍 Contenuti

- [NullifyPDF - AI Forensic Edition](#nullifypdf---ai-forensic-edition)
  - [📖 Documentazione Rapida](#-documentazione-rapida)
  - [📍 Contenuti](#-contenuti)
  - [📝 Descrizione del Progetto](#-descrizione-del-progetto)
    - [🛠️ Tecnologie utilizzate](#️-tecnologie-utilizzate)
  - [✨ Caratteristiche principali](#-caratteristiche-principali)
  - [⚠️ Limiti dello Strumento (Cosa NON fa)](#️-limiti-dello-strumento-cosa-non-fa)
  - [🚀 Guida all'uso](#-guida-alluso)
  - [🛠️ Come utilizzarlo](#️-come-utilizzarlo)
    - [⚙️ Installazione](#️-installazione)
    - [🤖 Script di automazione (Sviluppo e compilazione in locale)](#-script-di-automazione-sviluppo-e-compilazione-in-locale)
  - [💾 Download release](#-download-release)
  - [⚖️ Licenza](#️-licenza)
  - [👤 Info Autore](#-info-autore)

---

## 📝 Descrizione del Progetto

NullifyPDF va oltre la semplice copertura visiva del testo. Utilizza motori di *Natural Language Processing* (**NLP**) per comprendere il contesto e individuare entità come *nomi*, *indirizzi*, *indirizzi email*, *IBAN* e *numeri di carte di credito*. A differenza dei comuni editor PDF, questo tool esegue uno "scrubbing" forense, eliminando metadati, hyperlink e livelli vettoriali nascosti per garantire che la censura sia irreversibile.

### 🛠️ Tecnologie utilizzate

- **Python 3.12**: Versione supportata (richiesta per compatibilità con PyMuPDF wheel pre-compilate)
- **PySide6 (Qt6)**: Nuovo motore grafico con nterfaccia grafica moderna in Dark Mode.
- **PyMuPDF (fitz)**: Motore ad alte prestazioni per la manipolazione di PDF.
- **Microsoft Presidio & spaCy**: Motori AI per il riconoscimento delle entità (NER).

[Back To The Top](#nullifypdf---ai-forensic-edition)

---

## ✨ Caratteristiche principali

- 🧠 **AI-Powered Redaction:** Riconoscimento automatico bilingue (IT/EN) di PII (Nomi, Luoghi, Email, Telefoni, IBAN, Carte di Credito, Crypto).
- 🗄️ **UI Fluida & Thread-Safe:** Grazie all'integrazione di PySide6 e all'architettura Multithread, l'interfaccia non si blocca mai durante l'analisi AI. Estrazione testo in worker thread con serialization QMutex per document access sicuro.
- 📖 **Dizionari Intelligenti Persistenti:** Blocklist e Allowlist globali sincronizzate su disco (`~/.nullifypdf`) con logica di mutua esclusività e sistema anti-stacking delle censure. Fast-path O(1) per exact-match su allowlist grandi.
- 🛡️ **Forensic Scrubbing:** Non si limita a "colorare di nero". In fase di export, distrugge fisicamente i metadati, rimuove i link nascosti e appiattisce i moduli interattivi (AcroForms). Memory-efficient disk-backed export.
- 🖼️ **Blindfold Mode (Sostituzione Immagini):** Interruttore dedicato per censurare automaticamente tutte le immagini, loghi o QR code, sostituendoli con un segnaposto professionale `[ IMMAGINE RIMOSSA ]`.
- 📦 **Cross-Platform nativo:** Script di build integrati per generare `.exe` (Windows), `.app` bundle (macOS), e pacchetti `.deb`/`.rpm` (Linux).
- **Drag & Drop:** Supporto nativo per il trascinamento dei file sulla finestra.
- 📊 **Logging & Diagnostica:** File-based logging con rotation automatica (`~/.nullifypdf/logs/`) e debug mode per troubleshooting avanzato.

[Back To The Top](#nullifypdf---ai-forensic-edition)

---

## ⚠️ Limiti dello Strumento (Cosa NON fa)

Per garantire che NullifyPDF rimanga un software leggero, 100% offline e sicuro, sono presenti alcuni limiti tecnici di cui l'utente deve essere consapevole:

1. **Nessun OCR (Optical Character Recognition) Integrato:**
    L'intelligenza artificiale analizza solo il *testo vettoriale/digitale*. Se carichi un PDF che è una scansione o una fotografia (es. la foto di una patente), l'AI non "leggerà" il testo al suo interno.
    - *Soluzione integrata:* Utilizzare la funzione **"Oscura Immagini"** per rimuovere preventivamente l'intero blocco fotografico.
2. **Testo Scritto a Mano:**
    I modelli NLP non sono in grado di analizzare la grafia umana non digitalizzata.
3. **PDF Protetti da Password / Criptati:**
    NullifyPDF non è uno strumento di cracking. Se un documento richiede una password per l'apertura o ha restrizioni di estrazione DRM, il file verrà bloccato in fase di caricamento. È necessario decriptare il file prima di importarlo.
4. **Invalidazione delle Firme Digitali:**
    Poiché il processo di "Forensic Scrubbing" distrugge fisicamente oggetti nel codice binario del PDF per garantire la privacy, qualsiasi firma crittografica digitale (es. PAdES, firme notarili) presente sul documento originale risulterà logicamente e matematicamente invalidata nel file esportato.

[Back To The Top](#nullifypdf---ai-forensic-edition)

---

## 🚀 Guida all'uso

L'utilizzo è estremamente intuitivo. Per una spiegazione dettagliata di tutte le funzioni (Zoom, AI, Dizionari), leggi la nostra **[Guida Utente](./GUIDA_UTENTE.md)** oppure puoi scaricare la versione in PDF [Guida Utente NullifyPDF - Passo dopo Passo](Guida%20Utente%20NullifyPDF%20-%20Passo%20dopo%20Passo.pdf)

[Back To The Top](#nullifypdf---ai-forensic-edition)

---

## 🛠️ Come utilizzarlo

### ✅ Requisiti di Sistema

- **Python 3.12** (obbligatorio - compatibilità con le wheel pre-compilate di PyMuPDF)
  - **Windows**: Usa il launcher `py -3.12` (incluso in Python)
  - **macOS/Linux**: Installa `python3.12` tramite package manager (brew, apt, dnf, ecc.)
- **Spazio disco**: ~2 GB per dipendenze + modelli spaCy
- **RAM**: Minimo 4 GB (consigliato 8 GB per PDF grandi)

### ⚙️ Installazione

Se sei uno sviluppatore e vuoi eseguire il codice sorgente (consigliato usare lo script di automazione):

1. 📥 **Clona il repository**:

   ```bash
   git clone https://github.com/overwrite00/NullifyPDF.git
   cd NullifyPDF
   ```

2. 🐍 **Verifica di avere Python 3.12**:

   ```bash
   # Windows
   py -3.12 --version
   
   # macOS/Linux
   python3.12 --version
   ```

3. 🤖 **Usa lo script di setup automatico** (consigliato):

   ```bash
   python setup_env.py
   ```
   
   Lo script creerà automaticamente il venv, installerà tutte le dipendenze e scaricherà i modelli spaCy.

4. 🚀 **Avvia l'applicazione**:

   ```bash
   # Attiva il venv (se non già attivato)
   # Windows: .\.venv\Scripts\Activate.ps1
   # macOS/Linux: source .venv/bin/activate
   
   python NullifyPDF.py
   ```

### 🤖 Script di automazione (Sviluppo e compilazione in locale)

Per facilitare al massimo la vita agli sviluppatori e ai contributor, la repository include due script Python multipiattaforma che automatizzano l'intero ciclo di vita dello sviluppo:

1. **Setup dell'Ambiente (`setup_env.py`)**

   Crea un ambiente virtuale isolato (`.venv`) **con Python 3.12**, aggiorna i tool di base, installa tutte le dipendenze (`requirements`) e scarica in automatico i modelli NLP di spaCy (EN/IT).

   ```bash
   python setup_env.py
   ```

   **Supporto multipiattaforma automatico:**
   - **Windows**: Usa `py -3.12` (launcher Python)
   - **macOS/Linux**: Usa `python3.12` (richiede Python 3.12 installato)

    *(Ricordati di attivare l'ambiente dopo il setup:* `source .venv/bin/activate` *su Linux/Mac, o* `.\.venv\Scripts\Activate.ps1` *su Windows)*.

2. **Compilazione Automatica (`build_local.py`)**
  
    Uno script intelligente che pulisce le directory temporanee, rileva il tuo Sistema Operativo, legge dinamicamente il numero di versione dal codice e compila l'eseguibile standalone tramite PyInstaller rinominandolo in modo standardizzato (es. `NullifyPDF_v2.0.5_Windows.exe`).

    ```bash
    python build_local.py
    ```

    > **💡 Bonus Linux:** Se lanciato su Ubuntu o Fedora, lo script utilizzerà i tool nativi (`dpkg-deb` o `rpmbuild`) per generare automaticamente anche i pacchetti di installazione `.deb` e `.rpm` direttamente nella tua cartella `dist/`

3. **Smoke Tests (`pytest tests/`)**

    Per verificare che le correzioni critiche (input validation, resource management, edge cases) funzionino correttamente:

    ```bash
    # Assicurati di aver attivato il venv prima
    pip install pytest  # Se non già presente in requirements.txt
    pytest tests/ -v
    ```

    I test coprono:
    - PDFListManager (persistenza blocklist/allowlist)
    - Input validation (path, type checking, bounds)
    - Resource path resolution

[Back To The Top](#nullifypdf---ai-forensic-edition)

---

## 💾 Download release

  Se vuoi semplicemente usare il programma, scarica l'eseguibile pre-compilato dalla sezione [Release](https://github.com/overwrite00/NullifyPDF/releases)

[Back To The Top](#nullifypdf---ai-forensic-edition)

---

## ⚖️ Licenza

MIT License

Copyright (c) 2026 Graziano Mariella

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

[Back To The Top](#nullifypdf---ai-forensic-edition)

---

## 👤 Info Autore

- 👨‍💻 **Graziano Mariella**
- 📂 **GitHub:** @overwrite00
- 🌍 **Location**: Italy 🇮🇹
- [![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/graziano-mariella/)
