"""PR Context DTOs (Phase 6.7.2).

Mirror the JSON contract returned by the Java endpoint
GET /api/tasks/{taskId}/pr-context. Java camelCase fields keep the same
camelCase mapping already used for Java -> Python DTOs (see TaskMessage),
and the content state fields stay snake_case exactly as the Java response
exposes them: content_available, content_truncated, content_reason.

content is None whenever Java could not read the source; content_reason
then carries one of removed / unsupported_language / too_large / binary /
fetch_failed:<status>. An empty string content is a legitimate empty file
and must not be confused with an unavailable one.
"""

from pydantic import BaseModel, Field


class PrContextFile(BaseModel):
    """One changed file of a pull request context."""

    path: str
    status: str
    previousPath: str | None = None
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None
    blobUrl: str | None = None
    content_available: bool = False
    content_truncated: bool = False
    content_reason: str | None = None
    content: str | None = None


class PrContext(BaseModel):
    """PR context payload for one review task."""

    taskId: int
    owner: str
    repo: str
    prNumber: int
    commitSha: str
    title: str | None = None
    state: str | None = None
    baseRef: str | None = None
    headRef: str | None = None
    files: list[PrContextFile] = Field(default_factory=list)