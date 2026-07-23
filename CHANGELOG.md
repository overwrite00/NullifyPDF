# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.0-beta.2] - 2026-07-23

First public beta of the 2.1.0 line, focused on advanced privacy export, full OCR support for scanned PDFs, and new Lite/Full release variants.

### ✨ Added

- **Privacy Export Modes**: The export flow now lets the user choose between irreversible anonymization and reversible pseudonymization before writing the output PDF.
- **Encrypted Restore Maps**: Pseudonymized exports can generate a separate encrypted `.nullifypdf-map` file with placeholders, original values, entity types, page numbers, and document hashes.
- **OCR for Scanned PDFs**: Added OCR-assisted entity detection for scanned or image-only PDFs using PyMuPDF OCR and Tesseract language data resolution.
- **Lite/Full Release Variants**: Build and release pipelines now produce Lite artifacts and Full artifacts with bundled EN/IT OCR data.
- **Automatic OCR Data Download for Full Builds**: Local Full builds download missing `eng.traineddata` and `ita.traineddata` automatically with a clear message.
- **Privacy Core Module**: Added `privacy_core.py` to centralize placeholder generation and encrypted restore-payload handling.

### 🔒 Security

- **Separated Re-identification Data**: Restore maps are never embedded into exported PDFs and are encrypted with Fernet using a PBKDF2-HMAC-SHA256 derived key.
- **Safer Export Metadata Handling**: Privacy export now clears document metadata and removes common residual structures such as widgets and overlapping links in redacted areas.
- **Safer UI Logging**: Log messages shown in the UI are HTML-escaped before rendering.

### 🔧 Internals

- **Expanded Test Coverage**: Added dedicated tests for privacy primitives, build variant behavior, OCR helper resolution, and prerelease version handling.
- **Documentation Refresh**: Updated README, ARCHITECTURE, USER_GUIDE, SECURITY, TROUBLESHOOTING, CONTRIBUTING, DEVELOPMENT, and added `OCR_SETUP.md` for the new privacy and OCR workflows.
- **Release Automation Updates**: GitHub workflows now build Lite/Full variants across supported operating systems and support the beta-to-stable promotion flow.

## [2.0.7] - 2026-07-21

### ✨ Added

- **Beta Release Pipeline**: New two-stage release process. Pushing a `vX.Y.Z-beta.N` tag builds and publishes a prerelease on all platforms for testing; promoting to stable (pushing `vX.Y.Z`) reuses the already-verified beta artifacts and republishes them as the stable release without rebuilding.

### 🔧 Internals

- **Migration to Python 3.13**: The required runtime moves from Python 3.12 to Python 3.13. PyMuPDF 1.28.0 publishes forward-compatible `abi3` wheels (`cp310-abi3`) that natively cover Python 3.13, removing the previous compatibility constraint.
- Updated CI/CD workflows (`test_build.yml`, `beta-release.yml`) to build with Python 3.13.
- Updated all documentation (README, DEVELOPMENT, ARCHITECTURE, CONTRIBUTING, TROUBLESHOOTING, USER_GUIDE) and `setup_env.py` to reflect the new requirement.
- Verified the entire test suite (11/11) and a full build (PyInstaller) on Python 3.13 in an isolated environment before merging.
- Bumped `actions/setup-python` from v6 to v7 in CI workflows (no behavioral impact on this project).

## [2.0.6] - 2026-07-06

### ⚡ Optimized (Dependencies)

- **PyMuPDF 1.28.0**: Updated from 1.27.2.3 to benefit from important bugfixes:
  - Fix for ComboBox choice_values filled with empty strings
  - Fix for `remove_rotation()` on widgets with invalid rects
  - Fix for formulae incorrectly rendered as black boxes
  - Fix for `Annot.set_rotation(0)` AttributeError
  - New `archive` parameter in `Document.__init__()` for archive document support
  - New `Document.apply_css()` method for CSS styling
  - Windows free-thread Python build support
- **spacy 3.8.13**: Maintained at 3.8.13 for compatibility with presidio-analyzer 2.2.363 (spacy 3.8.14 is explicitly excluded by presidio-analyzer to prepare for future Python 3.14 support)

