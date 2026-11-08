"""Offscreen functional tests of the review / export / reconstruct flows.

mypy and unit tests do not exercise Qt slots and dialogs, so these drive the
real window with Qt's offscreen platform and stubbed modal dialogs. HOME is
isolated so the user's real ~/.nullifypdf is never touched.
"""

import json
import os

import pymupdf
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QDialog, QFileDialog, QInputDialog, QMessageBox,
)

import NullifyPDF as app  # noqa: E402
from privacy_core import (  # noqa: E402
    PrivacyMode, decrypt_restore_payload,
)
from review_dialog import ReviewDialog, mask_value  # noqa: E402


@pytest.fixture()
def window(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    qapp = QApplication.instance() or QApplication([])
    w = app.NullifyPDF()
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Paziente: Alessandro Marchetti nato a Napoli", fontsize=11)
    page.insert_text((72, 130), "Zorzi era presente alla visita", fontsize=11)
    doc.save(str(tmp_path / "Referto_Mario_Rossi.pdf"))
    doc.close()
    w.doc = pymupdf.open(str(tmp_path / "Referto_Mario_Rossi.pdf"))
    yield w
    try:
        w._cleanup_resources()
    except Exception:
        pass
    qapp.processEvents()


def _rect_of(w, word):
    page = w.doc[0]
    idx = app.build_page_index(page.get_text("words"))
    return list(app.whole_word_rects(idx, word)[0])


def _detection(w, word, etype, state, score=0.9):
    return {"text": word, "entity_type": etype, "rects": [_rect_of(w, word)],
            "state": state, "score": score, "reasons": ["context-cue"]}


def _redacts(w):
    return [a for a in w.doc[0].annots() if a.type[0] == app.PDF_ANNOT_REDACT]


def test_accepted_applies_and_suggested_waits_for_review(window):
    w = window
    w.apply_ai_to_page(0, [
        _detection(w, "Alessandro", "PERSON", "accepted"),
        _detection(w, "Zorzi", "PERSON", "suggested", 0.5),
    ])
    assert len(_redacts(w)) == 1
    assert len(w.pending_suggestions) == 1
    assert w.btn_review.text() == "Rivedi suggerimenti (1)" and w.btn_review.isEnabled()


def test_review_dialog_applies_only_selected(window, monkeypatch):
    w = window
    w.apply_ai_to_page(0, [_detection(w, "Zorzi", "PERSON", "suggested", 0.5)])

    def fake_exec(self):
        self.table.item(0, 0).setCheckState(app.Qt.CheckState.Checked)
        self._on_apply()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ReviewDialog, "exec", fake_exec)
    w._review_suggestions()
    assert w.pending_suggestions == []
    assert len(_redacts(w)) == 1


