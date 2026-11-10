"""Pure (Qt-free) helpers that make AI PII detection precise.

Presidio reports character offsets into the string it analyzed. This module
builds that string from PyMuPDF word boxes so the offsets map back to exact
rectangles, filters weak or generic hits, and propagates a detected value to
its other occurrences as *whole words* only.
"""

import json
import pathlib
import re
import statistics
from bisect import bisect_left
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

import lexicon_it

Rect4 = Tuple[float, float, float, float]

# (entity id, Italian label) shown in the selection dialog. An id may cover
# several Presidio entity types.
ENTITY_GROUPS: List[Tuple[str, str, Tuple[str, ...]]] = [
    ("PERSON", "Nomi e cognomi", ("PERSON",)),
    ("LOCATION", "Luoghi e indirizzi", ("LOCATION",)),
    ("EMAIL", "Email", ("EMAIL_ADDRESS",)),
    ("PHONE", "Telefono", ("PHONE_NUMBER",)),
    ("IBAN", "IBAN", ("IBAN_CODE",)),
    ("CARD", "Carte di credito", ("CREDIT_CARD",)),
    ("CRYPTO", "Wallet crypto", ("CRYPTO",)),
    ("FISCAL", "Codice fiscale", ("IT_FISCAL_CODE",)),
    ("VAT", "Partita IVA", ("IT_VAT_CODE",)),
    ("LICENSE", "Patente", ("IT_DRIVER_LICENSE",)),
    ("IDCARD", "Carta d'identità", ("IT_IDENTITY_CARD",)),
    ("PASSPORT", "Passaporto", ("IT_PASSPORT",)),
    ("BIRTHDATE", "Date di nascita", ("DATE_OF_BIRTH",)),
    ("HEALTHID", "Identificativi sanitari", ("HEALTH_ID",)),
    ("EXEMPT", "Codici di esenzione", ("HEALTH_EXEMPTION",)),
]
ALL_GROUP_IDS: List[str] = [g[0] for g in ENTITY_GROUPS]
ALL_ENTITY_TYPES: List[str] = [t for g in ENTITY_GROUPS for t in g[2]]

# Minimum Presidio score per entity type. Checksum-backed recognizers score
# 1.0 when valid; weak pattern recognizers score low without context words.
ENTITY_SCORE_THRESHOLDS: Dict[str, float] = {
    "PERSON": 0.5,
    "LOCATION": 0.5,
    "EMAIL_ADDRESS": 0.5,
    "PHONE_NUMBER": 0.4,
    "IBAN_CODE": 0.3,
    "CREDIT_CARD": 0.3,
    "CRYPTO": 0.3,
    "IT_FISCAL_CODE": 0.3,
    "IT_VAT_CODE": 0.3,
    "IT_DRIVER_LICENSE": 0.5,
    "IT_IDENTITY_CARD": 0.4,
    "IT_PASSPORT": 0.3,
    "DATE_OF_BIRTH": 0.5,
    "HEALTH_ID": 0.5,
    "HEALTH_EXEMPTION": 0.5,
}

# Entity types found by this module's own patterns, not by Presidio.
NON_PRESIDIO_TYPES: FrozenSet[str] = frozenset(
    {"DATE_OF_BIRTH", "HEALTH_ID", "HEALTH_EXEMPTION"}
)

_NER_TYPES = {"PERSON", "LOCATION"}

_GENERIC_WORDS = {
    "sig", "sig.ra", "sigra", "signor", "signora", "signore", "dott", "dott.ssa",
    "dottssa", "dr", "dra", "prof", "prof.ssa", "ing", "avv", "geom", "rag",
    "spett", "spett.le", "spettle", "gentile", "egregio", "egregia", "oggetto",
    "cliente", "fattura", "via", "viale", "piazza", "corso", "largo", "vicolo",
    "mr", "mrs", "ms", "miss", "dear", "subject", "re", "cc", "pec",
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
    "agosto", "settembre", "ottobre", "novembre", "dicembre",
    "lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "italia", "italy",
    # Labels, headings and list words that document/CV layouts capitalize.
    "telefono", "tel", "cellulare", "cell", "fax", "email", "mail", "web",
    "sito", "indirizzo", "residenza", "domicilio", "sede", "luogo", "data",
    "nome", "cognome", "nato", "nata", "presente", "attuale", "configurazione",
    "esperienza", "esperienze", "competenze", "formazione", "istruzione",
    "lingue", "lingua", "inglese", "italiano", "francese", "tedesco",
    "spagnolo", "profilo", "curriculum", "vitae", "obiettivo", "referenze",
    "interessi", "hobby", "patente", "certificazioni", "progetti", "sviluppo",
    "phone", "mobile", "address", "name", "surname", "present", "current",
    "configuration", "experience", "skills", "education", "languages",
    "english", "italian", "french", "german", "spanish", "profile", "summary",
    "objective", "references", "interests", "certifications", "projects",
    # Names of the identifiers themselves ("Partita IVA:", "Codice fiscale").
    "partita", "iva", "codice", "fiscale", "cf", "iban", "carta", "identità",
    "documento", "passaporto", "referente", "contatto", "titolare",
    # Job titles, often capitalized at the start of a CV line.
    "sviluppatore", "ingegnere", "analista", "responsabile", "consulente",
    "tecnico", "direttore", "amministratore", "impiegato", "impiegata",
    "programmatore", "progettista", "sistemista", "developer", "engineer",
    "analyst", "manager", "consultant", "technician", "director", "administrator",
}
_HONORIFICS = {
    "sig", "sig.", "sig.ra", "signor", "signora", "signore", "dott", "dott.",
    "dott.ssa", "dr", "dr.", "prof", "prof.", "prof.ssa", "ing", "ing.", "avv",
    "avv.", "geom", "geom.", "rag", "rag.", "mr", "mr.", "mrs", "mrs.", "ms",
    "ms.", "spett.le", "gentile", "egregio", "egregia",
    "referente", "contatto", "titolare", "responsabile",
}
_STREET_WORDS = {
    "via", "viale", "v.le", "piazza", "p.za", "piazzale", "corso", "c.so",
    "largo", "vicolo", "strada", "str.", "contrada", "località", "loc.",
    "frazione", "fraz.", "borgo", "lungotevere", "c/o", "street", "st.",
    "avenue", "road", "rd.", "lane",
}
_EDGE_PUNCT = " \t\r\n.,;:!?()[]{}<>\"'«»“”‘’-–—•·*▪►■"


@dataclass
class WordBox:
    start: int
    end: int
    rect: Rect4
    line_key: Tuple[int, int]
    text: str = ""
    # False for words over an image or from OCR: redaction there blanks
    # pixels, so those boxes are never reduced to a thin band.
    native: bool = True
    # The box before any clamping (what the word really occupies).
    orig_rect: Optional[Rect4] = None
    # True when the line spacing is so tight that no band can spare the
    # neighbouring lines; the full box is kept (never a leak, may damage).
    collision: bool = False


