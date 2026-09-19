"""Pure (Qt-free) helpers that make AI PII detection precise.

Presidio reports character offsets into the string it analyzed. This module
builds that string from PyMuPDF word boxes so the offsets map back to exact
rectangles, filters weak or generic hits, and propagates a detected value to
its other occurrences as *whole words* only.
"""

import json
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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
}

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


@dataclass
class PageTextIndex:
    """Analysis text plus a map from character offsets to word rectangles."""

    text: str = ""
    words: List[WordBox] = field(default_factory=list)


@dataclass
class Candidate:
    start: int
    end: int
    text: str
    entity_type: str
    score: float
    rects: List[Rect4] = field(default_factory=list)


def build_page_index(words: Iterable[Sequence[Any]]) -> PageTextIndex:
    """Build the analysis string from `page.get_text("words")` tuples."""
    ordered = sorted(
        (w for w in words if str(w[4]).strip()),
        key=lambda w: (int(w[5]), int(w[6]), int(w[7])),
    )
    parts: List[str] = []
    boxes: List[WordBox] = []
    pos = 0
    prev: Optional[Tuple[int, int]] = None
    for w in ordered:
        key = (int(w[5]), int(w[6]))
        if prev is not None:
            sep = " " if key == prev else ("\n" if key[0] == prev[0] else "\n\n")
            parts.append(sep)
            pos += len(sep)
        token = str(w[4])
        boxes.append(WordBox(pos, pos + len(token), (w[0], w[1], w[2], w[3]), key))
        parts.append(token)
        pos += len(token)
        prev = key
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
