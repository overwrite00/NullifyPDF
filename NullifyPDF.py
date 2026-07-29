import os
import sys
import re
import signal
import datetime
import pathlib
import string
import platform
import logging
import traceback
import atexit
import hashlib
import html
import importlib.util
import json
from typing import Optional, List, Set, Dict, Any, Tuple
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
    QInputDialog,
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
from PySide6.QtCore import Qt, QThread, QObject, Signal, Slot, QRectF, QPointF, QMutex, QMutexLocker

from privacy_core import (
    PlaceholderRegistry,
    PrivacyMode,
    build_restore_payload,
    encrypt_restore_payload,
)

__version__ = "2.1.0"
__version_prerelease__ = ""
APP_VERSION = (
    f"{__version__}-{__version_prerelease__}"
    if __version_prerelease__
    else __version__
)


def setup_logging() -> logging.Logger:
    """Configure file-based logging.

    Respects NULLIFYPDF_DEBUG environment variable for verbose output.

    Returns:
        logging.Logger: Configured logger instance for nullifypdf.
    """
    log_dir = pathlib.Path.home() / ".nullifypdf" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("nullifypdf")
    debug_mode = os.environ.get("NULLIFYPDF_DEBUG", "").lower() == "true"
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    if logger.handlers:
        return logger

    try:
        handler = logging.FileHandler(
            log_dir / "nullifypdf.log",
            encoding="utf-8"
        )
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    except Exception as e:
        print(f"Warning: Could not setup file logging: {e}")

    return logger


def resource_path(relative_path: str) -> str:
    """Get absolute path for resource file (compatible with PyInstaller).

    Args:
        relative_path: Relative path to resource file.

    Returns:
        str: Absolute path to resource.
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def sha256_file(path: str) -> str:
    """Return the SHA-256 digest for a local file."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_tessdata_dir() -> Optional[str]:
    """Find a local Tesseract tessdata directory for PyMuPDF OCR."""
    candidates = []
    env_value = os.environ.get("TESSDATA_PREFIX")
    if env_value:
        candidates.append(env_value)
    try:
        candidates.append(fitz.get_tessdata())
    except Exception:
        pass
    candidates.append(resource_path(os.path.join("ocr", "tessdata")))
    candidates.extend(
        [
            r"C:\Program Files\Tesseract-OCR\tessdata",
            r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
            "/usr/share/tesseract-ocr/4.00/tessdata",
            "/usr/share/tesseract-ocr/5/tessdata",
            "/usr/share/tessdata",
        ]
    )
    for candidate in candidates:
        if not candidate:
            continue
        path = pathlib.Path(candidate)
        if path.is_dir() and any(path.glob("*.traineddata")):
            return str(path)
    return None


def ocr_language_for_choice(choice: str, tessdata_dir: Optional[str]) -> str:
    """Map the UI language choice to installed Tesseract language codes."""
    requested = ["eng", "ita"] if choice == "BOTH" else ["ita" if choice == "IT" else "eng"]
    if not tessdata_dir:
        return "+".join(requested)
    available = [
        lang for lang in requested
        if (pathlib.Path(tessdata_dir) / f"{lang}.traineddata").exists()
    ]
    return "+".join(available or requested)


