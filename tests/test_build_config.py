"""Tests for build variant configuration."""

import pathlib

import pytest

from build_local import (
    ensure_ocr_data,
    get_file_version,
    get_version_info,
    normalize_build_variant,
    pyinstaller_datas,
    variant_from_args,
)


class Args:
    def __init__(self, *, lite=False, full=False):
        self.lite = lite
        self.full = full


def test_normalize_build_variant_defaults_to_lite(monkeypatch):
    monkeypatch.delenv("NULLIFYPDF_BUILD_VARIANT", raising=False)

    assert normalize_build_variant(None) == "lite"


def test_variant_from_args_prefers_cli_over_environment(monkeypatch):
    monkeypatch.setenv("NULLIFYPDF_BUILD_VARIANT", "full")

    assert variant_from_args(Args(lite=True)) == "lite"
    assert variant_from_args(Args(full=True)) == "full"


def test_invalid_build_variant_is_rejected():
    with pytest.raises(ValueError):
        normalize_build_variant("huge")


def test_get_version_info_reads_base_and_prerelease(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "NullifyPDF.py").write_text(
        '__version__ = "9.9.9"\n__version_prerelease__ = "beta.7"\n',
        encoding="utf-8",
    )

    assert get_version_info() == ("9.9.9", "beta.7")


def test_get_file_version_prefers_env_suffix_without_duplication():
    assert get_file_version("2.1.0", "beta.1", "") == "2.1.0-beta.1"
    assert get_file_version("2.1.0", "beta.1", "beta.1") == "2.1.0-beta.1"
    assert get_file_version("2.1.0", "", "beta.2") == "2.1.0-beta.2"


def test_lite_build_does_not_require_ocr_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert pyinstaller_datas("lite") == []


def test_full_build_can_reject_missing_ocr_data_when_download_disabled(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError):
        pyinstaller_datas("full", download_missing_ocr=False)


def test_full_build_downloads_missing_ocr_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def fake_download(output_dir):
        output_dir.mkdir(parents=True)
        (output_dir / "eng.traineddata").write_bytes(b"eng")
        (output_dir / "ita.traineddata").write_bytes(b"ita")

    ensure_ocr_data(download_func=fake_download)

    assert (pathlib.Path("ocr") / "tessdata" / "eng.traineddata").exists()
    assert (pathlib.Path("ocr") / "tessdata" / "ita.traineddata").exists()


def test_full_build_includes_ocr_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tessdata = pathlib.Path("ocr") / "tessdata"
    tessdata.mkdir(parents=True)
    (tessdata / "eng.traineddata").write_bytes(b"eng")
    (tessdata / "ita.traineddata").write_bytes(b"ita")

    datas = pyinstaller_datas("full")

    assert ("ocr/tessdata/eng.traineddata", "ocr/tessdata") in datas
    assert ("ocr/tessdata/ita.traineddata", "ocr/tessdata") in datas
