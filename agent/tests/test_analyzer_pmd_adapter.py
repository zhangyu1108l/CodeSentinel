"""Tests for the Phase 7.6 PMD adapter (Phase 7.6.1 java launcher).

A fake executor is injected everywhere: PMD is never installed, started or
needed. All payloads are synthetic, shaped after the PMD 7 JSON renderer
(source: pmd-core JsonRenderer, FORMAT_VERSION 0). The adapter launches
PMD through java directly (never pmd.bat), and the launcher is resolved
and validated so a same-named batch file cannot bypass the check.
"""

import json
import os
import shutil
import sys

import pytest

from app.analyzers import pmd_adapter
from app.analyzers.execution import (
    CommandExecutionRequest,
    CommandExecutionResult,
    ExecutionStatus,
    SubprocessExecutor,
)
from app.analyzers.pmd_adapter import PMDAdapter
from app.analyzers.tool_runner import ToolRunner
from app.schemas.review import Category, Severity
from app.schemas.static_analysis import (
    StaticAnalysisErrorCode,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)

_MISSING = object()

_BUILTIN_RULESET = "category/java/bestpractices.xml"

_HOSTILE_NAMES = (
    "a&b.java",
    "a%TEMP%b.java",
    "a!b.java",
    "a^b.java",
    "(x).java",
    "a b.java",
)


def completed(stdout="[]", exit_code=0, **overrides):
    data = {
        "status": ExecutionStatus.COMPLETED,
        "exit_code": exit_code,
        "stdout": stdout,
        "duration_ms": 12,
    }
    data.update(overrides)
    return CommandExecutionResult(**data)


class FakeExecutor:
    def __init__(self, result=None):
        self.requests = []
        self.result = result if result is not None else completed()

    def execute(self, request):
        self.requests.append(request)
        return self.result


def violation(
    beginline=1,
    endline=_MISSING,
    description="Unused local variable 'value'",
    rule="UnusedLocalVariable",
    ruleset="Best Practices",
    priority=3,
):
    entry = {
        "beginline": beginline,
        "begincolumn": 9,
        "endcolumn": 20,
        "description": description,
        "rule": rule,
        "priority": priority,
        "externalInfoUrl": "https://docs.pmd-code.org/latest/",
    }
    if endline is _MISSING:
        entry["endline"] = beginline
    elif endline is not None:
        entry["endline"] = endline
    if ruleset is not None:
        entry["ruleset"] = ruleset
    return entry


def pmd_file(filename="src/Main.java", *violations):
    return {"filename": filename, "violations": list(violations)}


def report(
    *file_entries,
    processing_errors=None,
    configuration_errors=None,
    suppressed=None,
):
    return json.dumps(
        {
            "formatVersion": 0,
            "pmdVersion": "7.28.0",
            "timestamp": "2026-10-10T00:00:00.000+00:00",
            "files": list(file_entries),
            "suppressedViolations": (
                list(suppressed) if suppressed is not None else []
            ),
            "processingErrors": (
                list(processing_errors)
                if processing_errors is not None
                else []
            ),
            "configurationErrors": (
                list(configuration_errors)
                if configuration_errors is not None
                else []
            ),
        }
    )