def test_review_dialog_reject_discards_and_later_keeps_pending(window, monkeypatch):
    w = window
    w.apply_ai_to_page(0, [_detection(w, "Zorzi", "PERSON", "suggested", 0.5)])
    monkeypatch.setattr(
        ReviewDialog, "exec",
        lambda self: (self._on_apply(), QDialog.DialogCode.Accepted)[1],
    )
    w._review_suggestions()
    assert w.pending_suggestions == [] and _redacts(w) == []
    w.apply_ai_to_page(0, [_detection(w, "Zorzi", "PERSON", "suggested", 0.5)])
    monkeypatch.setattr(ReviewDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    w._review_suggestions()
    assert len(w.pending_suggestions) == 1


def test_review_dialog_masks_values_until_asked(window):
    dlg = ReviewDialog([{"text": "Zorzi", "entity_type": "PERSON", "score": 0.5,
                         "page": 0, "reasons": ["lexicon"]}])
    assert dlg.table.item(0, 2).text() == mask_value("Zorzi") != "Zorzi"
    dlg.chk_show.setChecked(True)
    assert dlg.table.item(0, 2).text() == "Zorzi"
    dlg.spin.setValue(0.4)
    dlg._select_threshold()
    assert dlg.table.item(0, 0).checkState() == app.Qt.CheckState.Checked
    got = []
    dlg.navigate.connect(got.append)
    dlg._on_double_click(0, 0)
    assert got == [0]


def test_overlapping_detections_are_not_applied_twice(window):
    w = window
    w.apply_ai_to_page(0, [_detection(w, "Alessandro", "PERSON", "accepted")])
    w.apply_ai_to_page(0, [_detection(w, "Alessandro", "PERSON", "accepted")])
    assert len(_redacts(w)) == 1


def test_legacy_detection_without_rects_never_redacts_fragments(window):
    w = window
    w.doc.close()
    d = pymupdf.open()
    d.new_page().insert_text((72, 100), "Marchettini e Marchetti", fontsize=11)
    w.doc = d
    w.apply_ai_to_page(0, {"Ross"})
    assert _redacts(w) == []
    w.apply_ai_to_page(0, {"Marchetti"})
    assert len(_redacts(w)) == 1


def _stub_dialogs(monkeypatch, files, answer=QMessageBox.StandardButton.Yes):
    seq = list(files)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (seq.pop(0), "")))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: answer))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def test_anonymize_export_end_to_end(window, tmp_path, monkeypatch):
    w = window
    w.apply_ai_to_page(0, [
        _detection(w, "Alessandro", "PERSON", "accepted"),
        _detection(w, "Marchetti", "PERSON", "accepted"),
    ])
    out = tmp_path / "exported.pdf"
    _stub_dialogs(monkeypatch, [str(out)])
    monkeypatch.setattr(w, "_select_privacy_export", lambda: PrivacyMode.ANONYMIZE)
    w.cmd_export()
    assert out.exists()
    exported = pymupdf.open(str(out))
    text = exported[0].get_text()
    exported.close()
    assert "Alessandro" not in text and "Marchetti" not in text and "Napoli" in text
    assert sorted(p.name for p in tmp_path.iterdir() if p.suffix == ".tmp") == []
    audit = list((w.config_dir / "audit").glob("*.json"))
    assert len(audit) == 1
    record = json.loads(audit[0].read_text(encoding="utf-8"))
    assert record["entity_counts"] == {"PERSON": 2} and record["verification"]["ok"]
    assert "Marchetti" not in audit[0].read_text(encoding="utf-8")
    assert w.doc is not None and len(_redacts(w)) == 2  # original untouched


def test_export_warns_about_unreviewed_suggestions(window, tmp_path, monkeypatch):
    w = window
    w.apply_ai_to_page(0, [_detection(w, "Zorzi", "PERSON", "suggested", 0.5)])
    asked = []

    class Box:
        class _B:  # minimal stand-in for a QMessageBox button
            pass

    def fake_exec(self):
        asked.append(self.text())

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    # Clicking nothing = Cancel: export must stop before any file dialog.
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: None)
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: pytest.fail("export continued despite pending suggestions")),
    )
    w.cmd_export()
    assert asked and "non revisionati" in asked[0]


def test_pseudonymize_export_with_random_style_roundtrips(window, tmp_path, monkeypatch):
    w = window
    w.apply_ai_to_page(0, [
        _detection(w, "Alessandro", "PERSON", "accepted"),
        _detection(w, "Marchetti", "PERSON", "accepted"),
    ])
    out = tmp_path / "pseudo.pdf"
    mapf = tmp_path / "maps" / "m.nullifypdf-map"
    mapf.parent.mkdir()
    _stub_dialogs(monkeypatch, [str(out), str(mapf)])
    monkeypatch.setattr(w, "_select_privacy_export", lambda: PrivacyMode.PSEUDONYMIZE)
    monkeypatch.setattr(w, "_select_pseudonym_style", lambda: ("random", None))
    monkeypatch.setattr(w, "_ask_map_password", lambda: "una frase molto lunga 2026")
    monkeypatch.setattr(w, "_offer_recovery_key", lambda: None)
    w.cmd_export()
    assert out.exists() and mapf.exists()
    pdf = pymupdf.open(str(out))
    text = pdf[0].get_text()
    pdf.close()
    assert "Alessandro" not in text and "PERSON_" in text and "PERSON_001" not in text
    payload = decrypt_restore_payload(mapf.read_bytes(), "una frase molto lunga 2026")
    assert payload["source_name"] == ""
    assert {e["original"] for e in payload["entries"]} == {"Alessandro", "Marchetti"}
    restored = tmp_path / "restored.pdf"
    n = app.reconstruct_pdf(str(out), str(restored), payload)
    assert n == 2
    back = pymupdf.open(str(restored))
    assert "Alessandro" in back[0].get_text()
    back.close()