@dataclass
class PageTextIndex:
    """Analysis text plus a map from character offsets to word rectangles."""

    text: str = ""
    words: List[WordBox] = field(default_factory=list)

    @property
    def collisions(self) -> int:
        return sum(1 for w in self.words if w.collision)


@dataclass
class Candidate:
    start: int
    end: int
    text: str
    entity_type: str
    score: float
    rects: List[Rect4] = field(default_factory=list)
    # "accepted" candidates are applied; "suggested" ones await user review.
    state: str = "accepted"
    reasons: List[str] = field(default_factory=list)


NL = chr(10)
_LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi",
    "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st",
}


def _normalize_token(token: str) -> str:
    """Expand typographic ligatures so NER sees ordinary letters."""
    if not any(ch in _LIGATURES for ch in token):
        return token
    return "".join(_LIGATURES.get(ch, ch) for ch in token)


def _is_vertical(rect: Rect4, text: str) -> bool:
    w, h = rect[2] - rect[0], rect[3] - rect[1]
    return len(text) > 1 and h > 1.5 * w


def _near_duplicate(a: Rect4, b: Rect4) -> bool:
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    if ix <= 0 or iy <= 0:
        return False
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return ix * iy >= 0.8 * min(area_a, area_b)


# A glyph is deleted by a redaction when the rectangle intersects its box
# shrunk by this fraction of its width (each side) and height (top, bottom).
# Measured on PyMuPDF 2.1 / MuPDF 1.28; pinned by tests/test_geometry.py.
GLYPH_CORE_INSET = 0.10

# Smallest share of its own height a word box keeps after clamping. Below it
# the text overlaps its neighbours so heavily that trimming would risk
# leaving ink uncovered; the original box is kept.
CLAMP_MIN_RATIO = 0.3


# Safety margin (pt) kept between a band and the deletion core of a neighbour,
# and the least a band must overlap its own word's core.
GLYPH_CORE_MARGIN = 0.3
MIN_CORE_HIT = 0.5


def clamp_word_rects(
    boxes: List["WordBox"], ocr: bool = False, min_ratio: Optional[float] = None
) -> List[Rect4]:
    """Vertical extents of word boxes trimmed where they hit another line.

    PyMuPDF word boxes span ascender to descender (about 1.37 x the font
    size), so with normal leading they overlap the lines above and below.
    A box is trimmed only against boxes of *other* lines that overlap it
    horizontally, and only on the side facing that neighbour. Words on the
    same line never affect each other, so mixed font sizes keep their full
    height.

    Native text: a glyph is deleted only when the rectangle reaches its
    *core* (its box inset by GLYPH_CORE_INSET), so the band stops just short
    of the neighbour's core instead of its box edge. That spares neighbours
    at much tighter leading. If the remaining band would not reach the
    word's own core, the full box is kept and the word is flagged
    ``collision``.

    Image / OCR words (and everything when `ocr` is set): redaction blanks
    pixels, so the cut is at the middle of the overlap with a small
    horizontal margin, and never thinner than `min_ratio` of the height.
    """
    if min_ratio is None:
        min_ratio = CLAMP_MIN_RATIO
    n = len(boxes)
    out: List[Rect4] = [b.rect for b in boxes]
    if n < 2:
        return out
    order = sorted(range(n), key=lambda i: boxes[i].rect[1])
    y0s = [boxes[i].rect[1] for i in order]
    max_h = max(b.rect[3] - b.rect[1] for b in boxes)
    for i in range(n):
        b = boxes[i]
        x0, y0, x1, y1 = b.rect
        h = y1 - y0
        if h <= 0 or _is_vertical(b.rect, b.text):
            continue
        pixel_mode = ocr or not b.native
        lo = bisect_left(y0s, y0 - max_h)
        hi = bisect_left(y0s, y1)
        ny0, ny1 = y0, y1
        touched = False
        for j in order[lo:hi]:
            if j == i:
                continue
            o = boxes[j]
            if o.line_key == b.line_key or _is_vertical(o.rect, o.text):
                continue
            ox0, oy0, ox1, oy1 = o.rect
            if ox1 <= x0 or ox0 >= x1 or oy1 <= y0 or oy0 >= y1:
                continue
            if _near_duplicate(b.rect, o.rect):
                continue
            touched = True
            below = (oy0 + oy1) / 2 > (y0 + y1) / 2
            if pixel_mode:
                mid = (max(y0, oy0) + min(y1, oy1)) / 2
                if below:
                    ny1 = min(ny1, mid)
                else:
                    ny0 = max(ny0, mid)
            else:
                oh = oy1 - oy0
                if below:
                    ny1 = min(ny1, oy0 + GLYPH_CORE_INSET * oh - GLYPH_CORE_MARGIN)
                else:
                    ny0 = max(ny0, oy1 - GLYPH_CORE_INSET * oh + GLYPH_CORE_MARGIN)
        if not touched:
            continue
        if pixel_mode:
            if (ny1 - ny0) < min_ratio * h:
                continue
            pad = 1.0
            out[i] = (x0 - pad, ny0, x1 + pad, ny1)
            continue
        core0, core1 = y0 + GLYPH_CORE_INSET * h, y1 - GLYPH_CORE_INSET * h
        if min(ny1, core1) - max(ny0, core0) < MIN_CORE_HIT:
            b.collision = True
            continue
        out[i] = (x0, ny0, x1, ny1)
    return out


