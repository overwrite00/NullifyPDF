# 🏗️ Architecture — NullifyPDF

This document explains how NullifyPDF is structured today: application layers, privacy export flow, OCR support, release variants, and the main security boundaries that matter during maintenance.

> [!TIP]
> Read this after the [README](./README.md) if you want the technical view of how detection, redaction, pseudonymization, and packaging work together.

---

## 📋 Current Scope

NullifyPDF is a local-first desktop application for preparing PDFs before they are shared with third parties or uploaded to AI systems.

It supports two privacy export modes:

- **Irreversible anonymization** — selected content is redacted and removed from the exported PDF
- **Reversible pseudonymization** — selected content is replaced with stable placeholders, while original values are stored in a separate encrypted restore map

> [!NOTE]
> Reversible mode is pseudonymization, not true anonymization, because the encrypted restore map can re-identify the original values.

---

## 🧩 High-Level Components

| 📄 File | ✨ Responsibility |
| ------ | ----------------- |
| `NullifyPDF.py` | Main PySide6 UI, PDF rendering, AI scan orchestration, redaction, export, OCR integration |
| `privacy_core.py` | Privacy mode enum, placeholder registry, encrypted restore-map payloads |
| `PDF_Checker.py` | Heuristic post-export inspection helper |
| `build_local.py` | PyInstaller build script with Lite/Full release variants |
| `scripts/download_ocr_data.py` | Downloads EN/IT Tesseract `tessdata_fast` files for Full builds |
| `tests/` | Unit and smoke tests for validation, privacy primitives, OCR config, and build variants |

---

## 🧠 Runtime Architecture

```text
User
  |
  v
PySide6 UI (NullifyPDF)
  |
  |-- PDFView renders the current page with PyMuPDF pixmaps
  |-- Manual redaction draws pending redaction annotations
  |-- Export dialog selects anonymization or pseudonymization
  |
  v
AIWorker (QThread)
  |
  |-- Extracts digital text from pages
  |-- Runs OCR on scanned/image-only pages when enabled
  |-- Runs Presidio + spaCy entity detection
  |-- Emits detections back to UI thread
  |
  v
UI thread applies pending redaction annotations
  |
  v
Export pipeline writes a cleaned PDF copy
```

---

## 🏛️ Main Classes

| 🧱 Class | 📍 Location | 🎯 Purpose |
| ------- | ----------- | ---------- |
| `PDFListManager` | `NullifyPDF.py` | Loads and saves blocklist/allowlist files in `~/.nullifypdf` |
| `AIWorker` | `NullifyPDF.py` | Background NLP/OCR worker that emits page-level detections |
| `PDFView` | `NullifyPDF.py` | Custom `QGraphicsView` for rendering pages, drawing rectangles, and zooming |
| `NullifyPDF` | `NullifyPDF.py` | Main window and application controller |
| `PlaceholderRegistry` | `privacy_core.py` | Creates stable placeholders such as `PERSON_001` and `EMAIL_ADDRESS_001` |

---

## 🔄 Data Flow

### 📂 Load

1. User opens or drops a PDF.
2. `NullifyPDF.load_path()` validates the path and extension.
3. PyMuPDF opens the document.
4. Password-protected PDFs are rejected.
5. The first page is rendered in `PDFView`.
6. `_warn_if_scanned_pdf()` warns when pages look image-only and may need OCR.

### 🤖 AI Scan

1. User selects language: `EN`, `IT`, or `BOTH`.
2. User optionally enables:
   - `OCR PDF scansionati`
   - `Oscura Immagini`
3. `cmd_auto_ai()` checks OCR configuration if OCR is enabled.
4. `AIWorker.run_scan()` processes pages in a background thread.
5. For each page:
   - digital text is extracted with `page.get_text()`
   - if the page looks scanned, OCR is run with `page.get_textpage_ocr()`
   - Presidio analyzes the extracted/OCR text
   - detected entities are emitted with text, entity type, source, and optional OCR rectangles
6. `apply_ai_to_page()` runs on the UI thread and creates pending redaction annotations.

### 🖊️ Manual Review

Redactions remain annotations until export. The original in-memory document is not flattened while the user is reviewing it.

Manual drawing over text:

- adds a redaction annotation
- records the clipped text in annotation metadata when available
- adds the text to the blocklist

Clicking an existing redaction:

- removes the pending annotation
- adds the clipped text to the allowlist when available

---

## 🛡️ Privacy Export Pipeline

`cmd_export()` is the main export entry point.

1. User chooses privacy mode:
   - irreversible anonymization
   - reversible pseudonymization
2. User chooses output PDF path.
3. For pseudonymization only:
   - user chooses `.nullifypdf-map` path
   - user enters a password of at least 12 characters
   - `cryptography` availability is checked before writing output
4. The in-memory PDF is saved to a sibling temp file:
   - `<target>.nullifypdf.tmp`
5. The temp PDF is reopened as `ex_doc`.
6. Each page is processed:
   - overlapping links are deleted for redacted areas
   - redactions are applied with PyMuPDF
   - widgets are removed
