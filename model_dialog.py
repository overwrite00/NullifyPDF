"""Italian model-catalog dialog; it never downloads without explicit consent."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QTextBrowser,
    QVBoxLayout,
)

from help_guide import apply_tooltips
from model_manager import ModelCandidate, ModelManifest, ModelStore


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
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
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

    def _download_selected(self) -> None:
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
        progress = QProgressDialog("Download modello...", "", 0, 100, self)
        progress.setWindowTitle("Download modello")
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()
        total_size = max(1, manifest.total_size)
        completed = 0

        def on_progress(done: int, total: int) -> None:
            value = int(((completed + min(done, total)) / total_size) * 100)
            progress.setValue(min(100, value))
            QApplication.processEvents()

        try:
            for item in manifest.files:
                url = (
                    f"https://huggingface.co/{manifest.repo_id}/resolve/"
                    f"{manifest.revision}/{item.name}?download=true"
                )
                self._store.install_file(
                    manifest, item, url, timeout=120.0, progress=on_progress
                )
                completed += item.size
                progress.setValue(min(100, int(completed * 100 / total_size)))
                QApplication.processEvents()
            if not self._store.is_installed(manifest):
                raise RuntimeError("verifica finale del modello fallita")
        except Exception as exc:
            progress.close()
            QMessageBox.critical(self, "Download non riuscito", str(exc))
            return
        progress.setValue(100)
        progress.close()
        QMessageBox.information(self, "Download completato", "Il modello è stato verificato e installato.")
        self._show_details(current, None)

