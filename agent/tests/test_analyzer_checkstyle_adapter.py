"""Tests for the Phase 7.7.1 Checkstyle adapter.

A fake executor is injected everywhere: Checkstyle is never installed,
started or needed. Reports are synthetic, shaped after the documented
Checkstyle XML renderer (checkstyle 14.3.0 command line docs), including
the trailing ''Checkstyle ends with N errors.'' summary line that the CLI
prints after the document.
"""

import os
import shutil
import sys

import pytest

from app.analyzers import pmd_adapter
from app.analyzers.checkstyle_adapter import CheckstyleAdapter
from app.analyzers.execution import (
    CommandExecutionResult,
    ExecutionStatus,
)
from app.analyzers.tool_runner import ToolRunner
from app.schemas.review import Category, Severity
from app.schemas.static_analysis import (
    StaticAnalysisErrorCode,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)

_MISSING = object()

CODING_SOURCE = (
    "com.puppycrawl.tools.checkstyle.checks.coding."
    "FallThroughCheck"
)
JAVADOC_SOURCE = (
    "com.puppycrawl.tools.checkstyle.checks.javadoc."
    "MissingJavadocTypeCheck"
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


def error_element(
    line=1,
    severity="error",
    message="Fall through from previous branch of switch statement",
    source=CODING_SOURCE,
    column=None,
):
    parts = [f'line="{line}"']
    if column is not None:
        parts.append(f'column="{column}"')
    parts.append(f'severity="{severity}"')
    parts.append(f'message="{message}"')
    parts.append(f'source="{source}"')
    return "<error " + " ".join(parts) + "/>"


def xml_file(name="src/Main.java", *errors):
    return f'<file name="{name}">' + "".join(errors) + "</file>"


def checkstyle_report(
    *files,
    version="14.3.0",
    trailing="\nCheckstyle ends with 1 errors.\n",
):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<checkstyle version="{version}">'
        + "".join(files)
        + "</checkstyle>"
        + trailing
    )


def raw_error(attrs):
    return f"<error {attrs}/>"


def raw_report(body, attrs='version="14.3.0"'):
    return f"<checkstyle {attrs}>{body}</checkstyle>"