class PDFListManager:
    """Manages blocklist/allowlist persistence to disk.

    Handles loading and saving word lists with automatic path management
    and UTF-8 encoding.
    """

    def __init__(self, config_dir: pathlib.Path) -> None:
        """Initialize list manager with config directory.

        Args:
            config_dir: Path to configuration directory.
        """
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.block_file = config_dir / "blocklist.txt"
        self.allow_file = config_dir / "allowlist.txt"

    def load_blocklist(self) -> Set[str]:
        """Load blocklist from disk.

        Returns:
            Set[str]: Words to redact (lowercase).
        """
        return self._load_list(self.block_file)

    def load_allowlist(self) -> Set[str]:
        """Load allowlist from disk.

        Returns:
            Set[str]: Words to preserve from redaction (lowercase).
        """
        return self._load_list(self.allow_file)

    def save_blocklist(self, blocklist: Set[str]) -> None:
        """Persist blocklist to disk.

        Args:
            blocklist: Set of words to save.
        """
        self._save_list(self.block_file, blocklist)

    def save_allowlist(self, allowlist: Set[str]) -> None:
        """Persist allowlist to disk.

        Args:
            allowlist: Set of words to save.
        """
        self._save_list(self.allow_file, allowlist)

    def _load_list(self, path: pathlib.Path) -> Set[str]:
        """Load word list from file with validation.

        Args:
            path: Path to list file.

        Returns:
            Set[str]: Set of words (lowercase, stripped, min length 3).
        """
        if not path.exists():
            return set()
        try:
            # Use context manager to ensure file handle is closed deterministically
            with open(path, "r", encoding="utf-8") as fh:
                return {
                    line.strip().lower()
                    for line in fh
                    if len(line.strip()) > 2
                }
        except Exception as e:
            logging.getLogger(__name__).error(f"Error loading {path}: {e}")
            return set()

    def _save_list(self, path: pathlib.Path, words: Set[str]) -> None:
        """Save word list to file.

        Args:
            path: Path to save list.
            words: Set of words to save.
        """
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(sorted(words)))
        except Exception as e:
            logging.getLogger(__name__).error(f"Error saving {path}: {e}")


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
    """AI analysis worker thread for PDF sensitive data detection.

    Uses Microsoft Presidio + spaCy for NER (Named Entity Recognition).
    Runs in separate thread to prevent UI blocking.

    Signals:
        log_sig: Emits log message (str).
        progress_sig: Emits (current_page, total_pages) progress.
        page_done_sig: Emits (page_index, detections) when page scan completes.
        finished_sig: Emitted when all pages processed.
    """

    log_sig = Signal(str)
    progress_sig = Signal(int, int)
    page_done_sig = Signal(int, object)
    finished_sig = Signal()

    def __init__(self) -> None:
        """Initialize AI worker with empty analyzer."""
        super().__init__()
        self.analyzer: Optional[Any] = None
        self.loaded_langs: List[str] = []
        self._stop_requested = False

    def cleanup(self) -> None:
        """Release AI resources (Presidio, spaCy models).

        Must be called before thread termination to avoid hanging processes.
        """
        self._stop_requested = True
        try:
            if self.analyzer:
                # Clear analyzer reference; let GC reclaim spaCy/Presidio resources.
                # NOTE: Mutating nlp.vocab.vectors.shape is not supported in modern
                # spaCy (read-only property), so we simply drop the reference.
                self.analyzer = None
            self.loaded_langs.clear()
        except Exception as e:
            logging.getLogger("nullifypdf").debug(f"Error during AI cleanup: {e}")

    @Slot(object, object, str, list, set, bool, object)
    def run_scan(self, doc: Any, doc_mutex: Any, choice: str,
                 compiled_allowlist: List[Tuple[str, Any]],
                 allowlist_set: Set[str], use_ocr: bool,
                 tessdata_dir: Optional[str]) -> None:
        """Run AI scan on PDF pages and emit detected sensitive entities.

        Text extraction (`page.get_text()`) is performed inside this worker so
        it does not block the UI thread on large documents. Access to the
        shared PyMuPDF document is serialized through `doc_mutex` because the
        UI thread also reads from it (render) and writes to it (apply
        redactions) concurrently.

        Args:
            doc: PyMuPDF document (shared with UI thread, mutex-protected).
            doc_mutex: QMutex serializing access to `doc`.
            choice: Language choice: 'EN', 'IT', or 'BOTH'.
            compiled_allowlist: Pre-compiled regex patterns to skip redaction.
            allowlist_set: Set of allowlist entries (lowercase) for O(1)
                exact-match fast-path lookup before regex any() scan.
        """
        try:
            if self._stop_requested:
                self.finished_sig.emit()
                return

            if doc is None:
                self.log_sig.emit("ERRORE: doc non valido")
                self.finished_sig.emit()
                return

            if choice not in ("EN", "IT", "BOTH"):
                self.log_sig.emit(f"ERRORE: Scelta lingua non valida: {choice}")
                self.finished_sig.emit()
                return

            if not isinstance(compiled_allowlist, list):
                self.log_sig.emit("ERRORE: compiled_allowlist non valido")
                self.finished_sig.emit()
                return

            if not isinstance(allowlist_set, set):
                allowlist_set = set()

            target_langs = ["en", "it"] if choice == "BOTH" else [choice.lower()]
            ocr_language = ocr_language_for_choice(choice, tessdata_dir)
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
            self.log_sig.emit("Scansione privacy in corso...")
            targets = [
                "PERSON",
                "LOCATION",
                "EMAIL_ADDRESS",
                "PHONE_NUMBER",
                "IBAN_CODE",
                "CREDIT_CARD",
                "CRYPTO",
            ]

            # Determine page count under mutex (cheap, but doc may be replaced
            # mid-flight by load_path if not for the disabled UI during scan).
            with QMutexLocker(doc_mutex):
                total_pages = len(doc)

            for i in range(total_pages):
                if self._stop_requested:
                    break
                # Extract text in worker thread (off the UI thread) under mutex
                # because UI thread renders / mutates annotations on the same doc.
                used_ocr = False
                textpage = None
                with QMutexLocker(doc_mutex):
                    try:
                        page = doc[i]
                        text = page.get_text()
                        needs_ocr = use_ocr and self._page_needs_ocr(page, text)
                        if needs_ocr:
                            self.log_sig.emit(f"OCR pagina {i + 1}...")
                            textpage = page.get_textpage_ocr(
                                language=ocr_language,
                                dpi=300,
                                full=True,
                                tessdata=tessdata_dir,
                            )
                            text = page.get_text(textpage=textpage)
                            used_ocr = True
                    except Exception as e:
                        self.log_sig.emit(
                            f"Avviso: estrazione testo/OCR fallita pagina {i+1}: {e}"
                        )
                        text = ""
                found: Dict[str, str] = {}
                for lang in self.loaded_langs:
                    res = self.analyzer.analyze(
                        text=text, entities=targets, language=lang
                    )
                    for r in res:
                        w = text[r.start : r.end].strip()
                        if len(w) > 2:
                            found[w] = r.entity_type
                detections = []
                for m, entity_type in found.items():
                    clean = " ".join(m.strip(string.punctuation).lower().split())
                    if not clean:
                        continue
                    # Fast path: exact set membership is O(1). The vast majority
                    # of user allowlist entries are full tokens matched verbatim
                    # against `clean`, so this short-circuits before the O(N)
                    # regex any() scan over the whole allowlist.
                    if clean in allowlist_set:
                        continue
                    # Cache the word-boundary regex for `clean` so we don't
                    # rebuild and recompile it once per allowlist entry.
                    clean_pattern = re.compile(r"\b" + re.escape(clean) + r"\b")
                    if not any(
                        f_reg.search(clean) or clean_pattern.search(a_str)
                        for a_str, f_reg in compiled_allowlist
                    ):
                        detection = {
                            "text": m,
                            "entity_type": entity_type,
                            "rects": [],
                            "source": "ocr" if used_ocr else "text",
                        }
                        if used_ocr and textpage is not None:
                            with QMutexLocker(doc_mutex):
                                try:
                                    rects = doc[i].search_for(m, textpage=textpage)
                                    detection["rects"] = [
                                        (r.x0, r.y0, r.x1, r.y1) for r in rects
                                    ]
                                except Exception as e:
                                    self.log_sig.emit(
                                        f"Avviso: coordinate OCR non disponibili "
                                        f"pagina {i+1}: {e}"
                                    )
                        detections.append(detection)
                self.page_done_sig.emit(i, detections)
                self.progress_sig.emit(i + 1, total_pages)
            if not self._stop_requested:
                self.log_sig.emit("Anonimizzazione completata.")
        except Exception as e:
            # Log full traceback to file for diagnostics; show only summary in UI
            logging.getLogger("nullifypdf").error(
                f"AI scan error: {traceback.format_exc()}"
            )
            self.log_sig.emit(f"ERRORE AI: {type(e).__name__}: {str(e)}")
        finally:
            self.finished_sig.emit()

    def _page_needs_ocr(self, page: Any, extracted_text: str) -> bool:
        """Return True when a page looks scanned or text extraction is too poor."""
        text = (extracted_text or "").strip()
        if len(text) >= 20 and text.count("\ufffd") / max(len(text), 1) < 0.05:
            return False
        try:
            if page.get_image_info(hashes=False):
                return True
        except Exception:
            return len(text) < 20
        return len(text) < 20


