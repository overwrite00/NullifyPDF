"""Privacy primitives for NullifyPDF export workflows.

This module is deliberately independent from PySide / PyMuPDF so that the
security-sensitive policy and restore-map logic can be tested without a GUI.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


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
    # Typography of the original text under this box (native PDFs only):
    # {font, size, color, flags, origin, text}. None for scanned pages and
    # for maps written before version 3.
    style: Optional[Dict[str, Any]] = None
    # What was actually drawn when the full placeholder did not fit the box
    # (a compact form such as "P9F2A"). None when the full placeholder was
    # drawn. Restore uses the rectangle, never this text.
    label: Optional[str] = None


def validate_style(raw: Any) -> Dict[str, Any]:
    """Check a stored text style and return a normalized copy."""
    if not isinstance(raw, dict):
        raise ValueError("Mappa di ripristino: stile non valido.")
    origin = [float(v) for v in raw["origin"]]
    if len(origin) != 2:
        raise ValueError("Mappa di ripristino: stile non valido.")
    return {
        "font": str(raw.get("font", "")),
        "size": float(raw["size"]),
        "color": int(raw.get("color", 0)),
        "flags": int(raw.get("flags", 0)),
        "origin": origin,
        "text": str(raw.get("text", "")),
    }


@dataclass(frozen=True)
class PlaceholderEntry:
    """One reversible placeholder mapping entry."""

    placeholder: str
    original: str
    entity_type: str
    page: int
    occurrences: Tuple[PlaceholderOccurrence, ...] = ()


PSEUDONYM_STYLES = ("random", "counter", "opaque", "keyed")


class PlaceholderRegistry:
    """Create stable placeholders for detected personal data.

    Styles (``style``):
      - ``counter``: ``PERSON_001``, in first-seen order. The suffix reveals
        how many distinct values of a type exist and in which order they
        appear.
      - ``random``: ``PERSON_9F2A``, unpredictable, drawn from ``secrets``
        for each document; nothing about the order or count leaks.
      - ``opaque``: ``DATA_9F2A``; additionally hides the entity type.
      - ``keyed``: ``PERSON_3B7E10`` = HMAC(key, type || value); the same
        value gets the same pseudonym in every document made with the same
        key. Cross-document linking is intended; the key must be kept
        separately and protected (EDPB Guidelines 01/2025).
    """

    def __init__(self, style: str = "counter", key: Optional[bytes] = None) -> None:
        if style not in PSEUDONYM_STYLES:
            raise ValueError(f"Stile pseudonimi sconosciuto: {style}")
        if style == "keyed" and not key:
            raise ValueError("Lo stile 'keyed' richiede una chiave.")
        self._style = style
        self._key = key
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
        style: Optional[Dict[str, Any]] = None,
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
            placeholder = self._make_placeholder(
                clean_type, clean_original, next_index
            )
            self._by_value[key] = placeholder
            self._order.append(placeholder)
            self._meta[placeholder] = (clean_original, clean_type, page_index)
            self._occurrences[placeholder] = []

        if rect is not None:
            x0, y0, x1, y1 = (float(v) for v in tuple(rect)[:4])
            self._occurrences[placeholder].append(
                PlaceholderOccurrence(
                    page=page_index, rect=(x0, y0, x1, y1), style=style
                )
            )
        return placeholder

    def set_label(self, placeholder: str, rect: Sequence[float], label: str) -> None:
        """Record the compact label drawn for the occurrence at `rect`."""
        target = tuple(float(v) for v in tuple(rect)[:4])
        occs = self._occurrences.get(placeholder, [])
        for i, occ in enumerate(occs):
            if occ.rect == target:
                occs[i] = PlaceholderOccurrence(
                    page=occ.page, rect=occ.rect, style=occ.style, label=label
                )
                return

    def _make_placeholder(self, clean_type: str, original: str, n: int) -> str:
        if self._style == "counter":
            return f"{clean_type}_{n:03d}"
        prefix = "DATA" if self._style == "opaque" else clean_type
        taken = set(self._by_value.values())
        if self._style == "keyed":
            assert self._key is not None
            digest = hmac.new(
                self._key,
                (clean_type + "\x00" + original.casefold()).encode("utf-8"),
                hashlib.sha256,
            ).hexdigest().upper()
            for width in range(6, len(digest) + 1, 2):
                candidate = f"{prefix}_{digest[:width]}"
                if candidate not in taken:
                    return candidate
            return f"{prefix}_{digest}"
        # Four hex digits keep the placeholder short enough to fit the box
        # of a short word; widen only if collisions pile up.
        nbytes, tries = 2, 0
        while True:
            candidate = f"{prefix}_{secrets.token_hex(nbytes).upper()}"
            if candidate not in taken:
                return candidate
            tries += 1
            if tries % 8 == 0:
                nbytes += 1

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
RESTORE_MAP_VERSION = 4
# Version 1 maps carry no `occurrences`; they are still readable, and
# reconstruction falls back to searching the PDF for the placeholder text.
# Refusing them would permanently strand the PII of every map already issued.
# Version 3 adds an optional per-occurrence `style`; 2 maps stay readable.
# Version 4 adds an optional per-occurrence `label` (compact placeholder drawn
# when the full one did not fit); older maps stay readable.
SUPPORTED_RESTORE_MAP_VERSIONS = frozenset({1, 2, 3, 4})


def build_restore_payload(
    *,
    source_name: str,
    source_sha256: str,
    output_sha256: Optional[str],
    entries: Iterable[PlaceholderEntry],
    keep_source_name: bool = False,
) -> Dict[str, object]:
    """Build the JSON-serializable restore-map payload.

    The map is itself personal data, so it stores as little as possible: the
    source file name is omitted unless asked for (it often holds the data
    subject's name), and a style's ``text`` is dropped when it only repeats
    the original value already stored in the entry.
    """

    raw_entries: List[Dict[str, object]] = []
    for entry in entries:
        raw = asdict(entry)
        # asdict() keeps tuples as tuples; JSON round-trips them to lists, so
        # normalize here and keep the payload byte-comparable with itself.
        def slim(
            style: Optional[Dict[str, Any]], original: str = entry.original
        ) -> Optional[Dict[str, Any]]:
            if not style:
                return None
            out = dict(style)
            if " ".join(str(out.get("text", "")).split()) == " ".join(
                original.split()
            ):
                out.pop("text", None)
            return out

        raw["occurrences"] = [
            {
                "page": occurrence.page,
                "rect": list(occurrence.rect),
                **({"style": slim(occurrence.style)} if occurrence.style else {}),
                **(
                    {"label": occurrence.label}
                    if occurrence.label and occurrence.label != entry.placeholder
                    else {}
                ),
            }
            for occurrence in entry.occurrences
        ]
        raw_entries.append(raw)

    return {
        "format": RESTORE_MAP_FORMAT,
        "version": RESTORE_MAP_VERSION,
        "source_name": os.path.basename(source_name) if keep_source_name else "",
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
                    style=(
                        validate_style(raw_occ["style"])
                        if raw_occ.get("style")
                        else None
                    ),
                    label=(str(raw_occ["label"]) if raw_occ.get("label") else None),
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


MIN_PASSWORD_LENGTH = 12
PBKDF2_MIN_ITERATIONS = 100_000
PBKDF2_MAX_ITERATIONS = 5_000_000
SCRYPT_N = 2 ** 17
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAX_N = 2 ** 20

_COMMON_PASSWORDS = (
    "passwordpassword", "123456789012", "qwertyuiopas", "password1234",
    "administrator", "letmein123456",
)


def password_strength(password: str) -> Tuple[bool, str]:
    """Reject passwords that make the map trivial to open.

    Returns (acceptable, message). Length alone is not enough: a repeated
    character or a common phrase of 12 characters falls in seconds.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, "La password deve avere almeno 12 caratteri."
    if len(set(password)) < 6:
        return False, "La password usa troppi caratteri ripetuti."
    low = password.lower()
    if any(c in low for c in _COMMON_PASSWORDS):
        return False, "La password e troppo comune."
    classes = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if classes < 2 and len(password) < 20:
        return False, (
            "Usa almeno due tipi di caratteri (minuscole, maiuscole, cifre, "
            "simboli) oppure una frase di almeno 20 caratteri."
        )
    return True, ""


def _derive_key(password: str, envelope: Dict[str, Any], salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    kdf_name = str(envelope.get("kdf", "PBKDF2-HMAC-SHA256"))
    if kdf_name == "scrypt":
        n = int(envelope["n"])
        r = int(envelope.get("r", SCRYPT_R))
        p_ = int(envelope.get("p", SCRYPT_P))
        # Parameters come from an untrusted file: bound them before use so a
        # crafted map cannot exhaust memory or CPU.
        if (
            not (2 ** 14 <= n <= SCRYPT_MAX_N) or n & (n - 1)
            or not (1 <= r <= 16) or not (1 <= p_ <= 4)
        ):
            raise ValueError("Parametri KDF della mappa fuori dai limiti consentiti.")
        kdf: Any = Scrypt(salt=salt, length=32, n=n, r=r, p=p_)
    elif kdf_name == "PBKDF2-HMAC-SHA256":
        iterations = int(envelope["iterations"])
        if not (PBKDF2_MIN_ITERATIONS <= iterations <= PBKDF2_MAX_ITERATIONS):
            raise ValueError(
                "Numero di iterazioni della mappa fuori dai limiti consentiti."
            )
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations
        )
    else:
        raise ValueError("Algoritmo KDF della mappa non supportato.")
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def _encrypt_v2(payload: Dict[str, object], password: str) -> bytes:
    """Version 2 envelope (scrypt + Fernet). Kept for compatibility tests;
    new maps use :func:`encrypt_restore_payload` (version 3)."""

    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("La password della mappa deve avere almeno 12 caratteri.")

    from cryptography.fernet import Fernet

    salt = os.urandom(16)
    envelope: Dict[str, Any] = {
        "format": "NullifyPDF encrypted restore map",
        "version": 2,
        "kdf": "scrypt",
        "n": SCRYPT_N,
        "r": SCRYPT_R,
        "p": SCRYPT_P,
        "salt": base64.b64encode(salt).decode("ascii"),
    }
    key = _derive_key(password, envelope, salt)
    token = Fernet(key).encrypt(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    )
    envelope["token"] = token.decode("ascii")
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2).encode(
        "utf-8"
    )