def write_file(root, name, content="class Main {}\n"):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def make_env(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    config = tmp_path / "trusted_checks.xml"
    config.write_text('<module name="Checker"/>\n', encoding="utf-8")
    return repo, config


def make_jar(tmp_path):
    jar = tmp_path / "checkstyle-14.3.0-all.jar"
    jar.write_bytes(b"")
    return jar


def java_launcher():
    return os.path.realpath(sys.executable)


def config_argument(config):
    return os.path.realpath(str(config))


def jar_argument(jar):
    return os.path.realpath(str(jar))


def make_adapter(
    tmp_path,
    config=_MISSING,
    jar=_MISSING,
    java_executable=_MISSING,
):
    if config is _MISSING:
        _, config = make_env(tmp_path)
    if jar is _MISSING:
        jar = make_jar(tmp_path)
    executor = FakeExecutor()
    adapter = CheckstyleAdapter(
        ToolRunner(executor=executor),
        str(config),
        str(jar),
        java_executable=(
            sys.executable
            if java_executable is _MISSING
            else java_executable
        ),
    )
    return adapter, executor


def build(
    tmp_path,
    files=("src/Main.java",),
    config=_MISSING,
    jar=_MISSING,
):
    repo, trusted_config = make_env(tmp_path)
    for name in files:
        write_file(repo, name)
    if config is _MISSING:
        config = trusted_config
    if jar is _MISSING:
        jar = make_jar(tmp_path)
    executor = FakeExecutor()
    adapter = CheckstyleAdapter(
        ToolRunner(executor=executor),
        str(config),
        str(jar),
        java_executable=sys.executable,
    )
    return adapter, executor, repo, trusted_config


def analyze_with(
    tmp_path,
    execution,
    targets=("src/Main.java",),
    files=("src/Main.java",),
):
    adapter, executor, repo, config = build(tmp_path, files)
    executor.result = execution
    result = adapter.analyze(str(repo), list(targets))
    return result, executor


class TestCommandConstruction:
    def test_command_is_explicit_argument_list(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        assert executor.requests[0].command == [
            java_launcher(),
            "-jar",
            jar_argument(tmp_path / "checkstyle-14.3.0-all.jar"),
            "-c",
            config_argument(config),
            "-f",
            "xml",
            "src/Main.java",
        ]

    def test_cwd_is_repository_directory(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        assert executor.requests[0].cwd == os.path.realpath(str(repo))

    def test_java_launcher_is_resolved_realpath(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        assert executor.requests[0].command[0] == java_launcher()

    @pytest.mark.skipif(
        shutil.which("java") is None, reason="java is not on PATH"
    )
    def test_default_java_launcher_resolved_from_path(self, tmp_path):
        repo, config = make_env(tmp_path)
        write_file(repo, "src/Main.java")
        jar = make_jar(tmp_path)
        adapter, executor = make_adapter(
            tmp_path, config=config, jar=jar, java_executable="java"
        )
        adapter.analyze(str(repo), ["src/Main.java"])
        expected = os.path.realpath(shutil.which("java"))
        assert executor.requests[0].command[0] == expected

    def test_builtin_config_passed_verbatim(self, tmp_path):
        adapter, executor = make_adapter(
            tmp_path, config="google_checks.xml"
        )
        repo, _ = make_env(tmp_path)
        write_file(repo, "src/Main.java")
        adapter.analyze(str(repo), ["src/Main.java"])
        command = executor.requests[0].command
        assert command[3:5] == ["-c", "google_checks.xml"]

    def test_format_is_xml(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        command = executor.requests[0].command
        assert command[5:7] == ["-f", "xml"]

    def test_multiple_targets_keep_order(self, tmp_path):
        adapter, executor, repo, config = build(
            tmp_path, files=("src/Main.java", "src/Util.java")
        )
        adapter.analyze(str(repo), ["src/Main.java", "src/Util.java"])
        command = executor.requests[0].command
        assert command[-2:] == ["src/Main.java", "src/Util.java"]

    def test_no_batch_launcher_in_command(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        command = executor.requests[0].command
        assert not any(
            argument.lower().endswith((".bat", ".cmd"))
            for argument in command
        )
        assert "checkstyle.bat" not in command

    def test_all_arguments_are_strings(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["src/Main.java"])
        assert all(
            isinstance(argument, str)
            for argument in executor.requests[0].command
        )


class TestConfigValidation:
    @pytest.mark.parametrize(
        "config",
        [
            "google_checks.xml",
            "/google_checks.xml",
            "sun_checks.xml",
            "/sun_checks.xml",
        ],
    )
    def test_builtin_config_names_accepted(self, tmp_path, config):
        adapter, _ = make_adapter(tmp_path, config=config)
        assert adapter.config == config

    @pytest.mark.parametrize(
        "config",
        [
            "http://example.com/checks.xml",
            "https://example.com/checks.xml",
            "file:///etc/checks.xml",
            "HTTP://example.com/checks.xml",
        ],
    )
    def test_url_config_rejected(self, tmp_path, config):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, config=config)

    def test_missing_config_file_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            make_adapter(
                tmp_path, config=tmp_path / "missing-checks.xml"
            )

    def test_directory_config_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, config=tmp_path)

    def test_padded_config_rejected(self, tmp_path):
        _, config = make_env(tmp_path)
        with pytest.raises(ValueError):
            make_adapter(tmp_path, config=f" {config} ")

    def test_nul_config_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, config="a\x00b.xml")

    @pytest.mark.parametrize("config", ["", "   ", None, 42])
    def test_blank_or_non_string_config_rejected(
        self, tmp_path, config
    ):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, config=config)

    def test_external_config_resolved_to_realpath(self, tmp_path):
        _, config = make_env(tmp_path)
        adapter, _ = make_adapter(tmp_path, config=config)
        assert adapter.config == os.path.realpath(str(config))


class TestJarValidation:
    def test_existing_jar_resolved_to_realpath(self, tmp_path):
        jar = make_jar(tmp_path)
        adapter, _ = make_adapter(tmp_path, jar=jar)
        assert adapter.checkstyle_jar == os.path.realpath(str(jar))

    def test_missing_jar_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, jar=tmp_path / "missing.jar")

    def test_directory_jar_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, jar=tmp_path)

    def test_non_jar_suffix_rejected(self, tmp_path):
        path = tmp_path / "checkstyle.zip"
        path.write_bytes(b"")
        with pytest.raises(ValueError):
            make_adapter(tmp_path, jar=path)

    def test_uppercase_jar_suffix_accepted(self, tmp_path):
        path = tmp_path / "checkstyle-14.3.0-all.JAR"
        path.write_bytes(b"")
        adapter, _ = make_adapter(tmp_path, jar=path)
        assert adapter.checkstyle_jar == os.path.realpath(str(path))

    def test_padded_jar_rejected(self, tmp_path):
        jar = make_jar(tmp_path)
        with pytest.raises(ValueError):
            make_adapter(tmp_path, jar=f" {jar} ")

    def test_nul_jar_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, jar="a\x00b.jar")

    @pytest.mark.parametrize("jar", ["", "   ", None, 42])
    def test_blank_or_non_string_jar_rejected(self, tmp_path, jar):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, jar=jar)