class PDFView(QGraphicsView):
    """Custom graphics view for interactive PDF page display.

    Handles mouse events for rectangle drawing (redaction) and zoom control.

    Signals:
        rect_drawn: Emits QRectF when user finishes drawing selection rectangle.
        point_clicked: Emits QPointF when user clicks on page.
        zoom_req: Emits int (+1 for zoom in, -1 for zoom out).
    """

    rect_drawn = Signal(QRectF)
    point_clicked = Signal(QPointF)
    zoom_req = Signal(int)

    def __init__(self, scene: QGraphicsScene, parent: Optional[Any] = None) -> None:
        """Initialize PDF view with scene.

        Args:
            scene: Graphics scene to display.
            parent: Parent widget.
        """
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.start_pos: Optional[QPointF] = None
        self.temp_rect: Optional[QGraphicsRectItem] = None

    def mousePressEvent(self, event: Any) -> None:
        """Handle mouse press: start selection rectangle on left-click."""
        if event.button() == Qt.LeftButton:
            sp = self.mapToScene(event.position())
            self.start_pos = sp
            self.point_clicked.emit(sp)
            self.temp_rect = QGraphicsRectItem(QRectF(sp, sp))
            self.temp_rect.setPen(QPen(QColor("#ef4444"), 2))
            self.scene().addItem(self.temp_rect)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        """Update in-progress selection rectangle while dragging."""
        if self.start_pos and self.temp_rect:
            ep = self.mapToScene(event.position())
            self.temp_rect.setRect(QRectF(self.start_pos, ep).normalized())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        """Finalize selection rectangle and emit rect_drawn if large enough."""
        if event.button() == Qt.LeftButton and self.temp_rect:
            rect = self.temp_rect.rect()
            self.scene().removeItem(self.temp_rect)
            self.temp_rect = None
            self.start_pos = None
            if rect.width() > 5 and rect.height() > 5:
                self.rect_drawn.emit(rect)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: Any) -> None:
        if event.modifiers() == Qt.ControlModifier:
            self.zoom_req.emit(1 if event.angleDelta().y() > 0 else -1)
            event.accept()
        else:
            super().wheelEvent(event)


