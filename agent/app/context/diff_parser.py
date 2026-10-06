"""Unified diff parsing for GitHub pull request patches (Phase 6.1).

Pure functions, no IO and no third-party dependency. The expected input
is the per-file `patch` field returned by the GitHub API, which contains
only `@@` sections and no `---` / `+++` header. Full raw diffs and
malformed patches are tolerated: unparseable input degrades into notes
instead of raising.

All produced line numbers are 1-based and refer to the new side of the
diff, because findings must be anchored to the head revision.
"""

import re

from app.schemas.code_context import (
    ChangedRange,
    DiffLine,
    DiffLineKind,
    FileDiff,
    FileStatus,
    Hunk,
    Language,
)

JAVA_SUFFIXES = frozenset({".java"})
PYTHON_SUFFIXES = frozenset({".py", ".pyi"})

_HUNK_HEADER = re.compile(
    r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(.*)$"
)

_FILE_STATUS_MAP = {
    "added": FileStatus.ADDED,
    "modified": FileStatus.MODIFIED,
    "removed": FileStatus.REMOVED,
    "renamed": FileStatus.RENAMED,
    "copied": FileStatus.COPIED,
    "changed": FileStatus.MODIFIED,
    "unchanged": FileStatus.UNKNOWN,
}

_NO_NEWLINE_MARKER = "\\"
_DIFF_HEADER_PREFIX = "diff --git "


def detect_language(path: str) -> Language:
    """Map a repository-relative file path to a supported language."""
    if not path:
        return Language.OTHER

    normalized = path.replace("\\", "/")
    dot_index = normalized.rfind(".")
    slash_index = normalized.rfind("/")
    if dot_index <= slash_index:
        return Language.OTHER

    suffix = normalized[dot_index:].lower()
    if suffix in JAVA_SUFFIXES:
        return Language.JAVA
    if suffix in PYTHON_SUFFIXES:
        return Language.PYTHON
    return Language.OTHER


def parse_file_status(status: str | FileStatus | None) -> FileStatus:
    """Normalize a GitHub file status into FileStatus.

    Unknown values map to UNKNOWN so callers can record a note instead of
    guessing a change type.
    """
    if isinstance(status, FileStatus):
        return status
    if not status:
        return FileStatus.UNKNOWN
    return _FILE_STATUS_MAP.get(status.strip().lower(), FileStatus.UNKNOWN)


def parse_hunks(patch: str) -> list[Hunk]:
    """Parse a unified diff patch into hunks with resolved line numbers.

    An omitted hunk count means 1, following the unified diff format.
    Lines that cannot be attributed to a hunk are ignored, and a hunk
    stops consuming input once it has read the number of lines declared
    in its header.
    """
    if not patch:
        return []

    lines = patch.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    hunks: list[Hunk] = []
    current: Hunk | None = None
    old_next = 0
    new_next = 0
    old_seen = 0
    new_seen = 0

    for raw_line in lines:
        match = _HUNK_HEADER.match(raw_line)
        if match:
            current = _hunk_from_match(match, raw_line)
            hunks.append(current)
            old_next = current.old_start
            new_next = current.new_start
            old_seen = 0
            new_seen = 0
            continue

        if current is None:
            continue

        if raw_line.startswith(_DIFF_HEADER_PREFIX):
            current = None
            continue

        if raw_line.startswith(_NO_NEWLINE_MARKER):
            continue

        if raw_line.startswith("+"):
            current.lines.append(
                DiffLine(
                    kind=DiffLineKind.ADDED,
                    text=raw_line[1:],
                    new_line_no=_line_no(new_next),
                )
            )
            new_next += 1
            new_seen += 1
        elif raw_line.startswith("-"):
            current.lines.append(
                DiffLine(
                    kind=DiffLineKind.REMOVED,
                    text=raw_line[1:],
                    old_line_no=_line_no(old_next),
                )
            )
            old_next += 1
            old_seen += 1
        elif raw_line.startswith(" ") or raw_line == "":
            current.lines.append(
                DiffLine(
                    kind=DiffLineKind.CONTEXT,
                    text=raw_line[1:] if raw_line else "",
                    old_line_no=_line_no(old_next),
                    new_line_no=_line_no(new_next),
                )
            )
            old_next += 1
            new_next += 1
            old_seen += 1
            new_seen += 1
        else:
            continue

        if old_seen >= current.old_count and new_seen >= current.new_count:
            current = None

    return hunks