def _decrypt_v1v2(envelope: Dict[str, Any], password: str) -> Dict[str, object]:
    """Decrypt a version 1 (PBKDF2) or 2 (scrypt) envelope."""

    from cryptography.fernet import Fernet

    salt = base64.b64decode(envelope["salt"])
    key = _derive_key(password, envelope, salt)
    plaintext = Fernet(key).decrypt(envelope["token"].encode("ascii"))
    return json.loads(plaintext.decode("utf-8"))


# ---------------------------------------------------------------------------
# Envelope version 3: data key + key wrapping (password, optional recovery key)
# ---------------------------------------------------------------------------

MAP_FORMAT = "NullifyPDF encrypted restore map"
KEY_EXPORT_FORMAT = "NullifyPDF pseudonym key"
ARGON2_T = 3
ARGON2_M_KIB = 64 * 1024
ARGON2_P = 4
_PAYLOAD_AAD = b"NullifyPDF envelope v3 payload"
_RECOVERY_PREFIX = "NPDF"
_B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _unb64(s_: str) -> bytes:
    return base64.b64decode(s_.encode("ascii"))


def _argon2_available() -> bool:
    try:
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id  # noqa: F401

        return True
    except Exception:
        return False


def _password_kek(password: str, wrap: Dict[str, Any]) -> bytes:
    """Derive the key-encryption key for a password wrap (bounds-checked)."""
    salt = _unb64(wrap["salt"])
    if len(salt) < 16:
        raise ValueError("Parametri KDF della mappa fuori dai limiti consentiti.")
    kdf = str(wrap.get("kdf"))
    if kdf == "argon2id":
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

        t, m, p_ = int(wrap["t"]), int(wrap["m"]), int(wrap["p"])
        if not (1 <= t <= 10 and 19 * 1024 <= m <= 1024 * 1024 and 1 <= p_ <= 8 and m >= 8 * p_):
            raise ValueError("Parametri KDF della mappa fuori dai limiti consentiti.")
        return Argon2id(
            salt=salt, length=32, iterations=t, lanes=p_, memory_cost=m
        ).derive(password.encode("utf-8"))
    if kdf == "scrypt":
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

        n, r, p_ = int(wrap["n"]), int(wrap["r"]), int(wrap["p"])
        if (
            not (2 ** 14 <= n <= SCRYPT_MAX_N) or n & (n - 1)
            or not (1 <= r <= 16) or not (1 <= p_ <= 4)
        ):
            raise ValueError("Parametri KDF della mappa fuori dai limiti consentiti.")
        return Scrypt(salt=salt, length=32, n=n, r=r, p=p_).derive(password.encode("utf-8"))
    raise ValueError("Algoritmo KDF della mappa non supportato.")