def test_export_stops_when_verification_fails_and_user_deletes(window, tmp_path, monkeypatch):
    w = window
    w.apply_ai_to_page(0, [_detection(w, "Alessandro", "PERSON", "accepted")])
    out = tmp_path / "bad.pdf"
    _stub_dialogs(monkeypatch, [str(out)])
    monkeypatch.setattr(w, "_select_privacy_export", lambda: PrivacyMode.ANONYMIZE)
    # A value that survives redaction (it is in the visible text): force a
    # failing verification by claiming "Napoli" was removed.
    monkeypatch.setattr(app, "collect_removed_values", lambda *a, **k: ["Napoli"])
    import export_engine
    monkeypatch.setattr(export_engine, "text_outside_redactions", lambda d: "")
    w.cmd_export()
    assert not out.exists()
    assert not list((w.config_dir / "audit").glob("*.json"))


def test_wipe_local_data(window, monkeypatch):
    w = window
    (w.config_dir / "audit").mkdir(parents=True, exist_ok=True)
    (w.config_dir / "audit" / "x.json").write_text("{}")
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    w.cmd_wipe_local_data()
    assert not (w.config_dir / "audit").exists()


def test_default_language_follows_system_locale(window):
    assert window.rb_it.isChecked() or window.rb_both.isChecked()
    assert not window.rb_en.isChecked()


def test_worker_scan_end_to_end_with_real_italian_model(tmp_path, monkeypatch):
    """Drives AIWorker.run_scan itself: wiring of artifacts, classify, build."""
    spacy = pytest.importorskip("spacy")
    pytest.importorskip("presidio_analyzer")
    if not spacy.util.is_package("it_core_news_md"):
        pytest.skip("model missing")
    from PySide6.QtCore import QMutex

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    QApplication.instance() or QApplication([])
    doc = pymupdf.open()
    page = doc.new_page()
    lines = [
        "Certifico",
        "che il Sig. Mario Rossi, nato a Napoli il 12/03/1970,",
        "e' affetto da lombalgia.",
        "Prescrivo",
        "riposo assoluto.",
        "Codice fiscale: RSSMRA70C12F839Y",
    ]
    for i, t in enumerate(lines):
        page.insert_text((72, 100 + 16 * i), t, fontsize=11)
    worker = app.AIWorker()
    done, logs = [], []
    worker.page_done_sig.connect(lambda i, d: done.append((i, d)))
    worker.log_sig.connect(logs.append)
    enabled = app.expand_group_ids(app.ALL_GROUP_IDS)
    worker.run_scan(doc, QMutex(), "IT", [], set(), False, None, enabled, True)
    assert len(done) == 1, logs
    dets = done[0][1]
    texts = {d["text"] for d in dets}
    assert "Mario Rossi" in texts and "Napoli" in texts and "12/03/1970" in texts
    assert not texts & {"Certifico", "Prescrivo"}
    assert all("state" in d and d["rects"] for d in dets)
    assert any(l.startswith("Scansione completata") for l in logs)
    worker.cleanup()


def test_worker_ocr_of_embedded_images_keeps_native_text(tmp_path, monkeypatch):
    """A text page with an image: OCR adds the image text, native text stays."""
    spacy = pytest.importorskip("spacy")
    pytest.importorskip("presidio_analyzer")
    if not spacy.util.is_package("it_core_news_md"):
        pytest.skip("model missing")
    tessdata = app.find_tessdata_dir()
    if not tessdata:
        pytest.skip("tessdata missing")
    from PySide6.QtCore import QMutex

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    QApplication.instance() or QApplication([])
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Il Sig. Mario Rossi abita a Napoli.", fontsize=12)
    src = pymupdf.open()
    sp = src.new_page(width=300, height=60)
    sp.insert_text((10, 40), "Dott. Giuseppe Verdi", fontsize=22)
    page.insert_image(pymupdf.Rect(72, 200, 372, 260), pixmap=sp.get_pixmap(dpi=150))
    worker = app.AIWorker()
    done, logs = [], []
    worker.page_done_sig.connect(lambda i, d: done.append(d))
    worker.log_sig.connect(logs.append)
    enabled = app.expand_group_ids(app.ALL_GROUP_IDS)
    worker.run_scan(doc, QMutex(), "IT", [], set(), True, tessdata, enabled, False)
    texts = {" ".join(d["text"].split()) for d in done[0]}
    assert "Mario Rossi" in texts, (texts, logs)
    assert any("Giuseppe Verdi" in t for t in texts), (texts, logs)
    assert any("OCR immagini" in l for l in logs)
    worker.cleanup()


