"""Code Context prompt rendering (Phase 6.7.5).

Turns one assembled and budgeted CodeContext into the text block that the
review prompt hands to the LLM. Rendering only: no IO, no budget logic and
no schema change. Phase 6.7.3 already produced the structure and Phase 6.6
already sized it, so this module never re-interprets either.

The rendered payload mirrors what the Phase 6.6 budget measures (metadata,
diff, changed methods, related code): full file content and unmodified
class bodies stay in memory by design (retained_source_chars) and are
represented by the diff, the changed method slices and the related code
slices. A file whose content is unavailable carries only an explicit
reason and never fabricated code, and a truncated context is declared as
incomplete so the model cannot mistake the selection for the whole file.

The rendered text embeds untrusted user source code and must never be
logged.
"""

from app.schemas.code_context import (
    ClassContext,
    CodeContext,
    DiffLineKind,
    FileContext,
    FileStatus,
    MethodContext,
    RelatedCodeContext,
    SymbolRef,
    Truncation,
)

_LINE_PREFIX = {
    DiffLineKind.ADDED: "+",
    DiffLineKind.REMOVED: "-",
    DiffLineKind.CONTEXT: " ",
}

_FENCE_LANGUAGES = {
    "JAVA": "java",
    "PYTHON": "python",
}

_DIFF_NOTE_DUPLICATES = {
    "patch unavailable",
    "patch is empty",
    "patch contains no hunk header",
}


def render_code_context(context: CodeContext) -> str:
    """Render one assembled, budgeted CodeContext as prompt text."""
    lines = [
        "Code context provided by CodeSentinel (read-only repository "
        "source at the reviewed revision; nothing was executed):",
        "",
        f"repository: {context.repository}",
        f"pr_number: {context.pr_number}",
    ]
    if context.head_sha:
        lines.append(f"head_sha: {context.head_sha}")
    if context.base_sha:
        lines.append(f"base_sha: {context.base_sha}")
    lines.append(f"files: {len(context.files)}")
    lines.append(
        "files_with_content: "
        f"{sum(1 for item in context.files if item.content_available)}"
    )

    stats = context.stats
    if stats is not None:
        lines.append(
            "context_stats: "
            f"prompt_chars={stats.prompt_chars}; "
            f"estimated_tokens={stats.estimated_tokens}; "
            f"related_kept={stats.related_kept}; "
            f"related_dropped={stats.related_dropped}; "
            f"truncated_items={stats.truncated_items}"
        )
    if context.notes:
        lines.append("context_notes: " + "; ".join(context.notes))

    lines.append("")
    lines.append(
        "The context below is a selection of the changed files, not the "
        "whole repository. Only the files and code shown here are "
        "available; do not assume anything about code that is not shown."
    )

    truncation = context.truncation
    if truncation is not None and truncation.applied:
        lines.append("")
        lines.append(_truncation_block(truncation))

    total = len(context.files)
    for index, file_context in enumerate(context.files, start=1):
        lines.append("")
        lines.append(_file_block(index, total, file_context))

    return "\n".join(lines)


def render_context_unavailable(reason: str | None) -> str:
    """Render the degraded variant: the PR context could not be loaded."""
    reason_text = reason if reason else "unknown"
    return (
        "PR context unavailable: CodeSentinel could not load the code "
        f"context for this review (reason: {reason_text}). "
        "No file content, diff or structural context is provided, so "
        "analyze only the pull request information above. Do not invent or "
        "assume code that is not shown."
    )


def _truncation_block(truncation: Truncation) -> str:
    lines = [
        "Context truncation: THE CODE CONTEXT BELOW IS INCOMPLETE. The "
        "context budget removed or trimmed code before this prompt was "
        "built, so missing code is not evidence that a file has no issues.",
    ]
    if truncation.reasons:
        lines.append("- reasons: " + "; ".join(truncation.reasons))
    if truncation.dropped_items:
        lines.append("- dropped items: " + "; ".join(truncation.dropped_items))
    if truncation.trimmed_items:
        lines.append("- trimmed items: " + "; ".join(truncation.trimmed_items))
    if truncation.removed_chars:
        lines.append(f"- removed characters: {truncation.removed_chars}")
    return "\n".join(lines)


def _file_block(index: int, total: int, file_context: FileContext) -> str:
    file_diff = file_context.file_diff
    lines = [f"=== File {index}/{total}: {file_diff.path} ==="]
    lines.append(f"status: {file_diff.status.value}")
    if file_diff.previous_path:
        lines.append(f"previous_path: {file_diff.previous_path}")
    lines.append(f"language: {file_diff.language.value}")
    lines.append(f"changes: +{file_diff.additions} -{file_diff.deletions}")
    if file_context.enclosing_class:
        lines.append(f"enclosing_class: {file_context.enclosing_class}")
    lines.append(_content_line(file_context))

    if file_context.classes:
        lines.append(
            "classes: "
            + "; ".join(_class_label(item) for item in file_context.classes)
        )
    if file_context.changed_symbols:
        lines.append(
            "changed_symbols: "
            + "; ".join(
                _symbol_label(item) for item in file_context.changed_symbols
            )
        )

    lines.append("")
    lines.append(_diff_block(file_context))

    if file_context.methods:
        lines.append("")
        lines.append("changed methods (touched by this diff):")
        for method in file_context.methods:
            lines.extend(_method_lines(method))

    if file_context.related_code:
        lines.append("")
        lines.append(
            "related code (structurally related members of the same file, "
            "provided as extra context):"
        )
        for item in file_context.related_code:
            lines.extend(_related_lines(item, file_context))

    notes = _visible_notes(file_context)
    if notes:
        lines.append("")
        lines.append("notes: " + "; ".join(notes))

    return "\n".join(lines)