def write_file(root, name, content="class Main {}\n"):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def make_env(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    ruleset = tmp_path / "trusted_ruleset.xml"
    ruleset.write_text("<ruleset/>\n", encoding="utf-8")
    return repo, ruleset


def make_pmd_home(tmp_path, name="pmd"):
    home = tmp_path / name
    (home / "conf").mkdir(parents=True, exist_ok=True)
    lib = home / "lib"
    lib.mkdir(exist_ok=True)
    (lib / "pmd-cli-7.28.0.jar").write_bytes(b"")
    return home


def java_launcher():
    return os.path.realpath(sys.executable)


def classpath_for(home):
    resolved = os.path.realpath(str(home))
    return os.pathsep.join(
        [
            os.path.join(resolved, "conf"),
            os.path.join(resolved, "lib", "*"),
        ]
    )


def make_adapter(
    tmp_path,
    references,
    pmd_home=None,
    java_executable=_MISSING,
):
    home = pmd_home if pmd_home is not None else make_pmd_home(tmp_path)
    executor = FakeExecutor()
    adapter = PMDAdapter(
        ToolRunner(executor=executor),
        references,
        str(home),
        java_executable=(
            sys.executable
            if java_executable is _MISSING
            else java_executable
        ),
    )
    return adapter, executor


def build(tmp_path, files=("src/Main.java",), rulesets=None, pmd_home=None):
    repo, ruleset = make_env(tmp_path)
    for name in files:
        write_file(repo, name)
    home = pmd_home if pmd_home is not None else make_pmd_home(tmp_path)
    executor = FakeExecutor()
    references = (
        list(rulesets) if rulesets is not None else [str(ruleset)]
    )
    adapter = PMDAdapter(
        ToolRunner(executor=executor),
        references,
        str(home),
        java_executable=sys.executable,
    )
    return adapter, executor, repo, ruleset


def analyze_with(
    tmp_path,
    execution,
    targets=("src/Main.java",),
    files=("src/Main.java",),
    rulesets=None,
):
    adapter, executor, repo, ruleset = build(tmp_path, files, rulesets)
    executor.result = execution
    result = adapter.analyze(str(repo), list(targets))
    return result, executor


def ruleset_argument(ruleset):
    return f"--rulesets={os.path.realpath(str(ruleset))}"


class TestCommandConstruction:
    def test_command_is_explicit_argument_list(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        assert executor.requests[0].command == [
            java_launcher(),
            "-cp",
            classpath_for(tmp_path / "pmd"),
            "net.sourceforge.pmd.cli.PmdCli",
            "check",
            "--no-cache",
            "--no-progress",
            "--format=json",
            ruleset_argument(ruleset),
            "--dir=src/Main.java",
        ]

    def test_cwd_is_repository_directory(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        assert executor.requests[0].cwd == os.path.realpath(str(repo))

    def test_java_launcher_is_resolved_realpath(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        assert executor.requests[0].command[0] == java_launcher()

    @pytest.mark.skipif(
        shutil.which("java") is None, reason="java is not on PATH"
    )
    def test_default_java_launcher_resolved_from_path(self, tmp_path):
        repo, ruleset = make_env(tmp_path)
        write_file(repo, "src/Main.java")
        adapter, executor = make_adapter(
            tmp_path,
            [_BUILTIN_RULESET],
            java_executable="java",
        )
        adapter.analyze(str(repo), ["src/Main.java"])
        expected = os.path.realpath(shutil.which("java"))
        assert executor.requests[0].command[0] == expected

    def test_classpath_is_conf_then_lib_wildcard(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        classpath = executor.requests[0].command[2]
        conf, lib = classpath.split(os.pathsep)
        assert os.path.basename(conf) == "conf"
        assert lib.endswith("*")
        assert os.path.basename(os.path.dirname(lib)) == "lib"

    def test_pmd_home_with_spaces_kept_as_one_argument(self, tmp_path):
        home = make_pmd_home(tmp_path, name="pmd home")
        adapter, executor, repo, ruleset = build(
            tmp_path, pmd_home=home
        )
        adapter.analyze(str(repo), ["src/Main.java"])
        classpath = classpath_for(home)
        assert " " in classpath
        assert classpath in executor.requests[0].command
        assert executor.requests[0].command.count(classpath) == 1

    def test_builtin_ruleset_reference_passed_verbatim(self, tmp_path):
        adapter, executor, repo, ruleset = build(
            tmp_path,
            rulesets=(
                "category/java/bestpractices.xml",
                "rulesets/java/quickstart.xml",
            ),
        )
        adapter.analyze(str(repo), ["src/Main.java"])
        command = executor.requests[0].command
        assert (
            "--rulesets=category/java/bestpractices.xml" in command
        )
        assert "--rulesets=rulesets/java/quickstart.xml" in command

    def test_multiple_rulesets_keep_order(self, tmp_path):
        adapter, executor, repo, ruleset = build(
            tmp_path,
            rulesets=(
                "category/java/errorprone.xml",
                "category/java/security.xml",
            ),
        )
        adapter.analyze(str(repo), ["src/Main.java"])
        command = executor.requests[0].command
        assert command[8:10] == [
            "--rulesets=category/java/errorprone.xml",
            "--rulesets=category/java/security.xml",
        ]

    def test_relative_ruleset_and_pmd_home_resolved(
        self, tmp_path, monkeypatch
    ):
        repo, ruleset = make_env(tmp_path)
        write_file(repo, "src/Main.java")
        make_pmd_home(tmp_path)
        monkeypatch.chdir(tmp_path)
        executor = FakeExecutor(completed(report()))
        adapter = PMDAdapter(
            ToolRunner(executor=executor),
            ["trusted_ruleset.xml"],
            "pmd",
            java_executable=sys.executable,
        )
        adapter.analyze(str(repo), ["src/Main.java"])
        command = executor.requests[0].command
        assert ruleset_argument(ruleset) in command
        assert command[2] == classpath_for(tmp_path / "pmd")

    def test_multiple_targets_each_attached(self, tmp_path):
        adapter, executor, repo, ruleset = build(
            tmp_path, files=("src/Main.java", "src/Util.java")
        )
        adapter.analyze(str(repo), ["src/Main.java", "src/Util.java"])
        command = executor.requests[0].command
        assert command[-2:] == [
            "--dir=src/Main.java",
            "--dir=src/Util.java",
        ]

    def test_target_starting_with_dash_stays_attached(self, tmp_path):
        adapter, executor, repo, ruleset = build(
            tmp_path, files=("-Odd.java",)
        )
        adapter.analyze(str(repo), ["-Odd.java"])
        command = executor.requests[0].command
        assert "--dir=-Odd.java" in command
        assert "-Odd.java" not in command

    def test_no_batch_launcher_and_no_fail_relaxations(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        command = executor.requests[0].command
        assert "--report-file" not in command
        assert "--no-fail-on-violation" not in command
        assert "--no-fail-on-error" not in command
        assert "pmd" not in command
        assert not any(
            argument.lower().endswith((".bat", ".cmd"))
            for argument in command
        )
        assert "." not in command

    def test_all_arguments_are_strings(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        assert all(
            isinstance(argument, str)
            for argument in executor.requests[0].command
        )


class TestRulesetValidation:
    @pytest.mark.parametrize("reference", ["", "   ", None, 42])
    def test_blank_or_non_string_reference_rejected(
        self, tmp_path, reference
    ):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, [reference])

    def test_padded_reference_rejected(self, tmp_path):
        ruleset = tmp_path / "rules.xml"
        ruleset.write_text("<ruleset/>\n", encoding="utf-8")
        with pytest.raises(ValueError):
            make_adapter(tmp_path, [f" {ruleset} "])

    def test_nul_reference_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, ["a\x00b.xml"])

    @pytest.mark.parametrize(
        "reference",
        [
            "http://example.com/rules.xml",
            "https://example.com/rules.xml",
            "file:///etc/rules.xml",
            "HTTP://example.com/rules.xml",
        ],
    )
    def test_url_reference_rejected(self, tmp_path, reference):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, [reference])

    def test_missing_ruleset_file_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, [str(tmp_path / "missing.xml")])

    def test_directory_ruleset_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, [str(tmp_path)])

    def test_empty_rulesets_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, [])

    @pytest.mark.parametrize("reference", ["rules.xml", None, b"x"])
    def test_string_like_rulesets_rejected(self, reference):
        with pytest.raises(ValueError):
            PMDAdapter(
                ToolRunner(executor=FakeExecutor()),
                reference,
                "pmd",
            )

    def test_builtin_reference_needs_no_file(self, tmp_path):
        adapter, _ = make_adapter(tmp_path, [_BUILTIN_RULESET])
        assert adapter.rulesets == [_BUILTIN_RULESET]

    def test_ruleset_inside_repo_rejected(self, tmp_path):
        repo, _ = make_env(tmp_path)
        inside = repo / "rules.xml"
        inside.write_text("<ruleset/>\n", encoding="utf-8")
        write_file(repo, "src/Main.java")
        adapter, executor = make_adapter(tmp_path, [str(inside)])
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), ["src/Main.java"])
        assert executor.requests == []

    def test_nested_ruleset_inside_repo_rejected(self, tmp_path):
        repo, _ = make_env(tmp_path)
        inside = repo / "config" / "rules.xml"
        inside.parent.mkdir()
        inside.write_text("<ruleset/>\n", encoding="utf-8")
        adapter, executor = make_adapter(tmp_path, [str(inside)])
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), ["src/Main.java"])
        assert executor.requests == []


