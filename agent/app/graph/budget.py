"""Shared budget context for review graph nodes (Phase 8.2).

One graph run owns exactly one RequestBudget (monotonic deadline). Nodes
receive ReviewBudgetContext and may only use what is left: node_timeout
and llm_timeout cap a node's local allowance by the shared remaining
time, so a later node never restarts the full REVIEW_TOTAL_BUDGET.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.config.settings import settings
from app.services.request_budget import RequestBudget


class NodeBudgetExhaustedError(Exception):
    """A node cannot start because the shared review budget is spent."""


@dataclass(frozen=True)
class ReviewBudgetContext:
    """The single shared budget of one review graph run."""

    budget: RequestBudget

    @classmethod
    def create(
        cls,
        seconds: float = None,
        clock: Callable[[], float] = None,
    ) -> "ReviewBudgetContext":
        """Create a context; defaults to settings.REVIEW_TOTAL_BUDGET."""
        if seconds is None:
            seconds = settings.REVIEW_TOTAL_BUDGET
        if clock is None:
            return cls(RequestBudget(seconds))
        return cls(RequestBudget(seconds, clock=clock))

    @property
    def total_seconds(self) -> float:
        """The configured total budget of this run."""
        return self.budget.seconds

    def remaining(self) -> float:
        """Seconds left of the shared budget, never negative."""
        return self.budget.remaining()

    def expired(self) -> bool:
        """Whether the shared budget is already spent."""
        return self.budget.expired()

    def node_timeout(self, local_cap_seconds: float) -> float:
        """Timeout for one node: its local cap or what is left, whichever
        is smaller."""
        return self.budget.limit(local_cap_seconds)

    def llm_timeout(self, local_cap_seconds: float) -> float:
        """Timeout for one LLM call: its local cap or what is left,
        whichever is smaller."""
        return self.budget.limit(local_cap_seconds)

    def start_node(self, local_cap_seconds: float) -> float:
        """Return the node timeout, refusing to start when exhausted."""
        if self.expired():
            raise NodeBudgetExhaustedError(
                "shared review budget exhausted before the node started"
            )
        return self.node_timeout(local_cap_seconds)