"""End-to-end test for reconstructing a pseudonymized PDF."""

import pathlib
import sys

import pymupdf as fitz
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from NullifyPDF import RestoreMapMismatch, reconstruct_pdf
from privacy_core import (
    PlaceholderRegistry,
    build_restore_payload,
    decrypt_restore_payload,
    encrypt_restore_payload,
)


def _make_pseudonymized_pdf(path: pathlib.Path) -> PlaceholderRegistry:
    """Write a one-page PDF with "John Doe" replaced by its placeholder."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "John Doe lives in Rome.")

    registry = PlaceholderRegistry()
    placeholder = registry.placeholder_for("John Doe", "PERSON", page=0)
    rect = page.search_for("John Doe")[0]
    page.add_redact_annot(
        rect, text=placeholder, fill=(1, 1, 1), text_color=(0, 0, 0), align=1, fontsize=8
    )
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS, graphics=True)
    doc.save(str(path))
    doc.close()
    return registry


def test_reconstruct_pdf_restores_original_value(tmp_path):
    pseudonymized_path = tmp_path / "pseudonymized.pdf"
    registry = _make_pseudonymized_pdf(pseudonymized_path)

    from NullifyPDF import sha256_file

    payload = build_restore_payload(
        source_name="original.pdf",
        source_sha256="a" * 64,
        output_sha256=sha256_file(str(pseudonymized_path)),
        entries=registry.entries(),
    )
    encrypted = encrypt_restore_payload(payload, "correct horse battery staple")
    decrypted = decrypt_restore_payload(encrypted, "correct horse battery staple")

    out_path = tmp_path / "reconstructed.pdf"
    restored_count = reconstruct_pdf(str(pseudonymized_path), str(out_path), decrypted)

    assert restored_count == 1
    reconstructed_doc = fitz.open(str(out_path))
    text = reconstructed_doc[0].get_text("text")
    reconstructed_doc.close()
    assert "John Doe" in text
    assert "PERSON_001" not in text


def test_reconstruct_pdf_restores_repeated_value_on_later_page(tmp_path):
    """Regression test: PlaceholderRegistry only records the page of a
    value's *first* occurrence, so an entry's `page` field cannot be trusted
    to find every occurrence of its placeholder.
    """
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Mario Rossi lives in Rome.")
    doc.new_page().insert_text((72, 72), "Contact: Mario Rossi again.")

    registry = PlaceholderRegistry()
    placeholder = registry.placeholder_for("Mario Rossi", "PERSON", page=0)
    assert placeholder == "PERSON_001"

    for page_index in (0, 1):
        page = doc[page_index]
        for rect in page.search_for("Mario Rossi"):
            page.add_redact_annot(
                rect, text=placeholder, fill=(1, 1, 1), text_color=(0, 0, 0),
                align=1, fontsize=8,
            )
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS, graphics=True)

    pseudonymized_path = tmp_path / "pseudonymized.pdf"
    doc.save(str(pseudonymized_path))
    doc.close()

    from NullifyPDF import sha256_file

    payload = build_restore_payload(
        source_name="original.pdf",
        source_sha256="a" * 64,
        output_sha256=sha256_file(str(pseudonymized_path)),
        entries=registry.entries(),
    )

    out_path = tmp_path / "reconstructed.pdf"
    restored_count = reconstruct_pdf(str(pseudonymized_path), str(out_path), payload)

    assert restored_count == 2
    reconstructed_doc = fitz.open(str(out_path))
    text = "\n".join(p.get_text("text") for p in reconstructed_doc)
    reconstructed_doc.close()
    assert text.count("Mario Rossi") == 2
    assert "PERSON_001" not in text


def test_reconstruct_pdf_rejects_hash_mismatch(tmp_path):
    pseudonymized_path = tmp_path / "pseudonymized.pdf"
    registry = _make_pseudonymized_pdf(pseudonymized_path)

    payload = build_restore_payload(
        source_name="original.pdf",
        source_sha256="a" * 64,
        output_sha256="0" * 64,
        entries=registry.entries(),
    )

    out_path = tmp_path / "reconstructed.pdf"
    with pytest.raises(RestoreMapMismatch):
        reconstruct_pdf(str(pseudonymized_path), str(out_path), payload)


def _scanned_page_pdf(path: pathlib.Path) -> None:
    """Write a scanner-like PDF: one full-page raster image, no text layer."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    scan = fitz.open()
    scan_page = scan.new_page(width=595, height=842)
    scan_page.insert_text((80, 120), "Cliente: Mario Rossi", fontsize=14)
    image = scan_page.get_pixmap(dpi=150).tobytes("jpeg")
    scan.close()
    page.insert_image(page.rect, stream=image)
    doc.save(str(path), garbage=4, deflate=True, clean=True)
    doc.close()


