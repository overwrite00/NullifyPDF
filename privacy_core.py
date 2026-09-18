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
from typing import Dict, Iterable, List, Optional


class PrivacyMode(str, Enum):
    """Supported privacy export modes."""

    ANONYMIZE = "anonymize"
    PSEUDONYMIZE = "pseudonymize"


@dataclass(frozen=True)
class PlaceholderEntry:
    """One reversible placeholder mapping entry."""

    placeholder: str
    original: str
    entity_type: str
    page: int


class PlaceholderRegistry:
    """Create stable placeholders for detected personal data."""

    def __init__(self) -> None:
        self._counters: Dict[str, int] = {}
        self._by_value: Dict[tuple[str, str], str] = {}
        self._entries: List[PlaceholderEntry] = []

    @staticmethod
    def normalize_entity_type(entity_type: Optional[str]) -> str:
        value = (entity_type or "DATA").upper()
        value = re.sub(r"[^A-Z0-9_]+", "_", value).strip("_")
        return value or "DATA"

    def placeholder_for(
        self, original: str, entity_type: Optional[str] = None, page: int = 0
    ) -> str:
        clean_original = " ".join((original or "").split())
        clean_type = self.normalize_entity_type(entity_type)
        key = (clean_type, clean_original.casefold())
        if key in self._by_value:
            return self._by_value[key]

        next_index = self._counters.get(clean_type, 0) + 1
        self._counters[clean_type] = next_index
        placeholder = f"{clean_type}_{next_index:03d}"
        self._by_value[key] = placeholder
        self._entries.append(
            PlaceholderEntry(
                placeholder=placeholder,
                original=clean_original,
                entity_type=clean_type,
                page=max(0, int(page)),
            )
        )
        return placeholder

    def entries(self) -> List[PlaceholderEntry]:
        return list(self._entries)


RESTORE_MAP_FORMAT = "NullifyPDF restore map"
RESTORE_MAP_VERSION = 1


def build_restore_payload(
    *,
    source_name: str,
    source_sha256: str,
    output_sha256: Optional[str],
    entries: Iterable[PlaceholderEntry],
) -> Dict[str, object]:
    """Build the JSON-serializable restore-map payload."""

    return {
        "format": RESTORE_MAP_FORMAT,
        "version": RESTORE_MAP_VERSION,
        "source_name": os.path.basename(source_name),
        "source_sha256": source_sha256,
        "output_sha256": output_sha256,
        "entries": [asdict(entry) for entry in entries],
    }


def parse_restore_entries(payload: Dict[str, object]) -> List[PlaceholderEntry]:
    """Validate a decrypted restore-map payload and return its entries.

    Raises:
        ValueError: If the payload is not a recognized restore map.
    """
    if (
        not isinstance(payload, dict)
        or payload.get("format") != RESTORE_MAP_FORMAT
        or payload.get("version") != RESTORE_MAP_VERSION
    ):
        raise ValueError("Formato mappa di ripristino non riconosciuto.")

    entries: List[PlaceholderEntry] = []
    raw_entries = payload.get("entries") or []
    assert isinstance(raw_entries, list)
    for raw in raw_entries:
        entries.append(
            PlaceholderEntry(
                placeholder=str(raw["placeholder"]),
                original=str(raw["original"]),
                entity_type=str(raw["entity_type"]),
                page=int(raw["page"]),
            )
        )
    return entries


def group_entries_by_page(
    entries: Iterable[PlaceholderEntry],
) -> Dict[int, List[PlaceholderEntry]]:
    """Group restore entries by page, longest placeholder first on each page.

    Longest-first ordering matters because placeholder search is a substring
    match: once a type exceeds 9 instances (``PERSON_0010``), a shorter
    placeholder like ``PERSON_001`` would otherwise match its first 10
    characters and restore the wrong value.
    """
    by_page: Dict[int, List[PlaceholderEntry]] = {}
    for entry in entries:
        by_page.setdefault(entry.page, []).append(entry)
    for page_entries in by_page.values():
        page_entries.sort(key=lambda e: len(e.placeholder), reverse=True)
    return by_page


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
