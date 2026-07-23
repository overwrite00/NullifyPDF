# NullifyPDF - AI Privacy Edition

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
| 🧠 **AI-Powered**     | Bilingual (EN/IT) automatic detection |
| 🔐 **Local-first**    | No cloud uploads during PDF processing |
| ⚡ **Responsive UI**  | Background scanning with live preview |
| 🛡️ **Privacy Export** | Irreversible redaction or reversible placeholders |

---

## ✨ Key Features

- 🧠 **AI-Powered Redaction** — Automatic bilingual (EN/IT) detection of PII: names, locations, emails, phones, IBANs, credit cards, crypto addresses
- 🗄️ **Fluid UI & Thread-Safe** — PySide6 modern dark-mode interface with zero UI freezing. Text extraction in worker thread with QMutex serialization
- 📖 **Persistent Dictionaries** — Blocklist and Allowlist synchronized to disk (`~/.nullifypdf`) with O(1) fast-path matching
- 🛡️ **Privacy Export Modes** — Choose irreversible anonymization or reversible pseudonymization with a separately encrypted restore map
- 🔎 **OCR Support** — Full builds bundle EN/IT Tesseract language data for scanned PDFs
- 🖼️ **Blindfold Mode** — One-click image/logo censoring with professional placeholder: `[ IMAGE REMOVED ]`
- 📦 **Native Cross-Platform** — Automated build scripts generate Windows `.exe`, macOS ZIP bundles, and Linux `.deb`/`.rpm` packages
- 🎯 **Drag & Drop Support** — Native file drag-and-drop on main window
- 📊 **Logging & Diagnostics** — Local file-based logging (`~/.nullifypdf/logs/`) with debug mode for advanced troubleshooting

---

## ⚠️ Tool Limitations

To keep NullifyPDF lightweight, 100% offline, and secure, be aware of these technical limits:

| ❌ Limitation                       | 💡 Workaround                                                                                            |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------- |
| **OCR availability**              | Full builds include EN/IT OCR data. Lite builds require local Tesseract tessdata for scanned PDFs.      |
| **Handwritten Text**               | NLP models cannot analyze non-digitized handwriting.                                                    |
| **Password-Protected PDFs**        | Encrypted documents are blocked at load. Decrypt before importing.                                      |
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
- ✅ Linux (Ubuntu 20.04+, Fedora 33+)

### ⚙️ Installation

<details open>
<summary><strong>👤 End Users — Use Pre-Built Executable</strong></summary>

Download the latest pre-compiled executable from [Releases](https://github.com/overwrite00/NullifyPDF/releases):

- **Windows Lite:** `NullifyPDF_vX.Y.Z_Windows_Lite.exe`
- **Windows Full OCR:** `NullifyPDF_vX.Y.Z_Windows_Full.exe`
- **macOS Lite:** `NullifyPDF_vX.Y.Z_macOS_Lite.zip`
- **macOS Full OCR:** `NullifyPDF_vX.Y.Z_macOS_Full.zip`
- **Ubuntu Lite/Full:** `NullifyPDF_vX.Y.Z_Ubuntu_Lite.deb` or `NullifyPDF_vX.Y.Z_Ubuntu_Full.deb`
- **Fedora Lite/Full:** `NullifyPDF_vX.Y.Z_Fedora_Lite.rpm` or `NullifyPDF_vX.Y.Z_Fedora_Full.rpm`

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
- Downloads spaCy models (English, Italian, both)

**Automatic OS detection:**
- Windows: Uses `py -3.13` launcher
- macOS/Linux: Uses `python3.13` directly

</details>

<details>
<summary><strong>🏗️ build_local.py — Build Executable</strong></summary>

Compiles standalone executable with PyInstaller.

```bash
python build_local.py --lite
python build_local.py --full
```

**Features:**
- Cleans temporary directories
- Auto-detects your OS
- Reads version dynamically from code
- Generates named executables such as `NullifyPDF_vX.Y.Z_Windows_Lite.exe` or `NullifyPDF_vX.Y.Z_Windows_Full.exe`

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
- Build variant configuration

</details>

---

## 📚 Documentation

| 📄 Document                                 | 📖 Purpose                              |
| ------------------------------------------ | -------------------------------------- |
| [USER_GUIDE.md](./USER_GUIDE.md)           | Step-by-step usage instructions        |
| [CONTRIBUTING.md](./CONTRIBUTING.md)       | How to contribute code & report issues |
| [ARCHITECTURE.md](./ARCHITECTURE.md)       | System design & technical overview     |
| [DEVELOPMENT.md](./DEVELOPMENT.md)         | Local dev setup, testing & builds      |
| [OCR_SETUP.md](./OCR_SETUP.md)             | OCR data setup and Lite/Full build notes |
| [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | Common issues & solutions              |
| [CHANGELOG.md](./CHANGELOG.md)             | Release history & updates              |

---

## 🔒 Security & Privacy

✅ **100% Local Processing** — All analysis happens on your machine  
✅ **No Cloud Uploads** — PDF processing stays local  
✅ **Open Source** — Full code transparency  
✅ **No Telemetry** — Zero user tracking  

> [!IMPORTANT]
> Irreversible anonymization cannot be undone from the exported PDF. Always keep backups of original documents. Pseudonymization requires the encrypted restore map and its password.

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

**MIT License** — Free to use, modify, and distribute

Copyright (c) 2026 Graziano Mariella

See [LICENSE](./LICENSE) for full text.

---

## 🤝 Contributing

Want to help improve NullifyPDF? See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

---

*Last updated: 2026-07-23*  
*[User Guide →](./USER_GUIDE.md)*
