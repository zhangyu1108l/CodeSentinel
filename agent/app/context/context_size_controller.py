"""Context size control for a single FileContext (Phase 6.6).

Measures what a prompt may carry and trims it to a ContextBudget:

* measure_context reports the size of one FileContext without changing it;
* apply_context_budget returns an independent copy whose related_code fits
  the budget, together with a ContextStats and a Truncation record.

Only what a prompt may carry counts as prompt_chars: diff hunks, changed
method code, related code and a little metadata. The full file source and
the class bodies kept for later snippet building are reported separately
as retained_source_chars and are never budgeted.

Only a single FileContext is handled. Spreading a budget over several
files (max_total_chars) is a later Phase 6.6 step and must not be added
here. Every function is pure: no IO, no third party dependency and no
mutation of the input.

Trimming rules: related code is dropped whole by priority, except a
NESTED_TYPE whose body exceeds max_item_chars, which degrades to its
declaration header when ClassContext.header_end_line is known.
max_related_chars counts related code characters, without the separators
a prompt would add. Priority selects what to keep; the kept items are
returned in their original order, so a context under budget is left
untouched. Changed code is never removed; when it alone exceeds the
file budget the fact is recorded and the context is returned unchanged.
Every kept range still matches its source slice exactly, so a trimmed
item stays verifiable. Content is untrusted user source code and must
never be written to logs.
"""

import math
import re

from app.context.file_context_builder import split_lines
from app.context.source_scanner import code_slice
from app.schemas.code_context import (
    ContextBudget,
    ContextStats,
    FileContext,
    RelatedCodeContext,
    RelatedKind,
    RelatedReason,
    Truncation,
)

DEFAULT_BUDGET = ContextBudget()

REASON_ITEM_OVERFLOW = "single item exceeds max_item_chars"
REASON_RELATED_BUDGET = "related budget exceeded"
REASON_FILE_BUDGET = "file budget exceeded"
REASON_CHANGED_OVERFLOW = "changed code exceeds file budget"

_PAYLOAD_ORDER = ("metadata", "diff", "changed_methods", "related")

_REASON_RANK = {
    RelatedReason.SIBLING_OF_CHANGED_METHOD: 0,
    RelatedReason.MEMBER_OF_CHANGED_CLASS: 1,
}

_KIND_RANK = {
    RelatedKind.METHOD: 0,
    RelatedKind.FIELD: 1,
    RelatedKind.CONSTRUCTOR: 2,
    RelatedKind.NESTED_TYPE: 3,
}

_CJK_PATTERN = re.compile(
    "["
    "\u2e80-\u2fff"  # CJK radicals
    "\u3000-\u303f"  # CJK punctuation
    "\u3040-\u30ff"  # kana
    "\u31f0-\u31ff"  # kana extensions
    "\u3400-\u4dbf"  # CJK unified ideographs extension A
    "\u4e00-\u9fff"  # CJK unified ideographs
    "\uf900-\ufaff"  # compatibility ideographs
    "\ufe30-\ufe4f"  # CJK compatibility forms
    "\uff00-\uffef"  # fullwidth forms
    "]"
)

_OTHER_CHARS_PER_TOKEN = 3
_CJK_CHARS_PER_TOKEN = 1


def estimate_tokens(text: str) -> int:
    """Conservative token estimate for mixed Java and Python source text.

    Non CJK characters count three per token, deliberately below the four
    characters per token typical for code, and every CJK character counts
    as one token. The result is therefore a slight over-estimate on
    purpose. Empty text yields 0.
    """
    if not text:
        return 0

    cjk_chars = len(_CJK_PATTERN.findall(text))
    other_chars = len(text) - cjk_chars
    return (
        math.ceil(other_chars / _OTHER_CHARS_PER_TOKEN)
        + cjk_chars * _CJK_CHARS_PER_TOKEN
    )


def measure_context(file_context: FileContext) -> ContextStats:
    """Size of one FileContext without changing it.

    prompt_chars counts the concatenation of the four prompt payloads in
    _PAYLOAD_ORDER, estimated_tokens estimates that same concatenation,
    and retained_source_chars reports the source kept in memory for later
    snippet building. All counters describe the given context as is.
    """
    payloads = _payloads(file_context, file_context.related_code)
    prompt_chars_by_kind = {
        kind: len(payloads[kind]) for kind in _PAYLOAD_ORDER
    }
    related = file_context.related_code

    return ContextStats(
        prompt_chars=sum(prompt_chars_by_kind.values()),
        prompt_chars_by_kind=prompt_chars_by_kind,
        estimated_tokens=estimate_tokens(
            "".join(payloads[kind] for kind in _PAYLOAD_ORDER)
        ),
        related_total=len(related),
        related_kept=len(related),
        related_dropped=0,
        truncated_items=sum(1 for item in related if item.truncated),
        retained_source_chars=_retained_source_chars(file_context),
    )


