"""Optional Italian pipeline: verified download, safe unpacking, fallback."""

import hashlib
import io
import pathlib
import zipfile

import pytest

import spacy_models as sm


def _wheel(path: pathlib.Path, names) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in names:
            zf.writestr(name, b"x")
    data = buf.getvalue()
    path.write_bytes(data)
    return data


def _serve(monkeypatch, data: bytes):
    monkeypatch.setattr(sm.urllib.request, "urlopen", lambda url, timeout=0: io.BytesIO(data))


def test_rejects_non_https(tmp_path):
    with pytest.raises(sm.ModelDownloadError):
        sm.install_italian(tmp_path, url="http://example.com/x.whl")


def test_rejects_wrong_hash_and_leaves_nothing(tmp_path, monkeypatch):
    data = _wheel(tmp_path / "w.whl", [])
    _serve(monkeypatch, data)
    root = tmp_path / "root"
    with pytest.raises(sm.ModelDownloadError):
        sm.install_italian(root, url="https://example.com/x.whl", sha256="0" * 64, size=len(data))
    assert not sm.italian_installed(root)
    assert not list(root.glob("*.whl"))


def test_rejects_oversized_download(tmp_path, monkeypatch):
    _serve(monkeypatch, b"a" * 100)
    with pytest.raises(sm.ModelDownloadError):
        sm.install_italian(tmp_path / "r", url="https://e.com/x", sha256="0" * 64, size=10)


def test_rejects_path_traversal(tmp_path, monkeypatch):
    p = sm._PIPELINE_DIR
    data = _wheel(tmp_path / "w.whl", [p + "../../evil.txt"])
    _serve(monkeypatch, data)
    with pytest.raises(sm.ModelDownloadError):
        sm.install_italian(
            tmp_path / "r", url="https://e.com/x",
            sha256=hashlib.sha256(data).hexdigest(), size=len(data),
        )
    assert not (tmp_path / "evil.txt").exists()


def test_installs_valid_package(tmp_path, monkeypatch):
    p = sm._PIPELINE_DIR
    data = _wheel(tmp_path / "w.whl", [p + "meta.json", p + "ner/cfg", "other/ignored.txt"])
    _serve(monkeypatch, data)
    root = tmp_path / "r"
    seen = []
    folder = sm.install_italian(
        root, progress=lambda d, t: seen.append((d, t)), url="https://e.com/x",
        sha256=hashlib.sha256(data).hexdigest(), size=len(data),
    )
    assert sm.italian_installed(root) and (folder / "ner" / "cfg").is_file()
    assert not (folder / "ignored.txt").exists() and seen
    sm.remove_italian(root)
    assert not sm.italian_installed(root)


def test_blank_fallback_is_not_statistical(tmp_path):
    blank = sm.blank_italian(tmp_path)
    assert blank.statistical is False and (pathlib.Path(blank.name) / "meta.json").is_file()


def test_resolve_prefers_installed_package_then_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "_is_package", lambda: False)
    assert sm.resolve_italian(tmp_path) is None
    d = tmp_path / f"{sm.ITALIAN_PACKAGE}-{sm.ITALIAN_VERSION}"
    (d / "ner").mkdir(parents=True)
    (d / "meta.json").write_text("{}")
    assert sm.resolve_italian(tmp_path).name == str(d)
    monkeypatch.setattr(sm, "_is_package", lambda: True)
    assert sm.resolve_italian(tmp_path).name == sm.ITALIAN_PACKAGE


def test_licence_text_names_licence_and_source():
    t = sm.licence_text()
    assert "CC BY-NC-SA 3.0" in t and "SHA-256" in t
