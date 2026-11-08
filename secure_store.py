"""Protection of local secrets (Qt-free).

A single random master key protects the word lists and the pseudonym key.
The master key itself is kept by the best protector available:

* Windows: DPAPI (``CryptProtectData``, via ctypes - no extra dependency);
  bound to the Windows account.
* macOS / Linux: the OS keyring when the optional ``keyring`` package is
  installed and a real backend is active.
* Otherwise a key file (``keys/master.key``, mode 0600 where supported),
  which only protects against copying a single data file on its own, not
  against someone who can read the user's profile.

Data is sealed with AES-256-GCM. If the stored master key cannot be
recovered (profile moved to another account or machine) nothing is deleted or
overwritten: :class:`KeystoreUnavailable` is raised and callers degrade to
"no data" while leaving the encrypted files untouched.
"""

from __future__ import annotations

import base64
import json
import os
import pathlib
import stat
import sys
from typing import Any, Dict, Optional, Protocol

KEYSTORE_FORMAT = "NullifyPDF keystore"
_DPAPI_ENTROPY = b"NullifyPDF/secure_store/v1"


class KeystoreUnavailable(RuntimeError):
    """The master key cannot be recovered on this account / machine."""


class SealError(ValueError):
    """Sealed data is corrupt, tampered with, or for another context."""


# ----------------------------------------------------------------- sealing

def seal(plaintext: bytes, key: bytes, aad: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def open_sealed(blob: bytes, key: bytes, aad: bytes) -> bytes:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(blob) < 12 + 16:
        raise SealError("Dati cifrati troncati.")
    try:
        return AESGCM(key).decrypt(blob[:12], blob[12:], aad)
    except InvalidTag as e:
        raise SealError("Dati cifrati non validi o modificati.") from e


# -------------------------------------------------------------- protectors

class KeyProtector(Protocol):
    name: str

    def wrap(self, key: bytes) -> Dict[str, Any]: ...

    def unwrap(self, blob: Dict[str, Any]) -> bytes: ...


class DpapiProtector:
    name = "dpapi"

    @staticmethod
    def available() -> bool:
        return sys.platform == "win32"

    def _call(self, data: bytes, protect: bool) -> bytes:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        def blob_of(b: bytes) -> "tuple[DATA_BLOB, Any]":
            buf = ctypes.create_string_buffer(b, len(b))
            return DATA_BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        in_blob, keep1 = blob_of(data)
        ent_blob, keep2 = blob_of(_DPAPI_ENTROPY)
        out_blob = DATA_BLOB()
        CRYPTPROTECT_UI_FORBIDDEN = 0x1
        if protect:
            ok = crypt32.CryptProtectData(
                ctypes.byref(in_blob), "NullifyPDF", ctypes.byref(ent_blob),
                None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob),
            )
        else:
            ok = crypt32.CryptUnprotectData(
                ctypes.byref(in_blob), None, ctypes.byref(ent_blob),
                None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob),
            )
        del keep1, keep2
        if not ok:
            raise OSError(ctypes.WinError())  # type: ignore[attr-defined]
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)

    def wrap(self, key: bytes) -> Dict[str, Any]:
        return {
            "protector": self.name,
            "blob": base64.b64encode(self._call(key, True)).decode("ascii"),
        }

    def unwrap(self, blob: Dict[str, Any]) -> bytes:
        return self._call(base64.b64decode(blob["blob"]), False)


class KeyringProtector:
    name = "keyring"
    SERVICE = "NullifyPDF"
    USER = "master"

    @staticmethod
    def available() -> bool:
        try:
            import keyring  # type: ignore[import-not-found]
            from keyring.backends import fail, null  # type: ignore[import-not-found]

            backend = keyring.get_keyring()
            return not isinstance(backend, (fail.Keyring, null.Keyring))
        except Exception:
            return False

    def wrap(self, key: bytes) -> Dict[str, Any]:
        import keyring  # type: ignore[import-not-found]

        keyring.set_password(self.SERVICE, self.USER, base64.b64encode(key).decode("ascii"))
        return {"protector": self.name, "service": self.SERVICE, "user": self.USER}

    def unwrap(self, blob: Dict[str, Any]) -> bytes:
        import keyring  # type: ignore[import-not-found]

        secret = keyring.get_password(blob.get("service", self.SERVICE), blob.get("user", self.USER))
        if not secret:
            raise OSError("Segreto non presente nel portachiavi.")
        return base64.b64decode(secret)


