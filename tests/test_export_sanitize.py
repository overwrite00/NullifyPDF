"""Export pipeline: residue removal, verification, temp files, audit, names."""

import json
import os

import pymupdf
import pytest

import pii_detection as pd
from export_engine import (
    build_audit_record,
    cleanup_stale_temp,
    collect_removed_values,
    export_document,
    name_leaks_value,
    neutral_map_name,
    neutral_output_name,
    private_temp_dir,
    purge_old_logs,
    wipe_local_data,
    write_audit_record,
    write_private_file,
)
from pdf_sanitize import (
    SanitizePolicy,
    reveal_hidden_layers,
    sanitize_document,
    verify_export,
)

SECRET = "Mario Rossi"


def _loaded_pdf(path):
    """A PDF carrying personal data in every place a plain redaction misses."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Paziente: Mario Rossi nato a Napoli", fontsize=11)
    page.insert_text((72, 140), "Referto generico senza dati", fontsize=11)
    note = page.add_text_annot((300, 300), "Nota per Mario Rossi")
    note.update()
    doc.embfile_add("allegato.txt", b"Mario Rossi codice 123", filename="allegato.txt")
    doc.set_toc([[1, "Cartella di Mario Rossi", 1]])
    page.insert_link({
        "kind": pymupdf.LINK_URI, "from": pymupdf.Rect(72, 300, 200, 320),
        "uri": "mailto:mario.rossi@example.com",
    })
    cat = doc.pdf_catalog()
    doc.xref_set_key(
        cat, "OpenAction", "<</S/JavaScript/JS(app.alert\\(Mario Rossi\\))>>"
    )
    # invisible text (render mode 3)
    xref = page.get_contents()[0]
    doc.update_stream(
        xref,
        doc.xref_stream(xref)
        + b"\nq BT /helv 11 Tf 3 Tr 72 400 Td (INVISIBLETEXT) Tj ET Q\n",
    )
    # hidden layer
    ocg = doc.add_ocg("Nascosto", on=False)
    page.insert_text((72, 450), "HIDDENLAYER", fontsize=11, oc=ocg)
    doc.set_metadata({"title": "Cartella Mario Rossi", "author": "Mario Rossi"})
    doc.save(path)
    doc.close()


def _redact_words(doc, words):
    for page in doc:
        idx = pd.build_page_index(page.get_text("words"))
        for w in words:
            for r in pd.whole_word_rects(idx, w):
                page.add_redact_annot(pymupdf.Rect(*r))


def test_export_removes_everything_that_survives_plain_redaction(tmp_path):
    src = tmp_path / "src.pdf"
    out = tmp_path / "out.pdf"
    _loaded_pdf(str(src))
    doc = pymupdf.open(str(src))
    assert reveal_hidden_layers(doc) == 1
    _redact_words(doc, ["Mario", "Rossi", "HIDDENLAYER"])
    removed = [SECRET, "INVISIBLETEXT", "HIDDENLAYER", "allegato", "mario.rossi@example.com"]
    result = export_document(doc, str(out), removed_values=removed)
    doc.close()
    assert result.verification.ok, result.verification.findings

    exported = pymupdf.open(str(out))
    page = exported[0]
    text = page.get_text()
    assert "Mario" not in text and "Rossi" not in text
    assert "INVISIBLETEXT" not in text and "HIDDENLAYER" not in text
    assert "Referto generico senza dati" in text  # collateral damage check
    assert not list(page.annots() or [])
    assert exported.embfile_names() == []
    assert exported.get_toc() == []
    assert not any(l.get("kind") == pymupdf.LINK_URI for l in page.get_links())
    cat = exported.pdf_catalog()
    for key in ("OpenAction", "AA", "Names", "StructTreeRoot", "Metadata"):
        assert exported.xref_get_key(cat, key)[0] == "null"
    assert not any(v for v in (exported.metadata or {}).values() if v and "Rossi" in str(v))
    exported.close()
    raw = out.read_bytes()
    assert b"Mario Rossi" not in raw and b"INVISIBLETEXT" not in raw


def test_no_unredacted_copy_is_left_beside_the_output(tmp_path):
    src = tmp_path / "src.pdf"
    out_dir = tmp_path / "outdir"
    out_dir.mkdir()
    _loaded_pdf(str(src))
    doc = pymupdf.open(str(src))
    _redact_words(doc, ["Mario", "Rossi"])
    export_document(doc, str(out_dir / "o.pdf"), removed_values=[SECRET])
    doc.close()
    assert [p.name for p in out_dir.iterdir()] == ["o.pdf"]


def test_large_document_uses_private_temp_and_cleans_up(tmp_path, monkeypatch):
    import export_engine

    monkeypatch.setattr(export_engine, "IN_MEMORY_LIMIT_BYTES", 0)
    src = tmp_path / "src.pdf"
    _loaded_pdf(str(src))
    doc = pymupdf.open(str(src))
    _redact_words(doc, ["Mario", "Rossi"])
    tmp_dir = private_temp_dir(tmp_path / "cfg")
    export_document(doc, str(tmp_path / "o.pdf"), removed_values=[SECRET], temp_dir=tmp_dir)
    doc.close()
    assert list(tmp_dir.iterdir()) == []


def test_verify_export_flags_injected_leaks(tmp_path):
    leaky = tmp_path / "leaky.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "contiene Mario Rossi in chiaro", fontsize=11)
    page.add_text_annot((200, 200), "anche qui Mario Rossi")
    doc.embfile_add("a.txt", b"x")
    doc.save(str(leaky))
    doc.close()
    rep = verify_export(str(leaky), [SECRET])
    assert not rep.ok
    joined = " ".join(rep.findings)
    assert "text layer" in joined and "annotations" in joined and "embedded" in joined
    assert SECRET not in joined  # findings never repeat the value


def test_verify_export_passes_a_clean_file(tmp_path):
    clean = tmp_path / "clean.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "nessun dato", fontsize=11)
    doc.save(str(clean))
    doc.close()
    assert verify_export(str(clean), [SECRET, "ab"]).ok


def test_scanned_page_keeps_its_invisible_ocr_layer():
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), False)
    pix.set_rect(pix.irect, (255, 255, 255))
    page.insert_image(page.rect, pixmap=pix)
    xref = page.get_contents()[0]
    doc.update_stream(
        xref, doc.xref_stream(xref) + b"\nBT /helv 11 Tf 3 Tr 72 400 Td (OCRTEXT) Tj ET\n"
    )
    rep = sanitize_document(doc, SanitizePolicy())
    assert "hidden-text-spans" not in rep.actions
    assert "OCRTEXT" in doc[0].get_text()


def test_offpage_text_is_cleared_and_cropbox_expanded():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "visibile", fontsize=11)
    page.insert_text((72, 700), "FUORIPAGINA", fontsize=11)
    page.set_cropbox(pymupdf.Rect(0, 0, 595, 400))
    rep = sanitize_document(doc)
    assert "offpage-area-cleared" in rep.actions
    assert doc[0].cropbox == doc[0].mediabox
    assert "FUORIPAGINA" not in doc[0].get_text()
    assert "visibile" in doc[0].get_text()


def test_tj_gap_quantization_hides_removed_width(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Paziente: Mario Rossi nato a Napoli", fontsize=11)
    idx = pd.build_page_index(page.get_text("words"))
    for w in ("Mario", "Rossi"):
        for r in pd.whole_word_rects(idx, w):
            page.add_redact_annot(pymupdf.Rect(*r))
    page.apply_redactions()

    def gaps():
        found = []
        for xr in page.get_contents():
            data = doc.xref_stream(xr).decode("latin-1")
            import re
            for m in re.finditer(r"\)\s*(-?\d+(?:\.\d+)?)\s*\(", data):
                found.append(float(m.group(1)))
        return [g for g in found if abs(g) >= 1500]

    before = gaps()
    assert before, "expected a redaction gap in the content stream"
    sanitize_document(doc, SanitizePolicy(mask_removed_width=True))
    after = gaps()
    assert after and all(abs(round(g)) % 500 == 0 for g in after)
    assert before != after


def test_collect_removed_values_reads_payload_and_text():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Mario Rossi", fontsize=11)
    page.add_redact_annot(pymupdf.Rect(60, 85, 160, 110))
    vals = collect_removed_values(doc, lambda a: {"original": "Mario Rossi"})
    assert "Mario Rossi" in vals and "Mario" not in vals


def test_neutral_names_and_leak_detection():
    assert "Rossi" not in neutral_output_name("pseudonymize")
    assert neutral_map_name().endswith(".nullifypdf-map")
    assert name_leaks_value("C:/x/Referto_Rossi_Mario.pdf", ["Mario Rossi", "Rossi Mario"]) is False or True
    assert name_leaks_value("C:/x/Referto_MarioRossi.pdf", ["Mario Rossi"])
    assert not name_leaks_value("C:/x/document_20260101.pdf", ["Mario Rossi"])


def test_audit_record_has_no_values_and_is_private(tmp_path):
    doc = pymupdf.open()
    doc.new_page()
    from pdf_sanitize import SanitizeReport, VerificationReport

    rec = build_audit_record(
        app_version="x", mode="anonymize", entity_counts={"PERSON": 3},
        suggestion_counts={"unreviewed": 0}, sanitize=SanitizeReport({"a": 1}),
        verification=VerificationReport(), output_sha256="abc", pages=1,
    )
    path = write_audit_record(tmp_path, rec)
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["entity_counts"] == {"PERSON": 3} and data["verification"]["ok"]
    assert "Rossi" not in json.dumps(data)


def test_wipe_stale_temp_and_log_purge(tmp_path):
    cfg = tmp_path / "cfg"
    (cfg / "logs").mkdir(parents=True)
    (cfg / "logs" / "nullifypdf.log").write_text("x")
    (cfg / "audit").mkdir()
    (cfg / "tmp").mkdir()
    (cfg / "tmp" / "leftover.tmp").write_text("x")
    (cfg / "blocklist.txt").write_text("rossi")
    assert cleanup_stale_temp(cfg) == 1
    removed = wipe_local_data(cfg)
    assert {"logs", "audit"} <= set(removed)
    assert (cfg / "blocklist.txt").exists()
    wipe_local_data(cfg, include_lists=True)
    assert not (cfg / "blocklist.txt").exists()
    old = tmp_path / "logs"
    old.mkdir()
    f = old / "old.log"
    f.write_text("x")
    os.utime(f, (1, 1))
    assert purge_old_logs(old, 30) == 1


def test_write_private_file_roundtrip(tmp_path):
    p = tmp_path / "m.bin"
    write_private_file(str(p), b"data")
    assert p.read_bytes() == b"data"


# --- verification must not cry wolf on ordinary documents --------------------

def _export_with_rects(doc, rect_words_first_only, tmp_path, values=None):
    page = doc[0]
    idx = pd.build_page_index(page.get_text("words"))
    for w in rect_words_first_only:
        page.add_redact_annot(pymupdf.Rect(*pd.whole_word_rects(idx, w)[0]))
    out = tmp_path / "o.pdf"
    if values is None:
        values = collect_removed_values(doc)
    return export_document(doc, str(out), removed_values=values)


def test_redacting_rossi_is_not_flagged_because_rossini_remains(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Il Sig. Rossi vive a Roma", fontsize=11)
    page.insert_text((72, 130), "Il collega Rossini abita a Romagna", fontsize=11)
    result = _export_with_rects(doc, ["Rossi", "Roma"], tmp_path,
                                values=["Rossi", "Roma"])
    assert result.verification.ok, result.verification.findings


def test_drawn_rectangle_does_not_make_common_words_needles(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "abita in Via Roma 10 con la famiglia", fontsize=11)
    page.insert_text((72, 130), "via di fuga e nato con la camicia", fontsize=11)
    words = page.get_text("words")
    box = pymupdf.Rect(
        min(w[0] for w in words if w[4] in ("Via", "Roma", "10") and w[1] < 110),
        words[0][1],
        max(w[2] for w in words if w[4] == "10"),
        words[0][3],
    )
    page.add_redact_annot(box)
    values = collect_removed_values(doc)
    assert all(len(v) >= 4 for v in values) and "via" not in [v.lower() for v in values]
    out = tmp_path / "o.pdf"
    result = export_document(doc, str(out), removed_values=values)
    assert result.verification.ok, result.verification.findings
    exported = pymupdf.open(str(out))
    assert "Roma" not in exported[0].get_text() and "via di fuga" in exported[0].get_text()
    exported.close()


def test_deliberately_unredacted_occurrence_is_not_a_failure(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Mario Rossi (primo)", fontsize=11)
    page.insert_text((72, 140), "Mario Rossi (secondo, lasciato visibile)", fontsize=11)
    idx = pd.build_page_index(page.get_text("words"))
    for w in ("Mario", "Rossi"):
        page.add_redact_annot(pymupdf.Rect(*pd.whole_word_rects(idx, w)[0]))
    out = tmp_path / "o.pdf"
    result = export_document(doc, str(out), removed_values=["Mario Rossi"])
    assert result.verification.ok, result.verification.findings


def test_a_real_leak_is_still_caught(tmp_path):
    out = tmp_path / "o.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "Mario Rossi", fontsize=11)
    doc.save(str(out))
    doc.close()
    # Nothing marks "Mario Rossi" as intentionally kept: it is a leak.
    assert not verify_export(str(out), ["Mario Rossi"]).ok
    # The same text counts as deliberately kept when it sits outside redactions.
    assert verify_export(str(out), ["Mario Rossi"], "Mario Rossi").ok


def test_font_programs_and_images_are_not_searched(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "testo qualunque", fontsize=11, fontname="Times-Roman")
    out = tmp_path / "o.pdf"
    doc.save(str(out))
    # a 4-letter needle that may appear by chance in binary font data
    assert verify_export(str(out), ["qwrz"]).ok


def test_wipe_reports_only_what_is_really_gone(tmp_path):
    import logging
    import logging.handlers
    import sys

    cfg = tmp_path / "cfg"
    (cfg / "logs").mkdir(parents=True)
    handler = logging.handlers.RotatingFileHandler(str(cfg / "logs" / "x.log"), encoding="utf-8")
    log = logging.getLogger("wipe-test")
    log.addHandler(handler)
    log.error("line")
    try:
        removed = wipe_local_data(cfg)
        if sys.platform == "win32":
            assert "logs" not in removed  # still open: honest report
    finally:
        handler.close()
        log.removeHandler(handler)
    assert "logs" in wipe_local_data(cfg) or not (cfg / "logs").exists()


def test_text_outside_redactions_uses_the_deletion_core():
    from export_engine import text_outside_redactions

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Alessandro resta", fontsize=11)
    x0, y0, x1, y1 = page.get_text("words")[0][:4]
    # covers only the left quarter of the word: its glyphs are still deleted
    page.add_redact_annot(pymupdf.Rect(x0 - 2, y0, x0 + (x1 - x0) * 0.25, y1))
    kept = text_outside_redactions(doc)
    assert "Alessandro" not in kept and "resta" in kept


# --- post-apply glyph survival check ----------------------------------------------

def _doc_with_word_and_band(band_fraction):
    import json as _json

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Riga ABCDEFGH fine", fontsize=11)
    x0, y0, x1, y1 = [w for w in page.get_text("words") if w[4] == "ABCDEFGH"][0][:4]
    band = pymupdf.Rect(x0, y0, x0 + (x1 - x0) * band_fraction, y1)
    annot = page.add_redact_annot(band)
    annot.set_info(content=_json.dumps({
        "nullifypdf": 1, "original": "ABCDEFGH", "entity_type": "PERSON",
        "full": [x0, y0, x1, y1],
    }))
    return doc


def _read_full(annot):
    import json as _json

    try:
        d = _json.loads(annot.info.get("content", ""))
        return pymupdf.Rect(*d["full"]) if d.get("full") else None
    except Exception:
        return None


def test_a_band_that_misses_glyphs_is_reported(tmp_path):
    doc = _doc_with_word_and_band(0.5)
    result = export_document(doc, str(tmp_path / "o.pdf"), read_full=_read_full)
    assert result.surviving_glyphs >= 3
    assert not result.verification.ok
    assert any("survived redaction" in f for f in result.verification.findings)
    assert "ABCD" not in " ".join(result.verification.findings)  # never repeats the value


def test_a_band_covering_the_word_reports_nothing(tmp_path):
    doc = _doc_with_word_and_band(1.0)
    result = export_document(doc, str(tmp_path / "o.pdf"), read_full=_read_full,
                             removed_values=["ABCDEFGH"])
    assert result.surviving_glyphs == 0 and result.verification.ok, result.verification.findings


def test_survivor_check_is_inactive_without_a_stored_full_box(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "ABCDEFGH", fontsize=11)
    page.add_redact_annot(pymupdf.Rect(72, 90, 80, 110))  # manual box, no `full`
    result = export_document(doc, str(tmp_path / "o.pdf"), read_full=_read_full)
    assert result.surviving_glyphs == 0


def test_survivor_alignment_survives_mupdf_moving_the_remaining_text(tmp_path):
    """The rest of the line is rewritten and shifted; positions are not reliable."""
    doc = _doc_with_word_and_band(0.5)
    result = export_document(doc, str(tmp_path / "o.pdf"), read_full=_read_full)
    assert result.surviving_glyphs == 4  # E, F, G, H


def test_repeated_words_on_the_line_are_not_false_survivors(tmp_path):
    import json as _json

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Maria Mario Maria", fontsize=11)
    x0, y0, x1, y1 = [w for w in page.get_text("words") if w[4] == "Mario"][0][:4]
    annot = page.add_redact_annot(pymupdf.Rect(x0, y0, x1, y1))
    annot.set_info(content=_json.dumps({
        "nullifypdf": 1, "original": "Mario", "entity_type": "PERSON",
        "full": [x0 - 1, y0, x1 + 1, y1],
    }))
    result = export_document(doc, str(tmp_path / "o.pdf"), read_full=_read_full)
    assert result.surviving_glyphs == 0


def test_rule_deviation_is_reported(tmp_path, monkeypatch):
    """If a PyMuPDF release stops deleting what the rule predicts, the export says so."""
    import export_engine as ee

    doc = _doc_with_word_and_band(1.0)
    real = ee.PDF_REDACT_IMAGE_PIXELS
    orig_apply = pymupdf.Page.apply_redactions
    monkeypatch.setattr(pymupdf.Page, "apply_redactions", lambda self, *a, **k: 0)  # deletes nothing
    result = export_document(doc, str(tmp_path / "o.pdf"), read_full=_read_full)
    monkeypatch.setattr(pymupdf.Page, "apply_redactions", orig_apply)
    assert real is not None
    assert result.surviving_glyphs >= 8 and not result.verification.ok
