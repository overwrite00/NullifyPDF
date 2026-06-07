# 🔧 Troubleshooting — NullifyPDF

Common issues and how to fix them.

> [!NOTE]
> Can't find your issue? Open a [GitHub Issue](https://github.com/overwrite00/NullifyPDF/issues) to report it.

---

## 📋 Quick Diagnostic Checklist

Before diving in, verify these basics:

- ✅ Python 3.12 installed? Run: `python --version` (or `python3.12 --version`)
- ✅ NullifyPDF running? Check: Can you open a PDF?
- ✅ Debug mode enabled? Set: `NULLIFYPDF_DEBUG=true`
- ✅ Logs checked? Look in: `~/.nullifypdf/logs/nullifypdf.log`
- ✅ Tried restarting? Close and reopen NullifyPDF

---

## ❌ AI Scan Hangs or Freezes on Large PDFs

### Symptom
Application appears frozen during AI scanning. Progress bar stuck.

### Root Cause
Text extraction from large PDFs is CPU-intensive. This is **normal**, not a crash.

### Solution

**Wait.** Seriously, let it finish.

- Small PDF (10 pages): 2-5 seconds
- Medium PDF (100 pages): 10-30 seconds
- Large PDF (500+ pages): 30-60 seconds
- Very large (1000+ pages): 2-5 minutes

**Check it's actually working:**
1. Open `~/.nullifypdf/logs/nullifypdf.log` while scanning
2. Watch for new log lines being written
3. If log updates, it's working (just slowly)

**Speed it up:**
- Close other applications (frees RAM)
- Use language selection (**EN** or **IT**, not **BOTH**)
- Split document: Redact first 100 pages, then next 100

### Still Not Working?

If log isn't updating:
1. Force quit NullifyPDF
2. Check logs for errors
3. Report on GitHub with log contents

---

## 🔴 Export Fails or Crashes

### Symptom
Clicking "Export Secure PDF" causes error or app crash.

### Root Cause
- Insufficient disk space
- PDF file corrupted
- Unusual PDF structure
- File permissions issue

### Solution

**Step 1 — Check Disk Space**

| OS              | Command                      |
| --------------- | ---------------------------- |
| **Windows**     | `Get-Volume C:` (PowerShell) |
| **macOS/Linux** | `df -h` (terminal)           |

Need at least **2-3 GB free** for export buffer.

**Step 2 — Verify PDF**

Does the PDF open correctly?
- ✅ Can you scroll through pages?
- ✅ Can you load it without errors?
- ✅ No password-protected?

If no → PDF may be corrupted. Try opening in Adobe Reader or another tool.

**Step 3 — Check Permissions**

Can you write to the save location?

<details>
<summary><strong>Windows</strong></summary>

1. Right-click folder → **Properties** → **Security**
2. Verify you have **Write** permission
3. Try saving to **Desktop** or **Documents**

</details>

<details>
<summary><strong>macOS</strong></summary>

1. Right-click folder → **Get Info**
2. Check **Sharing & Permissions**
3. Try saving to `/Users/<username>/Desktop`

</details>

<details>
<summary><strong>Linux</strong></summary>

```bash
ls -ld /path/to/folder
# Check if you have write permission (w flag)
```

If not:
```bash
chmod u+w /path/to/folder
```

</details>

**Step 4 — Restart and Retry**

1. Close NullifyPDF
2. Reopen
3. Load PDF again
4. Try export to different folder

### Still Failing?

Enable debug mode and check logs:

```bash
export NULLIFYPDF_DEBUG=true
python3.12 NullifyPDF.py
```

Then try export again. Upload `~/.nullifypdf/logs/nullifypdf.log` to GitHub issue.

---

## 🧠 AI Doesn't Detect My Sensitive Data

### Symptom
Names, emails, or other PII should be detected but aren't highlighted.

### Root Cause
- Wrong language selected
- Text is in an image (not searchable)
- Unusual formatting
- Text is handwritten

### Solution

**Check 1 — Language Selection**

Open sidebar. Is the correct language selected?

| Language | Best For                         |
| -------- | -------------------------------- |
| **EN**   | English text only                |
| **IT**   | Italian text only                |
| **BOTH** | Mixed English + Italian (slower) |

> [!WARNING]
> Wrong language = **zero detection**. Test with a clear English name if unsure.

**Check 2 — Is It Searchable Text?**

Try copying text from the PDF:
1. Click and drag to select text
2. Right-click → Copy
3. Paste in text editor

If you can copy text → it's digital text → AI should detect it  
If you can't copy → it's an image → use **Blindfold Mode** to hide image blocks

**Check 3 — Enable Blindfold Mode**

For scanned PDFs:
1. Toggle **"Blindfold Mode"** in sidebar
2. Run **"Auto Redact"** again
3. All images replaced with placeholder

**Check 4 — Manual Redaction**

If AI still misses something:
1. Click and drag mouse over the text
2. A redaction box appears
3. Export — it will be destroyed

### Allowlist Issue?

If an entity should be detected but isn't:
1. Check `~/.nullifypdf/allowlist.txt`
2. If the word is there, it's intentionally ignored
3. Remove it from allowlist to re-enable detection

---

## 📧 Wrong Redactions Applied

### Symptom
AI redacted text that shouldn't be redacted (false positive).

### Solution

**Option 1 — Remove and Allowlist**

