# 📖 User Guide — NullifyPDF

Your step-by-step guide to redacting sensitive data from PDFs safely and securely.

> [!TIP]
> This takes about **5 minutes**. New to PDF redaction? Start with **Step 1** below.

---

## 📋 Quick Overview

| 🎯 Step            | ⏱️ Time  | What You'll Do                |
| ----------------- | ------- | ----------------------------- |
| **1️⃣ Load**        | 30 sec  | Open a PDF or Word DOCX file  |
| **2️⃣ Language**    | 30 sec  | Italian model (first use only) |
| **3️⃣ Auto-Redact** | 1-2 min | Run AI to find sensitive data |
| **4️⃣ Review**      | 1-2 min | Manually fix any mistakes     |
| **5️⃣ Blindfold**   | 30 sec  | Hide images (optional)        |
| **6️⃣ Export**      | 30 sec  | Save the redacted PDF         |

---

> [!TIP]
> The program has its own guide in Italian: press **F1** or the **Guida** button in the sidebar. Resting the pointer on any button, option or field shows a short description.

## Step 1️⃣ — Load Your PDF or Word Document

1. Click the blue **"Apri PDF"** button in the top left
2. Select a PDF or modern Word **DOCX** file from your computer
3. The document appears in the center. Scroll with mouse or use arrow buttons (top right)

> [!NOTE]
> Supported formats: unencrypted PDF and DOCX. A DOCX is read locally and converted to an internal PDF representation; the original Word file is never modified and macros, external links and embedded objects are not executed. Legacy binary `.doc` files must be saved as DOCX first. Digital PDF text is scanned directly; scanned pages require OCR.

### Optional local models

Open **Modelli locali** in the sidebar to view the reviewed shortlist (MiniLMv2 EN/IT, PiiScan, OpenMed Italian FastClinical, plus experimental entries that cannot be downloaded). Models are optional and are not included in the installer. Before downloading, the dialog shows the Hugging Face source, license, pinned revision and total size. After you confirm, the **Scarica modello** button itself turns into a progress bar with the overall percentage across all model files; click it again to cancel. The list and the Close button stay locked until the download ends. This is separate from the Italian name-recognition model of Step 2, which is downloaded on the first Auto Redact.

Only entries with a complete application manifest can be downloaded. The manifest fixes the revision, allowed files, expected sizes and SHA-256 values. Experimental entries without those checks remain unavailable. Installed models run locally and add suggestions for review; they never apply a redaction automatically.

---

## Step 2️⃣ — Language

NullifyPDF analyses **Italian** documents only; there is no language selector. The Italian name-recognition model is not part of the installer (its licence is non-commercial): the first time you run **Auto Redact** the program shows the licence, asks for your consent and downloads it. If you decline, the scan continues with rules and dictionaries only, which finds fewer names.

> [!WARNING]
> Documents in other languages are not supported: names and places in them will be missed.

---

## Step 3️⃣ — Automatic Redaction (AI Scan)

Click the **"Auto Redact"** button. A dialog first lets you tick which data types to look for (your choice is remembered). NullifyPDF will then automatically find and flag the selected types; other occurrences of a detected value are matched as whole words only ("Rossi" does not match "Rossini"):

- 🧑 **Names & Surnames**
- 🏙️ **Cities & Addresses**
- 📧 **Email Addresses**
- 📱 **Phone Numbers** (including Italian mobile/landline formats)
- 💳 **IBANs & Credit Card Numbers**
- ₿ **Cryptocurrency Addresses**
- 🇮🇹 **Italian national IDs**: Codice Fiscale, Partita IVA, carta d'identità, patente, passaporto

**What to expect:**
- Black boxes appear over detected data
- Progress bar shows scanning progress
- On large PDFs (500+ pages): 30-60 seconds normal
- UI stays responsive (no freezing)

> [!TIP]
> The AI isn't perfect. You'll review results in Step 4. If a type produces too many false positives (for example cities), untick it in the selection dialog next time. Field labels ("Telefono:"), headings and list items are ignored automatically.

---

### Review suggestions

Pending suggestions are also outlined in orange on the page (untick *Mostra suggerimenti* to hide them). Click an outline to censor or discard that suggestion; the outlines exist only on screen and never reach the exported file.


Detections that the text does not support strongly enough (for example a lone capitalized word with no context) are not applied: after the scan a **Revisione suggerimenti** dialog lists them with page, type, score and the reasons. Values are masked until you tick *Mostra i valori*. Tick the ones to censor and press *Applica selezionati* (the others are discarded), or *Rivedi più tardi* to keep them pending; the sidebar button *Rivedi suggerimenti (N)* reopens the list. Double-click a row to jump to its page.

