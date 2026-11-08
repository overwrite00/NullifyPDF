"""Regression tests for the PDF engine's redaction guarantees."""

import pymupdf
import pytest

from NullifyPDF import PDF_REDACT_IMAGE_PIXELS

SECRETS = ("SECRET-ONE", "SECRET-TWO", "SECRET-THREE")


def _pdf_with_quote_operator(path):
    """Build a page whose text is shown with the ``'`` operator after TL/Td."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 60), "Header line", fontsize=11)
    font = page.get_fonts(full=True)[0][4]
    stream = (
        f"BT /{font} 12 Tf 14 TL 72 700 Td (SECRET-ONE 123-45-6789) Tj "
        "0 -30 Td (SECRET-TWO mario@example.com) ' (SECRET-THREE iban) ' ET\n"
    ).encode()
    xref = page.get_contents()[0]
    doc.update_stream(xref, doc.xref_stream(xref) + b"\n" + stream)
    doc.save(path)
    doc.close()


def test_redaction_removes_text_shown_with_quote_operator(tmp_path):
    src = tmp_path / "src.pdf"
    out = tmp_path / "out.pdf"
    _pdf_with_quote_operator(str(src))

    doc = pymupdf.open(str(src))
    page = doc[0]
    for secret in SECRETS:
        for rect in page.search_for(secret):
            page.add_redact_annot(rect + (-2, -2, 150, 2))
    page.apply_redactions(images=PDF_REDACT_IMAGE_PIXELS, graphics=True)
    doc.save(str(out), garbage=4, deflate=True, clean=True)
    doc.close()

    result = pymupdf.open(str(out))
    assert "SECRET" not in result[0].get_text()
    leaked = [
        xref
        for xref in range(1, result.xref_length())
        if result.xref_is_stream(xref)
        and b"SECRET" in (result.xref_stream(xref) or b"")
    ]
    assert leaked == [], f"redacted text still present in streams {leaked}"
    result.close()
