import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from review_dialog import ReviewDialog

ITEM = [{"text": "Zorzi", "entity_type": "PERSON", "score": 0.5, "page": 0, "reasons": ["lexicon"]}]


def _app():
    return QApplication.instance() or QApplication([])


def test_a_construct_only():
    _a = _app()
    ReviewDialog(ITEM)


def test_b_show_and_threshold():
    _a = _app()
    dlg = ReviewDialog(ITEM)
    dlg.chk_show.setChecked(True)
    dlg.spin.setValue(0.4)
    dlg._select_threshold()


def test_c_navigate_connect():
    _a = _app()
    dlg = ReviewDialog(ITEM)
    got = []
    dlg.navigate.connect(got.append)
    dlg._on_double_click(0, 0)


def test_d_navigate_lambda():
    _a = _app()
    dlg = ReviewDialog(ITEM)
    got = []
    dlg.navigate.connect(lambda p: got.append(p))
    dlg._on_double_click(0, 0)


def test_e_item_access():
    _a = _app()
    dlg = ReviewDialog(ITEM)
    dlg.table.item(0, 2).text()
    dlg.table.item(0, 0).checkState()
