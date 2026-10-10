"""Shared path guard for the static analysis adapters (Phase 7.5.1).

Centralizes the path validation and normalization rules that Ruff,
Bandit and Semgrep previously duplicated (or imported across adapter
modules) so all three enforce identical safety semantics:

- validate_repo_dir returns the real path of an existing repository
  directory, so the boundary is resolved before any target is checked.
- validate_targets accepts only repository relative, existing regular
  files: no absolute path, drive letter, UNC share, traversal, dot or
  empty segment, NUL or surrounding whitespace. An optional suffix policy
  keeps Ruff and Bandit on .py/.pyi while Semgrep stays language
  agnostic. Duplicates are removed and input order is preserved.
- normalize_output_path folds a tool reported path to repository relative
  posix; absolute paths inside the repository are accepted, everything
  escaping or blank becomes None.
- map_output_path requires a normalized tool path to match a requested
  target. fold_case compares with os.path.normcase (case insensitive
  filesystems) and returns the canonical target spelling; matching is
  exact otherwise.
- is_within decides containment with os.path.commonpath instead of
  string prefixes, so '/a/repo' never contains '/a/repository' and
  different drives are never contained.

Every containment decision resolves symlinks through os.path.realpath,
so a link inside the repository cannot expose a file outside it. The
module performs no IO beyond stat/realpath lookups and never logs.
"""

import os
from collections.abc import Iterable, Sequence


def validate_repo_dir(repo_dir: str) -> str:
    """Return the real path of an existing repository directory."""
    if not isinstance(repo_dir, str) or not repo_dir.strip():
        raise ValueError("repo_dir must be a non-empty path")
    root = os.path.realpath(repo_dir)
    if not os.path.isdir(root):
        raise ValueError("repo_dir must be an existing directory")
    return root


def validate_targets(
    root: str,
    file_paths: Sequence[str],
    suffixes: Sequence[str] | None = None,
) -> list[str]:
    """Return validated repository relative targets in input order.

    suffixes restricts the allowed file suffixes when given (Ruff and
    Bandit pass .py/.pyi, Semgrep passes nothing). An empty result or a
    string/bytes file_paths value is rejected.
    """
    if file_paths is None or isinstance(file_paths, (str, bytes)):
        raise ValueError(
            "file_paths must be a sequence of paths, not a string"
        )
    targets: list[str] = []
    seen: set[str] = set()
    for path in file_paths:
        normalized = _validate_target(root, path, suffixes)
        if normalized in seen:
            continue
        seen.add(normalized)
        targets.append(normalized)
    if not targets:
        raise ValueError("at least one target file is required")
    return targets


def normalize_output_path(path: str, repo_dir: str) -> str | None:
    """Fold a tool reported path to repository relative posix or None.

    Absolute paths inside the repository are folded in; traversal, blank
    and outside paths return None.
    """
    if not isinstance(path, str) or not path.strip():
        return None
    candidate = path.replace("\\", "/")
    if _is_absolute(candidate):
        try:
            candidate = os.path.relpath(
                os.path.realpath(path), repo_dir
            )
        except (OSError, ValueError):
            return None
        candidate = candidate.replace("\\", "/")
    while candidate.startswith("./"):
        candidate = candidate[2:]
    if not candidate:
        return None
    if any(part in ("", ".", "..") for part in candidate.split("/")):
        return None
    return candidate


def map_output_path(
    path: str,
    repo_dir: str,
    allowed: Iterable[str],
    fold_case: bool = False,
) -> str | None:
    """Map a tool reported path onto a requested target or None.

    fold_case compares with os.path.normcase, matching case insensitive
    filesystems and returning the canonical target spelling; matching is
    exact otherwise.
    """
    normalized = normalize_output_path(path, repo_dir)
    if normalized is None:
        return None
    if not fold_case:
        return normalized if normalized in allowed else None
    canonical = {os.path.normcase(item): item for item in allowed}
    return canonical.get(os.path.normcase(normalized))


def is_within(root: str, resolved: str) -> bool:
    """Whether resolved is root itself or lies below it."""
    try:
        common = os.path.commonpath([root, resolved])
    except ValueError:
        return False
    return os.path.normcase(common) == os.path.normcase(root)


def _validate_target(
    root: str, path: str, suffixes: Sequence[str] | None
) -> str:
    if (
        not isinstance(path, str)
        or not path.strip()
        or path != path.strip()
    ):
        raise ValueError("target path must be a non-empty relative path")
    if "\x00" in path:
        raise ValueError("target path must not contain NUL")
    normalized = path.replace("\\", "/")
    if _is_absolute(normalized):
        raise ValueError("target path must be repository relative")
    parts = normalized.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(
            "target path must not contain empty, dot or traversal "
            "segments"
        )
    if suffixes is not None and not normalized.endswith(tuple(suffixes)):
        raise ValueError("target file suffix is not allowed")
    resolved = os.path.realpath(os.path.join(root, *parts))
    if not is_within(root, resolved):
        raise ValueError("target path escapes the repository directory")
    if not os.path.isfile(resolved):
        raise ValueError("target file does not exist")
    return normalized


def _is_absolute(path: str) -> bool:
    if path.startswith("/") or os.path.isabs(path):
        return True
    return (
        len(path) >= 2 and path[1] == ":" and path[0].isalpha()
    )