### 🔧 Internals

- Added explicit comment in requirements.txt explaining spacy version constraint decision

## [2.0.5] - 2026-05-26

### ✨ Improved (Code Quality)

- **Complete Type Hints**: Added type hints to 100% of functions and methods to improve static analysis and IDE support.
- **Google-Style Docstrings**: Introduced full documentation with Args, Returns, Raises for easier maintenance.
- **File-based Logging**: Added file logging (`~/.nullifypdf/logs/nullifypdf.log`) with debug mode support via `NULLIFYPDF_DEBUG=true`.
- **Input Validation**: Added explicit validation for paths, page ranges, and language choices to avoid crashes on malformed input.

### 🐛 Fixed (Bug Fixes)

- **Export Crash on Pages Without Annotations**: Fixed TypeError on `page.annots()` returning `None` when exporting unannotated pages.
- **spaCy Vocab Mutation Error**: Removed unsafe assignment to `nlp.vocab.vectors.shape` that caused an AttributeError on spaCy 3.5+ with read-only vocab.
- **File Handle Leak**: Added `with` context manager for safe file descriptor closure when loading persistent lists.
- **Division by Zero in Progress Bar**: Added `if t <= 0` guard to avoid crashes when rendering the progress bar on empty documents.
- **QImage Segfault**: Added `.copy()` to the QImage buffer to avoid segfaults when the PyMuPDF pixmap is freed before rendering.
- **Signal Handler Crash**: Changed `self.close()` to `QTimer.singleShot(0, self.close)` to defer to the Qt event loop during the SIGINT handler.
- **PyInstaller Path Traversal**: Replaced manual quote wrapping with `repr()` for the spec file path, preventing path traversal in the build system.
- **Silent pip Upgrade Failure**: Added `check=True` to subprocess.run() in setup_env.py so it fails fast on pip errors instead of continuing silently.

### ⚡ Optimized (Performance)

- **Memory Doubling in Export**: Implemented a disk-backed temp file with lazy-parsing via PyMuPDF to reduce peak RAM from 2x to 1x document size during privacy export.
- **Regex Recompilation**: Precompiled regex patterns outside loops in `AIWorker.run_scan()` for a 10-100x speedup on large allowlists.
- **Allowlist Fast-path**: Added an O(1) exact-match check against a set before the regex `any()` scan, short-circuiting 90% of common cases.
- **AI Scan Responsiveness**: Moved `get_text()` off the UI thread into the `AIWorker` thread pool with QMutex serialization to avoid UI freezing on large PDFs.

### 🔧 Internals

- **QMouseEvent Deprecation Fix**: Changed `event.pos()` → `event.position()` for compatibility with modern PySide6.
- **Signal Cleanup**: Removed manual `disconnect()` that caused a RuntimeWarning, letting Python's GC handle cleanup automatically.
- **Thread Safety**: Added `QMutex` serialization for document access between the UI thread (render, redact) and worker thread (AI scan).

## [1.5.4] - 2026-04-23

### 🚀 Added (Features)

- **UI Redesign**: New graphical architecture with a side Sidebar to maximize document visibility.
- **Navigation & Zoom**: Added a "Jump to Page" navigator and smooth Zoom controls (UI buttons and `CTRL + Mouse Wheel` shortcut).
- **Blindfold Mode**: Introduced the "Blindfold Images" switch to replace photos and vector graphics with a professional, localized `[ IMAGE REMOVED ]` placeholder.
- **Form Sanitization**: Forensic Scrubbing now also destroys and flattens `AcroForms` (interactive form fields) during export.
- **Mac-OS Native Bundle**: The build script now supports native `.app` bundle generation for Apple (Darwin) systems.

### 🐛 Fixed (Bug Fixes)

