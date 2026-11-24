"""Minimal, local DOCX importer used to create an analyzable PDF document.

The importer intentionally handles the OOXML text layer without executing
macros, embedded objects, external links or document relationships.  The
result is a new PDF representation; the original DOCX is never modified.
"""

from __future__ import annotations

import pathlib
import os
import tempfile
import sys
import logging
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

import pymupdf as fitz


LOGGER = logging.getLogger("nullifypdf")


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _paragraph_text(node: ET.Element) -> str:
    return "".join((t.text or "") for t in node.iter(_W + "t"))


def _font_name(rpr: ET.Element | None) -> str:
    """Map the common Word font variants to PDF Base-14 fonts."""
    if rpr is None:
        return "helv"
    bold = rpr.find(_W + "b") is not None
    italic = rpr.find(_W + "i") is not None
    if bold and italic:
        return "hebi"
    if bold:
        return "hebo"
    if italic:
        return "heit"
    return "helv"


def _run_style(run: ET.Element) -> Tuple[str, float]:
    rpr = run.find(_W + "rPr")
    size = 10.5
    if rpr is not None:
        sz = rpr.find(_W + "sz")
        raw_size = sz.get(_W + "val") if sz is not None else None
        if raw_size:
            try:
                size = max(4.0, float(raw_size) / 2.0)
            except ValueError:
                pass
    return _font_name(rpr), size


def _paragraph_runs(node: ET.Element) -> List[Tuple[str, str, float]]:
    """Read text runs while retaining the formatting Word stores on them."""
    runs: List[Tuple[str, str, float]] = []
    for run in node.findall(_W + "r"):
        text = "".join((t.text or "") for t in run.findall(".//" + _W + "t"))
        if text:
            font, size = _run_style(run)
            runs.append((text, font, size))
    return runs


def extract_docx_text(path: pathlib.Path) -> List[str]:
    """Extract paragraphs and table rows from a DOCX without running code."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    lines: List[str] = []
    body = root.find(_W + "body")
    if body is None:
        return lines
    for child in body:
        if child.tag == _W + "p":
            text = _paragraph_text(child).strip()
            if text:
                lines.append(text)
        elif child.tag == _W + "tbl":
            for row in child.findall(_W + "tr"):
                cells = [" ".join(_paragraph_text(p).split()) for p in row.findall(".//" + _W + "tc")]
                text = " | ".join(c for c in cells if c).strip()
                if text:
                    lines.append(text)
    return lines


def docx_to_pdf(path: str) -> fitz.Document:
    """Convert a DOCX to PDF, preferring installed Microsoft Word on Windows.

    Word's own renderer preserves the original layout much better than the
    OOXML fallback.  The COM path is deliberately isolated and hardened:
    macros and link updates are disabled, the source is read-only, and the
    temporary PDF is loaded into memory before it is deleted.
    """
    source = pathlib.Path(path)
    if source.suffix.lower() != ".docx":
        raise ValueError("Sono supportati documenti Word DOCX; il formato DOC binario non è supportato.")
    native = _docx_to_pdf_with_word(source)
    if native is not None:
        LOGGER.info("Conversione Word nativa usata per %s", source.name)
        return native
    LOGGER.warning(
        "Conversione Word nativa non disponibile per %s; uso il fallback OOXML",
        source.name,
    )
    with zipfile.ZipFile(source) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    document = fitz.open()
    page = document.new_page()
    margin = 54.0
    width = page.rect.width - 2 * margin
    y = margin
    body = root.find(_W + "body")
    paragraphs: List[ET.Element] = list(body) if body is not None else []
    if not paragraphs:
        paragraphs = [ET.Element(_W + "p")]
    for block in paragraphs:
        runs = _paragraph_runs(block) if block.tag == _W + "p" else []
        if block.tag == _W + "tbl":
            runs = [(" | ".join(extract_docx_text(source)), "helv", 10.5)]
        if not runs:
            runs = [("", "helv", 10.5)]
        x = margin
        line_height = max(size * 1.35 for _, _, size in runs)
        for text, font, size in runs:
            for token in text.replace("\t", "    ").splitlines() or [""]:
                words = token.split(" ") if token else [""]
                for index, word in enumerate(words):
                    piece = word + (" " if index < len(words) - 1 else "")
                    advance = fitz.get_text_length(piece, fontname=font, fontsize=size)
                    if x > margin and x + advance > margin + width:
                        y += line_height
                        x = margin
                    if y + line_height > page.rect.height - margin:
                        page = document.new_page()
                        y = margin
                        x = margin
                    if piece:
                        page.insert_text((x, y), piece, fontname=font, fontsize=size)
                        x += advance
                y += line_height if "\n" in text else 0
        y += line_height + 4.0
    return document


def _docx_to_pdf_with_word(source: pathlib.Path) -> fitz.Document | None:
    """Use a separate, non-interactive Word instance when pywin32 is present."""
    if sys.platform != "win32":
        return None
    try:
        import win32com.client  # type: ignore[import-untyped]
    except ImportError:
        return None

    pdf_path: pathlib.Path | None = None
    word = None
    document = None
    try:
        handle, raw_path = tempfile.mkstemp(suffix=".pdf")
        os.close(handle)
        pdf_path = pathlib.Path(raw_path)
        word = win32com.client.DispatchEx("Word.Application")
        # 3 = msoAutomationSecurityForceDisable.  Do not allow the document
        # to run macros or refresh external content during conversion.
        word.AutomationSecurity = 3
        word.DisplayAlerts = 0
        word.Visible = False
        document = word.Documents.Open(
            str(source), ReadOnly=True, AddToRecentFiles=False,
            ConfirmConversions=False,
        )
        # 17 = wdExportFormatPDF; 0 = wdExportOptimizeForPrint.
        document.ExportAsFixedFormat(str(pdf_path), 17, False, 0)
        pdf_bytes = pdf_path.read_bytes()
        return fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        LOGGER.warning("Conversione DOCX tramite Word fallita: %s", exc)
        return None
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit(False)
            except Exception:
                pass
        if pdf_path is not None:
            try:
                pdf_path.unlink(missing_ok=True)
            except OSError:
                pass


__all__ = ["docx_to_pdf", "extract_docx_text"]
