"""Class Context location (Phase 6.4).

Answers one question for every MethodContext: which class, interface,
enum, record or annotation type declares it. It reuses the scanning
primitives of source_scanner, so Method Context and Class Context share a
single masking, brace and indentation strategy instead of two parsers.

Ranges are inclusive and 1-based, start_line covers leading annotations or
decorators, end_line is the closing brace for Java and the last indented
line for Python, and code is the exact slice between them. Anonymous
classes are deliberately not turned into ClassContext because they have no
name to report; their body is tracked separately so a method inside one is
left without an enclosing class instead of being attributed to the
surrounding named type.

Everything degrades to "no class found". Nothing raises, and no input
object is mutated. Content is untrusted user source code and must never be
written to logs.
"""

import re

from app.context.file_context_builder import split_lines
from app.context.source_scanner import (
    JAVA_INLINE_ANNOTATION,
    code_slice,
    declaration_signature,
    indent_width,
    java_annotation_start,
    java_body_end,
    java_declaration_end,
    mask_java,
    mask_python,
    python_block_end,
    python_decorator_start,
    python_header_end,
)
from app.schemas.code_context import (
    ClassContext,
    FileContext,
    Language,
    MethodContext,
    SymbolSource,
    TypeKind,
)

CONFIDENCE_JAVA_TYPE = 0.9
CONFIDENCE_PYTHON_TYPE = 0.85

_JAVA_TYPE_KEYWORDS = {
    "class": TypeKind.CLASS,
    "interface": TypeKind.INTERFACE,
    "enum": TypeKind.ENUM,
    "record": TypeKind.RECORD,
    "@interface": TypeKind.ANNOTATION_TYPE,
}

_JAVA_MODIFIERS = (
    r"(?:(?:public|protected|private|static|final|abstract|sealed"
    r"|non-sealed|strictfp)[ \t]+)*"
)

_JAVA_TYPE_TAIL = (
    r"(?=[ \t]*(?:<[^;{}]*>)?[ \t]*"
    r"(?:\(|extends\b|implements\b|permits\b|\{|$))"
)

_JAVA_TYPE_DECL_RE = re.compile(
    r"^[ \t]*"
    + JAVA_INLINE_ANNOTATION
    + _JAVA_MODIFIERS
    + r"(?P<kind>@interface|class|interface|enum|record)"
    r"[ \t]+(?P<name>[\w$]+)"
    + _JAVA_TYPE_TAIL
)

_JAVA_ANONYMOUS_RE = re.compile(
    r"\bnew[ \t]+[\w$.]+[ \t]*(?:<[^;{}()]*>)?[ \t]*\("
)

_PYTHON_CLASS_RE = re.compile(
    r"^(?P<indent>[ \t]*)class[ \t]+(?P<name>[A-Za-z_]\w*)"
)


def find_classes(content: str, language: Language) -> list[ClassContext]:
    """Locate every named type declaration in one file.

    Nested and local types are included; depth counts how many other types
    of the same file enclose them, so depth 0 means a top level type.
    """
    if not content or language is Language.OTHER:
        return []

    lines = split_lines(content)
    if not lines:
        return []

    if language is Language.JAVA:
        return _find_java_classes(lines, mask_java(lines))

    masked, in_triple = mask_python(lines)
    return _find_python_classes(lines, masked, in_triple)


def find_anonymous_regions(content: str, language: Language) -> list[tuple[int, int]]:
    """Inclusive 1-based line ranges of Java anonymous class bodies."""
    if not content or language is not Language.JAVA:
        return []

    lines = split_lines(content)
    if not lines:
        return []

    masked = mask_java(lines)
    regions: list[tuple[int, int]] = []

    for index, text in enumerate(masked):
        for match in _JAVA_ANONYMOUS_RE.finditer(text):
            declaration_end = java_declaration_end(masked, index, match.end() - 1)
            if declaration_end is None:
                continue
            brace_line, brace_column, has_body = declaration_end
            if not has_body:
                continue
            body_end = java_body_end(masked, brace_line, brace_column)
            if body_end is None:
                continue
            regions.append((index + 1, body_end + 1))

    return regions


