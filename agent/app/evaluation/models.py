"""Minimal evaluation case format (Phase 8.8).

One case is one small code sample with the findings a correct reviewer is
expected to report. The format is deliberately small and shared by the
Java and Python case directories:

- case_id: unique id matching the file name
- language: "java" or "python"
- category: the review dimension of the case directory
- source: file path (repository relative) plus the full code
- expected_findings: at least one expected finding; every expected
  finding must use the case category
- notes: optional free text

No thresholds, no model outputs and no network access are part of this
module.
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.review import Category, Severity
from app.schemas.static_analysis import is_repo_relative_path


class EvalLanguage(str, Enum):
    """Language of one evaluation case."""

    JAVA = "java"
    PYTHON = "python"


class EvalSource(BaseModel):
    """The code sample of one case."""

    file_path: str
    code: str

    @field_validator("file_path")
    @classmethod
    def _reject_non_relative(cls, value: str) -> str:
        if not is_repo_relative_path(value):
            raise ValueError(
                "file_path must be a non-empty repository relative path"
            )
        return value

    @field_validator("code")
    @classmethod
    def _reject_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("code must not be blank")
        return value


class ExpectedFinding(BaseModel):
    """One finding a correct reviewer is expected to report."""

    rule_id: str
    category: Category
    severity: Severity
    file_path: str
    start_line: int = Field(ge=1)
    end_line: int
    description: str = ""

    @field_validator("rule_id")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rule_id must not be blank")
        return value

    @field_validator("file_path")
    @classmethod
    def _reject_non_relative(cls, value: str) -> str:
        if not is_repo_relative_path(value):
            raise ValueError(
                "file_path must be a non-empty repository relative path"
            )
        return value

    @model_validator(mode="after")
    def _reject_inverted_range(self) -> "ExpectedFinding":
        if self.end_line < self.start_line:
            raise ValueError("end_line must not be smaller than start_line")
        return self


class EvalCase(BaseModel):
    """One evaluation case (code sample plus expected findings)."""

    case_id: str
    language: EvalLanguage
    category: Category
    source: EvalSource
    expected_findings: list[ExpectedFinding] = Field(min_length=1)
    notes: str = ""

    @field_validator("case_id")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("case_id must not be blank")
        return value

    @model_validator(mode="after")
    def _expected_matches_case(self) -> "EvalCase":
        for finding in self.expected_findings:
            if finding.category is not self.category:
                raise ValueError(
                    "expected finding category must match the case "
                    "category"
                )
            if finding.file_path != self.source.file_path:
                raise ValueError(
                    "expected finding file_path must be the case source "
                    "file"
                )
        return self