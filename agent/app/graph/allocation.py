"""Bounded node budget allocation for the analysis workflow (Phase 8.7).

One analysis run owns exactly one RequestBudget (Phase 8.2). On top of
that shared deadline, every LLM calling node receives a bounded
allowance computed at node start:

    allowance = min(local_cap_seconds, remaining_seconds / stages_left)

- stages_left is the number of stages that still need time, known at the
  node boundary (the planner reserves room for at least one downstream
  agent; each agent shares the remaining time with the agents still to
  run). The planner knows how many agent nodes are still pending from
  its own plan.
- The allowance is recomputed from the remaining budget at every node
  start and is never a fresh full budget: a node can never reset the
  shared deadline.
- The allowance is only a cap. The node timeout and the LLM timeout are
  both derived from it, so no node or LLM call can outlive its share,
  and the total of the actual waits stays bounded by the shared budget
  plus at most one local overrun per node (subprocess work that cannot
  be cancelled is already bounded by its own stage share in
  StaticAnalysisService).

The function is pure, so the policy is unit tested without running a
graph or waiting for real time.
"""

import math


def node_allowance(
    remaining_seconds: float,
    stages_left: int,
    local_cap_seconds: float,
) -> float:
    """Bounded time allowance for one stage of the shared budget.

    Returns the smaller of the stage's local cap and an equal share of
    the remaining budget. Callers reject a value that is not positive
    before starting the stage, so zero remaining time can never start
    new work.
    """
    if (
        isinstance(remaining_seconds, bool)
        or not isinstance(remaining_seconds, (int, float))
        or not math.isfinite(remaining_seconds)
        or remaining_seconds < 0
    ):
        raise ValueError(
            "remaining_seconds must be a finite non-negative number"
        )
    if (
        isinstance(stages_left, bool)
        or not isinstance(stages_left, int)
        or stages_left < 1
    ):
        raise ValueError("stages_left must be an integer of at least 1")
    if (
        isinstance(local_cap_seconds, bool)
        or not isinstance(local_cap_seconds, (int, float))
        or not math.isfinite(local_cap_seconds)
        or local_cap_seconds <= 0
    ):
        raise ValueError(
            "local_cap_seconds must be a positive finite number"
        )
    return min(float(local_cap_seconds), float(remaining_seconds) / stages_left)