# NullifyPDF - AI Forensic Edition

![GitHub Release](https://img.shields.io/github/v/release/overwrite00/NullifyPDF?style=flat-square&color=1fb2e0)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/overwrite00/NullifyPDF/release.yml?style=flat-square&label=build)
![GitHub License](https://img.shields.io/github/license/overwrite00/NullifyPDF?style=flat-square&color=blue)
![Python Version](https://img.shields.io/badge/python-3.9%2B-blue?style=flat-square&logo=python)

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

- **Python 3.9+**
- **PySide6 (Qt6)**: Nuovo motore grafico con nterfaccia grafica moderna in Dark Mode.
- **PyMuPDF (fitz)**: Motore ad alte prestazioni per la manipolazione di PDF.
- **Microsoft Presidio & spaCy**: Motori AI per il riconoscimento delle entità (NER).

[Back To The Top](#nullifypdf---ai-forensic-edition)

---

## ✨ Caratteristiche principali

- 🧠 **AI-Powered Redaction:** Riconoscimento automatico bilingue (IT/EN) di PII (Nomi, Luoghi, Email, Telefoni, IBAN, Carte di Credito, Crypto).
- 🗄️ - **UI Fluida:** Grazie all'integrazione di PySide6 e all'architettura Multithread, l'interfaccia non si blocca mai durante l'analisi AI.
- 📖 **Dizionari Intelligenti Persistenti:** Blocklist e Allowlist globali sincronizzate su disco (`~/.nullifypdf`) con logica di mutua esclusività e sistema anti-stacking delle censure.
- 🛡️ **Forensic Scrubbing:** Non si limita a "colorare di nero". In fase di export, distrugge fisicamente i metadati, rimuove i link nascosti e appiattisce i moduli interattivi (AcroForms).
- 🖼️ **Blindfold Mode (Sostituzione Immagini):** Interruttore dedicato per censurare automaticamente tutte le immagini, loghi o QR code, sostituendoli con un segnaposto professionale `[ IMMAGINE RIMOSSA ]`.
- 📦 **Cross-Platform nativo:** Script di build integrati per generare `.exe` (Windows), `.app` bundle (macOS), e pacchetti `.deb`/`.rpm` (Linux).
- **Drag & Drop:** Supporto nativo per il trascinamento dei file sulla finestra.

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

### ⚙️ Installazione

Se sei uno sviluppatore e vuoi eseguire il codice sorgente:

1. 📥 **Clona il repository**:

   ```bash
   git clone https://github.com/overwrite00/NullifyPDF.git
   cd NullifyPDF

2. 📦 **Installa le dipendenze**:

   ```bash
   pip install pyinstaller PyMuPDF customtkinter Pillow presidio-analyzer spacy

3. 🧠 **Scarica i modelli linguistici AI**:

   ```bash
   python -m spacy download en_core_web_md
   python -m spacy download it_core_news_md

4. 🚀 **Avvia l'applicazione**:

   ```bash
   python NullifyPDF.py

### 🐧 Note per lo sviluppo e compilazione in locale su Linux (Fedora / Ubuntu)

Solitamente sui sistemi Windows la libreria grafica standard di Python `tkinter` è già inclusa ma, se intendi clonare la repository per sviluppare o compilare il progetto in locale su Linux, assicurati sia installata a livello di sistema. Senza di essa, PyInstaller genererà un errore fatale durante la compilazione di `customtkinter`.

A seconda della tua distribuzione, apri il terminale ed esegui:

**Su Fedora / RHEL:**

```bash
sudo dnf install python3-tkinter
```

**Su Debian / Ubuntu:**

```bash
sudo apt-get install python3-tk
```

### 🤖 Script di automazione (Sviluppo e compilazione in locale)

Per facilitare al massimo la vita agli sviluppatori e ai contributor, la repository include due script Python multipiattaforma che automatizzano l'intero ciclo di vita dello sviluppo:

1. **Setup dell'Ambiente (`setup_env.py`)**

   Crea un ambiente virtuale isolato (`.venv`), aggiorna i tool di base, installa tutte le dipendenze (`requirements`) e scarica in automatico i modelli NLP di spaCy (EN/IT).

   ```bash
   python setup_env.py
   ```

    *(Ricordati di attivare l'ambiente dopo il setup:* `source .venv/bin/activate` *su Linux/Mac, o* `.\.venv\Scripts\Activate.ps1` *su Windows)*.

2. **Compilazione Automatica (`build_local.py`)**
  
    Uno script intelligente che pulisce le directory temporanee, rileva il tuo Sistema Operativo, legge dinamicamente il numero di versione dal codice e compila l'eseguibile standalone tramite PyInstaller rinominandolo in modo standardizzato (es. `NullifyPDF_v1.3.0_Windows.exe`).

    > **💡 Bonus Linux:** Se lanciato su Ubuntu o Fedora, lo script utilizzerà i tool nativi (`dpkg-deb` o `rpmbuild`) per generare automaticamente anche i pacchetti di installazione `.deb` e `.rpm` direttamente nella tua cartella `dist/`

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