7. Document metadata and selected catalog keys are cleared.
8. The final PDF is saved with cleanup options.
9. The temp file is removed.

The original open document remains editable after export because the export works on a disk-backed copy.

---

## 🔒 Anonymization Mode

Irreversible anonymization applies redaction annotations directly. The exported PDF does not contain a restore map.

This mode should be used when the output PDF must not contain recoverable personal data from the selected redaction areas.

> [!WARNING]
> Residual risk still exists for complex PDFs. NullifyPDF removes selected redacted content and common metadata, form, and link structures, but the output should still be reviewed before high-risk sharing.

---

## 🔐 Pseudonymization Mode

Reversible pseudonymization replaces each selected value with a placeholder.

Example placeholders:

```text
PERSON_001
EMAIL_ADDRESS_001
IBAN_CODE_001
PHONE_NUMBER_001
DATA_001
```

The mapping is stored in a separate encrypted file:

```text
document.nullifypdf-map
```

The restore map contains:

- source filename
- source SHA-256 when available
- output SHA-256
- placeholder entries
- original values
- entity types
- page numbers

The map is encrypted with `cryptography` using Fernet and a key derived from the user password with PBKDF2-HMAC-SHA256.

> [!IMPORTANT]
> The restore map is never embedded in the pseudonymized PDF.

---

## 🔎 OCR Architecture

OCR is implemented through PyMuPDF's integrated Tesseract support.

Runtime behavior:

1. `find_tessdata_dir()` resolves Tesseract language data in this order:
   - `TESSDATA_PREFIX`
   - bundled `ocr/tessdata` via `resource_path()`
   - PyMuPDF's `fitz.get_tessdata()`
   - common platform locations
2. `ocr_language_for_choice()` maps UI language to Tesseract codes:
   - `EN` -> `eng`
   - `IT` -> `ita`
   - `BOTH` -> `eng+ita`
3. `AIWorker._page_needs_ocr()` runs OCR only when text extraction is missing or very poor.
4. OCR text is used for Presidio detection.
5. OCR search rectangles are used to place redactions on scanned pages.

The Full release bundles EN/IT OCR data. The Lite release requires local Tesseract `tessdata` when OCR is enabled.

---

## 🧵 Threading Model

The UI thread owns rendering and document mutation.

The worker thread performs text extraction, OCR, and NLP analysis. Access to the shared PyMuPDF document is serialized with `QMutex`.

Important rules:

- `AIWorker` should not mutate page annotations
- `apply_ai_to_page()` runs on the UI thread
- export happens after detection and review, not during the worker scan

This separation prevents UI freezes and reduces concurrent document-mutation risks.

---

## 📦 Build Variants

### 🪶 Lite

Lite builds do not bundle OCR language data. They are smaller and still support OCR if the user has Tesseract `tessdata` configured locally.

### 🧰 Full

Full builds bundle:

```text
ocr/tessdata/eng.traineddata
ocr/tessdata/ita.traineddata
```

If the files are missing, `build_local.py --full` automatically downloads them from `tesseract-ocr/tessdata_fast` through `scripts/download_ocr_data.py`.

The `.traineddata` files are ignored by git and are not stored in the repository.

---

## 🚀 CI/CD

GitHub Actions build both variants on each supported OS:

- Windows Lite / Full
- macOS Lite / Full
- Ubuntu Lite / Full
- Fedora Lite / Full

Beta releases build and upload all artifacts. Stable releases promote the latest verified beta artifacts without recompilation.

Expected artifact names include:

```text
NullifyPDF_vX.Y.Z_Windows_Lite.exe
NullifyPDF_vX.Y.Z_Windows_Full.exe
NullifyPDF_vX.Y.Z_macOS_Lite.zip
NullifyPDF_vX.Y.Z_macOS_Full.zip
NullifyPDF_vX.Y.Z_Ubuntu_Lite.deb
NullifyPDF_vX.Y.Z_Ubuntu_Full.deb
NullifyPDF_vX.Y.Z_Fedora_Lite.rpm
NullifyPDF_vX.Y.Z_Fedora_Full.rpm
```

---

## 🧪 Tests

Current tests cover:

- list persistence
- resource path resolution
- OCR configuration helpers
- privacy placeholder registry
- encrypted restore-map round trip
- build variant selection
- Full build OCR data inclusion behavior

Run:

```bash
pytest tests/ -v
```

---

## ⚠️ Known Limits

- Detection is probabilistic. Presidio, spaCy, and OCR can miss data or create false positives.
- OCR depends on Tesseract language data and scan quality.
- Handwriting is not reliably supported.
- Complex PDFs may contain structures not covered by automated cleanup.
- Pseudonymized PDFs are still personal-data processing when the restore map exists.
- Digital signatures are invalidated by privacy export.

> [!WARNING]
> For high-risk workflows, exported PDFs should be reviewed independently before sharing.

---

*Last updated: 2026-07-23*  
*[Back to README](./README.md) | [Development →](./DEVELOPMENT.md)*
