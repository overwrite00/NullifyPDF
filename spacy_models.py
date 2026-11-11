"""Optional spaCy pipelines that are downloaded on demand instead of bundled.

The Italian pipeline ``it_core_news_md`` is published under CC BY-NC-SA 3.0
(non-commercial, share-alike). NullifyPDF is AGPL-3.0, whose recipients may use
the program commercially, so that pipeline cannot be part of the installer.
It is downloaded only after the user has seen the licence and agreed, from the
publisher's release page, verified against a pinned size and SHA-256 and kept
in the user's configuration folder. Detection quality is the same as when it
was bundled.

When the user declines, a blank Italian pipeline (MIT, part of spaCy itself) is
used so the rule-based detectors keep working; only the statistical name
recogniser is missing and the caller must say so.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import Callable, Optional

ITALIAN_PACKAGE = "it_core_news_md"
ITALIAN_VERSION = "3.8.0"
ITALIAN_URL = (
    "https://github.com/explosion/spacy-models/releases/download/"
    f"{ITALIAN_PACKAGE}-{ITALIAN_VERSION}/{ITALIAN_PACKAGE}-{ITALIAN_VERSION}-py3-none-any.whl"
)
ITALIAN_SHA256 = "a731d2d8e7c5a7093ac42f88774ea2a2ad3d5809959eedee65632b3533f804ec"
ITALIAN_SIZE = 42389964
ITALIAN_LICENSE = "CC BY-NC-SA 3.0"
ITALIAN_LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/3.0/"
_MAX_UNPACKED = 120 * 1024 * 1024
_PIPELINE_DIR = f"{ITALIAN_PACKAGE}/{ITALIAN_PACKAGE}-{ITALIAN_VERSION}/"

ProgressFn = Callable[[int, int], None]


class ModelDownloadError(RuntimeError):
    """The pipeline could not be downloaded or failed verification."""


@dataclass(frozen=True)
class ResolvedModel:
    name: str  # what Presidio/spaCy should load: package name or folder path
    statistical: bool  # False for the blank fallback (no name recogniser)


def models_root(config_dir: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(config_dir) / "spacy_models"


def _installed_dir(root: pathlib.Path) -> pathlib.Path:
    return root / f"{ITALIAN_PACKAGE}-{ITALIAN_VERSION}"


def italian_installed(root: pathlib.Path) -> bool:
    d = _installed_dir(root)
    return (d / "meta.json").is_file() and (d / "ner").is_dir()


def _is_package() -> bool:
    import spacy

    return bool(spacy.util.is_package(ITALIAN_PACKAGE))


def resolve_italian(root: pathlib.Path) -> Optional[ResolvedModel]:
    """The Italian statistical pipeline if it is available locally, else None."""
    if _is_package():  # development checkouts and tests
        return ResolvedModel(ITALIAN_PACKAGE, True)
    if italian_installed(root):
        return ResolvedModel(str(_installed_dir(root)), True)
    return None


def blank_italian(root: pathlib.Path) -> ResolvedModel:
    """Rules-only fallback: tokenizer and sentence splitter, no NER."""
    import spacy

    path = root / "blank_it"
    if not (path / "meta.json").is_file():
        root.mkdir(parents=True, exist_ok=True)
        nlp = spacy.blank("it")
        nlp.add_pipe("sentencizer")
        nlp.to_disk(path)
    return ResolvedModel(str(path), False)


def _extract(wheel: pathlib.Path, target: pathlib.Path) -> None:
    """Unpack only the pipeline folder; reject any path that escapes."""
    total = 0
    base = target.resolve()
    with zipfile.ZipFile(wheel) as zf:
        for info in zf.infolist():
            if not info.filename.startswith(_PIPELINE_DIR) or info.is_dir():
                continue
            rel = pathlib.PurePosixPath(info.filename[len(_PIPELINE_DIR):])
            if rel.is_absolute() or ".." in rel.parts:
                raise ModelDownloadError("percorso non sicuro nel pacchetto")
            total += info.file_size
            if total > _MAX_UNPACKED:
                raise ModelDownloadError("pacchetto troppo grande")
            dest = (base / pathlib.Path(*rel.parts)).resolve()
            if base not in dest.parents:
                raise ModelDownloadError("percorso non sicuro nel pacchetto")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)


def install_italian(
    root: pathlib.Path,
    progress: Optional[ProgressFn] = None,
    url: str = ITALIAN_URL,
    sha256: str = ITALIAN_SHA256,
    size: int = ITALIAN_SIZE,
    timeout: float = 30.0,
) -> pathlib.Path:
    """Download, verify and unpack the pipeline. Returns its folder."""
    if not url.lower().startswith("https://"):
        raise ModelDownloadError("sono consentiti solo download HTTPS")
    root.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(suffix=".whl", dir=root)
    os.close(fd)
    tmp = pathlib.Path(tmp_name)
    staging = pathlib.Path(tempfile.mkdtemp(prefix="unpack-", dir=root))
    try:
        digest = hashlib.sha256()
        done = 0
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp, tmp.open("wb") as out:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > size:
                        raise ModelDownloadError("il file scaricato è più grande del previsto")
                    digest.update(chunk)
                    out.write(chunk)
                    if progress:
                        progress(done, size)
        except OSError as exc:
            raise ModelDownloadError(f"download non riuscito: {exc}") from exc
        if done != size or digest.hexdigest() != sha256:
            raise ModelDownloadError("verifica di integrità fallita (dimensione o SHA-256)")
        _extract(tmp, staging)
        if not ((staging / "meta.json").is_file() and (staging / "ner").is_dir()):
            raise ModelDownloadError("pacchetto incompleto")
        final = _installed_dir(root)
        if final.exists():
            shutil.rmtree(final)
        os.replace(staging, final)
        return final
    finally:
        tmp.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)


def remove_italian(root: pathlib.Path) -> None:
    shutil.rmtree(_installed_dir(root), ignore_errors=True)


def licence_text() -> str:
    return (
        "Il riconoscimento statistico dei nomi in italiano usa la pipeline spaCy "
        f"«{ITALIAN_PACKAGE}» {ITALIAN_VERSION} (Explosion), distribuita con licenza "
        f"{ITALIAN_LICENSE} ({ITALIAN_LICENSE_URL}): uso non commerciale, con "
        "attribuzione e condivisione alle stesse condizioni. Non è inclusa "
        "nell'installer perché NullifyPDF è AGPL-3.0 e consente l'uso commerciale.\n\n"
        f"Verrà scaricata da GitHub ({ITALIAN_SIZE // (1024 * 1024)} MB), "
        "verificata con SHA-256 e salvata solo sul tuo computer. "
        "Accettando dichiari di usarla nel rispetto di quella licenza."
    )


__all__ = [
    "ModelDownloadError",
    "ResolvedModel",
    "blank_italian",
    "install_italian",
    "italian_installed",
    "licence_text",
    "models_root",
    "remove_italian",
    "resolve_italian",
]