class TestPmdHomeValidation:
    @pytest.mark.parametrize("value", ["", "   ", None, 42])
    def test_blank_or_non_string_rejected(self, value):
        with pytest.raises(ValueError):
            PMDAdapter(
                ToolRunner(executor=FakeExecutor()),
                [_BUILTIN_RULESET],
                value,
                java_executable=sys.executable,
            )

    def test_padded_value_rejected(self, tmp_path):
        home = make_pmd_home(tmp_path)
        with pytest.raises(ValueError):
            PMDAdapter(
                ToolRunner(executor=FakeExecutor()),
                [_BUILTIN_RULESET],
                f" {home} ",
                java_executable=sys.executable,
            )

    def test_nul_value_rejected(self):
        with pytest.raises(ValueError):
            PMDAdapter(
                ToolRunner(executor=FakeExecutor()),
                [_BUILTIN_RULESET],
                "a\x00b",
                java_executable=sys.executable,
            )

    def test_missing_directory_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            PMDAdapter(
                ToolRunner(executor=FakeExecutor()),
                [_BUILTIN_RULESET],
                str(tmp_path / "missing"),
                java_executable=sys.executable,
            )

    def test_file_instead_of_directory_rejected(self, tmp_path):
        path = tmp_path / "pmd.zip"
        path.write_bytes(b"")
        with pytest.raises(ValueError):
            PMDAdapter(
                ToolRunner(executor=FakeExecutor()),
                [_BUILTIN_RULESET],
                str(path),
                java_executable=sys.executable,
            )

    def test_missing_conf_rejected(self, tmp_path):
        home = tmp_path / "pmd"
        (home / "lib").mkdir(parents=True)
        (home / "lib" / "pmd-cli-7.28.0.jar").write_bytes(b"")
        with pytest.raises(ValueError):
            PMDAdapter(
                ToolRunner(executor=FakeExecutor()),
                [_BUILTIN_RULESET],
                str(home),
                java_executable=sys.executable,
            )

    def test_missing_lib_rejected(self, tmp_path):
        home = tmp_path / "pmd"
        (home / "conf").mkdir(parents=True)
        with pytest.raises(ValueError):
            PMDAdapter(
                ToolRunner(executor=FakeExecutor()),
                [_BUILTIN_RULESET],
                str(home),
                java_executable=sys.executable,
            )

    def test_lib_without_jar_rejected(self, tmp_path):
        home = tmp_path / "pmd"
        (home / "conf").mkdir(parents=True)
        (home / "lib").mkdir()
        (home / "lib" / "notes.txt").write_text("no jars here")
        with pytest.raises(ValueError):
            PMDAdapter(
                ToolRunner(executor=FakeExecutor()),
                [_BUILTIN_RULESET],
                str(home),
                java_executable=sys.executable,
            )

    def test_existing_home_resolved_to_realpath(self, tmp_path):
        home = make_pmd_home(tmp_path)
        adapter, _ = make_adapter(tmp_path, [_BUILTIN_RULESET])
        assert adapter.pmd_home == os.path.realpath(str(home))


