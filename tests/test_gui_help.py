"""Guide and tooltips: every GUI element is explained, and the guide matches the UI."""

import os
import re

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton, QApplication, QCheckBox, QDialog, QPushButton, QRadioButton,
)

import NullifyPDF as app  # noqa: E402
from help_guide import (  # noqa: E402
    ENTITY_TOOLTIPS, GUIDE_TOPICS, TOOLTIPS, GuideDialog, apply_tooltips,
    widgets_without_tooltip,
)
from pii_detection import ENTITY_GROUPS  # noqa: E402
from review_dialog import ReviewDialog  # noqa: E402


@pytest.fixture()
def window(tmp_path, monkeypatch):
    import atexit
    import gc

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    qapp = QApplication.instance() or QApplication([])
    w = app.NullifyPDF()
    yield w
    try:
        w._cleanup_resources()
    except Exception:
        pass
    atexit.unregister(w._cleanup_on_exit)
    w.deleteLater()
    qapp.processEvents()
    gc.collect()


def _plain(html):
    return re.sub(r"<[^>]+>", " ", html)


def test_every_widget_of_the_main_window_has_a_tooltip(window):
    assert widgets_without_tooltip(window) == []


def test_buttons_have_tooltips_too(window):
    buttons = [b for b in window.findChildren(QAbstractButton)]
    assert len(buttons) >= 15
    assert all(b.toolTip().strip() for b in buttons), [b.text() for b in buttons if not b.toolTip()]


def test_tooltips_are_in_italian_and_not_empty():
    for key, tip in {**TOOLTIPS, **ENTITY_TOOLTIPS}.items():
        assert len(tip) > 10 and tip[0].isupper(), key


def test_every_entity_checkbox_has_a_tooltip():
    labels = {label for _gid, label, _t in ENTITY_GROUPS}
    assert labels <= set(ENTITY_TOOLTIPS), labels - set(ENTITY_TOOLTIPS)


def test_entity_dialog_has_tooltips(window, monkeypatch):
    seen = {}

    def fake_exec(self):
        seen["missing"] = widgets_without_tooltip(self)
        seen["boxes"] = [c.toolTip() for c in self.findChildren(QCheckBox)]
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", fake_exec)
    window._select_ai_entities()
    assert seen["missing"] == [] and all(seen["boxes"])


def test_review_and_dictionary_dialogs_have_tooltips(window):
    from dictionary_dialog import DictionaryDialog

    items = [{"text": "Zorzi", "entity_type": "PERSON", "score": 0.5, "page": 0, "reasons": []}]
    assert widgets_without_tooltip(ReviewDialog(items)) == []
    assert widgets_without_tooltip(DictionaryDialog(window.list_manager)) == []


def test_about_dialog_has_tooltips(window, monkeypatch):
    seen = {}

    def fake_exec(self):
        seen["missing"] = widgets_without_tooltip(self)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", fake_exec)
    window.cmd_about()
    assert seen["missing"] == []


def test_guide_dialog_lists_every_topic_and_has_tooltips(window):
    g = GuideDialog(window)
    assert g.topics.count() == len(GUIDE_TOPICS) >= 10
    assert widgets_without_tooltip(g) == []
    # No hover popups on the topic list and the text: they get in the way of reading.
    assert g.topics.toolTip() == "" and g.text.toolTip() == ""
    assert g.topics.viewport().toolTip() == "" and g.text.viewport().toolTip() == ""
    for row in range(g.topics.count()):
        g.topics.setCurrentRow(row)
        assert len(g.text.toPlainText()) > 80


def test_f1_and_the_guide_button_open_the_guide(window, monkeypatch):
    opened = []
    monkeypatch.setattr(GuideDialog, "exec", lambda self: opened.append(self.topics.count()) or 0)
    window._f1.activated.emit()
    btn = next(b for b in window.findChildren(QPushButton) if b.text() == "Guida")
    btn.click()
    assert len(opened) == 2


def test_the_guide_describes_every_control_of_the_sidebar(window):
    text = _plain(" ".join(html for _t, html in GUIDE_TOPICS))
    for w in window.findChildren(QAbstractButton):
        label = w.text().strip()
        if not label or label in {"-", "+", "<", ">", "Esci"} or label.startswith("Rivedi suggerimenti"):
            continue
        assert label in text, f"the guide never mentions «{label}»"
    assert "Rivedi suggerimenti" in text and "F1" in text
    for rb in window.findChildren(QRadioButton):
        assert rb.text() in text


def test_the_guide_matches_what_the_program_really_does():
    text = _plain(" ".join(html for _t, html in GUIDE_TOPICS))
    for fact in ("scadenza", "chiave di recupero", "mappa di ripristino",
                 "Ctrl + rotella", "Revisione", "OCR", "pseudonim"):
        assert fact.lower() in text.lower(), fact
    assert "Wikidata" not in text and "AI" not in text.split()  # no internals / no AI wording
