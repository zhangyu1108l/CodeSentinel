"""Unified analysis finding and report contract (Phase 8.7).

One analysis run merges findings from the dimension agents (LLM output
with confidence and evidence texts) and from the deterministic static
analysis tools (no confidence, tool metadata only). The merged
representation keeps both provenance and tool metadata; agent-only fields
stay None for static findings instead of being invented, so a valid tool
finding never needs an LLM style description to survive aggregation.

The report is the stable output of the analysis pipeline (Reporter):
findings, severity summary, per agent execution state, static tool status
and explicit degraded flags. Failures, skipped stages and partial runs are
never converted into a clean zero-finding success.
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.review import Category, Severity
from app.schemas.static_analysis import (
    StaticAnalysisTool,
    is_repo_relative_path,
)


class FindingSource(str, Enum):
    """Producer of one merged finding."""

    AGENT = "AGENT"
    STATIC = "STATIC"


class ReportStatus(str, Enum):
    """Stable status of one analysis report."""

    COMPLETED = "COMPLETED"
    DEGRADED = "DEGRADED"


class AnalysisFinding(BaseModel):
    """One merged finding of an analysis run.

    sources lists every producer of this issue in merge order (AGENT first
    when an agent finding was merged with static evidence). Agent findings
    carry agent / confidence / title / reason / suggestion; static findings
    carry tool and leave the agent-only fields None. rule_id and message
    must not be blank; the line range must not be inverted.
    """

    sources: list[FindingSource] = Field(min_length=1)
    category: Category
    severity: Severity
    rule_id: str
    message: str
    file_path: str
    start_line: int = Field(ge=1)
    end_line: int
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    title: str | None = None
    reason: str | None = None
    suggestion: str | None = None
    references: list[str] = Field(default_factory=list)
    agent: Category | None = None
    tool: StaticAnalysisTool | None = None

    @field_validator("rule_id", "message")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be blank")
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
    def _reject_inverted_range(self) -> "AnalysisFinding":
        if self.end_line < self.start_line:
            raise ValueError("end_line must not be smaller than start_line")
        return self


class AnalysisReport(BaseModel):
    """Stable result structure of one analysis pipeline run.

    findings is the merged, deduplicated finding list; severity_counts
    always contains every severity (zeros included); planned_agents /
    executed_agents / failed_agents / skipped_agents make node level
    outcomes explicit, so a run that never executed an agent cannot be
    mistaken for a clean zero-finding result. context, static_analysis and
    validation carry the safe status summaries of their stages; degraded
    is True as soon as any stage was incomplete or failed.
    """

    task_id: int
    repository: str
    pr_number: int
    commit_sha: str
    status: ReportStatus
    degraded: bool
    findings: list[AnalysisFinding] = Field(default_factory=list)
    finding_count: int = Field(ge=0)
    severity_counts: dict[str, int] = Field(default_factory=dict)
    source_counts: dict[str, int] = Field(default_factory=dict)
    duplicates_merged: int = Field(default=0, ge=0)
    planned_agents: list[Category] = Field(default_factory=list)
    executed_agents: list[Category] = Field(default_factory=list)
    failed_agents: list[Category] = Field(default_factory=list)
    skipped_agents: list[Category] = Field(default_factory=list)
    recoverable_errors: list[str] = Field(default_factory=list)
    context: dict | None = None
    static_analysis: dict | None = None
    validation: dict | None = None
    notes: list[str] = Field(default_factory=list)