class TestJavaLauncherValidation:
    @pytest.mark.parametrize("value", ["", "   ", None, 42])
    def test_blank_or_non_string_rejected(self, tmp_path, value):
        with pytest.raises(ValueError):
            make_adapter(
                tmp_path, [_BUILTIN_RULESET], java_executable=value
            )

    def test_missing_bare_name_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            make_adapter(
                tmp_path,
                [_BUILTIN_RULESET],
                java_executable="codesentinel-no-such-java-9f31",
            )

    def test_missing_path_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            make_adapter(
                tmp_path,
                [_BUILTIN_RULESET],
                java_executable=str(tmp_path / "java.exe"),
            )

    @pytest.mark.parametrize("suffix", [".bat", ".cmd", ".BAT"])
    def test_batch_path_rejected(self, tmp_path, suffix):
        launcher = tmp_path / f"fake-java{suffix}"
        launcher.write_text("@echo off\r\n", encoding="utf-8")
        with pytest.raises(ValueError):
            make_adapter(
                tmp_path,
                [_BUILTIN_RULESET],
                java_executable=str(launcher),
            )

    def test_bare_name_resolving_to_batch_rejected(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            pmd_adapter.shutil,
            "which",
            lambda name: r"C:\tools\java.bat",
        )
        with pytest.raises(ValueError):
            make_adapter(
                tmp_path, [_BUILTIN_RULESET], java_executable="java"
            )

    def test_bare_name_on_path_batch_rejected(
        self, tmp_path, monkeypatch
    ):
        bindir = tmp_path / "bin"
        bindir.mkdir()
        (bindir / "java.bat").write_text(
            "@echo off\r\n", encoding="utf-8"
        )
        monkeypatch.setenv(
            "PATH", str(bindir) + os.pathsep + os.environ.get("PATH", "")
        )
        found = shutil.which("java")
        if not found or not found.lower().endswith((".bat", ".cmd")):
            pytest.skip(
                "PATH resolution does not pick up batch launchers here"
            )
        with pytest.raises(ValueError):
            make_adapter(
                tmp_path, [_BUILTIN_RULESET], java_executable="java"
            )

    def test_resolved_launcher_is_absolute_realpath(self, tmp_path):
        adapter, _ = make_adapter(tmp_path, [_BUILTIN_RULESET])
        assert adapter.java_executable == java_launcher()


