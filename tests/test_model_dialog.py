import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from model_dialog import ModelDialog
from model_manager import MODEL_CANDIDATES


def test_model_dialog_lists_only_curated_candidates():
    app = QApplication.instance() or QApplication([])
    dialog = ModelDialog(MODEL_CANDIDATES)
    assert dialog.list.count() == len(MODEL_CANDIDATES)
    assert not dialog.btn_download.isEnabled()
    assert dialog.details.toPlainText()
    dialog.close()
    app.processEvents()