class TestJavaLauncherValidation:
    @pytest.mark.parametrize("value", ["", "   ", None, 42])
    def test_blank_or_non_string_rejected(self, tmp_path, value):
        with pytest.raises(ValueError):
            make_adapter(tmp_path, java_executable=value)

    def test_missing_bare_name_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            make_adapter(
                tmp_path,
                java_executable="codesentinel-no-such-java-9f31",
            )

    @pytest.mark.parametrize("suffix", [".bat", ".cmd"])
    def test_batch_path_rejected(self, tmp_path, suffix):
        launcher = tmp_path / f"fake-java{suffix}"
        launcher.write_text("@echo off\r\n", encoding="utf-8")
        with pytest.raises(ValueError):
            make_adapter(tmp_path, java_executable=str(launcher))

    def test_bare_name_resolving_to_batch_rejected(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            pmd_adapter.shutil,
            "which",
            lambda name: r"C:\tools\java.bat",
        )
        with pytest.raises(ValueError):
            make_adapter(tmp_path, java_executable="java")

    def test_resolved_launcher_is_absolute_realpath(self, tmp_path):
        adapter, _ = make_adapter(tmp_path)
        assert adapter.java_executable == java_launcher()


class TestConfigContainment:
    def test_config_inside_repo_rejected(self, tmp_path):
        repo, _ = make_env(tmp_path)
        inside = repo / "checks.xml"
        inside.write_text('<module name="Checker"/>\n')
        write_file(repo, "src/Main.java")
        adapter, executor = make_adapter(tmp_path, config=inside)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), ["src/Main.java"])
        assert executor.requests == []

    def test_nested_config_inside_repo_rejected(self, tmp_path):
        repo, _ = make_env(tmp_path)
        inside = repo / "config" / "checks.xml"
        inside.parent.mkdir()
        inside.write_text('<module name="Checker"/>\n')
        adapter, executor = make_adapter(tmp_path, config=inside)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), ["src/Main.java"])
        assert executor.requests == []

    def test_builtin_name_is_not_treated_as_repo_file(self, tmp_path):
        repo, config = make_env(tmp_path)
        (repo / "google_checks.xml").write_text("hostile")
        write_file(repo, "src/Main.java")
        adapter, executor = make_adapter(
            tmp_path, config="google_checks.xml"
        )
        adapter.analyze(str(repo), ["src/Main.java"])
        assert len(executor.requests) == 1


