"""Redaction geometry: no neighbour damage, no leak, correct partial policy."""

import pymupdf
import pytest

import pii_detection as pd
from _pdfgen import fake_words, make_doc, res
from export_engine import export_document

LINES = ["Commissione tributaria", "Mario Rossi gggg yyyy", "Programmazione generale"]


def _redact_and_export(doc, targets, tmp_path, clamp=True):
    page = doc[0]
    idx = pd.build_page_index(page.get_text("words"), clamp=clamp)
    for t in targets:
        for r in pd.whole_word_rects(idx, t):
            page.add_redact_annot(pymupdf.Rect(*r))
    out = tmp_path / "out.pdf"
    result = export_document(doc, str(out), removed_values=targets)
    exported = pymupdf.open(str(out))
    text = exported[0].get_text()
    exported.close()
    return result, text


@pytest.mark.parametrize("pitch", [7, 8, 9, 10, 11, 12, 13.2, 16])
def test_clamped_rects_keep_neighbour_lines_intact(pitch, tmp_path):
    doc = make_doc(LINES, pitch=pitch)
    result, text = _redact_and_export(doc, ["Mario", "Rossi", "gggg", "yyyy"], tmp_path)
    assert "Commissione tributaria" in text
    assert "Programmazione generale" in text
    for secret in ("Mario", "Rossi", "gggg", "yyyy"):
        assert secret not in text
    assert result.verification.ok, result.verification.findings


def test_unclamped_boxes_damage_tight_neighbours(tmp_path):
    """Documents the defect the clamp fixes (11 pt text, 11 pt pitch)."""
    doc = make_doc(LINES, pitch=11)
    _r, text = _redact_and_export(doc, ["Mario", "Rossi", "gggg", "yyyy"], tmp_path, clamp=False)
    assert not ("Commissione tributaria" in text and "Programmazione generale" in text)


def test_clamp_only_trims_against_other_lines():
    words = [
        (0, 0, 40, 15, "Alpha", 0, 0, 0),
        (45, 0, 60, 15, "Beta", 0, 0, 1),
        (0, 11, 40, 26, "Gamma", 0, 1, 0),
    ]
    idx = pd.build_page_index(words)
    alpha, beta, gamma = idx.words
    assert alpha.rect[3] == pytest.approx(11 + 0.1 * 15 - 0.3)  # stops short of the neighbour core
    assert beta.rect == (45, 0, 60, 15)  # no horizontal overlap: untouched
    assert gamma.rect[1] == pytest.approx(15 - 0.1 * 15 + 0.3)
    assert alpha.rect[0] == 0 and alpha.rect[2] == 40


def test_clamp_keeps_original_when_text_collides_heavily():
    words = [
        (0, 0, 40, 15, "Alpha", 0, 0, 0),
        (0, 2, 40, 17, "Beta", 0, 1, 0),
    ]
    idx = pd.build_page_index(words)
    assert idx.words[0].rect == (0, 0, 40, 15)
    assert idx.words[1].rect == (0, 2, 40, 17)


def test_clamp_ocr_mode_cuts_at_middle_of_overlap_and_pads():
    words = [
        (10, 0, 50, 15, "Alpha", 0, 0, 0),
        (10, 11, 50, 26, "Gamma", 0, 1, 0),
    ]
    idx = pd.build_page_index(words, ocr=True)
    assert idx.words[0].rect[3] == pytest.approx(13.0)
    assert idx.words[0].rect[0] == pytest.approx(9.0)
    assert idx.words[0].rect[2] == pytest.approx(51.0)


def test_mixed_sizes_on_one_line_keep_full_height():
    words = [
        (0, 0, 40, 15, "Big", 0, 0, 0),
        (42, 0, 50, 8, "2", 0, 0, 1),
        (0, 40, 40, 55, "Below", 0, 1, 0),
    ]
    idx = pd.build_page_index(words)
    assert [w.rect for w in idx.words] == [(0, 0, 40, 15), (42, 0, 50, 8), (0, 40, 40, 55)]


def test_vertical_text_is_not_clamped():
    words = [
        (0, 0, 8, 60, "Verticale", 0, 0, 0),
        (0, 55, 8, 115, "Altra", 0, 1, 0),
    ]
    idx = pd.build_page_index(words)
    assert idx.words[0].rect == (0, 0, 8, 60)


def test_letter_spaced_run_becomes_one_analysis_word():
    letters = "Commissione"
    words = [
        (10 + 9 * i, 0, 16 + 9 * i, 12, ch, 0, 0, i) for i, ch in enumerate(letters)
    ]
    idx = pd.build_page_index(words)
    assert idx.text == "Commissione"
    assert len(idx.words) == len(letters)


def test_hyphenated_name_is_joined_across_lines():
    words = [
        (10, 0, 40, 12, "Ros-", 0, 0, 0),
        (10, 14, 50, 26, "sini", 0, 1, 0),
    ]
    idx = pd.build_page_index(words, clamp=False)
    assert idx.text == "Rossini"
    rects = pd.rects_for_words(idx, pd.span_word_indices(idx, 0, 7))
    assert len(rects) == 2  # one rectangle per line


def test_ligatures_are_expanded_for_analysis():
    idx = pd.build_page_index([(0, 0, 50, 12, "Ufﬁcio", 0, 0, 0)])
    assert idx.text == "Ufficio"


def test_partial_policy_ner_rejects_fragment_of_longer_word():
    text = "Il collega Rossini abita qui"
    idx = pd.build_page_index(fake_words(text), clamp=False)
    c = pd.Candidate(text.index("Ross"), text.index("Ross") + 4, "Ross", "PERSON", 0.85)
    assert pd.resolve_word_indices(idx, c) == ([], "embedded-in-word")


