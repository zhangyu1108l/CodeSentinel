"""Tests for the safe temporary workspace materialization (Phase 8 prep)."""

import os
import shutil
from pathlib import Path

import pytest

from app.analyzers.workspace import MaterializedWorkspace


def create(files, parent):
    return MaterializedWorkspace.create(files, parent_dir=str(parent))


def visible_entries(directory: Path):
    return sorted(entry.name for entry in directory.iterdir())


UNSAFE_PATHS = [
    "/etc/passwd",
    "/root.py",
    "C:\\temp\\x.py",
    "C:relative.py",
    "\\\\server\\share\\x.py",
    "../x.py",
    "a/../../b.py",
    "a/./b.py",
    "a//b.py",
    "a/",
    "",
    "   ",
    " x.py ",
    "a\x00b.py",
    "CON",
    "con.txt",
    "NUL",
    "COM1",
    "LPT9.txt",
    "a./b.py",
    "a /b.py",
]


class TestCreate:
    def test_creates_nested_and_top_level_files(self, tmp_path):
        with create(
            {"main.py": "print(1)\n", "pkg/mod.py": "x = 1\n"}, tmp_path
        ) as workspace:
            root = Path(workspace.root)
            assert (
                root / "main.py"
            ).read_text(encoding="utf-8") == "print(1)\n"
            assert (
                root / "pkg" / "mod.py"
            ).read_text(encoding="utf-8") == "x = 1\n"

    def test_content_is_preserved_byte_for_byte(self, tmp_path):
        content = "line1\nline2\r\n\u4e2d\u6587 #\n"
        with create({"a.txt": content}, tmp_path) as workspace:
            data = (Path(workspace.root) / "a.txt").read_bytes()
        assert data == content.encode("utf-8")

    def test_allows_empty_content(self, tmp_path):
        with create({"empty.py": ""}, tmp_path) as workspace:
            target = Path(workspace.root) / "empty.py"
            assert target.exists()
            assert target.read_bytes() == b""

    def test_file_paths_normalizes_backslashes_and_keeps_order(
        self, tmp_path
    ):
        with create({"pkg\\mod.py": "", "main.py": ""}, tmp_path) as ws:
            assert ws.file_paths == ["pkg/mod.py", "main.py"]

    def test_file_paths_returns_a_copy(self, tmp_path):
        with create({"a.py": ""}, tmp_path) as workspace:
            paths = workspace.file_paths
            paths.append("injected.py")
            assert workspace.file_paths == ["a.py"]

    def test_root_is_inside_the_parent_directory(self, tmp_path):
        with create({}, tmp_path) as workspace:
            assert os.path.dirname(workspace.root) == os.path.realpath(
                str(tmp_path)
            )

    def test_each_workspace_gets_a_unique_root(self, tmp_path):
        first = create({}, tmp_path)
        second = create({}, tmp_path)
        try:
            assert first.root != second.root
        finally:
            first.close()
            second.close()

    def test_root_is_a_directory_while_open(self, tmp_path):
        with create({"a.py": ""}, tmp_path) as workspace:
            assert os.path.isdir(workspace.root)