def build_page_index(
    words: Iterable[Sequence[Any]],
    *,
    clamp: bool = True,
    ocr: bool = False,
    image_rects: Sequence[Rect4] = (),
    merge_spaced: bool = True,
    join_hyphen: bool = True,
) -> PageTextIndex:
    """Build the analysis string from `page.get_text("words")` tuples.

    Besides joining words, this: expands ligatures; glues letter-spaced runs
    ("C o m m i s s i o n e") into one analysis word; joins a word split by a
    line-end hyphen; and clamps each word box against neighbouring lines.
    """
    ordered = sorted(
        (w for w in words if str(w[4]).strip()),
        key=lambda w: (int(w[5]), int(w[6]), int(w[7])),
    )
    n = len(ordered)
    tokens = [_normalize_token(str(w[4])) for w in ordered]
    keys = [(int(w[5]), int(w[6])) for w in ordered]
    rects = [(w[0], w[1], w[2], w[3]) for w in ordered]

    # Separator placed *before* word i (i >= 1).
    seps: List[str] = [""] * n
    for i in range(1, n):
        seps[i] = (
            " " if keys[i] == keys[i - 1]
            else (NL if keys[i][0] == keys[i - 1][0] else NL + NL)
        )

    if merge_spaced:
        i = 0
        while i < n:
            j = i
            while (
                j + 1 < n and keys[j + 1] == keys[i]
                and len(tokens[j]) == 1 and tokens[j].isalnum()
                and len(tokens[j + 1]) == 1 and tokens[j + 1].isalnum()
            ):
                j += 1
            if j - i + 1 >= 4:
                gaps = [rects[k + 1][0] - rects[k][2] for k in range(i, j)]
                med = statistics.median(gaps)
                for k in range(i, j):
                    seps[k + 1] = " " if gaps[k - i] > 1.8 * med + 0.5 else ""
            i = j + 1

    if join_hyphen:
        for i in range(n - 1):
            t = tokens[i]
            if (
                len(t) >= 3 and t.endswith("-") and t[:-1].isalpha()
                and keys[i + 1][0] == keys[i][0]
                and keys[i + 1][1] == keys[i][1] + 1
                and tokens[i + 1][:1].islower()
            ):
                tokens[i] = t[:-1]
                seps[i + 1] = ""

    parts: List[str] = []
    boxes: List[WordBox] = []
    pos = 0
    for i in range(n):
        if i:
            parts.append(seps[i])
            pos += len(seps[i])
        cx, cy = (rects[i][0] + rects[i][2]) / 2, (rects[i][1] + rects[i][3]) / 2
        on_image = any(
            r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in image_rects
        )
        boxes.append(WordBox(
            pos, pos + len(tokens[i]), rects[i], keys[i], tokens[i],
            native=not (ocr or on_image), orig_rect=rects[i],
        ))
        parts.append(tokens[i])
        pos += len(tokens[i])
    if clamp and boxes:
        for box, r in zip(boxes, clamp_word_rects(boxes, ocr=ocr)):
            box.rect = r
    return PageTextIndex("".join(parts), boxes)


def _union(rects: List[Rect4]) -> Rect4:
    return (
        min(r[0] for r in rects), min(r[1] for r in rects),
        max(r[2] for r in rects), max(r[3] for r in rects),
    )


def span_to_rects(index: PageTextIndex, start: int, end: int) -> List[Rect4]:
    """Rectangles (one per line) for the words a span covers.

    A word is included only when the span covers at least half of it; it is
    never expanded to a whole word, so over-selection is impossible.
    """
    by_line: Dict[Tuple[int, int], List[Rect4]] = {}
    for w in index.words:
        overlap = min(end, w.end) - max(start, w.start)
        if overlap <= 0:
            continue
        if overlap * 2 < (w.end - w.start):
            continue
        by_line.setdefault(w.line_key, []).append(w.rect)
    return [_union(rs) for _, rs in sorted(by_line.items())]


def filter_results(
    results: Iterable[Any], text: str, enabled_types: Iterable[str]
) -> List[Candidate]:
    """Keep results of enabled types whose score reaches the type threshold."""
    enabled = set(enabled_types)
    out: List[Candidate] = []
    for r in results:
        etype = r.entity_type
        if etype not in enabled:
            continue
        if r.score < ENTITY_SCORE_THRESHOLDS.get(etype, 0.5):
            continue
        # A name or place never spans a line break; NER glues a heading or
        # label ("Graziano Mariella\nTelefono") to the previous line, so
        # judge each line of an NER span on its own.
        if etype in _NER_TYPES:
            segments = [
                (r.start + m.start(), m.group())
                for m in re.finditer(r"[^\r\n]+", text[r.start:r.end])
            ]
        else:
            segments = [(r.start, text[r.start:r.end])]
        for seg_start, raw in segments:
            lead = len(raw) - len(raw.lstrip(_EDGE_PUNCT))
            value = raw.strip(_EDGE_PUNCT)
            if len(value) <= 2:
                continue
            start = seg_start + lead
            out.append(
                Candidate(start, start + len(value), value, etype, float(r.score))
            )
    return out


def _line_bounds(text: str, start: int, end: int) -> Tuple[int, int]:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    return line_start, len(text) if line_end == -1 else line_end


def reject_label_like_hits(
    candidates: Iterable[Candidate], text: str
) -> List[Candidate]:
    """Drop single-word PERSON/LOCATION hits that look like labels or headings.

    Document layouts capitalize words that are not names, and the NER model
    tags them ("Telefono:", "- Presente", "Configurazione"). A one-word hit
    is rejected when it is:
    - followed by a colon (a field label);
    - a list item (preceded by a bullet or dash on its line);
    - a PERSON alone on its line (a heading);
    - also used in lowercase elsewhere on the page (a common noun, whereas a
      real name is essentially never written in lowercase).
    Multi-word spans such as "Mario Rossi" are left alone.
    """
    out: List[Candidate] = []
    for c in candidates:
        if c.entity_type not in _NER_TYPES or len(c.text.split()) != 1:
            out.append(c)
            continue
        after = text[c.end:c.end + 8].lstrip(" \t")
        if after.startswith(":"):
            continue
        ls, le = _line_bounds(text, c.start, c.end)
        before_raw = text[ls:c.start].strip()
        rest = text[c.end:le].strip(_EDGE_PUNCT)
        if before_raw and not before_raw.strip(_EDGE_PUNCT):
            continue  # only bullets/dashes before it: a list item
        if c.entity_type == "PERSON" and not before_raw and not rest:
            continue  # a lone word on its own line
        if c.entity_type == "PERSON" and not before_raw.strip(_EDGE_PUNCT):
            following = text[c.end:le].split()
            if following and following[0][:1].islower():
                continue  # capitalized only because it starts the line
        lowered = c.text.lower()
        if lowered != c.text and re.search(
            r"(?<!\w)" + re.escape(lowered) + r"(?!\w)", text
        ):
            continue
        out.append(c)
    return out


def _strip_honorifics(c: Candidate) -> Optional[Candidate]:
    tokens = list(re.finditer(r"\S+", c.text))
    drop = 0
    while drop < len(tokens) and tokens[drop].group().lower() in _HONORIFICS:
        drop += 1
    if drop == 0:
        return c
    if drop == len(tokens):
        return None
    shift = tokens[drop].start()
    return Candidate(
        c.start + shift, c.end, c.text[shift:], c.entity_type, c.score
    )


def _split_person_address(
    c: Candidate,
) -> Tuple[Optional[Candidate], Optional[Candidate]]:
    """Cut a PERSON span at the first street word or number token.

    NER often glues a name to the address that follows it ("Rossini Marco
    Via Garibaldi"). Returns ``(person, address_tail)``; either may be None.
    """
    tokens = list(re.finditer(r"\S+", c.text))
    for i, tok in enumerate(tokens):
        word = tok.group().strip(",;:()").lower()
        if word in _STREET_WORDS or any(ch.isdigit() for ch in word):
            if i == 0:
                return None, Candidate(
                    c.start, c.end, c.text, "LOCATION", c.score
                )
            cut = tokens[i].start()
            person_text = c.text[:cut].rstrip(_EDGE_PUNCT + " ")
            person = Candidate(
                c.start, c.start + len(person_text), person_text,
                c.entity_type, c.score,
            )
            tail_text = c.text[cut:].strip(_EDGE_PUNCT)
            tail = Candidate(
                c.start + cut, c.start + cut + len(tail_text), tail_text,
                "LOCATION", c.score,
            )
            return person, tail
    return c, None