class TestTargetValidation:
    @pytest.mark.parametrize(
        "target", ["script.py", "pom.xml", "Main.Java", "notes.md"]
    )
    def test_non_java_target_rejected(self, tmp_path, target):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [target])
        assert executor.requests == []

    @pytest.mark.parametrize("name", ["-Odd.java", "@file.java"])
    def test_option_like_target_rejected(self, tmp_path, name):
        adapter, executor, repo, config = build(tmp_path, files=(name,))
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [name])
        assert executor.requests == []

    @pytest.mark.parametrize(
        "name", ["src/-Odd.java", "src/@Odd.java"]
    )
    def test_option_like_name_inside_path_accepted(
        self, tmp_path, name
    ):
        adapter, executor, repo, config = build(tmp_path, files=(name,))
        adapter.analyze(str(repo), [name])
        assert executor.requests[0].command[-1] == name

    def test_backslash_input_normalized(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(str(repo), ["src\\Main.java"])
        assert executor.requests[0].command[-1] == "src/Main.java"

    def test_duplicate_targets_deduplicated(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        adapter.analyze(
            str(repo), ["src/Main.java", "src/Main.java"]
        )
        command = executor.requests[0].command
        assert command.count("src/Main.java") == 1

    @pytest.mark.parametrize(
        "target",
        [
            "/etc/Main.java",
            "C:/repo/Main.java",
            "\\\\server\\share\\Main.java",
        ],
    )
    def test_absolute_drive_and_unc_rejected(self, tmp_path, target):
        adapter, executor, repo, config = build(tmp_path)
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
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [target])
        assert executor.requests == []

    def test_nul_target_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), ["src/Main\x00.java"])
        assert executor.requests == []

    @pytest.mark.parametrize(
        "target", [" src/Main.java", "src/Main.java "]
    )
    def test_padded_target_rejected(self, tmp_path, target):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [target])
        assert executor.requests == []

    def test_missing_target_file_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), ["src/Missing.java"])
        assert executor.requests == []

    def test_empty_targets_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), [])

    @pytest.mark.parametrize(
        "targets", ["src/Main.java", b"src/Main.java", None]
    )
    def test_string_like_targets_rejected(self, tmp_path, targets):
        adapter, executor, repo, config = build(tmp_path)
        with pytest.raises(ValueError):
            adapter.analyze(str(repo), targets)


