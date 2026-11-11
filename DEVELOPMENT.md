# 👨‍💻 Development Guide — NullifyPDF

Complete guide for developers setting up a local development environment and contributing to NullifyPDF.

> [!IMPORTANT]
> Requires **Python 3.13**. Older versions are not compatible with PyMuPDF wheels.

---

## 📋 System Requirements

Before starting, verify you have:

| 📦 Requirement           | 💾 Space | 📝 Notes                                       |
| ----------------------- | ------- | --------------------------------------------- |
| **Python 3.13**         | 150 MB  | [Download](https://www.python.org/downloads/) |
| **Git**                 | 50 MB   | [Download](https://git-scm.com/)              |
| **Virtual Environment** | 2 GB    | `.venv/` auto-created by setup script         |
| **Disk Space**          | 3 GB    | Dependencies + Italian model                  |
| **RAM**                 | 4 GB    | 8 GB recommended                              |

---

## 🚀 Quick Start (5 Minutes)

### 1️⃣ Clone Repository

```bash
git clone https://github.com/overwrite00/NullifyPDF.git
cd NullifyPDF
```

### 2️⃣ Verify Python 3.13

```bash
# Windows
py -3.13 --version

# macOS/Linux
python3.13 --version
```

Should output: `Python 3.13.x`

### 3️⃣ Run Automated Setup

```bash
python setup_env.py
```

This automatically:
- ✅ Creates `.venv/` virtual environment
- ✅ Installs dependencies
- ✅ Installs the Italian spaCy model (development only)

### 4️⃣ Activate Virtual Environment

<details>
<summary><strong>🪟 Windows (PowerShell)</strong></summary>

```powershell
.\.venv\Scripts\Activate.ps1
```

If blocked by execution policy:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1
```

</details>

<details>
<summary><strong>🍎 macOS (Bash/Zsh)</strong></summary>

```bash
source .venv/bin/activate
```

</details>

<details>
<summary><strong>🐧 Linux (Bash)</strong></summary>

```bash
source .venv/bin/activate
```

</details>

Your prompt should now show: `(.venv) $`

### 5️⃣ Launch NullifyPDF

```bash
python NullifyPDF.py
```

If the GUI opens → **You're ready to develop!** 🎉

---

## 🏗️ Project Structure

```
NullifyPDF/
|-- NullifyPDF.py              # Main PySide6 application
|-- pii_detection.py           # Qt-free detection: word index, geometry, scoring, partial-match policy
|-- lexicon_it.py              # Italian word lists; lexicon_data_it.py is generated (ISTAT, Wikidata)
|-- privacy_core.py            # Privacy modes, placeholders and encrypted restore maps
|-- export_engine.py           # Qt-free export pipeline, audit record, local-data wipe
|-- pdf_sanitize.py            # Export sanitiser and output verification
|-- review_dialog.py           # Review of suggested detections
|-- secure_store.py            # Master key protection (DPAPI / keyring / key file), AES-GCM sealing
|-- word_lists.py              # Encrypted blocklist/allowlist with expiry
|-- dictionary_dialog.py       # Dictionary editor
|-- help_guide.py              # In-app guide (Italian) and tooltips
|-- licences_info.py           # Licences and links shown in the Info window and README
|-- spacy_models.py            # Italian spaCy pipeline downloaded on demand after consent
|-- model_manager.py           # Pinned local ONNX model catalog and integrity checks
|-- model_dialog.py            # Local model dialog with in-button download progress
|-- onnx_ner.py                # ONNX token-classification adapter
|-- word_import.py             # Safe DOCX text/table importer
|-- update_check.py            # Qt-free update check: versions, GitHub releases, asset choice, download
|-- PDF_Checker.py             # Heuristic verification utility
|-- setup_env.py               # Environment setup script
|-- build_local.py             # PyInstaller build script
|-- requirements.txt           # Python dependencies
|-- LICENSE, THIRD_PARTY_NOTICES.md
|-- scripts/
|   |-- download_ocr_data.py   # EN/IT OCR data downloader
|   |-- build_lexicon_data.py  # Generates lexicon_data_it.py (development only)
|   |-- extract_release_notes.py
|   `-- update_docs_dates.py
|-- tests/                     # pytest suite (unit, integration and offscreen GUI tests)
|-- images/
|   `-- NullifyPDF.png
`-- .github/
    `-- workflows/
        |-- test_build.yml     # unit tests and full build matrix
        |-- beta-release.yml   # v*-beta.N tags
        |-- release.yml        # vX.Y.Z tags
        |-- build-linux.yml    # reusable: .deb/.rpm build and smoke tests
        |-- guard-main-source.yml
        `-- project-automation.yml
```

---

## 📦 Dependency Overview

### Core Dependencies

| Package               | Version | Purpose                      |
| --------------------- | ------- | ---------------------------- |
| **PySide6**           | 6.12.0  | GUI framework (Qt6 bindings) |
| **PyMuPDF**           | 2.1     | PDF manipulation and OCR bridge |
| **presidio-analyzer** | 2.2.366 | PII detection                |
| **spaCy**             | 3.8.18  | NLP for entity recognition   |
| **cryptography**      | 50.0.2  | Encrypted restore maps and dictionaries |
| **keyring**           | 25.7.0  | OS key store (macOS and Linux only) |
| **onnxruntime**       | 1.31.1  | CPU inference for optional local PII models |
| **tokenizers**        | 0.23.3  | Fast local tokenizer with character offsets |
| **python-docx**       | —       | Not required; DOCX import uses the standard-library OOXML reader |
| **pytest**            | 9.2.0   | Testing framework            |
| **mypy**              | 1.20.2  | Type checking (blocking in CI) |
| **PyInstaller**       | 6.22.3  | Builds the executables       |

### Language Models

| Model             | Size  | Purpose     | Licence | In the installer |
| ----------------- | ----- | ----------- | ------- | ---------------- |
| `it_core_news_md` | 45 MB | Italian NER | CC BY-NC-SA 3.0 | **no**, downloaded by the app on demand (`spacy_models.py`) |

`setup_env.py` installs it in the development environment (the Italian tests
need it). The PyInstaller specs exclude `it_core_news_md`, `pymupdf4llm` and
`pymupdf.layout`. At run time the app asks for consent, downloads the Italian
pipeline from the publisher's release, checks its size and SHA-256 and stores it
under `~/.nullifypdf/spacy_models/`. If the user declines, a blank Italian
pipeline is used and only rule-based detection is available.

The optional ONNX models (MiniLMv2 EN/IT, PiiScan, OpenMed Italian FastClinical)
are described in `model_manager.py`; they are downloaded by the user from pinned
Hugging Face revisions into `~/.nullifypdf/models/` and add suggestions only.

---

## 🔍 Understanding the Code

### Entry Point: `NullifyPDF.py`

**Class Hierarchy:**

```python
NullifyPDF(QMainWindow)
|-- PDFListManager          # (word_lists.py) encrypted blocklist/allowlist
|-- AIWorker(QObject)       # NLP/OCR scanning in thread
|-- PDFView(QGraphicsView)  # PDF rendering and rectangle drawing
|-- privacy_core.py         # Privacy modes and encrypted restore maps
`-- UI Components
    |-- Sidebar
    |-- Toolbar
    |-- Progress bar
    `-- Dialogs
```

**Key Methods:**

```python
class NullifyPDF:
    def __init__(self)                  # Initialize GUI
    def load_path(self, path: str)      # Load PDF file
    def cmd_auto_ai(self)               # Start AI/OCR scan
    def apply_ai_to_page(self, i, data) # Receive AI results
    def cmd_export(self)                # Export privacy PDF
    def cmd_reconstruct(self)           # Reconstruct pseudonymized PDF from restore map
    def user_draw_rect(self, rect)      # Draw manual redaction
```

### Threading Model

**Single Responsibility:**
- **UI Thread** — Rendering, events, dialog management
- **AIWorker Thread** — Text extraction, NLP analysis

**Synchronization:**
```python
with QMutexLocker(self.mutex):
    text = pdf_doc.get_text()  # Safe access to PDF
# (no lock needed for NLP)
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed system design.

---

## 🧪 Running Tests

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test

```bash
pytest tests/test_validation.py::TestPDFListManager::test_save_and_load_blocklist -v
```

### Test Coverage

```bash
pytest tests/ --cov=. --cov-report=html
```

Opens `htmlcov/index.html` in browser.

### Type Checking

CI runs `mypy` as a blocking step. Run the same check locally before opening a PR:

```bash
mypy NullifyPDF.py pii_detection.py privacy_core.py update_check.py PDF_Checker.py export_engine.py pdf_sanitize.py review_dialog.py lexicon_it.py secure_store.py word_lists.py dictionary_dialog.py help_guide.py spacy_models.py licences_info.py
```

PyMuPDF is imported as `pymupdf` (aliased to `fitz`) so it is really type-checked; its dynamically defined constants are read once near the top of `NullifyPDF.py`.

### What's Tested

- ✅ **Detection** — word index, rectangle clamping and the glyph-deletion rule, scoring, partial-match policy, Italian lexicon
- ✅ **Redaction and export** — redaction engine, sanitiser, export verification (survivor and leak checks)
- ✅ **Privacy Core** — placeholders and encrypted restore maps (v1 to v4 formats, Argon2id envelope, recovery key), reconstruction with the original font
- ✅ **Local data** — encrypted dictionaries with expiry and the secure key store
- ✅ **GUI flows** — offscreen tests of review, export, reconstruction, guide and tooltips, Info window, model dialog and Italian-model consent
- ✅ **Models and import** — model catalog and integrity checks, on-demand Italian model download, DOCX import, update check
- ✅ **Licences and build** — licence consistency, OCR data bundling, PyInstaller configuration, resource paths

> [!TIP]
> GUI tests run offscreen (`QT_QPA_PLATFORM=offscreen`) and never touch the OS keyring (`NULLIFYPDF_DISABLE_KEYRING=1`).

---

## 🚀 Building a Local Executable

### Quick Build

```bash
python build_local.py
```

**Output:** `dist/NullifyPDF_vX.Y.Z_Windows.exe` (on Windows)

### What It Does

1. Cleans `build/` and `dist/` directories
2. Detects your OS (Windows/macOS/Linux)
3. Reads version from `NullifyPDF.py` (`__version__`)
4. Bundles EN/IT OCR data (downloaded automatically if missing)
5. Compiles with PyInstaller
6. Renames with version: `NullifyPDF_v{VERSION}_{OS}.exe`

### Distribution Artifacts

| OS          | Output                            |
| ----------- | --------------------------------- |
| **Windows** | `.exe` executable                 |
| **macOS**   | `.app` bundle ZIP                 |
| **Linux**   | Portable binary + `.deb` + `.rpm` packages (CI builds them in a RHEL 9 container, see `build-linux.yml`; `python build_local.py --deb-only` re-packages an existing binary as `.deb`) |

### Troubleshooting Build Issues

<details>
<summary><strong>Build fails on Windows with "RecursionError"</strong></summary>

**Cause:** spaCy models too large for default recursion.

**Fix:** Already handled in `.spec` file. If issue persists:

```python
# In build_local.py
import sys
sys.setrecursionlimit(5000)
```

</details>

<details>
<summary><strong>Build succeeds but executable won't run</strong></summary>

1. Check antivirus isn't blocking
2. Run in debug mode: `NullifyPDF_vX.Y.Z_Windows.exe` from PowerShell
3. Check `.stdout` file if created
4. Report on GitHub

</details>

---

## 🔄 Git Workflow

### Feature Branch Workflow

```bash
# 1. Update develop
git fetch origin
git checkout develop
git pull origin develop

# 2. Create feature branch
git checkout -b feature/my-feature

# 3. Make changes
# ... edit code ...

# 4. Test
pytest tests/ -v
python build_local.py

# 5. Commit with clear message
git commit -m "feat(ai): add IBAN detection"

# 6. Push and open PR
git push origin feature/my-feature
```

### Commit Message Format

```
type(scope): description

Optional longer explanation
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `ci`

**Examples:**
```bash
feat(ai): add cryptocurrency address detection
fix(export): reduce memory usage in privacy export
docs: update installation guide
perf(allowlist): implement O(1) fast-path lookup
```

See [CONTRIBUTING.md](./CONTRIBUTING.md#-commit-message-format) for details.

---

## 🐛 Debugging

### Enable Debug Logging

```bash
# Windows
$env:NULLIFYPDF_DEBUG = "true"
python NullifyPDF.py

# macOS/Linux
export NULLIFYPDF_DEBUG=true
python3.13 NullifyPDF.py
```

**Effect:** Logs verbose output to `~/.nullifypdf/logs/nullifypdf.log`

### Add Debug Prints

Use logging, not `print()`:

```python
import logging
logger = logging.getLogger("nullifypdf")

logger.debug(f"Variable: {value}")
logger.info(f"Action completed: {result}")
logger.error(f"Error occurred: {exception}")
```

### Interactive Debugging

Use Python debugger:

```python
import pdb
pdb.set_trace()  # Execution pauses here
```

Then in console:
- `l` — List current line
- `n` — Next line
- `s` — Step into function
- `c` — Continue
- `p var` — Print variable

---

## 📝 Code Style

### Type Hints (Required)

100% of functions must have type hints:

```python
# ✅ GOOD
def extract_text(pdf_path: str, page: int) -> str:
    """Extract text from page."""
    ...

# ❌ BAD
def extract_text(pdf_path, page):
    """Extract text from page."""
    ...
```

### Docstrings (Google Style)

```python
def redact_entity(text: str, entity: str) -> str:
    """Replace entity with redaction marker.
    
    Args:
        text: Input text containing entity
        entity: Entity to redact
        
    Returns:
        Text with entity replaced by [REDACTED]
        
    Raises:
        ValueError: If entity is empty
    """
```

### Imports

Use `isort` for automatic sorting:

```bash
pip install isort
isort NullifyPDF.py
```

---

## 📚 Key Files to Know

| File               | Purpose                 |
| ------------------ | ----------------------- |
| `NullifyPDF.py`    | Main app, GUI, OCR, export logic |
| `privacy_core.py`  | Placeholder and restore-map logic |
| `pii_detection.py` | AI detection precision: word-box index, rectangle clamping, thresholds, pattern validation, evidence scoring, entity selection |
| `lexicon_it.py`    | Italian word lists used to reject ordinary words / confirm names and places |
| `pdf_sanitize.py`  | Export sanitiser and output verification |
| `export_engine.py` | Qt-free export pipeline, audit record, local-data hygiene |
| `review_dialog.py` | Review dialog for suggested detections |
| `spacy_models.py`  | Italian spaCy pipeline downloaded on demand (consent, SHA-256, fallback) |
| `licences_info.py` | Licences and official links shown in the Info window and README (a test keeps README in step) |
| `model_manager.py` / `model_dialog.py` / `onnx_ner.py` | Optional ONNX models: catalog, verified download, adapter |
| `word_import.py`   | DOCX import |
| `secure_store.py`  | Master key protection (DPAPI / keyring / key file), AES-GCM sealing |
| `word_lists.py`    | Encrypted blocklist/allowlist with expiry |
| `dictionary_dialog.py` | Dictionary editor dialog |
| `help_guide.py` | In-app guide and tooltip table (keep the guide in sync with the UI: `tests/test_gui_help.py` checks it) |
| `scripts/build_lexicon_data.py` | Generates `lexicon_data_it.py` from ISTAT open data and (with `--wikidata`) Wikidata names; development only |
| `setup_env.py`     | Environment setup |
| `build_local.py`   | PyInstaller build |
| `PDF_Checker.py`   | Post-processing utility |
| `requirements.txt` | Dependencies |
| `tests/`           | Unit and smoke tests |

### Quick Edit Locations

| Feature             | File            | Method                |
| ------------------- | --------------- | --------------------- |
| Load PDF            | `NullifyPDF.py` | `load_path()`         |
| Auto Redact         | `NullifyPDF.py` | `cmd_auto_ai()`       |
| AI Processing       | `NullifyPDF.py` | `AIWorker.run_scan()` |
| Export              | `NullifyPDF.py` | `cmd_export()`        |
| Reconstruct         | `NullifyPDF.py` | `cmd_reconstruct()`   |
| Blocklist/Allowlist | `word_lists.py` | `PDFListManager`      |

---

## 🔒 Security Considerations

### Input Validation

Always validate file paths:

```python
# ✅ GOOD — Validate before use
path = pathlib.Path(user_input).resolve()
if not path.parent.exists():
    raise ValueError(f"Directory not found: {path.parent}")

# ❌ BAD — Direct user input
with open(user_input) as f:
    ...
```

### No Hardcoded Credentials

Never hardcode API keys or passwords.

### Resource Limits

- Avoid unbounded memory growth on large PDFs
- Keep long-running work off the UI thread
- Clean up temp files

---

## 📚 External Resources

| Resource     | Link                                                                  | Purpose            |
| ------------ | --------------------------------------------------------------------- | ------------------ |
| **PyMuPDF**  | [pymupdf.io](https://pymupdf.io/)                                     | PDF API            |
| **PySide6**  | [doc.qt.io/qtforpython](https://doc.qt.io/qtforpython/)               | GUI framework      |
| **spaCy**    | [spacy.io](https://spacy.io/)                                         | NLP models         |
| **Presidio** | [microsoft.github.io/presidio](https://microsoft.github.io/presidio/) | PII detection      |
| **Python**   | [python.org](https://www.python.org/)                                 | Language reference |

---

## ❓ Common Development Questions

### Q: How do I add a new feature?

**A:** 
1. Create feature branch: `git checkout -b feature/my-feature`
2. Edit code following code standards
3. Add tests: `pytest tests/test_my_feature.py`
4. Run full test suite: `pytest tests/ -v`
5. Build locally: `python build_local.py`
6. Commit and push

### Q: How do I test on different OS?

**A:** 
- GitHub Actions runs tests on all 3 OS automatically
- Or use virtual machine (VirtualBox, Parallels) for local testing

### Q: Where do I add new AI detections?

**A:**
1. Add the Presidio entity type (and its dialog label) to `ENTITY_GROUPS` in `pii_detection.py`, plus a threshold in `ENTITY_SCORE_THRESHOLDS`.
2. `AIWorker.run_scan()` analyzes the page text built by `build_page_index()`. Filtering (`filter_results`, `clean_candidates`, `resolve_overlaps`) and offset-to-rectangle mapping (`span_to_rects`, `propagate_whole_word`) live in `pii_detection.py`, which has no Qt dependency and is unit-tested in `tests/test_pii_detection.py`.
3. Detections are filtered through the allowlist in the worker.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for AI pipeline details.

### Q: How do I profile performance?

**A:**
```bash
pip install py-spy

# Profile running app
py-spy record -o profile.svg -- python NullifyPDF.py

# Analyze
py-spy top -- python NullifyPDF.py
```

---

## 🤝 Contributing

Ready to contribute? See [CONTRIBUTING.md](./CONTRIBUTING.md) for:
- PR workflow
- Code review process
- Issue templates
- Commit message standards

---

## 📞 Need Help?

- 📖 **User Guide:** [USER_GUIDE.md](./USER_GUIDE.md)
- 🐛 **Troubleshooting:** [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- 🏗️ **Architecture:** [ARCHITECTURE.md](./ARCHITECTURE.md)
- 🤝 **Contributing:** [CONTRIBUTING.md](./CONTRIBUTING.md)
- 💬 **GitHub Discussions:** [Discussions](https://github.com/overwrite00/NullifyPDF/discussions)
- 🐛 **GitHub Issues:** [Issues](https://github.com/overwrite00/NullifyPDF/issues)

### Release procedure

- **Beta**: work lands on `develop` through squash-merged pull requests; an annotated tag `vX.Y.Z-beta.N` on `develop` starts `beta-release.yml`. Set `__version_prerelease__` in `NullifyPDF.py` to the beta suffix.
- **Stable**: set `__version_prerelease__` to `""`, move the `[Unreleased]` changelog entries under `## [X.Y.Z] - date` (leave `[Unreleased]` empty), merge `develop` into `main` with a merge commit through a pull request (one approving review is required), then tag `vX.Y.Z` on `main`. `release.yml` checks the changelog and the version before building.
- Documentation-only changes do not need a release.
- When dependencies change, update `THIRD_PARTY_NOTICES.md` and `licences_info.py`; `tests/test_licences.py` fails if a non-commercial component would be bundled.

### Release notes and the update check

The release workflows fill each GitHub release body with `scripts/extract_release_notes.py`: the `## [X.Y.Z]` section for stable tags, `## [Unreleased]` for beta tags. The in-app update check displays that body, so keep the changelog sections accurate before tagging.

---

*Last updated: 2026-11-11*  
*← [Troubleshooting](./TROUBLESHOOTING.md) | [Back to README →](./README.md)*
