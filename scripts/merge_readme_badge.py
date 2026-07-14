"""Custom git merge driver: keep the current branch's README release badge.

main's badge tracks the latest stable release; develop's badge tracks the
latest beta (include_prereleases). The two lines are expected to always
differ, so a normal merge would overwrite one branch's badge with the
other's. This driver runs the regular 3-way text merge and then restores
whichever "GitHub Release" badge line was already present on our side,
so merging never requires a manual follow-up commit to fix the badge.

Registered via .gitattributes (`README.md merge=readme-badge`) and enabled
per clone with:
    git config merge.readme-badge.driver "python scripts/merge_readme_badge.py %O %A %B"
"""

import re
import subprocess
import sys

BADGE_PATTERN = re.compile(r"^!\[GitHub Release\].*$", re.MULTILINE)


def main() -> int:
    base_path, ours_path, theirs_path = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(ours_path, "r", encoding="utf-8") as f:
        our_badge_match = BADGE_PATTERN.search(f.read())

    result = subprocess.run(
        ["git", "merge-file", "-L", "HEAD", "-L", "base", "-L", "MERGE_HEAD", ours_path, base_path, theirs_path]
    )

    if our_badge_match:
        with open(ours_path, "r", encoding="utf-8") as f:
            merged = f.read()
        merged = BADGE_PATTERN.sub(our_badge_match.group(0), merged, count=1)
        with open(ours_path, "w", encoding="utf-8") as f:
            f.write(merged)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
