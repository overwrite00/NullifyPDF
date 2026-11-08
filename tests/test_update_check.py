"""Tests for the update checker and the release-notes extractor."""

import pathlib
import sys

import pytest

import update_check as uc

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from extract_release_notes import extract_notes  # noqa: E402


def rel(tag, prerelease=False, draft=False, assets=()):
    return {"tag_name": tag, "prerelease": prerelease, "draft": draft,
            "assets": list(assets)}


def test_version_ordering():
    v = uc.parse_version
    assert v("2.3.0-beta.3") < v("2.3.0") < v("2.3.1-beta.1") < v("2.3.1")
    assert v("v2.3.0-beta.9") < v("2.3.0-beta.10")
    assert v("garbage") is None


def test_stable_build_ignores_betas():
    rels = [rel("v2.4.0-beta.1", True), rel("v2.3.1"), rel("v2.3.0")]
    assert uc.find_update(rels, "2.3.0")["tag_name"] == "v2.3.1"
    assert uc.find_update([rel("v2.4.0-beta.1", True)], "2.3.0") is None


def test_beta_build_sees_both_and_picks_highest():
    rels = [rel("v2.3.1"), rel("v2.4.0-beta.2", True), rel("v2.4.0-beta.1", True)]
    assert uc.find_update(rels, "2.3.1-beta.1")["tag_name"] == "v2.4.0-beta.2"
    # the stable that supersedes the running beta is offered
    assert uc.find_update([rel("v2.3.0")], "2.3.0-beta.3")["tag_name"] == "v2.3.0"


def test_up_to_date_and_drafts():
    assert uc.find_update([rel("v2.3.0")], "2.3.0") is None
    assert uc.find_update([rel("v9.0.0", draft=True)], "2.3.0") is None


@pytest.mark.parametrize("system,suffix", [
    ("Windows", "_Windows.exe"), ("Darwin", "_macOS.zip")])
def test_asset_selection(system, suffix):
    base = "https://github.com/overwrite00/NullifyPDF/releases/download/v2.3.1/"
    names = ["NullifyPDF_v2.3.1_Windows.exe", "NullifyPDF_v2.3.1_macOS.zip"]
    release = rel("v2.3.1", assets=[
        {"name": n, "browser_download_url": base + n} for n in names])
    assert uc.select_asset(release, system)["name"].endswith(suffix)


def test_untrusted_asset_url_rejected():
    release = rel("v2.3.1", assets=[{
        "name": "NullifyPDF_v2.3.1_Windows.exe",
        "browser_download_url": "https://evil.example/NullifyPDF_v2.3.1_Windows.exe"}])
    assert uc.select_asset(release, "Windows") is None
    assert not uc.is_trusted_url("http://github.com/x")


def test_filename_safety(tmp_path):
    assert uc.safe_filename("../../evil.exe") == "evil.exe"
    (tmp_path / "a.exe").write_bytes(b"x")
    assert uc.unique_path(tmp_path, "a.exe").name == "a (1).exe"


CHANGELOG = """# Changelog

## [Unreleased]

- pending item

## [2.3.0] - 2026-09-19

### Added
- stable item

## [2.2.0] - 2026-09-18

- old item
"""


def test_notes_from_correct_section():
    assert extract_notes(CHANGELOG, "v2.3.0") == "### Added\n- stable item"
    assert extract_notes(CHANGELOG, "v2.4.0-beta.1") == "- pending item"
    assert extract_notes(CHANGELOG, "v9.9.9") == ""


def test_downloads_folder_exists():
    from PySide6.QtWidgets import QApplication  # noqa: F401
    import NullifyPDF
    assert NullifyPDF.downloads_folder().is_dir()


def test_auto_check_preference(tmp_path):
    f = tmp_path / "sub" / "update_check.json"
    assert uc.load_auto_check(f) is False  # default off, missing file
    uc.save_auto_check(f, True)
    assert uc.load_auto_check(f) is True
    uc.save_auto_check(f, False)
    assert uc.load_auto_check(f) is False
    f.write_text("garbage")
    assert uc.load_auto_check(f) is False