def clean_candidates(
    candidates: Iterable[Candidate],
    stopwords: Optional[Iterable[str]] = None,
    enabled_types: Optional[Iterable[str]] = None,
) -> List[Candidate]:
    """Drop generic/unlikely PERSON and LOCATION hits; other types pass.

    A PERSON span running into an address is cut before the address; the
    address part is kept as a LOCATION only when LOCATION is enabled.
    """
    stop = {s.lower() for s in (stopwords or ())}
    allowed = set(enabled_types) if enabled_types is not None else None
    out: List[Candidate] = []
    for c in candidates:
        if c.entity_type not in _NER_TYPES:
            out.append(c)
            continue
        cleaned: Optional[Candidate] = c
        if c.entity_type == "PERSON":
            cleaned = _strip_honorifics(c)
            tail: Optional[Candidate] = None
            if cleaned is not None:
                cleaned, tail = _split_person_address(cleaned)
            if tail is not None and (allowed is None or "LOCATION" in allowed):
                out.extend(clean_candidates([tail], stop, allowed))
        if cleaned is None or not any(ch.isupper() for ch in cleaned.text):
            continue
        tokens = [t.strip(_EDGE_PUNCT).lower() for t in cleaned.text.split()]
        tokens = [t for t in tokens if t]
        if not tokens or all(t in _GENERIC_WORDS or t in stop for t in tokens):
            continue
        if len(tokens) == 1 and cleaned.text.isupper() and len(cleaned.text) > 12:
            continue
        out.append(cleaned)
    return out


def resolve_overlaps(candidates: Iterable[Candidate]) -> List[Candidate]:
    """Of overlapping spans keep the highest score, then the longest."""
    ranked = sorted(
        candidates, key=lambda c: (-c.score, -(c.end - c.start), c.start)
    )
    kept: List[Candidate] = []
    for c in ranked:
        if not any(c.start < k.end and k.start < c.end for k in kept):
            kept.append(c)
    return sorted(kept, key=lambda c: c.start)


def _whole_word_pattern(value: str, case_sensitive: bool) -> "re.Pattern[str]":
    parts = [re.escape(p) for p in value.split()]
    return re.compile(
        r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)",
        0 if case_sensitive else re.IGNORECASE,
    )


def propagate_whole_word(
    index: PageTextIndex, value: str, case_sensitive: bool = True
) -> List[Rect4]:
    """Rectangles of every whole-word occurrence of `value` on the page."""
    if not value.strip():
        return []
    rects: List[Rect4] = []
    for m in _whole_word_pattern(value, case_sensitive).finditer(index.text):
        rects.extend(span_to_rects(index, m.start(), m.end()))
    return rects


def whole_word_rects(index: PageTextIndex, term: str) -> List[Rect4]:
    """Whole-word, case-insensitive search (blocklist / allowlist)."""
    return propagate_whole_word(index, term, case_sensitive=False)


def expand_group_ids(group_ids: Iterable[str]) -> List[str]:
    """Map dialog group ids to Presidio entity types."""
    wanted = set(group_ids)
    return [t for gid, _, types in ENTITY_GROUPS if gid in wanted for t in types]


def load_enabled_groups(path: pathlib.Path) -> List[str]:
    """Load the remembered selection; default (or on error) is everything."""
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        chosen = [g for g in data.get("enabled", []) if g in ALL_GROUP_IDS]
        return chosen if chosen else list(ALL_GROUP_IDS)
    except Exception:
        return list(ALL_GROUP_IDS)


def save_enabled_groups(path: pathlib.Path, groups: Iterable[str]) -> None:
    try:
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps({"enabled": [g for g in groups if g in ALL_GROUP_IDS]}),
            encoding="utf-8",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Evidence-based classification (Italian-aware), pattern validation and
# geometry policy. Everything below is Qt-free and exercised by the tests.
# ---------------------------------------------------------------------------

# Types validated by a checksum or a rigid format: when such a value is glued
# to a label or to other text it is redacted as a whole token rather than
# dropped, because under-redacting an identifier is a confidentiality breach.
VALIDATED_TYPES: FrozenSet[str] = frozenset({
    "IBAN_CODE", "CREDIT_CARD", "IT_FISCAL_CODE", "IT_VAT_CODE", "CRYPTO",
    "EMAIL_ADDRESS", "HEALTH_ID", "HEALTH_EXEMPTION",
})

ACCEPT_SCORE = 0.7
SUGGEST_SCORE = 0.4


def boundary_ok(
    text: str, start: int, end: int, *, digits_only: bool = False,
    apostrophe_ok: bool = False,
) -> bool:
    """True when the span is not glued to alphanumerics on either side."""
    def glue(ch: str) -> bool:
        if digits_only:
            return ch.isdigit()
        return ch.isalnum() or ch == "_"
    if start > 0:
        ch = text[start - 1]
        if glue(ch) and not (apostrophe_ok and ch in "'’"):
            return False
    if end < len(text) and glue(text[end]):
        return False
    return True


def _context(text: str, start: int, end: int, before: int = 40, after: int = 20) -> str:
    return text[max(0, start - before):start].lower() + " | " + text[end:end + after].lower()


_FISCAL_CTX = ("codice fiscale", "c.f.", "cod. fisc", "cf:", "cf ", "fiscal code", "tax code")
_VAT_CTX = ("p.iva", "p. iva", "partita iva", "partita i.v.a", "vat", "iva ")
_PASSPORT_CTX = ("passaporto", "passport")
_IDCARD_CTX = ("carta d'identit", "carta d’identit", "carta di identit",
               "carta identit", "documento n", "n. documento", "numero documento",
               "c.i.", "cie ", "identity card", "id card")
_LICENSE_CTX = ("patente di guida", "patente n", "n. patente", "numero patente",
                "patente:", "driving licen", "driver's licen", "driver licen")
_PHONE_CTX = ("tel", "cell", "telefono", "phone", "mobile", "fax", "whatsapp",
              "recapito", "contatt", "chiam")
_DATE_LIKE = re.compile(r"^\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}$")
_YEAR_RANGE = re.compile(r"^\d{4}\s*[-–/]\s*\d{4}$")