def merge_changed_ranges(hunks: list[Hunk]) -> list[ChangedRange]:
    """Collapse hunk changes into sorted, merged new-side line ranges.

    Added lines contribute their own line numbers. Removed lines have no
    new-side position, so a removal-only block is anchored to the closest
    preceding new-side line. When a removal is immediately followed by
    additions it is a replacement, and only the added lines are reported.
    Overlapping and directly adjacent ranges are merged.
    """
    spans: list[tuple[int, int]] = []
    for hunk in hunks:
        spans.extend(_hunk_spans(hunk))
    return _merge_spans(spans)


def parse_patch(
    path: str,
    patch: str | None,
    status: str,
    previous_path: str | None = None,
) -> FileDiff:
    """Build a FileDiff from one GitHub changed-file entry.

    A missing patch is a normal case (binary file, pure rename, oversized
    diff) and produces an empty FileDiff with an explanatory note rather
    than an error.
    """
    file_status = parse_file_status(status)
    language = detect_language(path)
    notes: list[str] = []

    if file_status is FileStatus.UNKNOWN and status:
        notes.append(f"unrecognized file status: {status}")
    if file_status is FileStatus.RENAMED and not previous_path:
        notes.append("renamed file without previous path")

    if patch is None:
        notes.append("patch unavailable")
        return FileDiff(
            path=path,
            status=file_status,
            language=language,
            previous_path=previous_path,
            patch_available=False,
            notes=notes,
        )

    if not patch.strip():
        notes.append("patch is empty")
        return FileDiff(
            path=path,
            status=file_status,
            language=language,
            previous_path=previous_path,
            patch_available=False,
            notes=notes,
        )

    hunks = parse_hunks(patch)
    if not hunks:
        notes.append("patch contains no hunk header")

    changed_ranges = merge_changed_ranges(hunks)
    additions = _count_lines(hunks, DiffLineKind.ADDED)
    deletions = _count_lines(hunks, DiffLineKind.REMOVED)

    if hunks and additions == 0 and deletions == 0:
        notes.append("patch contains no changed line")
    if deletions > 0 and not changed_ranges:
        notes.append("removed lines have no new-side position")

    return FileDiff(
        path=path,
        status=file_status,
        language=language,
        previous_path=previous_path,
        additions=additions,
        deletions=deletions,
        hunks=hunks,
        changed_ranges=changed_ranges,
        patch_available=True,
        notes=notes,
    )


def _hunk_from_match(match: re.Match, raw_line: str) -> Hunk:
    return Hunk(
        header=raw_line.rstrip(),
        old_start=int(match.group(1)),
        old_count=int(match.group(2)) if match.group(2) is not None else 1,
        new_start=int(match.group(3)),
        new_count=int(match.group(4)) if match.group(4) is not None else 1,
    )


def _line_no(value: int) -> int | None:
    return value if value >= 1 else None


def _count_lines(hunks: list[Hunk], kind: DiffLineKind) -> int:
    return sum(
        1 for hunk in hunks for line in hunk.lines if line.kind is kind
    )


def _hunk_spans(hunk: Hunk) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    removal_anchor = _leading_removal_anchor(hunk)
    added_start: int | None = None
    added_end: int | None = None
    last_new: int | None = None
    pending_removal: int | None = None

    for line in hunk.lines:
        if line.kind is DiffLineKind.CONTEXT:
            if added_start is not None and added_end is not None:
                spans.append((added_start, added_end))
                added_start = None
                added_end = None
            if pending_removal is not None:
                spans.append((pending_removal, pending_removal))
                pending_removal = None
            if line.new_line_no is not None:
                last_new = line.new_line_no
            continue

        if line.kind is DiffLineKind.ADDED:
            if line.new_line_no is None:
                continue
            pending_removal = None
            if added_start is None:
                added_start = line.new_line_no
            added_end = line.new_line_no
            last_new = line.new_line_no
            continue

        if added_start is not None and added_end is not None:
            spans.append((added_start, added_end))
            added_start = None
            added_end = None
        if pending_removal is None:
            anchor = last_new if last_new is not None else removal_anchor
            if anchor is not None:
                pending_removal = anchor

    if added_start is not None and added_end is not None:
        spans.append((added_start, added_end))
    if pending_removal is not None:
        spans.append((pending_removal, pending_removal))

    return spans


def _leading_removal_anchor(hunk: Hunk) -> int | None:
    """New-side line a removal can be anchored to when none precedes it."""
    candidate = hunk.new_start - 1
    return candidate if candidate >= 1 else None


def _merge_spans(spans: list[tuple[int, int]]) -> list[ChangedRange]:
    valid = sorted(
        (start, end) for start, end in spans if start >= 1 and end >= start
    )
    merged: list[list[int]] = []
    for start, end in valid:
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    return [
        ChangedRange(start_line=start, end_line=end) for start, end in merged
    ]
