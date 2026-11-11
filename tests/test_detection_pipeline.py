"""Italian precision, pattern validation and allowlist semantics."""

import pytest

import pii_detection as pd
from _pdfgen import fake_words, res
import lexicon_it


def _run(text, results, enabled=None, **kw):
    idx = pd.build_page_index(fake_words(text), clamp=False)
    enabled = enabled or pd.expand_group_ids(pd.ALL_GROUP_IDS)
    cands, stats = pd.classify_page(results, idx, enabled, **kw)
    return idx, cands, stats


# --- lexicon -----------------------------------------------------------------

@pytest.mark.parametrize("word", [
    "Certifico", "Prescrivo", "Dichiaro", "Attesto", "Rilascio", "Confermo",
    "Raccomando", "Ordina", "Anamnesi", "Diagnosi", "Terapia", "Paziente",
    "PRESCRIVO", "Comune", "Tribunale",
])
def test_ordinary_words_are_recognised(word):
    assert lexicon_it.is_common_word(word)


@pytest.mark.parametrize("word", ["Rossi", "Esposito", "Mario", "Napoli", "Rosa", "Bruno"])
def test_names_are_not_common_words(word):
    assert not lexicon_it.is_common_word(word)


def test_verb_forms_are_generated_from_stems():
    forms = lexicon_it.verb_forms()
    assert {"certifica", "certificano", "prescrive", "prescrivono", "dichiara"} <= forms


# --- fake-analyzer pipeline (no model needed) -----------------------------------

def test_lone_verb_tagged_as_location_is_dropped():
    text = "Certifico\nPrescrivo\nRaccomando"
    results = [res("LOCATION", text, w) for w in ("Certifico", "Prescrivo", "Raccomando")]
    _idx, cands, stats = _run(text, results)
    assert cands == [] and stats.get("lexicon", 0) == 3


def test_verb_plus_drug_keeps_only_the_non_verb():
    text = "Visita del 3 aprile Prescrivo Augmentin"
    r = res("LOCATION", text, "Prescrivo Augmentin")
    _idx, cands, _ = _run(text, [r])
    assert all("Prescrivo" not in c.text for c in cands)


def test_name_with_context_is_accepted_and_scored_from_evidence():
    text = "Il Sig. Mario Rossi vive a Roma"
    results = [res("PERSON", text, "Mario Rossi"), res("LOCATION", text, "Roma")]
    _idx, cands, _ = _run(text, results)
    by_type = {c.entity_type: c for c in cands}
    assert by_type["PERSON"].state == "accepted" and by_type["PERSON"].score >= 0.7
    assert by_type["LOCATION"].state == "accepted"


def test_ambiguous_single_word_becomes_a_suggestion_not_a_drop():
    text = "Il referto indica che Colombi era presente"
    r = res("PERSON", text, "Colombi")
    _idx, cands, _ = _run(text, [r])
    assert len(cands) == 1 and cands[0].state == "suggested"


def test_health_mode_never_drops_silently():
    text = "Certifico"
    r = res("LOCATION", text, "Certifico")
    # Lexicon edges are a hard rule; use an uncertain non-lexicon word instead.
    text2 = "Noi Zorzi andiamo"
    r2 = res("PERSON", text2, "Zorzi")
    _i, normal, _ = _run(text2, [r2])
    _i, health, _ = _run(text2, [r2], health_mode=True)
    assert len(health) >= len(normal) and all(c.state != "dropped" for c in health)


def test_split_lines_of_one_name_are_merged():
    text = "Esposito\nGiovanni abita a Napoli"
    results = [res("PERSON", text, "Esposito"), res("PERSON", text, "Giovanni")]
    _idx, cands, _ = _run(text, results)
    person = [c for c in cands if c.entity_type == "PERSON"]
    assert len(person) == 1 and person[0].text.replace("\n", " ") == "Esposito Giovanni"
    assert person[0].state == "accepted"


def test_field_label_is_rejected_outright():
    text = "Nome: Mario"
    r = res("PERSON", text, "Nome")
    _idx, cands, _ = _run(text, [r])
    assert cands == []


def test_fragments_and_ocr_noise_are_rejected():
    text = "Rnario Ro"
    _i, normal, _ = _run(text, [res("PERSON", text, "Rnario")], used_ocr=True)
    assert normal == []
    kept, n = pd.reject_fragment_hits(
        [pd.Candidate(0, 4, "Li", "PERSON", 0.85)], used_ocr=False
    )
    assert kept == [] and n == 1


# --- pattern validation --------------------------------------------------------

