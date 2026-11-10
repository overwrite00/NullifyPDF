import os
import sys
import re
import signal
import datetime
import pathlib
import string
import platform
import logging
import logging.handlers
import traceback
import atexit
import hashlib
import html
import importlib.util
import json
import math
from typing import Optional, List, Set, Dict, Any, Tuple, TypedDict, NotRequired
import pymupdf as fitz
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
    QDialogButtonBox,
    QLineEdit,
    QButtonGroup,
    QGraphicsRectItem,
    QMessageBox,
    QInputDialog,
    QTextBrowser,
)
from PySide6.QtGui import (
    QKeySequence,
    QShortcut,
    QIcon,
    QPixmap,
    QImage,
    QPainter,
    QColor,
    QPen,
    QDragEnterEvent,
    QDropEvent,
)
from PySide6.QtCore import (
    QLocale,
    Qt,
    QThread,
    QObject,
    Signal,
    Slot,
    QRectF,
    QPointF,
    QMutex,
    QMutexLocker,
    QStandardPaths,
    QTimer,
    QUrl,
)
from PySide6.QtGui import QDesktopServices

from privacy_core import (
    PSEUDONYM_STYLES,
    PlaceholderEntry,
    export_pseudonym_key,
    generate_recovery_key,
    import_pseudonym_key,
    parse_recovery_key,
    PlaceholderRegistry,
    PrivacyMode,
    password_strength,
    build_restore_payload,
    decrypt_restore_payload,
    encrypt_restore_payload,
    parse_restore_entries,
    sort_entries_longest_placeholder_first,
)
from pii_detection import (
    ALL_GROUP_IDS,
    ENTITY_GROUPS,
    NON_PRESIDIO_TYPES,
    build_detections,
    build_page_index,
    Candidate,
    classify_page,
    covered_fraction,
    expand_group_ids,
    load_enabled_groups,
    save_enabled_groups,
    whole_word_rects,
)
import update_check
from export_engine import (
    build_audit_record,
    cleanup_stale_temp,
    collect_removed_values,
    export_document,
    name_leaks_value,
    neutral_map_name,
    neutral_output_name,
    private_temp_dir,
    purge_old_logs,
    wipe_local_data,
    write_audit_record,
    write_private_file,
)
from pii_detection import GLYPH_CORE_INSET, core_hits as _core_hits, glyph_core, target_chars
from pdf_sanitize import (
    SanitizePolicy,
    page_image_coverage,
    reveal_hidden_layers,
    suggest_signature_areas,
)
from review_dialog import ReviewDialog
from model_dialog import ModelDialog
from help_guide import GuideDialog, apply_tooltips
from dictionary_dialog import DictionaryDialog
from word_lists import PDFListManager
from word_import import docx_to_pdf
import secure_store
from model_manager import CATALOG, MODEL_CANDIDATES, ModelStore
from onnx_ner import OnnxTokenDetector

# PyMuPDF defines these constants dynamically, which mypy cannot see; read
# them once here (with the suppression) instead of at every call site.
PDF_ANNOT_REDACT: int = fitz.PDF_ANNOT_REDACT  # type: ignore[attr-defined]
PDF_REDACT_IMAGE_PIXELS: int = fitz.PDF_REDACT_IMAGE_PIXELS  # type: ignore[attr-defined]

__version__ = "2.4.0"
__version_prerelease__ = "beta.4"
APP_VERSION = (
    f"{__version__}-{__version_prerelease__}"
    if __version_prerelease__
    else __version__
)


def about_version_text() -> str:
    """Version line of the About dialog; says "Beta" only for prereleases."""
    suffix = " Beta" if __version_prerelease__ else ""
    return f"v{APP_VERSION}{suffix}"


class UpdateCheckWorker(QThread):
    """Fetch the GitHub release list and pick the update (if any)."""

    result_sig = Signal(object)  # release dict, or None when up to date
    error_sig = Signal(str)

    def run(self) -> None:
        try:
            releases = update_check.fetch_releases()
            self.result_sig.emit(update_check.find_update(releases, APP_VERSION))
        except Exception as e:  # network errors, bad JSON, rate limit...
            logging.getLogger("nullifypdf").warning(f"Update check failed: {e}")
            self.error_sig.emit(f"{type(e).__name__}: {e}")


class UpdateDownloadWorker(QThread):
    """Download a release asset into the user's Downloads folder."""

    progress_sig = Signal(int, int)
    done_sig = Signal(str)
    error_sig = Signal(str)

    def __init__(self, url: str, dest: pathlib.Path, size: int, digest: str = "") -> None:
        super().__init__()
        self._digest = digest
        self._url = url
        self._dest = dest
        self._size = size
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            update_check.download_file(
                self._url,
                self._dest,
                expected_size=self._size,
                digest=self._digest,
                progress=lambda d, t: self.progress_sig.emit(d, t),
                cancelled=lambda: self._cancel,
            )
            self.done_sig.emit(str(self._dest))
        except InterruptedError:
            self.error_sig.emit("")
        except Exception as e:
            logging.getLogger("nullifypdf").warning(f"Update download failed: {e}")
            self.error_sig.emit(f"{type(e).__name__}: {e}")


def downloads_folder() -> pathlib.Path:
    """The user's Downloads folder as configured in the running OS.

    Qt resolves it per platform (Windows known folder, XDG user-dirs on
    Linux, ~/Downloads on macOS); fall back to ~/Downloads. The folder is
    not created here: the caller does it when it actually downloads.
    """
    path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    return pathlib.Path(path) if path else pathlib.Path.home() / "Downloads"


class DetectionDict(TypedDict):
    text: str
    entity_type: str
    rects: List[Tuple[float, float, float, float]]
    source: NotRequired[str]
    score: NotRequired[float]
    state: NotRequired[str]
    reasons: NotRequired[List[str]]
    glued: NotRequired[bool]