class TestXmlParsing:
    def test_clean_report_gives_empty_findings(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(checkstyle_report(), exit_code=0)
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []
        assert result.error_code is None
        assert result.exit_code == 0
        assert result.duration_ms == 12

    def test_self_closing_clean_report_accepted(self, tmp_path):
        stdout = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<checkstyle version="14.3.0"/>\n'
            "Checkstyle ends with 0 errors.\n"
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=0)
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.findings == []

    def test_leading_log_text_tolerated(self, tmp_path):
        stdout = "Starting audit...\n" + checkstyle_report()
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=1)
        )
        assert result.status is StaticAnalysisStatus.OK

    def test_trailing_summary_tolerated(self, tmp_path):
        stdout = checkstyle_report(
            trailing="\nAudit done.\nCheckstyle ends with 1 errors.\n"
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=1)
        )
        assert result.status is StaticAnalysisStatus.OK

    def test_single_error_field_mapping(self, tmp_path):
        entry = error_element(
            line=17,
            severity="error",
            message="Fall through from previous branch",
            source=CODING_SOURCE,
            column=17,
        )
        stdout = checkstyle_report(
            xml_file("src/Main.java", entry)
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=1)
        )
        finding = result.findings[0]
        assert finding.tool is StaticAnalysisTool.CHECKSTYLE
        assert finding.rule_id == CODING_SOURCE
        assert finding.message == "Fall through from previous branch"
        assert finding.category is Category.BUG
        assert finding.severity is Severity.HIGH
        assert finding.file_path == "src/Main.java"
        assert finding.start_line == 17
        assert finding.end_line == 17

    @pytest.mark.parametrize(
        ("severity", "expected"),
        [
            ("error", Severity.HIGH),
            ("warning", Severity.MEDIUM),
            ("info", Severity.LOW),
        ],
    )
    def test_severity_maps_explicitly(
        self, tmp_path, severity, expected
    ):
        entry = error_element(severity=severity)
        stdout = checkstyle_report(
            xml_file("src/Main.java", entry)
        )
        result, _ = analyze_with(tmp_path, completed(stdout=stdout))
        assert result.findings[0].severity is expected

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            (CODING_SOURCE, Category.BUG),
            (JAVADOC_SOURCE, Category.QUALITY),
            (
                "com.puppycrawl.tools.checkstyle.checks."
                "whitespace.FileTabCharacterCheck",
                Category.QUALITY,
            ),
            ("com.example.custom.MyCheck", Category.QUALITY),
        ],
    )
    def test_category_maps_from_check_package(
        self, tmp_path, source, expected
    ):
        entry = error_element(source=source)
        stdout = checkstyle_report(
            xml_file("src/Main.java", entry)
        )
        result, _ = analyze_with(tmp_path, completed(stdout=stdout))
        assert result.findings[0].category is expected

    def test_multiple_files_and_errors_keep_order(self, tmp_path):
        stdout = checkstyle_report(
            xml_file(
                "src/Main.java",
                error_element(line=3),
                error_element(line=5, severity="warning"),
            ),
            xml_file(
                "src/Util.java",
                error_element(line=9, source=JAVADOC_SOURCE),
            ),
        )
        result, _ = analyze_with(
            tmp_path,
            completed(stdout=stdout, exit_code=3),
            targets=("src/Main.java", "src/Util.java"),
            files=("src/Main.java", "src/Util.java"),
        )
        assert [finding.start_line for finding in result.findings] == [
            3,
            5,
            9,
        ]
        assert result.findings[2].file_path == "src/Util.java"

    def test_backslash_report_path_normalized(self, tmp_path):
        stdout = checkstyle_report(
            xml_file("src\\Main.java", error_element())
        )
        result, _ = analyze_with(tmp_path, completed(stdout=stdout))
        assert result.findings[0].file_path == "src/Main.java"

    def test_dot_slash_report_path_normalized(self, tmp_path):
        stdout = checkstyle_report(
            xml_file("./src/Main.java", error_element())
        )
        result, _ = analyze_with(tmp_path, completed(stdout=stdout))
        assert result.findings[0].file_path == "src/Main.java"

    def test_absolute_report_path_inside_repo_normalized(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        entry = xml_file(
            os.path.join(str(repo), "src", "Main.java"),
            error_element(),
        )
        executor.result = completed(
            checkstyle_report(entry), exit_code=1
        )
        result = adapter.analyze(str(repo), ["src/Main.java"])
        assert result.findings[0].file_path == "src/Main.java"


class TestParseFailures:
    @pytest.mark.parametrize("stdout", ["", " ", "\n"])
    def test_empty_output_with_zero_exit_is_parse_error(
        self, tmp_path, stdout
    ):
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=0)
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT
        assert result.findings == []

    @pytest.mark.parametrize("exit_code", [1, 5, 255])
    def test_empty_output_with_nonzero_exit_is_process_failed(
        self, tmp_path, exit_code
    ):
        result, _ = analyze_with(
            tmp_path, completed(stdout="", exit_code=exit_code)
        )
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.PROCESS_FAILED
        assert result.findings == []

    @pytest.mark.parametrize(
        "stdout",
        [
            "not xml",
            "<foo/>",
            "Checkstyle ends with 0 errors.",
            "<checkstyle",
        ],
    )
    def test_output_without_checkstyle_document_rejected(
        self, tmp_path, stdout
    ):
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=0)
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT

    def test_malformed_document_rejected(self, tmp_path):
        stdout = (
            '<checkstyle version="14.3.0">'
            '<file name="src/Main.java">'
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=0)
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT

    def test_unbalanced_document_rejected(self, tmp_path):
        stdout = (
            '<checkstyle version="14.3.0">'
            '<file name="src/Main.java"></checkstyle>'
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=0)
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT

    def test_wrong_root_tag_rejected(self, tmp_path):
        stdout = '<checkstylex version="14.3.0"/>'
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=0)
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_file_missing_name_rejected(self, tmp_path):
        stdout = raw_report("<file></file>")
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=0)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_unknown_root_child_rejected(self, tmp_path):
        stdout = raw_report("<foo/>")
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=0)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_unknown_file_child_rejected(self, tmp_path):
        stdout = raw_report(
            '<file name="src/Main.java"><warning/></file>'
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=0)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize(
        "attrs",
        [
            'severity="error" message="m" source="s"',
            'line="1" message="m" source="s"',
            'line="1" severity="error" source="s"',
            'line="1" severity="error" message="m"',
        ],
    )
    def test_missing_required_attribute_rejected(
        self, tmp_path, attrs
    ):
        stdout = raw_report(
            '<file name="src/Main.java">'
            f"<error {attrs}/>"
            "</file>"
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=0)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize(
        "attrs",
        [
            'line="1" severity="error" message="" source="s"',
            'line="1" severity="error" message="   " source="s"',
            'line="1" severity="error" message="m" source=""',
            'line="1" severity="error" message="m" source="   "',
        ],
    )
    def test_blank_message_or_source_rejected(self, tmp_path, attrs):
        stdout = raw_report(
            '<file name="src/Main.java">'
            f"<error {attrs}/>"
            "</file>"
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=0)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize(
        "line", ['"0"', '"-1"', '"abc"', '""', '"1.5"']
    )
    def test_invalid_line_rejected(self, tmp_path, line):
        attrs = (
            f"line={line} severity=\"error\" "
            'message="m" source="s"'
        )
        stdout = raw_report(
            '<file name="src/Main.java">'
            f"<error {attrs}/>"
            "</file>"
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=0)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    @pytest.mark.parametrize(
        "severity", ['"ignore"', '"ERROR"', '""', '"Warning"']
    )
    def test_invalid_severity_rejected(self, tmp_path, severity):
        attrs = (
            'line="1" '
            f"severity={severity} "
            'message="m" source="s"'
        )
        stdout = raw_report(
            '<file name="src/Main.java">'
            f"<error {attrs}/>"
            "</file>"
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=0)
        )
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_one_bad_entry_invalidates_whole_run(self, tmp_path):
        good = error_element(line=3)
        bad = raw_error(
            'line="1" severity="error" message="m"'
        )
        stdout = checkstyle_report(
            xml_file("src/Main.java", good, bad)
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=2)
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        assert result.findings == []

    def test_truncated_stdout_is_rejected(self, tmp_path):
        execution = completed(
            checkstyle_report(xml_file("src/Main.java", error_element())),
            exit_code=1,
            stdout_truncated=True,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT
        assert result.findings == []

    def test_truncated_partial_document_rejected(self, tmp_path):
        execution = completed(
            stdout='<checkstyle version="14.3.0"><file name="s',
            exit_code=1,
            stdout_truncated=True,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.error_code is StaticAnalysisErrorCode.INVALID_OUTPUT

    def test_truncated_stderr_alone_is_accepted(self, tmp_path):
        execution = completed(
            checkstyle_report(xml_file("src/Main.java", error_element())),
            exit_code=1,
            stderr_truncated=True,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.OK
        assert len(result.findings) == 1


class TestExitCodes:
    @pytest.mark.parametrize("exit_code", [0, 1, 7, 42, 255])
    def test_valid_report_accepted_regardless_of_exit_code(
        self, tmp_path, exit_code
    ):
        stdout = checkstyle_report(
            xml_file("src/Main.java", error_element())
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=exit_code)
        )
        assert result.status is StaticAnalysisStatus.OK
        assert result.exit_code == exit_code
        assert len(result.findings) == 1

    def test_nonzero_exit_without_report_is_process_failed(
        self, tmp_path
    ):
        result, _ = analyze_with(
            tmp_path, completed(stdout="boom", exit_code=1)
        )
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.PROCESS_FAILED
        assert result.findings == []

    def test_failure_without_report_keeps_exit_code(self, tmp_path):
        result, _ = analyze_with(
            tmp_path, completed(stdout="not xml", exit_code=7)
        )
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.PROCESS_FAILED
        assert result.exit_code == 7
        assert result.findings == []

    def test_schema_failure_keeps_exit_code(self, tmp_path):
        stdout = raw_report("<foo/>")
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=3)
        )
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.exit_code == 3


