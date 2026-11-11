"""Minimal, local DOCX importer used to create an analyzable PDF document.

The importer intentionally handles the OOXML text layer without executing
macros, embedded objects, external links or document relationships.  The
result is a new PDF representation; the original DOCX is never modified.
"""

from __future__ import annotations

import pathlib
import zipfile
import xml.etree.ElementTree as ET
from typing import List

import fitz  # type: ignore[import-untyped]


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _paragraph_text(node: ET.Element) -> str:
    return "".join((t.text or "") for t in node.iter(_W + "t"))


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
    """Return a local PDF representation of a DOCX for the existing pipeline."""
    source = pathlib.Path(path)
    if source.suffix.lower() != ".docx":
        raise ValueError("Sono supportati documenti Word DOCX; il formato DOC binario non è supportato.")
    lines = extract_docx_text(source)
    document = fitz.open()
    page = document.new_page()
    margin = 54.0
    width = page.rect.width - 2 * margin
    y = margin
    fontsize = 10.5
    line_height = 15.0
    for raw in lines or [""]:
        words = raw.split()
        current = ""
        chunks: List[str] = []
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and fitz.get_text_length(candidate, fontname="helv", fontsize=fontsize) > width:
                chunks.append(current)
                current = word
            else:
                current = candidate
        chunks.append(current)
        for line in chunks:
            if y + line_height > page.rect.height - margin:
                page = document.new_page()
                y = margin
            page.insert_text((margin, y), line, fontname="helv", fontsize=fontsize)
            y += line_height
        y += 4.0
    return document


__all__ = ["docx_to_pdf", "extract_docx_text"]