def innermost_scope(
    classes: list[ClassContext],
    line: int,
    anonymous_regions: list[tuple[int, int]] | None = None,
) -> tuple[int, int, str | None, ClassContext | None] | None:
    """Innermost scope around one line as (start, end, name, class).

    The innermost scope wins, so a line of a nested type resolves to the
    nested type and not to the outer one. An anonymous class body counts as
    a scope without a name and without a ClassContext, which is how a
    method inside one stays unattributed instead of being handed to the
    surrounding named type.
    """
    best: tuple[int, int, str | None, ClassContext | None] | None = None

    for item in classes:
        if item.start_line <= line <= item.end_line:
            best = _closer(
                best, (item.start_line, item.end_line, item.name, item)
            )

    for start, end in anonymous_regions or []:
        if start <= line <= end:
            best = _closer(best, (start, end, None, None))

    return best


def innermost_class(
    classes: list[ClassContext],
    line: int,
    anonymous_regions: list[tuple[int, int]] | None = None,
) -> ClassContext | None:
    """Named type directly enclosing one line, None inside anonymous bodies."""
    scope = innermost_scope(classes, line, anonymous_regions)
    return None if scope is None else scope[3]


def enclosing_class_name(
    classes: list[ClassContext],
    method: MethodContext,
    anonymous_regions: list[tuple[int, int]] | None = None,
) -> str | None:
    """Name of the innermost type around a method declaration.

    The innermost scope wins, so a method of a nested class belongs to the
    nested class and not to the outer one. An anonymous class body counts
    as a scope without a name, which yields None instead of attributing
    the method to the surrounding named type.
    """
    scope = innermost_scope(classes, method.start_line, anonymous_regions)
    return None if scope is None else scope[2]


def build_class_contexts(file_context: FileContext) -> list[ClassContext]:
    """Type declarations of one FileContext, empty when content is unusable."""
    classes, _ = _scan(file_context)
    return classes


def attach_class_contexts(file_context: FileContext) -> FileContext:
    """Return a copy of file_context with class level context filled in.

    classes lists every named type of the file, each method of
    file_context.methods learns its nearest enclosing type, and the file
    level enclosing_class is set only when it is unambiguous. The input is
    never mutated and no exception escapes for unreadable content.
    """
    classes, anonymous_regions = _scan(file_context)
    methods = [
        method.model_copy(
            update={
                "enclosing_class": enclosing_class_name(
                    classes, method, anonymous_regions
                )
            }
        )
        for method in file_context.methods
    ]

    return file_context.model_copy(
        update={
            "classes": classes,
            "methods": methods,
            "enclosing_class": _resolve_enclosing_class(classes, methods),
        }
    )


def _scan(file_context: FileContext) -> tuple[list[ClassContext], list[tuple[int, int]]]:
    content = file_context.content
    if (
        not file_context.content_available
        or content is None
        or content.content is None
    ):
        return [], []

    language = file_context.file_diff.language
    classes = find_classes(content.content, language)
    return classes, find_anonymous_regions(content.content, language)


def _resolve_enclosing_class(
    classes: list[ClassContext], methods: list[MethodContext]
) -> str | None:
    """File level enclosing type, set only when it cannot be a guess.

    With methods attached the unique enclosing type of those methods wins.
    Without methods a file declaring exactly one top level type uses that
    type. Anything ambiguous stays None.
    """
    if methods:
        names = {
            method.enclosing_class for method in methods if method.enclosing_class
        }
        if len(names) == 1:
            return next(iter(names))
        return None

    top_level = [item.name for item in classes if item.depth == 0]
    if len(top_level) == 1:
        return top_level[0]
    return None


