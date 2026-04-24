import os
import sys
import re
import datetime
import pathlib
import string
import platform
import fitz
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QCheckBox,
    QProgressBar,
    QTextEdit,
    QGraphicsView,
    QGraphicsScene,
    QFileDialog,
    QDialog,
    QLineEdit,
    QButtonGroup,
    QGraphicsRectItem,
    QMessageBox,
)
from PySide6.QtGui import (
    QIcon,
    QPixmap,
    QImage,
    QPainter,
    QColor,
    QPen,
    QDragEnterEvent,
    QDropEvent,
)
from PySide6.QtCore import Qt, QThread, QObject, Signal, Slot, QRectF, QPointF

__version__ = "2.0.5"


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


STYLESHEET = """
QMainWindow, QDialog { background-color: #0f172a; }
QWidget { color: #cbd5e1; font-family: 'Segoe UI', 'Roboto', sans-serif; font-size: 13px; }
QFrame#Sidebar, QFrame#Panel { background-color: #1e293b; border-radius: 6px; }
QPushButton { background-color: #334155; border: 1px solid #475569; border-radius: 4px; padding: 8px; color: #e2e8f0; font-weight: bold; }
QPushButton:hover { background-color: #475569; border-color: #0ea5e9; }
QPushButton#Primary { background-color: #0284c7; color: white; border: none; }
QPushButton#Primary:hover { background-color: #0369a1; }
QPushButton#Danger { background-color: #dc2626; color: white; border: none; }
QPushButton#Danger:hover { background-color: #b91c1c; }
QPushButton#Exit { background-color: transparent; border: none; color: #64748b; font-weight: normal; }
QPushButton#Exit:hover { color: #ef4444; background-color: #1e293b; }
QTextEdit { background-color: #0f172a; border: 1px solid #334155; border-radius: 4px; padding: 4px; color: #94a3b8; font-family: 'Consolas', monospace; }
QLineEdit { background-color: #0f172a; border: 1px solid #334155; border-radius: 4px; padding: 4px; color: #e2e8f0; }
QLineEdit:focus { border: 1px solid #0ea5e9; }
QProgressBar { background-color: #0f172a; border: 1px solid #334155; border-radius: 4px; text-align: center; color: transparent; height: 8px;}
QProgressBar::chunk { background-color: #0ea5e9; border-radius: 3px; }
QGraphicsView { border: none; background-color: #020617; }
QRadioButton::indicator, QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #475569; border-radius: 8px; background-color: #0f172a; }
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator:checked, QCheckBox::indicator:checked { background-color: #0ea5e9; border: 1px solid #0ea5e9; }
"""


class AIWorker(QObject):
    log_sig = Signal(str)
    progress_sig = Signal(int, int)
    page_done_sig = Signal(int, set)
    finished_sig = Signal()

    def __init__(self):
        super().__init__()
        self.analyzer = None
        self.loaded_langs = []

    @Slot(list, str, list)
    def run_scan(self, pages_text, choice, compiled_allowlist):
        try:
            target_langs = ["en", "it"] if choice == "BOTH" else [choice.lower()]
            if not self.analyzer or sorted(self.loaded_langs) != sorted(target_langs):
                self.log_sig.emit(f"Inizializzazione AI ({choice})...")
                from presidio_analyzer import AnalyzerEngine
                from presidio_analyzer.nlp_engine import NlpEngineProvider

                models = (
                    [{"lang_code": "en", "model_name": "en_core_web_md"}]
                    if "en" in target_langs
                    else []
                )
                if "it" in target_langs:
                    models.append({"lang_code": "it", "model_name": "it_core_news_md"})
                provider = NlpEngineProvider(
                    nlp_configuration={"nlp_engine_name": "spacy", "models": models}
                )
                self.analyzer = AnalyzerEngine(
                    nlp_engine=provider.create_engine(),
                    supported_languages=target_langs,
                )
                self.loaded_langs = target_langs
            self.log_sig.emit("Scansione forense in corso...")
            targets = [
                "PERSON",
                "LOCATION",
                "EMAIL_ADDRESS",
                "PHONE_NUMBER",
                "IBAN_CODE",
                "CREDIT_CARD",
                "CRYPTO",
            ]
            for i, text in enumerate(pages_text):
                found = set()
                for lang in self.loaded_langs:
                    res = self.analyzer.analyze(
                        text=text, entities=targets, language=lang
                    )
                    for r in res:
                        w = text[r.start : r.end].strip()
                        if len(w) > 2:
                            found.add(w)
                final_words = set()
                for m in found:
                    clean = " ".join(m.strip(string.punctuation).lower().split())
                    if not any(
                        f_reg.search(clean)
                        or re.search(r"\b" + re.escape(clean) + r"\b", a_str)
                        for a_str, f_reg in compiled_allowlist
                    ):
                        final_words.add(m)
                self.page_done_sig.emit(i, final_words)
                self.progress_sig.emit(i + 1, len(pages_text))
            self.log_sig.emit("Anonimizzazione completata.")
        except Exception as e:
            self.log_sig.emit(f"ERRORE AI: {str(e)}")
        finally:
            self.finished_sig.emit()