def _pattern(text, etype, value, score=1.0):
    start = text.index(value)
    c = pd.Candidate(start, start + len(value), value, etype, score)
    return pd.refine_pattern_hit(c, text)


def test_fiscal_code_needs_boundaries_digits_or_context():
    ok, _ = _pattern("Codice fiscale: RSSMRA80A01H501U fine", "IT_FISCAL_CODE", "RSSMRA80A01H501U")
    assert ok
    ok, why = _pattern("xxRSSMRA80A01H501Uxx", "IT_FISCAL_CODE", "RSSMRA80A01H501U")
    assert not ok and why == "embedded-in-token"
    ok, why = _pattern("parola AAAAAAAAAAAAAAAA fine", "IT_FISCAL_CODE", "AAAAAAAAAAAAAAAA")
    assert not ok and why == "no-digit-no-context"


def test_vat_spaced_digits_need_context():
    ok, why = _pattern("totale 1234 5678 901 euro", "IT_VAT_CODE", "1234 5678 901", 0.1)
    assert not ok
    ok, _ = _pattern("P.IVA 12345678903 grazie", "IT_VAT_CODE", "12345678903", 1.0)
    assert ok
    ok, why = _pattern("numero 1234567890312 lungo", "IT_VAT_CODE", "12345678903", 1.0)
    assert not ok and why == "embedded-in-digits"


@pytest.mark.parametrize("etype,value,ctx_ok,ctx_bad", [
    ("IT_DRIVER_LICENSE", "AB1234567C", "patente di guida n. AB1234567C ok", "codice prodotto AB1234567C ok"),
    ("IT_PASSPORT", "YA1234567", "passaporto YA1234567 ok", "ordine YA1234567 ok"),
    ("IT_IDENTITY_CARD", "CA12345AB", "carta d'identita CA12345AB ok", "ticket CA12345AB ok"),
])
def test_document_numbers_need_their_context(etype, value, ctx_ok, ctx_bad):
    assert _pattern(ctx_ok, etype, value, 0.4)[0]
    assert not _pattern(ctx_bad, etype, value, 0.4)[0]
    assert not _pattern(ctx_ok.replace(value, value.lower()), etype, value.lower(), 0.4)[0]


@pytest.mark.parametrize("text,value,expect", [
    ("Tel. 340 1234567 fine", "340 1234567", True),
    ("chiama +39 02 1234567", "+39 02 1234567", True),
    ("Fattura del 12/03/2024 n.", "12/03/2024", False),
    ("anni 2018 - 2022 presso", "2018 - 2022", False),
    ("ordine 5551234 ok", "5551234", False),
    ("codice A340123456789", "340123456789", False),
])
def test_phone_plausibility(text, value, expect):
    assert _pattern(text, "PHONE_NUMBER", value, 0.4)[0] is expect


def _health(text, kinds=("DATE_OF_BIRTH", "HEALTH_ID", "HEALTH_EXEMPTION"), health_mode=False):
    return [(c.entity_type, c.text, c.state) for c in
            pd.detect_health_patterns(text, kinds, health_mode)]


def test_date_of_birth_needs_its_anchor():
    assert ("DATE_OF_BIRTH", "12/03/1970", "accepted") in _health("nato a Napoli il 12/03/1970")
    assert ("DATE_OF_BIRTH", "3 marzo 1985", "accepted") in _health("nata il 3 marzo 1985 a Roma")
    assert _health("Fattura del 12/03/2024") == []
    assert pd.detect_health_patterns("nato il 12/03/1970", []) == []


def test_tessera_requires_valid_region_and_exact_length():
    assert ("HEALTH_ID", "80380000501234567890", "accepted") in _health("Tessera 80380000501234567890 ok")
    assert any(t == "HEALTH_ID" for t, _, _ in _health("TS 80380 00050 123456789 0 ok"))
    assert _health("n. 80380009991234567890") == []       # invalid region code
    assert _health("n. 8038000050123456789") == []        # 19 digits
    assert _health("n. 803800005012345678901") == []      # 21 digits


def test_tessera_and_nre_are_both_reported():
    text = "Tessera 80380000501234567890 Ricetta *050A01234567890*"
    types = [(t, v) for t, v, _ in _health(text)]
    assert ("HEALTH_ID", "80380000501234567890") in types
    assert any(t == "HEALTH_ID" and v.strip("*").startswith("050A0") for t, v in types)


