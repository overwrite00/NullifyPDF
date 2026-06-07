# 👨‍💻 Development Guide — NullifyPDF

Complete guide for developers setting up a local development environment and contributing to NullifyPDF.

> [!IMPORTANT]
> Requires **Python 3.12**. Older versions are not compatible with PyMuPDF wheels.

---

## 📋 System Requirements

Before starting, verify you have:

| 📦 Requirement           | 💾 Space | 📝 Notes                                       |
| ----------------------- | ------- | --------------------------------------------- |
| **Python 3.12**         | 150 MB  | [Download](https://www.python.org/downloads/) |
| **Git**                 | 50 MB   | [Download](https://git-scm.com/)              |
| **Virtual Environment** | 2 GB    | `.venv/` auto-created by setup script         |
| **Disk Space**          | 3 GB    | Dependencies + spaCy models                   |
| **RAM**                 | 4 GB    | 8 GB recommended                              |

---

## 🚀 Quick Start (5 Minutes)

### 1️⃣ Clone Repository

```bash
git clone https://github.com/overwrite00/NullifyPDF.git
cd NullifyPDF
```

### 2️⃣ Verify Python 3.12

```bash
# Windows
py -3.12 --version

# macOS/Linux
python3.12 --version
```

Should output: `Python 3.12.x`

### 3️⃣ Run Automated Setup

```bash
python setup_env.py
```

This automatically:
- ✅ Creates `.venv/` virtual environment
- ✅ Installs dependencies
- ✅ Downloads spaCy models (EN + IT)
- ✅ Runs smoke tests

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
├── NullifyPDF.py              ← Main application (≈2500 lines)
├── PDF_Checker.py             ← Verification utility
├── setup_env.py               ← Environment setup script
├── build_local.py             ← Build executable script
├── requirements.txt           ← Python dependencies
├── tests/
│   ├── test_pdf_manager.py    ← PDFListManager tests
│   ├── test_validation.py     ← Input validation tests
│   └── ...
├── images/
│   └── NullifyPDF.png         ← App logo
└── .github/
    └── workflows/
        └── release.yml        ← CI/CD automation
```

---

## 📦 Dependency Overview

### Core Dependencies

| Package               | Version | Purpose                      |
| --------------------- | ------- | ---------------------------- |
| **pyside6**           | ^6.x    | GUI framework (Qt6 bindings) |
| **pymupdf**           | ^1.24.x | PDF manipulation             |
| **presidio-analyzer** | ^2.2.x  | PII detection (regex-based)  |
| **spacy**             | ^3.7.x  | NLP for entity recognition   |
| **pytest**            | ^8.x    | Testing framework            |

### Language Models (Auto-Downloaded)

| Model             | Size  | Purpose     |
| ----------------- | ----- | ----------- |
| `en_core_web_md`  | 40 MB | English NER |
| `it_core_news_md` | 45 MB | Italian NER |

These are downloaded automatically by `setup_env.py`.

---

## 🔍 Understanding the Code

### Entry Point: `NullifyPDF.py`

**Class Hierarchy:**

```python
NullifyPDFApp(QMainWindow)
├── PDFListManager          # Manages blocklist/allowlist
├── AIWorker(QObject)       # NLP scanning in thread
├── PDFCanvas(QGraphicsView) # PDF rendering
└── UI Components
    ├── Sidebar
    ├── Toolbar
    ├── Progress bar
    ├── Dialogs
```

**Key Methods:**

```python
class NullifyPDFApp:
    def __init__(self)                  # Initialize GUI
    def load_pdf(self, path: str)       # Load PDF file
    def on_auto_redact(self)            # Start AI scan
    def handle_ai_results(self, data)   # Receive AI results
    def on_export_pdf(self)             # Export with redactions
    def add_redaction_box(self, rect)   # Draw on canvas
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
pytest tests/test_pdf_manager.py::test_load_blocklist -v
```

### Test Coverage

```bash
pytest tests/ --cov=. --cov-report=html
```

Opens `htmlcov/index.html` in browser.

### What's Tested

- ✅ **PDFListManager** — File I/O, persistence
- ✅ **Input Validation** — Path handling, type checking
- ✅ **Resource Paths** — PyInstaller compatibility

---

## 🚀 Building a Local Executable

### Quick Build

```bash
python build_local.py
```

**Output:** `dist/NullifyPDF_v2.0.5_Windows.exe` (on Windows)

### What It Does

1. Cleans `build/` and `dist/` directories
2. Detects your OS (Windows/macOS/Linux)
3. Reads version from `NullifyPDF.py` (`__version__`)
4. Compiles with PyInstaller
5. Renames with version: `NullifyPDF_v{VERSION}_{OS}.exe`

### Distribution Artifacts

| OS          | Output                            |
| ----------- | --------------------------------- |
| **Windows** | `.exe` executable                 |
| **macOS**   | `.app` bundle                     |
| **Linux**   | Binary + `.deb` + `.rpm` packages |

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
2. Run in debug mode: `NullifyPDF_v2.0.5_Windows.exe` from PowerShell
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
fix(export): reduce memory usage in forensic scrubbing
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
python3.12 NullifyPDF.py
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

| File               | Purpose                 | Lines |
| ------------------ | ----------------------- | ----- |
| `NullifyPDF.py`    | Main app, GUI, logic    | 2500+ |
| `setup_env.py`     | Environment setup       | 150   |
| `build_local.py`   | PyInstaller build       | 200   |
| `PDF_Checker.py`   | Post-processing utility | 300+  |
| `requirements.txt` | Dependencies            | 10    |
| `tests/`           | Unit tests              | 500+  |

### Quick Edit Locations

| Feature             | File            | Method                |
| ------------------- | --------------- | --------------------- |
| Load PDF            | `NullifyPDF.py` | `load_pdf()`          |
| Auto Redact         | `NullifyPDF.py` | `on_auto_redact()`    |
| AI Processing       | `NullifyPDF.py` | `AIWorker.run_scan()` |
| Export              | `NullifyPDF.py` | `on_export_pdf()`     |
| Blocklist/Allowlist | `NullifyPDF.py` | `PDFListManager`      |

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

- Cap PDF page count for reasonable memory usage
- Timeout long-running operations
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
In `AIWorker.run_scan()`:
1. Use Presidio analyzer for regex patterns
2. Use spaCy models for entity recognition
3. Merge and deduplicate results
4. Filter through allowlist

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

---

*Last updated: 2026-06-06*  
*← [Troubleshooting](./TROUBLESHOOTING.md) | [Back to README →](./README.md)*
