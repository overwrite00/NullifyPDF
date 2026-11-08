"""Dictionary (blocklist / allowlist) editor with per-entry expiry (Qt)."""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from word_lists import ListEntry, PDFListManager, MIN_TERM_LENGTH

TTL_CHOICES = [("Mai", None), ("30 giorni", 30), ("90 giorni", 90),
               ("180 giorni", 180), ("1 anno", 365)]
COL_TERM, COL_ADDED, COL_EXPIRES = range(3)
KINDS = (("blocklist", "🔴 Blocklist"), ("allowlist", "🟢 Allowlist"))


def parse_date(text: str) -> Optional[datetime.date]:
    text = text.strip()
    if not text or text.lower() in ("mai", "never"):
        return None
    return datetime.date.fromisoformat(text)


class DictionaryDialog(QDialog):
    """Edit both lists; `saved_blocklist` / `saved_allowlist` hold the result."""

    def __init__(self, manager: PDFListManager, parent: Any = None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Dizionari")
        self.resize(620, 520)
        self.saved_blocklist: Optional[set] = None
        self.saved_allowlist: Optional[set] = None
        lay = QVBoxLayout(self)
        self.status = QLabel(manager.protector_label())
        lay.addWidget(self.status)
        if manager.keystore_error:
            warn = QLabel(
                "Dizionari cifrati non leggibili su questo account/PC: verranno "
                "usati dizionari vuoti finché non li ripristini."
            )
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #f59e0b;")
            lay.addWidget(warn)
        self.tabs = QTabWidget()
        self.tables: Dict[str, QTableWidget] = {}
        for kind, title in KINDS:
            tab = QWidget()
            tl = QVBoxLayout(tab)
            table = QTableWidget(0, 3)
            table.setHorizontalHeaderLabels(["Termine", "Aggiunto il", "Scade il (AAAA-MM-GG)"])
            table.horizontalHeader().setStretchLastSection(True)
            table.setColumnWidth(COL_TERM, 260)
            self.tables[kind] = table
            tl.addWidget(table)
            row = QHBoxLayout()
            for label, slot in (
                ("Aggiungi", lambda _=False, k=kind: self.add_row(k)),
                ("Rimuovi", lambda _=False, k=kind: self.remove_selected(k)),
                ("Importa da testo…", lambda _=False, k=kind: self.import_text(k)),
                ("Esporta in chiaro…", lambda _=False, k=kind: self.export_plain(k)),
            ):
                b = QPushButton(label)
                b.clicked.connect(slot)
                row.addWidget(b)
            tl.addLayout(row)
            self.tabs.addTab(tab, title)
            for e in manager.load_entries(kind):
                self._append(kind, e)
        lay.addWidget(self.tabs)
        ttl_row = QHBoxLayout()
        ttl_row.addWidget(QLabel("Scadenza predefinita dei nuovi termini:"))
        self.ttl = QComboBox()
        current = manager.default_ttl_days()
        for i, (label, days) in enumerate(TTL_CHOICES):
            self.ttl.addItem(label, days)
            if days == current:
                self.ttl.setCurrentIndex(i)
        ttl_row.addWidget(self.ttl)
        ttl_row.addStretch(1)
        lay.addLayout(ttl_row)
        btn = QPushButton("Salva")
        btn.setObjectName("Primary")
        btn.clicked.connect(self.save)
        lay.addWidget(btn)

    # -- rows ---------------------------------------------------------
    def _append(self, kind: str, entry: ListEntry) -> None:
        t = self.tables[kind]
        r = t.rowCount()
        t.insertRow(r)
        t.setItem(r, COL_TERM, QTableWidgetItem(entry.term))
        added = QTableWidgetItem(entry.added.isoformat())
        added.setFlags(added.flags() & ~Qt.ItemFlag.ItemIsEditable)
        t.setItem(r, COL_ADDED, added)
        t.setItem(r, COL_EXPIRES, QTableWidgetItem(entry.expires.isoformat() if entry.expires else "Mai"))

    def add_term(self, kind: str, term: str) -> None:
        days = self.ttl.currentData()
        today = datetime.date.today()
        exp = today + datetime.timedelta(days=days) if days else None
        self._append(kind, ListEntry(term.strip().lower(), today, exp))

    def add_row(self, kind: str) -> None:
        text, ok = QInputDialog.getText(self, "Aggiungi termine", "Termine:")
        if ok and len(text.strip()) >= MIN_TERM_LENGTH:
            self.add_term(kind, text)

    def remove_selected(self, kind: str) -> None:
        t = self.tables[kind]
        for r in sorted({i.row() for i in t.selectedIndexes()}, reverse=True):
            t.removeRow(r)

    def import_text(self, kind: str) -> None:
        text, ok = QInputDialog.getMultiLineText(
            self, "Importa da testo", "Un termine per riga:"
        )
        if ok:
            for line in text.splitlines():
                if len(line.strip()) >= MIN_TERM_LENGTH:
                    self.add_term(kind, line)

    def export_plain(self, kind: str) -> None:
        ans = QMessageBox.warning(
            self, "Esporta in chiaro",
            "Il file esportato contiene dati personali in chiaro. Continuare?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Esporta", f"{kind}.txt", "Testo (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(e.term for e in self.entries(kind)))

    # -- result -------------------------------------------------------
    def entries(self, kind: str) -> List[ListEntry]:
        out: List[ListEntry] = []
        t = self.tables[kind]
        def cell(r: int, c: int) -> str:
            item = t.item(r, c)
            return item.text() if item is not None else ""

        for r in range(t.rowCount()):
            term = cell(r, COL_TERM).strip().lower()
            if len(term) < MIN_TERM_LENGTH:
                continue
            try:
                added = parse_date(cell(r, COL_ADDED)) or datetime.date.today()
                expires = parse_date(cell(r, COL_EXPIRES))
            except ValueError:
                raise ValueError(f"Data non valida per «{term}»: usa AAAA-MM-GG oppure «Mai».")
            out.append(ListEntry(term, added, expires))
        return out

    def save(self) -> None:
        try:
            block, allow = self.entries("blocklist"), self.entries("allowlist")
        except ValueError as e:
            QMessageBox.warning(self, "Data non valida", str(e))
            return
        self.manager.set_default_ttl_days(self.ttl.currentData())
        self.manager.save_entries("blocklist", block)
        self.manager.save_entries("allowlist", allow)
        self.saved_blocklist = {e.term for e in block}
        self.saved_allowlist = {e.term for e in allow}
        self.accept()
