# NullifyPDF - Privacy Edition

![GitHub Release](https://img.shields.io/github/v/release/overwrite00/NullifyPDF?style=flat-square&color=1fb2e0&label=stable)
![GitHub Release (beta)](https://img.shields.io/github/v/release/overwrite00/NullifyPDF?include_prereleases&style=flat-square&color=orange&label=beta)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/overwrite00/NullifyPDF/release.yml?style=flat-square&label=build)
![GitHub License](https://img.shields.io/github/license/overwrite00/NullifyPDF?style=flat-square&color=blue)
![Python Version](https://img.shields.io/badge/python-3.13-blue?style=flat-square&logo=python)

<p align="center">
  <img src="images/NullifyPDF.png" alt="NullifyPDF Logo" width="500">
</p>

> **NullifyPDF** is a local-first PDF privacy tool. It helps detect personal data, redact it irreversibly, or replace it with reversible placeholders before a PDF is shared with third parties or uploaded to AI systems.

> [!TIP]
> First time using NullifyPDF? Start with our [**User Guide**](./USER_GUIDE.md) — takes 5 minutes.

---

## 📋 Quick Overview

NullifyPDF goes beyond simple text covering. It uses **Natural Language Processing (NLP)** engines to identify entities like *names*, *addresses*, *email addresses*, *IBANs*, and *credit card numbers*. At export, the user chooses irreversible anonymization or reversible pseudonymization with an encrypted restore map.

| 🎯 Feature            | ✨ Benefit                             |
| -------------------- | ------------------------------------- |
| 🧠 **Auto-detection** | Bilingual (EN/IT) automatic detection |
| 🔐 **Local-first**    | No cloud uploads during PDF processing |
| ⚡ **Responsive UI**  | Background scanning with live preview |
| 🛡️ **Privacy Export** | Irreversible redaction or reversible placeholders |

---

## ✨ Key Features

- 🧠 **Automatic Redaction** — Automatic bilingual (EN/IT) detection of PII: names, locations, emails, phones, IBANs, credit cards, crypto addresses, Italian fiscal codes and IDs. A dialog lets you choose which data types to scan for, and matching is whole-word so ordinary text is not caught
- 🔄 **Update Check** — Optional, user-triggered check for new releases (stable builds see stable only, beta builds see both) showing the release notes and a one-click download into your Downloads folder; can be enabled at every start from the Info dialog (off by default)
- 🗄️ **Fluid UI & Thread-Safe** — PySide6 modern dark-mode interface with zero UI freezing. Text extraction in worker thread with QMutex serialization
- 📖 **Persistent Dictionaries** — Blocklist and Allowlist synchronized to disk (`~/.nullifypdf`) with O(1) fast-path matching
- 🛡️ **Privacy Export Modes** — Choose irreversible removal or reversible pseudonymization with a separately encrypted restore map; the exported file is sanitised (annotations, attachments, scripts, metadata, hidden text) and verified
- 📖 **Built-in guide and tooltips** — Press F1 for an Italian guide to every function; every control shows a description on hover
- 🔍 **Review of uncertain hits** — Detections without enough evidence are suggested for review instead of being applied or lost silently
- 🧠 **Optional local models** — Reviewed ONNX PII models can be downloaded by the user from pinned Hugging Face revisions; files are SHA-256 verified and models only add review suggestions
- 📄 **Word import** — DOCX paragraphs and tables can be imported locally into the analysis workflow; legacy binary DOC files are not supported
- 🔎 **OCR Support** — Bundled EN/IT Tesseract language data for scanned PDFs
- 🖼️ **Blindfold Mode** — One-click image/logo censoring with professional placeholder: `[ IMAGE REMOVED ]`
- 📦 **Native Cross-Platform** — Automated build scripts generate Windows `.exe`, macOS ZIP bundles, and Linux `.deb`/`.rpm` packages
- 🎯 **Drag & Drop Support** — Native file drag-and-drop on main window
- 📊 **Logging & Diagnostics** — Local file-based logging (`~/.nullifypdf/logs/`) with debug mode for advanced troubleshooting

---

## ⚠️ Tool Limitations

To keep NullifyPDF lightweight, 100% offline, and secure, be aware of these technical limits:

| ❌ Limitation                       | 💡 Workaround                                                                                            |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------- |
| **Handwritten Text**               | NLP models cannot analyze non-digitized handwriting.                                                    |
| **Password-Protected PDFs**        | Encrypted documents are blocked at load. Decrypt before importing.                                      |
| **Legacy Word DOC files**          | Only modern `.docx` files are supported; save legacy files as DOCX before importing.                    |
| **Digital Signatures Invalidated** | Privacy export changes the PDF; cryptographic signatures (PAdES, notarized) become invalid.            |

> [!WARNING]
> Digital signatures will be invalidated after redaction. Save unredacted originals separately for formal records.

---

## 🚀 Getting Started

### 📋 System Requirements

```
✅ Python 3.13 (required for PyMuPDF wheel compatibility)
✅ 2 GB disk space (dependencies + spaCy models)
✅ 4 GB RAM minimum (8 GB recommended for large PDFs)
```

**Operating System Support:**
- ✅ Windows 10/11
- ✅ macOS 11+
- ✅ Linux: Ubuntu 24.04 / 26.04 and Debian 13 (`.deb`), RHEL / Rocky / Alma 9-10 and current Fedora (`.rpm`). The packages are built against glibc 2.34, so Ubuntu 22.04 and Debian 12 also run them, but these are no longer tested

### ⚙️ Installation

<details open>
<summary><strong>👤 End Users — Use Pre-Built Executable</strong></summary>

Download the latest pre-compiled executable from [Releases](https://github.com/overwrite00/NullifyPDF/releases):

- **Windows:** `NullifyPDF_vX.Y.Z_Windows.exe`
- **macOS:** `NullifyPDF_vX.Y.Z_macOS.zip`
- **Ubuntu / Debian:** `NullifyPDF_vX.Y.Z_Ubuntu.deb`
- **Fedora / RHEL:** `NullifyPDF_vX.Y.Z_Fedora.rpm`

No installation needed on Windows/macOS - just run or unzip. Linux users can install the `.deb` or `.rpm` package.

</details>

<details>
<summary><strong>👨‍💻 Developers — Install from Source</strong></summary>

1. **Clone the repository**

   ```bash
   git clone https://github.com/overwrite00/NullifyPDF.git
   cd NullifyPDF
   ```

2. **Verify Python 3.13**

   ```bash
   # Windows
   py -3.13 --version
   
   # macOS/Linux
   python3.13 --version
   ```

3. **Run automated setup** (recommended)

   ```bash
   python setup_env.py
   ```

   This script automatically:
   - Creates isolated virtual environment (`.venv`)
   - Installs all dependencies
   - Downloads spaCy language models (EN/IT)

4. **Activate environment & launch**

   ```bash
   # Windows (PowerShell)
   .\.venv\Scripts\Activate.ps1
   python NullifyPDF.py
   
   # macOS/Linux (Bash)
   source .venv/bin/activate
   python3.13 NullifyPDF.py
   ```

</details>

### 🤖 Automation Scripts

The repository includes cross-platform Python scripts for developers:

<details>
<summary><strong>🔧 setup_env.py — Environment Setup</strong></summary>

Configures development environment with Python 3.13, virtual environment, and NLP models.

```bash
python setup_env.py
```

**What it does:**
- Detects OS (Windows/macOS/Linux)
- Creates `.venv` with Python 3.13
- Installs `requirements.txt` dependencies
- Installs the Italian spaCy model for development (the installer does not bundle it)

**Automatic OS detection:**
- Windows: Uses `py -3.13` launcher
- macOS/Linux: Uses `python3.13` directly

</details>

<details>
<summary><strong>🏗️ build_local.py — Build Executable</strong></summary>

Compiles standalone executable with PyInstaller.

```bash
python build_local.py
```

**Features:**
- Cleans temporary directories
- Auto-detects your OS
- Reads version dynamically from code
- Generates named executables such as `NullifyPDF_vX.Y.Z_Windows.exe`
- Bundles EN/IT OCR data (downloaded automatically if missing)

**Linux bonus:** On Ubuntu/Fedora, automatically builds `.deb` and `.rpm` packages in `dist/`

</details>

<details>
<summary><strong>✓ Running Tests</strong></summary>

Verify core behavior with smoke tests:

```bash
# Activate venv first
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows

pytest tests/ -v
```

**Test coverage:**
- PDFListManager (blocklist/allowlist persistence)
- Resource path resolution
- OCR configuration helpers
- Privacy placeholder and encrypted restore-map primitives
- AI detection helpers (offset mapping, filtering, whole-word matching) and reconstruction with the original font
- Build configuration

</details>

---

## 📚 Documentation

| 📄 Document                                 | 📖 Purpose                              |
| ------------------------------------------ | -------------------------------------- |
| [USER_GUIDE.md](./USER_GUIDE.md)           | Step-by-step usage instructions        |
| [CONTRIBUTING.md](./CONTRIBUTING.md)       | How to contribute code & report issues |
| [ARCHITECTURE.md](./ARCHITECTURE.md)       | System design & technical overview     |
| [DEVELOPMENT.md](./DEVELOPMENT.md)         | Local dev setup, testing & builds      |
| [OCR_SETUP.md](./OCR_SETUP.md)             | OCR data setup and build notes         |
| [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | Common issues & solutions              |
| [CHANGELOG.md](./CHANGELOG.md)             | Release history & updates              |

---

## 🔒 Security & Privacy

✅ **100% Local Processing** — All analysis happens on your machine  
✅ **No Cloud Uploads** — PDF processing stays local  
✅ **Open Source** — Full code transparency  
✅ **No Telemetry** — Zero user tracking  

> [!IMPORTANT]
> Irreversible removal cannot be undone from the exported PDF, and it does not by itself guarantee anonymisation: indirect identifiers can remain. A pseudonymized PDF and its restore map are personal data. Always keep backups of original documents. Pseudonymization requires the encrypted restore map and its password.

See [SECURITY.md](./SECURITY.md) for responsible disclosure and privacy details.

---

## 🛠️ Tech Stack

| Technology             | Purpose                                             |
| ---------------------- | --------------------------------------------------- |
| **Python 3.13**        | Core language (required for PyMuPDF compatibility)  |
| **PySide6 (Qt6)**      | Modern dark-mode GUI with multi-threading           |
| **PyMuPDF (fitz)**     | High-performance PDF manipulation                   |
| **Microsoft Presidio** | PII (Personally Identifiable Information) detection |
| **spaCy**              | NLP for entity recognition (bilingual EN/IT)        |
| **cryptography**       | Encrypted pseudonymization restore maps             |

---

## 📝 License

**GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)**

Copyright (c) 2026 Graziano Mariella

NullifyPDF is free of charge and is not sold by its author. It is AGPL-licensed
because it uses [PyMuPDF](https://pymupdf.readthedocs.io/), which is available
under the AGPL-3.0 or a commercial licence from Artifex. Anyone who distributes
the program, modified or not, must give the recipients the source code under the
same licence. Releases up to v2.4.0-beta.4 were published under the MIT licence.

The Italian name-recognition model (spaCy `it_core_news_md`, CC BY-NC-SA 3.0,
non-commercial) is **not** part of the installer: the program offers to download
it, shows its licence and asks for consent first. Licences of all third-party
components are listed in [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md).

**Notice.** NullifyPDF is free software, distributed under the AGPL-3.0-or-later. Every component and model it uses remains under its own licence, listed below with a link to the official text; using the program means respecting those conditions. The Italian spaCy model is for non-commercial use only and is downloaded only after your consent.

| Component | Licence | Used for |
|---|---|---|
| [NullifyPDF](https://github.com/overwrite00/NullifyPDF/blob/main/LICENSE) | AGPL-3.0-or-later | this program |
| [PyMuPDF / MuPDF](https://pymupdf.readthedocs.io/en/latest/about.html) | AGPL-3.0 or commercial (Artifex) | PDF reading and redaction |
| [PySide6 / Qt](https://opensource.org/license/lgpl-3-0) | LGPL-3.0 | graphical interface |
| [Presidio](https://github.com/microsoft/presidio/blob/main/LICENSE) | MIT | personal-data detection |
| [spaCy](https://github.com/explosion/spaCy/blob/master/LICENSE) | MIT | language processing |
| [spaCy it_core_news_md](https://creativecommons.org/licenses/by-nc-sa/3.0/) | CC BY-NC-SA 3.0 (non-commercial use only) | Italian model, downloaded after consent |
| [onnxruntime](https://github.com/microsoft/onnxruntime/blob/main/LICENSE) | MIT | running local models |
| [tokenizers](https://github.com/huggingface/tokenizers/blob/main/LICENSE) | Apache-2.0 | tokenizing for local models |
| [cryptography](https://github.com/pyca/cryptography/blob/main/LICENSE) | Apache-2.0 or BSD-3-Clause | encryption |
| [keyring](https://github.com/jaraco/keyring) | MIT | key storage (Linux/macOS) |
| [tldextract](https://github.com/john-kurkowski/tldextract/blob/master/LICENSE) | BSD-3-Clause | URL recognition |
| [NumPy](https://github.com/numpy/numpy/blob/main/LICENSE.txt) | BSD-3-Clause | numerical computing |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE) | Apache-2.0 | OCR of scanned documents |
| [tessdata_fast (eng, ita)](https://github.com/tesseract-ocr/tessdata_fast/blob/main/LICENSE) | Apache-2.0 | OCR language data |
| [ISTAT, elenco dei comuni](https://creativecommons.org/licenses/by/4.0/) | CC BY 4.0 | place names |
| [Wikidata](https://creativecommons.org/publicdomain/zero/1.0/) | CC0 1.0 | given names and surnames |

See [LICENSE](./LICENSE) for the full text.

---

## 🤝 Contributing

Want to help improve NullifyPDF? See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

---

*Last updated: 2026-11-11*  
*[User Guide →](./USER_GUIDE.md)*