class PDFView(QGraphicsView):
    rect_drawn = Signal(QRectF)
    point_clicked = Signal(QPointF)
    zoom_req = Signal(int)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.start_pos = None
        self.temp_rect = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            sp = self.mapToScene(event.pos())
            self.start_pos = sp
            self.point_clicked.emit(sp)
            self.temp_rect = QGraphicsRectItem(QRectF(sp, sp))
            self.temp_rect.setPen(QPen(QColor("#ef4444"), 2))
            self.scene().addItem(self.temp_rect)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.start_pos and self.temp_rect:
            ep = self.mapToScene(event.pos())
            self.temp_rect.setRect(QRectF(self.start_pos, ep).normalized())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.temp_rect:
            rect = self.temp_rect.rect()
            self.scene().removeItem(self.temp_rect)
            self.temp_rect = None
            self.start_pos = None
            if rect.width() > 5 and rect.height() > 5:
                self.rect_drawn.emit(rect)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            self.zoom_req.emit(1 if event.angleDelta().y() > 0 else -1)
            event.accept()
        else:
            super().wheelEvent(event)


class NullifyPDF(QMainWindow):
    start_scan_sig = Signal(list, str, list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("NullifyPDF - AI Forensic Edition")
        self.resize(1350, 950)
        self.setStyleSheet(STYLESHEET)
        self.setAcceptDrops(True)
        ip = resource_path(os.path.join("images", "NullifyPDF_icon.png"))
        if os.path.exists(ip):
            self.setWindowIcon(QIcon(ip))
        self.doc = None
        self.page_num = 0
        self.scale = 1.5
        self.config_dir = pathlib.Path.home() / ".nullifypdf"
        self.config_dir.mkdir(exist_ok=True)
        self.block_file = self.config_dir / "blocklist.txt"
        self.allow_file = self.config_dir / "allowlist.txt"
        self.blocklist = self.load_list(self.block_file)
        self.allowlist = self.load_list(self.allow_file)
        self.ai_thread = QThread()
        self.ai_worker = AIWorker()
        self.ai_worker.moveToThread(self.ai_thread)
        self.ai_worker.log_sig.connect(self.write_log)
        self.ai_worker.progress_sig.connect(self.update_progress)
        self.ai_worker.page_done_sig.connect(self.apply_ai_to_page)
        self.ai_worker.finished_sig.connect(self.ai_finished)
        self.start_scan_sig.connect(self.ai_worker.run_scan)
        self.ai_thread.start()
        self.build_ui()
        if len(sys.argv) > 1:
            self.load_path(sys.argv[1])

    def closeEvent(self, event):
        self.ai_thread.quit()
        self.ai_thread.wait()
        super().closeEvent(event)

    def load_list(self, p):
        return (
            {l.strip().lower() for l in open(p, "r", encoding="utf-8")}
            if p.exists()
            else set()
        )

    def save_list(self, p, d):
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(d)))

    def build_ui(self):
        c_widget = QWidget()
        self.setCentralWidget(c_widget)
        main_lay = QHBoxLayout(c_widget)
        main_lay.setContentsMargins(10, 10, 10, 10)
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(280)
        s_lay = QVBoxLayout(sidebar)
        lbl_title = QLabel("NullifyPDF")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #0ea5e9;")
        s_lay.addWidget(lbl_title)
        s_lay.addWidget(QLabel("AI Forensic Edition\n"))
        btn_open = QPushButton("Apri PDF")
        btn_open.setObjectName("Primary")
        btn_open.clicked.connect(self.cmd_open)
        s_lay.addWidget(btn_open)
        s_lay.addSpacing(20)
        s_lay.addWidget(QLabel("Modello Lingua AI:"))
        lang_lay = QHBoxLayout()
        self.rb_en = QRadioButton("EN")
        self.rb_it = QRadioButton("IT")
        self.rb_both = QRadioButton("BOTH")
        self.rb_en.setChecked(True)
        self.lang_grp = QButtonGroup(self)
        [
            (self.lang_grp.addButton(rb), lang_lay.addWidget(rb))
            for rb in (self.rb_en, self.rb_it, self.rb_both)
        ]
        s_lay.addLayout(lang_lay)
        s_lay.addSpacing(10)
        self.chk_img = QCheckBox("Oscura Immagini")
        s_lay.addWidget(self.chk_img)
        s_lay.addSpacing(20)
        btn_dict = QPushButton("Dizionari")
        btn_dict.clicked.connect(self.cmd_dict)
        s_lay.addWidget(btn_dict)
        self.btn_ai = QPushButton("Auto Redact (AI)")
        self.btn_ai.setObjectName("Danger")
        self.btn_ai.clicked.connect(self.cmd_auto_ai)
        s_lay.addWidget(self.btn_ai)
        btn_clear = QPushButton("Pulisci Pagina")
        btn_clear.clicked.connect(self.cmd_clear)
        s_lay.addWidget(btn_clear)
        s_lay.addSpacing(20)
        btn_export = QPushButton("Esporta PDF Sicuro")
        btn_export.setStyleSheet("border-color: #0ea5e9; color: #0ea5e9;")
        btn_export.clicked.connect(self.cmd_export)
        s_lay.addWidget(btn_export)
        s_lay.addStretch()
        btn_about = QPushButton("Info")
        btn_about.clicked.connect(self.cmd_about)
        s_lay.addWidget(btn_about)
        btn_exit = QPushButton("Esci")
        btn_exit.setObjectName("Exit")
        btn_exit.clicked.connect(self.close)
        s_lay.addWidget(btn_exit)
        main_lay.addWidget(sidebar)
        right_panel = QWidget()
        r_lay = QVBoxLayout(right_panel)
        top_bar = QWidget()
        top_bar.setObjectName("Panel")
        tb_lay = QHBoxLayout(top_bar)
        tb_lay.addWidget(QLabel("<b>Visualizzatore Documento</b>"))
        tb_lay.addStretch()
        btn_zout = QPushButton("-")
        btn_zout.clicked.connect(lambda: self.adjust_zoom(-1))
        self.lbl_zoom = QLabel("150%")
        btn_zin = QPushButton("+")
        btn_zin.clicked.connect(lambda: self.adjust_zoom(1))
        tb_lay.addWidget(btn_zout)
        tb_lay.addWidget(self.lbl_zoom)
        tb_lay.addWidget(btn_zin)
        tb_lay.addSpacing(20)
        btn_prev = QPushButton("<")
        btn_prev.clicked.connect(lambda: self.move_page(-1))
        self.le_page = QLineEdit("0")
        self.le_page.setFixedWidth(40)
        self.le_page.setAlignment(Qt.AlignCenter)
        self.le_page.returnPressed.connect(self.jump_page)
        self.lbl_tot = QLabel("/ 0")
        btn_next = QPushButton(">")
        btn_next.clicked.connect(lambda: self.move_page(1))
        tb_lay.addWidget(btn_prev)
        tb_lay.addWidget(self.le_page)
        tb_lay.addWidget(self.lbl_tot)
        tb_lay.addWidget(btn_next)
        r_lay.addWidget(top_bar)
        self.scene = QGraphicsScene()
        self.view = PDFView(self.scene)
        self.view.rect_drawn.connect(self.user_draw_rect)
        self.view.point_clicked.connect(self.user_click_pt)
        self.view.zoom_req.connect(self.adjust_zoom)
        r_lay.addWidget(self.view, stretch=1)
        footer = QWidget()
        footer.setObjectName("Panel")
        f_lay = QVBoxLayout(footer)
        self.prog = QProgressBar()
        self.prog.setValue(0)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(80)
        f_lay.addWidget(self.prog)
        f_lay.addWidget(self.log)
        r_lay.addWidget(footer)
        main_lay.addWidget(right_panel, stretch=1)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.load_path(urls[0].toLocalFile())

    def write_log(self, m):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        color = (
            "#ef4444"
            if "ERRORE" in m
            else (
                "#f59e0b"
                if "Avviso" in m
                else "#10b981" if "successo" in m or "completata" in m else "#94a3b8"
            )
        )
        self.log.append(f"<span style='color: {color};'>[{t}] {m}</span>")

    def update_progress(self, c, t):
        self.prog.setValue(int((c / t) * 100))

    def cmd_open(self):
        p, _ = QFileDialog.getOpenFileName(self, "Apri PDF", "", "PDF (*.pdf)")
        if p:
            self.load_path(p)

    def load_path(self, path):
        try:
            if self.doc:
                self.doc.close()
            tdoc = fitz.open(path)
            if tdoc.needs_pass:
                self.write_log("ERRORE: PDF cifrato.")
                tdoc.close()
                return
            self.doc = tdoc
            self.page_num = 0
            self.scale = 1.5
            self.adjust_zoom(0)
            self.write_log(f"Caricato: {os.path.basename(path)}")
        except Exception as e:
            self.write_log(f"ERRORE: {e}")

    def render(self):
        if not self.doc:
            return
        page = self.doc[self.page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(self.scale, self.scale), annots=True)
        img = QImage(
            pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888
        )
        self.scene.clear()
        self.scene.addPixmap(QPixmap.fromImage(img))
        self.scene.setSceneRect(0, 0, pix.width, pix.height)
        self.le_page.setText(str(self.page_num + 1))
        self.lbl_tot.setText(f"/ {len(self.doc)}")

    def adjust_zoom(self, d):
        self.scale = max(0.5, min(4.0, self.scale + (0.25 * d)))
        self.lbl_zoom.setText(f"{int(self.scale * 100)}%")
        self.render()

    def move_page(self, d):
        if self.doc and 0 <= self.page_num + d < len(self.doc):
            self.page_num += d
            self.render()

    def jump_page(self):
        try:
            n = int(self.le_page.text()) - 1
            if 0 <= n < len(self.doc):
                self.page_num = n
                self.render()
        except:
            pass

    def user_draw_rect(self, qrect):
        if not self.doc:
            return
        r = fitz.Rect(
            qrect.left() / self.scale,
            qrect.top() / self.scale,
            qrect.right() / self.scale,
            qrect.bottom() / self.scale,
        )
        p = self.doc[self.page_num]
        txt = p.get_text("text", clip=r).strip()
        if not txt:
            p.add_redact_annot(
                r,
                text="[ IMMAGINE RIMOSSA ]",
                align=1,
                fill=(0.9, 0.9, 0.9),
                fontsize=8,
            )
        else:
            p.add_redact_annot(r, fill=(0, 0, 0))
            cl = " ".join(txt.split()).lower()
            if len(cl) > 2:
                self.allowlist.discard(cl)
                self.blocklist.add(cl)
                self.save_list(self.block_file, self.blocklist)
                self.save_list(self.allow_file, self.allowlist)
        self.render()

    def user_click_pt(self, qpt):
        if not self.doc:
            return
        pt = fitz.Point(qpt.x() / self.scale, qpt.y() / self.scale)
        p = self.doc[self.page_num]
        ans = [
            a
            for a in p.annots()
            if a.type[0] == fitz.PDF_ANNOT_REDACT and a.rect.contains(pt)
        ]
        if ans:
            txt = p.get_text("text", clip=ans[0].rect)
            [p.delete_annot(a) for a in ans]
            cl = " ".join(txt.split()).lower()
            if len(cl) > 2:
                self.blocklist.discard(cl)
                self.allowlist.add(cl)
                self.save_list(self.block_file, self.blocklist)
                self.save_list(self.allow_file, self.allowlist)
            self.render()

    def cmd_clear(self):
        if not self.doc:
            return
        p = self.doc[self.page_num]
        [p.delete_annot(a) for a in p.annots() if a.type[0] == fitz.PDF_ANNOT_REDACT]
        self.render()
        self.write_log(f"Censure rimosse su pagina {self.page_num+1}")

    def cmd_dict(self):
        d = QDialog(self)
        d.setWindowTitle("Dizionari")
        d.resize(500, 450)
        lay = QVBoxLayout(d)
        lay.addWidget(QLabel("<b>🔴 BLOCKLIST</b>"))
        bx = QTextEdit()
        bx.setPlainText("\n".join(sorted(self.blocklist)))
        lay.addWidget(bx)
        lay.addWidget(QLabel("<b>🟢 ALLOWLIST</b>"))
        ax = QTextEdit()
        ax.setPlainText("\n".join(sorted(self.allowlist)))
        lay.addWidget(ax)
        btn = QPushButton("Salva")
        btn.setObjectName("Primary")

        def s():
            self.blocklist = {
                l.strip().lower()
                for l in bx.toPlainText().split("\n")
                if len(l.strip()) > 2
            }
            self.allowlist = {
                l.strip().lower()
                for l in ax.toPlainText().split("\n")
                if len(l.strip()) > 2
            }
            self.save_list(self.block_file, self.blocklist)
            self.save_list(self.allow_file, self.allowlist)
            d.accept()

        btn.clicked.connect(s)
        lay.addWidget(btn)
        d.exec()

    def cmd_about(self):
        d = QDialog(self)
        d.setWindowTitle("Info")
        d.setFixedSize(340, 440)
        lay = QVBoxLayout(d)
        lay.setAlignment(Qt.AlignCenter)
        ip = resource_path(os.path.join("images", "NullifyPDF_icon.png"))
        if os.path.exists(ip):
            lbl_icon = QLabel()
            lbl_icon.setPixmap(
                QPixmap(ip).scaled(
                    100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
            lbl_icon.setAlignment(Qt.AlignCenter)
            lay.addWidget(lbl_icon)
            lay.addSpacing(10)
        lbl_title = QLabel("NullifyPDF")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold;")
        lbl_title.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl_title)
        lbl_ver = QLabel(f"v{__version__} AI Forensic")
        lbl_ver.setStyleSheet("color: #0ea5e9; font-weight: bold;")
        lbl_ver.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl_ver)
        desc = QLabel(
            "\nAnonimizzazione PDF Offline.\n\nSviluppato da: Graziano Mariella\nLicenza MIT"
        )
        desc.setAlignment(Qt.AlignCenter)
        lay.addWidget(desc)
        lay.addSpacing(20)
        btn = QPushButton("Chiudi")
        btn.clicked.connect(d.accept)
        lay.addWidget(btn)
        d.exec()

    def cmd_auto_ai(self):
        if not self.doc:
            return
        self.btn_ai.setEnabled(False)
        self.prog.setValue(0)
        c_allow = [
            (a, re.compile(r"\b" + re.escape(a) + r"\b")) for a in self.allowlist
        ]
        lang = (
            "EN"
            if self.rb_en.isChecked()
            else "IT" if self.rb_it.isChecked() else "BOTH"
        )
        texts = [p.get_text() for p in self.doc]
        self.start_scan_sig.emit(texts, lang, c_allow)

    @Slot(int, set)
    def apply_ai_to_page(self, i, words):
        page = self.doc[i]
        e_rects = [a.rect for a in page.annots() if a.type[0] == fitz.PDF_ANNOT_REDACT]
        if self.chk_img.isChecked():
            for img in page.get_image_info(hashes=False):
                ir = fitz.Rect(img["bbox"])
                page.add_redact_annot(
                    ir,
                    text="[ IMMAGINE RIMOSSA ]",
                    align=1,
                    fill=(0.9, 0.9, 0.9),
                    fontsize=8,
                )
                e_rects.append(ir)
        for bw in self.blocklist:
            for r in page.search_for(bw):
                if not any(
                    e.contains(fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))
                    for e in e_rects
                ):
                    page.add_redact_annot(r, fill=(0, 0, 0))
                    e_rects.append(r)
        p_rects = [r for aw in self.allowlist for r in page.search_for(aw)]
        for w in words:
            for r in page.search_for(w):
                if any(r.intersects(pr) for pr in p_rects):
                    continue
                if not any(
                    e.contains(fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))
                    for e in e_rects
                ):
                    page.add_redact_annot(r, fill=(0, 0, 0))
                    e_rects.append(r)

    @Slot()
    def ai_finished(self):
        self.btn_ai.setEnabled(True)
        self.render()

    def cmd_export(self):
        if not self.doc:
            return
        p, _ = QFileDialog.getSaveFileName(
            self,
            "Esporta",
            f"{os.path.splitext(self.doc.name)[0]}_secured.pdf",
            "PDF (*.pdf)",
        )
        if p:
            self.write_log("Scrubbing Forense...")
            ex_doc = fitz.open("pdf", self.doc.write())
            for page in ex_doc:
                r_rects = [
                    a.rect for a in page.annots() if a.type[0] == fitz.PDF_ANNOT_REDACT
                ]
                try:
                    [
                        page.delete_link(lnk)
                        for lnk in page.get_links()
                        if any(fitz.Rect(lnk["from"]).intersects(r) for r in r_rects)
                    ]
                except:
                    pass
                page.apply_redactions(
                    images=fitz.PDF_REDACT_IMAGE_REMOVE, graphics=True
                )
                try:
                    [page.delete_widget(w) for w in page.widgets()]
                except:
                    pass
            ex_doc.set_metadata({})
            cx = ex_doc.pdf_catalog()
            for k in ["Metadata", "PieceInfo", "Properties", "AcroForm"]:
                ex_doc.xref_set_key(cx, k, "null")
            ex_doc.save(p, garbage=4, deflate=True, clean=True)
            ex_doc.close()
            self.write_log("ESPORTATO.")


if __name__ == "__main__":
    if platform.system() == "Linux":
        os.environ["QT_LOGGING_RULES"] = "qt.qpa.wayland.*=false"

    app = QApplication(sys.argv)
    app.setDesktopFileName("nullify-pdf")

    window = NullifyPDF()
    window.show()
    sys.exit(app.exec())
