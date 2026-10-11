"""Evaluation case loader (Phase 8.8).

Loads EvalCase JSON files from the repository level ``test-cases``
directory (``test-cases/<language>/<category>/<case>.json``). The loader
performs no I/O beyond reading the case files: no network, no LLM, no
tool execution.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from app.evaluation.models import EvalCase


def default_cases_root() -> Path:
    """The repository ``test-cases`` directory.

    app/evaluation/loader.py -> parents: evaluation, app, agent, repo root.
    """
    return Path(__file__).resolve().parents[3] / "test-cases"


def load_case(path: Path) -> EvalCase:
    """Load and validate one case file."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"invalid evaluation case JSON: {path}"
        ) from error
    try:
        return EvalCase.model_validate(data)
    except ValidationError as error:
        raise ValueError(f"invalid evaluation case: {path}") from error


def load_cases(root: Path | None = None) -> list[EvalCase]:
    """Load every case below root, ordered by case_id.

    Fails loudly on duplicate case ids so two files can never silently
    overwrite each other in the metrics.
    """
    base = Path(root) if root is not None else default_cases_root()
    if not base.is_dir():
        raise ValueError(f"evaluation cases directory not found: {base}")
    cases = [load_case(path) for path in sorted(base.rglob("*.json"))]
    seen: set[str] = set()
    for case in cases:
        if case.case_id in seen:
            raise ValueError(f"duplicate evaluation case id: {case.case_id}")
        seen.add(case.case_id)
    return sorted(cases, key=lambda case: case.case_id)