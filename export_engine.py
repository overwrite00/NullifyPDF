"""Qt-free export pipeline, local-data hygiene and audit record.

``export_document`` is the whole export: it works on a copy of the document
(kept in memory, or in a private per-user folder for very large files),
applies the redactions, sanitises the result, writes it and verifies it. The
GUI only supplies callbacks and user choices.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import secrets
import shutil
import stat
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional

import pymupdf

from pii_detection import GLYPH_CORE_INSET
from pdf_sanitize import (
    PDF_ANNOT_REDACT,
    SanitizePolicy,
    SanitizeReport,
    VerificationReport,
    sanitize_document,
    verify_export,
)

# Documents larger than this are copied through a private temp file instead
# of RAM.
IN_MEMORY_LIMIT_BYTES = 96 * 1024 * 1024
PDF_REDACT_IMAGE_PIXELS: int = pymupdf.PDF_REDACT_IMAGE_PIXELS  # type: ignore[attr-defined]


@dataclass
class ExportResult:
    output_sha256: str = ""
    sanitize: SanitizeReport = field(default_factory=SanitizeReport)
    verification: VerificationReport = field(default_factory=VerificationReport)
    pages: int = 0


def neutral_output_name(mode_value: str, now: Optional[datetime.datetime] = None) -> str:
    """Default file name that contains nothing from the source document."""
    now = now or datetime.datetime.now()
    return f"document_{mode_value}_{now:%Y%m%d_%H%M%S}.pdf"


def neutral_map_name(now: Optional[datetime.datetime] = None) -> str:
    now = now or datetime.datetime.now()
    return f"restore_map_{now:%Y%m%d_%H%M%S}.nullifypdf-map"


def name_leaks_value(path: str, values: Iterable[str]) -> bool:
    """True when the file name contains one of the values being removed."""
    base = "".join(os.path.basename(path).casefold().split())
    for v in values:
        n = "".join(v.casefold().split())
        if len(n) >= 4 and n in base:
            return True
    return False


def write_private_file(path: str, data: bytes) -> None:
    """Write `data` readable by the current user only (where supported)."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def private_temp_dir(config_dir: pathlib.Path) -> pathlib.Path:
    d = pathlib.Path(config_dir) / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def cleanup_stale_temp(config_dir: pathlib.Path, max_age_hours: float = 0.0) -> int:
    """Remove leftovers of a crashed export (called at startup)."""
    d = pathlib.Path(config_dir) / "tmp"
    removed = 0
    if not d.is_dir():
        return 0
    now = datetime.datetime.now().timestamp()
    for f in d.iterdir():
        try:
            if now - f.stat().st_mtime >= max_age_hours * 3600:
                f.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def collect_removed_values(
    doc: Any, read_payload: Optional[Callable[[Any], Dict[str, str]]] = None
) -> List[str]:
    """Every value a pending redaction will remove (for the output check)."""
    values: List[str] = []
    for page in doc:
        for annot in page.annots() or []:
            if annot.type[0] != PDF_ANNOT_REDACT:
                continue
            payload = read_payload(annot) if read_payload else {}
            original = (payload or {}).get("original", "")
            if original:
                values.append(original)
            try:
                clipped = page.get_text("text", clip=annot.rect).strip()
            except Exception:
                clipped = ""
            if clipped:
                values.append(" ".join(clipped.split()))
    seen: List[str] = []
    for v in values:
        if v and v not in seen:
            seen.append(v)
    return seen


def text_outside_redactions(doc: Any) -> str:
    """Source text that no redaction covers (it stays in the output)."""
    chunks: List[str] = []
    for page in doc:
        rects = [
            a.rect for a in (page.annots() or []) if a.type[0] == PDF_ANNOT_REDACT
        ]
        for w in page.get_text("words"):
            # A word is deleted when a redaction reaches its glyph core (the
            # box inset by GLYPH_CORE_INSET), not only when its centre is
            # covered; a partly covered word is not "kept".
            dx, dy = (w[2] - w[0]) * GLYPH_CORE_INSET, (w[3] - w[1]) * GLYPH_CORE_INSET
            core = pymupdf.Rect(w[0] + dx, w[1] + dy, w[2] - dx, w[3] - dy)
            if not any(core.intersects(r) for r in rects):
                chunks.append(w[4])
    return " ".join(chunks)