def _new_password_wrap(password: str, dek: bytes) -> Dict[str, Any]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = os.urandom(16)
    wrap: Dict[str, Any] = {"type": "password", "salt": _b64(salt)}
    if _argon2_available():
        wrap.update(kdf="argon2id", t=ARGON2_T, m=ARGON2_M_KIB, p=ARGON2_P)
        try:
            kek = _password_kek(password, wrap)
        except Exception:  # OpenSSL without Argon2: fall back for writing only
            wrap = {"type": "password", "salt": _b64(salt)}
            wrap.update(kdf="scrypt", n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
            kek = _password_kek(password, wrap)
    else:
        wrap.update(kdf="scrypt", n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
        kek = _password_kek(password, wrap)
    nonce = os.urandom(12)
    wrap["nonce"] = _b64(nonce)
    wrap["wrapped"] = _b64(AESGCM(kek).encrypt(nonce, dek, b"NullifyPDF wrap v3:password"))
    return wrap


def _recovery_kek(recovery_key: bytes, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=salt, info=b"nullifypdf-recovery"
    ).derive(recovery_key)


def _new_recovery_wrap(recovery_key: bytes, dek: bytes) -> Dict[str, Any]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(recovery_key) != 32:
        raise ValueError("Chiave di recupero non valida.")
    salt, nonce = os.urandom(16), os.urandom(12)
    kek = _recovery_kek(recovery_key, salt)
    return {
        "type": "recovery", "kdf": "hkdf-sha256", "salt": _b64(salt),
        "nonce": _b64(nonce),
        "wrapped": _b64(AESGCM(kek).encrypt(nonce, dek, b"NullifyPDF wrap v3:recovery")),
        "key_id": hashlib.sha256(recovery_key).hexdigest()[:8],
    }


def generate_recovery_key() -> Tuple[bytes, str]:
    """A fresh 256-bit recovery key and its display form (shown once).

    Display: ``NPDF-XXXX-...`` in base32 groups of four with a 2-character
    checksum, so typing mistakes are caught before any decryption.
    """
    raw = os.urandom(32)
    return raw, format_recovery_key(raw)


def _checksum(raw: bytes) -> str:
    v = int.from_bytes(hashlib.sha256(raw).digest()[:2], "big") & 0x3FF
    return _B32[v >> 5] + _B32[v & 31]


def format_recovery_key(raw: bytes) -> str:
    body = base64.b32encode(raw).decode("ascii").rstrip("=") + _checksum(raw)
    groups = [body[i:i + 4] for i in range(0, len(body), 4)]
    return _RECOVERY_PREFIX + "-" + "-".join(groups)


def parse_recovery_key(display: str) -> bytes:
    """Parse a displayed recovery key; raises ValueError on any typo."""
    text = "".join(display.upper().split()).replace("-", "")
    if text.startswith(_RECOVERY_PREFIX):
        text = text[len(_RECOVERY_PREFIX):]
    text = text.replace("0", "O").replace("1", "I")
    if len(text) != 54 or any(c not in _B32 for c in text):
        raise ValueError("Chiave di recupero non valida.")
    body, check = text[:52], text[52:]
    try:
        raw = base64.b32decode(body + "====")
    except Exception as e:
        raise ValueError("Chiave di recupero non valida.") from e
    if len(raw) != 32 or _checksum(raw) != check:
        raise ValueError("Chiave di recupero non valida: controlla di averla digitata bene.")
    return raw


def _encrypt_v3(
    payload: Dict[str, object], password: str, recovery_key: Optional[bytes], fmt: str
) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    dek = os.urandom(32)
    nonce = os.urandom(12)
    ciphertext = AESGCM(dek).encrypt(
        nonce,
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        _PAYLOAD_AAD,
    )
    wraps = [_new_password_wrap(password, dek)]
    if recovery_key is not None:
        wraps.append(_new_recovery_wrap(recovery_key, dek))
    envelope = {
        "format": fmt, "version": 3, "cipher": "AES-256-GCM",
        "nonce": _b64(nonce), "ciphertext": _b64(ciphertext), "wraps": wraps,
    }
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def _decrypt_v3(
    envelope: Dict[str, Any], password: Optional[str], recovery_key: Optional[bytes]
) -> Dict[str, object]:
    from cryptography.exceptions import InvalidTag
    from cryptography.fernet import InvalidToken
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    dek: Optional[bytes] = None
    for wrap in envelope.get("wraps", []):
        try:
            if wrap.get("type") == "password" and password is not None:
                kek = _password_kek(password, wrap)
                aad = b"NullifyPDF wrap v3:password"
            elif wrap.get("type") == "recovery" and recovery_key is not None:
                kek = _recovery_kek(recovery_key, _unb64(wrap["salt"]))
                aad = b"NullifyPDF wrap v3:recovery"
            else:
                continue
            dek = AESGCM(kek).decrypt(_unb64(wrap["nonce"]), _unb64(wrap["wrapped"]), aad)
            break
        except InvalidTag:
            continue
    if dek is None:
        raise InvalidToken()  # same signal the callers already handle
    try:
        plaintext = AESGCM(dek).decrypt(
            _unb64(envelope["nonce"]), _unb64(envelope["ciphertext"]), _PAYLOAD_AAD
        )
    except InvalidTag as e:
        raise InvalidToken() from e
    return json.loads(plaintext.decode("utf-8"))


def encrypt_restore_payload(
    payload: Dict[str, object],
    password: str,
    *,
    recovery_key: Optional[bytes] = None,
) -> bytes:
    """Encrypt a restore-map payload (envelope version 3).

    A random data key encrypts the payload (AES-256-GCM); it is wrapped by a
    key derived from the password (Argon2id, scrypt if unavailable) and, if
    given, by the recovery key. Maps from older versions remain readable.
    """
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("La password della mappa deve avere almeno 12 caratteri.")
    return _encrypt_v3(payload, password, recovery_key, MAP_FORMAT)


def decrypt_restore_payload(
    data: bytes,
    password: Optional[str] = None,
    *,
    recovery_key: Optional[bytes] = None,
) -> Dict[str, object]:
    """Decrypt an encrypted restore map (versions 1, 2 and 3)."""
    envelope = json.loads(data.decode("utf-8"))
    if not isinstance(envelope, dict) or envelope.get("format") != MAP_FORMAT:
        raise ValueError("File non riconosciuto come mappa di ripristino cifrata.")
    version = envelope.get("version")
    if version in (1, 2):
        if password is None:
            raise ValueError("Questa mappa si apre solo con la password.")
        return _decrypt_v1v2(envelope, password)
    if version == 3:
        return _decrypt_v3(envelope, password, recovery_key)
    raise ValueError("Versione della mappa non supportata: aggiorna NullifyPDF.")


def export_pseudonym_key(key: bytes, password: str) -> bytes:
    """Password-protected copy of the pseudonym key, for another computer."""
    if len(key) != 32:
        raise ValueError("Chiave dei segnaposto non valida.")
    return _encrypt_v3({"key": _b64(key)}, password, None, KEY_EXPORT_FORMAT)


def import_pseudonym_key(data: bytes, password: str) -> bytes:
    envelope = json.loads(data.decode("utf-8"))
    if not isinstance(envelope, dict) or envelope.get("format") != KEY_EXPORT_FORMAT:
        raise ValueError("File non riconosciuto come chiave dei segnaposto.")
    if envelope.get("version") != 3:
        raise ValueError("Versione della chiave non supportata: aggiorna NullifyPDF.")
    key = _unb64(str(_decrypt_v3(envelope, password, None)["key"]))
    if len(key) != 32:
        raise ValueError("Chiave dei segnaposto non valida.")
    return key
