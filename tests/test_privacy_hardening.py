"""Restore-map hardening and pseudonym styles."""

import base64
import json
import os

import pytest

pytest.importorskip("cryptography")

import privacy_core as pc


def _payload():
    reg = pc.PlaceholderRegistry()
    reg.placeholder_for(
        "Mario Rossi", "PERSON", page=0, rect=(1, 2, 3, 4),
        style={"font": "x", "size": 10.0, "color": 0, "flags": 0,
               "origin": [1.0, 2.0], "text": "Mario Rossi"},
    )
    return pc.build_restore_payload(
        source_name="C:/docs/Referto_Mario_Rossi.pdf", source_sha256="a",
        output_sha256="b", entries=reg.entries(),
    )


def test_payload_omits_source_name_and_duplicated_style_text():
    payload = _payload()
    assert payload["source_name"] == ""
    occ = payload["entries"][0]["occurrences"][0]
    assert "text" not in occ["style"]
    assert pc.parse_restore_entries(payload)[0].original == "Mario Rossi"
    kept = pc.build_restore_payload(
        source_name="a/b.pdf", source_sha256="", output_sha256=None,
        entries=[], keep_source_name=True,
    )
    assert kept["source_name"] == "b.pdf"


def test_style_text_is_kept_when_it_differs():
    reg = pc.PlaceholderRegistry()
    reg.placeholder_for("Mario", "PERSON", rect=(0, 0, 1, 1),
                        style={"font": "", "size": 9.0, "origin": [0, 0], "text": "Mario Rossi"})
    occ = pc.build_restore_payload(
        source_name="", source_sha256="", output_sha256=None, entries=reg.entries()
    )["entries"][0]["occurrences"][0]
    assert occ["style"]["text"] == "Mario Rossi"


def test_new_maps_are_v3_and_roundtrip():
    blob = pc.encrypt_restore_payload(_payload(), "una frase molto lunga 2026")
    env = json.loads(blob)
    assert env["version"] == 3 and env["cipher"] == "AES-256-GCM"
    assert [w["type"] for w in env["wraps"]] == ["password"]
    assert env["wraps"][0]["kdf"] in ("argon2id", "scrypt")
    assert pc.decrypt_restore_payload(blob, "una frase molto lunga 2026")["format"] == pc.RESTORE_MAP_FORMAT
    from cryptography.fernet import InvalidToken
    with pytest.raises(InvalidToken):
        pc.decrypt_restore_payload(blob, "una frase sbagliata 2026!")


def test_v2_scrypt_maps_still_decrypt():
    blob = pc._encrypt_v2(_payload(), "una frase molto lunga 2026")
    assert json.loads(blob)["version"] == 2
    assert pc.decrypt_restore_payload(blob, "una frase molto lunga 2026")["version"] == pc.RESTORE_MAP_VERSION


def _legacy_pbkdf2_blob(password, iterations):
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    salt = b"0123456789abcdef"
    key = base64.urlsafe_b64encode(
        PBKDF2HMAC(hashes.SHA256(), 32, salt, iterations).derive(password.encode())
    )
    token = Fernet(key).encrypt(json.dumps(_payload()).encode())
    return json.dumps({
        "format": "NullifyPDF encrypted restore map", "version": 1,
        "kdf": "PBKDF2-HMAC-SHA256", "iterations": iterations,
        "salt": base64.b64encode(salt).decode(), "token": token.decode(),
    }).encode()


def test_legacy_pbkdf2_maps_still_decrypt():
    blob = _legacy_pbkdf2_blob("legacy password 123", 600000)
    assert pc.decrypt_restore_payload(blob, "legacy password 123")["version"] == pc.RESTORE_MAP_VERSION


@pytest.mark.parametrize("iterations", [1, 99_999, 5_000_001, 10 ** 12])
def test_untrusted_iteration_counts_are_rejected_before_derivation(iterations):
    blob = _legacy_pbkdf2_blob("legacy password 123", 600000)
    env = json.loads(blob)
    env["iterations"] = iterations
    with pytest.raises(ValueError):
        pc.decrypt_restore_payload(json.dumps(env).encode(), "legacy password 123")


