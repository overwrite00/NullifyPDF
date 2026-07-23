# 📖 User Guide — NullifyPDF

Your step-by-step guide to redacting sensitive data from PDFs safely and securely.

> [!TIP]
> This takes about **5 minutes**. New to PDF redaction? Start with **Step 1** below.

---

## 📋 Quick Overview

| 🎯 Step            | ⏱️ Time  | What You'll Do                |
| ----------------- | ------- | ----------------------------- |
| **1️⃣ Load**        | 30 sec  | Open a PDF file               |
| **2️⃣ Configure**   | 30 sec  | Select document language      |
| **3️⃣ Auto-Redact** | 1-2 min | Run AI to find sensitive data |
| **4️⃣ Review**      | 1-2 min | Manually fix any mistakes     |
| **5️⃣ Blindfold**   | 30 sec  | Hide images (optional)        |
| **6️⃣ Export**      | 30 sec  | Save the redacted PDF         |

---

## Step 1️⃣ — Load Your PDF

1. Click the blue **"Apri PDF"** button in the top left
2. Select a PDF file from your computer
3. The document appears in the center. Scroll with mouse or use arrow buttons (top right)

> [!NOTE]
> Supported format: unencrypted PDF. Digital text is scanned directly; scanned pages require OCR.

---

## Step 2️⃣ — Configure AI Language

**Before scanning**, select your document's language from the left sidebar:

| 🌐 Language | Use When                          |
| ---------- | --------------------------------- |
| **EN**     | Document is entirely in English   |
| **IT**     | Document is entirely in Italian   |
| **BOTH**   | Document contains mixed languages |

> [!WARNING]
> Wrong language = missed detections. Choose the exact language of your document.

---

## Step 3️⃣ — Automatic Redaction (AI Scan)

Click the **"Auto Redact (AI)"** button. NullifyPDF will automatically find and flag:

- 🧑 **Names & Surnames**
- 🏙️ **Cities & Addresses**
- 📧 **Email Addresses**
- 📱 **Phone Numbers**
- 💳 **IBANs & Credit Card Numbers**
- ₿ **Cryptocurrency Addresses**

**What to expect:**
- Black boxes appear over detected data
- Progress bar shows scanning progress
- On large PDFs (500+ pages): 30-60 seconds normal
- UI stays responsive (no freezing)

> [!TIP]
> The AI isn't perfect. You'll review results in Step 4.

---

## Step 4️⃣ — Manual Review & Corrections

No AI is 100% accurate. You can fix mistakes:

### Add a Redaction
**Draw a box** over text you want to hide:
1. Click and drag mouse over sensitive text
2. A black box appears
3. Redaction is scheduled (not destructive yet)

### Remove a Redaction
**Click once** on a black box to remove it:
1. Single click on the redaction box
2. Box disappears
3. Word is added to **Allowlist** (AI will ignore it next time)

### Zoom In/Out
Make small text larger:
- Press **+** / **-** keys, OR
- Hold **CTRL** + Mouse wheel up/down

> [!IMPORTANT]
> Changes are **preview only** until you export. You can undo everything before export.

---

## Step 5️⃣ — Hide Images & Photos (Optional)

Remove logos, signatures, or scanned photos:

1. **Enable** the toggle: **"Oscura Immagini"** (sidebar)
2. Click **"Auto Redact (AI)"** again
3. All images replaced with gray placeholder: `[ IMAGE REMOVED ]`

> [!NOTE]
> For scanned documents, enable **OCR PDF scansionati** before running the AI scan. Full builds include EN/IT OCR data; Lite builds require local Tesseract tessdata.

---

## Step 6️⃣ — Export the Privacy PDF

When satisfied with redactions:

1. Click **"Esporta Privacy"**
2. Choose the export mode:
   - **Anonimizzazione irreversibile** removes selected personal data permanently
   - **Pseudonimizzazione reversibile** replaces selected personal data with placeholders and creates a separate encrypted restore map
3. Choose filename and location
4. Review the exported PDF before sharing it

> [!CAUTION]
> **Irreversible anonymization cannot be undone from the exported PDF.** Keep a backup of the original PDF. For pseudonymization, store the encrypted restore map separately from the PDF.

---

## 🔧 Dictionary Management

