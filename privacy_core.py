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


def build_restore_payload(
    *,
    source_name: str,
    source_sha256: str,
    output_sha256: Optional[str],
    entries: Iterable[PlaceholderEntry],
) -> Dict[str, object]:
    """Build the JSON-serializable restore-map payload."""

    return {
        "format": "NullifyPDF restore map",
        "version": 1,
        "source_name": os.path.basename(source_name),
        "source_sha256": source_sha256,
        "output_sha256": output_sha256,
        "entries": [asdict(entry) for entry in entries],
    }


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
