"""End-to-end test for reconstructing a pseudonymized PDF."""

import pathlib
import sys

import fitz
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