def test_roundtrip_with_trimmed_rectangles_on_tight_leading(window, tmp_path, monkeypatch):
    """11 pt text on a 12 pt pitch: rectangles are trimmed, restore still works."""
    w = window
    w.doc.close()
    d = pymupdf.open()
    pg = d.new_page()
    for i, t in enumerate([
        "Commissione tributaria provinciale",
        "Paziente Alessandro Marchetti nato oggi",
        "Programmazione generale dei servizi",
    ]):
        pg.insert_text((72, 100 + 12 * i), t, fontsize=11)
    w.doc = d
    w.apply_ai_to_page(0, [
        _detection(w, "Alessandro", "PERSON", "accepted"),
        _detection(w, "Marchetti", "PERSON", "accepted"),
    ])
    out = tmp_path / "t.pdf"
    mapf = tmp_path / "maps" / "m.nullifypdf-map"
    mapf.parent.mkdir()
    _stub_dialogs(monkeypatch, [str(out), str(mapf)])
    monkeypatch.setattr(w, "_select_privacy_export", lambda: PrivacyMode.PSEUDONYMIZE)
    monkeypatch.setattr(w, "_select_pseudonym_style", lambda: ("random", None))
    monkeypatch.setattr(w, "_ask_map_password", lambda: "una frase molto lunga 2026")
    monkeypatch.setattr(w, "_offer_recovery_key", lambda: None)
    w.cmd_export()
    pdf = pymupdf.open(str(out))
    text = pdf[0].get_text()
    pdf.close()
    assert "Commissione tributaria provinciale" in text
    assert "Programmazione generale dei servizi" in text
    assert "Alessandro" not in text
    payload = decrypt_restore_payload(mapf.read_bytes(), "una frase molto lunga 2026")
    restored = tmp_path / "r.pdf"
    assert app.reconstruct_pdf(str(out), str(restored), payload) == 2
    back = pymupdf.open(str(restored))
    t2 = back[0].get_text()
    back.close()
    assert "Alessandro" in t2 and "Marchetti" in t2
    assert "Commissione tributaria provinciale" in t2


def test_image_redaction_is_not_duplicated_by_later_applies(window, tmp_path):
    w = window
    w.doc.close()
    d = pymupdf.open()
    pg = d.new_page()
    pg.insert_text((72, 100), "Alessandro Marchetti", fontsize=11)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
    pix.set_rect(pix.irect, (10, 10, 10))
    pg.insert_image(pymupdf.Rect(300, 300, 340, 340), pixmap=pix)
    w.doc = d
    w.chk_img.setChecked(True)
    w.apply_ai_to_page(0, [_detection(w, "Alessandro", "PERSON", "accepted")])
    w.apply_ai_to_page(0, [_detection(w, "Marchetti", "PERSON", "accepted")])
    assert len(_redacts(w)) == 3  # two words + one image, not two images


def test_invalid_pseudonym_key_file_is_refused(window, monkeypatch):
    w = window
    (w.config_dir).mkdir(parents=True, exist_ok=True)
    (w.config_dir / "pseudonym.key").write_bytes(b"short")
    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox, "clickedButton", lambda self: next(
            b for b in self.buttons() if b.text() == "Coerente (chiave)"
        ),
    )
    monkeypatch.setattr(
        QMessageBox, "critical", staticmethod(lambda *a, **k: shown.append(a[2]))
    )
    assert w._select_pseudonym_style() is None
    assert shown and "32 byte" in shown[0]


def test_signature_suggestion_is_never_applied_without_review_and_export_removes_ink(window, tmp_path, monkeypatch):
    from pdf_sanitize import suggest_signature_areas

    w = window
    w.doc.close()
    import test_detection_pipeline as tdp

    w.doc = tdp._signature_doc()
    sug = suggest_signature_areas(w.doc[0])
    assert len(sug) == 1
    w.apply_ai_to_page(0, sug)
    assert _redacts(w) == [] and len(w.pending_suggestions) == 1  # not applied
    monkeypatch.setattr(
        ReviewDialog, "exec",
        lambda self: (self.table.item(0, 0).setCheckState(app.Qt.CheckState.Checked),
                      self._on_apply(), QDialog.DialogCode.Accepted)[2],
    )
    w._review_suggestions()
    assert len(_redacts(w)) == 1
    out = tmp_path / "sig.pdf"
    _stub_dialogs(monkeypatch, [str(out)])
    monkeypatch.setattr(w, "_select_privacy_export", lambda: PrivacyMode.ANONYMIZE)
    w.cmd_export()
    exported = pymupdf.open(str(out))
    region = pymupdf.Rect(*sug[0]["rects"][0])
    inside = [
        d for d in exported[0].get_drawings()
        if region.contains(d["rect"]) and any(it[0] == "c" for it in d["items"])
    ]  # the grey fill rectangle itself is expected
    exported.close()
    assert inside == []