class TestExecutionStatusMapping:
    def test_tool_not_found(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.UNAVAILABLE,
            error_code=StaticAnalysisErrorCode.TOOL_NOT_FOUND,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.tool is StaticAnalysisTool.PMD
        assert result.status is StaticAnalysisStatus.UNAVAILABLE
        assert result.error_code is StaticAnalysisErrorCode.TOOL_NOT_FOUND
        assert result.exit_code is None
        assert result.findings == []

    def test_timeout(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.TIMEOUT,
            error_code=StaticAnalysisErrorCode.TIMEOUT,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.TIMEOUT
        assert result.error_code is StaticAnalysisErrorCode.TIMEOUT
        assert result.findings == []

    def test_spawn_failure(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.ERROR,
            error_code=StaticAnalysisErrorCode.SPAWN_FAILED,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.SPAWN_FAILED
        assert result.findings == []

    def test_execution_error_unknown(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.ERROR,
            error_code=StaticAnalysisErrorCode.UNKNOWN,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.UNKNOWN
        assert result.findings == []


class TestExitCodeHandling:
    def test_exit_code_zero_without_violations(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(report(), exit_code=0)
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.exit_code == 0
        assert result.findings == []

    def test_exit_code_four_with_violations_is_ok(self, tmp_path):
        execution = completed(
            report(pmd_file("src/Main.java", violation())),
            exit_code=4,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.OK
        assert result.exit_code == 4
        assert len(result.findings) == 1

    def test_exit_code_four_without_violations_is_ok(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(report(), exit_code=4)
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []

    @pytest.mark.parametrize("exit_code", [1, 2, 5])
    def test_other_exit_codes_are_process_failed(
        self, tmp_path, exit_code
    ):
        execution = completed(report(), exit_code=exit_code)
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.PROCESS_FAILED
        assert result.exit_code == exit_code
        assert result.findings == []

    def test_exit_code_five_with_violations_still_failed(self, tmp_path):
        execution = completed(
            report(pmd_file("src/Main.java", violation())),
            exit_code=5,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.findings == []

    def test_parse_failure_keeps_exit_code(self, tmp_path):
        execution = completed("not json", exit_code=4)
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.exit_code == 4


class TestSuccessMapping:
    def test_no_violations_gives_empty_findings(self, tmp_path):
        result, _ = analyze_with(tmp_path, completed(report()))
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []
        assert result.error_code is None
        assert result.duration_ms == 12

    def test_single_violation_field_mapping(self, tmp_path):
        entry = violation(
            beginline=5,
            endline=7,
            description="Logger calls should be guarded.",
            rule="GuardLogStatement",
            ruleset="Best Practices",
            priority=2,
        )
        result, _ = analyze_with(
            tmp_path,
            completed(
                report(pmd_file("src/Main.java", entry)), exit_code=4
            ),
        )
        finding = result.findings[0]
        assert finding.tool is StaticAnalysisTool.PMD
        assert finding.rule_id == "GuardLogStatement"
        assert finding.message == "Logger calls should be guarded."
        assert finding.category is Category.QUALITY
        assert finding.severity is Severity.MEDIUM
        assert finding.file_path == "src/Main.java"
        assert finding.start_line == 5
        assert finding.end_line == 7

    def test_multiple_files_and_violations_keep_order(self, tmp_path):
        execution = completed(
            report(
                pmd_file(
                    "src/Main.java",
                    violation(rule="RuleA", beginline=1),
                    violation(rule="RuleB", beginline=2),
                ),
                pmd_file(
                    "src/Util.java",
                    violation(rule="RuleC", beginline=3),
                ),
            ),
            exit_code=4,
        )
        result, _ = analyze_with(
            tmp_path,
            execution,
            targets=("src/Main.java", "src/Util.java"),
            files=("src/Main.java", "src/Util.java"),
        )
        assert [finding.rule_id for finding in result.findings] == [
            "RuleA",
            "RuleB",
            "RuleC",
        ]
        assert result.findings[2].file_path == "src/Util.java"

    def test_missing_endline_falls_back_to_beginline(self, tmp_path):
        entry = violation(beginline=9, endline=None)
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings[0].start_line == 9
        assert result.findings[0].end_line == 9

    def test_suppressed_violations_are_ignored(self, tmp_path):
        execution = completed(
            report(
                suppressed=[
                    {
                        "filename": "src/Main.java",
                        "violations": [violation()],
                    }
                ]
            )
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []


class TestSeverityMapping:
    @pytest.mark.parametrize(
        ("priority", "expected"),
        [
            (1, Severity.HIGH),
            (2, Severity.MEDIUM),
            (3, Severity.MEDIUM),
            (4, Severity.LOW),
            (5, Severity.INFO),
        ],
    )
    def test_priority_maps_to_severity(
        self, tmp_path, priority, expected
    ):
        entry = violation(priority=priority)
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert result.findings[0].severity is expected

    @pytest.mark.parametrize("priority", [0, 6, -1, "3", 3.0, True])
    def test_invalid_priority_is_schema_mismatch(
        self, tmp_path, priority
    ):
        entry = violation(priority=priority)
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_missing_priority_is_schema_mismatch(self, tmp_path):
        entry = violation()
        del entry["priority"]
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )


class TestCategoryMapping:
    @pytest.mark.parametrize(
        ("ruleset", "expected"),
        [
            ("Best Practices", Category.QUALITY),
            ("Code Style", Category.QUALITY),
            ("Design", Category.QUALITY),
            ("Documentation", Category.QUALITY),
            ("Error Prone", Category.BUG),
            ("Multithreading", Category.BUG),
            ("Performance", Category.PERFORMANCE),
            ("Security", Category.SECURITY),
        ],
    )
    def test_ruleset_maps_to_category(
        self, tmp_path, ruleset, expected
    ):
        entry = violation(ruleset=ruleset)
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert result.findings[0].category is expected

    def test_ruleset_match_is_case_insensitive(self, tmp_path):
        entry = violation(ruleset="SECURITY")
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert result.findings[0].category is Category.SECURITY

    def test_unknown_ruleset_falls_back_to_quality(self, tmp_path):
        entry = violation(ruleset="My Company Rules")
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert result.findings[0].category is Category.QUALITY

    def test_missing_ruleset_falls_back_to_quality(self, tmp_path):
        entry = violation(ruleset=None)
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert result.findings[0].category is Category.QUALITY

    @pytest.mark.parametrize("ruleset", ["", "   "])
    def test_blank_ruleset_is_schema_mismatch(
        self, tmp_path, ruleset
    ):
        entry = violation(ruleset=ruleset)
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )


class TestLineNumbers:
    def test_beginline_maps_to_start_line(self, tmp_path):
        entry = violation(beginline=12)
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert result.findings[0].start_line == 12

    def test_endline_before_beginline_rejected(self, tmp_path):
        entry = violation(beginline=10, endline=4)
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    @pytest.mark.parametrize("line", [0, -1, "1", 1.0, True])
    def test_invalid_beginline_rejected(self, tmp_path, line):
        entry = violation(beginline=line)
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    @pytest.mark.parametrize("line", [0, -1, "2"])
    def test_invalid_endline_rejected(self, tmp_path, line):
        entry = violation(beginline=1, endline=line)
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_missing_beginline_rejected(self, tmp_path):
        entry = violation()
        del entry["beginline"]
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )


class TestParseFailures:
    @pytest.mark.parametrize(
        "stdout", ["", " ", "\n", "not json", "{} trailing"]
    )
    def test_non_json_output_is_parse_error(self, tmp_path, stdout):
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT
        assert result.findings == []

    @pytest.mark.parametrize(
        "stdout", ["[]", "42", '"text"', "null"]
    )
    def test_non_object_payload_is_schema_mismatch(
        self, tmp_path, stdout
    ):
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        assert result.findings == []

    def test_missing_files_is_schema_mismatch(self, tmp_path):
        stdout = json.dumps(
            {
                "suppressedViolations": [],
                "processingErrors": [],
                "configurationErrors": [],
            }
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_error_arrays_is_schema_mismatch(self, tmp_path):
        stdout = json.dumps({"files": []})
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize(
        "key",
        ["suppressedViolations", "processingErrors", "configurationErrors"],
    )
    def test_error_array_wrong_type_is_schema_mismatch(
        self, tmp_path, key
    ):
        payload = {
            "files": [],
            "suppressedViolations": [],
            "processingErrors": [],
            "configurationErrors": [],
        }
        payload[key] = "boom"
        result, _ = analyze_with(
            tmp_path, completed(json.dumps(payload))
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_files_wrong_type_is_schema_mismatch(self, tmp_path):
        stdout = json.dumps(
            {
                "files": {},
                "suppressedViolations": [],
                "processingErrors": [],
                "configurationErrors": [],
            }
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_file_entry_not_object_is_schema_mismatch(
        self, tmp_path
    ):
        stdout = json.dumps(
            {
                "files": [42],
                "suppressedViolations": [],
                "processingErrors": [],
                "configurationErrors": [],
            }
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_violations_wrong_type_is_schema_mismatch(
        self, tmp_path
    ):
        stdout = json.dumps(
            {
                "files": [
                    {"filename": "src/Main.java", "violations": {}}
                ],
                "suppressedViolations": [],
                "processingErrors": [],
                "configurationErrors": [],
            }
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_violation_not_object_is_schema_mismatch(
        self, tmp_path
    ):
        execution = completed(
            report(
                {
                    "filename": "src/Main.java",
                    "violations": [42],
                }
            )
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_rule_is_schema_mismatch(self, tmp_path):
        entry = violation()
        del entry["rule"]
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize("rule", ["", "   ", 42, None])
    def test_invalid_rule_is_schema_mismatch(self, tmp_path, rule):
        entry = violation(rule=rule)
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize("description", ["", "   ", 42])
    def test_invalid_description_is_schema_mismatch(
        self, tmp_path, description
    ):
        entry = violation(description=description)
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_missing_description_is_schema_mismatch(self, tmp_path):
        entry = violation()
        del entry["description"]
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_one_bad_entry_invalidates_whole_run(self, tmp_path):
        execution = completed(
            report(
                pmd_file(
                    "src/Main.java",
                    violation(rule="RuleA"),
                    {"beginline": 1},
                )
            )
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        assert result.findings == []

    def test_truncated_stdout_is_rejected(self, tmp_path):
        execution = completed(
            report(pmd_file("src/Main.java", violation())),
            stdout_truncated=True,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT
        assert result.findings == []

    def test_truncated_stdout_with_incomplete_json_rejected(
        self, tmp_path
    ):
        execution = completed(
            stdout='{"files": [{"filename": "src/Main.java"',
            stdout_truncated=True,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT

    def test_truncated_stderr_alone_is_accepted(self, tmp_path):
        execution = completed(
            report(pmd_file("src/Main.java", violation())),
            stderr_truncated=True,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.OK
        assert len(result.findings) == 1


class TestScanCompleteness:
    def test_processing_errors_reject_whole_run(self, tmp_path):
        execution = completed(
            report(
                pmd_file("src/Main.java", violation()),
                processing_errors=[
                    {
                        "filename": "src/Main.java",
                        "message": "ParseException",
                        "detail": "sensitive-detail",
                    }
                ],
            )
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.PROCESS_FAILED
        assert result.findings == []

    def test_configuration_errors_reject_whole_run(self, tmp_path):
        execution = completed(
            report(
                configuration_errors=[
                    {
                        "rule": "LoosePackageCoupling",
                        "ruleset": "Design",
                        "message": "No packages specified",
                    }
                ]
            )
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.PROCESS_FAILED
        assert result.findings == []


class TestFilePathMapping:
    def test_relative_path_kept(self, tmp_path):
        result, _ = analyze_with(
            tmp_path,
            completed(
                report(
                    pmd_file(
                        "src/Main.java", violation()
                    )
                )
            ),
        )
        assert result.findings[0].file_path == "src/Main.java"

    def test_backslash_path_normalized(self, tmp_path):
        execution = completed(
            report(pmd_file("src\\Main.java", violation()))
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.findings[0].file_path == "src/Main.java"

    def test_dot_slash_prefix_normalized(self, tmp_path):
        execution = completed(
            report(pmd_file("./src/Main.java", violation()))
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.findings[0].file_path == "src/Main.java"

    def test_absolute_path_inside_repo_normalized(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        entry = pmd_file(
            os.path.join(str(repo), "src", "Main.java"), violation()
        )
        executor.result = completed(report(entry))
        result = adapter.analyze(str(repo), ["src/Main.java"])
        assert result.findings[0].file_path == "src/Main.java"

    @pytest.mark.parametrize(
        "filename",
        [
            "../outside.java",
            "src/../../outside.java",
            "..\\outside.java",
            "",
            "   ",
        ],
    )
    def test_traversal_or_blank_path_rejected(
        self, tmp_path, filename
    ):
        execution = completed(
            report(pmd_file(filename, violation()))
        )
        result, _ = analyze_with(tmp_path, execution)
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_absolute_path_outside_repo_rejected(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        outside = os.path.join(
            str(tmp_path), "outside.java"
        )
        executor.result = completed(
            report(pmd_file(outside, violation()))
        )
        result = adapter.analyze(str(repo), ["src/Main.java"])
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_drive_absolute_path_rejected(self, tmp_path):
        execution = completed(
            report(pmd_file("C:/repo/Main.java", violation()))
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_unrequested_file_rejected(self, tmp_path):
        execution = completed(
            report(pmd_file("src/Other.java", violation()))
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_case_different_path_rejected(self, tmp_path):
        execution = completed(
            report(pmd_file("SRC/MAIN.java", violation()))
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_second_file_unrequested_invalidates_run(self, tmp_path):
        execution = completed(
            report(
                pmd_file("src/Main.java", violation()),
                pmd_file("src/Other.java", violation()),
            )
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.findings == []


class TestInputValidation:
    @pytest.mark.parametrize("repo_dir", ["", "   "])
    def test_blank_repo_dir_rejected(self, tmp_path, repo_dir):
        adapter, executor, repo, ruleset = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(repo_dir, ["src/Main.java"])

    def test_missing_repo_dir_rejected(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(
                os.path.join(str(tmp_path), "missing"),
                ["src/Main.java"],
            )

    def test_empty_targets_rejected(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [])

    @pytest.mark.parametrize(
        "targets", ["src/Main.java", b"src/Main.java", None]
    )
    def test_string_like_targets_rejected(self, tmp_path, targets):
        adapter, executor, repo, ruleset = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), targets)

    def test_non_string_target_rejected(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [42])

    @pytest.mark.parametrize(
        "target",
        [
            "/etc/Main.java",
            "C:/repo/Main.java",
            "\\\\server\\share\\Main.java",
        ],
    )
    def test_absolute_drive_and_unc_rejected(self, tmp_path, target):
        adapter, executor, repo, ruleset = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [target])
        assert executor.requests == []

    @pytest.mark.parametrize(
        "target",
        [
            "../outside.java",
            "src/../../outside.java",
            "..\\outside.java",
            "src/./Main.java",
            "src//Main.java",
            "src/Main.java/",
            ".",
        ],
    )
    def test_traversal_and_malformed_targets_rejected(
        self, tmp_path, target
    ):
        adapter, executor, repo, ruleset = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [target])
        assert executor.requests == []

    def test_nul_target_rejected(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), ["src/Main\x00.java"])
        assert executor.requests == []

    @pytest.mark.parametrize(
        "target", [" src/Main.java", "src/Main.java "]
    )
    def test_padded_target_rejected(self, tmp_path, target):
        adapter, executor, repo, ruleset = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [target])
        assert executor.requests == []

    @pytest.mark.parametrize(
        "target", ["script.py", "pom.xml", "Main.Java", "notes.md"]
    )
    def test_non_java_target_rejected(self, tmp_path, target):
        adapter, executor, repo, ruleset = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [target])
        assert executor.requests == []

    def test_missing_target_file_rejected(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), ["src/Missing.java"])
        assert executor.requests == []

    def test_backslash_input_normalized(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        adapter.analyze(str(repo), ["src\\Main.java"])
        assert "--dir=src/Main.java" in executor.requests[0].command

    def test_duplicate_targets_deduplicated(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        adapter.analyze(
            str(repo), ["src/Main.java", "src/Main.java"]
        )
        command = executor.requests[0].command
        assert command.count("--dir=src/Main.java") == 1


class TestHostileFilenames:
    @pytest.mark.parametrize("name", _HOSTILE_NAMES)
    def test_metacharacter_names_accepted_verbatim(
        self, tmp_path, name
    ):
        adapter, executor, repo, ruleset = build(
            tmp_path, files=(name,)
        )
        adapter.analyze(str(repo), [name])
        request = executor.requests[0]
        assert isinstance(request.command, list)
        assert f"--dir={name}" in request.command
        assert request.command.count(f"--dir={name}") == 1

    def test_metacharacter_result_path_maps_back(self, tmp_path):
        name = "a&b.java"
        adapter, executor, repo, ruleset = build(
            tmp_path, files=(name,)
        )
        executor.result = completed(
            report(pmd_file(name, violation()))
        )
        result = adapter.analyze(str(repo), [name])
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings[0].file_path == name

    def test_command_never_uses_batch_launcher(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        command = executor.requests[0].command
        assert not command[0].lower().endswith((".bat", ".cmd"))
        assert not any(
            argument.lower().endswith((".bat", ".cmd"))
            for argument in command
        )


class TestRealExecutorShellSafety:
    def test_executor_passes_arguments_verbatim(self):
        executor = SubprocessExecutor()
        request = CommandExecutionRequest(
            command=[
                sys.executable,
                "-c",
                "import sys; print(sys.argv[1])",
                "x&whoami",
            ],
        )
        result = executor.execute(request)
        assert result.status is ExecutionStatus.COMPLETED
        assert result.exit_code == 0
        assert result.stdout.strip() == "x&whoami"

    def test_pmd_command_shape_has_no_shell_string(self, tmp_path):
        adapter, executor, repo, ruleset = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        request = executor.requests[0]
        assert all(
            isinstance(argument, str)
            for argument in request.command
        )
        assert request.command[0].lower().endswith(".exe") or (
            not request.command[0].lower().endswith((".bat", ".cmd"))
        )


class TestSafety:
    def test_failure_result_does_not_expose_raw_output(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.ERROR,
            error_code=StaticAnalysisErrorCode.UNKNOWN,
            stdout="sensitive-source-content",
            stderr="sensitive-error-detail",
        )
        result, _ = analyze_with(tmp_path, execution)
        dumped = result.model_dump_json()
        assert "sensitive-source-content" not in dumped
        assert "sensitive-error-detail" not in dumped

    def test_parse_failure_does_not_expose_output(self, tmp_path):
        execution = completed(stdout="secret_token_123 not json")
        result, _ = analyze_with(tmp_path, execution)
        assert "secret_token_123" not in result.model_dump_json()

    def test_processing_error_detail_not_exposed(self, tmp_path):
        execution = completed(
            report(
                processing_errors=[
                    {
                        "filename": "src/Main.java",
                        "message": "ParseException",
                        "detail": "sensitive-stack-trace",
                    }
                ]
            )
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert "sensitive-stack-trace" not in result.model_dump_json()

    def test_description_only_in_findings(self, tmp_path):
        entry = violation(description="Avoid unused imports.")
        result, _ = analyze_with(
            tmp_path,
            completed(report(pmd_file("src/Main.java", entry))),
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings[0].message == "Avoid unused imports."


class TestResultContract:
    def test_ok_result_has_no_error_code(self, tmp_path):
        result, _ = analyze_with(
            tmp_path,
            completed(
                report(pmd_file("src/Main.java", violation()))
            ),
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.error_code is None

    @pytest.mark.parametrize(
        "execution",
        [
            CommandExecutionResult(
                status=ExecutionStatus.UNAVAILABLE,
                error_code=StaticAnalysisErrorCode.TOOL_NOT_FOUND,
            ),
            CommandExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                error_code=StaticAnalysisErrorCode.TIMEOUT,
            ),
            CommandExecutionResult(
                status=ExecutionStatus.ERROR,
                error_code=StaticAnalysisErrorCode.SPAWN_FAILED,
            ),
        ],
    )
    def test_failure_result_has_no_findings(self, tmp_path, execution):
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is not StaticAnalysisStatus.OK
        assert result.error_code is not None
        assert result.findings == []

    def test_findings_all_carry_pmd_tool(self, tmp_path):
        execution = completed(
            report(
                pmd_file(
                    "src/Main.java",
                    violation(rule="RuleA"),
                    violation(rule="RuleB", beginline=2),
                )
            )
        )
        result, _ = analyze_with(tmp_path, execution)
        assert all(
            finding.tool is StaticAnalysisTool.PMD
            for finding in result.findings
        )

    def test_ok_result_with_findings_round_trips(self, tmp_path):
        result, _ = analyze_with(
            tmp_path,
            completed(
                report(pmd_file("src/Main.java", violation()))
            ),
        )
        recreated = type(result).model_validate_json(
            result.model_dump_json()
        )
        assert recreated == result