@pytest.mark.parametrize("n,r,p", [(2 ** 30, 8, 1), (1000, 8, 1), (2 ** 17, 1000, 1), (2 ** 17, 8, 99)])
def test_untrusted_scrypt_parameters_are_rejected(n, r, p):
    env = json.loads(pc._encrypt_v2(_payload(), "una frase molto lunga 2026"))
    env.update(n=n, r=r, p=p)
    with pytest.raises(ValueError):
        pc.decrypt_restore_payload(json.dumps(env).encode(), "una frase molto lunga 2026")


def test_unknown_kdf_is_rejected():
    env = json.loads(pc._encrypt_v2(_payload(), "una frase molto lunga 2026"))
    env["kdf"] = "md5"
    with pytest.raises(ValueError):
        pc.decrypt_restore_payload(json.dumps(env).encode(), "una frase molto lunga 2026")


@pytest.mark.parametrize("pw,ok", [
    ("short1!", False),
    ("aaaaaaaaaaaaaaaa", False),
    ("passwordpassword1", False),
    ("abcdefghijklm", False),
    ("Abcdefghijklm", True),
    ("una frase molto lunga davvero", True),
    ("Xk3!mP9#qR2$", True),
])
def test_password_strength(pw, ok):
    assert pc.password_strength(pw)[0] is ok


def test_encrypt_still_requires_minimum_length():
    with pytest.raises(ValueError):
        pc.encrypt_restore_payload(_payload(), "short")


def test_counter_style_is_unchanged():
    reg = pc.PlaceholderRegistry()
    assert reg.placeholder_for("A Uno", "PERSON") == "PERSON_001"
    assert reg.placeholder_for("B Due", "PERSON") == "PERSON_002"
    assert reg.placeholder_for("a uno", "PERSON") == "PERSON_001"


def test_random_style_reveals_neither_order_nor_count():
    values = [f"Persona Numero{i}" for i in range(30)]
    a, b = pc.PlaceholderRegistry("random"), pc.PlaceholderRegistry("random")
    pa = [a.placeholder_for(v, "PERSON") for v in values]
    pb = [b.placeholder_for(v, "PERSON") for v in values]
    assert len(set(pa)) == 30
    assert pa != pb  # fresh randomness per document
    assert all(p.startswith("PERSON_") and len(p) >= len("PERSON_") + 4 for p in pa)
    assert pa == [a.placeholder_for(v, "PERSON") for v in values]  # stable within a document
    assert pa != sorted(pa) or pb != sorted(pb)


def test_opaque_style_hides_the_type():
    reg = pc.PlaceholderRegistry("opaque")
    assert reg.placeholder_for("Mario", "PERSON").startswith("DATA_")
    assert reg.entries()[0].entity_type == "PERSON"  # kept inside the encrypted map


def test_keyed_style_is_consistent_per_key_only():
    k1, k2 = b"k" * 32, b"j" * 32
    a = pc.PlaceholderRegistry("keyed", k1).placeholder_for("Mario Rossi", "PERSON")
    b = pc.PlaceholderRegistry("keyed", k1).placeholder_for("mario  rossi", "PERSON")
    c = pc.PlaceholderRegistry("keyed", k2).placeholder_for("Mario Rossi", "PERSON")
    assert a == b and a != c
    assert pc.PlaceholderRegistry("keyed", k1).placeholder_for("Mario Rossi", "LOCATION") != a
    with pytest.raises(ValueError):
        pc.PlaceholderRegistry("keyed")
    with pytest.raises(ValueError):
        pc.PlaceholderRegistry("nonsense")


def test_unknown_or_foreign_envelope_gives_a_clear_error():
    blob = pc._encrypt_v2(_payload(), "una frase molto lunga 2026")
    env = json.loads(blob)
    env["version"] = 9
    with pytest.raises(ValueError, match="non supportata"):
        pc.decrypt_restore_payload(json.dumps(env).encode(), "una frase molto lunga 2026")
    env["format"] = "something else"
    with pytest.raises(ValueError, match="non riconosciuto"):
        pc.decrypt_restore_payload(json.dumps(env).encode(), "una frase molto lunga 2026")


# --- envelope v3: recovery key, Argon2id, key export -----------------------------

PW = "una frase molto lunga 2026"


