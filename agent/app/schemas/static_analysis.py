"""Static analysis data contract (Phase 7.1).

Tool agnostic representation of static analysis runs and their findings.
Adapters (Phase 7.3+) translate tool specific output into these models;
nothing in this module executes tools, reads source or uses the network.

Contract notes:

- category and severity reuse the review enums (app.schemas.review), so a
  static finding can later be merged with LLM findings without a second
  taxonomy. Mapping tool specific rules onto these enums is the adapter's
  job, not the schema's.
- A finding intentionally carries no confidence: static analyzers do not
  produce calibrated confidence values, and inventing one here would
  fabricate evidence. Real confidence is established later by the
  Validator.
- Line numbers are 1-based and refer to the head revision, matching the
  Phase 6 code context contract.
- file_path must be a non-empty repository relative path. Absolute paths,
  Windows drive paths and traversal segments are rejected because findings
  are only ever anchored to files of the reviewed repository.
- status OK means the tool ran and its output was fully parsed: findings
  may legitimately be empty, and a non zero exit code is expected from
  several tools once they report issues. Every other status is an explicit
  degradation that must carry a safe error_code and never carries
  findings, so partial or unverified output cannot masquerade as a
  successful result.
"""

import re
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.review import Category, Severity


class StaticAnalysisTool(str, Enum):
    """Static analysis tools supported by the review pipeline."""

    RUFF = "RUFF"
    BANDIT = "BANDIT"
    SEMGREP = "SEMGREP"
    PMD = "PMD"
    CHECKSTYLE = "CHECKSTYLE"


class StaticAnalysisStatus(str, Enum):
    """Outcome of one tool execution.

    OK means the tool ran and its output was parsed successfully, even when
    it reported findings or exited with a non zero code. UNAVAILABLE,
    TIMEOUT, ERROR and PARSE_ERROR are explicit failures and can never
    carry findings.
    """

    OK = "OK"
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    PARSE_ERROR = "PARSE_ERROR"


class StaticAnalysisErrorCode(str, Enum):
    """Finite, safe error categories for failed runs.

    Raw stdout, stderr, source code and exception details must never reach
    this field: they can embed untrusted source or environment specifics.
    Only these codes may be exposed to consumers.
    """

    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    SPAWN_FAILED = "SPAWN_FAILED"
    TIMEOUT = "TIMEOUT"
    PROCESS_FAILED = "PROCESS_FAILED"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    UNKNOWN = "UNKNOWN"


_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


def _is_repo_relative_path(path: str) -> bool:
    """Whether path is a non-empty repository relative file path.

    Rejects surrounding whitespace, absolute POSIX and UNC paths, Windows
    drive paths (C:...) and any '..' traversal segment on either
    separator.
    """
    if not path or not path.strip() or path != path.strip():
        return False
    if path.startswith("/") or path.startswith("\\"):
        return False
    if _DRIVE_PREFIX.match(path):
        return False
    return ".." not in path.replace("\\", "/").split("/")


class StaticAnalysisFinding(BaseModel):
    """One static analysis finding produced by a single tool.

    tool keeps the producing tool so merged lists never lose provenance.
    start_line and end_line are 1-based inclusive head revision lines and
    end_line is never smaller than start_line. rule_id and message must
    not be blank. There is deliberately no confidence field.
    """

    tool: StaticAnalysisTool
    rule_id: str
    category: Category
    severity: Severity
    message: str
    file_path: str
    start_line: int = Field(ge=1)
    end_line: int

    @field_validator("rule_id", "message")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("file_path")
    @classmethod
    def _reject_non_relative(cls, value: str) -> str:
        if not _is_repo_relative_path(value):
            raise ValueError(
                "file_path must be a non-empty repository relative path"
            )
        return value

    @model_validator(mode="after")
    def _reject_inverted_range(self) -> "StaticAnalysisFinding":
        if self.end_line < self.start_line:
            raise ValueError("end_line must not be smaller than start_line")
        return self


class StaticAnalysisResult(BaseModel):
    """Outcome of one static analysis tool run.

    exit_code is the process exit code when a process actually ran, and
    None when the tool was never started. A non zero exit code does not
    imply failure: several tools exit non zero as soon as they report
    findings, which is still status OK. duration_ms is the measured wall
    clock duration, non negative when present.

    status OK requires error_code None and allows findings, including an
    empty list. Every non OK status requires a safe error_code and forbids
    findings. When findings are present, each one must come from the same
    tool as the result.
    """

    tool: StaticAnalysisTool
    status: StaticAnalysisStatus
    findings: list[StaticAnalysisFinding] = Field(default_factory=list)
    exit_code: int | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    error_code: StaticAnalysisErrorCode | None = None

    @model_validator(mode="after")
    def _enforce_status_contract(self) -> "StaticAnalysisResult":
        if self.status == StaticAnalysisStatus.OK:
            if self.error_code is not None:
                raise ValueError("error_code is not allowed when status is OK")
        else:
            if self.error_code is None:
                raise ValueError(
                    "error_code is required when status is not OK"
                )
            if self.findings:
                raise ValueError(
                    "findings are not allowed when status is not OK"
                )
        for finding in self.findings:
            if finding.tool != self.tool:
                raise ValueError("finding.tool must match the result tool")
        return self