def apply_context_budget(
    file_context: FileContext,
    budget: ContextBudget | None = None,
) -> FileContext:
    """Return a copy of file_context whose related_code fits the budget.

    The input, its methods, classes and content are never mutated. Related
    code is dropped whole from the lowest priority upwards, a NESTED_TYPE
    too large to fit may degrade to its declaration header, and changed
    code is never removed. A call that removes nothing carries the records
    of a previous call over unchanged, which keeps repeated calls stable.
    """
    limits = budget if budget is not None else DEFAULT_BUDGET
    related_before = list(file_context.related_code)
    ordered = sorted(
        enumerate(related_before),
        key=lambda pair: _priority_key(
            pair[1], file_context.file_diff.changed_ranges
        ),
    )

    reasons: list[str] = []
    dropped_originals: list[RelatedCodeContext] = []
    kept_entries: list[
        tuple[int, RelatedCodeContext, RelatedCodeContext, bool]
    ] = []
    kept_chars = 0

    for position, item in ordered:
        candidate, action = _fit_item(item, file_context, limits)
        if candidate is None:
            dropped_originals.append(item)
            _add_reason(reasons, REASON_ITEM_OVERFLOW)
            continue
        if kept_chars + len(candidate.code) > limits.max_related_chars:
            dropped_originals.append(item)
            _add_reason(reasons, REASON_RELATED_BUDGET)
            continue
        kept_entries.append((position, item, candidate, action == "trim"))
        kept_chars += len(candidate.code)
        if action == "trim":
            _add_reason(reasons, REASON_ITEM_OVERFLOW)

    probe = file_context.model_copy(
        update={"related_code": [entry[2] for entry in kept_entries]}
    )
    while (
        kept_entries
        and measure_context(probe).prompt_chars > limits.max_file_chars
    ):
        _, original, _, _ = kept_entries.pop()
        probe = file_context.model_copy(
            update={"related_code": [entry[2] for entry in kept_entries]}
        )
        dropped_originals.append(original)
        _add_reason(reasons, REASON_FILE_BUDGET)

    kept = [
        entry[2]
        for entry in sorted(kept_entries, key=lambda entry: entry[0])
    ]
    trims = [(entry[1], entry[2]) for entry in kept_entries if entry[3]]

    changed_only = file_context.model_copy(update={"related_code": []})
    if measure_context(changed_only).prompt_chars > limits.max_file_chars:
        _add_reason(reasons, REASON_CHANGED_OVERFLOW)

    dropped_descriptions = [_describe(item) for item in dropped_originals]
    trimmed_descriptions = [
        f"related:{original.kind.value}:{original.name} "
        f"({original.start_line}-{original.end_line} -> "
        f"{trimmed.start_line}-{trimmed.end_line})"
        for original, trimmed in trims
    ]
    removed_chars = sum(len(item.code) for item in dropped_originals) + sum(
        len(original.code) - len(trimmed.code)
        for original, trimmed in trims
    )
    new_cuts = bool(dropped_originals or trims)

    result = file_context.model_copy(update={"related_code": kept})
    result = result.model_copy(
        update={
            "truncation": _truncation_for(
                file_context,
                dropped_descriptions,
                trimmed_descriptions,
                reasons,
                removed_chars,
            )
        }
    )

    if new_cuts:
        stats = measure_context(result).model_copy(
            update={
                "related_total": len(related_before),
                "related_kept": len(kept),
                "related_dropped": len(dropped_originals),
                "truncated_items": len(trims),
            }
        )
    else:
        stats = file_context.stats or measure_context(result)

    return result.model_copy(update={"stats": stats})