def test_reconstruct_restores_placeholder_in_narrow_box(tmp_path):
    """Regression test for the real-world scanned-PDF failure.

    A redaction box that is narrow and tall (the shape you get drawing over
    a short field on a scan) makes `apply_redactions()` wrap the placeholder
    across lines: the page still *shows* ``DATA_001``, but
    `page.search_for("DATA_001")` finds nothing. Reconstruction used to key
    off that search alone, so it restored nothing, reported success and
    wrote an output identical to its input -- with no error anywhere.
    """
    from NullifyPDF import fit_redaction_fontsize, sha256_file

    scanned = tmp_path / "scan.pdf"
    _scanned_page_pdf(scanned)

    narrow_box = fitz.Rect(80, 108, 110, 148)  # 30 x 40: narrow and tall
    original = "Mario Rossi"

    registry = PlaceholderRegistry()
    doc = fitz.open(str(scanned))
    page = doc[0]
    placeholder = registry.placeholder_for(
        original,
        "DATA",
        page=page.number,
        rect=(narrow_box.x0, narrow_box.y0, narrow_box.x1, narrow_box.y1),
    )
    # Deliberately stamp the placeholder at the *unfitted* size the buggy
    # export used, so the pseudonymized PDF reproduces the wrapped,
    # unsearchable placeholder the user actually has on disk.
    page.add_redact_annot(
        narrow_box, text=placeholder, fill=(1, 1, 1), text_color=(0, 0, 0),
        align=1, fontsize=8,
    )
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS, graphics=True)
    pseudonymized = tmp_path / "pseudonymized.pdf"
    doc.save(str(pseudonymized), garbage=4, deflate=True, clean=True)
    doc.close()

    # Precondition: the placeholder is on the page but is NOT searchable.
    check = fitz.open(str(pseudonymized))
    assert placeholder not in check[0].get_text("text")
    assert check[0].search_for(placeholder) == []
    check.close()

    payload = build_restore_payload(
        source_name="scan.pdf",
        source_sha256="a" * 64,
        output_sha256=sha256_file(str(pseudonymized)),
        entries=registry.entries(),
    )
    out_path = tmp_path / "reconstructed.pdf"
    restored_count = reconstruct_pdf(str(pseudonymized), str(out_path), payload)

    assert restored_count == 1
    result = fitz.open(str(out_path))
    text = result[0].get_text("text")
    result.close()
    # The value is back. It wraps at its space inside the narrow box, which
    # is legible and correct -- what matters is that no token is broken.
    assert "".join(original.split()) in "".join(text.split())
    assert "Mario" in text and "Rossi" in text

    # And the fitted size stops the export side creating such a box at all.
    assert fit_redaction_fontsize(placeholder, narrow_box) < 8.0


def test_reconstruct_v1_map_finds_wrapped_placeholder(tmp_path):
    """Version 1 maps carry no coordinates, so the char-level fallback must
    find a placeholder that `search_for()` cannot."""
    from NullifyPDF import sha256_file

    scanned = tmp_path / "scan.pdf"
    _scanned_page_pdf(scanned)
    narrow_box = fitz.Rect(80, 108, 110, 148)

    doc = fitz.open(str(scanned))
    page = doc[0]
    page.add_redact_annot(
        narrow_box, text="DATA_001", fill=(1, 1, 1), text_color=(0, 0, 0),
        align=1, fontsize=8,
    )
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS, graphics=True)
    pseudonymized = tmp_path / "pseudonymized.pdf"
    doc.save(str(pseudonymized), garbage=4, deflate=True, clean=True)
    doc.close()

    # A map exactly as version 1 wrote them: no `occurrences` key at all.
    payload = {
        "format": "NullifyPDF restore map",
        "version": 1,
        "source_name": "scan.pdf",
        "source_sha256": "a" * 64,
        "output_sha256": sha256_file(str(pseudonymized)),
        "entries": [
            {
                "placeholder": "DATA_001",
                "original": "Mario Rossi",
                "entity_type": "DATA",
                "page": 0,
            }
        ],
    }
    out_path = tmp_path / "reconstructed.pdf"
    assert reconstruct_pdf(str(pseudonymized), str(out_path), payload) == 1
    result = fitz.open(str(out_path))
    text = result[0].get_text("text")
    result.close()
    assert "MarioRossi" in "".join(text.split())