def _open_copy(
    src_doc: Any, temp_dir: Optional[pathlib.Path]
) -> tuple[Any, Optional[str]]:
    """Open a working copy of `src_doc` without leaving PII beside the output."""
    size = 0
    try:
        size = os.path.getsize(src_doc.name) if src_doc.name else 0
    except OSError:
        size = 0
    if size <= IN_MEMORY_LIMIT_BYTES or temp_dir is None:
        return pymupdf.open("pdf", src_doc.tobytes(garbage=0, deflate=False)), None
    tmp = str(pathlib.Path(temp_dir) / f"{secrets.token_hex(8)}.tmp")
    data = src_doc.tobytes(garbage=0, deflate=False)
    write_private_file(tmp, data)
    return pymupdf.open(tmp), tmp


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def export_document(
    src_doc: Any,
    out_path: str,
    *,
    prepare_page: Optional[Callable[[Any], None]] = None,
    finish_page: Optional[Callable[[Any], None]] = None,
    policy: Optional[SanitizePolicy] = None,
    removed_values: Iterable[str] = (),
    temp_dir: Optional[pathlib.Path] = None,
    log: Optional[Callable[[str], None]] = None,
) -> ExportResult:
    """Apply redactions to a copy of `src_doc`, sanitise, save and verify."""
    result = ExportResult()
    kept_text = text_outside_redactions(src_doc)
    ex_doc, tmp = _open_copy(src_doc, temp_dir)
    try:
        for page in ex_doc.pages():
            if prepare_page is not None:
                prepare_page(page)
            redact_rects = [
                a.rect for a in (page.annots() or [])
                if a.type[0] == PDF_ANNOT_REDACT
            ]
            try:
                for lnk in page.get_links():
                    if any(pymupdf.Rect(lnk["from"]).intersects(r) for r in redact_rects):
                        page.delete_link(lnk)
            except (RuntimeError, AttributeError, KeyError) as e:
                if log:
                    log(f"link removal skipped: {e}")
            # PDF_REDACT_IMAGE_PIXELS blanks only the pixels under each rect;
            # IMAGE_REMOVE would delete a whole scanned page for one word.
            page.apply_redactions(images=PDF_REDACT_IMAGE_PIXELS, graphics=True)
            if finish_page is not None:
                # Text drawn after the redactions are applied: placeholders
                # must not go through apply_redactions(), which silently
                # drops text it cannot lay out at 4 pt or more.
                finish_page(page)
            try:
                for w in list(page.widgets() or []):
                    page.delete_widget(w)
            except (RuntimeError, AttributeError) as e:
                if log:
                    log(f"widget removal skipped: {e}")
            result.pages += 1
        result.sanitize = sanitize_document(ex_doc, policy)
        ex_doc.save(out_path, garbage=4, deflate=True, clean=True)
    finally:
        try:
            ex_doc.close()
        except Exception:
            pass
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass
    result.output_sha256 = sha256_of(out_path)
    result.verification = verify_export(out_path, removed_values, kept_text)
    return result


# ---------------------------------------------------------------------------
# Audit record (no values) and local data hygiene
# ---------------------------------------------------------------------------

def build_audit_record(
    *,
    app_version: str,
    mode: str,
    entity_counts: Dict[str, int],
    suggestion_counts: Dict[str, int],
    sanitize: SanitizeReport,
    verification: VerificationReport,
    output_sha256: str,
    pages: int,
) -> Dict[str, Any]:
    """Accountability record of one export. Holds no personal data."""
    return {
        "format": "NullifyPDF export audit",
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "app_version": app_version,
        "mode": mode,
        "pages": pages,
        "entity_counts": dict(entity_counts),
        "suggestions": dict(suggestion_counts),
        "sanitizer_actions": dict(sanitize.actions),
        "verification": {
            "ok": verification.ok,
            "findings": list(verification.findings),
        },
        "output_sha256": output_sha256,
    }


def write_audit_record(config_dir: pathlib.Path, record: Dict[str, Any]) -> str:
    d = pathlib.Path(config_dir) / "audit"
    d.mkdir(parents=True, exist_ok=True)
    name = f"export_{datetime.datetime.now():%Y%m%d_%H%M%S}_{secrets.token_hex(2)}.json"
    path = str(d / name)
    write_private_file(path, json.dumps(record, indent=2, sort_keys=True).encode("utf-8"))
    return path


def wipe_local_data(
    config_dir: pathlib.Path, include_lists: bool = False, include_keys: bool = False
) -> List[str]:
    """Delete logs, audit records, temp files and, optionally, the word lists
    and the keys (keystore, pseudonym key). Without the keys the encrypted
    lists and the stored pseudonym key become unreadable."""
    root = pathlib.Path(config_dir)
    removed: List[str] = []
    for sub in ("logs", "audit", "tmp"):
        d = root / sub
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            if not d.exists():  # report only what is really gone
                removed.append(sub)
    names = ["ai_entities.json"]
    if include_keys:
        names += ["keystore.json", "pseudonym.v2.enc", "pseudonym.key"]
        keys = root / "keys"
        if keys.is_dir():
            shutil.rmtree(keys, ignore_errors=True)
            if not keys.exists():
                removed.append("keys")
        try:
            import secure_store

            secure_store.forget_cached_keys()
        except Exception:
            pass
    if include_lists:
        names += ["blocklist.txt", "allowlist.txt", "blocklist.v2.enc", "allowlist.v2.enc"]
    for n in names:
        f = root / n
        if f.is_file():
            try:
                f.unlink()
                removed.append(n)
            except OSError:
                pass
    return removed


def purge_old_logs(log_dir: pathlib.Path, max_age_days: int = 30) -> int:
    d = pathlib.Path(log_dir)
    if not d.is_dir():
        return 0
    cutoff = datetime.datetime.now().timestamp() - max_age_days * 86400
    n = 0
    for f in d.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                n += 1
        except OSError:
            pass
    return n


def log_token(path: str) -> str:
    """Stable short token for a path, so logs never hold file names."""
    return hashlib.sha256(path.encode("utf-8", "ignore")).hexdigest()[:10]