def test_v3_password_and_recovery_open_the_same_payload():
    raw, shown = pc.generate_recovery_key()
    blob = pc.encrypt_restore_payload(_payload(), PW, recovery_key=raw)
    assert [w["type"] for w in json.loads(blob)["wraps"]] == ["password", "recovery"]
    by_pw = pc.decrypt_restore_payload(blob, PW)
    by_rk = pc.decrypt_restore_payload(blob, None, recovery_key=pc.parse_recovery_key(shown))
    assert by_pw == by_rk
    from cryptography.fernet import InvalidToken
    with pytest.raises(InvalidToken):
        pc.decrypt_restore_payload(blob, None, recovery_key=os.urandom(32))
    with pytest.raises(InvalidToken):
        pc.decrypt_restore_payload(blob)  # nothing supplied


def test_recovery_key_format_and_checksum():
    raw, shown = pc.generate_recovery_key()
    assert shown.startswith("NPDF-") and len(shown.replace("-", "")) == 4 + 54
    assert pc.parse_recovery_key(shown.lower().replace("-", " ")) == raw  # forgiving of case/spacing
    typo = shown[:8] + ("A" if shown[8] != "A" else "B") + shown[9:]
    with pytest.raises(ValueError, match="digitata|non valida"):
        pc.parse_recovery_key(typo)
    with pytest.raises(ValueError):
        pc.parse_recovery_key("NPDF-ABCD")


def test_v3_wrap_type_swap_fails():
    raw, _ = pc.generate_recovery_key()
    env = json.loads(pc.encrypt_restore_payload(_payload(), PW, recovery_key=raw))
    env["wraps"][1]["type"] = "password"   # pretend the recovery wrap is a password wrap
    env["wraps"].pop(0)
    from cryptography.fernet import InvalidToken
    with pytest.raises((InvalidToken, KeyError, ValueError)):
        pc.decrypt_restore_payload(json.dumps(env).encode(), PW)


def test_v3_tampering_is_detected():
    env = json.loads(pc.encrypt_restore_payload(_payload(), PW))
    ct = bytearray(base64.b64decode(env["ciphertext"]))
    ct[0] ^= 1
    env["ciphertext"] = base64.b64encode(bytes(ct)).decode()
    from cryptography.fernet import InvalidToken
    with pytest.raises(InvalidToken):
        pc.decrypt_restore_payload(json.dumps(env).encode(), PW)


@pytest.mark.skipif(not pc._argon2_available(), reason="Argon2id not available in this OpenSSL")
@pytest.mark.parametrize("field,value", [
    ("t", 0), ("t", 11), ("m", 1024), ("m", 2 ** 21), ("p", 0), ("p", 9),
])
def test_argon2id_bounds_are_enforced_before_derivation(field, value):
    env = json.loads(pc.encrypt_restore_payload(_payload(), PW))
    assert env["wraps"][0]["kdf"] == "argon2id"
    env["wraps"][0][field] = value
    with pytest.raises(ValueError, match="limiti"):
        pc.decrypt_restore_payload(json.dumps(env).encode(), PW)


def test_argon2_unavailable_falls_back_to_scrypt_for_writing(monkeypatch):
    monkeypatch.setattr(pc, "_argon2_available", lambda: False)
    blob = pc.encrypt_restore_payload(_payload(), PW)
    assert json.loads(blob)["wraps"][0]["kdf"] == "scrypt"
    assert pc.decrypt_restore_payload(blob, PW)["format"] == pc.RESTORE_MAP_FORMAT


def test_pseudonym_key_export_import_roundtrip_and_wrong_password():
    key = os.urandom(32)
    blob = pc.export_pseudonym_key(key, PW)
    assert key not in blob and base64.b64encode(key) not in blob
    assert pc.import_pseudonym_key(blob, PW) == key
    from cryptography.fernet import InvalidToken
    with pytest.raises(InvalidToken):
        pc.import_pseudonym_key(blob, "un'altra frase lunga 2026")
    with pytest.raises(ValueError):
        pc.import_pseudonym_key(pc.encrypt_restore_payload(_payload(), PW), PW)  # a map, not a key
    with pytest.raises(ValueError):
        pc.export_pseudonym_key(b"short", PW)