def test_dictionary_dialog_sets_expiry_and_persists(window, monkeypatch):
    import datetime
    from dictionary_dialog import DictionaryDialog

    w = window
    dlg = DictionaryDialog(w.list_manager)
    dlg.ttl.setCurrentIndex(1)  # 30 giorni
    dlg.add_term("blocklist", "Mario Rossi")
    dlg.add_term("allowlist", "comune")
    dlg.save()
    assert dlg.saved_blocklist == {"mario rossi"} and dlg.saved_allowlist == {"comune"}
    entries = w.list_manager.load_entries("blocklist")
    assert entries[0].expires == datetime.date.today() + datetime.timedelta(days=30)
    assert not (w.config_dir / "blocklist.txt").exists()
    assert b"rossi" not in (w.config_dir / "blocklist.v2.enc").read_bytes()


def test_dictionary_dialog_rejects_bad_dates_and_keeps_data(window, monkeypatch):
    from dictionary_dialog import DictionaryDialog

    w = window
    w.list_manager.save_blocklist({"mario rossi"})
    dlg = DictionaryDialog(w.list_manager)
    dlg.tables["blocklist"].item(0, 2).setText("domani")
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warned.append(a[2])))
    dlg.save()
    assert warned and dlg.saved_blocklist is None
    assert w.list_manager.load_blocklist() == {"mario rossi"}


def test_cmd_dict_updates_in_memory_lists(window, monkeypatch):
    import dictionary_dialog as dd

    w = window

    def fake_exec(self):
        self.add_term("blocklist", "nuovo termine")
        self.save()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(dd.DictionaryDialog, "exec", fake_exec)
    w.cmd_dict()
    assert w.blocklist == {"nuovo termine"}


# --- protected pseudonym key, recovery key ------------------------------------------

def test_plaintext_pseudonym_key_is_validated_sealed_and_removed(window):
    w = window
    w.config_dir.mkdir(parents=True, exist_ok=True)
    legacy = w.config_dir / "pseudonym.key"
    legacy.write_bytes(b"k" * 32)
    key = w._load_pseudonym_key()
    assert key == b"k" * 32
    assert not legacy.exists()
    enc = (w.config_dir / "pseudonym.v2.enc").read_bytes()
    assert b"k" * 32 not in enc
    assert w._load_pseudonym_key() == key


def test_new_pseudonym_key_is_created_sealed(window):
    w = window
    key = w._load_pseudonym_key()
    assert len(key) == 32 and w._load_pseudonym_key() == key
    assert key not in (w.config_dir / "pseudonym.v2.enc").read_bytes()
    assert not (w.config_dir / "pseudonym.key").exists()


def test_pseudonym_key_export_and_import_on_another_profile(window, tmp_path, monkeypatch):
    w = window
    key = w._load_pseudonym_key()
    out = tmp_path / "k.nullifypdf-key"
    monkeypatch.setattr(w, "_ask_map_password", lambda: "una frase molto lunga 2026")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), "")))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox, "clickedButton",
        lambda self: next(b for b in self.buttons() if b.text() == "Esporta chiave..."),
    )
    w._pseudonym_key_dialog()
    assert out.exists() and key not in out.read_bytes()
    # simulate a new machine: wipe the stored key, then import
    (w.config_dir / "pseudonym.v2.enc").unlink()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(out), "")))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("una frase molto lunga 2026", True)))
    monkeypatch.setattr(
        QMessageBox, "clickedButton",
        lambda self: next(b for b in self.buttons() if b.text() == "Importa chiave..."),
    )
    w._pseudonym_key_dialog()
    assert w._load_pseudonym_key() == key


