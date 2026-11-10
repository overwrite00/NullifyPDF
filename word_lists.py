"""Blocklist / allowlist persistence: encrypted at rest, optional expiry (Qt-free).

The lists can contain personal data (names the user always wants removed or
always wants kept), so they are stored sealed with the master key of
:mod:`secure_store` in ``blocklist.v2.enc`` / ``allowlist.v2.enc``. Each
entry carries the date it was added and an optional expiry date; expired
entries are dropped (and the file rewritten) when the list is loaded.

Compatibility: an existing plaintext ``blocklist.txt`` / ``allowlist.txt`` is
read, migrated transparently and then overwritten and removed. If encryption
is unavailable (no ``cryptography``, no usable protector) the plaintext files
keep working. If the keystore cannot be unwrapped (profile copied to another
account) nothing is deleted or overwritten and the lists are empty until the
keystore is restored.
"""

from __future__ import annotations

import datetime
import json
import logging
import pathlib
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set

import secure_store

MIN_TERM_LENGTH = 3
_MAGIC = b"NPDFL2\n"
_FORMAT = "NullifyPDF word list"
_log = logging.getLogger("nullifypdf")


@dataclass
class ListEntry:
    term: str
    added: datetime.date
    expires: Optional[datetime.date] = None

    def to_json(self) -> Dict[str, Optional[str]]:
        return {
            "term": self.term,
            "added": self.added.isoformat(),
            "expires": self.expires.isoformat() if self.expires else None,
        }


def _clean(term: str) -> str:
    return " ".join(term.strip().lower().split())


def _date(value: Optional[str]) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


