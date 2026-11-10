import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from review_dialog import ReviewDialog

ITEM = [{"text": "Zorzi", "entity_type": "PERSON", "score": 0.5, "page": 0, "reasons": ["lexicon"]}]
KEEP = []


def _app():
    return QApplication.instance() or QApplication([])


def test_e1_text_only():
    _a = _app()
    dlg = ReviewDialog(ITEM)
    dlg.table.item(0, 2).text()


def test_e2_checkstate_only():
    _a = _app()
    dlg = ReviewDialog(ITEM)
    dlg.table.item(0, 0).checkState()


def test_e3_keep_dialog_alive():
    _a = _app()
    dlg = ReviewDialog(ITEM)
    KEEP.append(dlg)
    dlg.table.item(0, 2).text()
    dlg.table.item(0, 0).checkState()


def test_e4_held_item_ref():
    _a = _app()
    dlg = ReviewDialog(ITEM)
    it = dlg.table.item(0, 2)
    it.text()
    del it


def test_e5_cell_helper_twice():
    _a = _app()
    dlg = ReviewDialog(ITEM)
    dlg._cell(0, 2).text()
    dlg._cell(0, 0).checkState()


def test_e6_delete_later():
    a = _app()
    dlg = ReviewDialog(ITEM)
    dlg.table.item(0, 2).text()
    dlg.deleteLater()
    a.processEvents()