1. **Click once** on the black redaction box
2. It disappears
3. Word is added to allowlist (won't be detected again)

**Option 2 — Manual Redaction**

1. Let AI detect it
2. Manually redact only the parts you need to hide
3. Remove AI's suggestion by clicking it

**Option 3 — Edit Allowlist**

For repeated false positives:

1. Open `~/.nullifypdf/allowlist.txt`
2. Add the word (one per line, lowercase)
3. Restart NullifyPDF
4. Run AI scan again

Example:
```
smith        ← common surname, might be false positive
john         ← common first name
company      ← company name that's not sensitive
```

---

## 🔐 File Permission Denied (Windows)

### Symptom
Error: "File access denied" or "Cannot open file" when exporting.

### Root Cause
PDF file is locked by another application.

### Solution

**Step 1 — Close All PDF Readers**

Check these applications and close any open PDFs:
- Adobe Reader
- Microsoft Edge
- Google Chrome
- Microsoft Word
- Preview (macOS)

**Step 2 — Check Antivirus**

Some antivirus software locks files. Temporarily disable:
- Windows Defender
- Third-party antivirus
- Then retry export

**Step 3 — Try Different Folder**

Save to a different location:
- Desktop (often has fewer restrictions)
- Documents folder
- External drive (if plugged in)

**Step 4 — Use Safe Mode (Advanced)**

On Windows, restart in Safe Mode and try again:
1. Right-click Start → Shut down or sign out → Hold Shift → Restart
2. Select Troubleshoot → Advanced → Safe Mode
3. Open NullifyPDF
4. Try export

---

## 🚫 "Unicode Error" or "Encoding Error"

### Symptom
Crash with error mentioning "UTF-8", "codec", or "Unicode".

### Root Cause
PDF contains unusual characters or encoding.

### Solution

**Most likely:** Already fixed in v2.0.5+

If still occurring:

1. Try on different PDF (test with simple document)
2. Check Python version: `python --version` (should be 3.12)
3. Report on GitHub with:
   - Python version
   - Error message
   - PDF file (if not sensitive)

---

## 💥 Segmentation Fault or Crash on macOS

### Symptom
App crashes with "Segmentation fault" or "SIGSEGV" on macOS.

### Root Cause
PyMuPDF buffer issue (rare). Usually fixed in latest version.

### Solution

**Step 1 — Update NullifyPDF**

```bash
cd /path/to/NullifyPDF
git pull origin main
python setup_env.py
```

**Step 2 — Clear Cache**

```bash
rm -rf .venv/
python setup_env.py
```

**Step 3 — Use Different PDF**

Does crash happen on all PDFs or just one?
- If one PDF → that PDF may be corrupted
- If all PDFs → report on GitHub

---

## 📋 QImage Errors or Display Issues

### Symptom
Black screen, no PDF visible, or rendering glitches.

### Root Cause
Graphics issue or high-DPI display (4K, Retina).

### Solution

**Try these steps:**

1. Restart NullifyPDF
2. Load a different PDF
3. Check logs for graphics errors: `~/.nullifypdf/logs/nullifypdf.log`
4. Report on GitHub with:
   - Monitor resolution (e.g., 4K, 1080p)
   - Operating system version
   - Log file contents

---

## 🔧 Enable Debug Mode for Advanced Troubleshooting

When reporting bugs, enable debug mode to get detailed logs:

<details open>
<summary><strong>🪟 Windows (PowerShell)</strong></summary>

```powershell
$env:NULLIFYPDF_DEBUG = "true"
python NullifyPDF.py
```

Reproduce the issue, then check logs:
```
C:\Users\<username>\.nullifypdf\logs\nullifypdf.log
```

</details>

<details>
<summary><strong>🍎 macOS (Terminal)</strong></summary>

```bash
export NULLIFYPDF_DEBUG=true
python3.12 NullifyPDF.py
```

Logs:
```
~/.nullifypdf/logs/nullifypdf.log
```

</details>

<details>
<summary><strong>🐧 Linux (Bash)</strong></summary>

```bash
export NULLIFYPDF_DEBUG=true
python3.12 NullifyPDF.py
```

Logs:
```
~/.nullifypdf/logs/nullifypdf.log
```

</details>

---

## 📬 Report a Bug

When opening a GitHub issue, include:

1. **Environment:**
   - OS (Windows 10, macOS 13, Ubuntu 22.04, etc.)
   - Python version: `python --version`
   - NullifyPDF version (see title bar)

2. **What Happened:**
   - Exact error message or description
   - Step-by-step to reproduce

3. **Logs:**
   - Content of `~/.nullifypdf/logs/nullifypdf.log` (with debug mode enabled)

4. **What Works:**
   - Does it work with different PDF?
   - Does it work with smaller file?

The more details, the faster we can fix it! 🚀

---

## 💡 Tips for Success

| ✅ Do                        | ❌ Don't                           |
| --------------------------- | --------------------------------- |
| Keep original PDF as backup | Delete original after export      |
| Test on copy first          | Redact production file first time |
| Use correct language        | Use BOTH if EN or IT works        |
| Check logs when stuck       | Restart without checking why      |
| Enable debug mode for bugs  | Submit bugs without logs          |
| Save to common folder       | Save to network drive (slow)      |

---

## 📚 More Help

- 📖 **User Guide:** [USER_GUIDE.md](./USER_GUIDE.md)
- 🏗️ **Architecture:** [ARCHITECTURE.md](./ARCHITECTURE.md)
- 🤝 **Contributing:** [CONTRIBUTING.md](./CONTRIBUTING.md)
- 🔒 **Security:** [SECURITY.md](./SECURITY.md)

---

*Last updated: 2026-06-06*  
*← [User Guide](./USER_GUIDE.md) | [Development →](./DEVELOPMENT.md)*
