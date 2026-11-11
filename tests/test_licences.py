"""Licence consistency: AGPL project, no non-commercial model in the installer."""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf8")


def test_license_file_is_agpl():
    text = _read("LICENSE")
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in text and "Version 3, 19 November 2007" in text
    assert "AGPL-3.0-or-later" in text


def test_installer_never_bundles_the_non_commercial_pipeline():
    src = _read("build_local.py")
    for line in src.splitlines():
        if "collect_all" in line or line.startswith("for pkg in"):
            assert "it_core_news_md" not in line
    assert src.count("excludes=['it_core_news_md'") >= 2
    assert "pymupdf4llm" in src


def test_docs_state_the_licence():
    assert "AGPL" in _read("README.md")
    notices = _read("THIRD_PARTY_NOTICES.md")
    for name in ("PyMuPDF", "PySide6", "it_core_news_md", "Tesseract"):
        assert name in notices
    assert re.search(r"AGPL-3\.0-or-later", _read("build_local.py"))


def test_no_declared_non_commercial_dependency_is_bundled():
    """Every installed distribution that declares a non-commercial licence must
    be on the (empty-by-default) list of components kept out of the installer."""
    from importlib import metadata

    kept_out = {"it-core-news-md", "it_core_news_md"}
    offenders = []
    for dist in metadata.distributions():
        name = (dist.metadata["Name"] or "").lower().replace("_", "-")
        lic = " ".join(filter(None, [dist.metadata.get("License"), dist.metadata.get("License-Expression")]))
        if re.search(r"\bNC\b|non-?commercial", lic, re.I) and name not in kept_out:
            offenders.append((name, lic))
    assert not offenders, offenders
