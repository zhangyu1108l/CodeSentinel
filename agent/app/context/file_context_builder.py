"""File Context building (Phase 6.2).

Associates each parsed FileDiff with the full source of that file at the
reviewed revision and records why a file could not be associated. Pure
functions with no IO: callers fetch content elsewhere and pass it in, so
a missing or unreadable file degrades into notes instead of raising and
never stops the rest of the context from being built.

Line numbers follow the Git line model (LF terminated, a missing final
newline does not add a line) so they stay aligned with the diff line
numbers produced by diff_parser. Content is untrusted user source code
and must never be written to logs.
"""

from collections.abc import Mapping

from app.schemas.code_context import (
    FileContent,
    FileContext,
    FileDiff,
    FileStatus,
)

SKIP_CONTENT_UNAVAILABLE = "file content unavailable"
SKIP_FILE_REMOVED = "file removed at head revision"
SKIP_BINARY_CONTENT = "binary content"
SKIP_PATH_MISMATCH = "content path mismatch"

NOTE_NO_CONTENT = "no content provided"
NOTE_CONTENT_IGNORED_FOR_REMOVED = "content ignored for removed file"
NOTE_BINARY_CONTENT = "content contains a NUL byte"
NOTE_REVISION_MISMATCH = "content revision mismatch"
NOTE_RANGE_BEYOND_FILE_LENGTH = (
    "changed range beyond file length (possible revision mismatch)"
)
NOTE_LINE_COUNT_BELOW_ADDITIONS = (
    "file has fewer lines than added lines (possible revision mismatch)"
)

_NUL = "\x00"


def split_lines(content: str) -> list[str]:
    """Split source text into lines using the Git line model.

    CRLF and lone CR are normalized to LF first. A single trailing empty
    element caused by a final newline is dropped, and no other character
    is treated as a line break.
    """
    if content == "":
        return []

    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines[-1] == "":
        lines.pop()
    return lines


def count_lines(content: str) -> int:
    """Total number of lines of a file, matching diff line numbering."""
    return len(split_lines(content))


def build_file_context(
    file_diff: FileDiff,
    content: FileContent | None = None,
    expected_revision: str | None = None,
) -> FileContext:
    """Combine one FileDiff with its full source into a FileContext.

    The content is only accepted when its path equals the new-side path of
    the diff, which prevents attaching the source of another file. Removed
    files never carry content because they do not exist at the head
    revision; the diff alone stays available for review.
    """
    notes: list[str] = list(file_diff.notes)

    if file_diff.status is FileStatus.REMOVED:
        if content is not None:
            if content.content is not None:
                notes.append(NOTE_CONTENT_IGNORED_FOR_REMOVED)
            elif content.error:
                notes.append(content.error)
        return FileContext(
            file_diff=file_diff,
            content=None,
            line_count=0,
            content_available=False,
            skipped_reason=SKIP_FILE_REMOVED,
            notes=notes,
        )

    if content is None:
        notes.append(NOTE_NO_CONTENT)
        return FileContext(
            file_diff=file_diff,
            content=None,
            line_count=0,
            content_available=False,
            skipped_reason=SKIP_CONTENT_UNAVAILABLE,
            notes=notes,
        )

    if content.path != file_diff.path:
        notes.append(f"{SKIP_PATH_MISMATCH}: {content.path}")
        return FileContext(
            file_diff=file_diff,
            content=None,
            line_count=0,
            content_available=False,
            skipped_reason=SKIP_PATH_MISMATCH,
            notes=notes,
        )

    if content.content is None:
        notes.append(content.error or NOTE_NO_CONTENT)
        return FileContext(
            file_diff=file_diff,
            content=content,
            line_count=0,
            content_available=False,
            skipped_reason=SKIP_CONTENT_UNAVAILABLE,
            notes=notes,
        )

    if _NUL in content.content:
        notes.append(NOTE_BINARY_CONTENT)
        return FileContext(
            file_diff=file_diff,
            content=content,
            line_count=0,
            content_available=False,
            skipped_reason=SKIP_BINARY_CONTENT,
            notes=notes,
        )

    if (
        expected_revision
        and content.revision
        and content.revision != expected_revision
    ):
        notes.append(NOTE_REVISION_MISMATCH)

    line_count = count_lines(content.content)

    last_changed_line = max(
        (changed.end_line for changed in file_diff.changed_ranges), default=0
    )
    if last_changed_line > line_count:
        notes.append(NOTE_RANGE_BEYOND_FILE_LENGTH)

    if (
        file_diff.status is FileStatus.ADDED
        and line_count < file_diff.additions
    ):
        notes.append(NOTE_LINE_COUNT_BELOW_ADDITIONS)

    return FileContext(
        file_diff=file_diff,
        content=content,
        line_count=line_count,
        content_available=True,
        skipped_reason=None,
        notes=notes,
    )


def build_file_contexts(
    file_diffs: list[FileDiff],
    contents: Mapping[str, FileContent] | None = None,
    expected_revision: str | None = None,
) -> list[FileContext]:
    """Build one FileContext per FileDiff, keyed by new-side path.

    Order matches file_diffs. Contents without a matching diff are
    ignored; a diff without content degrades to a content-less
    FileContext instead of failing the whole batch.
    """
    lookup: Mapping[str, FileContent] = contents or {}
    return [
        build_file_context(
            file_diff, lookup.get(file_diff.path), expected_revision
        )
        for file_diff in file_diffs
    ]
