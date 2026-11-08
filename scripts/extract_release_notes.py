"""Print the CHANGELOG.md section that matches a release tag.

Used by the release workflows to fill the GitHub release body, which the
in-app update check then shows to the user.

* stable tag ``vX.Y.Z``          -> the ``## [X.Y.Z] - date`` section
* beta tag ``vX.Y.Z-beta.N``     -> the ``## [Unreleased]`` section (betas get
  no heading of their own; only the final stable version does)

Usage: python scripts/extract_release_notes.py <tag> [CHANGELOG.md]
Exits 1 and prints nothing when the section is missing or empty.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def extract_notes(changelog: str, tag: str) -> str:
    version = tag[1:] if tag.startswith("v") else tag
    wanted = "Unreleased" if "-" in version else re.escape(version)
    lines = changelog.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^## \[{wanted}\]", line):
            start = i + 1
            break
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("## ["):
            break
        body.append(line)
    return "\n".join(body).strip()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(argv[2]) if len(argv) > 2 else Path("CHANGELOG.md")
    notes = extract_notes(path.read_text(encoding="utf-8"), argv[1])
    if not notes:
        return 1
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