class TestCleanup:
    def test_close_removes_the_directory(self, tmp_path):
        workspace = create({"a.py": "x"}, tmp_path)
        root = workspace.root
        assert os.path.isdir(root)
        workspace.close()
        assert not os.path.exists(root)

    def test_close_is_idempotent(self, tmp_path):
        workspace = create({"a.py": "x"}, tmp_path)
        root = workspace.root
        workspace.close()
        workspace.close()
        assert not os.path.exists(root)

    def test_context_manager_removes_the_directory_on_success(
        self, tmp_path
    ):
        with create({"a.py": "x"}, tmp_path) as workspace:
            root = workspace.root
        assert not os.path.exists(root)

    def test_context_manager_removes_the_directory_on_exception(
        self, tmp_path
    ):
        captured = {}
        with pytest.raises(RuntimeError, match="boom"):
            with create({"a.py": "x"}, tmp_path) as workspace:
                captured["root"] = workspace.root
                raise RuntimeError("boom")
        assert not os.path.exists(captured["root"])

    def test_context_manager_removes_the_directory_on_cancellation(
        self, tmp_path
    ):
        captured = {}
        with pytest.raises(KeyboardInterrupt):
            with create({"a.py": "x"}, tmp_path) as workspace:
                captured["root"] = workspace.root
                raise KeyboardInterrupt()
        assert not os.path.exists(captured["root"])

    def test_cleanup_failure_is_logged_and_not_raised(
        self, tmp_path, monkeypatch, caplog
    ):
        workspace = create({"a.py": "x"}, tmp_path)
        root = workspace.root
        original = shutil.rmtree

        def fail(path, *args, **kwargs):
            raise OSError("locked")

        monkeypatch.setattr(shutil, "rmtree", fail)
        try:
            with caplog.at_level(
                "WARNING", logger="codesentinel-ai.analyzer_workspace"
            ):
                workspace.close()
        finally:
            monkeypatch.undo()
            original(root, ignore_errors=True)
        assert any(
            "Failed to remove" in record.getMessage()
            for record in caplog.records
        )
        assert not os.path.exists(root)

    def test_failed_write_cleans_up_and_reraises(
        self, tmp_path, monkeypatch
    ):
        def boom(self):
            raise RuntimeError("write failed")

        monkeypatch.setattr(MaterializedWorkspace, "_write_files", boom)
        with pytest.raises(RuntimeError, match="write failed"):
            create({"a.py": "x"}, tmp_path)
        assert visible_entries(tmp_path) == []

    def test_conflicting_file_and_directory_layout_fails_and_cleans(
        self, tmp_path
    ):
        with pytest.raises(OSError):
            create({"a": "", "a/b.py": ""}, tmp_path)
        assert visible_entries(tmp_path) == []


class TestPathRejection:
    @pytest.mark.parametrize("path", UNSAFE_PATHS)
    def test_rejects_unsafe_paths_without_creating_anything(
        self, tmp_path, path
    ):
        with pytest.raises(ValueError):
            create({path: "x"}, tmp_path)
        assert visible_entries(tmp_path) == []

    @pytest.mark.parametrize("path", [None, 123, b"a.py"])
    def test_rejects_non_string_paths(self, tmp_path, path):
        with pytest.raises(ValueError):
            create({path: "x"}, tmp_path)

    @pytest.mark.parametrize("content", [None, 123, b"data", ["x"]])
    def test_rejects_non_string_content(self, tmp_path, content):
        with pytest.raises(ValueError):
            create({"a.py": content}, tmp_path)

    @pytest.mark.parametrize("files", [None, "a.py", ["a.py"], b"x", 42])
    def test_rejects_non_mapping_files(self, tmp_path, files):
        with pytest.raises(ValueError):
            MaterializedWorkspace.create(
                files, parent_dir=str(tmp_path)
            )

    def test_rejects_duplicates_after_normalization(self, tmp_path):
        with pytest.raises(ValueError, match="duplicate"):
            create({"a/b.py": "1", "a\\b.py": "2"}, tmp_path)
        assert visible_entries(tmp_path) == []

    @pytest.mark.skipif(
        os.name != "nt", reason="case folding is Windows specific"
    )
    def test_rejects_case_colliding_paths_on_windows(self, tmp_path):
        with pytest.raises(ValueError, match="duplicate"):
            create({"A.py": "1", "a.py": "2"}, tmp_path)

    def test_rejects_missing_parent_directory(self, tmp_path):
        with pytest.raises(ValueError, match="parent_dir"):
            MaterializedWorkspace.create(
                {"a.py": ""}, parent_dir=str(tmp_path / "missing")
            )

    def test_rejects_blank_parent_directory(self, tmp_path):
        with pytest.raises(ValueError, match="parent_dir"):
            MaterializedWorkspace.create(
                {"a.py": ""}, parent_dir="   "
            )


class TestContainment:
    def test_every_file_resolves_inside_the_root(self, tmp_path):
        with create({"a.py": "", "pkg/deep/b.py": ""}, tmp_path) as ws:
            for name in ws.file_paths:
                resolved = os.path.realpath(
                    os.path.join(ws.root, *name.split("/"))
                )
                common = os.path.commonpath([ws.root, resolved])
                assert os.path.normcase(common) == os.path.normcase(
                    ws.root
                )

    def test_only_the_workspace_entry_is_created_in_parent(
        self, tmp_path
    ):
        work = tmp_path / "work"
        work.mkdir()
        with create({"a.py": ""}, work) as workspace:
            entries = list(work.iterdir())
            assert len(entries) == 1
            assert os.path.realpath(
                str(entries[0])
            ) == workspace.root