class KeyFileProtector:
    name = "keyfile"

    def __init__(self, config_dir: pathlib.Path) -> None:
        self.path = pathlib.Path(config_dir) / "keys" / "master.key"

    def wrap(self, key: bytes) -> Dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
        fd = os.open(str(self.path), flags, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(key)
        try:
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        return {"protector": self.name, "path": "keys/master.key"}

    def unwrap(self, blob: Dict[str, Any]) -> bytes:
        return self.path.read_bytes()


# ---------------------------------------------------------------- keystore

def _keystore_path(config_dir: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(config_dir) / "keystore.json"


def _protectors(config_dir: pathlib.Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {"keyfile": KeyFileProtector(config_dir)}
    if DpapiProtector.available():
        out["dpapi"] = DpapiProtector()
    if KeyringProtector.available():
        out["keyring"] = KeyringProtector()
    return out


_CACHE: Dict[str, bytes] = {}


def forget_cached_keys() -> None:
    _CACHE.clear()


def protector_label(config_dir: pathlib.Path) -> str:
    """Human-readable (Italian) description of how the master key is kept."""
    try:
        data = json.loads(_keystore_path(config_dir).read_text(encoding="utf-8"))
        name = data["master"]["protector"]
    except Exception:
        name = None
    return {
        "dpapi": "Archivio protetto: Windows DPAPI",
        "keyring": "Archivio protetto: portachiavi di sistema",
        "keyfile": "File chiave locale (protezione limitata)",
    }.get(name or "", "Non ancora creato")


def load_or_create_master_key(config_dir: pathlib.Path) -> bytes:
    """Return the 32-byte master key, creating the keystore on first use.

    Raises :class:`KeystoreUnavailable` when a keystore exists but cannot be
    unwrapped on this account. Never overwrites an existing keystore.
    """
    cfg = pathlib.Path(config_dir)
    cache_key = str(cfg.resolve())
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    ks = _keystore_path(cfg)
    protectors = _protectors(cfg)
    if ks.exists():
        try:
            data = json.loads(ks.read_text(encoding="utf-8"))
            master = data["master"]
            prot = protectors.get(master["protector"])
            if prot is None:
                raise KeystoreUnavailable(
                    f"Protezione '{master['protector']}' non disponibile su questo sistema."
                )
            key = prot.unwrap(master)
        except KeystoreUnavailable:
            raise
        except Exception as e:
            raise KeystoreUnavailable(
                "Chiave dei dati locali non leggibile su questo account/PC."
            ) from e
        if len(key) != 32:
            raise KeystoreUnavailable("Chiave dei dati locali non valida.")
        _CACHE[cache_key] = key
        return key
    key = os.urandom(32)
    errors = []
    for name in ("dpapi", "keyring", "keyfile"):
        prot = protectors.get(name)
        if prot is None:
            continue
        try:
            master = prot.wrap(key)
            if prot.unwrap(master) != key:  # round trip before trusting it
                raise OSError("round trip mismatch")
        except Exception as e:
            errors.append(f"{name}: {e}")
            continue
        cfg.mkdir(parents=True, exist_ok=True)
        _write_private(ks, json.dumps(
            {"format": KEYSTORE_FORMAT, "version": 1, "master": master}, indent=2
        ).encode("utf-8"))
        _CACHE[cache_key] = key
        return key
    raise KeystoreUnavailable("Nessuna protezione disponibile: " + "; ".join(errors))


def _write_private(path: pathlib.Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
    fd = os.open(str(path), flags, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def atomic_write(path: pathlib.Path, data: bytes) -> None:
    """Write via a temp file in the same folder, then replace (atomic)."""
    tmp = path.with_name(path.name + ".part")
    _write_private(tmp, data)
    os.replace(tmp, path)


def secure_delete(path: pathlib.Path) -> None:
    """Best effort: overwrite with zeros, truncate, unlink.

    SSD wear levelling, backups and file-system journals may keep copies.
    """
    try:
        size = path.stat().st_size
        with open(path, "r+b") as fh:
            fh.write(b"\x00" * size)
            fh.flush()
            os.fsync(fh.fileno())
            fh.truncate(0)
    except OSError:
        pass
    try:
        path.unlink()
    except OSError:
        pass
