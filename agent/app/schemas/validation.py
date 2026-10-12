"""Safe diagnostics for Pydantic ValidationError objects.

Pydantic's default display of a ValidationError embeds a preview of the
validated input (``input_value=...``). Depending on the model, that input
can contain LLM output, source code fragments or file content, so a raw
ValidationError - or its chained cause - must never reach logs or
externally visible error messages. This helper exposes only non sensitive
facts: the error count, the offending field locations and the error types.
"""

from pydantic import ValidationError

_MAX_DETAILS = 5


def validation_error_summary(error: ValidationError) -> str:
    """Return a bounded, input free summary of a validation error."""
    details: list[str] = []
    for item in error.errors(include_input=False):
        location = ".".join(str(part) for part in item.get("loc", ()))
        details.append(f"{location or '$'}[{item.get('type', '?')}]")
    summary = f"{error.error_count()} schema error(s)"
    if not details:
        return summary
    shown = ", ".join(details[:_MAX_DETAILS])
    if len(details) > _MAX_DETAILS:
        shown += ", ..."
    return f"{summary}: {shown}"