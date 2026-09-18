import fitz
import pytest

from pii_detection import (
    Candidate,
    build_page_index,
    clean_candidates,
    expand_group_ids,
    filter_results,
    load_enabled_groups,
    propagate_whole_word,
    resolve_overlaps,
    save_enabled_groups,
    span_to_rects,
    whole_word_rects,
    ALL_GROUP_IDS,
)


def _index(*lines):
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 20
    return build_page_index(page.get_text("words"))


class R:
    def __init__(self, start, end, entity_type, score):
        self.start, self.end, self.entity_type, self.score = start, end, entity_type, score


def test_offsets_map_to_words_across_lines():
    idx = _index("Mario Rossi abita", "a Roma")
    start = idx.text.index("Rossi")
    rects = span_to_rects(idx, start, start + 5)
    assert len(rects) == 1
    multi = span_to_rects(idx, idx.text.index("abita"), idx.text.index("Roma") + 4)
    assert len(multi) == 2


def test_partial_word_below_half_is_dropped_not_expanded():
    idx = _index("Rossini")
    assert span_to_rects(idx, 0, 3) == []
    assert len(span_to_rects(idx, 0, 5)) == 1


def test_whole_word_propagation_skips_longer_words():
    idx = _index("Rossi e Rossini", "Sig. Rossi")
    assert len(propagate_whole_word(idx, "Rossi")) == 2
    assert len(whole_word_rects(idx, "rossi")) == 2
    assert whole_word_rects(idx, "ross") == []


def test_thresholds_and_enabled_types():
    text = "x" * 40
    res = [R(0, 10, "IT_PASSPORT", 0.01), R(0, 10, "IBAN_CODE", 1.0),
           R(0, 10, "EMAIL_ADDRESS", 1.0)]
    out = filter_results(res, text, ["IT_PASSPORT", "IBAN_CODE"])
    assert [c.entity_type for c in out] == ["IBAN_CODE"]


def test_clean_drops_generic_and_lowercase_and_strips_honorifics():
    cands = [
        Candidate(0, 3, "Sig", "PERSON", 0.85),
        Candidate(0, 7, "gennaio", "LOCATION", 0.85),
        Candidate(0, 7, "mario rossi", "PERSON", 0.85),
        Candidate(0, 15, "Sig. Mario Rossi", "PERSON", 0.85),
        Candidate(0, 6, "a@b.it", "EMAIL_ADDRESS", 1.0),
    ]
    out = clean_candidates(cands)
    assert [c.text for c in out] == ["Mario Rossi", "a@b.it"]


def test_overlap_prefers_higher_score_then_longer():
    a = Candidate(0, 19, "CF RSSMRA80A01H501U", "LOCATION", 0.85)
    b = Candidate(3, 19, "RSSMRA80A01H501U", "IT_FISCAL_CODE", 1.0)
    assert resolve_overlaps([a, b]) == [b]


def test_group_persistence_and_corrupt_file(tmp_path):
    f = tmp_path / "sub" / "sel.json"
    assert load_enabled_groups(f) == ALL_GROUP_IDS
    save_enabled_groups(f, ["IBAN", "bogus"])
    assert load_enabled_groups(f) == ["IBAN"]
    f.write_text("{not json", encoding="utf-8")
    assert load_enabled_groups(f) == ALL_GROUP_IDS
    assert expand_group_ids(["IBAN", "PHONE"]) == ["PHONE_NUMBER", "IBAN_CODE"]


def test_real_analyzer_no_partial_word_redaction():
    pytest.importorskip("presidio_analyzer")
    spacy = pytest.importorskip("spacy")
    if not spacy.util.is_package("it_core_news_md"):
        pytest.skip("model missing")
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    nlp = NlpEngineProvider(nlp_configuration={"nlp_engine_name": "spacy", "models": [
        {"lang_code": "it", "model_name": "it_core_news_md"}]}).create_engine()
    reg = RecognizerRegistry(supported_languages=["it"])
    reg.load_predefined_recognizers(languages=["it"], nlp_engine=nlp)
    an = AnalyzerEngine(nlp_engine=nlp, registry=reg, supported_languages=["it"])
    idx = _index("Il Sig. Mario Rossi vive a Roma.", "Il collega Rossini abita a Romano.")
    res = an.analyze(text=idx.text, language="it", entities=["PERSON", "LOCATION"])
    cands = resolve_overlaps(clean_candidates(filter_results(res, idx.text, ["PERSON", "LOCATION"])))
    assert cands
    for c in cands:
        first = c.text.split()[0].lower()
        for rect in propagate_whole_word(idx, c.text):
            words = [idx.text[w.start:w.end] for w in idx.words if w.rect[1] == rect[1] and w.rect[0] >= rect[0] - 0.1 and w.rect[2] <= rect[2] + 0.1]
            assert words and words[0].strip(".,").lower() == first


def test_person_glued_to_address_is_split():
    text = "Rossini Marco Via Garibaldi"
    c = Candidate(0, len(text), text, "PERSON", 0.85)
    out = clean_candidates([c])
    assert [(x.entity_type, x.text) for x in out] == [
        ("LOCATION", "Via Garibaldi"), ("PERSON", "Rossini Marco"),
    ]
    only_person = clean_candidates([c], enabled_types=["PERSON"])
    assert [x.text for x in only_person] == ["Rossini Marco"]
    numbered = Candidate(0, 15, "Mario Rossi 12 A", "PERSON", 0.85)
    assert [x.text for x in clean_candidates([numbered], enabled_types=["PERSON"])] == ["Mario Rossi"]
    addr_first = Candidate(0, 13, "Via Garibaldi", "PERSON", 0.85)
    assert [x.entity_type for x in clean_candidates([addr_first])] == ["LOCATION"]
