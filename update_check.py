"""Qt-free helpers for the "check for updates" feature.

The check is only ever started by an explicit click in the About dialog; the
application never contacts the network on its own.

Stable builds only look at stable releases, beta builds look at both.
"""

from __future__ import annotations

import os
import pathlib
import platform
import re
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_URL = "https://github.com/overwrite00/NullifyPDF"
RELEASES_API_URL = "https://api.github.com/repos/overwrite00/NullifyPDF/releases"

# Downloads and release metadata may only come from GitHub over HTTPS.
_ALLOWED_HOSTS = (
    "api.github.com",
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
)

_VERSION_RE = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$"
)

VersionKey = Tuple[int, int, int, int, Tuple[Any, ...]]


def parse_version(text: str) -> Optional[VersionKey]:
    """Return a sortable key for ``2.3.0`` / ``v2.3.0-beta.4``, or None.

    A prerelease sorts before the same version without suffix (SemVer), and
    numeric prerelease identifiers compare numerically (beta.10 > beta.9).
    """
    m = _VERSION_RE.match(text.strip())
    if not m:
        return None
    major, minor, patch = (int(m.group(i)) for i in (1, 2, 3))
    pre = m.group(4)
    if not pre:
        return (major, minor, patch, 1, ())
    parts: List[Any] = []
    for ident in pre.split("."):
        parts.append((0, int(ident), "") if ident.isdigit() else (1, 0, ident))
    return (major, minor, patch, 0, tuple(parts))


def is_prerelease_version(text: str) -> bool:
    key = parse_version(text)
    return key is not None and key[3] == 0


def is_trusted_url(url: str) -> bool:
    """True for https URLs on the GitHub hosts used for releases."""
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "") in _ALLOWED_HOSTS


def find_update(
    releases: List[Dict[str, Any]], current_version: str
) -> Optional[Dict[str, Any]]:
    """Pick the newest release the running build should be offered.

    Stable builds consider stable releases only; beta builds consider both.
    Drafts and unparsable tags are ignored. Returns None when up to date.
    """
    current = parse_version(current_version)
    if current is None:
        return None
    include_pre = is_prerelease_version(current_version)
    best: Optional[Tuple[VersionKey, Dict[str, Any]]] = None
    for rel in releases:
        if rel.get("draft"):
            continue
        key = parse_version(str(rel.get("tag_name", "")))
        if key is None:
            continue
        # Trust the tag, not the GitHub flag, for what counts as a prerelease.
        if (key[3] == 0 or rel.get("prerelease")) and not include_pre:
            continue
        if key <= current:
            continue
        if best is None or key > best[0]:
            best = (key, rel)
    return best[1] if best else None


def _linux_family() -> str:
    """'deb' or 'rpm' from /etc/os-release (defaults to deb)."""
    try:
        text = pathlib.Path("/etc/os-release").read_text(encoding="utf-8").lower()
    except OSError:
        return "deb"
    ids = " ".join(
        line.split("=", 1)[1]
        for line in text.splitlines()
        if line.startswith(("id=", "id_like="))
    )
    if any(w in ids for w in ("fedora", "rhel", "centos", "suse")):
        return "rpm"
    return "deb"


def asset_suffix_for_platform(system: Optional[str] = None) -> str:
    """Release-asset suffix matching the running OS."""
    system = system or platform.system()
    if system == "Windows":
        return "_Windows.exe"
    if system == "Darwin":
        return "_macOS.zip"
    return "_Fedora.rpm" if _linux_family() == "rpm" else "_Ubuntu.deb"


def select_asset(
    release: Dict[str, Any], system: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """The release asset to download for this OS, or None."""
    suffix = asset_suffix_for_platform(system)
    for asset in release.get("assets", []):
        name = str(asset.get("name", ""))
        if name.startswith("NullifyPDF_v") and name.endswith(suffix):
            if is_trusted_url(str(asset.get("browser_download_url", ""))):
                return asset
    return None


def safe_filename(name: str) -> str:
    """Strip any directory part so a release asset cannot escape the folder."""
    return os.path.basename(name.replace("\\", "/")) or "NullifyPDF_update"


def unique_path(folder: pathlib.Path, name: str) -> pathlib.Path:
    """``folder/name``, or ``name (1)``-style variant if it already exists."""
    target = folder / safe_filename(name)
    stem, suffix = target.stem, target.suffix
    n = 1
    while target.exists():
        target = folder / f"{stem} ({n}){suffix}"
        n += 1
    return target


def fetch_releases(timeout: float = 15.0) -> List[Dict[str, Any]]:
    """Download the release list from the GitHub API."""
    import json

    req = urllib.request.Request(
        RELEASES_API_URL + "?per_page=30",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "NullifyPDF-update-check",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("Unexpected response from GitHub")
    return data


def download_file(
    url: str,
    dest: pathlib.Path,
    expected_size: int = 0,
    progress: Optional[Callable[[int, int], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None,
    timeout: float = 30.0,
) -> None:
    """Stream ``url`` to ``dest`` (via a .part file) and check the size."""
    if not is_trusted_url(url):
        raise ValueError("Refusing to download from an untrusted address")
    req = urllib.request.Request(url, headers={"User-Agent": "NullifyPDF-update-check"})
    part = dest.with_name(dest.name + ".part")
    done = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(part, "wb") as out:  # noqa: S310
            if not is_trusted_url(resp.geturl()):
                raise ValueError("Download redirected to an untrusted address")
            total = int(resp.headers.get("Content-Length") or expected_size or 0)
            while True:
                if cancelled and cancelled():
                    raise InterruptedError("Download cancelled")
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if expected_size and done != expected_size:
            raise IOError(f"Incomplete download ({done} of {expected_size} bytes)")
        part.replace(dest)
    except BaseException:
        try:
            part.unlink()
        except OSError:
            pass
        raise


def load_auto_check(path: pathlib.Path) -> bool:
    """Whether the user enabled the check at every start (default: off)."""
    import json

    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return bool(data.get("check_on_startup", False))
    except Exception:
        return False


def save_auto_check(path: pathlib.Path, enabled: bool) -> None:
    import json

    try:
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"check_on_startup": bool(enabled)}), encoding="utf-8")
    except Exception:
        pass
