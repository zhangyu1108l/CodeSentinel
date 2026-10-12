"""Safe temporary workspace materialization for static analysis (Phase 8 prep).

Writes caller supplied file contents (for example the changed files that
were already fetched for one pull request) into a fresh, private temporary
directory, so the Phase 7 static analysis adapters can run on a real
directory tree without cloning, fetching or executing anything.

Security boundaries:

- The workspace root is created with tempfile.mkdtemp under the system
  temporary directory (or an explicitly supplied parent directory). A
  unique new directory is always created, so existing user files are
  never overwritten, and cleanup removes exactly that created directory.
- Every target path is validated before anything is written: only
  repository relative posix paths survive, with no absolute path, drive
  letter, UNC prefix, NUL, surrounding whitespace, traversal, dot or empty
  segment. Segments ending in a space or dot and Windows reserved device
  names are rejected too, so behavior stays deterministic across
  platforms. Paths that collide after normalization (including Windows
  case folding) are rejected instead of silently overwriting each other.
- Containment is enforced with the shared Phase 7.5.1 path guard
  (os.path.realpath plus os.path.commonpath inside is_within), never with
  string prefixes.
- Contents are written as UTF-8 with newline="" so they are stored byte
  for byte; they are inert data and are never executed.
- Cleanup runs on normal exit, on exception and on cancellation, and a
  cleanup failure is logged without replacing the caller's exception.

Deliberately not implemented here:

- No git clone, fetch, diff download, HTTP request or any other source
  retrieval. Callers can only materialize content they already hold.
- No execution of workspace files and no tool invocation; the scheduler
  runs analyzers on top of a materialized workspace.
"""

import logging
import os
import re
import shutil
import tempfile
from collections.abc import Mapping

from app.analyzers.path_guard import is_within

logger = logging.getLogger("codesentinel-ai.analyzer_workspace")

_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_TEMP_PREFIX = "codesentinel-analysis-"
_RESERVED_WINDOWS_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


class MaterializedWorkspace:
    """A temporary directory holding exactly the supplied files.

    Create instances with MaterializedWorkspace.create(...) and prefer the
    context manager form, which removes the workspace on success, on
    exception and on cancellation:

        with MaterializedWorkspace.create(files) as workspace:
            scheduler.run(workspace.root, workspace.file_paths)

    close() is idempotent and best effort: a failure to remove the
    directory is logged, never raised.
    """

    def __init__(self, root: str, files: Mapping[str, str]):
        self.root = root
        self._files = dict(files)
        self._closed = False

    @classmethod
    def create(
        cls,
        files: Mapping[str, str],
        parent_dir: str | None = None,
    ) -> "MaterializedWorkspace":
        """Materialize files into a new temporary directory.

        files maps repository relative paths to their full text content;
        an empty mapping produces an empty workspace. All paths and
        contents are validated before the directory is created, so invalid
        input never leaves a partial directory behind.
        """
        if not isinstance(files, Mapping):
            raise ValueError(
                "files must be a mapping of relative path to content"
            )
        parent = _validate_parent_dir(parent_dir)

        normalized: dict[str, str] = {}
        seen: set[str] = set()
        for path, content in files.items():
            relative = _validate_workspace_path(path)
            if not isinstance(content, str):
                raise ValueError(
                    "file content must be a string: " + relative
                )
            folded = os.path.normcase(relative)
            if folded in seen:
                raise ValueError(
                    "duplicate file path after normalization: " + relative
                )
            seen.add(folded)
            normalized[relative] = content

        root = os.path.realpath(
            tempfile.mkdtemp(prefix=_TEMP_PREFIX, dir=parent)
        )
        workspace = cls(root, normalized)
        try:
            workspace._write_files()
        except BaseException:
            _remove_tree(root)
            raise
        logger.debug(
            "Materialized %d file(s) into an analysis workspace",
            len(normalized),
        )
        return workspace

    @property
    def file_paths(self) -> list[str]:
        """Normalized repository relative paths, in input order."""
        return list(self._files.keys())

    def close(self) -> None:
        """Remove the workspace directory (idempotent, best effort)."""
        if self._closed:
            return
        self._closed = True
        _remove_tree(self.root)

    def __enter__(self) -> "MaterializedWorkspace":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _write_files(self) -> None:
        for relative, content in self._files.items():
            parts = relative.split("/")
            resolved = os.path.realpath(
                os.path.join(self.root, *parts)
            )
            if not is_within(self.root, resolved):
                raise ValueError(
                    "file path escapes the workspace: " + relative
                )
            parent = os.path.dirname(resolved)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(
                resolved, "w", encoding="utf-8", newline=""
            ) as handle:
                handle.write(content)


def _validate_parent_dir(parent_dir: str | None) -> str | None:
    if parent_dir is None:
        return None
    if (
        not isinstance(parent_dir, str)
        or not parent_dir.strip()
        or parent_dir != parent_dir.strip()
    ):
        raise ValueError("parent_dir must be a non-empty path")
    if "\x00" in parent_dir:
        raise ValueError("parent_dir must not contain NUL")
    if not os.path.isdir(parent_dir):
        raise ValueError("parent_dir must be an existing directory")
    return parent_dir


def _validate_workspace_path(path: str) -> str:
    """Validate a not-yet-existing workspace path and normalize it.

    The shape rules mirror the shared path guard; existence and suffix
    checks do not apply because the file is created here. Windows device
    names and segments with trailing spaces or dots are rejected on every
    platform so the accepted set does not depend on the host OS.
    """
    if not isinstance(path, str):
        raise ValueError("file path must be a string")
    if not path or not path.strip() or path != path.strip():
        raise ValueError("file path must be a non-empty relative path")
    if "\x00" in path:
        raise ValueError("file path must not contain NUL")
    normalized = path.replace("\\", "/")
    if normalized.startswith("/") or _DRIVE_PREFIX.match(normalized):
        raise ValueError("file path must be repository relative")
    parts = normalized.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(
            "file path must not contain empty, dot or traversal segments"
        )
    for part in parts:
        if part.rstrip(" .") != part:
            raise ValueError(
                "file path segments must not end with a space or dot"
            )
        if _is_reserved_windows_name(part):
            raise ValueError(
                "file path must not use a reserved device name"
            )
    return normalized


def _is_reserved_windows_name(segment: str) -> bool:
    stem = segment.split(".", 1)[0].rstrip(" .")
    return stem.upper() in _RESERVED_WINDOWS_NAMES


def _remove_tree(root: str) -> None:
    if not root:
        return
    try:
        shutil.rmtree(root)
    except FileNotFoundError:
        return
    except OSError:
        logger.warning(
            "Failed to remove analysis workspace directory: %s", root
        )