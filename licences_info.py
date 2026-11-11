"""Licences of NullifyPDF and of the components it uses, with official links.

Single source for the "Info" window and for the README table (a test keeps the
README in step). Informational only: each component remains under its own
licence, which is what the notice says.
"""

from __future__ import annotations

import html
from typing import List, NamedTuple

REPO = "https://github.com/overwrite00/NullifyPDF"
AGPL_URL = "https://opensource.org/license/agpl-v3"
LGPL_URL = "https://opensource.org/license/lgpl-3-0"
CC_NC_SA_URL = "https://creativecommons.org/licenses/by-nc-sa/3.0/"

APP_LICENCE = "AGPL-3.0-or-later"
NOTICE = (
    "NullifyPDF è software libero e gratuito, distribuito con licenza "
    f"{APP_LICENCE}. Ogni componente e ogni modello usati dal programma restano "
    "soggetti alla propria licenza, indicata qui sotto con il collegamento al testo "
    "ufficiale: usando il programma se ne rispettano le condizioni. Il modello "
    "italiano di spaCy è per solo uso non commerciale e viene scaricato solo dopo "
    "il tuo consenso."
)


class Component(NamedTuple):
    name: str
    licence: str
    url: str  # official page or licence text
    role: str
    role_en: str = ""
    licence_en: str = ""


COMPONENTS: List[Component] = [
    Component("NullifyPDF", APP_LICENCE, f"{REPO}/blob/main/LICENSE", "questo programma", "this program"),
    Component("PyMuPDF / MuPDF", "AGPL-3.0 o commerciale (Artifex)",
              "https://pymupdf.readthedocs.io/en/latest/about.html", "lettura e redazione dei PDF", "PDF reading and redaction",
              "AGPL-3.0 or commercial (Artifex)"),
    Component("PySide6 / Qt", "LGPL-3.0", LGPL_URL, "interfaccia grafica", "graphical interface"),
    Component("Presidio", "MIT", "https://github.com/microsoft/presidio/blob/main/LICENSE",
              "riconoscimento dei dati personali", "personal-data detection"),
    Component("spaCy", "MIT", "https://github.com/explosion/spaCy/blob/master/LICENSE",
              "elaborazione del linguaggio", "language processing"),
    Component("spaCy it_core_news_md", "CC BY-NC-SA 3.0 (solo uso non commerciale)", CC_NC_SA_URL,
              "modello italiano, scaricato dopo il consenso", "Italian model, downloaded after consent",
              "CC BY-NC-SA 3.0 (non-commercial use only)"),
    Component("onnxruntime", "MIT", "https://github.com/microsoft/onnxruntime/blob/main/LICENSE",
              "esecuzione dei modelli locali", "running local models"),
    Component("tokenizers", "Apache-2.0", "https://github.com/huggingface/tokenizers/blob/main/LICENSE",
              "tokenizzazione dei modelli locali", "tokenizing for local models"),
    Component("cryptography", "Apache-2.0 o BSD-3-Clause",
              "https://github.com/pyca/cryptography/blob/main/LICENSE", "cifratura", "encryption",
              "Apache-2.0 or BSD-3-Clause"),
    Component("keyring", "MIT", "https://github.com/jaraco/keyring", "archivio chiavi (Linux/macOS)", "key storage (Linux/macOS)"),
    Component("tldextract", "BSD-3-Clause",
              "https://github.com/john-kurkowski/tldextract/blob/master/LICENSE", "riconoscimento URL", "URL recognition"),
    Component("NumPy", "BSD-3-Clause", "https://github.com/numpy/numpy/blob/main/LICENSE.txt",
              "calcolo numerico", "numerical computing"),
    Component("Tesseract OCR", "Apache-2.0", "https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE",
              "OCR dei documenti scansionati", "OCR of scanned documents"),
    Component("tessdata_fast (eng, ita)", "Apache-2.0",
              "https://github.com/tesseract-ocr/tessdata_fast/blob/main/LICENSE", "dati OCR", "OCR language data"),
    Component("ISTAT, elenco dei comuni", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/",
              "nomi dei luoghi", "place names"),
    Component("Wikidata", "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/",
              "nomi e cognomi", "given names and surnames"),
]

EXTRA_LINKS = [
    ("LICENSE", f"{REPO}/blob/main/LICENSE"),
    ("THIRD_PARTY_NOTICES", f"{REPO}/blob/main/THIRD_PARTY_NOTICES.md"),
]


def about_html() -> str:
    """HTML for the scrollable licence area of the Info window."""
    rows = "".join(
        f"<li><a href=\"{html.escape(c.url)}\">{html.escape(c.name)}</a>"
        f" &mdash; {html.escape(c.licence)} ({html.escape(c.role)})</li>"
        for c in COMPONENTS
    )
    extra = " &middot; ".join(
        f"<a href=\"{html.escape(u)}\">{html.escape(n)}</a>" for n, u in EXTRA_LINKS
    )
    return f"<p>{html.escape(NOTICE)}</p><ul>{rows}</ul><p>{extra}</p>"


def readme_markdown() -> str:
    lines = ["| Component | Licence | Used for |", "|---|---|---|"]
    for c in COMPONENTS:
        lines.append(f"| [{c.name}]({c.url}) | {c.licence_en or c.licence} | {c.role_en} |")
    return "\n".join(lines)