def test_export_with_recovery_key_and_reconstruct_by_recovery(window, tmp_path, monkeypatch):
    from privacy_core import generate_recovery_key, parse_recovery_key

    w = window
    w.apply_ai_to_page(0, [
        _detection(w, "Alessandro", "PERSON", "accepted"),
        _detection(w, "Marchetti", "PERSON", "accepted"),
    ])
    out, mapf = tmp_path / "p.pdf", tmp_path / "maps" / "m.nullifypdf-map"
    mapf.parent.mkdir()
    raw, shown = generate_recovery_key()
    _stub_dialogs(monkeypatch, [str(out), str(mapf)])
    monkeypatch.setattr(w, "_select_privacy_export", lambda: PrivacyMode.PSEUDONYMIZE)
    monkeypatch.setattr(w, "_select_pseudonym_style", lambda: ("random", None))
    monkeypatch.setattr(w, "_ask_map_password", lambda: "una frase molto lunga 2026")
    monkeypatch.setattr(w, "_offer_recovery_key", lambda: raw)
    w.cmd_export()
    blob = mapf.read_bytes()
    assert raw not in blob and shown.encode() not in blob
    for f in tmp_path.rglob("*"):
        if f.is_file():
            assert shown.encode() not in f.read_bytes()
    env = json.loads(blob)
    assert [x["type"] for x in env["wraps"]] == ["password", "recovery"]
    # reconstruct through the recovery key only
    restored = tmp_path / "r.pdf"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(
        lambda *a, **k: (str(out), "") if "pseudonimizzato" in a[1] else (str(mapf), "")))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(restored), "")))
    monkeypatch.setattr(w, "_ask_decrypt_secret", lambda: (None, parse_recovery_key(shown)))
    w.cmd_reconstruct()
    back = pymupdf.open(str(restored))
    assert "Alessandro" in back[0].get_text()
    back.close()


def test_wrong_secret_gives_one_clear_message(window, tmp_path, monkeypatch):
    w = window
    w.apply_ai_to_page(0, [_detection(w, "Alessandro", "PERSON", "accepted")])
    out, mapf = tmp_path / "p.pdf", tmp_path / "m.nullifypdf-map"
    _stub_dialogs(monkeypatch, [str(out), str(mapf)])
    monkeypatch.setattr(w, "_select_privacy_export", lambda: PrivacyMode.PSEUDONYMIZE)
    monkeypatch.setattr(w, "_select_pseudonym_style", lambda: ("random", None))
    monkeypatch.setattr(w, "_ask_map_password", lambda: "una frase molto lunga 2026")
    monkeypatch.setattr(w, "_offer_recovery_key", lambda: None)
    w.cmd_export()
    shown = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(
        lambda *a, **k: (str(out), "") if "pseudonimizzato" in a[1] else (str(mapf), "")))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(tmp_path / "x.pdf"), "")))
    monkeypatch.setattr(w, "_ask_decrypt_secret", lambda: ("password completamente sbagliata", None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: shown.append(a[2])))
    w.cmd_reconstruct()
    assert shown and "recupero" in shown[0]


def test_wipe_keys_makes_encrypted_lists_unreadable_only_with_confirmation(window, monkeypatch):
    w = window
    w.list_manager.save_blocklist({"mario rossi"})
    answers = iter([QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Yes])
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: next(answers)))
    w.cmd_wipe_local_data()
    assert not (w.config_dir / "keystore.json").exists()
    assert not (w.config_dir / "blocklist.v2.enc").exists()


# --- preview overlay of pending suggestions (real mouse events) ------------------------

def _click_scene_point(w, scene_pt):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    vp = w.view.mapFromScene(scene_pt)
    gp = QPointF(vp)
    glob = QPointF(w.view.viewport().mapToGlobal(vp))
    for typ, fn, btns in (
        (QEvent.Type.MouseButtonPress, w.view.mousePressEvent, Qt.MouseButton.LeftButton),
        (QEvent.Type.MouseButtonRelease, w.view.mouseReleaseEvent, Qt.MouseButton.NoButton),
    ):
        fn(QMouseEvent(typ, gp, glob, Qt.MouseButton.LeftButton, btns, Qt.KeyboardModifier.NoModifier))
    QApplication.processEvents()
    # the view defers a lone click slightly (to tell it from a double click)
    import time
    deadline = time.time() + 1.0
    while time.time() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)


def _overlays(w):
    return [i for i in w.scene.items() if isinstance(i, app.SuggestionItem)]


def _pick(monkeypatch, label):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox, "clickedButton",
        lambda self: next(b for b in self.buttons() if b.text() == label),
    )


def _two_page_doc(w):
    w.doc.close()
    d = pymupdf.open()
    for t in ("Pagina uno Zorzi presente", "Pagina due Colombi presente"):
        d.new_page().insert_text((72, 100), t, fontsize=11)
    w.doc = d
    w.page_num = 0
    w.render_page()


def _sugg(w, page, word):
    idx = app.build_page_index(w.doc[page].get_text("words"))
    return {"text": word, "entity_type": "PERSON", "score": 0.5, "page": page,
            "rects": [list(app.whole_word_rects(idx, word)[0])], "reasons": ["lexicon"],
            "state": "suggested"}


