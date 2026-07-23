"""Tests for privacy export primitives."""

import pytest

from privacy_core import (
    PlaceholderRegistry,
    build_restore_payload,
    decrypt_restore_payload,
    encrypt_restore_payload,
)


def test_placeholder_registry_reuses_same_value():
    registry = PlaceholderRegistry()

    first = registry.placeholder_for("Mario Rossi", "person", page=1)
    second = registry.placeholder_for("Mario Rossi", "PERSON", page=2)

    assert first == "PERSON_001"
    assert second == first
    assert len(registry.entries()) == 1


def test_placeholder_registry_separates_entity_types():
    registry = PlaceholderRegistry()

    person = registry.placeholder_for("Roma", "person")
    location = registry.placeholder_for("Roma", "location")

    assert person == "PERSON_001"
    assert location == "LOCATION_001"


def test_encrypted_restore_map_round_trip():
    registry = PlaceholderRegistry()
    registry.placeholder_for("mario.rossi@example.com", "EMAIL_ADDRESS", page=0)
    payload = build_restore_payload(
        source_name="input.pdf",
        source_sha256="a" * 64,
        output_sha256=None,
        entries=registry.entries(),
    )

    encrypted = encrypt_restore_payload(payload, "Password lunga 123!")
    decrypted = decrypt_restore_payload(encrypted, "Password lunga 123!")

    assert b"mario.rossi@example.com" not in encrypted
    assert decrypted == payload


def test_restore_map_requires_strong_enough_password():
    with pytest.raises(ValueError):
        encrypt_restore_payload({}, "short")