def refine_pattern_hit(c: Candidate, text: str) -> Tuple[bool, str]:
    """Extra validation of pattern-based hits (not NER). Returns (keep, reason)."""
    t = c.entity_type
    value = text[c.start:c.end]
    ctx = _context(text, c.start, c.end)
    if t in ("IT_FISCAL_CODE", "CRYPTO"):
        if not boundary_ok(text, c.start, c.end):
            return False, "embedded-in-token"
    if t == "IT_FISCAL_CODE":
        has_ctx = any(k in ctx for k in _FISCAL_CTX)
        if not any(ch.isdigit() for ch in value) and not has_ctx:
            return False, "no-digit-no-context"
        if value != value.upper() and not has_ctx:
            return False, "lowercase-no-context"
    elif t == "CREDIT_CARD":
        if not boundary_ok(text, c.start, c.end, digits_only=True):
            return False, "embedded-in-digits"
    elif t == "IT_VAT_CODE":
        if not boundary_ok(text, c.start, c.end, digits_only=True):
            return False, "embedded-in-digits"
        has_ctx = any(k in ctx for k in _VAT_CTX) or value.upper().startswith("IT")
        if (" " in value.strip() or "_" in value) and not has_ctx:
            return False, "spaced-digits-no-context"
        if not has_ctx and c.score < 0.9:
            return False, "no-context"
    elif t == "IT_PASSPORT":
        if not boundary_ok(text, c.start, c.end):
            return False, "embedded-in-token"
        if value != value.upper() or not any(k in ctx for k in _PASSPORT_CTX):
            return False, "no-context"
    elif t == "IT_IDENTITY_CARD":
        if not boundary_ok(text, c.start, c.end):
            return False, "embedded-in-token"
        if value != value.upper() or not any(k in ctx for k in _IDCARD_CTX):
            return False, "no-context"
    elif t == "IT_DRIVER_LICENSE":
        if not boundary_ok(text, c.start, c.end):
            return False, "embedded-in-token"
        if value != value.upper() or not any(k in ctx for k in _LICENSE_CTX):
            return False, "no-context"
    elif t == "PHONE_NUMBER":
        compact = value.strip()
        digits = re.sub(r"\D", "", compact)
        if _DATE_LIKE.match(compact) or _YEAR_RANGE.match(compact):
            return False, "date-like"
        if not boundary_ok(text, c.start, c.end, digits_only=True):
            return False, "embedded-in-digits"
        before = text[c.start - 1] if c.start > 0 else " "
        if before.isalpha():
            return False, "embedded-in-letters"
        has_ctx = any(k in ctx for k in _PHONE_CTX)
        plausible_start = compact.startswith(("+", "00", "0", "3"))
        if len(digits) < 8 or len(digits) > 15:
            return False, "digit-count"
        if not (plausible_start or has_ctx):
            return False, "implausible-prefix"
    return True, ""


def strip_lexicon_edges(
    candidates: Iterable[Candidate],
) -> Tuple[List[Candidate], int]:
    """Cut ordinary words off the start/end of PERSON/LOCATION spans.

    "Prescrivo Augmentin" becomes "Augmentin"; "Certifico" alone disappears.
    Returns the remaining candidates and the number removed or trimmed.
    """
    out: List[Candidate] = []
    dropped = 0
    for c in candidates:
        if c.entity_type not in _NER_TYPES:
            out.append(c)
            continue
        toks = list(re.finditer(r"\S+", c.text))
        lo, hi = 0, len(toks)
        while lo < hi and lexicon_it.is_common_word(toks[lo].group()):
            lo += 1
        while hi > lo and lexicon_it.is_common_word(toks[hi - 1].group()):
            hi -= 1
        if lo == hi:
            dropped += 1
            continue
        if lo == 0 and hi == len(toks):
            out.append(c)
            continue
        dropped += 1
        s0, e0 = toks[lo].start(), toks[hi - 1].end()
        raw = c.text[s0:e0]
        value = raw.strip(_EDGE_PUNCT)
        if len(value) <= 2:
            continue
        start = c.start + s0 + (len(raw) - len(raw.lstrip(_EDGE_PUNCT)))
        out.append(Candidate(start, start + len(value), value, c.entity_type,
                             c.score, state=c.state, reasons=list(c.reasons)))
    return out, dropped


def reject_fragment_hits(
    candidates: Iterable[Candidate], used_ocr: bool = False
) -> Tuple[List[Candidate], int]:
    """Drop NER hits that look like text-layer or OCR fragments."""
    out: List[Candidate] = []
    dropped = 0
    min_alpha = 4 if used_ocr else 3
    for c in candidates:
        if c.entity_type not in _NER_TYPES:
            out.append(c)
            continue
        toks = c.text.split()
        multi = len(toks) >= 2
        letters = sum(ch.isalpha() for ch in c.text)
        non_space = sum(not ch.isspace() for ch in c.text) or 1
        bad = False
        if letters / non_space < 0.8:
            bad = True
        elif not multi and letters < min_alpha:
            bad = True
        elif used_ocr and any(re.search(r"[a-zà-ÿ][A-ZÀ-Ý]", t) for t in toks):
            bad = True
        elif any(t.endswith("-") and len(t) > 2 for t in toks):
            bad = True
        if bad:
            dropped += 1
        else:
            out.append(c)
    return out, dropped


def merge_adjacent_lines(
    candidates: List[Candidate], text: str
) -> List[Candidate]:
    """Join PERSON hits on consecutive lines ("Esposito" / "Giovanni")."""
    ordered = sorted(candidates, key=lambda c: c.start)
    out: List[Candidate] = []
    i = 0
    while i < len(ordered):
        c = ordered[i]
        if (
            c.entity_type == "PERSON" and i + 1 < len(ordered)
            and len(c.text.split()) == 1
        ):
            n = ordered[i + 1]
            gap = text[c.end:n.start]
            if (
                n.entity_type == "PERSON" and len(n.text.split()) == 1
                and gap == NL
                and not lexicon_it.is_common_word(c.text)
                and not lexicon_it.is_common_word(n.text)
                and c.text[:1].isupper() and n.text[:1].isupper()
            ):
                out.append(Candidate(
                    c.start, n.end, text[c.start:n.end], "PERSON",
                    max(c.score, n.score),
                ))
                i += 2
                continue
        out.append(c)
        i += 1
    return out


_PERSON_CUES = (
    "paziente", "assistito", "assistita", "sottoscritto", "sottoscritta",
    "signor", "sig.", "sig.ra", "dott", "prof", "avv", "ing.", "nome",
    "cognome", "nato", "nata", "intestatario", "intestataria", "titolare",
    "firmato", "gentile", "egregio", "egregia", "spett", "patient", "mr.",
    "mrs.", "ms.", "dear", "tutore", "genitore", "figlio", "figlia", "coniuge",
)
_LOCATION_CUES = (
    "nato a", "nata a", "nato il", "residente a", "residente in", "residente presso",
    "domiciliato", "domiciliata", "con sede in", "con sede a", "sede legale",
    "comune di", "provincia di", "in via", "presso", "luogo di nascita",
    "indirizzo", "residenza", "domicilio", "born in", "lives in",
)
_PROVINCE_AFTER = re.compile(r"^\s*[\(\[]\s*[A-Z]{2}\s*[\)\]]|^\s*,?\s*\d{5}\b|^\s*,\s*\d+\b")


def _is_name_shaped(tokens: List[str]) -> bool:
    return len(tokens) >= 2 and all(
        t[:1].isupper()
        and t.replace("'", "").replace("’", "").replace("-", "").isalpha()
        for t in tokens
    )


