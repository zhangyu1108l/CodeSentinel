"""Graph state for the review workflow (Phase 8.1).

The state carries only the review request, the produced result and a
sanitized failure marker (exception type name). It deliberately does not
carry raw exception objects: graph state may be logged or serialized by
later nodes, and raw validation errors can embed input previews.
"""

from typing import TypedDict

from app.schemas.review import ReviewTaskRequest, ReviewTaskResult


class ReviewGraphState(TypedDict, total=False):
    """State passed between review workflow nodes.

    request: the review request accepted by the graph entry point.
    result: the ReviewTaskResult produced by the review node, or None.
    error: sanitized failure marker (exception type name), None on success.
    """

    request: ReviewTaskRequest
    result: ReviewTaskResult | None
    error: str | None