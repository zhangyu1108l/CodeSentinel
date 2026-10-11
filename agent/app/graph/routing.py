"""Conditional routing helpers for review graphs (Phase 8.2).

The routing decision is a pure function over the graph state so it can be
unit tested without compiling or running a graph. Phase 8.3 uses it as
the conditional edge after the planner and after every analysis node.
"""

from langgraph.graph import END

from app.graph.state import ReviewGraphState, ReviewGraphStatus

STOP_STATUSES = frozenset(
    {
        ReviewGraphStatus.UNRECOVERABLE_ERROR,
        ReviewGraphStatus.BUDGET_EXHAUSTED,
    }
)


def select_next_node(state: ReviewGraphState) -> str | None:
    """Next planned node that has not completed, or None to finish.

    Returns None immediately when the run reached a terminal stop status
    (unrecoverable failure or budget exhaustion), otherwise walks
    state["planned_nodes"] in order and picks the first node id that is
    not in state["completed_nodes"].
    """
    if state.get("status") in STOP_STATUSES:
        return None
    completed = set(state.get("completed_nodes", []))
    for node_id in state.get("planned_nodes", []):
        if node_id not in completed:
            return node_id
    return None


def route_next(state: ReviewGraphState) -> str:
    """Conditional-edge target: the next planned node id or END."""
    return select_next_node(state) or END