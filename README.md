# 🔒 NullifyPDF — AI Forensic Edition

![GitHub Release](https://img.shields.io/github/v/release/overwrite00/NullifyPDF?style=flat-square&color=1fb2e0)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/overwrite00/NullifyPDF/release.yml?style=flat-square&label=build)
![GitHub License](https://img.shields.io/github/license/overwrite00/NullifyPDF?style=flat-square&color=blue)
![Python Version](https://img.shields.io/badge/python-3.12-blue?style=flat-square&logo=python)

<p align="center">
  <img src="images/NullifyPDF.png" alt="NullifyPDF Logo" width="500">
</p>

> 🔐 **NullifyPDF** is a professional tool for forensic PDF anonymization. Designed for absolute privacy, it operates entirely locally using artificial intelligence to identify and permanently destroy sensitive data without ever uploading files to the cloud.

> [!TIP]
> First time using NullifyPDF? Start with our [**User Guide**](./USER_GUIDE.md) — takes 5 minutes.

---

## 📋 Quick Overview

NullifyPDF goes beyond simple text covering. It uses **Natural Language Processing (NLP)** engines to understand context and identify entities like *names*, *addresses*, *email addresses*, *IBANs*, and *credit card numbers*. Unlike common PDF editors, this tool performs **forensic scrubbing**, destroying metadata, hyperlinks, and hidden vector layers to ensure censorship is irreversible.

| 🎯 Feature            | ✨ Benefit                             |
| -------------------- | ------------------------------------- |
| 🧠 **AI-Powered**     | Bilingual (EN/IT) automatic detection |
| 🔐 **100% Local**     | No cloud uploads, complete privacy    |
| ⚡ **Real-time**      | Instant scanning with live preview    |
| 🛡️ **Forensic-Grade** | Binary-level data destruction         |

---

## ✨ Key Features

- 🧠 **AI-Powered Redaction** — Automatic bilingual (EN/IT) detection of PII: names, locations, emails, phones, IBANs, credit cards, crypto addresses
- 🗄️ **Fluid UI & Thread-Safe** — PySide6 modern dark-mode interface with zero UI freezing. Text extraction in worker thread with QMutex serialization
- 📖 **Intelligent Persistent Dictionaries** — Blocklist and Allowlist synchronized to disk (`~/.nullifypdf`) with mutual exclusivity and anti-stacking logic. O(1) fast-path matching
- 🛡️ **Forensic Scrubbing** — Not just black boxes. Binary-level destruction of metadata, hidden links, and flattened interactive forms (AcroForms) at export
- 🖼️ **Blindfold Mode** — One-click image/logo censoring with professional placeholder: `[ IMAGE REMOVED ]`
- 📦 **Native Cross-Platform** — Automated build scripts generate `.exe` (Windows), `.app` bundles (macOS), and `.deb`/`.rpm` packages (Linux)
- 🎯 **Drag & Drop Support** — Native file drag-and-drop on main window
- 📊 **Logging & Diagnostics** — Rotating file-based logging (`~/.nullifypdf/logs/`) with debug mode for advanced troubleshooting

---

## ⚠️ Tool Limitations

To keep NullifyPDF lightweight, 100% offline, and secure, be aware of these technical limits:

| ❌ Limitation                       | 💡 Workaround                                                                                            |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------- |
| **No Built-in OCR**                | AI reads only digital text, not scanned images. Use Blindfold Mode to remove photo blocks entirely.     |
| **Handwritten Text**               | NLP models cannot analyze non-digitized handwriting.                                                    |
| **Password-Protected PDFs**        | Encrypted documents are blocked at load. Decrypt before importing.                                      |
| **Digital Signatures Invalidated** | Forensic scrubbing destroys binary objects; cryptographic signatures (PAdES, notarized) become invalid. |

> [!WARNING]
> Digital signatures will be invalidated after redaction. Save unredacted originals separately for formal records.

---

## 🚀 Getting Started

### 📋 System Requirements

```
✅ Python 3.12 (required for PyMuPDF wheel compatibility)
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

- **Windows:** `NullifyPDF_v2.0.5_Windows.exe`
- **macOS:** `NullifyPDF_v2.0.5_macOS.app`
- **Linux:** `nullifypdf_2.0.5_amd64.deb` or `.rpm`

No installation needed on Windows/macOS — just run. Linux users: `sudo dpkg -i nullifypdf_*.deb`

</details>

<details>
<summary><strong>👨‍💻 Developers — Install from Source</strong></summary>

1. **Clone the repository**

   ```bash
   git clone https://github.com/overwrite00/NullifyPDF.git
   cd NullifyPDF
   ```

2. **Verify Python 3.12**

   ```bash
   # Windows
   py -3.12 --version
   
   # macOS/Linux
   python3.12 --version
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
   python3.12 NullifyPDF.py
   ```

</details>

### 🤖 Automation Scripts

The repository includes cross-platform Python scripts for developers:

<details>
<summary><strong>🔧 setup_env.py — Environment Setup</strong></summary>

Configures development environment with Python 3.12, virtual environment, and NLP models.

```bash
python setup_env.py
```

**What it does:**
- Detects OS (Windows/macOS/Linux)
- Creates `.venv` with Python 3.12
- Installs `requirements.txt` dependencies
- Downloads spaCy models (English, Italian, both)
- Runs smoke tests to verify installation

**Automatic OS detection:**
- Windows: Uses `py -3.12` launcher
- macOS/Linux: Uses `python3.12` directly

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
- Generates named executable: `NullifyPDF_v2.0.5_Windows.exe`

**Linux bonus:** On Ubuntu/Fedora, automatically builds `.deb` and `.rpm` packages in `dist/`

</details>

<details>
<summary><strong>✓ Running Tests</strong></summary>

Verify critical fixes with smoke tests:

```bash
# Activate venv first
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows

pytest tests/ -v
```

**Test coverage:**
- PDFListManager (blocklist/allowlist persistence)
- Input validation (path, range, language selection)
- Resource path resolution

</details>

---

## 📚 Documentation

| 📄 Document                                 | 📖 Purpose                              |
| ------------------------------------------ | -------------------------------------- |
| [USER_GUIDE.md](./USER_GUIDE.md)           | Step-by-step usage instructions        |
| [CONTRIBUTING.md](./CONTRIBUTING.md)       | How to contribute code & report issues |
| [ARCHITECTURE.md](./ARCHITECTURE.md)       | System design & technical overview     |
| [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | Common issues & solutions              |
| [CHANGELOG.md](./CHANGELOG.md)             | Release history & updates              |

---

## 🔒 Security & Privacy

✅ **100% Local Processing** — All analysis happens on your machine  
✅ **No Network Calls** — Except GitHub release checks  
✅ **Open Source** — Full code transparency  
✅ **No Telemetry** — Zero user tracking  

> [!IMPORTANT]
> NullifyPDF performs binary-level data destruction. Always keep backups of original documents.

See [SECURITY.md](./SECURITY.md) for responsible disclosure and privacy details.

---

## 🛠️ Tech Stack

| Technology             | Purpose                                             |
| ---------------------- | --------------------------------------------------- |
| **Python 3.12**        | Core language (required for PyMuPDF compatibility)  |
| **PySide6 (Qt6)**      | Modern dark-mode GUI with multi-threading           |
| **PyMuPDF (fitz)**     | High-performance PDF manipulation                   |
| **Microsoft Presidio** | PII (Personally Identifiable Information) detection |
| **spaCy**              | NLP for entity recognition (bilingual EN/IT)        |

---

## 📝 License

**MIT License** — Free to use, modify, and distribute

Copyright (c) 2026 Graziano Mariella

See [LICENSE](./LICENSE) for full text.

---

## 🤝 Contributing

Want to help improve NullifyPDF? See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

---

*Last updated: 2026-06-06*  
*← [README_IT](./README_IT.md) | [User Guide →](./USER_GUIDE.md)*