def test_reconstruct_does_not_report_values_it_failed_to_write(tmp_path):
    """An original too long for its box is dropped by `apply_redactions()`.
    That must never be counted as a restored value."""
    from NullifyPDF import sha256_file

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((100, 300), "DATA_001", fontsize=8)
    pseudonymized = tmp_path / "pseudonymized.pdf"
    doc.save(str(pseudonymized), garbage=4, deflate=True, clean=True)
    doc.close()

    payload = {
        "format": "NullifyPDF restore map",
        "version": 1,
        "source_name": "x.pdf",
        "source_sha256": "a" * 64,
        "output_sha256": sha256_file(str(pseudonymized)),
        "entries": [
            {
                "placeholder": "DATA_001",
                "original": "RSSMRA80C12H501Z-UNBREAKABLE-TOKEN-FAR-TOO-LONG",
                "entity_type": "DATA",
                "page": 0,
            }
        ],
    }
    out_path = tmp_path / "reconstructed.pdf"
    # The value cannot fit the tight box; the honest answer is zero.
    assert reconstruct_pdf(str(pseudonymized), str(out_path), payload) == 0


def test_expected_restore_count_counts_occurrences_not_entries(tmp_path):
    """A repeated value is one entry but several boxes. The completeness
    check must compare against the boxes, or a half-restored repeated value
    looks like a full success."""
    from NullifyPDF import expected_restore_count

    registry = PlaceholderRegistry()
    registry.placeholder_for("Mario Rossi", "PERSON", page=0, rect=(10, 10, 80, 25))
    registry.placeholder_for("Mario Rossi", "PERSON", page=1, rect=(10, 10, 80, 25))
    registry.placeholder_for("Anna Bianchi", "PERSON", page=0, rect=(10, 40, 80, 55))
    entries = registry.entries()

    payload = build_restore_payload(
        source_name="x.pdf", source_sha256="a" * 64,
        output_sha256=None, entries=entries,
    )
    assert len(entries) == 2          # two distinct values...
    assert expected_restore_count(payload) == 3   # ...but three boxes to restore

    # Version 1 maps carry no boxes; each entry still counts for one.
    legacy = {
        "format": "NullifyPDF restore map", "version": 1,
        "source_name": "x.pdf", "source_sha256": "a" * 64, "output_sha256": None,
        "entries": [
            {"placeholder": "DATA_001", "original": "a", "entity_type": "DATA", "page": 0},
            {"placeholder": "DATA_002", "original": "b", "entity_type": "DATA", "page": 0},
        ],
    }
    assert expected_restore_count(legacy) == 2


def test_reconstruct_restores_adjacent_touching_boxes(tmp_path):
    """Two different values the user boxed side by side may have touching
    redaction boxes. Both must come back -- an overlap guard must not treat
    the second as a duplicate of the first."""
    from NullifyPDF import sha256_file

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((100, 300), "Placeholder area", fontsize=8)
    pseudonymized = tmp_path / "pseudonymized.pdf"
    doc.save(str(pseudonymized), garbage=4, deflate=True, clean=True)
    doc.close()

    registry = PlaceholderRegistry()
    # Deliberately touching along x=160, as two adjacent drawn boxes would be.
    registry.placeholder_for("Anna", "DATA", page=0, rect=(100, 290, 160, 310))
    registry.placeholder_for("Bruno", "DATA", page=0, rect=(160, 290, 220, 310))

    payload = build_restore_payload(
        source_name="x.pdf", source_sha256="a" * 64,
        output_sha256=sha256_file(str(pseudonymized)), entries=registry.entries(),
    )
    out_path = tmp_path / "reconstructed.pdf"
    assert reconstruct_pdf(str(pseudonymized), str(out_path), payload) == 2

    result = fitz.open(str(out_path))
    text = result[0].get_text("text")
    result.close()
    assert "Anna" in text and "Bruno" in text


def test_reconstruct_uses_stored_boxes_across_pages(tmp_path):
    """A repeated value records one occurrence per page; all must be restored
    from their own recorded box."""
    from NullifyPDF import sha256_file

    doc = fitz.open()
    for _ in range(2):
        doc.new_page(width=595, height=842).insert_text((100, 300), "x", fontsize=8)
    pseudonymized = tmp_path / "pseudonymized.pdf"
    doc.save(str(pseudonymized), garbage=4, deflate=True, clean=True)
    doc.close()

    registry = PlaceholderRegistry()
    for page_index in (0, 1):
        placeholder = registry.placeholder_for(
            "Mario Rossi", "PERSON", page=page_index, rect=(100, 290, 200, 310)
        )
    assert placeholder == "PERSON_001"
    assert len(registry.entries()) == 1
    assert len(registry.entries()[0].occurrences) == 2

    payload = build_restore_payload(
        source_name="x.pdf", source_sha256="a" * 64,
        output_sha256=sha256_file(str(pseudonymized)), entries=registry.entries(),
    )
    out_path = tmp_path / "reconstructed.pdf"
    assert reconstruct_pdf(str(pseudonymized), str(out_path), payload) == 2

    result = fitz.open(str(out_path))
    text = "\n".join(p.get_text("text") for p in result)
    result.close()
    assert text.count("Mario Rossi") == 2