def test_overlay_only_on_the_suggestion_page_and_follows_zoom(window):
    w = window
    _two_page_doc(w)
    w.pending_suggestions = [_sugg(w, 0, "Zorzi"), _sugg(w, 1, "Colombi")]
    w.render_page()
    assert len(_overlays(w)) == 1
    r0 = _overlays(w)[0].rect()
    w.adjust_zoom(+2)
    r1 = _overlays(w)[0].rect()
    assert r1.width() == pytest.approx(r0.width() * w.scale / (w.scale - 0.5), rel=1e-6)
    w.move_page(1)
    assert len(_overlays(w)) == 1 and _overlays(w)[0].suggestion["text"] == "Colombi"
    w.chk_sugg.setChecked(False)
    assert _overlays(w) == []


def test_overlay_click_accept_creates_one_redaction(window, monkeypatch):
    w = window
    _two_page_doc(w)
    w.pending_suggestions = [_sugg(w, 0, "Zorzi")]
    w._update_review_button()
    w.render_page()
    _pick(monkeypatch, "Censura")
    _click_scene_point(w, _overlays(w)[0].sceneBoundingRect().center())
    assert len(_redacts(w)) == 1 and w.pending_suggestions == []
    assert w.btn_review.text() == "Rivedi suggerimenti (0)"
    assert _overlays(w) == []


def test_overlay_click_reject_discards_without_annotation(window, monkeypatch):
    w = window
    _two_page_doc(w)
    w.pending_suggestions = [_sugg(w, 0, "Zorzi")]
    w.render_page()
    _pick(monkeypatch, "Scarta")
    _click_scene_point(w, _overlays(w)[0].sceneBoundingRect().center())
    assert _redacts(w) == [] and w.pending_suggestions == []


def test_overlay_cancel_keeps_the_suggestion(window, monkeypatch):
    w = window
    _two_page_doc(w)
    w.pending_suggestions = [_sugg(w, 0, "Zorzi")]
    w.render_page()
    _pick(monkeypatch, "Annulla")
    _click_scene_point(w, _overlays(w)[0].sceneBoundingRect().center())
    assert len(w.pending_suggestions) == 1 and _redacts(w) == []


def test_overlay_never_reaches_the_export(window, tmp_path, monkeypatch):
    w = window
    _two_page_doc(w)
    w.pending_suggestions = [_sugg(w, 0, "Zorzi")]
    w.render_page()
    assert _redacts(w) == []
    pix = w.doc[0].get_pixmap()
    from PySide6.QtWidgets import QMessageBox as QMB

    out = tmp_path / "o.pdf"
    _stub_dialogs(monkeypatch, [str(out)])
    monkeypatch.setattr(w, "_select_privacy_export", lambda: PrivacyMode.ANONYMIZE)
    monkeypatch.setattr(QMB, "exec", lambda self: 0)
    monkeypatch.setattr(QMB, "clickedButton", lambda self: next(
        b for b in self.buttons() if b.text() == "Esporta comunque"))
    w.cmd_export()
    exported = pymupdf.open(str(out))
    assert "Zorzi" in exported[0].get_text()  # not censored: still only a suggestion
    exported.close()
    assert pix.width > 0


def test_review_row_selection_highlights_the_overlay(window):
    w = window
    _two_page_doc(w)
    s = _sugg(w, 0, "Zorzi")
    w.pending_suggestions = [s]
    w.render_page()
    dlg = ReviewDialog(w.pending_suggestions)
    dlg.highlight.connect(w._highlight_suggestion)
    dlg.table.setCurrentCell(0, 2)
    assert _overlays(w)[0].pen().width() == 4


# --- review findings: clip text, mixed glyph heights, 9 pt round trip, recovery -----------

def _tight_doc(w, pitch=9.0):
    w.doc.close()
    d = pymupdf.open()
    pg = d.new_page()
    for i, t in enumerate([
        "Commissione tributaria provinciale",
        "Paziente Alessandro Marchetti nato oggi",
        "Programmazione generale dei servizi",
    ]):
        pg.insert_text((72, 100 + pitch * i), t, fontsize=11)
    w.doc = d
    w.page_num = 0
    w.render_page()


