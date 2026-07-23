# OCR Setup for Scanned PDFs

NullifyPDF uses PyMuPDF's integrated OCR support for scanned PDFs. PyMuPDF
contains the OCR integration code, but it still needs Tesseract language data
(`tessdata`) installed on the machine.

Windows:

```powershell
setx TESSDATA_PREFIX "C:\Program Files\Tesseract-OCR\tessdata"
```

Linux:

```bash
export TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata
```

Install or download the language data you need:

- `eng.traineddata` for English OCR.
- `ita.traineddata` for Italian OCR.

For release builds, NullifyPDF uses the `Full` variant to bundle these two
files automatically. Developers can prepare a local Full build with:

```bash
python build_local.py --full
```

If the OCR files are missing, the Full build downloads them automatically from
`tesseract-ocr/tessdata_fast` before running PyInstaller.

Use `python build_local.py --lite` for a smaller build without bundled OCR
data.

If OCR is enabled in the app but `tessdata` cannot be found, NullifyPDF stops
before scanning and asks you to configure Tesseract instead of silently
processing scanned pages without OCR.

---

*Last updated: 2026-07-23*  
*[Back to README](./README.md) | [Architecture →](./ARCHITECTURE.md)*