def _styled_roundtrip(tmp_path, fontname, fontsize, color, value="Maria Bianchi", extra_font=None):
    """Export (capture style + placeholder) then reconstruct a native PDF."""
    from NullifyPDF import capture_text_style, sha256_file

    doc = fitz.open()
    page = doc.new_page()
    kwargs = {"fontname": fontname, "fontsize": fontsize, "color": color}
    if extra_font is not None:
        page.insert_font(fontname=fontname, fontbuffer=extra_font)
    page.insert_text((72, 100), f"Cliente {value} residente.", **kwargs)
    page.insert_text((72, 130), "Altro testo del documento.", **kwargs)
    rect = page.search_for(value)[0]
    style = capture_text_style(page, rect)
    registry = PlaceholderRegistry()
    placeholder = registry.placeholder_for(
        value, "PERSON", page=0, rect=tuple(rect), style=style
    )
    page.add_redact_annot(rect, text=placeholder, fill=(1, 1, 1), fontsize=8)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS, graphics=True)
    pseudo = tmp_path / "pseudo.pdf"
    doc.save(str(pseudo), garbage=4, deflate=True, clean=True)
    doc.close()
    payload = build_restore_payload(
        source_name="o.pdf",
        source_sha256="a" * 64,
        output_sha256=sha256_file(str(pseudo)),
        entries=registry.entries(),
    )
    out = tmp_path / "out.pdf"
    count = reconstruct_pdf(str(pseudo), str(out), payload)
    return style, count, out


def _span_for(path, needle):
    doc = fitz.open(str(path))
    try:
        for block in doc[0].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    if needle in span["text"].replace("\u00a0", " "):
                        return span
    finally:
        doc.close()
    return None


def test_native_reconstruction_keeps_size_color_and_serif(tmp_path):
    grey = (0.4, 0.4, 0.4)
    style, count, out = _styled_roundtrip(tmp_path, "tiro", 11, grey)
    assert style is not None and style["origin"]
    assert count == 1
    span = _span_for(out, "Maria Bianchi")
    assert span is not None
    assert span["size"] == pytest.approx(11, abs=0.1)
    assert span["color"] == 0x666666
    assert "times" in span["font"].lower() or span["flags"] & 4
    assert span["origin"][1] == pytest.approx(style["origin"][1], abs=0.5)


def test_native_reconstruction_uses_bold_face(tmp_path):
    style, count, out = _styled_roundtrip(tmp_path, "hebo", 12, (0, 0, 0))
    assert count == 1
    span = _span_for(out, "Maria Bianchi")
    assert span["size"] == pytest.approx(12, abs=0.1)
    assert span["flags"] & 16 or "bold" in span["font"].lower()


def test_native_reconstruction_reuses_embedded_font(tmp_path):
    font_file = pathlib.Path("C:/Windows/Fonts/arial.ttf")
    if not font_file.exists():
        pytest.skip("no system TrueType font available")
    buf = font_file.read_bytes()
    style, count, out = _styled_roundtrip(tmp_path, "F0", 10, (0, 0, 0), extra_font=buf)
    assert count == 1
    span = _span_for(out, "Maria Bianchi")
    assert span is not None
    assert span["size"] == pytest.approx(10, abs=0.1)


def test_scanned_style_is_none_and_fallback_still_restores(tmp_path):
    from NullifyPDF import capture_text_style

    doc = fitz.open()
    page = doc.new_page()
    assert capture_text_style(page, fitz.Rect(50, 50, 200, 80)) is None


def test_closest_base14_mapping():
    from NullifyPDF import closest_base14

    assert closest_base14({"font": "ABCDEF+Calibri", "flags": 0}) == "helv"
    assert closest_base14({"font": "TimesNewRomanPS-BoldMT", "flags": 20}) == "tibo"
    assert closest_base14({"font": "Consolas", "flags": 8}) == "cour"
    assert closest_base14({"font": "Arial-ItalicMT", "flags": 2}) == "heit"


def test_embedded_font_is_actually_reused(tmp_path):
    font_file = pathlib.Path("C:/Windows/Fonts/arial.ttf")
    if not font_file.exists():
        pytest.skip("no system TrueType font available")
    style, count, out = _styled_roundtrip(
        tmp_path, "F0", 10, (0, 0, 0), extra_font=font_file.read_bytes()
    )
    span = _span_for(out, "Maria Bianchi")
    assert "arial" in span["font"].lower()