def score_ner_candidate(
    c: Candidate, text: str, verb_like: Iterable[str] = ()
) -> Tuple[float, List[str]]:
    """Evidence-based score (0..1) for a PERSON/LOCATION hit.

    Presidio gives every NER hit the same constant, so the model score cannot
    separate "Mario Rossi" from "Certifico". Evidence in the text can.
    """
    verb = {v.lower() for v in verb_like}
    tokens = [t.strip(_EDGE_PUNCT) for t in c.text.split()]
    tokens = [t for t in tokens if t]
    lowered = [t.lower() for t in tokens]
    score = 0.5
    why: List[str] = []
    ls, le = _line_bounds(text, c.start, c.end)
    before_raw = text[ls:c.start]
    before_ctx = text[max(0, c.start - 30):c.start].lower()
    after_ctx = text[c.end:c.end + 12]
    single = len(tokens) == 1
    all_caps = c.text.isupper() and len(c.text) > 2

    cues = _PERSON_CUES if c.entity_type == "PERSON" else _LOCATION_CUES
    if any(cue in before_ctx for cue in cues):
        score += 0.35
        why.append("context-cue")
    if c.entity_type == "PERSON":
        if _is_name_shaped(tokens):
            score += 0.25
            why.append("name-shape")
        if any(lexicon_it.is_given_name(t) for t in tokens):
            score += 0.2
            why.append("given-name")
        elif len(tokens) >= 2 and any(lexicon_it.is_known_surname(t) for t in tokens):
            score += 0.15
            why.append("known-surname")
    else:
        if any(lexicon_it.is_known_place(t) for t in tokens) or lexicon_it.is_known_place(c.text):
            score += 0.3
            why.append("known-place")
        elif any(lexicon_it.is_ambiguous_place(t) for t in tokens) or lexicon_it.is_ambiguous_place(c.text):
            score += 0.1
            why.append("ambiguous-place")
        pm = _PROVINCE_AFTER.match(after_ctx)
        if pm:
            code = re.search(r"[A-Z]{2}", pm.group())
            bracketed = pm.group().lstrip().startswith(("(", "["))
            if not bracketed or (code and code.group() in lexicon_it.province_codes()):
                score += 0.2
                why.append("province-or-postcode")
        if len(tokens) >= 2 and _is_name_shaped(tokens):
            score += 0.1
    occurrences = len(re.findall(
        r"(?<!\w)" + re.escape(c.text) + r"(?!\w)", text
    ))
    if occurrences >= 2:
        score += 0.15
        why.append("repeated")

    if any(lexicon_it.is_common_word(t) for t in tokens):
        score -= 0.35 if single else 0.2
        why.append("lexicon")
    if any(t in verb or t in lexicon_it.verb_forms() for t in lowered):
        score -= 0.25
        why.append("verb-form")
    if single and not before_raw.strip(_EDGE_PUNCT):
        score -= 0.2
        why.append("line-start")
    if all_caps and not (
        any(lexicon_it.is_given_name(t) or lexicon_it.is_known_place(t) for t in tokens)
    ):
        score -= 0.2
        why.append("all-caps")
    nxt = after_ctx.strip().split()
    if nxt and nxt[0].lower() in ("che", "di") and single:
        score -= 0.1
        why.append("followed-by-function-word")
    if not tokens:
        score = 0.0
    return max(0.0, min(1.0, score)), why


def evaluate_ner_candidates(
    candidates: Iterable[Candidate], text: str, *, health_mode: bool = False,
    verb_like: Iterable[str] = (),
) -> Tuple[List[Candidate], int]:
    """Assign each PERSON/LOCATION hit a state: accepted / suggested / dropped.

    Field labels ("Nome:") and list items are rejected outright. The rest is
    scored from evidence; uncertain hits become *suggestions* the user
    reviews instead of being silently applied or lost. In health mode no
    hit is silently dropped: low scores become suggestions too.
    """
    out: List[Candidate] = []
    dropped = 0
    verb_like = list(verb_like)
    for c in candidates:
        if c.entity_type not in _NER_TYPES or "address-pattern" in c.reasons:
            out.append(c)
            continue
        after = text[c.end:c.end + 8].lstrip(" \t")
        ls, _le = _line_bounds(text, c.start, c.end)
        before_raw = text[ls:c.start].strip()
        single = len(c.text.split()) == 1
        if single and after.startswith(":"):
            dropped += 1
            continue
        if single and before_raw and not before_raw.strip(_EDGE_PUNCT):
            dropped += 1  # list item
            continue
        score, why = score_ner_candidate(c, text, verb_like)
        if score >= ACCEPT_SCORE:
            state = "accepted"
        elif score >= SUGGEST_SCORE or health_mode:
            state = "suggested"
            if score < SUGGEST_SCORE:
                why.append("low-confidence")
        else:
            dropped += 1
            continue
        out.append(Candidate(
            c.start, c.end, c.text, c.entity_type, score, state=state, reasons=why
        ))
    return out, dropped


_DOB_NUM = re.compile(
    r"(?i)\b(?:nato|nata|nascita|born|dob)\b[^\n]{0,40}?"
    r"(?P<d>(?<!\d)\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*(?:19|20)?\d{2}(?!\d))"
)
_DOB_TXT = re.compile(
    r"(?i)\b(?:nato|nata|nascita|born)\b[^\n]{0,40}?"
    r"(?P<d>(?<!\d)\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|"
    r"agosto|settembre|ottobre|novembre|dicembre|january|february|march|april|may|"
    r"june|july|august|september|october|november|december)\s+(?:19|20)\d{2})"
)
_REGION = r"(?:010|020|030|041|042|050|060|070|080|090|1[0-9]0|200)"
# Tessera sanitaria: 20 digits = 80 (health card) + 380 (Italy) + 00 + ISTAT
# region code + 9-digit serial + check digit (no public check algorithm).
_TESSERA = re.compile(
    r"(?<!\d)(?P<d>80\s?380\s?00\s?" + _REGION + r"(?:\s?\d){10})(?!\d)"
)
# NRE (electronic prescription number): 15 characters = region/PA code (3
# digits) + lot code (2 alphanumeric) + 10 digits; printed forms may carry
# spaces or asterisks around/inside it.
_NRE = re.compile(
    r"(?<![0-9A-Za-z])\*?(?P<d>" + _REGION
    + r"[\s*]?[0-9A-Z]{2}[\s*]?(?:\d[\s*]?){9}\d)\*?(?![0-9A-Za-z])"
)
_NRE_CTX = ("nre", "ricetta", "n. ricetta", "numero ricetta", "prescrizione",
            "ricetta elettronica", "promemoria")