class TestFilePathMapping:
    def test_unrequested_file_rejected(self, tmp_path):
        stdout = checkstyle_report(
            xml_file("src/Other.java", error_element())
        )
        result, _ = analyze_with(tmp_path, completed(stdout=stdout))
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

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
        stdout = checkstyle_report(
            xml_file(filename, error_element())
        )
        result, _ = analyze_with(tmp_path, completed(stdout=stdout))
        assert (
            result.error_code
            is StaticAnalysisErrorCode.SCHEMA_MISMATCH
        )

    def test_absolute_path_outside_repo_rejected(self, tmp_path):
        adapter, executor, repo, config = build(tmp_path)
        outside = os.path.join(str(tmp_path), "outside.java")
        executor.result = completed(
            checkstyle_report(xml_file(outside, error_element()))
        )
        result = adapter.analyze(str(repo), ["src/Main.java"])
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_drive_absolute_path_rejected(self, tmp_path):
        stdout = checkstyle_report(
            xml_file("C:/repo/Main.java", error_element())
        )
        result, _ = analyze_with(tmp_path, completed(stdout=stdout))
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_case_different_path_rejected(self, tmp_path):
        stdout = checkstyle_report(
            xml_file("SRC/MAIN.java", error_element())
        )
        result, _ = analyze_with(tmp_path, completed(stdout=stdout))
        assert result.error_code is StaticAnalysisErrorCode.SCHEMA_MISMATCH

    def test_second_file_unrequested_invalidates_run(self, tmp_path):
        stdout = checkstyle_report(
            xml_file("src/Main.java", error_element()),
            xml_file("src/Other.java", error_element()),
        )
        result, _ = analyze_with(tmp_path, completed(stdout=stdout))
        assert result.status is StaticAnalysisStatus.PARSE_ERROR
        assert result.findings == []


