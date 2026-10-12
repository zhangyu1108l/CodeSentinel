"""Request time budget for one review request (Phase 8 timeout governance).

One review request is handled by several stages with their own local
timeouts (PR context fetch, DeepSeek call) and an outer HTTP client
timeout in the worker. Without a shared budget every stage could wait for
its own full timeout, so the total could exceed the worker's patience and
leave orphan work behind. RequestBudget carries one monotonic deadline:

- remaining() is the time left before the deadline, never negative.
- limit(local_seconds) returns the smaller of a stage's local timeout and
  the remaining budget, so a local cap can never outlive the request.
- expired() marks the deadline as reached.

The clock is injectable for tests. A budget must be a positive finite
number; zero, negative, NaN and infinite budgets are caller defects and
are rejected instead of being silently accepted.
"""

import math
import time
from collections.abc import Callable


class ReviewBudgetExceededError(Exception):
    """The review ran out of its total request budget.

    This is a fatal review error, never a success: it is raised instead of
    returning a result whenever the budget is used up before or during the
    LLM analysis, so the existing failure path (worker retry) applies.
    """


class RequestBudget:
    """Monotonic deadline shared by all stages of one request."""

    def __init__(
        self,
        seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        if (
            isinstance(seconds, bool)
            or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds)
            or seconds <= 0
        ):
            raise ValueError("seconds must be a positive finite number")
        self._seconds = float(seconds)
        self._clock = clock
        self._deadline = clock() + self._seconds

    @property
    def seconds(self) -> float:
        """The configured total budget in seconds."""
        return self._seconds

    def remaining(self) -> float:
        """Seconds left before the deadline, never negative."""
        return max(0.0, self._deadline - self._clock())

    def expired(self) -> bool:
        """Whether the deadline has been reached."""
        return self.remaining() <= 0.0

    def limit(self, local_seconds: float) -> float:
        """The smaller of a stage local timeout and the remaining budget."""
        return min(local_seconds, self.remaining())