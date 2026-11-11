"""Italian model-catalog dialog; it never downloads without explicit consent."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from help_guide import apply_tooltips
from model_manager import ModelCandidate, ModelManifest, ModelStore


class ModelDownloadWorker(QThread):
    """Download and verify every file of a manifest off the UI thread."""

    progress_sig = Signal(int)  # whole-model percentage
    done_sig = Signal()
    error_sig = Signal(str)
    cancelled_sig = Signal()

    def __init__(self, store: ModelStore, manifest: ModelManifest) -> None:
        super().__init__()
        self._store = store
        self._manifest = manifest
        self._cancel = False
        self._completed = 0
        self._total = max(1, manifest.total_size)

    def cancel(self) -> None:
        self._cancel = True

    def _on_bytes(self, done: int, total: int) -> None:
        if self._cancel:
            raise InterruptedError("download annullato")
        value = int(((self._completed + min(done, total)) / self._total) * 100)
        self.progress_sig.emit(min(100, value))

    def run(self) -> None:
        try:
            for item in self._manifest.files:
                url = (
                    f"https://huggingface.co/{self._manifest.repo_id}/resolve/"
                    f"{self._manifest.revision}/{item.name}?download=true"
                )
                self._store.install_file(
                    self._manifest, item, url, timeout=120.0, progress=self._on_bytes
                )
                self._completed += item.size
                self.progress_sig.emit(min(100, int(self._completed * 100 / self._total)))
            if not self._store.is_installed(self._manifest):
                raise RuntimeError("verifica finale del modello fallita")
            self.done_sig.emit()
        except InterruptedError:
            self.cancelled_sig.emit()
        except Exception as exc:
            self.error_sig.emit(str(exc))


class ModelDialog(QDialog):
    """Show the reviewed model shortlist and its verification state."""

    def __init__(
        self,
        candidates: Iterable[ModelCandidate],
        selected_id: Optional[str] = None,
        manifests: Iterable[ModelManifest] = (),
        store: Optional[ModelStore] = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Modelli locali")
        self.resize(700, 520)
        self._candidates = list(candidates)
        self._selected_id = selected_id
        self._manifests = {m.model_id: m for m in manifests}
        self._store = store
        lay = QVBoxLayout(self)
        intro = QLabel(
            "I modelli vengono eseguiti localmente e producono solo suggerimenti. "
            "Il download sarà consentito soltanto quando revisione, licenza e SHA-256 "
            "saranno fissati nel manifest dell'applicazione."
        )
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.list = QListWidget()
        self.list.setObjectName("model_list")
        for candidate in self._candidates:
            item = QListWidgetItem(
                f"{candidate.title} — {candidate.size_label} — {candidate.status}"
            )
            item.setData(Qt.ItemDataRole.UserRole, candidate.model_id)
            self.list.addItem(item)
        lay.addWidget(self.list)
        self.details = QTextBrowser()
        self.details.setObjectName("model_details")
        lay.addWidget(self.details)
        self.btn_download = QPushButton("Scarica modello")
        self.btn_download.setObjectName("model_download")
        self.btn_download.setEnabled(False)
        self.btn_download.setToolTip(
            "Il download è attivo solo per modelli con revisione, file, licenza e SHA-256 verificati."
        )
        lay.addWidget(self.btn_download)
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._buttons.rejected.connect(self.reject)
        lay.addWidget(self._buttons)
        self._worker: Optional[ModelDownloadWorker] = None
        self.list.currentItemChanged.connect(self._show_details)
        self.btn_download.clicked.connect(self._download_selected)
        if self.list.count():
            row = 0
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.ItemDataRole.UserRole) == selected_id:
                    row = i
                    break
            self.list.setCurrentRow(row)
        apply_tooltips(self)

    def _show_details(self, current: Optional[QListWidgetItem], _previous: Any) -> None:
        if current is None:
            self.details.clear()
            return
        model_id = current.data(Qt.ItemDataRole.UserRole)
        candidate = next((c for c in self._candidates if c.model_id == model_id), None)
        if candidate is None:
            return
        self.details.setPlainText(
            f"Nome: {candidate.title}\n"
            f"Repository: {candidate.repo_id}\n"
            f"Licenza: {candidate.license}\n"
            f"Runtime: {candidate.runtime}\n"
            f"Lingue: {', '.join(candidate.languages)}\n"
            f"Copertura dichiarata: {candidate.scope}\n"
            f"Stato: {candidate.status}\n\n"
            f"{candidate.notes}"
        )
        manifest = self._manifests.get(candidate.model_id)
        if manifest is not None:
            self.details.append(
                f"\n\nFonte fissata: {manifest.source_url}\n"
                f"File manifest: {len(manifest.files)}; SHA-256 verificati localmente."
            )
        self.btn_download.setEnabled(manifest is not None and self._store is not None)
        if manifest is not None and self._store is not None and self._store.is_installed(manifest):
            self.btn_download.setText("Modello già installato")
            self.btn_download.setEnabled(False)
        else:
            self.btn_download.setText("Scarica modello")
            if manifest is None:
                self.btn_download.setToolTip(
                    "Modello sperimentale non scaricabile: manca un manifest verificato "
                    "con revisione, licenza, dimensioni e SHA-256."
                )
            else:
                self.btn_download.setToolTip(
                    "Download HTTPS da Hugging Face alla revisione fissata nel manifest."
                )

    # -- download with progress shown inside the button -------------------
    def _set_button_progress(self, percent: int) -> None:
        """Fill the button from the left like a progress bar and show the %."""
        p = min(max(percent, 0), 100) / 100.0
        edge = min(p, 0.998)
        self.btn_download.setText(f"Download in corso… {percent}%  (clic per annullare)")
        self.btn_download.setStyleSheet(
            "QPushButton#model_download { background: qlineargradient("
            "x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 #0284c7, stop:{edge:.3f} #0284c7, "
            f"stop:{edge + 0.001:.3f} #334155, stop:1 #334155); }}"
        )

    def _set_downloading(self, on: bool) -> None:
        self.list.setEnabled(not on)
        close = self._buttons.button(QDialogButtonBox.StandardButton.Close)
        if close is not None:
            close.setEnabled(not on)
        if not on:
            self.btn_download.setStyleSheet("")

    def is_downloading(self) -> bool:
        return self._worker is not None

    def reject(self) -> None:
        if self._worker is None:
            super().reject()

    def closeEvent(self, event: Any) -> None:
        if self._worker is not None:
            event.ignore()
        else:
            super().closeEvent(event)

    def _download_selected(self) -> None:
        if self._worker is not None:  # second click while downloading: cancel
            self._worker.cancel()
            self.btn_download.setText("Annullamento…")
            self.btn_download.setEnabled(False)
            return
        current = self.list.currentItem()
        if current is None or self._store is None:
            return
        model_id = current.data(Qt.ItemDataRole.UserRole)
        manifest = self._manifests.get(model_id)
        if manifest is None:
            return
        answer = QMessageBox.question(
            self,
            "Consenso al download",
            f"Scaricare {manifest.model_id} ({manifest.total_size / 1024**2:.1f} MB)?\n"
            f"Licenza: {manifest.license}\n"
            f"Revisione: {manifest.revision}\n\n"
            "I file saranno salvati nella cartella locale dell'applicazione.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._set_downloading(True)
        self._set_button_progress(0)
        worker = ModelDownloadWorker(self._store, manifest)
        # Bound methods, not lambdas capturing self (no reference cycle).
        worker.progress_sig.connect(self._set_button_progress)
        worker.done_sig.connect(self._on_download_done)
        worker.error_sig.connect(self._on_download_error)
        worker.cancelled_sig.connect(self._on_download_cancelled)
        self._worker = worker
        worker.start()

    def _finish_worker(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.wait()
        self.btn_download.setEnabled(True)
        self._set_downloading(False)

    def _on_download_done(self) -> None:
        self._finish_worker()
        QMessageBox.information(self, "Download completato", "Il modello è stato verificato e installato.")
        self._show_details(self.list.currentItem(), None)

    def _on_download_error(self, message: str) -> None:
        self._finish_worker()
        self._show_details(self.list.currentItem(), None)
        QMessageBox.critical(self, "Download non riuscito", message)

    def _on_download_cancelled(self) -> None:
        self._finish_worker()
        self._show_details(self.list.currentItem(), None)