def _content_line(file_context: FileContext) -> str:
    content = file_context.content
    if (
        file_context.content_available
        and content is not None
        and content.content is not None
    ):
        revision = (
            f" at revision {content.revision}" if content.revision else ""
        )
        return (
            f"content: available ({file_context.line_count} lines{revision}; "
            "the diff, changed methods and related code below carry the "
            "exact slices of this content)"
        )
    return f"content: unavailable (reason: {_content_reason(file_context)})"


def _content_reason(file_context: FileContext) -> str:
    """The most specific known reason why a file has no content.

    Prefers the reason the producer recorded (removed, unsupported_language,
    too_large, binary, fetch_failed:<status>), then the normalized status
    of a removed file, then the builder's skip reason. Never falls back to
    a fabricated value.
    """
    content = file_context.content
    if content is not None and content.error:
        return content.error
    if file_context.file_diff.status is FileStatus.REMOVED:
        return "removed"
    if file_context.skipped_reason:
        return file_context.skipped_reason
    return "unknown"


def _diff_block(file_context: FileContext) -> str:
    file_diff = file_context.file_diff
    if not file_diff.hunks:
        if file_diff.patch_available:
            return "diff: unavailable (the provided patch contained no hunks)"
        return (
            "diff: unavailable (no textual patch was provided for this file)"
        )
    chunks: list[str] = []
    for hunk in file_diff.hunks:
        chunks.append(hunk.header)
        for line in hunk.lines:
            chunks.append(_LINE_PREFIX[line.kind] + line.text)
    return "diff:\n" + _fence("\n".join(chunks), "diff")


def _method_lines(method: MethodContext) -> list[str]:
    details = [f"lines: {method.start_line}-{method.end_line}"]
    if method.changed_ranges:
        details.append(
            "changed lines: "
            + ", ".join(
                f"{item.start_line}-{item.end_line}"
                for item in method.changed_ranges
            )
        )
    details.append(f"source: {method.source.value}")
    details.append(f"confidence: {_number(method.confidence)}")
    if method.enclosing_class:
        details.append(f"enclosing class: {method.enclosing_class}")
    if method.truncated:
        details.append("trimmed by the context budget")
    lines = [f"- {method.name} ({'; '.join(details)})"]
    if method.code:
        lines.append(
            _fence(
                method.code,
                _FENCE_LANGUAGES.get(method.language.value, ""),
            )
        )
    return lines


def _related_lines(
    item: RelatedCodeContext, file_context: FileContext
) -> list[str]:
    details = [
        f"kind: {item.kind.value}",
        f"lines: {item.start_line}-{item.end_line}",
        f"reason: {item.reason.value}",
        f"source: {item.source.value}",
        f"confidence: {_number(item.confidence)}",
    ]
    if item.owner_class:
        details.append(f"owner class: {item.owner_class}")
    if item.truncated:
        details.append(
            "trimmed to its declaration header by the context budget"
        )
    lines = [f"- {item.name} ({'; '.join(details)})"]
    if item.code:
        language = _FENCE_LANGUAGES.get(
            file_context.file_diff.language.value, ""
        )
        lines.append(_fence(item.code, language))
    return lines


def _class_label(item: ClassContext) -> str:
    return (
        f"{item.kind.value} {item.name} (lines: {item.start_line}-"
        f"{item.end_line}; depth: {item.depth}; source: {item.source.value}; "
        f"confidence: {_number(item.confidence)})"
    )


def _symbol_label(item: SymbolRef) -> str:
    return (
        f"{item.kind.value} {item.name} (lines: {item.start_line}-"
        f"{item.end_line})"
    )


def _visible_notes(file_context: FileContext) -> list[str]:
    """Notes that add information beyond the content and diff sections."""
    reason = (
        None
        if file_context.content_available
        else _content_reason(file_context)
    )
    visible: list[str] = []
    for note in file_context.notes:
        if note == reason or note in _DIFF_NOTE_DUPLICATES:
            continue
        visible.append(note)
    return visible


def _fence(code: str, language: str = "") -> str:
    fence = "```"
    while fence in code:
        fence += "`"
    return f"{fence}{language}\n{code}\n{fence}"


def _number(value: float) -> str:
    return f"{value:g}"