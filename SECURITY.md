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
| **No Cloud**                | No file uploads, no network transmission          |
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

1. ✅ **Metadata Stripped** — Creation date, author, and document metadata removed
2. ✅ **Links Removed When Redacted** — Links overlapping redaction areas are deleted
3. ✅ **Redactions Applied** — Selected text/image areas are removed from the exported PDF
4. ✅ **Pseudonymization Maps Encrypted** — Restore maps are stored separately and encrypted with a user password

### Temporary Files

During export, NullifyPDF uses **disk-backed temporary files**:

- Temporary data written to system temp directory
- Automatically cleaned up after export completes
- On Windows: `%APPDATA%\Local\Temp\`
- On macOS/Linux: `/tmp/`

### No Sensitive Data in Memory

- Original PDF kept in memory only while open
- AI results (detected entities) stored only in-memory during session
- Exported PDF overwrites original data locations
- Graceful cleanup on app close

---

## 🔑 Input Validation & Safety

### File Type Verification

- ✅ PDF files only (blocked: `.exe`, `.zip`, etc.)
- ✅ Password-protected PDFs are blocked before processing
- ✅ Encryption detection (blocks password-protected PDFs)
- ✅ Extension and existence checks before opening PDFs

### User Input Validation

- ✅ Page number bounds checking
- ✅ Language selection validation (EN/IT/BOTH only)
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
# Type checking
mypy NullifyPDF.py

# Linting
pylint NullifyPDF.py

# Security scanning
bandit NullifyPDF.py
```

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
| **cryptography**      | Restore-map encryption | ✅ Actively maintained |

### Vulnerability Scanning

We monitor dependencies for CVEs:

- GitHub Dependabot alerts enabled
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

*Last updated: 2026-07-23*  
*← [Contributing](./CONTRIBUTING.md) | [Back to README →](./README.md)*