def test_nre_needs_context_unless_health_mode_where_it_is_a_suggestion():
    bare = "codice 050A01234567890 fine"
    assert _health(bare) == []
    assert ("HEALTH_ID", "050A01234567890", "suggested") in _health(bare, health_mode=True)
    assert _health("fattura 123456789012345") == []
    assert _health("Numero ricetta: 050A01234567890")[0][2] == "accepted"


def test_exemption_codes_need_context():
    assert ("HEALTH_EXEMPTION", "E01", "accepted") in _health("Esenzione: E01")
    assert _health("modello E01") == []
    assert ("HEALTH_EXEMPTION", "RA0010", "accepted") in _health("cod. es. RA0010 rara")
    assert _health("sezione C03 del regolamento") == []


def _addr(text, **kw):
    cands = pd.detect_address_parts(text, ["LOCATION"], **kw)
    return [(c.text, c.state) for c in cands]


def test_civic_number_joins_street_and_postcode_is_found():
    found = _addr("Via Garibaldi 12/B, 80100 Napoli (NA)")
    assert ("Via Garibaldi 12/B", "accepted") in found and ("80100", "accepted") in found
    assert ("Via Roma 10", "accepted") in _addr("abita in Via Roma 10 con la famiglia")


def test_postcode_not_matched_in_prices_dates_quantities():
    for text in ("Totale 12345 euro", "importo € 10000,00", "prot. 45678 del",
                 "ordinati 12345 Pezzi", "il 01/02/2024"):
        assert _addr(text) == [], text


def test_postcode_requires_an_anchor():
    assert ("20121", "accepted") in _addr("codice 20121 Milano")
    assert _addr("lotto 20121 Alfa") == []
    assert ("20121", "suggested") in _addr("lotto 20121 Alfa", health_mode=True)
    assert pd.detect_address_parts("Via Roma 10", ["PERSON"]) == []


def test_address_candidates_survive_the_pipeline_unscored():
    text = "Residente in Via Garibaldi 12 80100 Napoli"
    idx = pd.build_page_index(fake_words(text), clamp=False)
    cands, _ = pd.classify_page([], idx, ["LOCATION"])
    assert any(c.text.startswith("Via Garibaldi 12") and c.state == "accepted" for c in cands)


# --- allowlist semantics ----------------------------------------------------------

def _detections(text, etype, value, allow):
    idx = pd.build_page_index(fake_words(text), clamp=False)
    start = text.index(value)
    c = pd.Candidate(start, start + len(value), value, etype, 0.9)
    return pd.build_detections(idx, [c], allowlist=allow)


def test_allowlist_entry_does_not_suppress_a_shorter_value():
    # "rossini" allowlisted must not hide "Rossi" (substring bug).
    out = _detections("Dott. Rossi lavora qui", "PERSON", "Rossi", ["rossini"])
    assert len(out) == 1


def test_allowlisted_word_only_drops_that_word_from_a_longer_value():
    out = _detections("Mario Rossi vive qui", "PERSON", "Mario Rossi", ["mario"])
    assert len(out) == 1
    assert len(out[0]["rects"]) == 1
    # only "Rossi" remains covered
    idx = pd.build_page_index(fake_words("Mario Rossi vive qui"), clamp=False)
    assert out[0]["rects"][0][0] == pytest.approx(idx.words[1].rect[0])


def test_fully_allowlisted_value_disappears():
    assert _detections("Mario Rossi vive qui", "PERSON", "Mario Rossi", ["mario rossi"]) == []
    assert _detections("Il Comune di Roma", "LOCATION", "Roma", ["roma"]) == []


def test_allowlist_word_on_adjacent_line_never_cancels_pii():
    text = "Mario Rossi\nroma"
    out = _detections(text, "PERSON", "Mario Rossi", ["roma"])
    assert len(out) == 1


def test_propagation_keeps_whole_words_only_and_respects_allowlist():
    text = "Rossi e Rossini e Rossi"
    idx = pd.build_page_index(fake_words(text), clamp=False)
    c = pd.Candidate(0, 5, "Rossi", "PERSON", 0.9)
    out = pd.build_detections(idx, [c])
    assert len(out[0]["rects"]) == 2


def test_detection_carries_state_reasons_and_glued_flag():
    idx = pd.build_page_index(fake_words("CF:RSSMRA80A01H501U fine"), clamp=False)
    start = 3
    c = pd.Candidate(start, start + 16, "RSSMRA80A01H501U", "IT_FISCAL_CODE", 1.0)
    d = pd.build_detections(idx, [c])[0]
    assert d["state"] == "accepted" and d["rects"] and "reasons" in d


# --- real model (skipped when unavailable) ---------------------------------------

