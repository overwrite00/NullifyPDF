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


# --- download progress lives inside the button --------------------------------

import time  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402

from model_manager import ModelFile, ModelManifest  # noqa: E402


def _manifest():
    return ModelManifest(
        model_id="fake-model", repo_id="owner/fake", revision="a" * 40, license="MIT",
        runtime="onnx", labels=("PER",),
        files=(ModelFile("model.onnx", 1000, "b" * 64),),
    )


class FakeStore:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.installed = False

    def is_installed(self, manifest):
        return self.installed

    def install_file(self, manifest, item, url, *, timeout=30.0, progress=None):
        self.behaviour(self, progress, item)


def _dialog(store, qapp):
    manifest = _manifest()
    dlg = ModelDialog(MODEL_CANDIDATES, manifests=[manifest], store=store)
    dlg._manifests = {c.model_id: manifest for c in MODEL_CANDIDATES}
    dlg.list.setCurrentRow(0)
    dlg.btn_download.setEnabled(True)
    return dlg


def _wait(qapp, cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end and not cond():
        qapp.processEvents()
        time.sleep(0.01)
    return cond()


@pytest.fixture()
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def boxes(monkeypatch):
    seen = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: seen.append("info"))
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: seen.append(("error", a[2])))
    return seen


def test_download_progress_is_in_the_button_and_ui_is_locked(qapp, boxes):
    gate = {"go": False}

    def slow(store, progress, item):
        progress(500, item.size)
        while not gate["go"]:
            time.sleep(0.01)
        progress(1000, item.size)
        store.installed = True

    dlg = _dialog(FakeStore(slow), qapp)
    dlg.btn_download.click()
    assert dlg.is_downloading()
    assert _wait(qapp, lambda: "50%" in dlg.btn_download.text())
    assert "qlineargradient" in dlg.btn_download.styleSheet()
    assert not dlg.list.isEnabled()
    dlg.reject()  # closing is refused while downloading
    assert dlg.is_downloading()
    gate["go"] = True
    assert _wait(qapp, lambda: not dlg.is_downloading())
    assert boxes == ["info"] and dlg.list.isEnabled() and dlg.btn_download.styleSheet() == ""
    dlg.close()


def test_second_click_cancels_and_restores_button(qapp, boxes):
    def endless(store, progress, item):
        while True:
            progress(1, item.size)  # raises InterruptedError once cancelled
            time.sleep(0.01)

    dlg = _dialog(FakeStore(endless), qapp)
    dlg.btn_download.click()
    assert _wait(qapp, lambda: dlg.is_downloading() and dlg.btn_download.text().startswith("Download"))
    dlg.btn_download.click()
    assert _wait(qapp, lambda: not dlg.is_downloading())
    assert boxes == []  # cancelling is silent
    assert dlg.btn_download.isEnabled() and dlg.list.isEnabled()
    assert dlg.btn_download.text() == "Scarica modello"
    dlg.close()


def test_failed_download_reports_error_and_unlocks(qapp, boxes):
    def broken(store, progress, item):
        raise RuntimeError("hash non corrispondente")

    dlg = _dialog(FakeStore(broken), qapp)
    dlg.btn_download.click()
    assert _wait(qapp, lambda: not dlg.is_downloading())
    assert boxes and boxes[0][0] == "error" and "hash" in boxes[0][1]
    assert dlg.list.isEnabled() and dlg.btn_download.styleSheet() == ""
    dlg.close()