# Exemption codes: income E01-E04, invalidity C01-C06, work L01-L04, service
# S01-S03, war G01-G02, rare diseases R + letter + 4 characters (RA0010...).
_EXEMPT = re.compile(
    r"(?<![A-Z0-9])(?P<d>E0[1-4]|C0[1-6]|L0[1-4]|S0[1-3]|G0[12]|R[A-Z][A-Z0-9]\d{3})(?![A-Z0-9])"
)
_EXEMPT_CTX = ("esenzione", "esente", "cod. es", "codice esenzione", "esenz.")


def _ctx_before(text: str, start: int, words: Tuple[str, ...], span: int = 60) -> bool:
    window = text[max(0, start - span):start].lower()
    return any(w in window for w in words)


def detect_health_patterns(
    text: str, enabled: Iterable[str], health_mode: bool = False
) -> List[Candidate]:
    """Date of birth, health card, prescription and exemption codes.

    Everything is anchored: dates of birth on "nato/a il", the prescription
    number and exemption codes on their label. Without the label a hit is
    only a *suggestion*, and only in health mode.
    """
    on = set(enabled)
    out: List[Candidate] = []
    if "DATE_OF_BIRTH" in on:
        for rx in (_DOB_NUM, _DOB_TXT):
            for m in rx.finditer(text):
                out.append(Candidate(
                    m.start("d"), m.end("d"), m.group("d"), "DATE_OF_BIRTH", 0.9
                ))
    if "HEALTH_ID" in on:
        for m in _TESSERA.finditer(text):
            if len(re.sub(r"\D", "", m.group("d"))) == 20:
                out.append(Candidate(
                    m.start("d"), m.end("d"), m.group("d"), "HEALTH_ID", 0.9
                ))
        for m in _NRE.finditer(text):
            digits = re.sub(r"[\s*]", "", m.group("d"))
            if len(digits) != 15:
                continue
            if _ctx_before(text, m.start("d"), _NRE_CTX):
                out.append(Candidate(
                    m.start("d"), m.end("d"), m.group("d"), "HEALTH_ID", 0.85
                ))
            elif health_mode:
                out.append(Candidate(
                    m.start("d"), m.end("d"), m.group("d"), "HEALTH_ID", 0.55,
                    state="suggested", reasons=["no-context"],
                ))
    if "HEALTH_EXEMPTION" in on:
        for m in _EXEMPT.finditer(text):
            if _ctx_before(text, m.start("d"), _EXEMPT_CTX, span=40):
                out.append(Candidate(
                    m.start("d"), m.end("d"), m.group("d"), "HEALTH_EXEMPTION", 0.8
                ))
            elif health_mode and not m.group("d")[1:].isalpha():
                out.append(Candidate(
                    m.start("d"), m.end("d"), m.group("d"), "HEALTH_EXEMPTION", 0.5,
                    state="suggested", reasons=["no-context"],
                ))
    return out


# --- addresses: house numbers and postcodes ----------------------------------

_STREET = (
    r"(?:via|viale|v\.le|piazza|p\.za|piazzale|corso|c\.so|largo|vicolo|strada|"
    r"contrada|localit\u00e0|loc\.|frazione|fraz\.|borgo|lungotevere)"
)
_CIVICO = re.compile(
    r"(?i)\b" + _STREET + r"\s+(?:[A-Z\u00c0-\u00dd][\w'\u2019.-]*\s+){0,5}?"
    r"[A-Z\u00c0-\u00dd][\w'\u2019.-]*\s*,?\s*(?:n\.?|nr\.?|civico|n\u00b0)?\s*"
    r"(?P<num>\d{1,4}(?:\s*/\s*[A-Za-z0-9]{1,3}|\s*[A-Za-z](?![a-z])|\s+(?:bis|ter|quater))?)"
    r"(?![\d.,]\d)"
)
_CAP = re.compile(
    r"(?<![\d.,\u20ac$])(?P<cap>\d{5})(?![\d.,%])\s+"
    r"(?P<city>[A-Z\u00c0-\u00dd][\w'\u2019-]+(?:\s+[A-Z\u00c0-\u00dd][\w'\u2019-]+){0,3})"
    r"(?:\s*\(\s*(?P<prov>[A-Z]{2})\s*\))?"
)
_MONEY_BEFORE = ("\u20ac", "euro", "eur", "importo", "totale", "n.", "prot.", "fattura")


def detect_address_parts(
    text: str, enabled: Iterable[str], health_mode: bool = False
) -> List[Candidate]:
    """Street + house number as one span, and postcodes in an address context.

    A postcode needs an anchor (a street before it, a province code or a
    known place after it, or the label "CAP"); prices, protocol numbers,
    dates and quantities never match. Without an anchor it is only a
    suggestion in health mode.
    """
    if "LOCATION" not in set(enabled):
        return []
    out: List[Candidate] = []
    street_ends: List[int] = []
    for m in _CIVICO.finditer(text):
        out.append(Candidate(
            m.start(), m.end("num"), text[m.start():m.end("num")], "LOCATION", 0.95,
            reasons=["address-pattern"],
        ))
        street_ends.append(m.end("num"))
    for m in _CAP.finditer(text):
        cap = m.group("cap")
        if not (10 <= int(cap) <= 98168):
            continue
        before = text[max(0, m.start() - 10):m.start()].lower()
        if any(k in before for k in _MONEY_BEFORE):
            continue
        after = text[m.end("cap"):m.end("cap") + 4]
        if after.startswith((",0", ",00", "\u20ac", "%")):
            continue
        window = text[max(0, m.start() - 6):m.start()].lower()
        prov = m.group("prov")
        anchored = (
            any(0 <= m.start() - e <= 80 for e in street_ends)
            or bool(prov and prov in lexicon_it.province_codes())
            or lexicon_it.is_known_place(m.group("city").split()[0])
            or "cap" in window
        )
        if anchored:
            out.append(Candidate(
                m.start("cap"), m.end("cap"), cap, "LOCATION", 0.9,
                reasons=["address-pattern", "postcode"],
            ))
        elif health_mode:
            out.append(Candidate(
                m.start("cap"), m.end("cap"), cap, "LOCATION", 0.5,
                state="suggested", reasons=["address-pattern", "postcode", "no-anchor"],
            ))
    return out


# --- geometry policy -------------------------------------------------------

def span_word_indices(
    index: PageTextIndex, start: int, end: int, min_ratio: float = 0.5
) -> List[int]:
    """Indices of the words a span covers by at least `min_ratio` of their length."""
    out: List[int] = []
    for i, w in enumerate(index.words):
        overlap = min(end, w.end) - max(start, w.start)
        if overlap <= 0:
            continue
        if overlap < min_ratio * (w.end - w.start):
            continue
        out.append(i)
    return out


def rects_for_words(
    index: PageTextIndex, idxs: Iterable[int], original: bool = False
) -> List[Rect4]:
    """One rectangle per line for the given words (clamped, or `original`)."""
    by_line: Dict[Tuple[int, int], List[Rect4]] = {}
    for i in idxs:
        w = index.words[i]
        by_line.setdefault(w.line_key, []).append(
            w.orig_rect if original and w.orig_rect else w.rect
        )
    return [_union(rs) for _, rs in sorted(by_line.items())]


