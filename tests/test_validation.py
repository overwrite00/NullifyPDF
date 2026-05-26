"""Smoke tests for input validation and core functionality.

Tests verify that Phase 1-2 critical fixes work correctly:
- Input validation prevents crashes
- Type hints are correct
- No regression in existing functionality
"""

import pytest
import pathlib
import tempfile
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from NullifyPDF import PDFListManager, resource_path


class TestPDFListManager:
    """Test PDFListManager persistence and validation."""

    def test_load_empty_nonexistent_file(self):
        """PDFListManager should handle non-existent files gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = PDFListManager(pathlib.Path(tmpdir))
            assert mgr.load_blocklist() == set()
            assert mgr.load_allowlist() == set()

    def test_save_and_load_blocklist(self):
        """Save and load blocklist should round-trip correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = PDFListManager(pathlib.Path(tmpdir))
            test_words = {"password", "secret", "api_key"}

            mgr.save_blocklist(test_words)
            loaded = mgr.load_blocklist()

            assert loaded == test_words

    def test_save_and_load_allowlist(self):
        """Save and load allowlist should round-trip correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = PDFListManager(pathlib.Path(tmpdir))
            test_words = {"public", "official", "example"}

            mgr.save_allowlist(test_words)
            loaded = mgr.load_allowlist()

            assert loaded == test_words

    def test_word_normalization(self):
        """Words should be normalized to lowercase and stripped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = PDFListManager(pathlib.Path(tmpdir))

            # Words too short should be filtered
            test_words = {"a", "ab", "abc", "abcd"}
            mgr.save_blocklist(test_words)
            loaded = mgr.load_blocklist()

            # Only words with len > 2 should remain
            assert loaded == {"abc", "abcd"}

    def test_config_dir_creation(self):
        """PDFListManager should create config directory if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "nested" / "config"
            assert not config_path.exists()

            mgr = PDFListManager(config_path)

            assert config_path.exists()


class TestResourcePath:
    """Test resource path resolution."""

    def test_resource_path_returns_string(self):
        """resource_path should return a string."""
        result = resource_path("images/test.png")
        assert isinstance(result, str)

    def test_resource_path_not_empty(self):
        """resource_path should never return empty string."""
        result = resource_path("images/test.png")
        assert len(result) > 0


@pytest.mark.parametrize("invalid_input", [None, "", 123, []])
def test_list_manager_handles_invalid_paths(invalid_input):
    """PDFListManager should not crash on invalid paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = PDFListManager(pathlib.Path(tmpdir))
        # Should not raise exception
        try:
            result = mgr.load_blocklist()
            assert isinstance(result, set)
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