@pytest.mark.parametrize("pitch", [9.0, 10.0, 12.0])
def test_manual_rectangle_stores_only_its_own_line(window, tmp_path, monkeypatch, pitch):
    """A box drawn over a word at tight leading must not capture the neighbours."""
    from PySide6.QtCore import QRectF

    w = window
    _tight_doc(w, pitch)
    idx = app.build_page_index(w.doc[0].get_text("words"), clamp=False)  # raw word box
    x0, y0, x1, y1 = app.whole_word_rects(idx, "Alessandro")[0]
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    w.user_draw_rect(QRectF(x0 * w.scale, y0 * w.scale, (x1 - x0) * w.scale, (y1 - y0) * w.scale))
    annots = _redacts(w)
    assert len(annots) == 1
    assert w._read_redaction_payload(annots[0])["original"] == "Alessandro"
    out, mapf = tmp_path / "m.pdf", tmp_path / "maps" / "m.nullifypdf-map"
    mapf.parent.mkdir()
    _stub_dialogs(monkeypatch, [str(out), str(mapf)])
    monkeypatch.setattr(w, "_select_privacy_export", lambda: PrivacyMode.PSEUDONYMIZE)
    monkeypatch.setattr(w, "_select_pseudonym_style", lambda: ("random", None))
    monkeypatch.setattr(w, "_ask_map_password", lambda: "una frase molto lunga 2026")
    monkeypatch.setattr(w, "_offer_recovery_key", lambda: None)
    w.cmd_export()
    payload = decrypt_restore_payload(mapf.read_bytes(), "una frase molto lunga 2026")
    assert {e["original"] for e in payload["entries"]} == {"Alessandro"}


def test_pseudonymize_round_trip_at_9pt_keeps_neighbours_and_counts(window, tmp_path, monkeypatch):
    w = window
    _tight_doc(w, 9.0)
    w.apply_ai_to_page(0, [
        _detection(w, "Alessandro", "PERSON", "accepted"),
        _detection(w, "Marchetti", "PERSON", "accepted"),
    ])
    out, mapf = tmp_path / "t9.pdf", tmp_path / "maps" / "m.nullifypdf-map"
    mapf.parent.mkdir()
    _stub_dialogs(monkeypatch, [str(out), str(mapf)])
    monkeypatch.setattr(w, "_select_privacy_export", lambda: PrivacyMode.PSEUDONYMIZE)
    monkeypatch.setattr(w, "_select_pseudonym_style", lambda: ("random", None))
    monkeypatch.setattr(w, "_ask_map_password", lambda: "una frase molto lunga 2026")
    monkeypatch.setattr(w, "_offer_recovery_key", lambda: None)
    w.cmd_export()
    pdf = pymupdf.open(str(out))
    text = pdf[0].get_text()
    pdf.close()
    assert "Commissione tributaria provinciale" in text
    assert "Programmazione generale dei servizi" in text
    assert "Alessandro" not in text
    payload = decrypt_restore_payload(mapf.read_bytes(), "una frase molto lunga 2026")
    restored = tmp_path / "r9.pdf"
    n = app.reconstruct_pdf(str(out), str(restored), payload)
    assert n == app.expected_restore_count(payload) == 2
    back = pymupdf.open(str(restored))
    t2 = back[0].get_text()
    back.close()
    assert "Alessandro" in t2 and "Marchetti" in t2
    assert t2.count("Commissione tributaria provinciale") == 1
    assert "Programmazione generale dei servizi" in t2


def test_word_with_a_taller_glyph_falls_back_to_the_full_box(window):
    """A thin band that misses one glyph of the target must not be used."""
    w = window
    w.doc.close()
    d = pymupdf.open()
    pg = d.new_page()
    pg.insert_text((72, 100), "Riga sopra del testo", fontsize=11)
    pg.insert_text((72, 109), "Codice AB", fontsize=11)
    pg.insert_text((72 + 62, 109 - 5), "123", fontsize=6)   # raised, smaller trailing digits
    pg.insert_text((72, 118), "Riga sotto del testo", fontsize=11)
    w.doc = d
    idx = app.build_page_index(d[0].get_text("words"))
    fulls = app.whole_word_rects(idx, "AB")
    band = fitz_rect = pymupdf.Rect(*fulls[0])
    full = pymupdf.Rect(band.x0, band.y0 - 6, band.x1 + 30, band.y1)
    thin = pymupdf.Rect(full.x0, full.y0 + 9, full.x1, full.y0 + 10)  # misses the raised digits
    assert not app.band_covers_target(d[0], thin, full)
    assert app.band_covers_target(d[0], full, full)


def test_recovery_wrap_is_kept_even_if_the_dialog_is_closed_without_ticking(window, monkeypatch):
    w = window
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    raw = w._offer_recovery_key()
    assert isinstance(raw, bytes) and len(raw) == 32
