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


def test_downloads_folder_resolves_without_side_effects():
    import NullifyPDF
    assert NullifyPDF.downloads_folder().name


def test_auto_check_preference(tmp_path):
    f = tmp_path / "sub" / "update_check.json"
    assert uc.load_auto_check(f) is False  # default off, missing file
    uc.save_auto_check(f, True)
    assert uc.load_auto_check(f) is True
    uc.save_auto_check(f, False)
    assert uc.load_auto_check(f) is False
    f.write_text("garbage")
    assert uc.load_auto_check(f) is False


# --- Linux family / download hardening ---------------------------------------

@pytest.mark.parametrize("osrel,suffix", [
    ('ID=ubuntu\nID_LIKE=debian\n', "_Ubuntu.deb"),
    ('ID=debian\n', "_Ubuntu.deb"),
    ('ID="rocky"\nID_LIKE="rhel centos fedora"\n', "_Fedora.rpm"),
    ('ID=fedora\n', "_Fedora.rpm"),
    ('ID=opensuse-leap\nID_LIKE="suse opensuse"\n', None),
    ('ID=arch\n', None),
])
def test_linux_family_from_os_release(monkeypatch, osrel, suffix):
    monkeypatch.setattr(pathlib.Path, "read_text", lambda self, **kw: osrel)
    assert uc.asset_suffix_for_platform("Linux") == suffix


def test_unknown_distribution_gets_no_asset(monkeypatch):
    monkeypatch.setattr(pathlib.Path, "read_text", lambda self, **kw: "ID=arch\n")
    release = rel("v2.3.1", assets=[{
        "name": "NullifyPDF_v2.3.1_Ubuntu.deb",
        "browser_download_url": "https://github.com/overwrite00/NullifyPDF/releases/download/v2.3.1/NullifyPDF_v2.3.1_Ubuntu.deb"}])
    assert uc.select_asset(release, "Linux") is None


class _FakeResp:
    def __init__(self, data, url="https://github.com/x/NullifyPDF_v1_Windows.exe"):
        self._d, self._url, self.headers = data, url, {"Content-Length": str(len(data))}

    def read(self, n):
        out, self._d = self._d[:n], self._d[n:]
        return out

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_open(monkeypatch, data, url="https://github.com/x/f.exe"):
    monkeypatch.setattr(uc._OPENER, "open", lambda req, timeout=0: _FakeResp(data, url))


def test_download_ok_and_digest_checked(tmp_path, monkeypatch):
    import hashlib
    data = b"installer" * 1000
    _patch_open(monkeypatch, data)
    dest = tmp_path / "f.exe"
    uc.download_file("https://github.com/x/f.exe", dest, len(data),
                     digest="sha256:" + hashlib.sha256(data).hexdigest())
    assert dest.read_bytes() == data and not (tmp_path / "f.exe.part").exists()


def test_download_bad_digest_or_size_leaves_nothing(tmp_path, monkeypatch):
    _patch_open(monkeypatch, b"abc")
    dest = tmp_path / "f.exe"
    with pytest.raises(IOError):
        uc.download_file("https://github.com/x/f.exe", dest, 3, digest="sha256:" + "0" * 64)
    with pytest.raises(IOError):
        uc.download_file("https://github.com/x/f.exe", dest, 99)
    assert list(tmp_path.iterdir()) == []


def test_download_cancel_and_untrusted(tmp_path, monkeypatch):
    _patch_open(monkeypatch, b"abc" * 10)
    with pytest.raises(InterruptedError):
        uc.download_file("https://github.com/x/f.exe", tmp_path / "f.exe", cancelled=lambda: True)
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(ValueError):
        uc.download_file("https://evil.example/f.exe", tmp_path / "f.exe")
    _patch_open(monkeypatch, b"abc", url="https://evil.example/f.exe")
    with pytest.raises(ValueError):
        uc.download_file("https://github.com/x/f.exe", tmp_path / "g.exe")


def test_redirect_handler_refuses_untrusted_hosts():
    h = uc._TrustedRedirects()
    with pytest.raises(ValueError):
        h.redirect_request(None, None, 302, "Found", {}, "http://github.com/x")
