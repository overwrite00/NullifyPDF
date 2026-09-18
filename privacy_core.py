"""Privacy primitives for NullifyPDF export workflows.

This module is deliberately independent from PySide / PyMuPDF so that the
security-sensitive policy and restore-map logic can be tested without a GUI.
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


class PrivacyMode(str, Enum):
    """Supported privacy export modes."""

    ANONYMIZE = "anonymize"
    PSEUDONYMIZE = "pseudonymize"


@dataclass(frozen=True)
class PlaceholderOccurrence:
    """Where one placeholder was stamped into the exported PDF.

    Reconstruction uses these coordinates instead of searching the output
    for the placeholder string. Text search is unreliable: MuPDF may wrap
    the placeholder across lines to fit a narrow redaction box, which makes
    the rendered string unfindable even though it is perfectly legible.
    The rect is also the box the *original* value came from, so it is wide
    enough to take that value back at a readable font size.
    """

    page: int
    rect: Tuple[float, float, float, float]


@dataclass(frozen=True)
class PlaceholderEntry:
    """One reversible placeholder mapping entry."""

    placeholder: str
    original: str
    entity_type: str
    page: int
    occurrences: Tuple[PlaceholderOccurrence, ...] = ()


class PlaceholderRegistry:
    """Create stable placeholders for detected personal data."""

    def __init__(self) -> None:
        self._counters: Dict[str, int] = {}
        self._by_value: Dict[tuple[str, str], str] = {}
        self._order: List[str] = []
        self._meta: Dict[str, Tuple[str, str, int]] = {}
        self._occurrences: Dict[str, List[PlaceholderOccurrence]] = {}

    @staticmethod
    def normalize_entity_type(entity_type: Optional[str]) -> str:
        value = (entity_type or "DATA").upper()
        value = re.sub(r"[^A-Z0-9_]+", "_", value).strip("_")
        return value or "DATA"

    def placeholder_for(
        self,
        original: str,
        entity_type: Optional[str] = None,
        page: int = 0,
        rect: Optional[Sequence[float]] = None,
    ) -> str:
        """Return the stable placeholder for `original`, recording this hit.

        Args:
            original: The sensitive value being replaced.
            entity_type: Detected entity type, normalized to a placeholder prefix.
            page: 0-based page index of *this* occurrence.
            rect: Redaction box (x0, y0, x1, y1) of *this* occurrence, if known.

        Every call records an occurrence, not just the first one: the same
        value may appear on several pages and reconstruction needs all of
        their coordinates.
        """
        clean_original = " ".join((original or "").split())
        clean_type = self.normalize_entity_type(entity_type)
        key = (clean_type, clean_original.casefold())
        page_index = max(0, int(page))

        placeholder = self._by_value.get(key)
        if placeholder is None:
            next_index = self._counters.get(clean_type, 0) + 1
            self._counters[clean_type] = next_index
            placeholder = f"{clean_type}_{next_index:03d}"
            self._by_value[key] = placeholder
            self._order.append(placeholder)
            self._meta[placeholder] = (clean_original, clean_type, page_index)
            self._occurrences[placeholder] = []

        if rect is not None:
            x0, y0, x1, y1 = (float(v) for v in tuple(rect)[:4])
            self._occurrences[placeholder].append(
                PlaceholderOccurrence(page=page_index, rect=(x0, y0, x1, y1))
            )
        return placeholder

    def entries(self) -> List[PlaceholderEntry]:
        entries: List[PlaceholderEntry] = []
        for placeholder in self._order:
            clean_original, clean_type, first_page = self._meta[placeholder]
            entries.append(
                PlaceholderEntry(
                    placeholder=placeholder,
                    original=clean_original,
                    entity_type=clean_type,
                    page=first_page,
                    occurrences=tuple(self._occurrences[placeholder]),
                )
            )
        return entries


RESTORE_MAP_FORMAT = "NullifyPDF restore map"
RESTORE_MAP_VERSION = 2
# Version 1 maps carry no `occurrences`; they are still readable, and
# reconstruction falls back to searching the PDF for the placeholder text.
# Refusing them would permanently strand the PII of every map already issued.
SUPPORTED_RESTORE_MAP_VERSIONS = frozenset({1, 2})


def build_restore_payload(
    *,
    source_name: str,
    source_sha256: str,
    output_sha256: Optional[str],
    entries: Iterable[PlaceholderEntry],
) -> Dict[str, object]:
    """Build the JSON-serializable restore-map payload."""

    raw_entries: List[Dict[str, object]] = []
    for entry in entries:
        raw = asdict(entry)
        # asdict() keeps tuples as tuples; JSON round-trips them to lists, so
        # normalize here and keep the payload byte-comparable with itself.
        raw["occurrences"] = [
            {"page": occurrence.page, "rect": list(occurrence.rect)}
            for occurrence in entry.occurrences
        ]
        raw_entries.append(raw)

    return {
        "format": RESTORE_MAP_FORMAT,
        "version": RESTORE_MAP_VERSION,
        "source_name": os.path.basename(source_name),
        "source_sha256": source_sha256,
        "output_sha256": output_sha256,
        "entries": raw_entries,
    }


def parse_restore_entries(payload: Dict[str, object]) -> List[PlaceholderEntry]:
    """Validate a decrypted restore-map payload and return its entries.

    Raises:
        ValueError: If the payload is not a recognized restore map.
    """
    if (
        not isinstance(payload, dict)
        or payload.get("format") != RESTORE_MAP_FORMAT
        or payload.get("version") not in SUPPORTED_RESTORE_MAP_VERSIONS
    ):
        raise ValueError("Formato mappa di ripristino non riconosciuto.")

    entries: List[PlaceholderEntry] = []
    raw_entries = payload.get("entries") or []
    assert isinstance(raw_entries, list)
    for raw in raw_entries:
        occurrences: List[PlaceholderOccurrence] = []
        for raw_occ in raw.get("occurrences") or []:
            coords = [float(v) for v in raw_occ["rect"]]
            if len(coords) != 4:
                raise ValueError("Mappa di ripristino: rettangolo non valido.")
            occurrences.append(
                PlaceholderOccurrence(
                    page=int(raw_occ["page"]),
                    rect=(coords[0], coords[1], coords[2], coords[3]),
                )
            )
        entries.append(
            PlaceholderEntry(
                placeholder=str(raw["placeholder"]),
                original=str(raw["original"]),
                entity_type=str(raw["entity_type"]),
                page=int(raw["page"]),
                occurrences=tuple(occurrences),
            )
        )
    return entries


def sort_entries_longest_placeholder_first(
    entries: Iterable[PlaceholderEntry],
) -> List[PlaceholderEntry]:
    """Sort restore entries with the longest placeholder text first.

    Longest-first ordering matters because placeholder search is a substring
    match: once a type exceeds 9 instances (``PERSON_0010``), a shorter
    placeholder like ``PERSON_001`` would otherwise match its first 10
    characters and restore the wrong value.

    Only relevant to the version 1 fallback path: version 2 maps carry each
    occurrence's coordinates, so reconstruction addresses boxes directly
    instead of matching placeholder text.
    """
    return sorted(entries, key=lambda e: len(e.placeholder), reverse=True)


def encrypt_restore_payload(payload: Dict[str, object], password: str) -> bytes:
    """Encrypt and authenticate a restore-map payload with a password."""

    if not password or len(password) < 12:
        raise ValueError("La password della mappa deve avere almeno 12 caratteri.")

    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
    token = Fernet(key).encrypt(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    )
    envelope = {
        "format": "NullifyPDF encrypted restore map",
        "version": 1,
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": 600000,
        "salt": base64.b64encode(salt).decode("ascii"),
        "token": token.decode("ascii"),
    }
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2).encode(
        "utf-8"
    )


def decrypt_restore_payload(data: bytes, password: str) -> Dict[str, object]:
    """Decrypt an encrypted restore map."""

    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    envelope = json.loads(data.decode("utf-8"))
    salt = base64.b64decode(envelope["salt"])
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=int(envelope["iterations"]),
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
    plaintext = Fernet(key).decrypt(envelope["token"].encode("ascii"))
    return json.loads(plaintext.decode("utf-8"))