def _closer(
    best: tuple[int, int, str | None, ClassContext | None] | None,
    candidate: tuple[int, int, str | None, ClassContext | None],
) -> tuple[int, int, str | None, ClassContext | None]:
    if best is None:
        return candidate
    if candidate[0] > best[0] or (
        candidate[0] == best[0] and candidate[1] < best[1]
    ):
        return candidate
    return best


def _find_java_classes(lines: list[str], masked: list[str]) -> list[ClassContext]:
    classes: list[ClassContext] = []

    for index, text in enumerate(masked):
        match = _JAVA_TYPE_DECL_RE.match(text)
        if match is None:
            continue

        declaration_end = java_declaration_end(masked, index, 0)
        if declaration_end is None:
            continue
        brace_line, brace_column, has_body = declaration_end
        if not has_body:
            continue

        body_end = java_body_end(masked, brace_line, brace_column)
        if body_end is None:
            continue

        start_index = java_annotation_start(masked, index)
        classes.append(
            _make_class(
                lines=lines,
                name=match.group("name"),
                kind=_JAVA_TYPE_KEYWORDS[match.group("kind")],
                language=Language.JAVA,
                start_index=start_index,
                decl_index=index,
                signature_end_index=brace_line,
                signature_end_column=brace_column,
                include_terminator=False,
                end_index=body_end,
                confidence=CONFIDENCE_JAVA_TYPE,
            )
        )

    return _assign_depths(_dedupe_classes(classes))


def _find_python_classes(
    lines: list[str], masked: list[str], in_triple: list[bool]
) -> list[ClassContext]:
    classes: list[ClassContext] = []

    for index, text in enumerate(masked):
        if in_triple[index]:
            continue
        match = _PYTHON_CLASS_RE.match(text)
        if match is None:
            continue

        header_end = python_header_end(masked, index)
        if header_end is None:
            continue
        header_index, header_column = header_end

        indent = indent_width(match.group("indent"))
        end_index = python_block_end(lines, in_triple, header_index, indent)
        start_index = python_decorator_start(lines, masked, in_triple, index)
        classes.append(
            _make_class(
                lines=lines,
                name=match.group("name"),
                kind=TypeKind.CLASS,
                language=Language.PYTHON,
                start_index=start_index,
                decl_index=index,
                signature_end_index=header_index,
                signature_end_column=header_column,
                include_terminator=True,
                end_index=end_index,
                confidence=CONFIDENCE_PYTHON_TYPE,
            )
        )

    return _assign_depths(_dedupe_classes(classes))


def _make_class(
    lines: list[str],
    name: str,
    kind: TypeKind,
    language: Language,
    start_index: int,
    decl_index: int,
    signature_end_index: int,
    signature_end_column: int,
    include_terminator: bool,
    end_index: int,
    confidence: float,
) -> ClassContext:
    return ClassContext(
        name=name,
        start_line=start_index + 1,
        end_line=end_index + 1,
        kind=kind,
        language=language,
        signature=declaration_signature(
            lines,
            decl_index,
            signature_end_index,
            signature_end_column,
            include_terminator,
        ),
        code=code_slice(lines, start_index, end_index),
        source=SymbolSource.HEURISTIC,
        confidence=confidence,
    )


def _assign_depths(classes: list[ClassContext]) -> list[ClassContext]:
    """Nesting level of every type, counted from the other declared types.

    Counting containing types instead of raw brace depth keeps the meaning
    identical for Java and Python: a local class declared inside a method
    is nested one level, not two.
    """
    result: list[ClassContext] = []

    for item in classes:
        depth = sum(
            1
            for other in classes
            if other is not item
            and other.start_line <= item.start_line
            and other.end_line >= item.end_line
        )
        result.append(item.model_copy(update={"depth": depth}))

    return result


def _dedupe_classes(classes: list[ClassContext]) -> list[ClassContext]:
    unique: dict[tuple[str, int, int], ClassContext] = {}
    for item in classes:
        unique.setdefault((item.name, item.start_line, item.end_line), item)
    return list(unique.values())
