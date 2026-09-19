"""Tests for build configuration."""

import pathlib

import pytest

from build_local import (
    ensure_ocr_data,
    get_file_version,
    get_version_info,
    pyinstaller_datas,
)


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


def test_build_rejects_missing_ocr_data_when_download_disabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError):
        pyinstaller_datas(download_missing_ocr=False)


def test_build_downloads_missing_ocr_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def fake_download(output_dir):
        output_dir.mkdir(parents=True)
        (output_dir / "eng.traineddata").write_bytes(b"eng")
        (output_dir / "ita.traineddata").write_bytes(b"ita")

    ensure_ocr_data(download_func=fake_download)

    assert (pathlib.Path("ocr") / "tessdata" / "eng.traineddata").exists()
    assert (pathlib.Path("ocr") / "tessdata" / "ita.traineddata").exists()


def test_build_includes_ocr_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tessdata = pathlib.Path("ocr") / "tessdata"
    tessdata.mkdir(parents=True)
    (tessdata / "eng.traineddata").write_bytes(b"eng")
    (tessdata / "ita.traineddata").write_bytes(b"ita")

    datas = pyinstaller_datas()

    assert ("ocr/tessdata/eng.traineddata", "ocr/tessdata") in datas
    assert ("ocr/tessdata/ita.traineddata", "ocr/tessdata") in datas


def test_tldextract_data_is_bundled_by_the_build_recipes():
    """Presidio's email recognizer needs tldextract's `.tld_set_snapshot`.

    Without it the frozen app raised FileNotFoundError on the first email
    found by an AI scan, so every build recipe must collect the package.
    """
    root = pathlib.Path(__file__).parent.parent
    for recipe in ("NullifyPDF.spec", "build_local.py"):
        assert "'tldextract'" in (root / recipe).read_text(encoding="utf-8"), recipe

    pytest.importorskip("PyInstaller")
    from PyInstaller.utils.hooks import collect_all

    datas = collect_all("tldextract")[0]
    assert any(src.endswith(".tld_set_snapshot") for src, _dest in datas)
