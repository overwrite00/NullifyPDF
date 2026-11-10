"""Review dialog for AI suggestions (Qt).

Detections the evidence score could not settle are *suggestions*: they are
never applied silently and never lost silently. The user accepts or rejects
each one here; values are masked until the user asks to see them.
"""

from __future__ import annotations

from typing import Any, Dict, List

from help_guide import apply_tooltips
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

REASON_LABELS: Dict[str, str] = {
    "context-cue": "contesto",
    "name-shape": "forma di nome",
    "given-name": "nome proprio noto",
    "known-place": "luogo noto",
    "province-or-postcode": "provincia/CAP",
    "repeated": "ripetuto",
    "lexicon": "parola comune",
    "verb-form": "forma verbale",
    "line-start": "inizio riga",
    "all-caps": "maiuscolo",
    "followed-by-function-word": "seguito da che/di",
    "low-confidence": "bassa confidenza",
    "signature-anchor": "vicino a firma/timbro",
    "overlaps-text": "il riquadro tocca del testo",
    "curve-ink": "tratti a mano",
    "raster-stamp": "timbro/immagine",
    "no-context": "senza contesto",
    "no-anchor": "senza riferimento",
    "postcode": "CAP",
    "known-surname": "cognome noto",
    "ambiguous-place": "luogo omonimo di parola comune",
}

COL_APPLY, COL_PAGE, COL_VALUE, COL_TYPE, COL_SCORE, COL_WHY = range(6)


def mask_value(value: str) -> str:
    v = " ".join(value.split())
    if len(v) <= 1:
        return "•"
    return v[0] + "•" * min(len(v) - 1, 8)


class ReviewDialog(QDialog):
    """Table of suggestions with per-row accept / reject."""

    navigate = Signal(int)
    highlight = Signal(object)  # the suggestion dict of the selected row

    def __init__(self, suggestions: List[Dict[str, Any]], parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Revisione suggerimenti")
        self.resize(760, 460)
        self._items = list(suggestions)
        self._applied: List[Dict[str, Any]] = []
        self._rejected: List[Dict[str, Any]] = []
        lay = QVBoxLayout(self)
        intro = QLabel(
            "Questi elementi non hanno prove sufficienti per essere censurati "
            "automaticamente. Seleziona quelli da censurare: i non selezionati "
            "vengono scartati se premi «Applica selezionati»."
        )
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.table = QTableWidget(len(self._items), 6, self)
        self.table.setObjectName("review_table")
        self.table.verticalHeader().setVisible(False)
        self.table.setHorizontalHeaderLabels(
            ["Censura", "Pag.", "Valore", "Tipo", "Punteggio", "Motivi"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            COL_WHY, QHeaderView.ResizeMode.Stretch
        )
        lay.addWidget(self.table)
        self.chk_show = QCheckBox("Mostra i valori")
        self.chk_show.toggled.connect(self._refresh_values)
        lay.addWidget(self.chk_show)
        for row, it in enumerate(self._items):
            apply_item = QTableWidgetItem()
            apply_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            apply_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, COL_APPLY, apply_item)
            self.table.setItem(row, COL_PAGE, QTableWidgetItem(str(int(it.get("page", 0)) + 1)))
            self.table.setItem(row, COL_VALUE, QTableWidgetItem(""))
            self.table.setItem(row, COL_TYPE, QTableWidgetItem(str(it.get("entity_type", ""))))
            self.table.setItem(row, COL_SCORE, QTableWidgetItem(f"{float(it.get('score', 0.0)):.2f}"))
            why = ", ".join(REASON_LABELS.get(r, r) for r in it.get("reasons", []))
            self.table.setItem(row, COL_WHY, QTableWidgetItem(why))
        self._refresh_values()
        self.table.cellDoubleClicked.connect(self._on_double_click)
        self.table.currentCellChanged.connect(self._on_row_changed)

        bar = QHBoxLayout()
        btn_all = QPushButton("Seleziona tutti")
        btn_none = QPushButton("Nessuno")
        self.spin = QDoubleSpinBox()
        self.spin.setRange(0.0, 1.0)
        self.spin.setSingleStep(0.05)
        self.spin.setValue(0.6)
        self.spin.setObjectName("review_threshold")
        btn_thr = QPushButton("Seleziona ≥ soglia")
        # Bound methods, not lambdas capturing `self`: a lambda makes a
        # reference cycle that keeps the dialog alive until the garbage
        # collector runs, possibly after QApplication is gone.
        btn_all.clicked.connect(self._select_all)
        btn_none.clicked.connect(self._select_none)
        btn_thr.clicked.connect(self._select_threshold)
        for w in (btn_all, btn_none, self.spin, btn_thr):
            bar.addWidget(w)
        bar.addStretch(1)
        lay.addLayout(bar)

        bottom = QHBoxLayout()
        self.btn_apply = QPushButton("Applica selezionati")
        self.btn_apply.setObjectName("Danger")
        self.btn_later = QPushButton("Rivedi più tardi")
        self.btn_apply.clicked.connect(self._on_apply)
        self.btn_later.clicked.connect(self.reject)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_later)
        bottom.addWidget(self.btn_apply)
        lay.addLayout(bottom)
        apply_tooltips(self)

    # -- helpers ---------------------------------------------------------
    def _cell(self, row: int, col: int) -> QTableWidgetItem:
        item = self.table.item(row, col)
        assert item is not None
        return item

    def _refresh_values(self) -> None:
        show = self.chk_show.isChecked()
        for row, it in enumerate(self._items):
            text = " ".join(str(it.get("text", "")).split())
            if not text:
                self._cell(row, COL_VALUE).setText("(area grafica)")
                continue
            self._cell(row, COL_VALUE).setText(text if show else mask_value(text))

    def _select_all(self) -> None:
        self._set_all(True)

    def _select_none(self) -> None:
        self._set_all(False)

    def _set_all(self, state: bool) -> None:
        for row in range(self.table.rowCount()):
            self._cell(row, COL_APPLY).setCheckState(
                Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
            )

    def _select_threshold(self) -> None:
        thr = self.spin.value()
        for row, it in enumerate(self._items):
            if float(it.get("score", 0.0)) >= thr:
                self._cell(row, COL_APPLY).setCheckState(Qt.CheckState.Checked)

    def _on_row_changed(self, row: int, _c: int, _pr: int, _pc: int) -> None:
        if 0 <= row < len(self._items):
            self.highlight.emit(self._items[row])

    def _on_double_click(self, row: int, _col: int) -> None:
        self.navigate.emit(int(self._items[row].get("page", 0)))

    def _on_apply(self) -> None:
        self._applied, self._rejected = [], []
        for row, it in enumerate(self._items):
            checked = self._cell(row, COL_APPLY).checkState() == Qt.CheckState.Checked
            (self._applied if checked else self._rejected).append(it)
        self.accept()

    # -- results ---------------------------------------------------------
    def applied(self) -> List[Dict[str, Any]]:
        return list(self._applied)

    def declined(self) -> List[Dict[str, Any]]:
        return list(self._rejected)