class NullifyPDF(QMainWindow):
    """Main application window for PDF privacy redaction using AI.

    Handles PDF loading, manual/AI-assisted redaction, blocklist/allowlist
    management, and privacy-focused export.

    Attributes:
        doc: Currently loaded PDF document (None if not loaded).
        page_num: Current page index (0-based).
        scale: Current zoom scale factor (0.5 - 4.0).
        blocklist: Set of strings to redact automatically.
        allowlist: Set of strings to preserve from redaction.
        config_dir: Path to user config directory (~/.nullifypdf).
    """

    start_scan_sig = Signal(object, object, str, list, set, bool, object)

    def __init__(self) -> None:
        """Initialize main application window and setup UI."""
        super().__init__()
        self.logger = setup_logging()
        self.logger.info("Application started")
        self.setWindowTitle("NullifyPDF - Privacy Edition")
        self.resize(1350, 950)
        self.setStyleSheet(STYLESHEET)
        self.setAcceptDrops(True)
        ip = resource_path(os.path.join("images", "NullifyPDF_icon.png"))
        if os.path.exists(ip):
            self.setWindowIcon(QIcon(ip))
        self.doc = None
        self.page_num = 0
        self.scale = 1.5
        # Mutex guards `self.doc` against concurrent access from the AI worker
        # thread (text extraction) and the UI thread (render, apply redactions).
        self.doc_mutex = QMutex()
        self.config_dir = pathlib.Path.home() / ".nullifypdf"
        self.list_manager = PDFListManager(self.config_dir)
        self.blocklist = self.list_manager.load_blocklist()
        self.allowlist = self.list_manager.load_allowlist()
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
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        # Register cleanup on exit
        atexit.register(self._cleanup_on_exit)
        if len(sys.argv) > 1:
            self.load_path(sys.argv[1])

    def _setup_signal_handlers(self) -> None:
        """Setup SIGINT/SIGTERM handlers for graceful shutdown.

        Allows Ctrl+C to properly cleanup resources before exit.
        """
        from PySide6.QtCore import QTimer

        def signal_handler(signum: int, frame: Any) -> None:
            self.logger.info(f"Signal {signum} received, initiating graceful shutdown")
            # Defer close() onto the Qt event loop. Python signal handlers run
            # at arbitrary points in main-thread bytecode; calling Qt APIs
            # directly from one can crash or leave Qt in an inconsistent state.
            QTimer.singleShot(0, self.close)

        # Windows doesn't support SIGTERM for user processes, but SIGINT works
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)

    def _cleanup_resources(self) -> None:
        """Cleanup all resources before application termination.

        Releases:
        - PDF document (PyMuPDF)
        - AI worker thread and models
        - All connections
        """
        self.logger.info("Starting resource cleanup")
        try:
            # Stop AI worker from processing
            if hasattr(self, 'ai_worker'):
                self.ai_worker.cleanup()

            # Quit and wait for thread
            if hasattr(self, 'ai_thread') and self.ai_thread.isRunning():
                self.ai_thread.quit()
                # Wait up to 5 seconds for thread to finish
                if not self.ai_thread.wait(5000):
                    self.logger.warning("AI thread did not terminate within timeout, forcing termination")
                    self.ai_thread.terminate()
                    self.ai_thread.wait()

            # Close PDF document
            if self.doc:
                try:
                    self.doc.close()
                    self.logger.debug("PDF document closed")
                except Exception as e:
                    self.logger.debug(f"Error closing PDF: {e}")
                self.doc = None

            # Note: Signal disconnection is optional - Python's garbage collector
            # will clean up signal/slot connections when objects are destroyed.
            # Explicit disconnect() is not necessary and can cause RuntimeWarning
            # if the worker thread has already been cleaned up.

            self.logger.info("Resource cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def _cleanup_on_exit(self) -> None:
        """Final cleanup hook called on application exit via atexit.

        This ensures cleanup happens even if closeEvent is not called.
        """
        self._cleanup_resources()

    def closeEvent(self, event: Any) -> None:
        """Handle window close event with proper resource cleanup.

        Args:
            event: Qt QCloseEvent passed by the framework.
        """
        self._cleanup_resources()
        super().closeEvent(event)

    def build_ui(self) -> None:
        """Build main application UI layout."""
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
        s_lay.addWidget(QLabel("AI Privacy Edition\n"))
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
        for rb in (self.rb_en, self.rb_it, self.rb_both):
            self.lang_grp.addButton(rb)
            lang_lay.addWidget(rb)
        s_lay.addLayout(lang_lay)
        s_lay.addSpacing(10)
        self.chk_img = QCheckBox("Oscura Immagini")
        s_lay.addWidget(self.chk_img)
        self.chk_ocr = QCheckBox("OCR PDF scansionati")
        self.chk_ocr.setChecked(True)
        s_lay.addWidget(self.chk_ocr)
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
        btn_export = QPushButton("Esporta Privacy")
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

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        """Accept drag enter event for dropped files."""
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent) -> None:
        """Handle dropped PDF files."""
        urls = e.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.load_path(urls[0].toLocalFile())

    def write_log(self, m: str) -> None:
        """Write message to UI log with color coding.

        Args:
            m: Message to log.
        """
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
        safe_message = html.escape(m)
        self.log.append(f"<span style='color: {color};'>[{t}] {safe_message}</span>")

    def update_progress(self, c: int, t: int) -> None:
        """Update progress bar.

        Args:
            c: Current progress.
            t: Total progress.
        """
        # Guard against division by zero (empty document edge case)
        if t <= 0:
            self.prog.setValue(0)
            return
        self.prog.setValue(int((c / t) * 100))

    def cmd_open(self) -> None:
        """Open file dialog to load PDF."""
        p, _ = QFileDialog.getOpenFileName(self, "Apri PDF", "", "PDF (*.pdf)")
        if p:
            self.load_path(p)

    def load_path(self, path: str) -> None:
        """Load a PDF document from disk and reset viewer state.

        Args:
            path: Filesystem path to a .pdf file.
        """
        if not path or not isinstance(path, str):
            self.write_log("ERRORE: Path non valido")
            return
        if not os.path.exists(path):
            self.write_log(f"ERRORE: File non trovato: {path}")
            return
        if not path.lower().endswith('.pdf'):
            self.write_log("ERRORE: Solo file PDF sono supportati")
            return

        try:
            tdoc = fitz.open(path)
            if tdoc.needs_pass:
                self.write_log("ERRORE: PDF cifrato - inserire password non supportato")
                tdoc.close()
                return
            # Swap docs under mutex so the AI worker thread (if running) is not
            # holding a reference to a closed document.
            with QMutexLocker(self.doc_mutex):
                if self.doc:
                    self.doc.close()
                self.doc = tdoc
                self.page_num = 0
                self.scale = 1.5
            self.adjust_zoom(0)
            self.write_log(f"Caricato: {os.path.basename(path)}")
            self._warn_if_scanned_pdf()
        except FileNotFoundError:
            self.write_log(f"ERRORE: File non trovato")
        except Exception as e:
            self.logger.error(f"Error loading PDF: {traceback.format_exc()}")
            self.write_log(f"ERRORE: {type(e).__name__}: {str(e)}")

    def _warn_if_scanned_pdf(self) -> None:
        """Warn when pages look image-only and therefore need OCR support."""
        if not self.doc:
            return
        scanned_pages = []
        with QMutexLocker(self.doc_mutex):
            if not self.doc:
                return
            for page in self.doc:
                text = page.get_text("text").strip()
                has_images = bool(page.get_image_info(hashes=False))
                if not text and has_images:
                    scanned_pages.append(page.number + 1)
        if scanned_pages:
            preview = ", ".join(str(n) for n in scanned_pages[:10])
            suffix = "..." if len(scanned_pages) > 10 else ""
            self.write_log(
                "Avviso: probabile PDF scansionato senza testo OCR "
                f"nelle pagine {preview}{suffix}. "
                "Serve OCR prima della rilevazione automatica dei dati personali."
            )

    def render(self) -> None:
        """Render current PDF page to display."""
        if not self.doc:
            return
        with QMutexLocker(self.doc_mutex):
            if not self.doc or self.page_num >= len(self.doc):
                return
            page = self.doc[self.page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(self.scale, self.scale), annots=True)
            total = len(self.doc)
        # QImage does NOT copy `pix.samples`; if `pix` is garbage-collected before
        # the image is used the buffer is freed (UB / crash). Force a deep copy.
        img = QImage(
            pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888
        ).copy()
        self.scene.clear()
        self.scene.addPixmap(QPixmap.fromImage(img))
        self.scene.setSceneRect(0, 0, pix.width, pix.height)
        self.le_page.setText(str(self.page_num + 1))
        self.lbl_tot.setText(f"/ {total}")

    def adjust_zoom(self, d: int) -> None:
        """Adjust zoom level.

        Args:
            d: Zoom direction (+1 to zoom in, -1 to zoom out).
        """
        self.scale = max(0.5, min(4.0, self.scale + (0.25 * d)))
        self.lbl_zoom.setText(f"{int(self.scale * 100)}%")
        self.render()

    def move_page(self, d: int) -> None:
        """Move to adjacent page.

        Args:
            d: Page direction (+1 for next, -1 for previous).
        """
        if self.doc and 0 <= self.page_num + d < len(self.doc):
            self.page_num += d
            self.render()

    def jump_page(self) -> None:
        """Jump to the page number entered in the page selector."""
        if not self.doc:
            self.write_log("Avviso: Nessun PDF caricato")
            return
        try:
            n = int(self.le_page.text()) - 1
            if 0 <= n < len(self.doc):
                self.page_num = n
                self.render()
            else:
                self.write_log(f"Avviso: Pagina {n + 1} non esiste (intervallo: 1-{len(self.doc)})")
        except ValueError:
            self.write_log("ERRORE: Inserire un numero valido per il numero di pagina")
        except Exception as e:
            self.logger.error(f"Unexpected error in jump_page: {traceback.format_exc()}")
            self.write_log(f"ERRORE: {type(e).__name__}: {str(e)}")

    def user_draw_rect(self, qrect: QRectF) -> None:
        """Handle user-drawn redaction rectangle.

        Args:
            qrect: Rectangle drawn by user in scene coordinates.
        """
        if not self.doc:
            return
        r = fitz.Rect(
            qrect.left() / self.scale,
            qrect.top() / self.scale,
            qrect.right() / self.scale,
            qrect.bottom() / self.scale,
        )
        with QMutexLocker(self.doc_mutex):
            if not self.doc:
                return
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
                self._add_privacy_redaction(
                    p,
                    r,
                    original=txt,
                    entity_type=self._infer_entity_type(txt),
                )
                cl = " ".join(txt.split()).lower()
                if len(cl) > 2:
                    self.allowlist.discard(cl)
                    self.blocklist.add(cl)
                    self.list_manager.save_blocklist(self.blocklist)
                    self.list_manager.save_allowlist(self.allowlist)
        self.render()

    def user_click_pt(self, qpt: QPointF) -> None:
        """Handle user click on redaction to delete it.

        Args:
            qpt: Point clicked by user in scene coordinates.
        """
        if not self.doc:
            return
        pt = fitz.Point(qpt.x() / self.scale, qpt.y() / self.scale)
        has_ans = False
        with QMutexLocker(self.doc_mutex):
            if not self.doc:
                return
            p = self.doc[self.page_num]
            ans = [
                a
                for a in (p.annots() or [])
                if a.type[0] == fitz.PDF_ANNOT_REDACT and a.rect.contains(pt)
            ]
            if ans:
                has_ans = True
                txt = p.get_text("text", clip=ans[0].rect)
                for a in ans:
                    p.delete_annot(a)
                cl = " ".join(txt.split()).lower()
                if len(cl) > 2:
                    self.blocklist.discard(cl)
                    self.allowlist.add(cl)
                    self.list_manager.save_blocklist(self.blocklist)
                    self.list_manager.save_allowlist(self.allowlist)
        if has_ans:
            self.render()

    def cmd_clear(self) -> None:
        """Clear all redactions on current page."""
        if not self.doc:
            return
        with QMutexLocker(self.doc_mutex):
            if not self.doc:
                return
            p = self.doc[self.page_num]
            # Materialize list first: deleting annotations invalidates the
            # generator returned by p.annots(), and list-comprehension-for-
            # side-effects is an anti-pattern (PEP 8 / pylint W0106).
            to_delete = [
                a for a in (p.annots() or []) if a.type[0] == fitz.PDF_ANNOT_REDACT
            ]
            for a in to_delete:
                p.delete_annot(a)
        self.render()
        self.write_log(f"Censure rimosse su pagina {self.page_num+1}")

    def cmd_dict(self) -> None:
        """Open dialog to edit blocklist/allowlist."""
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

        def s() -> None:
            self.blocklist = {
                line.strip().lower()
                for line in bx.toPlainText().split("\n")
                if len(line.strip()) > 2
            }
            self.allowlist = {
                line.strip().lower()
                for line in ax.toPlainText().split("\n")
                if len(line.strip()) > 2
            }
            self.list_manager.save_blocklist(self.blocklist)
            self.list_manager.save_allowlist(self.allowlist)
            d.accept()

        btn.clicked.connect(s)
        lay.addWidget(btn)
        d.exec()

    def cmd_about(self) -> None:
        """Show about dialog."""
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
        lbl_ver = QLabel(f"v{APP_VERSION} AI Privacy Beta")
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

    def cmd_auto_ai(self) -> None:
        """Start AI scan for sensitive entities.

        Text extraction is delegated to the AIWorker thread so the UI stays
        responsive on large documents. Access to `self.doc` is serialized via
        `self.doc_mutex` between the UI thread and the worker.
        """
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
        use_ocr = self.chk_ocr.isChecked()
        tessdata_dir = find_tessdata_dir() if use_ocr else None
        if use_ocr and not tessdata_dir:
            self.btn_ai.setEnabled(True)
            QMessageBox.warning(
                self,
                "OCR non configurato",
                "Per i PDF scansionati serve Tesseract tessdata. "
                "Installa Tesseract-OCR e imposta TESSDATA_PREFIX oppure "
                "disattiva OCR per analizzare solo il testo digitale.",
            )
            return
        # Pass a snapshot copy of the allowlist set so the worker is insulated
        # from concurrent mutation by the UI (user_draw_rect / cmd_dict).
        self.start_scan_sig.emit(
            self.doc,
            self.doc_mutex,
            lang,
            c_allow,
            set(self.allowlist),
            use_ocr,
            tessdata_dir,
        )

    def _select_privacy_export(self) -> Optional[PrivacyMode]:
        """Ask the user which privacy export mode to use."""
        box = QMessageBox(self)
        box.setWindowTitle("Modalita privacy")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("Scegli come trattare i dati personali nel PDF esportato.")
        box.setInformativeText(
            "Anonimizzazione: rimozione irreversibile.\n"
            "Pseudonimizzazione: segnaposto reversibili con mappa cifrata separata."
        )
        anonymize_btn = box.addButton(
            "Anonimizzazione irreversibile", QMessageBox.ButtonRole.AcceptRole
        )
        pseudonymize_btn = box.addButton(
            "Pseudonimizzazione reversibile", QMessageBox.ButtonRole.ActionRole
        )
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked == anonymize_btn:
            return PrivacyMode.ANONYMIZE
        if clicked == pseudonymize_btn:
            return PrivacyMode.PSEUDONYMIZE
        return None

    def _infer_entity_type(self, value: str) -> str:
        """Infer a coarse placeholder type for manually marked text."""
        compact = " ".join(value.split())
        if re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", compact, re.I):
            return "EMAIL_ADDRESS"
        if re.search(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", compact.replace(" ", ""), re.I):
            return "IBAN_CODE"
        if re.search(r"\+?\d[\d\s()./-]{6,}\d", compact):
            return "PHONE_NUMBER"
        if re.search(r"\b\d{13,19}\b", compact.replace(" ", "")):
            return "CREDIT_CARD"
        return "DATA"

    def _collect_redaction_rects(self, page: Any) -> List[fitz.Rect]:
        """Return redaction rectangles for a page."""
        return [
            a.rect for a in (page.annots() or [])
            if a.type[0] == fitz.PDF_ANNOT_REDACT
        ]

    def _add_privacy_redaction(
        self,
        page: Any,
        rect: fitz.Rect,
        *,
        original: str = "",
        entity_type: str = "DATA",
        fill: Tuple[float, float, float] = (0, 0, 0),
    ) -> None:
        """Add a redaction annotation carrying optional in-memory privacy data."""
        annot = page.add_redact_annot(rect, fill=fill)
        clean_original = " ".join((original or "").split())
        if clean_original:
            payload = {
                "nullifypdf": 1,
                "original": clean_original,
                "entity_type": PlaceholderRegistry.normalize_entity_type(entity_type),
            }
            try:
                annot.set_info(content=json.dumps(payload, ensure_ascii=False))
            except Exception as e:
                self.logger.debug(f"Could not store redaction metadata: {e}")

    def _read_redaction_payload(self, annot: Any) -> Dict[str, str]:
        """Read privacy data stored on a pending redaction annotation."""
        try:
            raw = annot.info.get("content", "")
            payload = json.loads(raw) if raw else {}
        except Exception:
            return {}
        if payload.get("nullifypdf") != 1:
            return {}
        return {
            "original": str(payload.get("original", "")),
            "entity_type": str(payload.get("entity_type", "DATA")),
        }

    def _prepare_pseudonymized_page(
        self, page: Any, registry: PlaceholderRegistry
    ) -> None:
        """Replace pending redaction annotations with placeholder redactions."""
        pending = [
            (
                annot.rect,
                self._read_redaction_payload(annot),
                page.get_text("text", clip=annot.rect).strip(),
            )
            for annot in (page.annots() or [])
            if annot.type[0] == fitz.PDF_ANNOT_REDACT
        ]
        for annot in list(page.annots() or []):
            if annot.type[0] == fitz.PDF_ANNOT_REDACT:
                page.delete_annot(annot)
        for rect, payload, clipped_text in pending:
            clean_original = " ".join(
                (payload.get("original") or clipped_text).split()
            )
            if clean_original:
                entity_type = payload.get("entity_type") or self._infer_entity_type(
                    clean_original
                )
                placeholder = registry.placeholder_for(
                    clean_original,
                    entity_type,
                    page=page.number,
                )
                page.add_redact_annot(
                    rect,
                    text=placeholder,
                    fill=(1, 1, 1),
                    text_color=(0, 0, 0),
                    align=1,
                    fontsize=8,
                )
            else:
                page.add_redact_annot(
                    rect,
                    text="[IMAGE_REMOVED]",
                    fill=(1, 1, 1),
                    text_color=(0, 0, 0),
                    align=1,
                    fontsize=8,
                )

    @Slot(int, object)
    def apply_ai_to_page(self, i: int, detections: Any) -> None:
        """Apply AI-detected redactions to page.

        Runs on the UI thread (Qt slot). Holds `doc_mutex` while mutating the
        page so the AI worker's `get_text()` calls do not race.

        Args:
            i: Page index.
            detections: Sensitive data detections with optional OCR rectangles.
        """
        if not self.doc:
            return
        if isinstance(detections, set):
            normalized_detections = [
                {"text": word, "entity_type": self._infer_entity_type(word), "rects": []}
                for word in detections
            ]
        else:
            normalized_detections = list(detections or [])
        with QMutexLocker(self.doc_mutex):
            if i >= len(self.doc):
                return
            page = self.doc[i]
            e_rects = [
                a.rect for a in (page.annots() or [])
                if a.type[0] == fitz.PDF_ANNOT_REDACT
            ]
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
                        self._add_privacy_redaction(
                            page,
                            r,
                            original=bw,
                            entity_type=self._infer_entity_type(bw),
                        )
                        e_rects.append(r)
            p_rects = [r for aw in self.allowlist for r in page.search_for(aw)]
            for detection in normalized_detections:
                word = str(detection.get("text", ""))
                entity_type = str(detection.get("entity_type", "DATA"))
                raw_rects = detection.get("rects") or []
                rects = [fitz.Rect(*coords) for coords in raw_rects]
                if not rects and word:
                    rects = list(page.search_for(word))
                for r in rects:
                    if any(r.intersects(pr) for pr in p_rects):
                        continue
                    if not any(
                        e.contains(fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))
                        for e in e_rects
                    ):
                        self._add_privacy_redaction(
                            page,
                            r,
                            original=word,
                            entity_type=entity_type,
                        )
                        e_rects.append(r)

    @Slot()
    def ai_finished(self) -> None:
        """Handle AI scan completion."""
        self.btn_ai.setEnabled(True)
        self.render()

    def cmd_export(self) -> None:
        """Export current PDF in irreversible or reversible privacy mode.

        Memory strategy (fix C1): instead of materializing the whole document
        in RAM via `self.doc.write()` (which would double peak memory on large
        PDFs), we stream through a sibling temp file next to the target path:

            1. Save `self.doc` (with annotations, NOT yet flattened) to
               `<target>.tmp` on disk.
            2. Open the temp file as `ex_doc`.
            3. Apply redactions / scrub metadata on `ex_doc`.
            4. Save `ex_doc` to the user-chosen final path.
            5. Remove the temp file.

        The original `self.doc` is never mutated (redactions stay as
        annotations), so the user can keep editing after export. Peak extra
        memory is O(1) over what PyMuPDF needs internally for save().
        """
        if not self.doc:
            return
        mode = self._select_privacy_export()
        if mode is None:
            return
        p, _ = QFileDialog.getSaveFileName(
            self,
            "Esporta",
            f"{os.path.splitext(self.doc.name)[0]}_{mode.value}.pdf",
            "PDF (*.pdf)",
        )
        if not p:
            return
        map_path = ""
        map_password = ""
        if mode == PrivacyMode.PSEUDONYMIZE:
            map_path, _ = QFileDialog.getSaveFileName(
                self,
                "Salva mappa cifrata",
                f"{os.path.splitext(p)[0]}.nullifypdf-map",
                "NullifyPDF map (*.nullifypdf-map)",
            )
            if not map_path:
                return
            map_password, ok = QInputDialog.getText(
                self,
                "Password mappa",
                "Password per cifrare la mappa di ripristino (minimo 12 caratteri):",
                QLineEdit.Password,
            )
            if not ok:
                return
            if len(map_password) < 12:
                QMessageBox.warning(
                    self,
                    "Password troppo corta",
                    "La password della mappa deve avere almeno 12 caratteri.",
                )
                return
            if importlib.util.find_spec("cryptography") is None:
                QMessageBox.critical(
                    self,
                    "Dipendenza mancante",
                    "La pseudonimizzazione richiede la libreria 'cryptography'.",
                )
                return

        self.write_log(
            "Export anonimizzato..." if mode == PrivacyMode.ANONYMIZE
            else "Export pseudonimizzato..."
        )
        # Sibling temp file (same directory as target so rename/cleanup are
        # always on the same filesystem; avoids cross-device issues).
        tmp_path = p + ".nullifypdf.tmp"
        ex_doc = None
        registry = PlaceholderRegistry()
        try:
            source_name = self.doc.name or "document.pdf"
            source_sha256 = sha256_file(source_name) if os.path.exists(source_name) else ""
            # Step 1: serialize `self.doc` (with annotations) to disk under
            # the mutex so the AI worker thread cannot mutate mid-write.
            with QMutexLocker(self.doc_mutex):
                if not self.doc:
                    return
                # `clean=False` here: we want a faithful copy of the
                # in-memory state, including all redact annotations. The
                # real cleanup pass happens on ex_doc.save() below.
                self.doc.save(tmp_path, garbage=0, deflate=False, clean=False)

            # Step 2: reopen the on-disk copy. PyMuPDF lazy-parses pages, so
            # this does NOT load the whole PDF into RAM up front.
            ex_doc = fitz.open(tmp_path)

            # Step 3: scrub on the disk-backed copy.
            for page in ex_doc:
                if mode == PrivacyMode.PSEUDONYMIZE:
                    self._prepare_pseudonymized_page(page, registry)
                # page.annots() may return None for pages with no annotations
                r_rects = self._collect_redaction_rects(page)
                try:
                    links_to_delete = [
                        lnk for lnk in page.get_links()
                        if any(fitz.Rect(lnk["from"]).intersects(r) for r in r_rects)
                    ]
                    for lnk in links_to_delete:
                        page.delete_link(lnk)
                except (RuntimeError, AttributeError, KeyError) as e:
                    self.logger.debug(f"Could not delete link: {e}")
                page.apply_redactions(
                    images=fitz.PDF_REDACT_IMAGE_REMOVE, graphics=True
                )
                try:
                    # Materialize first: mutating during iteration of
                    # page.widgets() can invalidate the generator.
                    for w in list(page.widgets() or []):
                        page.delete_widget(w)
                except (RuntimeError, AttributeError) as e:
                    self.logger.debug(f"Could not delete widget: {e}")
            ex_doc.set_metadata({})
            cx = ex_doc.pdf_catalog()
            for k in ["Metadata", "PieceInfo", "Properties", "AcroForm"]:
                ex_doc.xref_set_key(cx, k, "null")

            # Step 4: write final scrubbed output. Must save to a different
            # path than the open source (`tmp_path`) to avoid PyMuPDF's
            # "save to original" restriction on incremental saves.
            ex_doc.save(p, garbage=4, deflate=True, clean=True)
            if mode == PrivacyMode.PSEUDONYMIZE:
                payload = build_restore_payload(
                    source_name=source_name,
                    source_sha256=source_sha256,
                    output_sha256=sha256_file(p),
                    entries=registry.entries(),
                )
                encrypted = encrypt_restore_payload(payload, map_password)
                with open(map_path, "wb") as fh:
                    fh.write(encrypted)
                self.write_log(
                    f"ESPORTATO. Mappa cifrata creata con {len(registry.entries())} segnaposto."
                )
            else:
                self.write_log("ESPORTATO.")
        except Exception as e:
            self.logger.error(f"Export failed: {traceback.format_exc()}")
            self.write_log(f"ERRORE export: {type(e).__name__}: {str(e)}")
        finally:
            # Always close ex_doc, even on failure, to release the file
            # handle on tmp_path before we try to remove it (Windows locks
            # open files).
            if ex_doc is not None:
                try:
                    ex_doc.close()
                except Exception as e:
                    self.logger.debug(f"Error closing ex_doc: {e}")
            # Step 5: remove temp file (best-effort).
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError as e:
                self.logger.debug(f"Could not remove temp file {tmp_path}: {e}")


if __name__ == "__main__":
    if platform.system() == "Linux":
        os.environ["QT_LOGGING_RULES"] = "qt.qpa.wayland.*=false"

    app = QApplication(sys.argv)
    app.setDesktopFileName("nullify-pdf")

    try:
        window = NullifyPDF()
        window.show()
        exit_code = app.exec()
    except Exception as e:
        logger = setup_logging()
        logger.error(f"Unhandled exception: {traceback.format_exc()}")
        exit_code = 1
    finally:
        # Final cleanup on exit
        try:
            if 'window' in locals():
                window._cleanup_resources()
        except Exception as e:
            logging.getLogger("nullifypdf").debug(f"Error in final cleanup: {e}")

    sys.exit(exit_code)