def resolve_word_indices(
    index: PageTextIndex, c: Candidate
) -> Tuple[List[int], str]:
    """Word indices to redact for a candidate, per the partial-match policy.

    Returns (indices, status). Status is "ok", "glued" (a validated
    identifier stuck to other text: the whole token is redacted) or a
    rejection reason (indices empty).
    """
    text = index.text
    if c.entity_type in _NER_TYPES:
        if not boundary_ok(text, c.start, c.end, apostrophe_ok=True):
            return [], "embedded-in-word"
        idxs = span_word_indices(index, c.start, c.end)
        return (idxs, "ok") if idxs else ([], "partial-word")
    idxs = span_word_indices(index, c.start, c.end)
    if idxs:
        return idxs, "ok"
    if c.entity_type in VALIDATED_TYPES:
        touched = span_word_indices(index, c.start, c.end, min_ratio=0.0)
        if touched:
            return touched, "glued"
    return [], "partial-word"


def protected_word_indices(
    index: PageTextIndex, terms: Iterable[str]
) -> Set[int]:
    """Word indices covered by whole-word occurrences of allowlist terms."""
    protected: Set[int] = set()
    for term in terms:
        term = (term or "").strip()
        if not term:
            continue
        for m in _whole_word_pattern(term, False).finditer(index.text):
            protected.update(span_word_indices(index, m.start(), m.end()))
    return protected


def classify_page(
    results: Iterable[Any],
    index: PageTextIndex,
    enabled_types: Iterable[str],
    *,
    used_ocr: bool = False,
    health_mode: bool = False,
    verb_like: Iterable[str] = (),
    stopwords: Optional[Iterable[str]] = None,
) -> Tuple[List[Candidate], Dict[str, int]]:
    """Run the full candidate pipeline on analyzer results for one page.

    Returns the surviving candidates (state "accepted" or "suggested") and a
    count of rejections per reason (no values, safe to log).
    """
    text = index.text
    enabled = list(enabled_types)
    stats: Dict[str, int] = {}

    def bump(reason: str, n: int = 1) -> None:
        if n:
            stats[reason] = stats.get(reason, 0) + n

    cands = filter_results(results, text, enabled)
    cands.extend(detect_health_patterns(text, enabled, health_mode))
    kept: List[Candidate] = []
    for c in cands:
        if c.entity_type in _NER_TYPES:
            kept.append(c)
            continue
        ok, reason = refine_pattern_hit(c, text)
        if ok:
            kept.append(c)
        else:
            bump(f"pattern:{c.entity_type}:{reason}")
    address = detect_address_parts(text, enabled, health_mode)
    before = len(kept)
    kept = clean_candidates(kept, stopwords=stopwords, enabled_types=enabled)
    bump("generic-word", max(0, before - len(kept)))
    kept, n = strip_lexicon_edges(kept)
    bump("lexicon", n)
    kept, n = reject_fragment_hits(kept, used_ocr)
    bump("fragment", n)
    kept = merge_adjacent_lines(kept, text)
    kept.extend(address)
    kept = resolve_overlaps(kept)
    kept, n = evaluate_ner_candidates(
        kept, text, health_mode=health_mode, verb_like=verb_like
    )
    bump("ner-evidence", n)
    return kept, stats


def build_detections(
    index: PageTextIndex,
    candidates: Iterable[Candidate],
    *,
    allowlist: Iterable[str] = (),
    source: str = "text",
    stats: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """Turn candidates into detections with rectangles.

    Allowlist semantics are by word identity: a word is protected when it is
    part of a whole-word occurrence of an allowlist entry. A detection whose
    words are all protected disappears; a longer detection only loses the
    protected words. Substring containment and rectangle intersection are
    never used, so an allowlist entry cannot suppress a different value.
    """
    terms = [t for t in allowlist if t and t.strip()]
    allow_set = {" ".join(t.lower().split()) for t in terms}
    protected = protected_word_indices(index, terms) if terms else set()

    def note(reason: str) -> None:
        if stats is not None:
            stats[reason] = stats.get(reason, 0) + 1

    out: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str]] = set()
    for c in candidates:
        value = c.text
        clean = " ".join(value.strip(_EDGE_PUNCT).lower().split())
        if not clean:
            continue
        if clean in allow_set:
            note("allowlist")
            continue
        idxs, status = resolve_word_indices(index, c)
        if not idxs:
            note(f"geometry:{status}")
            continue
        idxs = [i for i in idxs if i not in protected]
        if not idxs:
            note("allowlist")
            continue
        rects = rects_for_words(index, idxs)
        full_rects = rects_for_words(index, idxs, original=True)
        key = (value, c.entity_type)
        if key not in seen:
            seen.add(key)
            pattern = _whole_word_pattern(
                value, c.entity_type in _NER_TYPES
            )
            for m in pattern.finditer(index.text):
                extra_idx = [
                    i for i in span_word_indices(index, m.start(), m.end())
                    if i not in protected
                ]
                for r, fr in zip(
                    rects_for_words(index, extra_idx),
                    rects_for_words(index, extra_idx, original=True),
                ):
                    if r not in rects:
                        rects.append(r)
                        full_rects.append(fr)
        out.append({
            "text": value,
            "entity_type": c.entity_type,
            "rects": rects,
            "full_rects": full_rects,
            "source": source,
            "score": c.score,
            "state": c.state,
            "reasons": list(c.reasons),
            "glued": status == "glued",
        })
    return out


# --- rectangle merging / dedup ---------------------------------------------

def merge_line_rects(rects: Iterable[Rect4], gap: float = 1.5) -> List[Rect4]:
    """Merge rectangles on the same line that touch or overlap."""
    rs = sorted(rects, key=lambda r: (round((r[1] + r[3]) / 2, 0), r[0]))
    merged: List[Rect4] = []
    for r in rs:
        if merged:
            m = merged[-1]
            oy = min(m[3], r[3]) - max(m[1], r[1])
            minh = min(m[3] - m[1], r[3] - r[1])
            if minh > 0 and oy >= 0.6 * minh and r[0] - m[2] <= gap:
                merged[-1] = (
                    min(m[0], r[0]), min(m[1], r[1]),
                    max(m[2], r[2]), max(m[3], r[3]),
                )
                continue
        merged.append(r)
    return merged


def covered_fraction(rect: Rect4, others: Iterable[Rect4]) -> float:
    """Largest share of `rect` covered by any single rectangle of `others`."""
    area = max(0.0, (rect[2] - rect[0]) * (rect[3] - rect[1]))
    if area <= 0:
        return 1.0
    best = 0.0
    for o in others:
        ix = min(rect[2], o[2]) - max(rect[0], o[0])
        iy = min(rect[3], o[3]) - max(rect[1], o[1])
        if ix > 0 and iy > 0:
            best = max(best, ix * iy / area)
    return best
