"""Qt-free export sanitiser and verifier.

Redacting visible text is not enough to share a PDF: annotations, embedded
files, JavaScript, bookmarks, tagged-PDF alternative text, hidden layers,
invisible text and text outside the page box all survive a plain
``apply_redactions()``. :func:`sanitize_document` removes them;
:func:`verify_export` reopens the written file and checks that none of the
removed values is still recoverable from it.

Reports contain counts and locations, never the removed values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import pymupdf

PDF_REDACT_IMAGE_NONE: int = pymupdf.PDF_REDACT_IMAGE_NONE  # type: ignore[attr-defined]
PDF_ANNOT_REDACT: int = pymupdf.PDF_ANNOT_REDACT  # type: ignore[attr-defined]

# Catalog keys removed at export: they carry scripts, attachments, outlines,
# structure (alternative text), threads or legal attestations.
CATALOG_KEYS_TO_DROP = (
    "Names", "OpenAction", "AA", "StructTreeRoot", "MarkInfo", "Outlines",
    "Threads", "SpiderInfo", "Perms", "Legal", "AcroForm", "Metadata",
    "PieceInfo", "Properties", "URI", "Collection",
)
PAGE_KEYS_TO_DROP = ("AA", "PieceInfo", "Metadata", "Thumb", "StructParents")


@dataclass
class SanitizePolicy:
    remove_hidden_text: bool = True
    remove_annotations: bool = True
    remove_external_links: bool = True
    reveal_layers: bool = True
    expand_cropbox: bool = True
    regenerate_id: bool = True
    mask_removed_width: bool = False


@dataclass
class SanitizeReport:
    actions: Dict[str, int] = field(default_factory=dict)

    def bump(self, key: str, n: int = 1) -> None:
        if n:
            self.actions[key] = self.actions.get(key, 0) + n


def reveal_hidden_layers(doc: Any) -> int:
    """Switch every optional-content layer on so hidden text becomes visible.

    Text in a layer that is OFF is not returned by ``get_text()``, so neither
    the detector nor the reviewer would ever see it. Returns the layer count.
    """
    try:
        ocgs = doc.get_ocgs()
    except Exception:
        return 0
    if not ocgs:
        return 0
    try:
        doc.set_layer(-1, basestate="ON", off=[])
    except Exception:
        try:
            doc.set_layer(-1, on=list(ocgs.keys()), off=[])
        except Exception:
            return 0
    return len(ocgs)


def _page_image_coverage(page: Any) -> float:
    try:
        area = page.rect.width * page.rect.height
        if area <= 0:
            return 0.0
        covered = 0.0
        for info in page.get_image_info(hashes=False):
            r = pymupdf.Rect(info["bbox"]) & page.rect
            covered += max(0.0, r.width * r.height)
        return covered / area
    except Exception:
        return 0.0


page_image_coverage = _page_image_coverage


def hidden_text_rects(page: Any) -> List[Any]:
    """Rectangles of text that is drawn invisibly.

    Invisible = render mode 3, zero opacity or sub-1pt font size. On pages
    that are mostly one image the invisible layer is the OCR text of a scan
    and is left alone: it is only removed where the image is redacted.
    """
    try:
        spans = page.get_texttrace()
    except Exception:
        return []
    scanned = _page_image_coverage(page) >= 0.6
    out: List[Any] = []
    for sp in spans:
        invisible = (
            sp.get("type") == 3
            or float(sp.get("opacity", 1.0)) <= 0.0
            or float(sp.get("size", 10.0)) < 1.0
        )
        if not invisible:
            continue
        if scanned and sp.get("type") == 3:
            continue
        r = pymupdf.Rect(sp["bbox"])
        if r.is_empty or r.is_infinite:
            continue
        out.append(r)
    return out


def _quantize_tj_gaps(doc: Any, page: Any, bucket: int = 500, threshold: int = 1500) -> int:
    """Round large TJ gaps so the width of removed text is not recoverable.

    ``apply_redactions`` leaves a numeric gap equal to the removed text's
    width in the text-showing operator. Word spaces and kerning are far
    smaller than ``threshold``, so only gaps left by removed text are
    touched; the following text shifts by at most ``bucket / 2`` units.
    """
    changed = 0
    num = re.compile(rb"(?<![\w.\-])-?\d+(?:\.\d+)?(?![\w.])")
    arr = re.compile(rb"\[(?:[^\]\\]|\\.)*\]\s*TJ", re.S)
    for xref in page.get_contents():
        try:
            data = doc.xref_stream(xref)
        except Exception:
            continue
        if not data:
            continue

        def fix_array(m: "re.Match[bytes]") -> bytes:
            nonlocal changed
            body = m.group(0)
            # Keep string literals untouched: split on them.
            out = bytearray()
            i = 0
            depth = 0
            while i < len(body):
                ch = body[i:i + 1]
                if ch == b"(":
                    j = i + 1
                    depth = 1
                    while j < len(body) and depth:
                        if body[j:j + 1] == b"\\":
                            j += 2
                            continue
                        if body[j:j + 1] == b"(":
                            depth += 1
                        elif body[j:j + 1] == b")":
                            depth -= 1
                        j += 1
                    out += body[i:j]
                    i = j
                elif ch == b"<":
                    j = body.find(b">", i)
                    j = len(body) if j == -1 else j + 1
                    out += body[i:j]
                    i = j
                else:
                    j = i
                    while j < len(body) and body[j:j + 1] not in (b"(", b"<"):
                        j += 1
                    seg = body[i:j]

                    def rnd(nm: "re.Match[bytes]") -> bytes:
                        nonlocal changed
                        v = float(nm.group(0))
                        if abs(v) < threshold:
                            return nm.group(0)
                        q = int(round(abs(v) / bucket)) * bucket
                        new = -q if v < 0 else q
                        if new != v:
                            changed += 1
                        return str(new).encode()

                    out += num.sub(rnd, seg)
                    i = j
            return bytes(out)

        new_data = arr.sub(fix_array, data)
        if new_data != data:
            doc.update_stream(xref, new_data)
    return changed


def sanitize_document(doc: Any, policy: Optional[SanitizePolicy] = None) -> SanitizeReport:
    """Strip everything that survives redaction, in place."""
    policy = policy or SanitizePolicy()
    rep = SanitizeReport()

    if policy.reveal_layers:
        rep.bump("layers-revealed", reveal_hidden_layers(doc))

    for page in doc:
        if policy.remove_hidden_text:
            rects = hidden_text_rects(page)
            for r in rects:
                page.add_redact_annot(r)
            if rects:
                page.apply_redactions(
                    images=PDF_REDACT_IMAGE_NONE, graphics=0
                )
                rep.bump("hidden-text-spans", len(rects))
        if policy.expand_cropbox:
            mb, cb = page.mediabox, page.cropbox
            if cb != mb:
                # Text between the visible box and the media box is neither
                # shown nor analysed: redact it, then drop the crop.
                for strip in _strips(mb, cb):
                    page.add_redact_annot(strip)
                page.apply_redactions(images=PDF_REDACT_IMAGE_NONE, graphics=0)
                page.set_cropbox(mb)
                rep.bump("offpage-area-cleared")
        if policy.remove_annotations:
            for a in list(page.annots() or []):
                page.delete_annot(a)
                rep.bump("annotations-removed")
        if policy.remove_external_links:
            for lnk in page.get_links():
                if lnk.get("kind") in (pymupdf.LINK_URI, pymupdf.LINK_LAUNCH,
                                       pymupdf.LINK_GOTOR):
                    page.delete_link(lnk)
                    rep.bump("links-removed")
        for key in PAGE_KEYS_TO_DROP:
            try:
                if doc.xref_get_key(page.xref, key)[0] != "null":
                    doc.xref_set_key(page.xref, key, "null")
                    rep.bump(f"page-key:{key}")
            except Exception:
                pass

    try:
        n_files = len(doc.embfile_names())
    except Exception:
        n_files = 0
    rep.bump("embedded-files-removed", n_files)
    try:
        doc.scrub(
            attached_files=True, clean_pages=True, embedded_files=True,
            hidden_text=False, javascript=True, metadata=True,
            redactions=False, remove_links=False, reset_fields=True,
            reset_responses=True, thumbnails=True, xml_metadata=True,
        )
    except Exception:
        rep.bump("scrub-failed")
    if policy.mask_removed_width:
        # After scrub: cleaning rewrites content streams, which would
        # re-serialise the numbers this pass has just rounded.
        for page in doc:
            rep.bump("tj-gaps-quantized", _quantize_tj_gaps(doc, page))
    try:
        if doc.get_toc():
            rep.bump("bookmarks-removed", len(doc.get_toc()))
        doc.set_toc([])
    except Exception:
        pass
    cat = doc.pdf_catalog()
    for key in CATALOG_KEYS_TO_DROP:
        try:
            if doc.xref_get_key(cat, key)[0] != "null":
                doc.xref_set_key(cat, key, "null")
                rep.bump(f"catalog-key:{key}")
        except Exception:
            pass
    doc.set_metadata({})
    if policy.regenerate_id:
        try:
            doc.xref_set_key(-1, "ID", "null")
            rep.bump("trailer-id-removed")
        except Exception:
            pass
    return rep


def _strips(mediabox: Any, cropbox: Any) -> List[Any]:
    strips = []
    if cropbox.y0 > mediabox.y0:
        strips.append(pymupdf.Rect(mediabox.x0, mediabox.y0, mediabox.x1, cropbox.y0))
    if cropbox.y1 < mediabox.y1:
        strips.append(pymupdf.Rect(mediabox.x0, cropbox.y1, mediabox.x1, mediabox.y1))
    if cropbox.x0 > mediabox.x0:
        strips.append(pymupdf.Rect(mediabox.x0, mediabox.y0, cropbox.x0, mediabox.y1))
    if cropbox.x1 < mediabox.x1:
        strips.append(pymupdf.Rect(cropbox.x1, mediabox.y0, mediabox.x1, mediabox.y1))
    return strips


# ---------------------------------------------------------------------------
# Signature and stamp areas (suggestions only)
# ---------------------------------------------------------------------------

_ANCHOR_SINGLE = {"firma", "firmato", "firmata", "timbro", "visto", "f.to"}
_ANCHOR_PAIRS = {
    ("il", "medico"), ("il", "dottore"), ("in", "fede"), ("il", "dichiarante"),
    ("il", "richiedente"), ("l'assistito", ""), ("il", "titolare"),
    ("il", "paziente"), ("timbro", "e"),
}
_ANCHOR_REGION_BELOW = 90.0
_ANCHOR_REGION_SIDE = 200.0


def _anchor_rects(words: List[Any]) -> List[Any]:
    out: List[Any] = []
    low = [(str(w[4]).lower().strip(".,:;"), w) for w in words]
    for i, (t, w) in enumerate(low):
        nxt = low[i + 1][0] if i + 1 < len(low) else ""
        if t in _ANCHOR_SINGLE or (t, nxt) in _ANCHOR_PAIRS or (t, "") in _ANCHOR_PAIRS:
            out.append(pymupdf.Rect(w[:4]))
    return out


def _merge_close(rects: List[Any], gap: float = 8.0) -> List[Any]:
    rects = [pymupdf.Rect(r) for r in rects]
    merged = True
    while merged:
        merged = False
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                grown = pymupdf.Rect(rects[i]) + (-gap, -gap, gap, gap)
                if grown.intersects(rects[j]):
                    rects[i] |= rects[j]
                    del rects[j]
                    merged = True
                    break
            if merged:
                break
    return rects


def suggest_signature_areas(page: Any, words: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    """Suggest handwritten-signature / stamp areas near signature labels.

    Anchored on words such as "firma", "timbro", "il medico". Looks for
    curve-rich vector ink without text, and for small images, in a region
    around each anchor. Always returns *suggestions* (state "suggested"),
    never applied without review. The rectangle is the union of the ink plus
    a small padding: vector paths are removed only when fully contained.
    """
    words = words if words is not None else page.get_text("words")
    anchors = _anchor_rects(words)
    if not anchors:
        return []
    page_area = page.rect.width * page.rect.height
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []
    try:
        images = page.get_image_info(hashes=False)
    except Exception:
        images = []
    word_rects = [pymupdf.Rect(w[:4]) for w in words]
    found: List[Dict[str, Any]] = []
    seen: List[Any] = []
    for anchor in anchors:
        region = pymupdf.Rect(
            anchor.x0 - _ANCHOR_REGION_SIDE, anchor.y0 - 5,
            anchor.x1 + _ANCHOR_REGION_SIDE, anchor.y1 + _ANCHOR_REGION_BELOW,
        ) & page.rect
        ink: List[Any] = []
        widths: List[float] = [1.0]
        for d in drawings:
            r = pymupdf.Rect(d["rect"])
            if r.is_empty and r.width < 0.5 and r.height < 0.5:
                continue
            if not region.contains(r):
                continue
            items = d.get("items", [])
            curves = sum(1 for it in items if it[0] == "c")
            lines = sum(1 for it in items if it[0] == "l")
            straight = len(items) == 1 and items[0][0] == "l"
            if straight or (r.width > 200 and r.height < 3) or (r.height > 200 and r.width < 3):
                continue  # table borders, underlines
            if curves >= 4 or lines >= 8:
                ink.append(r)
                widths.append(float(d.get("width") or 1.0))
        for cluster in _merge_close(ink):
            area = cluster.width * cluster.height
            if not (200 <= area <= 40000):
                continue
            if any(wr.contains(pymupdf.Point((cluster.x0 + cluster.x1) / 2, (cluster.y0 + cluster.y1) / 2))
                   for wr in word_rects):
                continue
            # MuPDF removes a vector path only when the rectangle covers its
            # box grown by the stroke's miter extent (default miter limit 10).
            pad = 10.0 * max(widths) + 0.5
            box = cluster + (-pad, -pad, pad, pad)
            overlaps_text = any(
                wr.intersects(box + (-pad / 2, -pad / 2, pad / 2, pad / 2)) for wr in word_rects
            )
            if any(box.intersects(s) for s in seen):
                continue
            seen.append(box)
            found.append({
                "text": "", "entity_type": "SIGNATURE",
                "rects": [tuple(box)], "source": "graphics", "score": 0.7,
                "state": "suggested",
                "reasons": ["signature-anchor", "curve-ink"]
                + (["overlaps-text"] if overlaps_text else []),
                "glued": False,
            })
        for info in images:
            r = pymupdf.Rect(info["bbox"])
            if not r.intersects(region) or r.width * r.height > 0.25 * page_area:
                continue
            box = r + (-2, -2, 2, 2)
            if any(box.intersects(s) for s in seen):
                continue
            seen.append(box)
            found.append({
                "text": "", "entity_type": "SIGNATURE",
                "rects": [tuple(box)], "source": "graphics", "score": 0.6,
                "state": "suggested",
                "reasons": ["signature-anchor", "raster-stamp"], "glued": False,
            })
    return found


# ---------------------------------------------------------------------------
# Verification of the written file
# ---------------------------------------------------------------------------

@dataclass
class VerificationReport:
    ok: bool = True
    findings: List[str] = field(default_factory=list)  # locations only

    def add(self, where: str) -> None:
        self.ok = False
        if where not in self.findings:
            self.findings.append(where)


MIN_NEEDLE_LENGTH = 4


def _squash(s: str) -> str:
    return " ".join(s.split())


def _compile_needles(values: Iterable[str]) -> List["re.Pattern[str]"]:
    """Whole-word patterns for the removed values.

    Only whole values count (never their individual words) and only from
    four characters up, and a match must not be glued to other letters or
    digits: a redacted "Rossi" must not be reported because "Rossini" is
    still on the page.
    """
    out: List["re.Pattern[str]"] = []
    seen = set()
    for v in values:
        sq = _squash(v)
        if len(sq) < MIN_NEEDLE_LENGTH or sq.casefold() in seen:
            continue
        seen.add(sq.casefold())
        body = r"\s+".join(re.escape(part) for part in sq.split())
        out.append(re.compile(r"(?<!\w)" + body + r"(?!\w)", re.IGNORECASE))
    return out


def _hit(needles: List["re.Pattern[str]"], text: str) -> bool:
    flat = _squash(text)
    return any(n.search(flat) for n in needles)


def _is_binary_resource(obj_text: str) -> bool:
    """Font programs and images: binary noise, not readable text."""
    return any(
        k in obj_text
        for k in ("/Length1", "/FontFile", "/Type1C", "/CIDFontType0C",
                  "/OpenType", "/Subtype/Image", "/Subtype /Image")
    )


def _object_texts(doc: Any, xref: int) -> List[str]:
    texts: List[str] = []
    try:
        obj = doc.xref_object(xref, compressed=False)
    except Exception:
        obj = ""
    texts.append(obj)
    try:
        if doc.xref_is_stream(xref) and not _is_binary_resource(obj):
            raw = doc.xref_stream(xref) or b""
            texts.append(raw.decode("latin-1", errors="ignore"))
            texts.append(raw.decode("utf-16-be", errors="ignore"))
    except Exception:
        pass
    return texts


def verify_export(
    out_path: str,
    removed_values: Iterable[str],
    still_present_text: str = "",
) -> VerificationReport:
    """Check that no removed value can still be read from the written file.

    Looks at page text (page-box clipping off), every object and decompressed
    stream, annotations, embedded files, bookmarks and metadata, and flags any
    leftover annotation, script or attachment. Locations are reported, never
    the values. A value that the user deliberately left unredacted elsewhere
    (it occurs in `still_present_text`, the source text outside every
    redaction) is not a finding.
    """
    rep = VerificationReport()
    needles = [
        n for n in _compile_needles(removed_values)
        if not (still_present_text and n.search(_squash(still_present_text)))
    ]
    doc = pymupdf.open(out_path)
    try:
        flags = pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_PRESERVE_LIGATURES
        for page in doc.pages():
            text = page.get_text("text", flags=flags)
            words = " ".join(w[4] for w in page.get_text("words", flags=flags))
            if _hit(needles, text) or _hit(needles, words):
                rep.add(f"page {page.number + 1}: text layer")
            if list(page.annots() or []):
                rep.add(f"page {page.number + 1}: annotations remain")
            for lnk in page.get_links():
                if lnk.get("kind") == pymupdf.LINK_URI:
                    rep.add(f"page {page.number + 1}: external link remains")
        meta = " ".join(str(v) for v in (doc.metadata or {}).values())
        if _hit(needles, meta):
            rep.add("document info")
        if doc.embfile_names():
            rep.add("embedded files remain")
        if _hit(needles, " ".join(str(t[1]) for t in doc.get_toc())):
            rep.add("bookmarks")
        cat = doc.pdf_catalog()
        for key in ("OpenAction", "AA", "Names"):
            if doc.xref_get_key(cat, key)[0] != "null":
                rep.add(f"catalog /{key} remains")
        for xref in range(1, doc.xref_length()):
            for blob in _object_texts(doc, xref):
                if _hit(needles, blob):
                    rep.add(f"object {xref}")
                    break
    finally:
        doc.close()
    return rep