### Documents with health data

Tick **Profilo documenti sanitari** before scanning. It also looks for dates of birth and health identifiers (health card number, prescription number) and never drops an uncertain hit silently: it becomes a suggestion.

---

## Step 4️⃣ — Manual Review & Corrections

No AI is 100% accurate. You can fix mistakes:

### Add a Redaction
**Draw a box** over text you want to hide:
1. Click and drag mouse over sensitive text
2. A black box appears (redaction is scheduled, not destructive yet)
3. If the covered text is recognized, you're asked whether to add it to the **Blocklist** — say yes only if it should be redacted in *every* PDF you open in the future, not just this one

### Remove a Redaction
**Click once** on a black box to remove it:
1. Single click on the redaction box
2. Choose what happens next:
   - **Solo questo documento**: the box disappears, nothing is saved to the lists (this document only)
   - **Whitelist permanente**: the box disappears and the word is added to the **Allowlist** (AI will ignore it in every future document)
   - **Annulla**: keeps the redaction in place

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
2. Click **"Auto Redact"** again
3. All images replaced with gray placeholder: `[ IMAGE REMOVED ]`

> [!NOTE]
> For scanned documents, enable **OCR PDF scansionati** before running the AI scan. Every build includes EN/IT OCR data.

---

## Step 6️⃣ — Export the Privacy PDF

When satisfied with redactions:

1. Click **"Esporta PDF"**
2. If suggestions are still unreviewed you are asked whether to review them first
3. Choose the export mode:
   - **Rimozione irreversibile** removes selected personal data permanently
   - **Pseudonimizzazione reversibile** replaces selected personal data with placeholders and creates a separate encrypted restore map. You choose the placeholder style: *Casuale* (recommended; reveals neither order nor count), *Progressivo* (`PERSON_001`...; reveals how many values exist and their order), *Generico* (also hides the type) or *Coerente (chiave)* (the same value gets the same placeholder in every document made with the same key, which links the documents)