class PDFListManager:
    """Loads and saves the blocklist and allowlist."""

    def __init__(
        self,
        config_dir: pathlib.Path,
        today: Callable[[], datetime.date] = datetime.date.today,
    ) -> None:
        self.config_dir = pathlib.Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.block_file = self.config_dir / "blocklist.txt"
        self.allow_file = self.config_dir / "allowlist.txt"
        self._today = today
        self.expired_removed = 0
        self.keystore_error: Optional[str] = None
        self.encrypted = True

    # ------------------------------------------------------------ paths
    def _enc_path(self, kind: str) -> pathlib.Path:
        return self.config_dir / f"{kind}.v2.enc"

    def _plain_path(self, kind: str) -> pathlib.Path:
        return self.block_file if kind == "blocklist" else self.allow_file

    # ------------------------------------------------------- settings
    def default_ttl_days(self) -> Optional[int]:
        try:
            data = json.loads((self.config_dir / "settings.json").read_text(encoding="utf-8"))
            ttl = data.get("list_ttl_days")
            return int(ttl) if ttl else None
        except Exception:
            return None

    def set_default_ttl_days(self, days: Optional[int]) -> None:
        path = self.config_dir / "settings.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        data["list_ttl_days"] = days
        secure_store.atomic_write(path, json.dumps(data).encode("utf-8"))

    def protector_label(self) -> str:
        if not self.encrypted:
            return "Non cifrato"
        return secure_store.protector_label(self.config_dir)

    # ------------------------------------------------------- entries
    def load_entries(self, kind: str) -> List[ListEntry]:
        enc, plain = self._enc_path(kind), self._plain_path(kind)
        if enc.exists():
            entries = self._read_encrypted(kind, enc)
            kept = [e for e in entries if not (e.expires and e.expires < self._today())]
            if len(kept) != len(entries):
                self.expired_removed += len(entries) - len(kept)
                self._write_encrypted(kind, kept)
            return kept
        if plain.exists():
            entries = self._read_plain(plain)
            if self._can_encrypt():
                try:
                    self._write_encrypted(kind, entries)
                    secure_store.secure_delete(plain)
                except Exception as e:  # keep the readable file on any failure
                    _log.error(f"List migration failed: {e}")
                    self.encrypted = False
            else:
                self.encrypted = False
            return entries
        return []

    def save_entries(self, kind: str, entries: List[ListEntry]) -> None:
        clean: Dict[str, ListEntry] = {}
        for e in entries:
            term = _clean(e.term)
            if len(term) >= MIN_TERM_LENGTH:
                clean[term] = ListEntry(term, e.added, e.expires)
        final = sorted(clean.values(), key=lambda e: e.term)
        if self._can_encrypt():
            try:
                self._write_encrypted(kind, final)
                plain = self._plain_path(kind)
                if plain.exists():
                    secure_store.secure_delete(plain)
                return
            except secure_store.KeystoreUnavailable as e:
                self.keystore_error = str(e)
                raise
            except Exception as e:
                _log.error(f"Encrypted list save failed: {e}")
        self.encrypted = False
        try:
            secure_store.atomic_write(
                self._plain_path(kind), "\n".join(e.term for e in final).encode("utf-8")
            )
        except OSError as e:
            _log.error(f"Error saving {kind}: {e}")

    # -------------------------------------------- set-based convenience
    def load_blocklist(self) -> Set[str]:
        return self._terms("blocklist")

    def load_allowlist(self) -> Set[str]:
        return self._terms("allowlist")

    def save_blocklist(self, blocklist: Set[str]) -> None:
        self._save_terms("blocklist", blocklist)

    def save_allowlist(self, allowlist: Set[str]) -> None:
        self._save_terms("allowlist", allowlist)

    def _terms(self, kind: str) -> Set[str]:
        try:
            return {e.term for e in self.load_entries(kind)}
        except secure_store.KeystoreUnavailable as e:
            self.keystore_error = str(e)
            _log.error("Word lists unreadable: %s", e)
            return set()
        except Exception as e:
            _log.error(f"Error loading {kind}: {e}")
            return set()

    def _save_terms(self, kind: str, words: Set[str]) -> None:
        """Save a set of terms, keeping dates of the ones already present."""
        try:
            existing = {e.term: e for e in self.load_entries(kind)}
        except secure_store.KeystoreUnavailable:
            existing = {}
        except Exception as e:  # corrupt / tampered file: start from the new set
            _log.error(f"Unreadable {kind} file ignored: {e}")
            existing = {}
        ttl = self.default_ttl_days()
        today = self._today()
        entries: List[ListEntry] = []
        for w in words:
            term = _clean(w)
            if len(term) < MIN_TERM_LENGTH:
                continue
            old = existing.get(term)
            if old:
                entries.append(old)
            else:
                exp = today + datetime.timedelta(days=ttl) if ttl else None
                entries.append(ListEntry(term, today, exp))
        try:
            self.save_entries(kind, entries)
        except secure_store.KeystoreUnavailable:
            pass  # error kept in self.keystore_error; nothing is overwritten

    # ------------------------------------------------------ plumbing
    def _can_encrypt(self) -> bool:
        try:
            import cryptography  # noqa: F401

            secure_store.load_or_create_master_key(self.config_dir)
            return True
        except secure_store.KeystoreUnavailable as e:
            self.keystore_error = str(e)
            raise
        except Exception:
            return False

    def _read_plain(self, path: pathlib.Path) -> List[ListEntry]:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                terms = {_clean(line) for line in fh if len(line.strip()) >= MIN_TERM_LENGTH}
        except Exception as e:
            _log.error(f"Error loading {path}: {e}")
            return []
        today = self._today()
        return [ListEntry(t, today, None) for t in sorted(terms) if len(t) >= MIN_TERM_LENGTH]

    def _read_encrypted(self, kind: str, path: pathlib.Path) -> List[ListEntry]:
        key = secure_store.load_or_create_master_key(self.config_dir)
        raw = path.read_bytes()
        if not raw.startswith(_MAGIC):
            raise ValueError("Formato del dizionario non riconosciuto.")
        data = json.loads(
            secure_store.open_sealed(raw[len(_MAGIC):], key, b"nullifypdf-list:" + kind.encode())
        )
        out = []
        for item in data.get("entries", []):
            term = _clean(str(item.get("term", "")))
            if len(term) < MIN_TERM_LENGTH:
                continue
            out.append(ListEntry(
                term, _date(item.get("added")) or self._today(), _date(item.get("expires"))
            ))
        return out

    def _write_encrypted(self, kind: str, entries: List[ListEntry]) -> None:
        key = secure_store.load_or_create_master_key(self.config_dir)
        payload = json.dumps({
            "format": _FORMAT, "version": 2, "entries": [e.to_json() for e in entries],
        }, ensure_ascii=False).encode("utf-8")
        sealed = secure_store.seal(payload, key, b"nullifypdf-list:" + kind.encode())
        secure_store.atomic_write(self._enc_path(kind), _MAGIC + sealed)
