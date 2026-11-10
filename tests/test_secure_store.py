"""Encrypted word lists with expiry, and the key-protection layer."""

import datetime
import json
import os
import sys

import pytest

pytest.importorskip("cryptography")

import secure_store
from word_lists import ListEntry, PDFListManager


@pytest.fixture(autouse=True)
def _fresh_cache():
    secure_store.forget_cached_keys()
    yield
    secure_store.forget_cached_keys()


def test_seal_open_roundtrip_and_aad_binding():
    key = os.urandom(32)
    blob = secure_store.seal(b"dati", key, b"ctx-a")
    assert secure_store.open_sealed(blob, key, b"ctx-a") == b"dati"
    with pytest.raises(secure_store.SealError):
        secure_store.open_sealed(blob, key, b"ctx-b")
    with pytest.raises(secure_store.SealError):
        secure_store.open_sealed(blob[:-1] + bytes([blob[-1] ^ 1]), key, b"ctx-a")
    with pytest.raises(secure_store.SealError):
        secure_store.open_sealed(b"short", key, b"ctx-a")


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
def test_dpapi_roundtrip_and_account_binding(tmp_path):
    p = secure_store.DpapiProtector()
    key = os.urandom(32)
    assert p.unwrap(p.wrap(key)) == key
    assert key not in json.dumps(p.wrap(key)).encode()


def test_keyfile_protector_creates_private_file(tmp_path):
    p = secure_store.KeyFileProtector(tmp_path)
    key = os.urandom(32)
    blob = p.wrap(key)
    assert p.unwrap(blob) == key
    mode = (tmp_path / "keys" / "master.key").stat().st_mode & 0o777
    if sys.platform != "win32":
        assert mode == 0o600


def test_master_key_is_stable_and_not_stored_in_clear_in_keystore(tmp_path):
    k1 = secure_store.load_or_create_master_key(tmp_path)
    secure_store.forget_cached_keys()
    k2 = secure_store.load_or_create_master_key(tmp_path)
    assert k1 == k2 and len(k1) == 32
    ks = (tmp_path / "keystore.json").read_bytes()
    if json.loads(ks)["master"]["protector"] == "dpapi":
        assert k1 not in ks
        assert "DPAPI" in secure_store.protector_label(tmp_path)


def test_keyring_unavailable_falls_back_to_keyfile(tmp_path, monkeypatch):
    monkeypatch.setattr(secure_store, "DpapiProtector", type("D", (), {"available": staticmethod(lambda: False)}))
    monkeypatch.setattr(secure_store.KeyringProtector, "available", staticmethod(lambda: False))
    secure_store.load_or_create_master_key(tmp_path)
    assert json.loads((tmp_path / "keystore.json").read_text())["master"]["protector"] == "keyfile"


def test_plaintext_lists_migrate_transparently(tmp_path):
    (tmp_path / "blocklist.txt").write_text("mario rossi\nvia roma\nab", encoding="utf-8")
    (tmp_path / "allowlist.txt").write_text("comune", encoding="utf-8")
    m = PDFListManager(tmp_path)
    assert m.load_blocklist() == {"mario rossi", "via roma"}
    assert m.load_allowlist() == {"comune"}
    assert not (tmp_path / "blocklist.txt").exists()
    enc = (tmp_path / "blocklist.v2.enc").read_bytes()
    assert b"rossi" not in enc and enc.startswith(b"NPDFL2\n")
    assert PDFListManager(tmp_path).load_blocklist() == {"mario rossi", "via roma"}  # reload


def test_save_roundtrip_filters_short_terms_and_keeps_dates(tmp_path):
    day = {"now": datetime.date(2026, 1, 1)}
    m = PDFListManager(tmp_path, today=lambda: day["now"])
    m.save_blocklist({"abc", "ab", "Mario Rossi"})
    assert m.load_blocklist() == {"abc", "mario rossi"}
    day["now"] = datetime.date(2026, 3, 1)
    m.save_blocklist({"abc", "nuovo termine"})
    entries = {e.term: e for e in m.load_entries("blocklist")}
    assert entries["abc"].added == datetime.date(2026, 1, 1)  # kept
    assert entries["nuovo termine"].added == datetime.date(2026, 3, 1)


def test_expired_entries_are_dropped_and_purged(tmp_path):
    day = {"now": datetime.date(2026, 1, 1)}
    m = PDFListManager(tmp_path, today=lambda: day["now"])
    m.save_entries("blocklist", [
        ListEntry("scade presto", day["now"], datetime.date(2026, 1, 10)),
        ListEntry("per sempre", day["now"], None),
    ])
    day["now"] = datetime.date(2026, 1, 11)
    assert m.load_blocklist() == {"per sempre"}
    assert m.expired_removed == 1
    day["now"] = datetime.date(2025, 12, 1)  # purged for good, not merely hidden
    assert PDFListManager(tmp_path, today=lambda: day["now"]).load_blocklist() == {"per sempre"}


def test_default_ttl_applies_to_new_terms(tmp_path):
    m = PDFListManager(tmp_path, today=lambda: datetime.date(2026, 1, 1))
    m.set_default_ttl_days(30)
    m.save_blocklist({"nuovo termine"})
    e = m.load_entries("blocklist")[0]
    assert e.expires == datetime.date(2026, 1, 31)


def test_unreadable_keystore_degrades_without_data_loss(tmp_path):
    m = PDFListManager(tmp_path)
    m.save_blocklist({"mario rossi"})
    before = (tmp_path / "blocklist.v2.enc").read_bytes()
    ks = json.loads((tmp_path / "keystore.json").read_text())
    if ks["master"]["protector"] == "dpapi":
        ks["master"]["blob"] = "AAAA"
    else:
        (tmp_path / "keys" / "master.key").write_bytes(b"x" * 5)
    (tmp_path / "keystore.json").write_text(json.dumps(ks))
    secure_store.forget_cached_keys()
    m2 = PDFListManager(tmp_path)
    assert m2.load_blocklist() == set()
    assert m2.keystore_error
    m2.save_blocklist({"altro termine"})  # must not overwrite anything
    assert (tmp_path / "blocklist.v2.enc").read_bytes() == before


def test_no_cryptography_keeps_plaintext(tmp_path, monkeypatch):
    import builtins

    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "cryptography" or name.startswith("cryptography."):
            raise ImportError(name)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    m = PDFListManager(tmp_path)
    m.save_blocklist({"mario rossi"})
    monkeypatch.setattr(builtins, "__import__", real)
    assert (tmp_path / "blocklist.txt").read_text(encoding="utf-8") == "mario rossi"
    assert PDFListManager(tmp_path).load_blocklist() == {"mario rossi"}


def test_tampered_list_file_is_not_trusted(tmp_path):
    m = PDFListManager(tmp_path)
    m.save_blocklist({"mario rossi"})
    p = tmp_path / "blocklist.v2.enc"
    raw = bytearray(p.read_bytes())
    raw[-1] ^= 1
    p.write_bytes(bytes(raw))
    assert PDFListManager(tmp_path).load_blocklist() == set()
