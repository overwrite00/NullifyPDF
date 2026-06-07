# 🏗️ Architecture — NullifyPDF

This document explains the system design, components, and data flow of NullifyPDF. Understanding this helps with contributing code and debugging issues.

> [!TIP]
> Start with [System Overview](#system-overview), then explore specific components based on your interest.

---

## 📋 System Overview

```
┌─────────────────────────────────────────────────────────┐
│                   NullifyPDF Application                 │
├──────────────────┬──────────────────┬──────────────────┤
│   UI Layer       │  Core Logic      │  Data Layer      │
│  (PySide6)       │  (Python)        │  (Persistence)   │
├──────────────────┼──────────────────┼──────────────────┤
│ • Main Window    │ • PDF Engine     │ • Blocklist      │
│ • Canvas/Render  │ • AI Pipeline    │ • Allowlist      │
│ • Dialogs        │ • Text Extract   │ • Logs           │
│ • Sidebar        │ • Redaction      │ • Config         │
│ • Events         │ • Export         │                  │
└──────────────────┴──────────────────┴──────────────────┘
        ↑                    ↑                   ↑
   QThread                 Worker             Disk
   (UI)                  (AI/PDF)          (~/.nullifypdf/)
```

### 🔄 Data Flow

```
User loads PDF
        ↓
[UI Thread] Render in QGraphicsView
        ↓
User clicks "Auto Redact"
        ↓
[Worker Thread] Extract text (QMutex lock)
        ↓
[Worker Thread] Run AI scan (Presidio + spaCy)
        ↓
[Worker Thread] Emit results to UI
        ↓
[UI Thread] Draw redaction boxes on canvas
        ↓
User clicks "Export PDF"
        ↓
[Worker Thread] Disk-backed temp export
        ↓
[Worker Thread] Destructive scrubbing (metadata, links, AcroForms)
        ↓
Export completed ✅
```

---

## 🔧 Core Components

### 1️⃣ Main Entry Point — `NullifyPDF.py`

**Purpose:** Application initialization, GUI setup, event handling.

**Key Classes:**

| Class            | Purpose                         | Threading     |
| ---------------- | ------------------------------- | ------------- |
| `NullifyPDFApp`  | Main application window         | UI Thread     |
| `PDFListManager` | Blocklist/Allowlist persistence | Main          |
| `AIWorker`       | NLP scanning in background      | Worker Thread |
| `PDFCanvas`      | QGraphicsView for PDF rendering | UI Thread     |

**Key Methods:**

```python
class NullifyPDFApp(QMainWindow):
    def load_pdf(path: str) -> None
        # Load PDF, render first page, enable UI controls
        
    def on_auto_redact(self) -> None
        # Emit signal to start AI scan in worker thread
        
    def on_export_pdf(self) -> None
        # Export with forensic scrubbing
        
    def handle_ai_results(results: dict) -> None
        # Receive detections from worker, draw on canvas
```

**Threading Model:**

- **UI Thread:** Rendering, user interactions, dialog management
- **Worker Thread:** `AIWorker` runs NLP without blocking UI
- **Synchronization:** `QMutex` serializes PDF document access

**Key Files:**
- `NullifyPDF.py` (≈2500 lines)

---

### 2️⃣ PDF Engine — PyMuPDF (fitz)

**Purpose:** Load, render, manipulate, and export PDF documents.

**Operations:**

```python
import fitz

# Load PDF
doc = fitz.open("document.pdf")

# Render page to image
page = doc[0]
pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))

# Extract text
text = page.get_text()

# Add annotation (redaction box)
rect = fitz.Rect(100, 100, 200, 150)  # (x0, y0, x1, y1)
annot = page.add_redact_annot(rect)
page.apply_redactions()  # Destructive!

# Destroy metadata
doc.metadata = {}
doc.set_xml_metadata(None)

# Export
doc.save("output.pdf", deflate=True)
```

**In NullifyPDF:**

- **Load:** Read file, detect if encrypted/protected
- **Render:** Convert pages to QImage for display
- **Extract:** Get text for AI analysis (with QMutex lock)
- **Annotate:** Store redaction data (non-destructive, in-memory)
- **Export:** Apply redactions, scrub metadata, flatten forms

**Key Constraints:**

- ✅ PyMuPDF wheels are pre-compiled → **requires Python 3.12**
- ✅ `doc.get_text()` is CPU-bound → run in worker thread
- ✅ Metadata destruction is binary-level → cannot undo after export
- ✅ Digital signatures invalidated after redaction

**See:** [PyMuPDF Documentation](https://pymupdf.io/)

---

### 3️⃣ AI Pipeline — NLP Entity Detection

**Purpose:** Identify Personally Identifiable Information (PII) in extracted text.

**Components:**

```
Extracted Text
      ↓
┌─────────────────────────────────────┐
│  Microsoft Presidio Analyzer        │
│  (PII detection via regexes)        │
│  • IBAN, Credit Cards, Emails       │
│  • Phone numbers, URLs              │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│  spaCy NLP Models (EN/IT)           │
│  (Named Entity Recognition)         │
│  • PERSON, LOCATION, ORG            │
│  • Custom entities (crypto address) │
└─────────────────────────────────────┘
      ↓
Merged Results → Deduplicate → Allowlist Filter
      ↓
Final Detections (coordinates + text)
```

**Models Used:**

| Model               | Language | Size   | Purpose            |
| ------------------- | -------- | ------ | ------------------ |
| `en_core_web_md`    | English  | 40 MB  | General NER        |
| `it_core_news_md`   | Italian  | 45 MB  | General NER        |
| `presidio-analyzer` | Multi    | Custom | PII regex patterns |

**User Language Selection:**

- **EN only:** Use English spaCy + Presidio (fast)
- **IT only:** Use Italian spaCy + Presidio (fast)
- **BOTH:** Run both pipelines, merge results (slower, thorough)

**Allowlist Integration:**

```python
# AI detects: "John Smith", "john@example.com"
# Allowlist contains: "john"

# Pre-compiled allowlist regexes
if is_in_allowlist("john", allowlist_patterns):
    skip_detection  # Don't redact
else:
    add_to_redactions
```

**O(1) Fast-path Optimization:**

```python
# Exact-match check first (fast)
if detected_text in allowlist_set:
    skip  # Common case (90%)
else:
    # Regex matching fallback (slow)
    for pattern in allowlist_regexes:
        if pattern.match(detected_text):
            skip
```

**See:**
- [Presidio Documentation](https://microsoft.github.io/presidio/)
- [spaCy Models](https://spacy.io/models)

---

### 4️⃣ Data Persistence — `PDFListManager`

**Purpose:** Save and load Blocklist/Allowlist from disk.

**Storage Location:**

| OS              | Path                               |
| --------------- | ---------------------------------- |
| **Windows**     | `C:\Users\<username>\.nullifypdf\` |
| **macOS/Linux** | `~/.nullifypdf/`                   |

**File Structure:**

```
~/.nullifypdf/
├── blocklist.txt          (words to always redact)
├── allowlist.txt          (words to never redact)
├── logs/
│   └── nullifypdf.log     (rotating, max 5 MB per file)
```

**Format:**

- One word per line
- Lowercase, trimmed whitespace
- UTF-8 encoding
- Mutual exclusivity: word cannot be in both lists

**Example:**

```text
# blocklist.txt
john smith
acme corp
admin@company.com

# allowlist.txt
and
the
common
```

**Implementation:**

```python
class PDFListManager:
    def load_blocklist(self) -> Set[str]:
        """Load from ~/.nullifypdf/blocklist.txt"""
        
    def save_allowlist(self, allowlist: Set[str]) -> None:
        """Persist to ~/.nullifypdf/allowlist.txt"""
        
    # Mutual exclusivity check
    if word in blocklist:
        blocklist.remove(word)  # Remove from block if in allow
```

---

### 5️⃣ Threading & Synchronization

**Problem:** PDF document operations are CPU-bound. Running NLP analysis on UI thread freezes the GUI.

**Solution:** Background worker thread with `QMutex` synchronization.

**Architecture:**

```
┌──────────────────────────────────────┐
│ Main Qt Event Loop (UI Thread)       │
│                                      │
│  • Handle user clicks                │
│  • Render PDF pages                  │
│  • Update progress bar               │
│                                      │
│ ┌────────────────────────────────┐  │
│ │ QMutex Lock                    │  │
│ │ (Access PDF document safely)   │  │
│ │ fitz.open().get_text() {       │  │
│ │    locked access only          │  │
│ │ }                              │  │
│ └────────────────────────────────┘  │
└──────────────────────────────────────┘
             ↑ Signals
             │
┌────────────────────────────────────────┐
│ AIWorker Thread (Background)           │
│                                        │
│  1. Lock QMutex                        │
│  2. Extract text: doc.get_text()       │
│  3. Unlock QMutex                      │
│  4. Run NLP (no lock needed)           │
│  5. Emit signal: results_ready.emit() │
│                                        │
│ Runs in: QThreadPool                  │
└────────────────────────────────────────┘
```

**Signal/Slot Pattern:**

```python
class AIWorker(QObject):
    results_ready = Signal(dict)  # Emitted when scan done
    progress_update = Signal(int)  # Emitted for progress bar
    
    def run_scan(self) -> None:
        # Acquire lock
        with QMutexLocker(self.mutex):
            text = self.pdf_doc.get_text()
        
        # Run AI (no lock, safe in worker thread)
        detections = self.analyze_text(text)
        
        # Signal results back to UI
        self.results_ready.emit(detections)

# In main UI thread
worker.results_ready.connect(self.on_redactions_detected)
```

**Key Guarantees:**

✅ UI never blocks  
✅ PDF document accessed safely (one thread at a time)  
✅ No race conditions  
✅ Progress updates smooth  

---

### 6️⃣ Export Pipeline (Forensic Scrubbing)

**Problem:** In-memory PDF modification could use 2x RAM (original + modified copy).

**Solution:** Disk-backed temporary file with lazy parsing.

**Flow:**

```
1. Load original PDF into memory
        ↓
2. Create temp file (disk-backed)
        ↓
3. For each page:
   a. Copy page from original
   b. Apply redaction annotations
   c. Destroy metadata, links, AcroForms
   d. Write to temp file
        ↓
4. Once complete, move temp → final output
        ↓
5. Original + temp deleted
```

**Memory Efficiency:**

```python
# OLD (Memory doubling) ❌
doc = fitz.open("input.pdf")
doc.saveIncr()  # Doubles RAM usage

# NEW (Memory efficient) ✅
doc = fitz.open("input.pdf")
temp = fitz.open()  # Empty doc
for page_num in range(doc.page_count):
    page = doc[page_num]
    temp.insert_pdf(doc, page_num, page_num)
    # Temp is smaller, only current page in buffer
temp.save("output.pdf")  # Atomic write
```

**Destructive Operations:**

| Operation                | Effect                           | Reversible?           |
| ------------------------ | -------------------------------- | --------------------- |
| **Redaction overlay**    | Covers text with black box       | No (binary destroyed) |
| **Metadata removal**     | Strips /Info, /CreationDate      | No                    |
| **Link destruction**     | Removes /Annot array entries     | No                    |
| **AcroForms flattening** | Disables interactive fields      | No                    |
| **Digital signature**    | Becomes invalid (binary changed) | No                    |

---

## 📊 Logging & Diagnostics

### Log Locations

| OS              | Path                                                  |
| --------------- | ----------------------------------------------------- |
| **Windows**     | `C:\Users\<username>\.nullifypdf\logs\nullifypdf.log` |
| **macOS/Linux** | `~/.nullifypdf/logs/nullifypdf.log`                   |

### Log Format

```
2026-06-06 14:23:45 - INFO - Loaded PDF: /path/to/document.pdf
2026-06-06 14:23:46 - DEBUG - Page count: 10
2026-06-06 14:23:50 - INFO - AI scan complete: 5 detections found
2026-06-06 14:24:10 - ERROR - Export failed: Permission denied
2026-06-06 14:24:10 - DEBUG - Traceback: ...
```

### Debug Mode

Enable verbose logging via environment variable:

```bash
# Windows (PowerShell)
$env:NULLIFYPDF_DEBUG = "true"
python NullifyPDF.py

# macOS/Linux (Bash)
export NULLIFYPDF_DEBUG=true
python3.12 NullifyPDF.py
```

**Effect:** Log level changes from `INFO` to `DEBUG`, includes full stack traces.

### Log Rotation

- Max file size: 5 MB
- Backup count: 3 (old logs auto-deleted)
- Encoding: UTF-8

---

## 🛠️ Utility Scripts

### `setup_env.py` — Environment Configuration

**Purpose:** Prepare development environment on any OS.

**Steps:**

1. Detect OS (Windows/macOS/Linux)
2. Create virtual environment with Python 3.12
3. Upgrade pip, setuptools, wheel
4. Install requirements.txt dependencies
5. Download spaCy models (EN + IT)
6. Run smoke tests

**Dependencies Added:**

- `pyside6` — GUI framework
- `pymupdf` — PDF manipulation
- `presidio-analyzer` — PII detection
- `spacy` — NLP engine
- `pytest` — Testing framework

---

### `build_local.py` — Executable Compilation

**Purpose:** Generate standalone executable for distribution.

**Process:**

1. Clean temporary directories (`build/`, `dist/`)
2. Detect OS (Windows/macOS/Linux)
3. Read version from `NullifyPDF.py` (`__version__`)
4. Run PyInstaller with OS-specific settings
5. Rename executable: `NullifyPDF_v2.0.5_Windows.exe`

**Output Artifacts:**

- **Windows:** `.exe` executable
- **macOS:** `.app` bundle (signed, if certificate available)
- **Linux:** Binary + optional `.deb`, `.rpm` packages

**PyInstaller Configuration:**

```python
# Bundles:
# - NullifyPDF.py
# - All .py dependencies
# - spaCy models
# - Resource files (images/)

# Excludes (to reduce size):
# - Development tools
# - Test files
# - Docs
```

---

### `PDF_Checker.py` — Post-Processing Analysis

**Purpose:** Verify exported PDF for successful redaction.

**Features:**

- Scan for remaining text under redaction boxes
- Check metadata was removed
- Verify links destroyed
- Confirm AcroForms flattened

**Usage:**

```bash
python PDF_Checker.py output.pdf
```

---

## 📁 File Structure

```
NullifyPDF/
├── NullifyPDF.py              ← Main application (GUI, logic)
├── PDF_Checker.py             ← Utility for verification
├── setup_env.py               ← Environment setup
├── build_local.py             ← Build executable
├── requirements.txt           ← Python dependencies
├── README.md                  ← English overview
├── README_IT.md               ← Italian version
├── USER_GUIDE.md              ← Usage instructions
├── CONTRIBUTING.md            ← Contributor guidelines
├── ARCHITECTURE.md            ← This file
├── CHANGELOG.md               ← Release history
├── LICENSE                    ← MIT License
├── images/
│   └── NullifyPDF.png         ← App logo
├── tests/
│   ├── test_pdf_manager.py    ← PDFListManager tests
│   ├── test_validation.py     ← Input validation tests
│   └── ...
└── .github/
    └── workflows/
        └── release.yml        ← CI/CD automation
```

---

## 🔐 Security Considerations

### What's Protected

✅ **Data Destruction** — Binary-level scrubbing, not recoverable  
✅ **Offline Processing** — No network calls (except GitHub release checks)  
✅ **Input Validation** — Path traversal, type checking, bounds  
✅ **Resource Limits** — Graceful handling of large PDFs  

### What's NOT in Scope

❌ **OCR** — Scanned images not analyzed  
❌ **Handwriting** — Not digitized text  
❌ **Password Cracking** — Encrypted PDFs rejected at load  
❌ **Signature Forgery** — Signatures invalidated, not forged  

---

## 🚀 Performance Characteristics

### Typical Operations

| Operation                | Time          | Scaling                   |
| ------------------------ | ------------- | ------------------------- |
| Load PDF (100 pages)     | 500 ms        | O(n pages)                |
| Extract text (100 pages) | 2-5 seconds   | O(n pages)                |
| AI scan (100 pages)      | 10-30 seconds | O(n pages × n words)      |
| Export with redaction    | 15-60 seconds | O(n pages × n redactions) |

### Memory Usage

| Scenario                 | RAM        | Optimization       |
| ------------------------ | ---------- | ------------------ |
| Small PDF (10 pages)     | 50-100 MB  | Efficient          |
| Large PDF (500 pages)    | 200-500 MB | Disk-backed export |
| Very large (1000+ pages) | May swap   | Consider splitting |

### Optimization Opportunities

1. **Allowlist caching** — Pre-compile regexes (done ✅)
2. **Text extraction parallelism** — Multiple pages at once (future)
3. **GPU acceleration** — For spaCy models (future)
4. **Lazy loading** — Only load pages user views (future)

---

## 🔄 Development Workflow

### Adding a New Feature

1. **Create branch:** `git checkout -b feature/your-feature develop`
2. **Write code:** Follow standards in [CONTRIBUTING.md](./CONTRIBUTING.md)
3. **Add tests:** Cover happy path + edge cases
4. **Run smoke tests:** `pytest tests/ -v`
5. **Build locally:** `python build_local.py`
6. **Update CHANGELOG.md:** Document changes
7. **Open PR:** Describe what + why

### Debugging Tips

1. **Enable debug mode:**
   ```bash
   export NULLIFYPDF_DEBUG=true
   python3.12 NullifyPDF.py
   ```

2. **Check logs:** `~/.nullifypdf/logs/nullifypdf.log`

3. **Add print statements:**
   ```python
   logger.debug(f"Variable value: {var}")  # Use logging, not print()
   ```

4. **Test in isolation:**
   ```bash
   pytest tests/test_specific.py::test_function -v
   ```

---

## 📚 External Resources

| Resource                                            | Purpose                |
| --------------------------------------------------- | ---------------------- |
| [PyMuPDF Docs](https://pymupdf.io/)                 | PDF manipulation API   |
| [PySide6 Docs](https://doc.qt.io/qtforpython/)      | GUI framework          |
| [spaCy Models](https://spacy.io/models)             | NLP entity recognition |
| [Presidio](https://microsoft.github.io/presidio/)   | PII detection patterns |
| [Qt Threading](https://doc.qt.io/qt-6/qthread.html) | Thread synchronization |

---

## ❓ Questions?

- 💬 See [CONTRIBUTING.md](./CONTRIBUTING.md) for contact info
- 🐛 Report issues on [GitHub Issues](https://github.com/overwrite00/NullifyPDF/issues)
- 📖 Read [USER_GUIDE.md](./USER_GUIDE.md) for usage questions

---

*Last updated: 2026-06-06*  
*← [Back to README](./README.md) | [Contributing →](./CONTRIBUTING.md)*