CASES = {
    "T1": ("Certifico\nche il Sig. Mario Rossi, nato a Napoli il 12/03/1970,",
           {"Mario Rossi", "Napoli", "12/03/1970"}, {"Certifico"}),
    "T2": ("Prescrivo\nTachipirina 1000 mg, 1 cpr ogni 8 ore", set(), {"Prescrivo"}),
    "T3": ("Certifico\nPrescrivo\nRaccomando", set(), {"Certifico", "Prescrivo", "Raccomando"}),
    "T4": ("Visita del 3/4. Prescrivo Augmentin.", set(), {"Prescrivo"}),
    "T5": ("CERTIFICO CHE IL PAZIENTE E' IDONEO. PRESCRIVO ESAMI EMATOCHIMICI.",
           set(), {"CERTIFICO", "PRESCRIVO", "PAZIENTE", "IDONEO"}),
    "T6": ("Il sottoscritto Avv. Paolo Neri dichiara\nche la sig.ra Gialli Anna e' residente a Roma.",
           {"Paolo Neri", "Gialli Anna", "Roma"}, {"dichiara", "Dichiara"}),
    "T7": ("Visto l'art. 7 del Regolamento, Ordina la comparizione delle parti.",
           set(), {"Ordina", "Visto"}),
    "T8": ("Esposito\nGiovanni, nato a Napoli.", {"Esposito Giovanni", "Napoli"}, set()),
    "T9": ("Rosa Bianco", {"Rosa Bianco"}, set()),
    "T11": ("Milano, 3 marzo 2026", {"Milano"}, set()),
    "T12": ("Dichiaro di aver ricevuto l'informativa.", set(), {"Dichiaro"}),
    "T13": ("Firmato: Dott.ssa Lucia Verdi", {"Lucia Verdi"}, {"Firmato"}),
    "T14": ("Anamnesi\nEsame obiettivo\nTerapia\nPrognosi", set(),
            {"Anamnesi", "Esame", "Terapia", "Prognosi"}),
}


@pytest.fixture(scope="module")
def italian_analyzer():
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
    return AnalyzerEngine(nlp_engine=nlp, registry=reg, supported_languages=["it"])


@pytest.mark.parametrize("case", sorted(CASES))
def test_italian_documents_with_real_model(italian_analyzer, case):
    text, must, never = CASES[case]
    idx = pd.build_page_index(fake_words(text), clamp=False)
    enabled = pd.expand_group_ids(pd.ALL_GROUP_IDS)
    presidio = [t for t in enabled if t not in pd.NON_PRESIDIO_TYPES]
    results = italian_analyzer.analyze(text=idx.text, entities=presidio, language="it")
    cands, _ = pd.classify_page(results, idx, enabled)
    accepted = {" ".join(c.text.split()) for c in cands if c.state == "accepted"}
    flagged = {w for c in cands for w in c.text.split()}
    assert must <= accepted, (case, accepted)
    assert not (never & flagged), (case, flagged)


def test_precision_on_ordinary_clinical_text_with_real_model(italian_analyzer):
    text = (
        "Certifico che il paziente e' affetto da lombalgia.\n"
        "Prescrivo riposo assoluto e visita di controllo.\n"
        "Raccomando terapia e dieta.\nDichiaro quanto sopra."
    )
    idx = pd.build_page_index(fake_words(text), clamp=False)
    enabled = pd.expand_group_ids(pd.ALL_GROUP_IDS)
    results = italian_analyzer.analyze(
        text=idx.text,
        entities=[t for t in enabled if t not in pd.NON_PRESIDIO_TYPES],
        language="it",
    )
    cands, _ = pd.classify_page(results, idx, enabled)
    assert [c for c in cands if c.state == "accepted"] == []


# --- signature / stamp suggestions ----------------------------------------------

def _signature_doc(extra_line=False):
    import pymupdf as _pm

    doc = _pm.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Il medico", fontsize=11)
    page.insert_text((72, 114), "Firma:", fontsize=11)
    sh = page.new_shape()
    for k in range(6):  # a curve-rich squiggle
        x = 120 + k * 12
        sh.draw_bezier(_pm.Point(x, 130), _pm.Point(x + 3, 105), _pm.Point(x + 7, 150), _pm.Point(x + 12, 128))
    sh.finish(color=(0, 0, 0), fill=None, closePath=False)
    sh.commit()
    if extra_line:
        page.draw_line(_pm.Point(72, 160), _pm.Point(400, 160))  # underline
    return doc