def _payloads(
    file_context: FileContext, related: list[RelatedCodeContext]
) -> dict[str, str]:
    """Text a prompt may carry, split by kind, in _PAYLOAD_ORDER keys."""
    file_diff = file_context.file_diff
    diff_chunks: list[str] = []
    for hunk in file_diff.hunks:
        diff_chunks.append(hunk.header)
        diff_chunks.extend(line.text for line in hunk.lines)

    metadata = [
        file_diff.path,
        file_diff.status.value,
        file_diff.language.value,
        str(file_diff.additions),
        str(file_diff.deletions),
    ]
    if file_context.enclosing_class:
        metadata.append(file_context.enclosing_class)

    return {
        "metadata": " ".join(metadata),
        "diff": "\n".join(diff_chunks),
        "changed_methods": "\n".join(
            method.code for method in file_context.methods
        ),
        "related": "\n".join(item.code for item in related),
    }


def _retained_source_chars(file_context: FileContext) -> int:
    content = file_context.content
    content_chars = 0
    if content is not None and content.content:
        content_chars = len(content.content)
    return content_chars + sum(
        len(item.code) for item in file_context.classes
    )


def _priority_key(item: RelatedCodeContext, changed_ranges: list) -> tuple:
    """Higher value first: reason, kind, confidence, proximity, stability.

    Mirrors the Related Code builder ordering (reason, then kind, then
    confidence) and adds line distance to the nearest changed range, which
    needs no semantic inference.
    """
    return (
        _REASON_RANK[item.reason],
        _KIND_RANK[item.kind],
        -item.confidence,
        _proximity(item, changed_ranges),
        item.start_line,
        item.name,
    )


def _proximity(item: RelatedCodeContext, changed_ranges: list) -> int:
    """Line distance from the item to the closest changed range, 0 if any."""
    if not changed_ranges:
        return 0

    best: int | None = None
    for changed in changed_ranges:
        if item.end_line < changed.start_line:
            distance = changed.start_line - item.end_line
        elif item.start_line > changed.end_line:
            distance = item.start_line - changed.end_line
        else:
            distance = 0
        best = distance if best is None else min(best, distance)
    return best or 0


def _fit_item(
    item: RelatedCodeContext,
    file_context: FileContext,
    limits: ContextBudget,
) -> tuple[RelatedCodeContext | None, str]:
    """Decide keep, trim or drop for one related item."""
    if len(item.code) <= limits.max_item_chars:
        return item, "keep"

    if (
        item.kind is RelatedKind.NESTED_TYPE
        and limits.allow_nested_header_only
        and not item.truncated
    ):
        candidate = _nested_header_only(item, file_context)
        if candidate is not None and len(candidate.code) <= limits.max_item_chars:
            return candidate, "trim"

    return None, "drop"


def _nested_header_only(
    item: RelatedCodeContext, file_context: FileContext
) -> RelatedCodeContext | None:
    """Degrade a nested type to its declaration header, or None.

    The class must be known to this FileContext and must carry a recorded
    header_end_line that actually shortens the item. The returned copy is
    an exact slice of the new range, so it can still be verified.
    """
    content = file_context.content
    if content is None or content.content is None:
        return None

    class_context = next(
        (
            item_class
            for item_class in file_context.classes
            if item_class.name == item.name
            and item_class.start_line == item.start_line
            and item_class.end_line == item.end_line
        ),
        None,
    )
    if class_context is None:
        return None

    header_end = class_context.header_end_line
    if not item.start_line <= header_end < item.end_line:
        return None

    lines = split_lines(content.content)
    if header_end > len(lines):
        return None

    return item.model_copy(
        update={
            "end_line": header_end,
            "code": code_slice(lines, item.start_line - 1, header_end - 1),
            "truncated": True,
        }
    )


def _truncation_for(
    file_context: FileContext,
    dropped_items: list[str],
    trimmed_items: list[str],
    reasons: list[str],
    removed_chars: int,
) -> Truncation:
    """This call's record; a call with nothing to do carries the old one.

    Reasons without new drops, such as changed code exceeding the budget,
    keep the previous record and only add what is new, so repeated calls
    with the same budget stay stable.
    """
    if dropped_items or trimmed_items:
        return Truncation(
            applied=True,
            reasons=reasons,
            dropped_items=dropped_items,
            trimmed_items=trimmed_items,
            removed_chars=removed_chars,
        )

    if reasons:
        previous = file_context.truncation
        if previous is None:
            return Truncation(applied=True, reasons=reasons)
        merged = list(previous.reasons)
        for reason in reasons:
            _add_reason(merged, reason)
        return previous.model_copy(update={"applied": True, "reasons": merged})

    return file_context.truncation or Truncation()


def _describe(item: RelatedCodeContext) -> str:
    return f"related:{item.kind.value}:{item.name} ({item.start_line}-{item.end_line})"


def _add_reason(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)