Your redaction preferences are saved automatically:

### Storage Location

| OS          | Path                               |
| ----------- | ---------------------------------- |
| **Windows** | `C:\Users\<username>\.nullifypdf\` |
| **macOS**   | `~/.nullifypdf/`                   |
| **Linux**   | `~/.nullifypdf/`                   |

### Files Inside

```
.nullifypdf/
├── blocklist.txt     ← Words to ALWAYS redact
├── allowlist.txt     ← Words to NEVER redact
├── logs/
│   └── nullifypdf.log
```

### How to Edit Manually

<details>
<summary><strong>📝 Edit Blocklist/Allowlist Directly</strong></summary>

1. Open file manager, navigate to `~/.nullifypdf/`
2. Edit `blocklist.txt` or `allowlist.txt` with any text editor
3. One word per line, UTF-8 encoding
4. Restart NullifyPDF to load changes

**Example blocklist.txt:**
```
john smith
acme corporation
admin@example.com
```

</details>

### Blocklist and Allowlist

The manual redaction workflow keeps clicked/drawn terms mutually exclusive.
When editing dictionary files or the dictionary dialog directly, review both
lists and avoid adding the same term to both.

---

## ✅ Best Practices

1. **Backup Original** — Always keep the original PDF before redacting
2. **Test on Copy** — Redact a test copy first, verify results
3. **Verify Export** — Open exported PDF to confirm redactions look correct
4. **Choose Language Carefully** — Wrong language = missed detections
5. **Use Allowlist Sparingly** — Only add words you're 100% sure aren't sensitive

---

## 📊 Logging & Diagnostics

### View Logs

Log files track all activity. Location:

| OS              | Path                                                  |
| --------------- | ----------------------------------------------------- |
| **Windows**     | `C:\Users\<username>\.nullifypdf\logs\nullifypdf.log` |
| **macOS/Linux** | `~/.nullifypdf/logs/nullifypdf.log`                   |

### Log Format

```
2026-06-06 14:23:45 - INFO - Loaded PDF: document.pdf
2026-06-06 14:23:50 - INFO - AI scan complete: 5 detections
2026-06-06 14:24:10 - ERROR - Export failed
```

### Enable Debug Mode

For detailed troubleshooting, enable verbose logging:

<details>
<summary><strong>🔍 Windows (PowerShell)</strong></summary>

```powershell
$env:NULLIFYPDF_DEBUG = "true"
python NullifyPDF.py
```

</details>

<details>
<summary><strong>🔍 macOS/Linux (Bash)</strong></summary>

```bash
export NULLIFYPDF_DEBUG=true
python3.13 NullifyPDF.py
```

</details>

**Effect:** Debug logs include full stack traces. Useful when reporting bugs.

### Log File

- **Encoding:** UTF-8
- **Location:** `~/.nullifypdf/logs/nullifypdf.log`
- **Rotation:** not currently implemented; remove old logs manually if needed

---

## ❓ Common Questions

### Q: Why doesn't AI detect text in my scanned PDF?
**A:** Enable **OCR PDF scansionati** before running the AI scan. Full builds include EN/IT OCR data; Lite builds need local Tesseract `tessdata`.

### Q: Can I password-protect the exported PDF?
**A:** Not built-in. Use a PDF editor after export for password protection.

### Q: How do I know redactions are applied?
**A:** Export applies PDF redactions and removes selected metadata. Review the exported file before sharing, especially for high-risk documents.

### Q: Can I undo changes after export?
**A:** Irreversible anonymization cannot be undone from the exported PDF. Pseudonymization can be restored only with the encrypted restore map and its password.

### Q: Does NullifyPDF send data to the cloud?
**A:** **No.** PDF processing is local. Full builds may download OCR data during build time, not while processing your PDFs.

---

## 🚀 Next Steps

- ✅ Ready to use? Start with **Step 1** above
- 🐛 Stuck? See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- 👨‍💻 Want to contribute? Read [CONTRIBUTING.md](./CONTRIBUTING.md)
- 🏗️ Curious about architecture? Check [ARCHITECTURE.md](./ARCHITECTURE.md)

---

*Last updated: 2026-07-23*  
*← [Back to README](./README.md) | [Troubleshooting →](./TROUBLESHOOTING.md)*
