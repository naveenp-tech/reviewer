"""Minimal unified-diff parser.

We do not send the raw diff to the model blindly: we extract, per file, the
added lines with their line numbers in the *new* file. That gives the model a
stable way to cite findings and lets us cap how much we send.

Supported: git-style diffs (`diff --git`, `---`, `+++`, `@@`) and plain
unified diffs. Not supported: binary patches, renames-only hunks.
"""

import re
from dataclasses import dataclass, field

HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass(frozen=True)
class ChangedFile:
    path: str
    added: list[tuple[int, str]] = field(default_factory=list)

    @property
    def added_line_count(self) -> int:
        return len(self.added)


def parse_unified_diff(diff: str) -> list[ChangedFile]:
    """Return only files that contain at least one added line."""
    files: dict[str, ChangedFile] = {}
    current: str | None = None
    new_line = 0

    for raw in diff.splitlines():
        if raw.startswith("diff --git "):
            current = None
            continue

        if raw.startswith("+++ "):
            path = raw[4:].strip()
            if path == "/dev/null":
                current = None
                continue
            if path.startswith("b/"):
                path = path[2:]
            current = path
            files.setdefault(path, ChangedFile(path))
            continue

        if raw.startswith("--- "):
            continue

        if raw.startswith("@@"):
            match = HUNK_HEADER.match(raw)
            if match:
                new_line = int(match.group(1))
            continue

        if current is None:
            continue

        if raw.startswith("+"):
            files[current].added.append((new_line, raw[1:]))
            new_line += 1
        elif raw.startswith("-"):
            continue
        elif raw.startswith("\\"):
            continue
        else:
            # Context line (leading space) or empty line inside a hunk.
            new_line += 1

    return [changed for changed in files.values() if changed.added]
