"""Tests for the shared adapter path guard (Phase 7.5.1).

Pure filesystem fixtures only: no external tool, no network.
"""

import os
import subprocess

import pytest

from app.analyzers.path_guard import (
    is_within,
    map_output_path,
    normalize_output_path,
    validate_repo_dir,
    validate_targets,
)

PY_SUFFIXES = (".py", ".pyi")


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    return repo


def write_file(root, name, content="x = 1\n"):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def make_symlink_or_skip(link, target):
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this system")


def make_dir_link_or_skip(link, target):
    """Create a directory link: symlink, or a Windows junction fallback."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
        )
        if result.returncode == 0:
            return
    pytest.skip("directory link creation not permitted on this system")


class TestValidateRepoDir:
    def test_existing_directory_returns_realpath(self, tmp_path):
        repo = make_repo(tmp_path)
        assert validate_repo_dir(str(repo)) == os.path.realpath(
            str(repo)
        )

    @pytest.mark.parametrize("value", ["", "   ", None, 42])
    def test_blank_or_non_string_rejected(self, value):
        with pytest.raises(ValueError):
            validate_repo_dir(value)

    def test_missing_directory_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            validate_repo_dir(str(tmp_path / "missing"))

    def test_file_rejected(self, tmp_path):
        path = tmp_path / "file.txt"
        path.write_text("x", encoding="utf-8")
        with pytest.raises(ValueError):
            validate_repo_dir(str(path))


class TestValidateTargetsSuffixPolicy:
    def test_python_files_accepted(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "pkg/mod.py")
        write_file(repo, "pkg/stub.pyi")
        root = validate_repo_dir(str(repo))
        targets = validate_targets(
            root, ["pkg/mod.py", "pkg/stub.pyi"], suffixes=PY_SUFFIXES
        )
        assert targets == ["pkg/mod.py", "pkg/stub.pyi"]

    def test_non_python_rejected_with_suffix_policy(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "src/Main.java")
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(root, ["src/Main.java"], suffixes=PY_SUFFIXES)

    def test_uppercase_suffix_rejected_with_policy(self, tmp_path):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(root, ["mod.PY"], suffixes=PY_SUFFIXES)

    @pytest.mark.parametrize(
        "name", ["src/Main.java", "web/app.js", "svc/main.go", "doc.md"]
    )
    def test_any_suffix_accepted_without_policy(self, tmp_path, name):
        repo = make_repo(tmp_path)
        write_file(repo, name)
        root = validate_repo_dir(str(repo))
        assert validate_targets(root, [name]) == [name]

    def test_suffix_policy_checked_before_existence(self, tmp_path):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(
                root, ["missing.java"], suffixes=PY_SUFFIXES
            )


class TestValidateTargetsInput:
    def test_empty_list_rejected(self, tmp_path):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(root, [])

    @pytest.mark.parametrize("value", ["pkg/mod.py", b"pkg/mod.py", None])
    def test_string_like_container_rejected(self, tmp_path, value):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(root, value)

    def test_non_string_item_rejected(self, tmp_path):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(root, [42])

    @pytest.mark.parametrize("value", ["", " ", "  \t "])
    def test_blank_item_rejected(self, tmp_path, value):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(root, [value])

    @pytest.mark.parametrize(
        "value", [" pkg/mod.py", "pkg/mod.py "]
    )
    def test_padded_item_rejected(self, tmp_path, value):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(root, [value])

    def test_nul_rejected(self, tmp_path):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(root, ["pkg/mod\x00.py"])

    @pytest.mark.parametrize(
        "value",
        [
            "/etc/passwd",
            "C:/repo/mod.py",
            "c:mod.py",
            "\\\\server\\share\\mod.py",
        ],
    )
    def test_absolute_drive_and_unc_rejected(self, tmp_path, value):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(root, [value])

    @pytest.mark.parametrize(
        "value",
        [
            "../outside.py",
            "pkg/../../outside.py",
            "..\\outside.py",
            "pkg/./mod.py",
            "pkg//mod.py",
            "pkg/mod.py/",
            ".",
            "..",
        ],
    )
    def test_traversal_and_malformed_segments_rejected(
        self, tmp_path, value
    ):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(root, [value])

    def test_missing_file_rejected(self, tmp_path):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(root, ["pkg/missing.py"])

    def test_backslash_relative_normalized(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "pkg/mod.py")
        root = validate_repo_dir(str(repo))
        assert validate_targets(root, ["pkg\\mod.py"]) == ["pkg/mod.py"]

    def test_duplicates_deduplicated_and_order_kept(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "a.py")
        write_file(repo, "pkg/mod.py")
        root = validate_repo_dir(str(repo))
        targets = validate_targets(
            root,
            ["pkg\\mod.py", "a.py", "pkg/mod.py", "a.py"],
        )
        assert targets == ["pkg/mod.py", "a.py"]


class TestSymlinkEscape:
    def test_file_symlink_outside_rejected(self, tmp_path):
        repo = make_repo(tmp_path)
        outside = tmp_path / "outside.py"
        outside.write_text("x = 1\n", encoding="utf-8")
        make_symlink_or_skip(repo / "link.py", outside)
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(root, ["link.py"], suffixes=PY_SUFFIXES)

    def test_directory_symlink_outside_rejected(self, tmp_path):
        repo = make_repo(tmp_path)
        outside = tmp_path / "outside"
        outside.mkdir()
        write_file(outside, "evil.py")
        make_dir_link_or_skip(repo / "link", outside)
        root = validate_repo_dir(str(repo))
        with pytest.raises(ValueError):
            validate_targets(
                root, ["link/evil.py"], suffixes=PY_SUFFIXES
            )

    def test_symlink_inside_repo_accepted(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "pkg/mod.py")
        make_symlink_or_skip(repo / "alias.py", repo / "pkg" / "mod.py")
        root = validate_repo_dir(str(repo))
        assert validate_targets(
            root, ["alias.py"], suffixes=PY_SUFFIXES
        ) == ["alias.py"]

    def test_relative_symlink_output_not_mapped(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "pkg/mod.py")
        make_dir_link_or_skip(repo / "link", repo / "pkg")
        root = validate_repo_dir(str(repo))
        assert map_output_path("link/mod.py", root, {"pkg/mod.py"}) is None

    def test_absolute_symlink_output_folds_to_target(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "pkg/mod.py")
        make_dir_link_or_skip(repo / "link", repo / "pkg")
        root = validate_repo_dir(str(repo))
        output = os.path.join(str(repo), "link", "mod.py")
        assert (
            map_output_path(output, root, {"pkg/mod.py"})
            == "pkg/mod.py"
        )


class TestNormalizeOutputPath:
    def test_relative_path_kept(self, tmp_path):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        assert (
            normalize_output_path("pkg/mod.py", root) == "pkg/mod.py"
        )

    def test_nested_relative_path_kept(self, tmp_path):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        assert (
            normalize_output_path("a/b/c/d.py", root) == "a/b/c/d.py"
        )

    def test_backslash_normalized(self, tmp_path):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        assert (
            normalize_output_path("a\\b\\c.py", root) == "a/b/c.py"
        )

    def test_dot_slash_prefix_stripped(self, tmp_path):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        assert (
            normalize_output_path("./pkg/mod.py", root) == "pkg/mod.py"
        )
        assert (
            normalize_output_path("././pkg/mod.py", root)
            == "pkg/mod.py"
        )

    def test_absolute_inside_repo_folded(self, tmp_path):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        absolute = os.path.join(str(repo), "pkg", "mod.py")
        assert normalize_output_path(absolute, root) == "pkg/mod.py"

    def test_absolute_outside_repo_none(self, tmp_path):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        outside = os.path.join(str(tmp_path), "outside.py")
        assert normalize_output_path(outside, root) is None

    @pytest.mark.parametrize(
        "value",
        [
            "../outside.py",
            "pkg/../../outside.py",
            "..\\outside.py",
            "pkg/./mod.py",
            "pkg//mod.py",
            ".",
            "..",
            "C:/repo/mod.py",
            "\\\\server\\share\\mod.py",
        ],
    )
    def test_escaping_or_malformed_none(self, tmp_path, value):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        assert normalize_output_path(value, root) is None

    @pytest.mark.parametrize("value", ["", " ", None, 42])
    def test_blank_or_non_string_none(self, tmp_path, value):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        assert normalize_output_path(value, root) is None


class TestMapOutputPath:
    def test_exact_target_returned(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "pkg/mod.py")
        root = validate_repo_dir(str(repo))
        assert (
            map_output_path("pkg/mod.py", root, {"pkg/mod.py"})
            == "pkg/mod.py"
        )

    def test_backslash_output_mapped(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "pkg/mod.py")
        root = validate_repo_dir(str(repo))
        assert (
            map_output_path("pkg\\mod.py", root, ["pkg/mod.py"])
            == "pkg/mod.py"
        )

    def test_absolute_inside_mapped(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "pkg/mod.py")
        root = validate_repo_dir(str(repo))
        output = os.path.join(str(repo), "pkg", "mod.py")
        assert (
            map_output_path(output, root, {"pkg/mod.py"})
            == "pkg/mod.py"
        )

    def test_unrequested_file_not_mapped(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "other.py")
        root = validate_repo_dir(str(repo))
        assert map_output_path("other.py", root, {"pkg/mod.py"}) is None

    def test_traversal_never_mapped(self, tmp_path):
        repo = make_repo(tmp_path)
        root = validate_repo_dir(str(repo))
        assert (
            map_output_path("../mod.py", root, {"pkg/mod.py"}) is None
        )

    def test_case_different_not_mapped_without_fold(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "pkg/mod.py")
        root = validate_repo_dir(str(repo))
        assert (
            map_output_path("PKG/MOD.py", root, {"pkg/mod.py"}) is None
        )

    def test_fold_case_exact_match(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "pkg/mod.py")
        root = validate_repo_dir(str(repo))
        assert (
            map_output_path(
                "pkg/mod.py", root, ["pkg/mod.py"], fold_case=True
            )
            == "pkg/mod.py"
        )

    @pytest.mark.skipif(
        os.name != "nt", reason="case folding is Windows specific"
    )
    def test_fold_case_returns_canonical_spelling(self, tmp_path):
        repo = make_repo(tmp_path)
        write_file(repo, "pkg/mod.py")
        root = validate_repo_dir(str(repo))
        assert (
            map_output_path(
                "PKG/MOD.py", root, ["pkg/mod.py"], fold_case=True
            )
            == "pkg/mod.py"
        )


class TestIsWithin:
    def test_child_is_within(self, tmp_path):
        root = make_repo(tmp_path)
        assert is_within(str(root), str(root / "pkg" / "mod.py"))

    def test_same_path_is_within(self, tmp_path):
        root = make_repo(tmp_path)
        assert is_within(str(root), str(root))

    def test_sibling_not_within(self, tmp_path):
        root = make_repo(tmp_path)
        assert not is_within(str(root), str(tmp_path / "other.py"))

    def test_prefix_similar_sibling_not_within(self, tmp_path):
        root = make_repo(tmp_path)
        sibling = tmp_path / "repository" / "x.py"
        assert not is_within(str(root), str(sibling))

    @pytest.mark.skipif(
        os.name != "nt", reason="drive semantics are Windows specific"
    )
    def test_different_drive_not_within(self, tmp_path):
        root = make_repo(tmp_path)
        assert not is_within(str(root), "D:\\codesentinel-other\\x.py")