def test_partial_policy_validated_identifier_glued_to_label_is_redacted():
    text = "CF:RSSMRA80A01H501U fine"
    idx = pd.build_page_index(fake_words(text), clamp=False)
    start = text.index("RSSMRA")
    c = pd.Candidate(start, start + 16, text[start:start + 16], "IT_FISCAL_CODE", 1.0)
    idxs, status = pd.resolve_word_indices(idx, c)
    assert idxs and status in ("ok", "glued")


def test_partial_policy_short_overlap_of_validated_type_redacts_whole_token():
    text = "IBANIT60X0542811101000000123456 fine"
    idx = pd.build_page_index(fake_words(text), clamp=False)
    start = text.index("IT60")
    c = pd.Candidate(start, start + 5, text[start:start + 5], "IBAN_CODE", 1.0)
    idxs, status = pd.resolve_word_indices(idx, c)
    assert idxs and status == "glued"


def test_merge_line_rects_and_covered_fraction():
    merged = pd.merge_line_rects([(0, 0, 10, 10), (10.5, 0, 20, 10), (0, 30, 10, 40)])
    assert merged == [(0, 0, 20, 10), (0, 30, 10, 40)]
    assert pd.covered_fraction((0, 0, 10, 10), [(0, 0, 10, 5)]) == pytest.approx(0.5)
    assert pd.covered_fraction((0, 0, 10, 10), [(20, 20, 30, 30)]) == 0.0


def test_fake_result_helper_roundtrip():
    text = "Mario Rossi"
    r = res("PERSON", text, "Rossi")
    assert text[r.start:r.end] == "Rossi"


# --- the deletion rule the core-band clamp relies on (canary for new releases) ----

@pytest.mark.parametrize("fontname,size", [("helv", 11), ("helv", 20), ("tiro", 11), ("cour", 11)])
def test_glyph_deletion_core_is_ten_percent_inset(fontname, size):
    """MuPDF deletes a glyph only when the rectangle reaches its core box.

    If a PyMuPDF release changes this, the core-band clamp is unsafe: this
    test (and the CI job against the latest PyMuPDF) must fail first.
    """
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((100, 300), "H", fontsize=size, fontname=fontname)
    ch = page.get_text("rawdict")["blocks"][0]["lines"][0]["spans"][0]["chars"][0]
    x0, y0, x1, y1 = ch["bbox"]
    h = y1 - y0
    top_core = y0 + 0.10 * h
    bottom_core = y1 - 0.10 * h

    def deleted(band):
        d2 = pymupdf.open("pdf", doc.tobytes())
        p2 = d2[0]
        p2.add_redact_annot(pymupdf.Rect(*band))
        p2.apply_redactions()
        return "H" not in p2.get_text()

    eps = 0.15
    # just short of the core from above / below: kept; just inside: deleted
    assert not deleted((x0 - 5, y0 - 5, x1 + 5, top_core - eps))
    assert deleted((x0 - 5, y0 - 5, x1 + 5, top_core + eps))
    assert not deleted((x0 - 5, bottom_core + eps, x1 + 5, y1 + 5))
    assert deleted((x0 - 5, bottom_core - eps, x1 + 5, y1 + 5))


def test_core_band_mixed_sizes_spares_neighbours(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Intestazione piccola", fontsize=9)
    page.insert_text((72, 108), "Paziente Alessandro Marchetti", fontsize=11)
    page.insert_text((72, 118), "Nota finale minuscola", fontsize=8)
    result, text = _redact_and_export(doc, ["Alessandro", "Marchetti"], tmp_path)
    assert "Intestazione piccola" in text and "Nota finale minuscola" in text
    assert "Alessandro" not in text and "Marchetti" not in text


def test_empty_clipped_target_never_approves_thin_band():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Mario Rossi", fontsize=11)
    idx = pd.build_page_index(page.get_text("words"), clamp=False)
    full = pymupdf.Rect(*pd.whole_word_rects(idx, "Mario")[0])
    thin = pymupdf.Rect(full.x0, full.y0, full.x1, full.y0 + 0.01)
    from NullifyPDF import band_covers_target
    assert not band_covers_target(page, thin, full)


def test_no_safe_band_flags_collision_and_still_removes_target(tmp_path):
    doc = make_doc(LINES, pitch=5)
    page = doc[0]
    idx = pd.build_page_index(page.get_text("words"))
    assert idx.collisions > 0
    result, text = _redact_and_export(doc, ["Mario", "Rossi"], tmp_path)
    assert "Mario" not in text and "Rossi" not in text


def test_words_over_an_image_never_get_a_thin_band():
    words = [
        (10, 0, 50, 15, "Alpha", 0, 0, 0),
        (10, 11, 50, 26, "Gamma", 0, 1, 0),
    ]
    native = pd.build_page_index(words)
    over_image = pd.build_page_index(words, image_rects=[(0, 0, 100, 40)])
    assert native.words[0].native and not over_image.words[0].native
    assert over_image.words[0].rect[3] == pytest.approx(13.0)  # mid-overlap
    assert over_image.words[0].rect[0] == pytest.approx(9.0)   # horizontal pad


@pytest.mark.parametrize("pitch", [9, 10, 12])
def test_style_capture_ignores_neighbour_lines(pitch):
    from NullifyPDF import capture_text_style

    doc = make_doc(
        ["Commissione tributaria provinciale", "Paziente Alessandro nato", "Programmazione generale dei servizi"],
        pitch=pitch,
    )
    page = doc[0]
    idx = pd.build_page_index(page.get_text("words"), clamp=False)
    for rect in pd.whole_word_rects(idx, "Alessandro"):  # raw, unclamped box
        style = capture_text_style(page, pymupdf.Rect(*rect))
        assert style is not None and style["text"] == "Alessandro"