def setup_logging() -> logging.Logger:
    """Configure file-based logging.

    Respects NULLIFYPDF_DEBUG environment variable for verbose output.

    Returns:
        logging.Logger: Configured logger instance for nullifypdf.
    """
    log_dir = pathlib.Path.home() / ".nullifypdf" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    purge_old_logs(log_dir, max_age_days=30)

    logger = logging.getLogger("nullifypdf")
    debug_mode = os.environ.get("NULLIFYPDF_DEBUG", "").lower() == "true"
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    if logger.handlers:
        return logger

    try:
        # Rotating, so diagnostics are not kept indefinitely (storage
        # limitation); old rotated files are also purged above.
        handler = logging.handlers.RotatingFileHandler(
            log_dir / "nullifypdf.log",
            maxBytes=512 * 1024,
            backupCount=3,
            encoding="utf-8",
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
        base_path = getattr(sys, "_MEIPASS")
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


class RestoreMapMismatch(ValueError):
    """Raised when a restore map's recorded hash doesn't match the PDF."""


REDACTION_FONTNAME = "helv"
# Labels (longest first) drawn on image / signature areas after redaction.
KIND_LABELS: Dict[str, List[str]] = {
    "IMAGE": ["[IMMAGINE RIMOSSA]", "[IMMAGINE]", "[IMG]", "#"],
    "SIGNATURE": ["[FIRMA RIMOSSA]", "[FIRMA]", "[F]", "#"],
}
REDACTION_MAX_FONTSIZE = 8.0
# PyMuPDF's apply_redactions() never inserts replacement text below 4 pt, so
# a smaller floor would only produce text that is silently dropped.
REDACTION_MIN_FONTSIZE = 4.0
# Text written with TextWriter has no such floor.
LABEL_MIN_FONTSIZE = 1.0
LABEL_PREFERRED_MIN_FONTSIZE = 4.0


def fit_redaction_fontsize(
    text: str,
    rect: "fitz.Rect",
    max_size: float = REDACTION_MAX_FONTSIZE,
    min_size: float = REDACTION_MIN_FONTSIZE,
) -> float:
    """Return the largest font size that lays `text` out inside `rect` intact.

    `apply_redactions()` lays its replacement text out as a text *box*: when
    the text is wider than the box it wraps, and MuPDF will happily break in
    the middle of a token, turning ``DATA_001`` into ``DATA_`` + ``001``. The
    result is still perfectly legible on screen but is no longer findable by
    `page.search_for("DATA_001")`, which silently breaks reconstruction. If
    the text cannot be wrapped into the box at all, MuPDF drops it entirely.

    Picking a size that fits up front avoids both outcomes. Wrapping
    *between words* is fine and stays legible, so the size only has to make
    the longest unbreakable token fit the box width; the box must then be
    tall enough for the resulting number of wrapped lines.

    Args:
        text: The replacement string to be stamped into the box.
        rect: The redaction box.
        max_size: Preferred (largest) font size.
        min_size: Floor; returned even if the text still does not fit.

    Returns:
        float: Font size to pass to `add_redact_annot(..., fontsize=...)`.
    """
    tokens = text.split() or [text]
    usable_width = max(1.0, rect.width - 2.0)
    size = max_size
    while size > min_size:
        line_height = size * 1.35
        widest_token = max(
            fitz.get_text_length(token, fontname=REDACTION_FONTNAME, fontsize=size)
            for token in tokens
        )
        total_width = fitz.get_text_length(
            text, fontname=REDACTION_FONTNAME, fontsize=size
        )
        lines_needed = max(1, math.ceil(total_width / usable_width))
        if widest_token <= usable_width and lines_needed * line_height <= rect.height:
            return size
        size -= 0.25
    return min_size


def _placeholder_rects_by_chars(page: Any, placeholder: str) -> List["fitz.Rect"]:
    """Locate a placeholder that `search_for()` cannot find, character by character.

    Fallback for version 1 restore maps (which carry no coordinates) whose
    placeholder was wrapped by `apply_redactions()`. Depending on the
    PyMuPDF version, a wrap can land its pieces on separate *lines* of the
    same text block, or in entirely separate *blocks* (observed with
    PyMuPDF 1.28.2: a narrow box wraps "DATA_001" into a "DATA_" block and a
    separate "001" block). Concatenating only within each block therefore
    still misses it, so this walks every character on the page, in reading
    order, ignoring block/line boundaries entirely.
    """
    rects: List["fitz.Rect"] = []
    try:
        raw = page.get_text("rawdict")
    except Exception:
        return rects
    chars: List[Any] = []
    for block in raw.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                chars.extend(span.get("chars", []))
    if not chars:
        return rects
    text = "".join(ch.get("c", "") for ch in chars)
    start = text.find(placeholder)
    while start != -1:
        matched = chars[start:start + len(placeholder)]
        box = fitz.Rect(matched[0]["bbox"])
        for ch in matched[1:]:
            box |= fitz.Rect(ch["bbox"])
        rects.append(box)
        start = text.find(placeholder, start + len(placeholder))
    return rects


def capture_text_style(page: Any, rect: "fitz.Rect") -> Optional[Dict[str, Any]]:
    """Read the typography of the native text under `rect`.

    Returns ``{font, size, color, flags, origin, text}`` for the line the
    box was taken from, where ``text`` is the text of that line inside the
    box and ``origin`` the baseline start of its first character. Only
    characters on a single baseline whose deletion core the box intersects
    are used, so with tight leading the text of the lines above and below
    (whose boxes overlap this one) is never captured. Returns None when the
    box holds no real text: no span at all, or only an invisible OCR layer
    (GlyphLessFont / render mode 3). That is what distinguishes a native PDF
    from a scanned one.
    """
    try:
        blocks = page.get_text("rawdict", clip=rect).get("blocks", [])
    except Exception:
        return None
    # (baseline y rounded, span, char)
    hits: List[Tuple[float, Dict[str, Any], Dict[str, Any]]] = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if "glyphless" in str(span.get("font", "")).lower():
                    continue
                if span.get("alpha", 255) == 0:
                    continue
                for ch in span.get("chars", []):
                    if not str(ch.get("c", "")).strip():
                        continue
                    if not _core_hits(tuple(ch["bbox"]), rect):
                        continue
                    hits.append((round(float(ch["origin"][1]), 1), span, ch))
    if not hits:
        return None
    centre = (rect.y0 + rect.y1) / 2
    counts: Dict[float, int] = {}
    for base, _sp, _ch in hits:
        counts[base] = counts.get(base, 0) + 1
    # The target line is the baseline nearest the middle of the box among
    # those inside it; with tight leading a neighbour's baseline can also
    # fall inside the box, but never closer to its middle.
    inside = [k for k in counts if rect.y0 <= k <= rect.y1] or list(counts)
    base = min(inside, key=lambda k: (abs(k - centre), -counts[k]))
    chosen = [(sp, ch) for b_, sp, ch in hits if b_ == base]
    chosen.sort(key=lambda t: t[1]["origin"][0])
    spans_used: Dict[int, int] = {}
    for sp, _ch in chosen:
        spans_used[id(sp)] = spans_used.get(id(sp), 0) + 1
    dominant = next(sp for sp, _ in chosen if spans_used[id(sp)] == max(spans_used.values()))
    # Spaces between the selected characters are not in `hits` (they were
    # filtered out above); rebuild them from the horizontal gaps.
    pieces: List[str] = []
    prev_x1: Optional[float] = None
    for _sp, ch in chosen:
        x0, _y0, x1, _y1 = ch["bbox"]
        if prev_x1 is not None and x0 - prev_x1 > 0.25 * float(dominant["size"]):
            pieces.append(" ")
        pieces.append(str(ch["c"]))
        prev_x1 = x1
    first = chosen[0][1]
    return {
        "font": str(dominant.get("font", "")),
        "size": float(dominant["size"]),
        "color": int(dominant.get("color", 0)),
        "flags": int(dominant.get("flags", 0)),
        "origin": [float(first["origin"][0]), float(first["origin"][1])],
        "text": "".join(pieces).strip(),
    }


def band_covers_target(page: Any, band: "fitz.Rect", full: "fitz.Rect") -> bool:
    """True when `band` reaches the deletion core of every target character.

    A glyph that is smaller or higher than the rest of its word (a
    superscript, a trailing digit) could keep its core outside a thin band
    and survive the redaction.
    """
    chars = target_chars(page, full)
    # An empty clipped result is not proof of coverage.  A band trimmed
    # against neighbouring lines can otherwise leave part of the glyph.
    return bool(chars) and all(_core_hits(tuple(ch["bbox"]), band) for ch in chars)


def text_under_rect(page: Any, rect: "fitz.Rect") -> str:
    """The text a box was drawn over, without neighbouring lines' fragments.

    `get_text(clip=...)` follows a different rule from glyph deletion and, with
    tight leading, returns pieces of the lines above and below. Native text is
    read from a single baseline (see capture_text_style); the plain clip text
    is only the fallback for scanned / image pages.
    """
    style = capture_text_style(page, rect)
    if style and style.get("text"):
        return " ".join(str(style["text"]).split())
    return " ".join(page.get_text("text", clip=rect).split())


_BASE14 = {
    # (family, bold, italic) -> Base-14 font code
    ("sans", False, False): "helv", ("sans", True, False): "hebo",
    ("sans", False, True): "heit", ("sans", True, True): "hebi",
    ("serif", False, False): "tiro", ("serif", True, False): "tibo",
    ("serif", False, True): "tiit", ("serif", True, True): "tibi",
    ("mono", False, False): "cour", ("mono", True, False): "cobo",
    ("mono", False, True): "coit", ("mono", True, True): "cobi",
}
_SERIF_HINTS = (
    "times", "serif", "georgia", "cambria", "garamond", "book", "palatino", "minion",
)


def _strip_subset_prefix(name: str) -> str:
    return re.sub(r"^[A-Z]{6}\+", "", name or "").lower()


def _same_face(basefont: str, wanted: str) -> bool:
    """Loose font-name match: ignores subset prefix, case and punctuation."""
    def norm(name: str) -> str:
        n = re.sub(r"[^a-z0-9]", "", _strip_subset_prefix(name))
        return re.sub(r"(regular|mt|ps)$", "", n)

    a, b = norm(basefont), norm(wanted)
    return bool(a) and bool(b) and (a == b or a.startswith(b) or b.startswith(a))


def closest_base14(style: Dict[str, Any]) -> str:
    """Pick the Base-14 font code closest to the original face."""
    name = _strip_subset_prefix(str(style.get("font", "")))
    flags = int(style.get("flags", 0))
    if "mono" in name or "courier" in name or "consolas" in name or flags & 8:
        family = "mono"
    elif "sans" not in name and (flags & 4 or any(k in name for k in _SERIF_HINTS)):
        family = "serif"
    else:
        family = "sans"
    bold = bool(flags & 16) or any(k in name for k in ("bold", "black", "heavy"))
    italic = bool(flags & 2) or any(k in name for k in ("italic", "oblique"))
    return _BASE14[(family, bold, italic)]


def resolve_font(
    doc: Any, page: Any, style: Dict[str, Any], text: str
) -> Tuple["fitz.Font", str]:
    """Return ``(font, description)`` for restoring `text` in `style`.

    Prefers the original embedded font when the file still carries it and it
    has a glyph for every character; otherwise the closest Base-14 face.
    """
    wanted = _strip_subset_prefix(str(style.get("font", "")))
    if wanted:
        try:
            for entry in page.get_fonts(full=True):
                xref, basefont = entry[0], str(entry[3])
                if xref <= 0 or not _same_face(basefont, wanted):
                    continue
                _name, ext, _type, buffer = doc.extract_font(xref)
                if not buffer or ext in ("", "n/a"):
                    continue
                font = fitz.Font(fontbuffer=buffer)
                if all(font.has_glyph(ord(ch)) for ch in text if not ch.isspace()):
                    return font, f"embedded:{basefont}"
        except Exception:
            pass
    code = closest_base14(style)
    return fitz.Font(code), f"base14:{code}"


def write_styled_text(
    doc: Any, page: Any, rect: "fitz.Rect", text: str, style: Dict[str, Any]
) -> None:
    """Write `text` with the original size, colour, baseline and closest font."""
    font, used = resolve_font(doc, page, style, text)
    logging.getLogger("nullifypdf").debug(
        "Reconstruction font: original=%s used=%s", style.get("font"), used
    )
    size = float(style["size"])
    color = fitz.sRGB_to_pdf(int(style.get("color", 0)))
    origin = fitz.Point(style["origin"][0], style["origin"][1])
    width = font.text_length(text, fontsize=size)
    usable = max(1.0, rect.width + 1.0)
    writer = fitz.TextWriter(page.rect)
    if width <= usable:
        writer.append(origin, text, font=font, fontsize=size)
    else:
        # Wider in the fallback font (or a multi-line original): shrink a
        # little, and wrap inside the box if it still does not fit.
        scaled = max(LABEL_MIN_FONTSIZE, size * usable / width)
        if font.text_length(text, fontsize=scaled) <= usable:
            writer.append(origin, text, font=font, fontsize=scaled)
        else:
            writer.fill_textbox(rect, text, font=font, fontsize=scaled, align=0)
    writer.write_text(page, color=color)


def compact_labels(placeholder: str) -> List[str]:
    """Shorter stand-ins for a placeholder, longest first (full one first)."""
    head, _, tail = placeholder.rpartition("_")
    if not head or not tail:
        return [placeholder]
    out = [placeholder, f"{head[:1]}{tail}", tail, f"#{tail[:2]}"]
    seen: List[str] = []
    for item in out:
        if item not in seen:
            seen.append(item)
    return seen


def write_label(
    page: Any,
    rect: "fitz.Rect",
    labels: List[str],
    *,
    style: Optional[Dict[str, Any]] = None,
    allowance: float = 0.0,
    max_size: float = REDACTION_MAX_FONTSIZE,
) -> str:
    """Draw the first of `labels` that is legible inside the box; return it.

    Drawn with TextWriter after apply_redactions(), so there is no 4 pt
    floor and no silent drop. A label may extend past the box to the right by
    `allowance` points (free space on the same line). Preference: the longest
    label that fits at 4 pt or more; otherwise the shortest at whatever size
    fits (down to 1 pt).
    """
    font = fitz.Font(REDACTION_FONTNAME)
    # A band squeezed between tight lines is short: keep the label inside it.
    max_size = min(max_size, max(LABEL_MIN_FONTSIZE, rect.height * 0.9))
    usable = max(1.0, rect.width - 1.0 + allowance)
    chosen = labels[-1]
    size = LABEL_MIN_FONTSIZE
    for lab in labels:
        full = font.text_length(lab, fontsize=1.0)
        fit = min(max_size, usable / full) if full > 0 else max_size
        if fit >= LABEL_PREFERRED_MIN_FONTSIZE:
            chosen, size = lab, fit
            break
    else:
        full = font.text_length(chosen, fontsize=1.0)
        size = max(LABEL_MIN_FONTSIZE, min(max_size, usable / full if full else max_size))
    if style and style.get("origin"):
        base_y = float(style["origin"][1])
    else:
        base_y = rect.y0 + (rect.height + size * 0.7) / 2
    writer = fitz.TextWriter(page.rect)
    writer.append(fitz.Point(rect.x0 + 0.5, base_y), chosen, font=font, fontsize=size)
    writer.write_text(page, color=(0, 0, 0))
    return chosen


def free_space_right(page: Any, rect: "fitz.Rect", limit: float = 40.0) -> float:
    """Free width to the right of `rect` on the same line (after redaction)."""
    gap = limit
    for w in page.get_text("words"):
        overlap = min(rect.y1, w[3]) - max(rect.y0, w[1])
        if overlap < 0.5 * min(rect.height, w[3] - w[1]):
            continue
        if w[0] >= rect.x1 - 0.5:
            gap = min(gap, w[0] - rect.x1 - 1.0)
    return max(0.0, gap)


def _restore_targets(
    page: Any, entry: PlaceholderEntry
) -> List[Tuple["fitz.Rect", Optional[Dict[str, Any]]]]:
    """Return the ``(box, style)`` pairs on `page` that should get `entry.original` back.

    Prefers the coordinates recorded in the restore map (version 2+), which
    are the boxes the original value was taken from, so the value fits back
    into them. Falls back to text search only for version 1 maps.
    """
    stored = [
        (fitz.Rect(occurrence.rect), occurrence.style)
        for occurrence in entry.occurrences
        if occurrence.page == page.number
    ]
    if stored:
        return stored
    hits = list(page.search_for(entry.placeholder))
    if not hits:
        hits = _placeholder_rects_by_chars(page, entry.placeholder)
    return [(hit, None) for hit in hits]


def reconstruct_pdf(in_path: str, out_path: str, payload: Dict[str, Any]) -> int:
    """Rebuild a pseudonymized PDF's original values from a decrypted restore map.

    Replaces every placeholder occurrence (e.g. ``PERSON_001``) with the
    original value, using the same add_redact_annot()-then-apply_redactions()
    mechanism used to create the placeholders during export. Does not restore
    the original layout: a placeholder's redaction box is sized for the
    placeholder text, so a longer original value may be visually clipped or
    crowd the box.

    Uses the redaction boxes recorded in the restore map (version 2+) and
    only falls back to searching for the placeholder text with version 1
    maps, which carry no coordinates.

    Args:
        in_path: Path to the pseudonymized PDF to reconstruct from.
        out_path: Path to write the reconstructed PDF to.
        payload: Decrypted restore-map payload (see `privacy_core.build_restore_payload`).

    Returns:
        int: Number of placeholder occurrences whose original value was
            **verified present** in the saved output. The count is taken
            from the written file, not from the number of redactions
            requested, so a value that `apply_redactions()` silently
            dropped is never reported as restored.

    Raises:
        ValueError: If the payload is not a recognized restore map.
        RestoreMapMismatch: If `output_sha256` in the payload does not match
            the SHA-256 of `in_path`.
    """
    expected_sha256 = payload.get("output_sha256")
    if expected_sha256 and sha256_file(in_path) != expected_sha256:
        raise RestoreMapMismatch(
            "La mappa di ripristino non corrisponde a questo PDF "
            "(hash SHA-256 diverso)."
        )

    entries = sort_entries_longest_placeholder_first(parse_restore_entries(payload))
    # (page index, box, original value) for every restoration we attempted,
    # so the saved output can be checked against it below.
    attempted: List[Tuple[int, fitz.Rect, str]] = []
    doc = fitz.open(in_path)
    try:
        for page in doc.pages():
            claimed: List[fitz.Rect] = []
            styled: List[Tuple[fitz.Rect, str, Dict[str, Any]]] = []
            plain: List[Tuple[fitz.Rect, str]] = []
            for entry in entries:
                for rect, style in _restore_targets(page, entry):
                    # Entries are sorted longest-placeholder-first, so a
                    # shorter placeholder must not re-redact a box a longer
                    # one already claimed: searching for PERSON_001 also hits
                    # the first ten characters of a rendered PERSON_0010, and
                    # that hit sits *inside* the longer one's box.
                    # Containment, not intersection: two separate fields the
                    # user boxed side by side may legitimately touch, and
                    # skipping the second would drop a value.
                    if any(taken.contains(rect) for taken in claimed):
                        continue
                    claimed.append(fitz.Rect(rect))
                    if style:
                        # Native text: blank the box now, write the value in
                        # its original typography after apply_redactions()
                        # (which would otherwise erase it).
                        text = entry.original  # never the captured clip text
                        page.add_redact_annot(rect, fill=(1, 1, 1))
                        styled.append((fitz.Rect(rect), text, style))
                        attempted.append((page.number, fitz.Rect(rect), text))
                        continue
                    page.add_redact_annot(rect, fill=(1, 1, 1))
                    plain.append((fitz.Rect(rect), entry.original))
                    attempted.append((page.number, fitz.Rect(rect), entry.original))
            page.apply_redactions(images=PDF_REDACT_IMAGE_PIXELS, graphics=True)
            for rect, text, style in styled:
                write_styled_text(doc, page, rect, text, style)
            for rect, text in plain:
                write_label(page, rect, [text])
        doc.save(out_path, garbage=4, deflate=True, clean=True)
    finally:
        doc.close()

    return _verify_restored(out_path, attempted)


def expected_restore_count(payload: Dict[str, Any]) -> int:
    """Return how many placeholder occurrences a restore map should put back.

    Counts occurrences, not entries: one entry can carry several boxes (the
    same value redacted on more than one page), and `reconstruct_pdf`
    returns restored *occurrences*. Comparing its result against the entry
    count would hide a partial restore -- which is exactly the repeated-value
    case reconstruction has already gone wrong on once.
    """
    return sum(
        max(1, len(entry.occurrences)) for entry in parse_restore_entries(payload)
    )


def _verify_restored(
    out_path: str, attempted: List[Tuple[int, "fitz.Rect", str]]
) -> int:
    """Count how many attempted restorations actually landed in the output.

    `apply_redactions()` drops its replacement text silently when the text
    cannot be laid out inside the box, so counting the redactions we asked
    for would over-report: the feature would claim to have restored values
    it had in fact destroyed. Read the answer back off the written file.
    """
    logger = logging.getLogger("nullifypdf")
    restored = 0
    doc = fitz.open(out_path)
    try:
        for page_number, rect, original in attempted:
            probe = fitz.Rect(rect) + (-2, -2, 2, 2)
            # Whitespace-insensitive: a long value legitimately wraps onto
            # several lines inside its box. What matters is that its
            # characters are back on the page, not how they are broken up.
            found = "".join(doc[page_number].get_text("text", clip=probe).split())
            if "".join(original.split()) in found:
                restored += 1
            else:
                logger.warning(
                    "Reconstruction: value not restored on page %s at %s "
                    "(it did not fit its redaction box).",
                    page_number + 1,
                    tuple(round(v, 1) for v in (rect.x0, rect.y0, rect.x1, rect.y1)),
                )
    finally:
        doc.close()
    return restored


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
QListWidget, QTableWidget, QTextBrowser { background-color: #0f172a; border: 1px solid #334155; border-radius: 4px; color: #cbd5e1; gridline-color: #334155; selection-background-color: #0284c7; selection-color: white; }
QListWidget::item { padding: 6px; }
QHeaderView::section { background-color: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 4px; }
QComboBox, QDoubleSpinBox { background-color: #0f172a; border: 1px solid #334155; border-radius: 4px; padding: 4px; color: #e2e8f0; }
QComboBox QAbstractItemView { background-color: #0f172a; color: #e2e8f0; selection-background-color: #0284c7; }
QTabWidget::pane { border: 1px solid #334155; }
QTabBar::tab { background-color: #1e293b; color: #cbd5e1; padding: 6px 14px; border: 1px solid #334155; }
QTabBar::tab:selected { background-color: #0284c7; color: white; }
QToolTip { background-color: #1e293b; color: #e2e8f0; border: 1px solid #0ea5e9; padding: 4px; }
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
        self.model_detectors: List[Tuple[str, OnnxTokenDetector]] = []
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
            self.model_detectors.clear()
        except Exception as e:
            logging.getLogger("nullifypdf").debug(f"Error during AI cleanup: {e}")

    @Slot(object, object, str, list, set, bool, object, list, bool)
    def run_scan(self, doc: Any, doc_mutex: Any, choice: str,
                 compiled_allowlist: List[Tuple[str, Any]],
                 allowlist_set: Set[str], use_ocr: bool,
                 tessdata_dir: Optional[str],
                 enabled_types: List[str],
                 health_mode: bool = False) -> None:
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
            enabled_types: Presidio entity types the user chose to detect.
            health_mode: Health-document profile: no uncertain hit is dropped
                silently, it becomes a suggestion for review instead.
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
                self.log_sig.emit(f"Inizializzazione motore di rilevamento ({choice})...")
                from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
                from presidio_analyzer.nlp_engine import NlpEngineProvider
                from presidio_analyzer.predefined_recognizers import PhoneRecognizer

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
                nlp_engine = provider.create_engine()

                registry = RecognizerRegistry(supported_languages=target_langs)
                registry.load_predefined_recognizers(
                    languages=target_langs, nlp_engine=nlp_engine
                )
                # Presidio's default PhoneRecognizer regions
                # (US/UK/DE/FR/IL/IN/CA/BR) omit Italy, so Italian numbers
                # without an explicit "+39" prefix (e.g. mobile "340 1234567"
                # or landline "02 1234567") are never matched. Replace it
                # with an IT-aware instance for each loaded language.
                phone_regions = PhoneRecognizer.DEFAULT_SUPPORTED_REGIONS + ("IT",)
                registry.recognizers = [
                    r for r in registry.recognizers
                    if not isinstance(r, PhoneRecognizer)
                ]
                for lang in target_langs:
                    registry.recognizers.append(
                        PhoneRecognizer(
                            supported_language=lang, supported_regions=phone_regions
                        )
                    )

                self.analyzer = AnalyzerEngine(
                    nlp_engine=nlp_engine,
                    registry=registry,
                    supported_languages=target_langs,
                )
                self.loaded_langs = target_langs
            self.log_sig.emit("Scansione privacy in corso...")
            self._load_local_detectors()
            targets = list(enabled_types)
            presidio_targets = [
                t for t in targets if t not in NON_PRESIDIO_TYPES
            ]
            allow_terms = sorted(
                set(allowlist_set) | {a for a, _ in compiled_allowlist}
            )

            # Determine page count under mutex (cheap, but doc may be replaced
            # mid-flight by load_path if not for the disabled UI during scan).
            with QMutexLocker(doc_mutex):
                total_pages = len(doc)

            totals: Dict[str, int] = {}
            n_suggested = 0
            for i in range(total_pages):
                if self._stop_requested:
                    break
                # Extract text in worker thread (off the UI thread) under mutex
                # because UI thread renders / mutates annotations on the same doc.
                used_ocr = False
                has_images = False
                textpage = None
                signature_dets: List[Dict[str, Any]] = []
                with QMutexLocker(doc_mutex):
                    try:
                        page = doc[i]
                        text = page.get_text()
                        needs_ocr = use_ocr and self._page_needs_ocr(page, text)
                        coverage = page_image_coverage(page)
                        has_images = coverage > 0.0
                        words = page.get_text("words")
                        if needs_ocr:
                            self.log_sig.emit(f"OCR pagina {i + 1}...")
                            textpage = page.get_textpage_ocr(
                                language=ocr_language,
                                dpi=300,
                                full=True,
                                tessdata=tessdata_dir,
                            )
                            words = page.get_text("words", textpage=textpage)
                            used_ocr = True
                        elif use_ocr and tessdata_dir and coverage >= 0.03:
                            # Text page with embedded images (stamps, scanned
                            # attachments): OCR the images only and merge.
                            self.log_sig.emit(f"OCR immagini pagina {i + 1}...")
                            textpage = page.get_textpage_ocr(
                                language=ocr_language,
                                dpi=300,
                                full=False,
                                tessdata=tessdata_dir,
                            )
                            words = page.get_text("words", textpage=textpage)
                            used_ocr = True
                        index = build_page_index(
                            words, ocr=used_ocr,
                            image_rects=[
                                tuple(i["bbox"])
                                for i in page.get_image_info(hashes=False)
                            ],
                        )
                        if health_mode:
                            signature_dets = suggest_signature_areas(page)
                        if index.collisions:
                            self.log_sig.emit(
                                f"Avviso: interlinea molto stretta a pagina "
                                f"{i + 1}: {index.collisions} parole vicine "
                                "potrebbero essere danneggiate. Controlla l'anteprima."
                            )
                    except Exception as e:
                        self.log_sig.emit(
                            f"Avviso: estrazione testo/OCR fallita pagina {i+1}: {e}"
                        )
                        index = build_page_index([])
                results: List[Any] = []
                verb_like: Set[str] = set()
                for lang in self.loaded_langs:
                    if not presidio_targets or not index.text:
                        break
                    artifacts = None
                    try:
                        artifacts = self.analyzer.nlp_engine.process_text(
                            index.text, lang
                        )
                    except Exception:
                        artifacts = None
                    res = self.analyzer.analyze(
                        text=index.text, entities=presidio_targets,
                        language=lang, nlp_artifacts=artifacts,
                    )
                    results.extend(res)
                    verb_like |= self._first_person_verbs(artifacts)
                candidates, stats = classify_page(
                    results, index, targets,
                    used_ocr=used_ocr, health_mode=health_mode,
                    verb_like=verb_like,
                )
                detections = build_detections(
                    index, candidates, allowlist=allow_terms,
                    source="ocr" if used_ocr else "text", stats=stats,
                )
                model_candidates: List[Tuple[Candidate, str]] = []
                for model_id, detector in self.model_detectors:
                    try:
                        for entity in detector.detect(index.text):
                            entity_type = entity.label
                            if entity_type not in targets:
                                continue
                            model_candidates.append((
                                Candidate(
                                    entity.start,
                                    entity.end,
                                    entity.text,
                                    entity_type,
                                    min(1.0, max(0.0, entity.score)),
                                    state="suggested",
                                    reasons=[f"model:{model_id}"],
                                ),
                                model_id,
                            ))
                    except Exception as exc:
                        self.log_sig.emit(f"Avviso: modello locale {model_id} non disponibile a pagina {i + 1}: {exc}")
                for candidate, model_id in model_candidates:
                    model_detections = build_detections(
                        index,
                        [candidate],
                        allowlist=allow_terms,
                        source=f"model:{model_id}",
                        stats=stats,
                    )
                    detections.extend(model_detections)
                detections.extend(signature_dets)
                for key, n in stats.items():
                    totals[key] = totals.get(key, 0) + n
                n_suggested += sum(1 for d in detections if d.get("state") == "suggested")
                self.page_done_sig.emit(i, detections)
                self.progress_sig.emit(i + 1, total_pages)
            if not self._stop_requested:
                if totals:
                    summary = ", ".join(f"{k}={v}" for k, v in sorted(totals.items()))
                    logging.getLogger("nullifypdf").info(
                        f"Scan discards (no values): {summary}"
                    )
                msg = "Scansione completata."
                if n_suggested:
                    msg += f" {n_suggested} suggerimenti da rivedere."
                self.log_sig.emit(msg)
        except Exception as e:
            # Log full traceback to file for diagnostics; show only summary in UI
            logging.getLogger("nullifypdf").error(
                f"AI scan error: {traceback.format_exc()}"
            )
            self.log_sig.emit(f"ERRORE rilevamento: {type(e).__name__}: {str(e)}")
        finally:
            self.finished_sig.emit()

    @staticmethod
    def _first_person_verbs(artifacts: Any) -> Set[str]:
        """Lowercase first-person finite verb forms spaCy found on the page.

        A weak signal only: the grammar tags of capitalised words are not
        reliable enough to reject a hit on their own.
        """
        out: Set[str] = set()
        try:
            for tok in artifacts.tokens:
                if tok.pos_ in ("VERB", "AUX") and "Person=1" in str(tok.morph):
                    out.add(tok.text.lower())
        except Exception:
            return set()
        return out

    def _load_local_detectors(self) -> None:
        """Load every installed, manifest-verified local model once per scan."""
        if self.model_detectors:
            return
        store = ModelStore(pathlib.Path.home() / ".nullifypdf" / "models")
        for manifest in CATALOG:
            if not manifest.enabled or not store.is_installed(manifest):
                continue
            try:
                self.model_detectors.append(
                    (manifest.model_id, OnnxTokenDetector(store.model_dir(manifest), manifest))
                )
                self.log_sig.emit(f"Modello locale caricato: {manifest.model_id}")
            except Exception as exc:
                self.log_sig.emit(f"Avviso: modello locale {manifest.model_id} ignorato: {exc}")

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
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.start_pos: Optional[QPointF] = None
        self.temp_rect: Optional[QGraphicsRectItem] = None

    def mousePressEvent(self, event: Any) -> None:
        """Handle mouse press: start selection rectangle on left-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            sp = self.mapToScene(event.position().toPoint())
            self.start_pos = sp
            self.temp_rect = QGraphicsRectItem(QRectF(sp, sp))
            self.temp_rect.setPen(QPen(QColor("#ef4444"), 2))
            self.scene().addItem(self.temp_rect)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        """Update in-progress selection rectangle while dragging."""
        if self.start_pos and self.temp_rect:
            ep = self.mapToScene(event.position().toPoint())
            self.temp_rect.setRect(QRectF(self.start_pos, ep).normalized())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        """Finalize the gesture: a small movement is a click (point_clicked),
        a larger one is a drawn selection (rect_drawn). Deferring both to
        release, based on the final swept distance, keeps them mutually
        exclusive so a drag never also fires a click mid-gesture.
        """
        if event.button() == Qt.MouseButton.LeftButton and self.temp_rect:
            rect = self.temp_rect.rect()
            start = self.start_pos
            self.scene().removeItem(self.temp_rect)
            self.temp_rect = None
            self.start_pos = None
            if rect.width() > 5 and rect.height() > 5:
                self.rect_drawn.emit(rect)
            elif start is not None:
                self.point_clicked.emit(start)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: Any) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.zoom_req.emit(1 if event.angleDelta().y() > 0 else -1)
            event.accept()
        else:
            super().wheelEvent(event)


class SuggestionItem(QGraphicsRectItem):
    """Scene-only outline of a pending suggestion.

    It lives in the graphics scene, never in the document: it cannot reach an
    export or a print, and it becomes a redaction only through the
    "Censura" decision.
    """

    def __init__(self, rect_pdf: Tuple[float, ...], suggestion: Dict[str, Any], scale: float) -> None:
        r = rect_pdf
        super().__init__(QRectF(r[0] * scale, r[1] * scale, (r[2] - r[0]) * scale, (r[3] - r[1]) * scale))
        self.suggestion = suggestion
        pen = QPen(QColor("#f97316"), 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QColor(249, 115, 22, 40))
        self.setZValue(10)
        self.setToolTip(
            f"Suggerimento: {suggestion.get('entity_type', '')} "
            f"({float(suggestion.get('score', 0.0)):.2f}) - clic per decidere"
        )

    def set_highlight(self, on: bool) -> None:
        pen = QPen(QColor("#f97316"), 4 if on else 2)
        pen.setStyle(Qt.PenStyle.SolidLine if on else Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self.setPen(pen)


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

    start_scan_sig = Signal(object, object, str, list, set, bool, object, list, bool)

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
        # Detections the evidence score could not settle; never applied
        # silently, reviewed by the user (see review_dialog.ReviewDialog).
        self.pending_suggestions: List[Dict[str, Any]] = []
        self._export_labels: List[Tuple[int, Any, List[str], Optional[Dict[str, Any]], Optional[str]]] = []
        self.config_dir = pathlib.Path.home() / ".nullifypdf"
        # Update-check threads outlive their dialogs: keep them referenced
        # until they finish so a QThread is never destroyed while running.
        self._bg_threads: Set[QThread] = set()
        cleanup_stale_temp(self.config_dir)
        self.list_manager = PDFListManager(self.config_dir)
        self.blocklist = self.list_manager.load_blocklist()
        self.allowlist = self.list_manager.load_allowlist()
        if self.list_manager.keystore_error:
            self.logger.error("Word lists unreadable: keystore unavailable")
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
        apply_tooltips(self)
        self._f1 = QShortcut(QKeySequence("F1"), self)
        self._f1.activated.connect(self.cmd_guide)
        if self.list_manager.expired_removed:
            self.write_log(
                f"Rimossi {self.list_manager.expired_removed} termini scaduti dai dizionari."
            )
        if self.list_manager.keystore_error:
            self.write_log(
                "Avviso: dizionari cifrati non leggibili su questo account/PC; "
                "verranno usati dizionari vuoti finché non vengono ripristinati."
            )
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
        for t in list(self._bg_threads):
            cancel = getattr(t, "cancel", None)
            if cancel is not None:
                cancel()
            if t.isRunning():
                t.wait(12000)
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
        s_lay.addWidget(QLabel("Privacy Edition\n"))
        btn_open = QPushButton("Apri PDF")
        btn_open.setObjectName("Primary")
        btn_open.clicked.connect(self.cmd_open)
        s_lay.addWidget(btn_open)
        s_lay.addSpacing(20)
        s_lay.addWidget(QLabel("Modello lingua:"))
        lang_lay = QHBoxLayout()
        self.rb_en = QRadioButton("EN")
        self.rb_it = QRadioButton("IT")
        self.rb_both = QRadioButton("BOTH")
        # Default to the interface language: running the English model on
        # Italian text only adds false positives.
        if QLocale.system().language() == QLocale.Language.Italian:
            self.rb_it.setChecked(True)
        else:
            self.rb_both.setChecked(True)
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
        self.chk_sugg = QCheckBox("Mostra suggerimenti")
        self.chk_sugg.setChecked(True)
        self.chk_sugg.setToolTip("Contorna in arancione, nell'anteprima, i suggerimenti da rivedere.")
        self.chk_sugg.toggled.connect(lambda _on: self.render_page())
        s_lay.addWidget(self.chk_sugg)
        self.chk_health = QCheckBox("Profilo documenti sanitari")
        self.chk_health.setToolTip(
            "Rileva anche date di nascita e identificativi sanitari e non "
            "scarta in silenzio i casi incerti: li propone in revisione."
        )
        s_lay.addWidget(self.chk_health)
        self.chk_mask_width = QCheckBox("Maschera larghezza testo rimosso")
        self.chk_mask_width.setToolTip(
            "Arrotonda lo spazio lasciato dal testo rimosso, che altrimenti "
            "ne rivela la larghezza. Puo spostare di poco il testo seguente."
        )
        s_lay.addWidget(self.chk_mask_width)
        s_lay.addSpacing(20)
        btn_dict = QPushButton("Dizionari")
        btn_dict.clicked.connect(self.cmd_dict)
        s_lay.addWidget(btn_dict)
        btn_models = QPushButton("Modelli locali")
        btn_models.setObjectName("model_settings")
        btn_models.clicked.connect(self.cmd_models)
        s_lay.addWidget(btn_models)
        self.btn_ai = QPushButton("Auto Redact")
        self.btn_ai.setObjectName("Danger")
        self.btn_ai.clicked.connect(self.cmd_auto_ai)
        s_lay.addWidget(self.btn_ai)
        self.btn_review = QPushButton("Rivedi suggerimenti (0)")
        self.btn_review.clicked.connect(self._review_suggestions)
        self.btn_review.setEnabled(False)
        s_lay.addWidget(self.btn_review)
        btn_clear = QPushButton("Pulisci Pagina")
        btn_clear.clicked.connect(self.cmd_clear)
        s_lay.addWidget(btn_clear)
        s_lay.addSpacing(20)
        btn_export = QPushButton("Esporta PDF")
        btn_export.setStyleSheet("border-color: #0ea5e9; color: #0ea5e9;")
        btn_export.clicked.connect(self.cmd_export)
        s_lay.addWidget(btn_export)
        btn_reconstruct = QPushButton("Ricostruisci PDF")
        btn_reconstruct.clicked.connect(self.cmd_reconstruct)
        s_lay.addWidget(btn_reconstruct)
        btn_wipe = QPushButton("Elimina dati locali")
        btn_wipe.setToolTip(
            "Cancella log, registri di esportazione e file temporanei salvati "
            "in ~/.nullifypdf."
        )
        btn_wipe.clicked.connect(self.cmd_wipe_local_data)
        s_lay.addWidget(btn_wipe)
        s_lay.addStretch()
        btn_guide = QPushButton("Guida")
        btn_guide.clicked.connect(self.cmd_guide)
        s_lay.addWidget(btn_guide)
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
        self.lbl_zoom.setObjectName("lbl_zoom")
        btn_zin = QPushButton("+")
        btn_zin.clicked.connect(lambda: self.adjust_zoom(1))
        tb_lay.addWidget(btn_zout)
        tb_lay.addWidget(self.lbl_zoom)
        tb_lay.addWidget(btn_zin)
        tb_lay.addSpacing(20)
        btn_prev = QPushButton("<")
        btn_prev.clicked.connect(lambda: self.move_page(-1))
        self.le_page = QLineEdit("0")
        self.le_page.setObjectName("le_page")
        self.le_page.setFixedWidth(40)
        self.le_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.le_page.returnPressed.connect(self.jump_page)
        self.lbl_tot = QLabel("/ 0")
        self.lbl_tot.setObjectName("lbl_tot")
        btn_next = QPushButton(">")
        btn_next.clicked.connect(lambda: self.move_page(1))
        tb_lay.addWidget(btn_prev)
        tb_lay.addWidget(self.le_page)
        tb_lay.addWidget(self.lbl_tot)
        tb_lay.addWidget(btn_next)
        r_lay.addWidget(top_bar)
        self.scene = QGraphicsScene()
        self.view = PDFView(self.scene)
        self.view.setObjectName("view")
        self.view.rect_drawn.connect(self.user_draw_rect)
        self.view.point_clicked.connect(self.user_click_pt)
        self.view.zoom_req.connect(self.adjust_zoom)
        r_lay.addWidget(self.view, stretch=1)
        footer = QWidget()
        footer.setObjectName("Panel")
        f_lay = QVBoxLayout(footer)
        self.prog = QProgressBar()
        self.prog.setObjectName("prog")
        self.prog.setValue(0)
        self.log = QTextEdit()
        self.log.setObjectName("log")
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

    def cmd_models(self) -> None:
        """Show the curated local-model catalog and its verification state."""
        store = ModelStore(self.config_dir / "models")
        ModelDialog(
            MODEL_CANDIDATES,
            manifests=CATALOG,
            store=store,
            parent=self,
        ).exec()

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
        p, _ = QFileDialog.getOpenFileName(
            self, "Apri documento", "", "PDF e Word (*.pdf *.docx);;PDF (*.pdf);;Word DOCX (*.docx)"
        )
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
        suffix = pathlib.Path(path).suffix.lower()
        if suffix not in {".pdf", ".docx"}:
            self.write_log("ERRORE: Sono supportati solo PDF e Word DOCX")
            return

        try:
            imported_word = suffix == ".docx"
            tdoc = docx_to_pdf(path) if imported_word else fitz.open(path)
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
                self.pending_suggestions = []
            self._update_review_button()
            self.adjust_zoom(0)
            label = "Word DOCX convertito in PDF locale" if imported_word else "PDF"
            self.write_log(f"Caricato {label}: {os.path.basename(path)}")
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
            QMessageBox.information(
                self,
                "PDF scansionato rilevato",
                f"Questo documento sembra scansionato (nessun testo trovato "
                f"nelle pagine {preview}{suffix}).\n\n"
                'Puoi comunque selezionare manualmente le aree da censurare. '
                'Per il riconoscimento automatico dei dati personali, attiva '
                'prima "OCR PDF scansionati" e poi avvia "Auto Redact".',
            )

    def render_page(self) -> None:
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
            pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888
        ).copy()
        self.scene.clear()
        self.scene.addPixmap(QPixmap.fromImage(img))
        self.scene.setSceneRect(0, 0, pix.width, pix.height)
        self.le_page.setText(str(self.page_num + 1))
        self.lbl_tot.setText(f"/ {total}")
        self._draw_suggestion_overlays()

    def _draw_suggestion_overlays(self) -> None:
        """Outline the pending suggestions of the current page (view only)."""
        if not self.chk_sugg.isChecked():
            return
        for s in self.pending_suggestions:
            if int(s.get("page", -1)) != self.page_num:
                continue
            # The clamped band is internal redaction geometry.  Showing it
            # makes a correctly detected word appear partially selected.
            for rect in s.get("full_rects") or s.get("rects") or []:
                self.scene.addItem(SuggestionItem(tuple(rect), s, self.scale))

    def _highlight_suggestion(self, suggestion: Any) -> None:
        for it in self.scene.items():
            if isinstance(it, SuggestionItem):
                it.set_highlight(it.suggestion is suggestion)

    def _decide_suggestion(self, s: Dict[str, Any]) -> None:
        """Accept or discard one suggestion clicked in the page view."""
        reveal = False
        while True:
            value = " ".join(str(s.get("text", "")).split())
            shown = "(area grafica)" if not value else (value if reveal else value[:1] + "•" * min(len(value) - 1, 8))
            box = QMessageBox(self)
            box.setWindowTitle("Suggerimento")
            box.setText(
                f"{s.get('entity_type', '')} - {shown}\n"
                f"Punteggio {float(s.get('score', 0.0)):.2f}: "
                + ", ".join(str(r) for r in s.get("reasons", []))
            )
            b_yes = box.addButton("Censura", QMessageBox.ButtonRole.AcceptRole)
            b_no = box.addButton("Scarta", QMessageBox.ButtonRole.DestructiveRole)
            b_show = box.addButton("Mostra valore", QMessageBox.ButtonRole.ActionRole)
            b_yes.setToolTip("Applica la censura a questo suggerimento.")
            b_no.setToolTip("Scarta il suggerimento senza censurare nulla.")
            b_show.setToolTip("Mostra il valore in chiaro prima di decidere.")
            box.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked == b_show and value and not reveal:
                reveal = True
                continue
            break
        if clicked not in (b_yes, b_no):
            return
        if clicked == b_yes:
            self._apply_detections(int(s.get("page", self.page_num)), [s])
        self.pending_suggestions = [p for p in self.pending_suggestions if p is not s]
        self._update_review_button()
        self.render_page()

    def adjust_zoom(self, d: int) -> None:
        """Adjust zoom level.

        Args:
            d: Zoom direction (+1 to zoom in, -1 to zoom out).
        """
        self.scale = max(0.5, min(4.0, self.scale + (0.25 * d)))
        self.lbl_zoom.setText(f"{int(self.scale * 100)}%")
        self.render_page()

    def move_page(self, d: int) -> None:
        """Move to adjacent page.

        Args:
            d: Page direction (+1 for next, -1 for previous).
        """
        if self.doc and 0 <= self.page_num + d < len(self.doc):
            self.page_num += d
            self.render_page()

    def jump_page(self) -> None:
        """Jump to the page number entered in the page selector."""
        if not self.doc:
            self.write_log("Avviso: Nessun PDF caricato")
            return
        try:
            n = int(self.le_page.text()) - 1
            if 0 <= n < len(self.doc):
                self.page_num = n
                self.render_page()
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
        cl = ""
        with QMutexLocker(self.doc_mutex):
            if not self.doc:
                return
            p = self.doc[self.page_num]
            txt = text_under_rect(p, fitz.Rect(r))
            if not txt:
                self._add_kind_redaction(p, r, "IMAGE")
            else:
                self._add_privacy_redaction(
                    p,
                    r,
                    original=txt,
                    entity_type=self._infer_entity_type(txt),
                )
                cl = " ".join(txt.split()).lower()
        self.render_page()
        # The redaction on this page is already applied regardless of the
        # answer below; this only decides whether the word is also
        # persisted to blocklist.txt so it gets auto-redacted in every
        # future document.
        if len(cl) > 2 and cl not in self.blocklist:
            answer = QMessageBox.question(
                self,
                "Aggiungi alla blacklist",
                f'Vuoi aggiungere "{cl}" alla blacklist?\n\n'
                "Verrà censurata automaticamente in ogni documento PDF "
                "che aprirai in futuro.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.allowlist.discard(cl)
                self.blocklist.add(cl)
                self.list_manager.save_blocklist(self.blocklist)
                self.list_manager.save_allowlist(self.allowlist)

    def user_click_pt(self, qpt: QPointF) -> None:
        """Handle user click on redaction to delete it.

        Args:
            qpt: Point clicked by user in scene coordinates.
        """
        if not self.doc:
            return
        overlays = [it for it in self.scene.items(qpt) if isinstance(it, SuggestionItem)]
        if overlays:
            self._decide_suggestion(overlays[0].suggestion)
            return
        pt = fitz.Point(qpt.x() / self.scale, qpt.y() / self.scale)
        cl = ""
        with QMutexLocker(self.doc_mutex):
            if not self.doc:
                return
            p = self.doc[self.page_num]
            ans = [
                a
                for a in (p.annots() or [])
                if a.type[0] == PDF_ANNOT_REDACT and a.rect.contains(pt)
            ]
            if not ans:
                return
            txt = text_under_rect(p, ans[0].rect)
            cl = " ".join(txt.split()).lower()

        add_to_whitelist = False
        if len(cl) > 2:
            box = QMessageBox(self)
            box.setWindowTitle("Rimuovi censura")
            box.setText(
                f'Rimuovere la censura su "{cl}"?\n\n'
                "Scegli se escluderla solo da questo documento oppure "
                "aggiungerla alla whitelist permanente (non verrà mai più "
                "censurata in nessun documento)."
            )
            btn_doc_only = box.addButton(
                "Solo questo documento", QMessageBox.ButtonRole.AcceptRole
            )
            btn_whitelist = box.addButton(
                "Whitelist permanente", QMessageBox.ButtonRole.YesRole
            )
            btn_cancel = box.addButton(
                "Annulla", QMessageBox.ButtonRole.RejectRole
            )
            box.setDefaultButton(btn_doc_only)
            box.exec()
            clicked = box.clickedButton()
            if clicked == btn_cancel:
                return
            add_to_whitelist = clicked == btn_whitelist

        with QMutexLocker(self.doc_mutex):
            if not self.doc:
                return
            p = self.doc[self.page_num]
            ans = [
                a
                for a in (p.annots() or [])
                if a.type[0] == PDF_ANNOT_REDACT and a.rect.contains(pt)
            ]
            for a in ans:
                p.delete_annot(a)
            if add_to_whitelist and len(cl) > 2:
                self.blocklist.discard(cl)
                self.allowlist.add(cl)
                self.list_manager.save_blocklist(self.blocklist)
                self.list_manager.save_allowlist(self.allowlist)
        self.render_page()

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
                a for a in (p.annots() or []) if a.type[0] == PDF_ANNOT_REDACT
            ]
            for a in to_delete:
                p.delete_annot(a)
        self.render_page()
        self.write_log(f"Censure rimosse su pagina {self.page_num+1}")

    def cmd_dict(self) -> None:
        """Open the dictionary editor (blocklist / allowlist with expiry)."""
        d = DictionaryDialog(self.list_manager, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            if d.saved_blocklist is not None:
                self.blocklist = d.saved_blocklist
            if d.saved_allowlist is not None:
                self.allowlist = d.saved_allowlist

    def _start_bg_thread(self, w: QThread) -> None:
        """Start ``w`` and keep it referenced until it has finished."""
        self._bg_threads.add(w)

        def done() -> None:
            self._bg_threads.discard(w)
            w.deleteLater()

        w.finished.connect(done)
        w.start()

    def auto_check_updates(self) -> None:
        """Silent check at startup, only if the user enabled it in Info.

        Nothing is shown unless a newer release exists; failures (offline,
        rate limit) are only logged.
        """
        if not update_check.load_auto_check(self.config_dir / "update_check.json"):
            return
        w = UpdateCheckWorker()
        w.result_sig.connect(self._on_auto_update_result)
        self._start_bg_thread(w)

    def _on_auto_update_result(self, release: Any) -> None:
        if release is not None:
            self._show_update_dialog(release, self)

    def cmd_guide(self) -> None:
        """Open the user guide (also bound to F1)."""
        GuideDialog(self).exec()

    def cmd_about(self) -> None:
        """Show about dialog."""
        d = QDialog(self)
        d.setWindowTitle("Info")
        d.setFixedSize(340, 560)
        lay = QVBoxLayout(d)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ip = resource_path(os.path.join("images", "NullifyPDF_icon.png"))
        if os.path.exists(ip):
            lbl_icon = QLabel()
            lbl_icon.setPixmap(
                QPixmap(ip).scaled(
                    100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )
            lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lbl_icon)
            lay.addSpacing(10)
        lbl_title = QLabel("NullifyPDF")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl_title)
        lbl_ver = QLabel(about_version_text())
        lbl_ver.setStyleSheet("color: #0ea5e9; font-weight: bold;")
        lbl_ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl_ver)
        desc = QLabel(
            "\nCensura e pseudonimizzazione PDF offline.\n\nSviluppato da: Graziano Mariella\nLicenza MIT"
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(desc)
        lbl_repo = QLabel(
            f'<a href="{update_check.REPO_URL}">{update_check.REPO_URL}</a>'
        )
        lbl_repo.setTextFormat(Qt.TextFormat.RichText)
        lbl_repo.setOpenExternalLinks(True)
        lbl_repo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl_repo)
        lay.addSpacing(10)
        btn_upd = QPushButton("Controlla aggiornamenti")
        lay.addWidget(btn_upd)
        chk_auto = QCheckBox("Controlla ad ogni avvio")
        pref_path = self.config_dir / "update_check.json"
        chk_auto.setChecked(update_check.load_auto_check(pref_path))
        chk_auto.toggled.connect(lambda on: update_check.save_auto_check(pref_path, on))
        lay.addWidget(chk_auto, alignment=Qt.AlignmentFlag.AlignCenter)
        lbl_upd = QLabel("")
        lbl_upd.setWordWrap(True)
        lbl_upd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl_upd)
        lay.addSpacing(10)
        btn = QPushButton("Chiudi")
        btn.clicked.connect(d.accept)
        lay.addWidget(btn)

        state: Dict[str, Any] = {"closed": False}

        def on_result(release: Any) -> None:
            if state["closed"]:
                return
            btn_upd.setEnabled(True)
            if release is None:
                lbl_upd.setText("Nessun aggiornamento disponibile: la versione è aggiornata.")
                return
            lbl_upd.setText(f"Disponibile: {release.get('tag_name', '')}")
            self._show_update_dialog(release, d)

        def on_error(msg: str) -> None:
            btn_upd.setEnabled(True)
            lbl_upd.setText(f"Controllo non riuscito (connessione assente?)\n{msg}")

        def start_check() -> None:
            btn_upd.setEnabled(False)
            lbl_upd.setText("Controllo in corso...")
            w = UpdateCheckWorker()
            w.result_sig.connect(on_result)
            w.error_sig.connect(on_error)
            self._start_bg_thread(w)

        btn_upd.clicked.connect(start_check)
        apply_tooltips(d)
        d.exec()
        state["closed"] = True

    def _show_update_dialog(self, release: Dict[str, Any], parent: QWidget) -> None:
        """Release notes, link to the release and a [Download] button."""
        tag = str(release.get("tag_name", ""))
        url = str(release.get("html_url", ""))
        if not update_check.is_trusted_url(url):
            url = f"{update_check.REPO_URL}/releases"
        asset = update_check.select_asset(release)

        d = QDialog(parent)
        d.setWindowTitle("Aggiornamento disponibile")
        d.resize(560, 480)
        lay = QVBoxLayout(d)
        kind = " (beta)" if release.get("prerelease") else ""
        lay.addWidget(QLabel(f"<b>Nuova versione: {html.escape(tag)}{kind}</b>"))
        lbl_link = QLabel(f'<a href="{html.escape(url)}">{html.escape(url)}</a>')
        lbl_link.setTextFormat(Qt.TextFormat.RichText)
        lbl_link.setOpenExternalLinks(True)
        lay.addWidget(lbl_link)
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        body = str(release.get("body") or "").strip()
        notes.setMarkdown(body or "_Nessuna nota di rilascio disponibile._")
        lay.addWidget(notes)
        bar = QProgressBar()
        bar.setVisible(False)
        lay.addWidget(bar)
        lbl_status = QLabel("")
        lbl_status.setWordWrap(True)
        lay.addWidget(lbl_status)
        row = QHBoxLayout()
        btn_dl = QPushButton("Download")
        btn_dl.setObjectName("Primary")
        btn_close = QPushButton("Chiudi")
        row.addWidget(btn_dl)
        row.addWidget(btn_close)
        lay.addLayout(row)
        btn_close.clicked.connect(d.reject)

        if asset is None:
            btn_dl.setEnabled(False)
            lbl_status.setText(
                "Nessun file per questo sistema operativo: usa il link alla release."
            )

        state: Dict[str, Any] = {"worker": None, "closed": False}

        def on_progress(done: int, total: int) -> None:
            if total > 0:
                bar.setMaximum(total)
                bar.setValue(done)
            else:
                bar.setMaximum(0)

        def on_done(path: str) -> None:
            if state["closed"]:
                return
            bar.setVisible(False)
            btn_dl.setEnabled(False)
            lbl_status.setText(f"Scaricato in: {path}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(pathlib.Path(path).parent)))

        def on_error(msg: str) -> None:
            if state["closed"]:
                return
            bar.setVisible(False)
            btn_dl.setEnabled(True)
            lbl_status.setText(f"Download non riuscito: {msg}" if msg else "Download annullato.")

        def start_download() -> None:
            if asset is None:
                return
            try:
                folder = downloads_folder()
                folder.mkdir(parents=True, exist_ok=True)
                dest = update_check.unique_path(folder, str(asset.get("name", "")))
            except OSError as e:
                lbl_status.setText(f"Cartella Download non accessibile: {e}")
                return
            btn_dl.setEnabled(False)
            bar.setValue(0)
            bar.setVisible(True)
            lbl_status.setText(f"Download in {dest.parent} ...")
            w = UpdateDownloadWorker(
                str(asset["browser_download_url"]),
                dest,
                int(asset.get("size") or 0),
                str(asset.get("digest") or ""),
            )
            w.progress_sig.connect(on_progress)
            w.done_sig.connect(on_done)
            w.error_sig.connect(on_error)
            state["worker"] = w
            self._start_bg_thread(w)

        btn_dl.clicked.connect(start_download)
        apply_tooltips(d)
        d.exec()
        state["closed"] = True
        w = state["worker"]
        if w is not None and w.isRunning():
            w.cancel()  # the thread stops by itself; the window never blocks

    def cmd_auto_ai(self) -> None:
        """Start AI scan for sensitive entities.

        Text extraction is delegated to the AIWorker thread so the UI stays
        responsive on large documents. Access to `self.doc` is serialized via
        `self.doc_mutex` between the UI thread and the worker.
        """
        if not self.doc:
            return
        enabled_groups = self._select_ai_entities()
        if not enabled_groups:
            return
        health_mode = self.chk_health.isChecked()
        if health_mode:
            for gid in ("BIRTHDATE", "HEALTHID", "EXEMPT"):
                if gid not in enabled_groups:
                    enabled_groups = list(enabled_groups) + [gid]
        self.btn_ai.setEnabled(False)
        self.prog.setValue(0)
        # Text in a layer that is switched off is invisible to extraction, so
        # neither the detector nor the reviewer would ever see it: show all
        # layers (in memory only) before scanning.
        with QMutexLocker(self.doc_mutex):
            revealed = reveal_hidden_layers(self.doc)
        if revealed:
            self.write_log(
                f"Avviso: {revealed} livelli nascosti resi visibili per l'analisi."
            )
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
            expand_group_ids(enabled_groups),
            health_mode,
        )

    def _select_ai_entities(self) -> Optional[List[str]]:
        """Ask which data types the AI scan should look for.

        Returns the chosen group ids, or None if the user cancels. The
        selection is remembered in ``ai_entities.json``.
        """
        store = self.config_dir / "ai_entities.json"
        previous = set(load_enabled_groups(store))
        dlg = QDialog(self)
        dlg.setWindowTitle("Tipi di dati da rilevare")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Seleziona i dati da censurare / pseudonimizzare:"))
        boxes: Dict[str, QCheckBox] = {}
        for gid, label, _types in ENTITY_GROUPS:
            cb = QCheckBox(label)
            cb.setChecked(gid in previous)
            boxes[gid] = cb
            lay.addWidget(cb)
        row = QHBoxLayout()
        btn_all = QPushButton("Seleziona tutto")
        btn_none = QPushButton("Deseleziona tutto")
        row.addWidget(btn_all)
        row.addWidget(btn_none)
        lay.addLayout(row)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        lay.addWidget(bb)
        ok = bb.button(QDialogButtonBox.StandardButton.Ok)

        def refresh() -> None:
            ok.setEnabled(any(cb.isChecked() for cb in boxes.values()))

        for cb in boxes.values():
            cb.toggled.connect(refresh)
        def set_all(state: bool) -> None:
            for cb in boxes.values():
                cb.setChecked(state)

        btn_all.clicked.connect(lambda: set_all(True))
        btn_none.clicked.connect(lambda: set_all(False))
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        refresh()
        apply_tooltips(dlg)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        chosen = [gid for gid in ALL_GROUP_IDS if boxes[gid].isChecked()]
        save_enabled_groups(store, chosen)
        return chosen

    def _select_privacy_export(self) -> Optional[PrivacyMode]:
        """Ask the user which privacy export mode to use."""
        box = QMessageBox(self)
        box.setWindowTitle("Modalita privacy")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("Scegli come trattare i dati personali nel PDF esportato.")
        box.setInformativeText(
            "Rimozione irreversibile: i valori selezionati vengono eliminati "
            "dal file. Il risultato puo contenere ancora dati personali non "
            "rilevati o indiretti (date, luoghi, dettagli): controllalo prima "
            "di condividerlo.\n\n"
            "Pseudonimizzazione: segnaposto reversibili con mappa cifrata "
            "separata. Il file e la mappa restano dati personali."
        )
        anonymize_btn = box.addButton(
            "Rimozione irreversibile", QMessageBox.ButtonRole.AcceptRole
        )
        anonymize_btn.setToolTip(
            "Elimina per sempre i valori selezionati dal file. Non si può tornare indietro."
        )
        pseudonymize_btn = box.addButton(
            "Pseudonimizzazione reversibile", QMessageBox.ButtonRole.ActionRole
        )
        pseudonymize_btn.setToolTip(
            "Sostituisce i valori con segnaposto e crea una mappa cifrata per ripristinarli."
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
        compact_nospace = compact.replace(" ", "")
        if re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", compact, re.I):
            return "EMAIL_ADDRESS"
        if re.search(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", compact_nospace, re.I):
            return "IBAN_CODE"
        if re.fullmatch(
            r"[A-Z]{6}\d{2}[A-EHLMPR-T]\d{2}[A-Z]\d{3}[A-Z]", compact_nospace, re.I
        ):
            return "IT_FISCAL_CODE"
        if re.fullmatch(r"\d{11}", compact_nospace):
            return "IT_VAT_CODE"
        if re.search(r"\+?\d[\d\s()./-]{6,}\d", compact):
            return "PHONE_NUMBER"
        if re.search(r"\b\d{13,19}\b", compact_nospace):
            return "CREDIT_CARD"
        return "DATA"

    def _collect_redaction_rects(self, page: Any) -> List[fitz.Rect]:
        """Return redaction rectangles for a page."""
        return [
            a.rect for a in (page.annots() or [])
            if a.type[0] == PDF_ANNOT_REDACT
        ]

    def _add_privacy_redaction(
        self,
        page: Any,
        rect: fitz.Rect,
        *,
        original: str = "",
        entity_type: str = "DATA",
        fill: Tuple[float, float, float] = (0, 0, 0),
        full: Optional[fitz.Rect] = None,
    ) -> None:
        """Add a redaction annotation carrying optional in-memory privacy data.

        `full` is the whole box of the word when `rect` is a thinner band: the
        export uses it to check that no glyph of the word survived.
        """
        annot = page.add_redact_annot(rect, fill=fill)
        clean_original = " ".join((original or "").split())
        if clean_original:
            payload: Dict[str, Any] = {
                "nullifypdf": 1,
                "original": clean_original,
                "entity_type": PlaceholderRegistry.normalize_entity_type(entity_type),
            }
            if full is not None and fitz.Rect(full) != fitz.Rect(rect):
                payload["full"] = [full.x0, full.y0, full.x1, full.y1]
            try:
                annot.set_info(content=json.dumps(payload, ensure_ascii=False))
            except Exception as e:
                self.logger.debug(f"Could not store redaction metadata: {e}")

    def _add_kind_redaction(self, page: Any, rect: fitz.Rect, kind: str) -> None:
        """Redaction of a graphic area (image or signature) without overlay text.

        The label is drawn after the redactions are applied (see
        `_finish_labels_page`), so it is not lost in a small box.
        """
        annot = page.add_redact_annot(rect, fill=(0.9, 0.9, 0.9))
        try:
            annot.set_info(content=json.dumps(
                {"nullifypdf": 1, "original": "", "entity_type": kind}
            ))
        except Exception as e:
            self.logger.debug(f"Could not store {kind} metadata: {e}")

    def _read_redaction_full(self, annot: Any) -> Optional[fitz.Rect]:
        """The whole word box stored with a band annotation, if any."""
        try:
            raw = annot.info.get("content", "")
            payload = json.loads(raw) if raw else {}
            if payload.get("nullifypdf") == 1 and payload.get("full"):
                return fitz.Rect(*[float(v) for v in payload["full"]])
        except Exception:
            return None
        return None

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
                text_under_rect(page, annot.rect),
                capture_text_style(page, annot.rect),
            )
            for annot in (page.annots() or [])
            if annot.type[0] == PDF_ANNOT_REDACT
        ]
        for annot in list(page.annots() or []):
            if annot.type[0] == PDF_ANNOT_REDACT:
                page.delete_annot(annot)
        for rect, payload, clipped_text, style in pending:
            if payload.get("entity_type") in ("SIGNATURE", "IMAGE"):
                self._add_kind_redaction(page, rect, str(payload["entity_type"]))
                self._export_labels.append(
                    (page.number, fitz.Rect(rect),
                     KIND_LABELS[str(payload["entity_type"])], None, None)
                )
                continue
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
                    rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                    style=style,
                )
                # The placeholder is drawn after apply_redactions() (see
                # _finish_pseudonymized_page): replacement text passed to
                # the annotation is dropped when it cannot be laid out at 4 pt.
                page.add_redact_annot(rect, fill=(1, 1, 1))
                self._export_labels.append(
                    (page.number, fitz.Rect(rect), compact_labels(placeholder),
                     style, placeholder)
                )
            else:
                self._add_kind_redaction(page, rect, "IMAGE")
                self._export_labels.append(
                    (page.number, fitz.Rect(rect), KIND_LABELS["IMAGE"], None, None)
                )

    def _prepare_label_annots(self, page: Any) -> None:
        """Anonymize mode: remember the image / signature areas to label."""
        for annot in page.annots() or []:
            if annot.type[0] != PDF_ANNOT_REDACT:
                continue
            kind = self._read_redaction_payload(annot).get("entity_type")
            if kind in KIND_LABELS:
                self._export_labels.append(
                    (page.number, fitz.Rect(annot.rect), KIND_LABELS[kind], None, None)
                )

    def _finish_labels_page(
        self, page: Any, registry: Optional[PlaceholderRegistry] = None
    ) -> None:
        """Draw placeholders and image/signature labels once redactions are applied."""
        for page_no, rect, labels, style, placeholder in self._export_labels:
            if page_no != page.number:
                continue
            drawn = write_label(
                page, rect, labels, style=style,
                allowance=free_space_right(page, rect) if placeholder else 0.0,
            )
            if placeholder and registry is not None and drawn != placeholder:
                registry.set_label(
                    placeholder, (rect.x0, rect.y0, rect.x1, rect.y1), drawn
                )

    def _finish_pseudonymized_page(
        self, page: Any, registry: PlaceholderRegistry
    ) -> None:
        self._finish_labels_page(page, registry)

    @Slot(int, object)
    def apply_ai_to_page(self, i: int, detections: Any) -> None:
        """Apply AI-detected redactions to page.

        Runs on the UI thread (Qt slot). Detections in state "accepted" are
        applied; those in state "suggested" are queued for review and never
        applied silently.

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
        accepted = [
            d for d in normalized_detections if d.get("state", "accepted") == "accepted"
        ]
        for d in normalized_detections:
            if d.get("state") == "suggested":
                self.pending_suggestions.append({**d, "page": i})
        self._update_review_button()
        self._apply_detections(i, accepted)

    def _update_review_button(self) -> None:
        n = len(self.pending_suggestions)
        self.btn_review.setText(f"Rivedi suggerimenti ({n})")
        self.btn_review.setEnabled(n > 0)

    def _apply_detections(self, i: int, detections: List[Dict[str, Any]]) -> None:
        """Add redaction annotations for `detections` on page `i`."""
        with QMutexLocker(self.doc_mutex):
            if not self.doc or i >= len(self.doc):
                return
            page = self.doc[i]
            e_rects = [
                a.rect for a in (page.annots() or [])
                if a.type[0] == PDF_ANNOT_REDACT
            ]

            def already_covered(r: fitz.Rect) -> bool:
                return covered_fraction(
                    (r.x0, r.y0, r.x1, r.y1),
                    [(e.x0, e.y0, e.x1, e.y1) for e in e_rects],
                ) >= 0.6

            if self.chk_img.isChecked():
                for img in page.get_image_info(hashes=False):
                    ir = fitz.Rect(img["bbox"])
                    if already_covered(ir):
                        continue
                    self._add_kind_redaction(page, ir, "IMAGE")
                    e_rects.append(ir)
            try:
                has_images = bool(page.get_image_info(hashes=False))
            except Exception:
                has_images = False
            page_index = build_page_index(
                page.get_text("words"),
                image_rects=[
                    tuple(i["bbox"]) for i in page.get_image_info(hashes=False)
                ],
            )
            # Accepted redactions must cover the actual word box.  The
            # clamped index is useful for analysis, but using its thin band
            # for the final annotation can leave the top/bottom of a glyph
            # visible (as happens with tightly spaced lines).
            full_page_index = build_page_index(page.get_text("words"), clamp=False)

            def cover_word(rect: fitz.Rect) -> fitz.Rect:
                padded = fitz.Rect(rect.x0 - 0.5, rect.y0 - 0.5, rect.x1 + 0.5, rect.y1 + 0.5)
                return padded & page.rect

            for bw in self.blocklist:
                for r in (cover_word(fitz.Rect(*t)) for t in whole_word_rects(full_page_index, bw)):
                    if not already_covered(r):
                        self._add_privacy_redaction(
                            page,
                            r,
                            original=bw,
                            entity_type=self._infer_entity_type(bw),
                        )
                        e_rects.append(r)
            for detection in detections:
                word = str(detection.get("text", ""))
                entity_type = str(detection.get("entity_type", "DATA"))
                raw_rects = detection.get("rects") or []
                rects = [fitz.Rect(*coords) for coords in raw_rects]
                fulls = detection.get("full_rects") or []
                for k, band in enumerate(rects):
                    if k < len(fulls):
                        # Always use the original word box for the final
                        # redaction, with a small margin in both dimensions.
                        rects[k] = cover_word(fitz.Rect(*fulls[k]))
                if entity_type == "SIGNATURE":
                    # Graphic area (signature / stamp): no text, no value.
                    for r in rects:
                        if already_covered(r):
                            continue
                        self._add_kind_redaction(page, r, "SIGNATURE")
                        e_rects.append(r)
                    continue
                if not rects and word:
                    # Legacy detections without geometry: whole words only,
                    # never a substring search (it redacts fragments of
                    # longer words), and never a word the allowlist protects.
                    protected = [
                        fitz.Rect(*t)
                        for aw in self.allowlist
                        for t in whole_word_rects(full_page_index, aw)
                    ]
                    rects = [
                        fitz.Rect(*t)
                        for t in whole_word_rects(full_page_index, word)
                        if not any(
                            pr.contains(fitz.Point((t[0] + t[2]) / 2, (t[1] + t[3]) / 2))
                            for pr in protected
                        )
                    ]
                for k, r in enumerate(rects):
                    if not already_covered(r):
                        full_box = (
                            cover_word(fitz.Rect(*fulls[k]))
                            if (k < len(fulls) and raw_rects) else None
                        )
                        self._add_privacy_redaction(
                            page,
                            r,
                            original=word,
                            entity_type=entity_type,
                            full=full_box,
                        )
                        e_rects.append(r)

    def _review_suggestions(self) -> None:
        """Let the user accept or reject the queued suggestions."""
        if not self.pending_suggestions:
            return
        dlg = ReviewDialog(self.pending_suggestions, self)
        dlg.navigate.connect(self._go_to_page)
        dlg.highlight.connect(self._highlight_suggestion)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        by_page: Dict[int, List[Dict[str, Any]]] = {}
        for item in dlg.applied():
            by_page.setdefault(int(item.get("page", 0)), []).append(item)
        for page_no, items in by_page.items():
            self._apply_detections(page_no, items)
        decided = dlg.applied() + dlg.declined()
        self.pending_suggestions = [
            p for p in self.pending_suggestions
            if not any(p is d for d in decided)
        ]
        self._update_review_button()
        self.render_page()
        self.write_log(
            f"Revisione: {len(dlg.applied())} applicati, "
            f"{len(dlg.declined())} scartati."
        )

    def _go_to_page(self, page_no: int) -> None:
        if self.doc and 0 <= page_no < len(self.doc):
            self.page_num = page_no
            self.render_page()

    @Slot()
    def ai_finished(self) -> None:
        """Handle AI scan completion."""
        self.btn_ai.setEnabled(True)
        self.render_page()
        if self.pending_suggestions:
            self._review_suggestions()

    def _redaction_counts(self) -> Dict[str, int]:
        """Pending redactions per entity type (no values)."""
        counts: Dict[str, int] = {}
        for page in self.doc or []:
            for annot in page.annots() or []:
                if annot.type[0] != PDF_ANNOT_REDACT:
                    continue
                payload = self._read_redaction_payload(annot)
                key = payload.get("entity_type") or "UNSPECIFIED"
                counts[key] = counts.get(key, 0) + 1
        return counts

    def _select_pseudonym_style(self) -> Optional[Tuple[str, Optional[bytes]]]:
        """Ask how pseudonyms are generated. Returns (style, key) or None."""
        box = QMessageBox(self)
        box.setWindowTitle("Stile dei segnaposto")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("Come devono essere generati i segnaposto?")
        box.setInformativeText(
            "Casuale: non rivela ordine o numero dei valori (consigliato).\n"
            "Progressivo: PERSON_001, PERSON_002... rivela quanti valori "
            "distinti esistono e l'ordine in cui compaiono.\n"
            "Generico: nasconde anche il tipo di dato.\n"
            "Coerente: lo stesso valore riceve lo stesso segnaposto in tutti i "
            "documenti creati con la stessa chiave (permette di collegarli)."
        )
        b_random = box.addButton("Casuale", QMessageBox.ButtonRole.AcceptRole)
        b_counter = box.addButton("Progressivo", QMessageBox.ButtonRole.ActionRole)
        b_opaque = box.addButton("Generico", QMessageBox.ButtonRole.ActionRole)
        b_keyed = box.addButton("Coerente (chiave)", QMessageBox.ButtonRole.ActionRole)
        b_manage = box.addButton("Gestisci chiave...", QMessageBox.ButtonRole.ActionRole)
        b_random.setToolTip("Segnaposto casuali: non rivelano ordine né numero dei valori (consigliato).")
        b_counter.setToolTip("PERSON_001, PERSON_002...: rivelano quanti valori distinti ci sono e l'ordine.")
        b_opaque.setToolTip("Segnaposto generici: nascondono anche il tipo di dato.")
        b_keyed.setToolTip("Lo stesso valore ha lo stesso segnaposto in ogni documento creato con la stessa chiave.")
        b_manage.setToolTip("Esporta o importa la chiave dei segnaposto coerenti, protetta da password.")
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked == b_random:
            return "random", None
        if clicked == b_counter:
            return "counter", None
        if clicked == b_opaque:
            return "opaque", None
        if clicked == b_manage:
            self._pseudonym_key_dialog()
            return self._select_pseudonym_style()
        if clicked == b_keyed:
            try:
                key = self._load_pseudonym_key()
            except (secure_store.KeystoreUnavailable, secure_store.SealError, OSError) as e:
                QMessageBox.critical(self, "Chiave non disponibile", str(e))
                return None
            QMessageBox.information(
                self,
                "Chiave dei segnaposto",
                "La chiave e protetta ("
                + secure_store.protector_label(self.config_dir)
                + "). Conservane una copia protetta da password con "
                "\"Gestisci chiave...\" per usarla su un altro computer: chi "
                "la possiede puo ricollegare i segnaposto ai valori noti, e "
                "senza di essa i documenti futuri avranno segnaposto diversi.",
            )
            return "keyed", key
        return None
        return None

    def _pseudonym_key_paths(self) -> Tuple[pathlib.Path, pathlib.Path]:
        return self.config_dir / "pseudonym.v2.enc", self.config_dir / "pseudonym.key"

    def _store_pseudonym_key(self, key: bytes) -> None:
        enc, _legacy = self._pseudonym_key_paths()
        master = secure_store.load_or_create_master_key(self.config_dir)
        secure_store.atomic_write(
            enc, secure_store.seal(key, master, b"nullifypdf-pseudonym-key")
        )

    def _load_pseudonym_key(self) -> bytes:
        """The 32-byte pseudonym key, protected by the local master key.

        A plaintext ``pseudonym.key`` from an older version is validated,
        sealed and removed. Raises on an invalid or unreadable key.
        """
        enc, legacy = self._pseudonym_key_paths()
        master = secure_store.load_or_create_master_key(self.config_dir)
        if enc.exists():
            key = secure_store.open_sealed(
                enc.read_bytes(), master, b"nullifypdf-pseudonym-key"
            )
        elif legacy.exists():
            key = legacy.read_bytes()
            if len(key) != 32:
                raise OSError(
                    "Chiave dei segnaposto non valida: il file deve "
                    "contenere esattamente 32 byte."
                )
            self._store_pseudonym_key(key)
            secure_store.secure_delete(legacy)
        else:
            key = os.urandom(32)
            self._store_pseudonym_key(key)
        if len(key) != 32:
            raise OSError("Chiave dei segnaposto non valida.")
        return key

    def _pseudonym_key_dialog(self) -> None:
        """Export / import a password-protected copy of the pseudonym key."""
        box = QMessageBox(self)
        box.setWindowTitle("Chiave dei segnaposto")
        box.setText("Esporta o importa la chiave dei segnaposto coerenti.")
        box.setInformativeText(
            "La copia esportata e protetta da password e serve per usare la "
            "stessa chiave su un altro computer."
        )
        b_exp = box.addButton("Esporta chiave...", QMessageBox.ButtonRole.ActionRole)
        b_imp = box.addButton("Importa chiave...", QMessageBox.ButtonRole.ActionRole)
        b_exp.setToolTip("Salva una copia della chiave protetta da password.")
        b_imp.setToolTip("Carica una copia della chiave esportata da un altro computer.")
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        clicked = box.clickedButton()
        try:
            if clicked == b_exp:
                key = self._load_pseudonym_key()
                pw = self._ask_map_password()
                if pw is None:
                    return
                path, _ = QFileDialog.getSaveFileName(
                    self, "Esporta chiave", "pseudonym_key.nullifypdf-key",
                    "NullifyPDF key (*.nullifypdf-key)",
                )
                if path:
                    write_private_file(path, export_pseudonym_key(key, pw))
                    self.write_log("Chiave dei segnaposto esportata.")
            elif clicked == b_imp:
                path, _ = QFileDialog.getOpenFileName(
                    self, "Importa chiave", "", "NullifyPDF key (*.nullifypdf-key)"
                )
                if not path:
                    return
                pw, ok = QInputDialog.getText(
                    self, "Password chiave", "Password della copia della chiave:",
                    QLineEdit.EchoMode.Password,
                )
                if not ok or not pw:
                    return
                enc, legacy = self._pseudonym_key_paths()
                if enc.exists() or legacy.exists():
                    ans = QMessageBox.question(
                        self, "Sostituire la chiave?",
                        "Esiste gia una chiave: sostituirla cambia i segnaposto "
                        "dei documenti futuri. Continuare?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if ans != QMessageBox.StandardButton.Yes:
                        return
                with open(path, "rb") as fh:
                    key = import_pseudonym_key(fh.read(), pw)
                self._store_pseudonym_key(key)
                self.write_log("Chiave dei segnaposto importata.")
        except Exception as e:
            from cryptography.fernet import InvalidToken

            msg = "Password errata o file corrotto." if isinstance(e, InvalidToken) else str(e)
            QMessageBox.critical(self, "Chiave dei segnaposto", msg)

    def _offer_recovery_key(self) -> Optional[bytes]:
        """Offer a recovery key for the map; shown once, never stored."""
        ans = QMessageBox.question(
            self,
            "Chiave di recupero",
            "Vuoi creare anche una chiave di recupero? Permette di aprire la "
            "mappa se dimentichi la password. Non viene salvata dal programma.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return None
        raw, shown = generate_recovery_key()
        dlg = QDialog(self)
        dlg.setWindowTitle("Chiave di recupero")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(
            "Conserva questa chiave in un luogo sicuro, separato dalla mappa. "
            "Viene mostrata una sola volta."
        ))
        field = QLineEdit(shown)
        field.setReadOnly(True)
        lay.addWidget(field)
        row = QHBoxLayout()
        field.setToolTip("Chiave di recupero: mostrata una sola volta e non salvata dal programma.")
        btn_copy = QPushButton("Copia")
        btn_copy.setToolTip("Copia la chiave negli appunti (vengono svuotati alla chiusura).")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(shown))
        btn_save = QPushButton("Salva su file...")
        btn_save.setToolTip("Salva la chiave in un file di testo, da conservare lontano dalla mappa.")

        def save_file() -> None:
            path, _ = QFileDialog.getSaveFileName(
                dlg, "Salva chiave di recupero", "recovery_key.txt", "Testo (*.txt)"
            )
            if path:
                write_private_file(path, shown.encode("utf-8"))

        btn_save.clicked.connect(save_file)
        row.addWidget(btn_copy)
        row.addWidget(btn_save)
        lay.addLayout(row)
        chk = QCheckBox(
            "Ho conservato la chiave di recupero in un luogo sicuro, separato dalla mappa"
        )
        chk.setToolTip("Spunta per confermare: serve per proseguire.")
        lay.addWidget(chk)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_btn = bb.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setEnabled(False)
        chk.toggled.connect(ok_btn.setEnabled)
        bb.accepted.connect(dlg.accept)
        lay.addWidget(bb)
        dlg.exec()
        QApplication.clipboard().clear()
        # The key has been shown (and maybe saved): the map must carry its
        # wrap even if the dialog was closed without ticking the box.
        return raw

    def _ask_decrypt_secret(self) -> Optional[Tuple[Optional[str], Optional[bytes]]]:
        """Ask for the map password, or the recovery key. None = cancelled."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Password mappa")
        lay = QVBoxLayout(dlg)
        label = QLabel("Password per decifrare la mappa di ripristino:")
        lay.addWidget(label)
        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addWidget(field)
        use_rk = QCheckBox("Usa la chiave di recupero")
        use_rk.setToolTip("Apre la mappa con la chiave di recupero (NPDF-...) invece che con la password.")
        field.setToolTip("Password della mappa, oppure la chiave di recupero se hai spuntato l'opzione.")

        def toggled(on: bool) -> None:
            label.setText(
                "Chiave di recupero (NPDF-...):" if on
                else "Password per decifrare la mappa di ripristino:"
            )

        use_rk.toggled.connect(toggled)
        lay.addWidget(use_rk)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() != QDialog.DialogCode.Accepted or not field.text():
            return None
        if use_rk.isChecked():
            try:
                return None, parse_recovery_key(field.text())
            except ValueError as e:
                QMessageBox.warning(self, "Chiave di recupero", str(e))
                return None
        return field.text(), None

    def _ask_map_password(self) -> Optional[str]:
        """Ask twice for the map password and enforce a minimum strength."""
        while True:
            pw, ok = QInputDialog.getText(
                self,
                "Password mappa",
                "Password per cifrare la mappa di ripristino (minimo 12 caratteri):",
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return None
            good, why = password_strength(pw)
            if not good:
                QMessageBox.warning(self, "Password non valida", why)
                continue
            confirm, ok = QInputDialog.getText(
                self,
                "Conferma password",
                "Ripeti la password (senza di essa la mappa non e recuperabile):",
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return None
            if confirm != pw:
                QMessageBox.warning(
                    self, "Password diversa", "Le due password non coincidono."
                )
                continue
            return pw

    def cmd_wipe_local_data(self) -> None:
        """Delete logs, audit records and temp files kept in ~/.nullifypdf."""
        ans = QMessageBox.question(
            self,
            "Elimina dati locali",
            "Verranno eliminati log, registri di esportazione e file "
            "temporanei. Vuoi eliminare anche i dizionari (blocklist e "
            "allowlist)?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Cancel:
            return
        include_lists = ans == QMessageBox.StandardButton.Yes
        include_keys = False
        if include_lists:
            include_keys = QMessageBox.question(
                self,
                "Elimina anche le chiavi",
                "Eliminare anche le chiavi? I dizionari cifrati e la chiave dei "
                "segnaposto diventeranno illeggibili.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes
        # The rotating log file is open: release it first or it cannot be
        # removed (Windows), then reopen logging afterwards.
        for h in list(self.logger.handlers):
            try:
                h.close()
            except Exception:
                pass
            self.logger.removeHandler(h)
        removed = wipe_local_data(
            self.config_dir, include_lists=include_lists, include_keys=include_keys
        )
        self.logger = setup_logging()
        if include_lists:
            self.blocklist, self.allowlist = set(), set()
        self.write_log(f"Dati locali eliminati: {', '.join(removed) or 'nessuno'}.")

    def cmd_export(self) -> None:
        """Export the current PDF in irreversible or reversible privacy mode.

        The work happens in :func:`export_engine.export_document` on a copy
        kept in memory (or in a private per-user folder for very large
        files): the original ``self.doc`` is never mutated, so the user can
        keep editing, and no unredacted copy is ever written beside the
        output. The written file is sanitised and then verified.
        """
        if not self.doc:
            return
        if self.pending_suggestions:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Suggerimenti non revisionati")
            box.setText(
                f"Ci sono {len(self.pending_suggestions)} suggerimenti non "
                "revisionati: non verranno censurati."
            )
            b_review = box.addButton("Rivedi ora", QMessageBox.ButtonRole.AcceptRole)
            b_go = box.addButton("Esporta comunque", QMessageBox.ButtonRole.DestructiveRole)
            b_review.setToolTip("Apre l'elenco dei suggerimenti prima di esportare.")
            b_go.setToolTip("Esporta senza censurare i suggerimenti non revisionati.")
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            if box.clickedButton() == b_review:
                self._review_suggestions()
                return
            if box.clickedButton() != b_go:
                return
        mode = self._select_privacy_export()
        if mode is None:
            return
        with QMutexLocker(self.doc_mutex):
            removed_values = collect_removed_values(
                self.doc, self._read_redaction_payload
            )
            entity_counts = self._redaction_counts()
        src_dir = os.path.dirname(self.doc.name or "") or str(pathlib.Path.home())
        p, _ = QFileDialog.getSaveFileName(
            self,
            "Esporta",
            os.path.join(src_dir, neutral_output_name(mode.value)),
            "PDF (*.pdf)",
        )
        if not p:
            return
        if name_leaks_value(p, removed_values):
            ans = QMessageBox.question(
                self,
                "Nome file con dati personali",
                "Il nome scelto contiene un valore che stai rimuovendo. "
                "Continuare comunque?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
        map_path = ""
        map_password = ""
        recovery_key: Optional[bytes] = None
        style, key = "counter", None
        if mode == PrivacyMode.PSEUDONYMIZE:
            if importlib.util.find_spec("cryptography") is None:
                QMessageBox.critical(
                    self,
                    "Dipendenza mancante",
                    "La pseudonimizzazione richiede la libreria 'cryptography'.",
                )
                return
            chosen = self._select_pseudonym_style()
            if chosen is None:
                return
            style, key = chosen
            map_path, _ = QFileDialog.getSaveFileName(
                self,
                "Salva mappa cifrata",
                os.path.join(str(pathlib.Path.home()), neutral_map_name()),
                "NullifyPDF map (*.nullifypdf-map)",
            )
            if not map_path:
                return
            same_dir = os.path.dirname(os.path.abspath(map_path)) == os.path.dirname(
                os.path.abspath(p)
            )
            synced = any(
                tag in os.path.abspath(map_path).lower()
                for tag in ("onedrive", "dropbox", "google drive", "icloud")
            )
            if same_dir or synced:
                ans = QMessageBox.question(
                    self,
                    "Posizione della mappa",
                    "La mappa di ripristino e dato personale e va conservata "
                    "separatamente dal PDF pseudonimizzato"
                    + (", non in una cartella sincronizzata" if synced else "")
                    + ". Salvarla qui comunque?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if ans != QMessageBox.StandardButton.Yes:
                    return
            pw = self._ask_map_password()
            if pw is None:
                return
            map_password = pw
            recovery_key = self._offer_recovery_key()

        self.write_log(
            "Export con rimozione irreversibile..." if mode == PrivacyMode.ANONYMIZE
            else "Export pseudonimizzato..."
        )
        registry = PlaceholderRegistry(style=style, key=key)
        policy = SanitizePolicy(mask_removed_width=self.chk_mask_width.isChecked())
        try:
            source_name = self.doc.name or "document.pdf"
            source_sha256 = sha256_file(source_name) if os.path.exists(source_name) else ""
            prepare = (
                (lambda page: self._prepare_pseudonymized_page(page, registry))
                if mode == PrivacyMode.PSEUDONYMIZE else self._prepare_label_annots
            )
            finish = (
                (lambda page: self._finish_labels_page(page, registry))
                if mode == PrivacyMode.PSEUDONYMIZE else self._finish_labels_page
            )
            self._export_labels = []
            with QMutexLocker(self.doc_mutex):
                if not self.doc:
                    return
                result = export_document(
                    self.doc,
                    p,
                    prepare_page=prepare,
                    finish_page=finish,
                    read_full=self._read_redaction_full,
                    policy=policy,
                    removed_values=removed_values,
                    temp_dir=private_temp_dir(self.config_dir),
                    log=self.logger.debug,
                )
            if not result.verification.ok:
                where = "\n".join(result.verification.findings[:12])
                ans = QMessageBox.critical(
                    self,
                    "Verifica dell'esportazione fallita",
                    "Nel file esportato sono ancora presenti dati che dovevano "
                    "essere rimossi o contenuti attivi. Posizioni:\n" + where
                    + "\n\nEliminare il file esportato?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                self.logger.error(
                    f"Export verification failed at {len(result.verification.findings)} location(s)"
                )
                if ans == QMessageBox.StandardButton.Yes:
                    try:
                        os.remove(p)
                    except OSError as e:
                        self.logger.debug(f"Could not remove failed export: {e}")
                    self.write_log("ERRORE export: file eliminato dopo verifica fallita.")
                    return
            if mode == PrivacyMode.PSEUDONYMIZE:
                payload = build_restore_payload(
                    source_name=source_name,
                    source_sha256=source_sha256,
                    output_sha256=result.output_sha256,
                    entries=registry.entries(),
                )
                encrypted = encrypt_restore_payload(
                    payload, map_password, recovery_key=recovery_key
                )
                write_private_file(map_path, encrypted)
                self.write_log(
                    f"ESPORTATO. Mappa cifrata creata con {len(registry.entries())} segnaposto."
                )
            else:
                self.write_log("ESPORTATO.")
            record = build_audit_record(
                app_version=APP_VERSION,
                mode=mode.value,
                entity_counts=entity_counts,
                suggestion_counts={"unreviewed": len(self.pending_suggestions)},
                sanitize=result.sanitize,
                verification=result.verification,
                output_sha256=result.output_sha256,
                pages=result.pages,
            )
            write_audit_record(self.config_dir, record)
            QMessageBox.information(
                self,
                "Esportazione completata",
                (
                    "Il file esportato puo contenere ancora dati personali non "
                    "rilevati o indiretti. Controllalo prima di condividerlo."
                    if mode == PrivacyMode.ANONYMIZE
                    else "Il PDF pseudonimizzato e la mappa di ripristino "
                    "restano dati personali: conservali separatamente e proteggi "
                    "la password."
                ),
            )
        except Exception as e:
            self.logger.error(f"Export failed: {traceback.format_exc()}")
            self.write_log(f"ERRORE export: {type(e).__name__}: {str(e)}")

    def cmd_reconstruct(self) -> None:
        """Reconstruct a previously pseudonymized PDF using its restore map.

        Operates on files chosen by the user, independent of whatever
        document (if any) is currently loaded in the viewer.
        """
        if importlib.util.find_spec("cryptography") is None:
            QMessageBox.critical(
                self,
                "Dipendenza mancante",
                "La ricostruzione richiede la libreria 'cryptography'.",
            )
            return

        pdf_path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona il PDF pseudonimizzato", "", "PDF (*.pdf)"
        )
        if not pdf_path:
            return
        map_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona la mappa di ripristino",
            "",
            "NullifyPDF map (*.nullifypdf-map)",
        )
        if not map_path:
            return
        secret = self._ask_decrypt_secret()
        if secret is None:
            return
        map_password, recovery_secret = secret
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salva PDF ricostruito",
            os.path.join(
                os.path.dirname(pdf_path),
                neutral_output_name("restored"),
            ),
            "PDF (*.pdf)",
        )
        if not out_path:
            return

        from cryptography.fernet import InvalidToken

        self.write_log("Ricostruzione PDF in corso...")
        try:
            with open(map_path, "rb") as fh:
                encrypted = fh.read()
            payload = decrypt_restore_payload(
                encrypted, map_password, recovery_key=recovery_secret
            )
            expected = expected_restore_count(payload)
            restored_count = reconstruct_pdf(pdf_path, out_path, payload)
            self.write_log(
                f"RICOSTRUITO. {restored_count} segnaposto ripristinati."
            )
            QMessageBox.information(
                self,
                "PDF ricostruito",
                "Il file ricostruito contiene di nuovo tutti i dati personali "
                "originali: trattalo e conservalo di conseguenza.",
            )
            # A restore that silently puts nothing back used to look like a
            # success: same message, no dialog, output identical to input.
            if restored_count < expected:
                QMessageBox.warning(
                    self,
                    "Ricostruzione incompleta",
                    f"Ripristinati solo {restored_count} valori su {expected} "
                    "attesi.\n\nI valori mancanti non sono stati riscritti nel "
                    "PDF: il file originale e la mappa restano l'unica copia. "
                    "Controlla il log per i dettagli.",
                )
        except RestoreMapMismatch as e:
            self.write_log(f"ERRORE ricostruzione: {e}")
            QMessageBox.critical(self, "Mappa non corrispondente", str(e))
        except InvalidToken:
            self.write_log("ERRORE ricostruzione: password/chiave errata o mappa corrotta.")
            QMessageBox.critical(
                self,
                "Errore decifrazione",
                "Password o chiave di recupero errata, oppure mappa corrotta.",
            )
        except Exception as e:
            self.logger.error(f"Reconstruction failed: {traceback.format_exc()}")
            self.write_log(f"ERRORE ricostruzione: {type(e).__name__}: {str(e)}")


if __name__ == "__main__":
    if platform.system() == "Linux":
        os.environ["QT_LOGGING_RULES"] = "qt.qpa.wayland.*=false"

    app = QApplication(sys.argv)
    app.setDesktopFileName("nullify-pdf")

    try:
        window = NullifyPDF()
        window.show()
        QTimer.singleShot(1500, window.auto_check_updates)
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
