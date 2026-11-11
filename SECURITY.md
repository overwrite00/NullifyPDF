# 🔒 Security — NullifyPDF

Information about NullifyPDF's security model, privacy boundaries, and how to report security vulnerabilities.

> [!IMPORTANT]
> NullifyPDF is designed for local-first privacy workflows. This document explains the security boundaries and what to do if you discover a vulnerability.

---

## 🛡️ Security Model

### Privacy-First Design

NullifyPDF follows a **privacy-first architecture**:

| Principle                   | Implementation                                    |
| --------------------------- | ------------------------------------------------- |
| **100% Local**              | All PDF processing happens on your machine        |
| **No Cloud**                | No file uploads; the only network access is the optional update check (Info → Controlla aggiornamenti, or at every start if the user enables it; off by default) and the model downloads the user approves (Italian spaCy model from the publisher's GitHub release, optional ONNX models from Hugging Face). None of them sends document data |
| **No Telemetry**            | Zero user tracking or analytics                   |
| **Open Source**             | Full code transparency, auditable by anyone       |
| **Privacy Export**          | Irreversible redaction or encrypted reversible pseudonymization |

### What NullifyPDF Does NOT Do

❌ **No Cloud Uploads During PDF Processing**  
❌ **No Data Collection** (no logs sent anywhere)  
❌ **No Third-party Processing APIs** (analysis runs locally)  
❌ **No User Accounts** (no registration required)  
❌ **No Tracking** (no cookies, no analytics)  

---

## 🔐 Technical Security

### PDF Processing

When you export a PDF with redactions:

1. ✅ **Redactions applied** — selected text/image areas are removed from the content stream, not just covered
2. ✅ **Sanitiser** — annotations, embedded files, external links, bookmarks, JavaScript, tagged-PDF alternative text, thumbnails, document and XMP metadata, invisible text, text outside the visible page box and the trailer ID are removed; hidden layers are shown before the scan so their text is analysed
3. ✅ **Verification** — every redacted word is checked glyph by glyph (the number of characters actually deleted must match the measured deletion rule, and characters a thin box cannot reach are reported), then the written file is re-opened and checked for any removed value in the text layer, every object and decompressed stream, annotations, attachments, bookmarks and metadata; findings list locations, never the values
4. ✅ **Pseudonymization maps encrypted** — restore maps are stored separately and encrypted with AES-256-GCM under a data key wrapped by a password-derived key (Argon2id) and, optionally, a recovery key
5. ⚙️ **Optional width masking** — the space left by removed text can be rounded so its width is not recoverable (off by default: it can shift the following text slightly)

Limits you should know about:

- Detection is statistical. Review the result and the suggestions before sharing; unrecognised or indirect identifiers (dates, places, job titles, clinical details) remain.
- Text drawn as part of an image is removed only where the image is redacted; OCR is used to find it.
- Signatures, stamps and photos are not detected automatically; use "Oscura Immagini" or draw a redaction manually.

### Downloaded models

Models are untrusted data until verified. The Italian spaCy pipeline is downloaded over HTTPS only after the user has seen its licence and agreed; its size and SHA-256 are pinned in the program, the archive is unpacked only into `~/.nullifypdf/spacy_models/` (paths that escape that folder are rejected) and an incomplete or altered download is discarded. Optional ONNX models come from pinned Hugging Face revisions and every file is checked for size and SHA-256 before it is installed. Models only produce suggestions; the user decides what is redacted.

### Temporary Files

- The working copy used during export is kept **in memory**. Only very large documents use a private per-user folder (`~/.nullifypdf/tmp`), emptied after the export and at the next start-up.
- No unredacted copy is written next to the exported file.
- Logs (`~/.nullifypdf/logs`) are rotated and purged after 30 days; they contain no detected values. "Elimina dati locali" removes logs, audit records and temporary files.

### Data kept in memory and on disk

- Original PDF kept in memory only while open
- AI results (detected entities) stored only in memory during the session; suggestions are never written to disk
- The restore map is written with owner-only permissions where the platform supports it; keep it away from the PDF and from synchronised folders
- The blocklist and allowlist (`~/.nullifypdf/*.v2.enc`) may themselves contain personal data, so they are encrypted with AES-256-GCM under a master key protected by Windows DPAPI, the OS keyring (`keyring` package, installed on macOS and Linux; headless Linux without a Secret Service falls back to the key file) or, as a fallback, a local key file. Terms can expire and are then purged. DPAPI and the keyring bind the data to the user account and machine; the key file only protects against copying a single data file, not against someone who can read the user's profile. Overwriting migrated plaintext files is best effort (SSD wear levelling and backups may keep copies)
- If the keystore cannot be read (profile copied to another account or PC) nothing is deleted or overwritten: the lists stay empty and the encrypted files untouched
- The pseudonym key is stored sealed under the same master key; a password-protected copy can be exported for another computer
- Restore maps (version 3 envelope): a random data key encrypts the map with AES-256-GCM; it is wrapped by a password-derived key (Argon2id, scrypt if unavailable) and optionally by a recovery key (256-bit, shown once, never stored). Key-derivation parameters read from a file are bounded before use
- Graceful cleanup on app close

---

## ⚖️ GDPR Notes

NullifyPDF runs locally; the person or organisation using it is the controller of the data it processes.

- **Redaction is not a guarantee of anonymisation.** Under Recital 26 GDPR, data that can still be attributed to a person is personal data. A redacted document that keeps dates, places or context may remain personal data.
- **Pseudonymised output is personal data** (Art. 4(5) GDPR; EDPB Guidelines 01/2025 on pseudonymisation). The restore map is the "additional information" that must be kept separately and protected; it is itself personal data. A random or keyed placeholder avoids leaking the order and number of values; the "sequential" style does leak them.
- **Special categories (Art. 9)**: documents with health data need particular care. The health-document profile keeps uncertain hits as suggestions instead of dropping them; in Italy, health data may not be disseminated (art. 2-septies d.lgs. 196/2003).
- **Accuracy and minimisation**: over-redaction removes meaning and under-redaction discloses data. Uncertain detections are shown for review rather than applied or discarded silently.
- The export audit record (`~/.nullifypdf/audit`) supports accountability; it contains counts and hashes only.

---

## 🔑 Input Validation & Safety

### File Type Verification

- ✅ PDF and Word DOCX files only (blocked: `.exe`, `.zip`, etc.); DOCX macros, external links and embedded objects are never executed
- ✅ Password-protected PDFs are blocked before processing
- ✅ Encryption detection (blocks password-protected PDFs)
- ✅ Extension and existence checks before opening PDFs

### User Input Validation

- ✅ Page number bounds checking
- ✅ File path sanitization
- ✅ Type hints on all functions

---

## 🚨 Responsible Disclosure

### Found a Vulnerability?

Do **NOT** open a public GitHub issue. Instead, follow these steps:

1. **Assess the Risk**
   - Is it a privacy leak? (severity: HIGH)
   - Is it a data corruption risk? (severity: HIGH)
   - Is it a UI bug? (severity: LOW)

2. **Report Through Proper Channel**
   - Open a **private security advisory** on GitHub, OR
   - Contact through GitHub security form (coming soon)

3. **What to Include**
   - Detailed vulnerability description
   - Steps to reproduce
   - Affected version(s)
   - Suggested fix (if you have one)
   - Your name (if you want credit)

4. **Timeline**
   - You'll receive acknowledgment within 48 hours
   - Fix will be attempted within 2 weeks (critical) or 1 month (standard)
   - You'll be credited in release notes

### Security Policy

We follow responsible disclosure principles:

- **Embargo Period:** 30 days for critical vulnerabilities
- **Public Disclosure:** After patch is released
- **Credit:** Security researchers credited by name (unless anonymous requested)

---

## 🔒 Security Support

**Only the latest released version receives security updates.** Always use the newest version for security patches and critical fixes.

---

## 📋 Known Limitations

### What We Don't Protect Against

1. **Shoulder Surfing** — If someone watches your screen while redacting
2. **Malware on Your Computer** — If your machine is compromised
3. **Unencrypted Storage** — Save your PDF to an encrypted drive if sensitive
4. **Physical Access** — If someone accesses your hard drive directly
5. **Residual PDF Artifacts** — Complex PDFs may contain structures not covered by automated checks

### What You Can Do

- 🔒 Use **encrypted storage** (BitLocker, FileVault, LUKS)
- 🛡️ Keep **antivirus software** updated
- 🔑 Use **strong passwords** on your machine
- 🚫 Don't share exported PDFs on unsecured channels
- 🔄 Use **trusted networks** when processing sensitive documents

---

## 🧪 Security Auditing

### Code Review

The codebase is open source and welcomes security audits:

- Review code on [GitHub](https://github.com/overwrite00/NullifyPDF)
- Check `NullifyPDF.py` for data handling
- Review `ARCHITECTURE.md` for system design
- Examine test coverage in `tests/`

### Static Analysis

We use Python static analysis tools:

```bash
# Type checking (blocking in CI; full file list in DEVELOPMENT.md)
mypy NullifyPDF.py pii_detection.py privacy_core.py
```

GitHub code scanning (CodeQL) analyses every pull request to `main`, and Dependabot proposes dependency updates.

### Testing

Security-relevant tests cover:

- Input validation smoke tests
- Resource cleanup (file handles, memory)
- Privacy-core and build-configuration tests

Run tests:
```bash
pytest tests/ -v
```

---

## 🔐 Privacy of Redaction Preferences

### Local Storage

Your redaction preferences (blocklist/allowlist) are stored locally:

| OS          | Location                           |
| ----------- | ---------------------------------- |
| **Windows** | `C:\Users\<username>\.nullifypdf\` |
| **macOS**   | `~/.nullifypdf/`                   |
| **Linux**   | `~/.nullifypdf/`                   |

- ✅ Only accessible by your user account
- ✅ Not synced to cloud
- ✅ Not shared with anyone
- ✅ Deleted when you remove files

### File Permissions

The application relies on the operating system's standard user permissions for
`~/.nullifypdf/`. Store sensitive files on encrypted storage when required.

---

## 🔄 Dependency Security

### Third-Party Libraries

NullifyPDF uses trusted, actively-maintained libraries:

| Library               | Purpose          | Status                    |
| --------------------- | ---------------- | ------------------------- |
| **pyside6**           | GUI framework    | ✅ Actively maintained     |
| **pymupdf**           | PDF manipulation | ✅ Actively maintained     |
| **presidio-analyzer** | PII detection    | ✅ Maintained by Microsoft |
| **spacy**             | NLP engine       | ✅ Actively maintained     |
| **onnxruntime**       | Local model inference | ✅ Actively maintained |
| **cryptography**      | Restore-map encryption | ✅ Actively maintained |

### Vulnerability Scanning

We monitor dependencies for CVEs:

- GitHub Dependabot alerts enabled
- GitHub code scanning (CodeQL) on pull requests to `main`
- Security updates applied promptly
- Community reports welcomed

---

## ⚠️ Disclaimer

NullifyPDF is provided **as-is** without warranty. While we take security seriously:

- **No Guarantee of Unrecoverability** — For highly sensitive data, consult legal/security experts
- **No Liability** — Use at your own risk
- **Not a Legal Tool** — Consult lawyers for document redaction in legal cases
- **Residual Risk** — For highly sensitive or legally critical documents, perform independent review and validation

For mission-critical or legal redactions, consider:
- Professional redaction services
- Dedicated security appliances
- Expert legal guidance

---

## 🙏 Security Contributors

We acknowledge and credit security researchers who responsibly disclose vulnerabilities:

- [List of past security fixes and contributors]
- (Updates as vulnerabilities are resolved)

---

## 📞 Contact

### Security Issues

For **security vulnerabilities only**:
- GitHub Security Advisory (coming soon)
- OR check GitHub repository for security contact

### General Questions

- 📖 See [README.md](./README.md)
- 💬 Open [GitHub Discussion](https://github.com/overwrite00/NullifyPDF/discussions)
- 🐛 Report bugs on [GitHub Issues](https://github.com/overwrite00/NullifyPDF/issues)

---

## 📚 Further Reading

- [OWASP Security Best Practices](https://owasp.org/)
- [Python Security](https://docs.python.org/3/library/security_warnings.html)
- [PII Protection Guide](https://www.nist.gov/itl/applied-cybersecurity/privacy-engineering)

---

*Last updated: 2026-11-11*  
*← [Contributing](./CONTRIBUTING.md) | [Back to README →](./README.md)*