def test_signature_curves_near_firma_are_suggested_only():
    from pdf_sanitize import suggest_signature_areas

    doc = _signature_doc(extra_line=True)
    sugg = suggest_signature_areas(doc[0])
    assert len(sugg) == 1
    s = sugg[0]
    assert s["state"] == "suggested" and s["entity_type"] == "SIGNATURE" and not s["text"]
    x0, y0, x1, y1 = s["rects"][0]
    assert x0 < 112 and x1 > 195 and y0 < 100 and y1 > 155


def test_table_lines_and_unanchored_ink_are_not_signatures():
    import pymupdf as _pm
    from pdf_sanitize import suggest_signature_areas

    doc = _pm.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Firma:", fontsize=11)
    for k in range(8):
        page.draw_line(_pm.Point(72, 120 + k * 10), _pm.Point(472, 120 + k * 10))
    assert suggest_signature_areas(page) == []
    other = _pm.open()
    pg = other.new_page()
    pg.insert_text((72, 100), "Relazione tecnica", fontsize=11)
    sh = pg.new_shape()
    for k in range(6):
        x = 120 + k * 12
        sh.draw_bezier(_pm.Point(x, 130), _pm.Point(x + 3, 105), _pm.Point(x + 7, 150), _pm.Point(x + 12, 128))
    sh.finish(color=(0, 0, 0), fill=None, closePath=False)
    sh.commit()
    assert suggest_signature_areas(pg) == []


# --- ISTAT place data ------------------------------------------------------------

def test_generated_module_is_lazy_and_carries_sources_and_licence():
    import subprocess
    import sys

    code = (
        "import sys; sys.path.insert(0, %r); import lexicon_it; "
        "assert 'lexicon_data_it' not in sys.modules; "
        "assert lexicon_it.is_known_place('Zungri'); "
        "assert 'lexicon_data_it' in sys.modules"
    )
    root = __import__("pathlib").Path(__file__).resolve().parent.parent
    code = code % str(root)
    r = subprocess.run([sys.executable, "-I", "-c", code], cwd=str(root),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    head = (root / "lexicon_data_it.py").read_text(encoding="utf-8")[:600]
    assert "CC BY 4.0" in head and "istat_comuni" in head
    assert "CC BY 4.0" in (root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")


def test_istat_place_confirms_but_absence_never_rejects():
    assert lexicon_it.is_known_place("Zungri") and lexicon_it.is_known_place("Reggio nell'Emilia")
    text = "Il Sig. Mario Rossi abita a Zzyzxville"
    r = res("LOCATION", text, "Zzyzxville")
    _i, cands, _ = _run(text, [r])
    assert cands == [] or all(c.state != "dropped" for c in cands)  # scored as before, not rejected for absence


def test_ambiguous_comune_gets_only_a_small_boost():
    assert lexicon_it.is_ambiguous_place("Sale") and not lexicon_it.is_known_place("Sale")
    text = "Sale"
    r = res("LOCATION", text, "Sale")
    _i, cands, _ = _run(text, [r])
    assert all(c.state != "accepted" for c in cands)


def test_province_codes_come_from_istat():
    assert {"MI", "NA", "SU", "BT"} <= lexicon_it.province_codes()


def test_known_surname_helps_a_two_word_name_but_never_rejects():
    assert lexicon_it.is_known_surname("Marchetti")
    text = "Il referto di Gianpiero Marchetti"
    _i, cands, _ = _run(text, [res("PERSON", text, "Gianpiero Marchetti")])
    assert cands and "known-surname" in cands[0].reasons
    text2 = "Il referto di Gianpiero Qwertyuiop"
    _i, cands2, _ = _run(text2, [res("PERSON", text2, "Gianpiero Qwertyuiop")])
    assert cands2 and cands2[0].state in ("accepted", "suggested")  # absence is not a reason to reject


def test_wikidata_names_confirm_but_ambiguous_ones_do_not():
    import lexicon_data_it as d

    unambiguous = sorted(d.NAMES_SURNAMES - d.NAMES_AMBIGUOUS)
    assert unambiguous and lexicon_it.is_known_surname(unambiguous[0])
    ambiguous = sorted(d.NAMES_AMBIGUOUS & d.NAMES_SURNAMES)
    assert ambiguous and not lexicon_it.is_known_surname(ambiguous[0]) or ambiguous[0] in lexicon_it.SURNAMES
    assert not lexicon_it.is_known_surname("zzqxv")
    assert "Wikidata" in open(
        __import__("pathlib").Path(__file__).resolve().parent.parent / "THIRD_PARTY_NOTICES.md",
        encoding="utf-8").read()
