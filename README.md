# NullifyPDF - AI Forensic Edition

![GitHub Release](https://img.shields.io/github/v/release/TUO_USERNAME/NOME_REPO?style=flat-square&color=1fb2e0)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/TUO_USERNAME/NOME_REPO/release.yml?style=flat-square&label=build)
![GitHub License](https://img.shields.io/github/license/TUO_USERNAME/NOME_REPO?style=flat-square&color=blue)
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python)

<p align="center">
  <img src="images/NullifyPDF.png" alt="NullifyPDF">
</p>

> **NullifyPDF** è uno strumento professionale per l'anonimizzazione forense dei PDF. Progettato per la privacy assoluta, opera interamente in locale utilizzando l'intelligenza artificiale per identificare e distruggere permanentemente dati sensibili senza mai caricare file nel cloud.

---

### 📍 Table of Contents
- [NullifyPDF - AI Forensic Edition](#nullifypdf---ai-forensic-edition)
    - [📍 Table of Contents](#-table-of-contents)
  - [📝 Description](#-description)
      - [🛠️ Technologies](#️-technologies)
  - [✨ Key Features](#-key-features)
  - [🛠️ How To Use](#️-how-to-use)
      - [⚙️ Installation](#️-installation)
      - [💾 **Download release**](#-download-release)
  - [⚖️ License](#️-license)
  - [👤 Author info](#-author-info)

---

## 📝 Description

NullifyPDF va oltre la semplice copertura visiva del testo. Utilizza motori di Natural Language Processing (NLP) per comprendere il contesto e individuare entità come nomi, indirizzi, IBAN e numeri di carte di credito. A differenza dei comuni editor PDF, questo tool esegue uno "scrubbing" forense, eliminando metadati, hyperlink e livelli vettoriali nascosti per garantire che la censura sia irreversibile.

#### 🛠️ Technologies

- **Python 3.10+**
- **CustomTkinter**: Interfaccia grafica moderna in Dark Mode.
- **PyMuPDF (fitz)**: Motore ad alte prestazioni per la manipolazione di PDF.
- **Microsoft Presidio & spaCy**: Motori AI per il riconoscimento delle entità (NER).
- **Pillow**: Gestione avanzata degli asset grafici e icone.

[Back To The Top](#nullifypdf---ai-forensic-edition)

---

## ✨ Key Features

- 🧠 **AI-Powered Redaction**: Supporto bilingue (Italiano e Inglese) per il rilevamento automatico di dati sensibili.
- 🛡️ **Forensic Scrubbing**: Rimozione automatica di metadati, link e oggetti nascosti sotto le aree censurate.
- 📖 **Smart Dictionaries**: Gestione di **Blocklist** (termini da censurare sempre) e **Allowlist** (termini da ignorare).
- 🖱️ **Interactive Review**: Sistema di revisione che permette di annullare le censure con un semplice click prima dell'esportazione.
- 💻 **Cross-Platform**: Disponibile per Windows (.exe), macOS e Ubuntu (.deb).
- 🔒 **Privacy First**: Funzionamento 100% offline. Nessun dato lascia mai il tuo computer.

[Back To The Top](#nullifypdf---ai-forensic-edition)

---

## 🛠️ How To Use

#### ⚙️ Installation

Se sei uno sviluppatore e vuoi eseguire il codice sorgente:

1. 📥 **Clona il repository**:
   ```bash
   git clone [https://github.com/TUO_USERNAME/NOME_REPO.git](https://github.com/TUO_USERNAME/NOME_REPO.git)
   cd NOME_REPO

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

 #### 💾 **Download release**
  Se vuoi semplicemente usare il programma, scarica l'eseguibile pre-compilato dalla sezione [Release](https://github.com/overwrite00/NullifyPDF/releases)

[Back To The Top](#nullifypdf---ai-forensic-edition)

---

## ⚖️ License

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

## 👤 Author info

- 👨‍💻 **Graziano Mariella**
- 📂 **GitHub:** @overwrite00
- 🌍 **Location**: Italy 🇮🇹
- <a href="https://linkedin.com/in/TUO_PROFILO" target="blank"><img align="center" src="https://raw.githubusercontent.com/rahuldkjain/github-profile-readme-generator/master/src/images/icons/Social/linked-in-alt.svg" alt="LinkedIn" height="20" width="20" /></a> [Graziano Mariella](https://www.linkedin.com/in/graziano-mariella/)