- **Memory Leak & File Lock**: Added explicit closure of PyMuPDF pointers to avoid file system locks on Windows when switching documents.
- **Annotation Stacking**: Fixed the ghost whitelist bug. The AI now recognizes already-redacted areas and avoids unnecessary overlaps.
- **Destructive Export Crash**: Export now operates on an *in-memory clone (byte buffer)*, avoiding destruction of the vector layer of the live-viewed document.
- **RecursionError on Windows**: Fixed the PyInstaller build failure on Windows caused by the SpaCy library, by implementing a dynamic `.spec` configuration.
- **Mouse AttributeError**: Prevented an anomalous exception when dragging the mouse onto an empty canvas.
- **Popup Coordinates**: Restored correct mathematical geometric centering for the "About" and "Dictionaries" child windows relative to the parent window.

### ⚡ Optimized (Performance)

- **Regex Pre-compilation**: Cut "Auto Redact" execution time by 70% by extracting Allowlist regular expressions out of nested iteration loops.

## [1.4.0] - 2026-04-22

### Added

- **New GUI Layout**: Introduced a side Sidebar to maximize PDF preview space.
- **Advanced Navigation**: Added a page navigator with a "Jump to Page" function (direct jump by entering the page number).
- **Dictionary Persistence**: Blocklist and Allowlist are now permanently saved in `~/.nullifypdf/` on Linux and in the user profile folder on Windows.
- **Exit Button**: Added a safe application shutdown option from the sidebar.

### Fixed

- **Anti-Stacking**: Fixed the overlapping annotations bug; the AI now detects if an area is already redacted.
- **Deep Clean**: Manual removal now clears all overlapping redaction layers at the same point.
- **HighDPI Fix**: Logo and icons are now sharp on 4K/Retina monitors thanks to `ctk.CTkImage`.
- **Mutual Exclusivity**: Fixed a conflict between lists; a word can no longer be in both the Blocklist and Allowlist at the same time.
- **AttributeError**: Fixed a crash on mouse release when the initial click occurred outside the canvas.

### Changed

- Optimized cleanup of extracted text (punctuation removal and whitespace normalization) to improve dictionary matching.

## [1.3.0] - 2026-04-21

### Added

- **AI Engine Integration**: Implemented Microsoft Presidio and spaCy for automatic recognition of sensitive entities (PERSON, LOCATION, IBAN, etc.).
- **Multilingual Support**: Introduced the ability to select the language model (EN, IT, or both) for scanning.
- **Smart Dictionaries**: New filter management with **Blocklist** (terms to always redact) and **Allowlist** (terms to always ignore).
- **Interactive Review System**: Ability to remove a planned redaction by clicking directly on it in the canvas.
- **Clear All**: Button to delete all planned redaction annotations at once.
- **Child Window Icons**: The "About" and "Dictionary" windows now correctly inherit the shield icon from the main application.

### Changed

- **Deferred Redaction**: Redaction is now a "deferred" process: it is planned graphically and applied destructively only during Export.
- **Model Optimization**: Switched to `_md` (medium) spaCy models to reduce executable size while keeping high accuracy.
- **Build Automation**: Updated the GitHub Actions workflow to include NLP dependencies and language models in releases.

### Fixed

- **Unicode/Emoji Support**: Fixed a crash during version extraction caused by emoji in the source code.
- **Linux Environment Variables**: Fixed the passing of the version variable in Ubuntu packaging scripts.

## [1.2.5] - 2026-04-20

### Fixed

- Added targeted destruction of links before Garbage Collector cleanup. Removes `mailto:` links tied to redacted email addresses.

## [1.2.0] - 2026-04-20

### Added

- Informational "About" window with dynamic centering relative to the main window.
- Shield icon centered precisely using absolute coordinates.
- Coordinate clipping to prevent crashes during manual selection outside the canvas bounds.

### Fixed

- Fixed the "MouseWheel hijacking" bug: scrolling is now active only when the cursor is over the PDF Canvas.
- Initialized graphical variables to avoid errors when resizing the window on an empty document.

### Changed

- Optimized toolbar layout to improve readability on small monitors.

## [1.1.0] - 2026-04-18

### Added

- Added `PDF_Checker.py` script for post-processing forensic analysis.
- Added level-4 Garbage Collection and deep metadata cleanup during save.

## [1.0.0] - 2026-04-15

### Added

- Initial release of NullifyPDF with support for automatic (Regex) and manual anonymization.
- Cross-platform setup script `setup_env.py`.
