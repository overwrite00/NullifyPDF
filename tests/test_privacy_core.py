"""Tests for privacy export primitives."""

import pytest

from privacy_core import (
    PlaceholderEntry,
    PlaceholderRegistry,
    build_restore_payload,
    decrypt_restore_payload,
    encrypt_restore_payload,
    parse_restore_entries,
    sort_entries_longest_placeholder_first,
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


def test_parse_restore_entries_round_trip():
    registry = PlaceholderRegistry()
    registry.placeholder_for("Mario Rossi", "PERSON", page=0)
    payload = build_restore_payload(
        source_name="input.pdf",
        source_sha256="a" * 64,
        output_sha256="b" * 64,
        entries=registry.entries(),
    )

    entries = parse_restore_entries(payload)

    assert entries == [
        PlaceholderEntry(
            placeholder="PERSON_001",
            original="Mario Rossi",
            entity_type="PERSON",
            page=0,
        )
    ]


def test_parse_restore_entries_rejects_unknown_format():
    with pytest.raises(ValueError):
        parse_restore_entries({"format": "something else", "version": 1})


def test_sort_entries_longest_placeholder_first():
    entries = [
        PlaceholderEntry("PERSON_001", "Ann", "PERSON", page=0),
        PlaceholderEntry("PERSON_0010", "Bob", "PERSON", page=0),
        PlaceholderEntry("EMAIL_ADDRESS_001", "a@b.com", "EMAIL_ADDRESS", page=1),
    ]

    sorted_entries = sort_entries_longest_placeholder_first(entries)

    assert [e.placeholder for e in sorted_entries] == [
        "EMAIL_ADDRESS_001",
        "PERSON_0010",
        "PERSON_001",
    ]
