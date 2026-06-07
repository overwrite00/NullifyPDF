# 🤝 Contributing to NullifyPDF

Thank you for your interest in improving NullifyPDF! This guide explains how to contribute code, report bugs, and help grow this project.

> [!IMPORTANT]
> All contributions must follow the standards outlined in this document. Questions? Open a [discussion](https://github.com/overwrite00/NullifyPDF/discussions).

---

## 📋 Quick Start for Contributors

### 1️⃣ Fork & Clone

```bash
# Fork on GitHub, then:
git clone https://github.com/YOUR_USERNAME/NullifyPDF.git
cd NullifyPDF
git remote add upstream https://github.com/overwrite00/NullifyPDF.git
```

### 2️⃣ Set Up Development Environment

```bash
python setup_env.py
```

This creates isolated venv, installs dependencies, and downloads NLP models.

### 3️⃣ Create Feature Branch

```bash
# Update main branch
git fetch upstream
git checkout -b feature/your-feature-name develop

# Example names:
# feature/ai-entity-detection
# fix/export-memory-leak
# docs/installation-guide
```

### 4️⃣ Make Changes & Test

```bash
# Activate venv
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows

# Make your changes...

# Run tests
pytest tests/ -v

# Build to verify compilation
python build_local.py
```

### 5️⃣ Commit with Clear Messages

See [Commit Message Format](#commit-message-format) below.

### 6️⃣ Push & Open PR

```bash
git push origin feature/your-feature-name
```

Then open Pull Request on GitHub with description from template.

---

## ✨ What We're Looking For

### 🎯 Accepted Contributions

✅ **Bug Fixes** — Crashes, memory leaks, incorrect behavior  
✅ **Performance** — Optimization, reduced memory usage  
✅ **Features** — New functionality (discuss first in issues)  
✅ **Documentation** — README, guides, API docs, examples  
✅ **Tests** — Improved coverage, edge cases  
✅ **Build/CI** — GitHub Actions improvements, cross-platform fixes  

### ❌ Not Currently Accepting

❌ **Major Architecture Changes** — Discuss first via issue  
❌ **New Dependencies** — Heavy libraries (keep slim & local)  
❌ **OCR Implementation** — Out of scope (use Blindfold Mode instead)  
❌ **Cloud Features** — Must remain 100% local  

> [!TIP]
> Want to work on something big? Open an issue first to discuss approach and get buy-in.

---

## 📝 Code Standards

### Type Hints (100% Required)

All functions must have complete type hints. This improves IDE support and catches bugs early.

```python
# ✅ GOOD
def extract_text(pdf_path: str, page_num: int) -> str:
    """Extract text from PDF page.
    
    Args:
        pdf_path: Path to PDF file
        page_num: Page number (0-indexed)
        
    Returns:
        Extracted text as string
        
    Raises:
        FileNotFoundError: If PDF not found
        ValueError: If page_num out of range
    """
    ...

# ❌ BAD
def extract_text(pdf_path, page_num):
    # Extract text from PDF
    ...
```

### Docstrings (Google Style)

Use Google-style docstrings with Args, Returns, Raises sections.

```python
def redact_entities(text: str, entities: list[str]) -> str:
    """Replace entities with redaction markers.
    
    Args:
        text: Input text to redact
        entities: List of entity strings to hide
        
    Returns:
        Text with entities replaced by [REDACTED]
    """
```

### Code Organization

- **Imports:** Use isort for automatic sorting
- **Functions:** Group related functions by feature
- **Classes:** Use dataclasses where applicable
- **Comments:** Only for non-obvious logic (see examples in code)
- **Line Length:** Max 100 characters

### Testing Requirements

- New features must include tests
- All tests must pass: `pytest tests/ -v`
- Aim for >80% code coverage
- Test edge cases, not just happy path

```python
def test_extract_text_empty_pdf():
    """Verify extraction handles empty PDFs."""
    result = extract_text("empty.pdf", 0)
    assert result == ""

def test_extract_text_invalid_page():
    """Verify ValueError on page out of range."""
    with pytest.raises(ValueError):
        extract_text("test.pdf", 999)
```

---

## 📌 Commit Message Format

Use descriptive, concise commit messages following this pattern:

```
type(scope): description

Body with more details (optional)
```

### Format Rules

- **Type:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `ci`
- **Scope:** Component affected (e.g., `ai`, `pdf`, `ui`, `logging`)
- **Description:** Imperative mood, lowercase, no period
- **Body:** Explain *why*, not *what* (body is optional)

### Examples

```bash
# Feature
git commit -m "feat(ai): add IBAN detection to Presidio pipeline"

# Bug fix
git commit -m "fix(export): resolve memory doubling in forensic scrubbing"

# Documentation
git commit -m "docs: update installation guide for Python 3.12"

# Performance
git commit -m "perf(allowlist): implement O(1) exact-match lookup"

# With detailed explanation
git commit -m "fix(threading): add QMutex serialization for document access

Prevents race conditions between UI thread (render) and AI worker
thread when scanning large PDFs concurrently."
```

---

## 🔍 Pull Request Process

### Before Opening PR

1. ✅ Run tests: `pytest tests/ -v`
2. ✅ Build locally: `python build_local.py`
3. ✅ Update CHANGELOG.md with your changes
4. ✅ Self-review your code (would you understand this in 6 months?)
5. ✅ Check links in documentation

### PR Description Template

```markdown
## 📝 Description

Brief explanation of what changed and why.

## 🎯 Type of Change

- [ ] Bug fix (non-breaking, fixes issue)
- [ ] New feature (non-breaking)
- [ ] Breaking change (requires version bump)
- [ ] Documentation update

## ✅ Testing

- [ ] Unit tests added/updated
- [ ] Manual testing completed
- [ ] All tests pass locally

## 📋 Checklist

- [ ] Code follows style guidelines
- [ ] No new dependencies added
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Commits have clear messages
```

### Review Process

1. CI/CD checks must pass (GitHub Actions)
2. Code review by maintainer
3. Approval → merge to `develop` branch
4. Included in next release

> [!NOTE]
> Major changes may require discussion before implementation. Open an issue first if uncertain.

---

## 🐛 Bug Reports

Found a bug? Open an issue on GitHub with:

1. **Title:** Clear, specific description
2. **Environment:** Python version, OS, GUI version
3. **Steps to Reproduce:** Exact steps to trigger bug
4. **Expected Behavior:** What should happen
5. **Actual Behavior:** What actually happens
6. **Logs:** Paste relevant logs from `~/.nullifypdf/logs/`

Enable debug mode for detailed logs:

```bash
# Windows (PowerShell)
$env:NULLIFYPDF_DEBUG = "true"
python NullifyPDF.py

# macOS/Linux (Bash)
export NULLIFYPDF_DEBUG=true
python3.12 NullifyPDF.py
```

---

## ✨ Feature Requests

Have an idea? Open an issue with:

1. **Title:** Feature description
2. **Use Case:** Why do you need this?
3. **Proposed Solution:** How should it work?
4. **Alternatives Considered:** Other approaches?

Feature discussion happens in issues before implementation. No PRs without prior discussion.

---

## 🏗️ Project Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed system design:

- **Core Components** — PDF engine, AI pipeline, UI layer
- **Threading Model** — QThread + QMutex architecture
- **Data Flow** — Load → Extract → Analyze → Redact → Export
- **Key Files** — Entry point, worker classes, utility modules

Understanding architecture helps choose right place for changes.

---

## 📦 Dependencies

NullifyPDF prioritizes **staying lean and local**. Before adding a dependency:

1. Justify why it's needed
2. Check if functionality exists in stdlib
3. Verify cross-platform support (Windows/macOS/Linux)
4. Consider maintenance burden
5. **Discuss in issue first**

Heavy dependencies (like large ML frameworks) are not accepted unless truly essential.

---

## 🔐 Security Concerns

Found a security vulnerability? **Do not open a public issue.** Please follow the responsible disclosure guidelines in [SECURITY.md](./SECURITY.md) to report it safely and privately.

See [SECURITY.md](./SECURITY.md) for the full responsible disclosure policy and reporting instructions.

---

## 📊 Development Workflow

```
main (stable releases)
  ↓
develop (integration branch)
  ↓
feature/your-feature (your work)
```

**Branch strategy:**
- `main` — Production-ready code only
- `develop` — Integration branch for next release
- Feature branches — Created from `develop`, merged back to `develop`

---

## 🎓 Learning Resources

- **Python 3.12** — [docs.python.org](https://docs.python.org/3.12/)
- **PySide6** — [doc.qt.io/qtforpython](https://doc.qt.io/qtforpython/)
- **PyMuPDF** — [pymupdf.io](https://pymupdf.io/)
- **spaCy** — [spacy.io](https://spacy.io/)
- **Presidio** — [microsoft.github.io/presidio](https://microsoft.github.io/presidio/)

---

## ❓ Questions?

- 💬 **Discussions:** [GitHub Discussions](https://github.com/overwrite00/NullifyPDF/discussions) — General questions and ideas
- 🐛 **Bug Reports:** [GitHub Issues](https://github.com/overwrite00/NullifyPDF/issues) — Report bugs and request features

---

## 🎉 Thank You!

Every contribution — code, docs, bug reports, ideas — helps make NullifyPDF better. We appreciate your time and effort!

---

*Last updated: 2026-06-06*  
*← [Back to README](./README.md) | [Architecture →](./ARCHITECTURE.md)*
