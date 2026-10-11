"""Planner output contract (Phase 8.3).

The planner may only choose analysis agents from the code-defined
whitelist (the existing Category enum) and may not attach any extra
fields: extra="forbid" rejects attempts to smuggle tools, commands or
code through the plan.
"""

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.review import Category


class AnalysisTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: Category


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[AnalysisTask]

    @model_validator(mode="after")
    def _validate_tasks(self) -> "AnalysisPlan":
        if not self.tasks:
            raise ValueError("plan must contain at least one task")
        agents = [task.agent for task in self.tasks]
        if len(agents) != len(set(agents)):
            raise ValueError("plan must not repeat an agent")
        return self

    @property
    def agents(self) -> list[Category]:
        """Planned agent categories in plan order."""
        return [task.agent for task in self.tasks]