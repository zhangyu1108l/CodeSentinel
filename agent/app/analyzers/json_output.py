"""JSON output boundary for static analysis tools (Phase 7.2).

A tool's stdout is never assumed to be JSON: parsing either succeeds or
the result is explicitly EMPTY / INVALID, so arbitrary text such as a log
line or an error message can never be silently accepted as structured
output. No exception text, raw output or source code becomes part of the
returned model; only a finite StaticAnalysisErrorCode is exposed.
"""

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, model_validator

from app.schemas.static_analysis import StaticAnalysisErrorCode


class JsonStatus(str, Enum):
    """Whether one stdout capture carried parseable JSON."""

    VALID = "VALID"
    EMPTY = "EMPTY"
    INVALID = "INVALID"


class JsonParseResult(BaseModel):
    """Outcome of parsing one stdout capture as JSON.

    VALID carries the decoded JSON value in data, which may itself be
    null, an empty list or any other JSON value. EMPTY means the capture
    was empty or whitespace only. INVALID means non empty text that is not
    valid JSON. EMPTY and INVALID both carry INVALID_OUTPUT and never
    carry data.
    """

    status: JsonStatus
    data: Any = None
    error_code: StaticAnalysisErrorCode | None = None

    @model_validator(mode="after")
    def _enforce_parse_contract(self) -> "JsonParseResult":
        if self.status == JsonStatus.VALID:
            if self.error_code is not None:
                raise ValueError(
                    "valid JSON must not carry an error_code"
                )
        else:
            if self.error_code != StaticAnalysisErrorCode.INVALID_OUTPUT:
                raise ValueError(
                    "non valid JSON must carry INVALID_OUTPUT"
                )
        return self


def parse_json_output(stdout: str) -> JsonParseResult:
    """Parse a captured stdout as JSON, separating the failure modes.

    Leading and trailing whitespace around a JSON document is tolerated.
    Anything else that is not one valid JSON value is INVALID: plain text
    is never treated as a successful parse. The exception detail of a
    malformed document is deliberately discarded.
    """
    if not stdout or not stdout.strip():
        return JsonParseResult(
            status=JsonStatus.EMPTY,
            error_code=StaticAnalysisErrorCode.INVALID_OUTPUT,
        )
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, RecursionError):
        return JsonParseResult(
            status=JsonStatus.INVALID,
            error_code=StaticAnalysisErrorCode.INVALID_OUTPUT,
        )
    return JsonParseResult(status=JsonStatus.VALID, data=data)