class TestExecutionStatusMapping:
    def test_tool_not_found(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.UNAVAILABLE,
            error_code=StaticAnalysisErrorCode.TOOL_NOT_FOUND,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.tool is StaticAnalysisTool.CHECKSTYLE
        assert result.status is StaticAnalysisStatus.UNAVAILABLE
        assert result.error_code is StaticAnalysisErrorCode.TOOL_NOT_FOUND
        assert result.findings == []

    def test_timeout(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.TIMEOUT,
            error_code=StaticAnalysisErrorCode.TIMEOUT,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.TIMEOUT
        assert result.findings == []

    def test_spawn_failure(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.ERROR,
            error_code=StaticAnalysisErrorCode.SPAWN_FAILED,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert (
            result.error_code is StaticAnalysisErrorCode.SPAWN_FAILED
        )
        assert result.findings == []

    def test_execution_error_unknown(self, tmp_path):
        execution = CommandExecutionResult(
            status=ExecutionStatus.ERROR,
            error_code=StaticAnalysisErrorCode.UNKNOWN,
        )
        result, _ = analyze_with(tmp_path, execution)
        assert result.status is StaticAnalysisStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.UNKNOWN


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
        execution = completed(
            stdout="secret_token_123 not xml", exit_code=0
        )
        result, _ = analyze_with(tmp_path, execution)
        assert "secret_token_123" not in result.model_dump_json()

    def test_message_only_in_findings(self, tmp_path):
        stdout = checkstyle_report(
            xml_file(
                "src/Main.java",
                error_element(message="Missing a Javadoc comment."),
            )
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=1)
        )
        assert result.status is StaticAnalysisStatus.OK
        assert (
            result.findings[0].message == "Missing a Javadoc comment."
        )


class TestResultContract:
    def test_ok_result_has_no_error_code(self, tmp_path):
        stdout = checkstyle_report(
            xml_file("src/Main.java", error_element())
        )
        result, _ = analyze_with(tmp_path, completed(stdout=stdout))
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

    def test_findings_all_carry_checkstyle_tool(self, tmp_path):
        stdout = checkstyle_report(
            xml_file(
                "src/Main.java",
                error_element(line=1),
                error_element(line=2, severity="warning"),
            )
        )
        result, _ = analyze_with(
            tmp_path, completed(stdout=stdout, exit_code=2)
        )
        assert all(
            finding.tool is StaticAnalysisTool.CHECKSTYLE
            for finding in result.findings
        )

    def test_ok_result_with_findings_round_trips(self, tmp_path):
        stdout = checkstyle_report(
            xml_file("src/Main.java", error_element())
        )
        result, _ = analyze_with(tmp_path, completed(stdout=stdout))
        recreated = type(result).model_validate_json(
            result.model_dump_json()
        )
        assert recreated == result