4. Choose filename and location. The suggested name does not contain the source file name
5. For pseudonymization, choose where to save the map (not the PDF's folder, not a synchronised folder) and enter the password twice
6. NullifyPDF re-opens the exported file and verifies it. If a removed value is still readable you are told where and can delete the file
7. Review the exported PDF before sharing it

Annotations, attachments, external links, bookmarks, scripts, metadata, invisible text and text outside the page are removed on export. "Maschera larghezza testo rimosso" (sidebar) additionally rounds the space left by removed text.

> [!CAUTION]
> **Removal cannot be undone from the exported PDF, and it is not a guarantee of anonymisation**: dates, places or context left in the document can still identify a person. Keep a backup of the original PDF. A pseudonymized PDF and its restore map remain personal data: store the map separately from the PDF and protect its password.

---

## Step 7️⃣ — Reconstruct a Pseudonymized PDF

If you exported a PDF with **Pseudonimizzazione reversibile**, you can later restore the original values back into it:

1. Click **"Ricostruisci PDF"**
2. Select the pseudonymized PDF (the one containing placeholders like `PERSON_001`)
3. Select its matching `.nullifypdf-map` restore map file
4. Enter the map's password
5. Choose where to save the reconstructed PDF

NullifyPDF checks the SHA-256 hash recorded in the restore map against the selected PDF and refuses to proceed if they don't match, to avoid applying the wrong mapping to a document.

> [!NOTE]
> For PDFs created by other applications (Word, Office, etc. — not scans), the restore map also records each value's font, size, colour and baseline, and reconstruction writes the text back with the same size, colour and position, reusing the original embedded font when the file still carries it and otherwise the closest standard font (serif/sans/mono, bold/italic). Glyph shapes may therefore differ slightly from the original when the font cannot be reused. For scanned PDFs there is no font to restore, so the value is fitted into its box: it may be clipped or visually crowd it. Maps created by earlier versions keep the previous behaviour.

---

## 🧹 Local data

NullifyPDF keeps a rotating log, an export audit record (counts and hashes, no values) and, for very large files, a temporary folder under `~/.nullifypdf`. **Elimina dati locali** removes them (and, if you confirm, the dictionaries).

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
├── blocklist.v2.enc  ← Words to ALWAYS redact (encrypted)
├── allowlist.v2.enc  ← Words to NEVER redact (encrypted)
├── keystore.json     ← How the encryption key is protected
├── pseudonym.v2.enc  ← Key of the "Coerente" placeholder style (encrypted)
├── update_check.json ← "Check at every start" preference (Info dialog)
├── audit/            ← Export records (counts and hashes, no values)
├── logs/
│   └── nullifypdf.log
├── ai_entities.json  ← Data types chosen in the Auto Redact dialog
├── spacy_models/     ← Italian name-recognition model (downloaded after your consent)
├── models/           ← Optional local ONNX models you downloaded
└── tmp/              ← Private temporary files for very large exports (emptied after use)
```

### Editing the dictionaries

Open **Dizionari**. Each list is a table with the term, the date it was added and an optional expiry date (`AAAA-MM-GG`, or *Mai*). Use *Aggiungi* / *Rimuovi*, *Importa da testo...* (one term per line) and *Esporta in chiaro...* (the exported file contains personal data in clear). *Scadenza predefinita* sets the expiry of new terms, including the ones added by clicking or drawing on the page. Expired terms are removed automatically. The label at the top shows how the lists are protected.

> [!NOTE]
> The lists are encrypted for the current user account. If you copy `~/.nullifypdf` to another account or PC they cannot be read there (they stay untouched and are shown empty). Older plaintext `blocklist.txt` / `allowlist.txt` files are migrated automatically.

### Blocklist and Allowlist

The manual redaction workflow keeps clicked/drawn terms mutually exclusive.
When editing the dictionary dialog, review both lists and avoid adding the
same term to both.

---

## ✅ Best Practices

1. **Backup Original** — Always keep the original PDF before redacting
2. **Test on Copy** — Redact a test copy first, verify results
3. **Verify Export** — Open exported PDF to confirm redactions look correct
4. **Italian documents only** — Other languages are not analysed, so names and places in them are missed
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
- **Rotation:** the file rotates at about 512 KB (3 older files kept) and logs older than 30 days are deleted at start-up

---

## ❓ Common Questions

### Q: Why doesn't AI detect text in my scanned PDF?
**A:** Enable **OCR PDF scansionati** before running the AI scan. Every build includes EN/IT OCR data.

### Q: Can I password-protect the exported PDF?
**A:** Not built-in. Use a PDF editor after export for password protection.

### Q: How do I know redactions are applied?
**A:** Export applies PDF redactions and removes selected metadata. Review the exported file before sharing, especially for high-risk documents.

### Q: Can I undo changes after export?
**A:** Irreversible anonymization cannot be undone from the exported PDF. Pseudonymization can be restored using **"Ricostruisci PDF"** together with the encrypted restore map and its password (see [Step 7](#step-7%EF%B8%8F%E2%83%A3--reconstruct-a-pseudonymized-pdf) below).

### Q: Does NullifyPDF send data to the cloud?
**A:** **No.** PDF processing is local and no document data ever leaves your machine. The only network access is the optional update check (see below) and the downloads you approve: the Italian name-recognition model (from the publisher's GitHub release) and the optional local models (from Hugging Face), each verified with a pinned SHA-256. OCR data is downloaded at build time, not while processing your PDFs.

### Q: How do I check for new versions?
**A:** Open **Info** and click **Controlla aggiornamenti**. NullifyPDF asks the public GitHub releases of this repository whether a newer version exists (no PDF content or personal data is sent). If one does, a window shows the version, the link to the release, the **release notes** (taken from the matching section of `CHANGELOG.md`) and a **Download** button that saves the installer for your operating system into your system **Downloads** folder (the location configured in your OS), after checking its size and the SHA-256 published by GitHub. Nothing is installed automatically. On Linux distributions other than Debian/Ubuntu and Fedora/RHEL-based ones the window only offers the release link, where you can pick the file yourself.

- **Stable** builds are only offered newer *stable* releases; **beta** builds are offered both stable and beta releases.
- Tick **Controlla ad ogni avvio** in the Info dialog to run the same check silently each time the app starts. It is **off by default**; when enabled, a window appears only if a newer version exists, and a failed check (for example offline) is silently logged. Untick it to go back to fully manual checks.

---

## 🚀 Next Steps

- ✅ Ready to use? Start with **Step 1** above
- 🐛 Stuck? See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- 👨‍💻 Want to contribute? Read [CONTRIBUTING.md](./CONTRIBUTING.md)
- 🏗️ Curious about architecture? Check [ARCHITECTURE.md](./ARCHITECTURE.md)

---

*Last updated: 2026-11-11*  
*← [Back to README](./README.md) | [Troubleshooting →](./TROUBLESHOOTING.md)*
