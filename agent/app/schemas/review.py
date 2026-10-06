from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    BUG = "BUG"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    QUALITY = "QUALITY"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ReviewTaskRequest(BaseModel):
    task_id: int
    repository: str
    pr_number: int
    commit_sha: str
    files: list[str] = Field(default_factory=list)


class ReviewFinding(BaseModel):
    category: Category
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    rule_id: str
    title: str
    file_path: str
    start_line: int
    end_line: int
    description: str
    reason: str
    suggestion: str
    references: list[str]


class ReviewTaskResult(BaseModel):
    task_id: int
    status: str
    report: dict
    findings: list[ReviewFinding]
