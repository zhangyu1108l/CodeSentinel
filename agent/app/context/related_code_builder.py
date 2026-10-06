"""Related Code selection (Phase 6.5).

Adds the structural neighbourhood of a change: for every type that owns a
changed line, the other members of that same type are offered as related
code, so a reviewer or a later agent sees the changed method next to its
siblings, fields, constructors and nested types.

Selection is strictly structural and strictly local to one FileContext:

* the anchor is the innermost named type around a changed method or a
  changed line, resolved with the Class Context builder;
* candidates are direct members of that anchor and nothing else, so no
  cross file lookup, no call graph, no name similarity and no semantic
  inference is involved;
* the anchor type itself, a changed method, a changed type and anything
  already covered by a changed line are never re-emitted.

Everything is reused from the earlier phases: masking, brace depth and
indentation from source_scanner, methods from the Method Context builder,
types and scope resolution from the Class Context builder. Only field and
class attribute detection is new. Failures degrade to an empty list,
inputs are never mutated, and content must never be written to logs.
"""

import re

from app.context.class_context_builder import (
    find_anonymous_regions,
    find_classes,
    innermost_class,
)
from app.context.file_context_builder import split_lines
from app.context.method_context_builder import find_methods, match_methods
from app.context.source_scanner import (
    JAVA_INLINE_ANNOTATION,
    JAVA_TYPE,
    code_slice,
    indent_width,
    java_annotation_start,
    java_brace_depths,
    java_declaration_end,
    mask_java,
    mask_python,
    python_header_end,
)
from app.schemas.code_context import (
    ChangedRange,
    ClassContext,
    FileContext,
    Language,
    MethodContext,
    RelatedCodeContext,
    RelatedKind,
    RelatedReason,
    SymbolSource,
)

CONFIDENCE_JAVA_FIELD = 0.8
CONFIDENCE_PYTHON_ATTRIBUTE = 0.8

KIND_PRIORITY = {
    RelatedKind.METHOD: 0,
    RelatedKind.FIELD: 1,
    RelatedKind.CONSTRUCTOR: 2,
    RelatedKind.NESTED_TYPE: 3,
}

Anchor = tuple[ClassContext, RelatedReason]

_MAX_STATEMENT_LINES = 50

_JAVA_FIELD_RE = re.compile(
    r"^[ \t]*"
    + JAVA_INLINE_ANNOTATION
    + r"(?:(?:public|protected|private|static|final|transient|volatile)[ \t]+)*"
    r"(?P<type>" + JAVA_TYPE + r")"
    r"[ \t]+(?P<name>[\w$]+)"
    r"(?P<tail>[ \t]*(?:\[[ \t]*\])*[ \t]*(?:=|;|,))"
)

_PYTHON_ASSIGN_RE = re.compile(r"^(?P<name>[A-Za-z_]\w*)[ \t]*(?::[^=]*)?=(?!=)")

_PYTHON_ANNOTATION_RE = re.compile(r"^(?P<name>[A-Za-z_]\w*)[ \t]*:[ \t]*\S")

_PYTHON_CLASS_STATEMENT_RE = re.compile(
    r"^[ \t]*class[ \t]+(?P<name>[A-Za-z_]\w*)"
)

_PYTHON_KEYWORDS = frozenset(
    {
        "False",
        "None",
        "True",
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "case",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "match",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
    }
)


def build_related_code(file_context: FileContext) -> list[RelatedCodeContext]:
    """Direct members of the types that own the changes in one file.

    The result is deduplicated and stably ordered by kind priority, then by
    line and name, so the same input always yields the same list.
    """
    prepared = _prepare(file_context)
    if prepared is None:
        return []

    scan, classes, anchors = prepared
    path = file_context.file_diff.path
    items: list[RelatedCodeContext] = []

    for anchor, reason in anchors:
        items.extend(_members_of(path, anchor, reason, scan, classes))

    return _finalize(items)


def attach_related_code(file_context: FileContext) -> FileContext:
    """Return a copy of file_context with related_code filled in.

    The input object, its methods, classes and content are never mutated.
    """
    return file_context.model_copy(
        update={"related_code": build_related_code(file_context)}
    )


class _Scan:
    """Precomputed view of one file, shared by every anchor of that file."""

    def __init__(
        self,
        lines: list[str],
        language: Language,
        methods: list[MethodContext],
        anonymous_regions: list[tuple[int, int]],
        changed_ranges: list[ChangedRange],
    ):
        self.lines = lines
        self.language = language
        self.methods = methods
        self.anonymous_regions = anonymous_regions
        self.changed_ranges = changed_ranges
        self.masked: list[str] = []
        self.depths: list[int] = []
        self.in_triple: list[bool] = []

        if language is Language.JAVA:
            self.masked = mask_java(lines)
            self.depths = java_brace_depths(self.masked)
        else:
            self.masked, self.in_triple = mask_python(lines)


def _prepare(
    file_context: FileContext,
) -> tuple[_Scan, list[ClassContext], list[Anchor]] | None:
    """Collect everything the selection needs, or None when there is nothing.

    Unusable content, an unsupported language, a file without types and a
    change that no type owns all end here, which is what keeps the public
    entry points free of error handling.
    """
    content = file_context.content
    if (
        not file_context.content_available
        or content is None
        or content.content is None
    ):
        return None

    text = content.content
    language = file_context.file_diff.language
    if not text or language is Language.OTHER:
        return None

    lines = split_lines(text)
    if not lines:
        return None

    classes = file_context.classes or find_classes(text, language)
    if not classes:
        return None

    anonymous_regions = (
        find_anonymous_regions(text, language) if language is Language.JAVA else []
    )
    changed_ranges = file_context.file_diff.changed_ranges
    scan = _Scan(
        lines,
        language,
        find_methods(text, language),
        anonymous_regions,
        changed_ranges,
    )

    changed_methods = file_context.methods or match_methods(
        scan.methods, changed_ranges
    )
    anchors = _anchors(
        classes, changed_methods, changed_ranges, anonymous_regions
    )
    if not anchors:
        return None

    return scan, classes, anchors


def _anchors(
    classes: list[ClassContext],
    changed_methods: list[MethodContext],
    changed_ranges: list[ChangedRange],
    anonymous_regions: list[tuple[int, int]],
) -> list[Anchor]:
    """Types that own a change, with the reason they were selected.

    A changed method makes its type a sibling source, which is stronger
    evidence than a changed line landing somewhere in the type, so the
    method based reason wins when both apply.
    """
    found: dict[tuple[str, int, int], Anchor] = {}

    for method in changed_methods:
        owner = innermost_class(classes, method.start_line, anonymous_regions)
        if owner is not None:
            _remember(found, owner, RelatedReason.SIBLING_OF_CHANGED_METHOD)

    for changed in changed_ranges:
        for line in (changed.start_line, changed.end_line):
            owner = innermost_class(classes, line, anonymous_regions)
            if owner is not None:
                _remember(found, owner, RelatedReason.MEMBER_OF_CHANGED_CLASS)

    return sorted(
        found.values(), key=lambda anchor: (anchor[0].start_line, anchor[0].name)
    )


def _remember(
    found: dict[tuple[str, int, int], Anchor],
    owner: ClassContext,
    reason: RelatedReason,
) -> None:
    key = (owner.name, owner.start_line, owner.end_line)
    existing = found.get(key)
    if existing is None or reason is RelatedReason.SIBLING_OF_CHANGED_METHOD:
        found[key] = (owner, reason)


def _members_of(
    path: str,
    anchor: ClassContext,
    reason: RelatedReason,
    scan: _Scan,
    classes: list[ClassContext],
) -> list[RelatedCodeContext]:
    """Direct members of one anchor type that the diff does not already show.

    A candidate overlapping a changed line is dropped: it is either a
    changed method reported by Method Context, an anchor type, or a field
    the diff already contains.
    """
    items = [
        _method_item(path, method, anchor, reason, scan.language)
        for method in scan.methods
        if _is_direct_member(method.start_line, anchor, scan, classes)
        and not _is_changed(method.start_line, method.end_line, scan)
    ]

    items.extend(_fields_of(path, anchor, reason, scan, classes))

    items.extend(
        _nested_type_item(path, nested, anchor, reason)
        for nested in classes
        if _is_direct_child(nested, anchor)
        and not _is_changed(nested.start_line, nested.end_line, scan)
    )

    return items


def _is_changed(start_line: int, end_line: int, scan: _Scan) -> bool:
    return any(
        changed.start_line <= end_line and changed.end_line >= start_line
        for changed in scan.changed_ranges
    )


def _method_item(
    path: str,
    method: MethodContext,
    anchor: ClassContext,
    reason: RelatedReason,
    language: Language,
) -> RelatedCodeContext:
    return RelatedCodeContext(
        path=path,
        name=method.name,
        start_line=method.start_line,
        end_line=method.end_line,
        reason=reason,
        kind=(
            RelatedKind.CONSTRUCTOR
            if _is_constructor(method, anchor, language)
            else RelatedKind.METHOD
        ),
        owner_class=anchor.name,
        code=method.code,
        source=method.source,
        confidence=method.confidence,
    )


def _nested_type_item(
    path: str,
    nested: ClassContext,
    anchor: ClassContext,
    reason: RelatedReason,
) -> RelatedCodeContext:
    return RelatedCodeContext(
        path=path,
        name=nested.name,
        start_line=nested.start_line,
        end_line=nested.end_line,
        reason=reason,
        kind=RelatedKind.NESTED_TYPE,
        owner_class=anchor.name,
        code=nested.code,
        source=nested.source,
        confidence=nested.confidence,
    )


def _is_direct_member(
    line: int, anchor: ClassContext, scan: _Scan, classes: list[ClassContext]
) -> bool:
    owner = innermost_class(classes, line, scan.anonymous_regions)
    return owner is not None and _key(owner) == _key(anchor)


def _is_direct_child(nested: ClassContext, anchor: ClassContext) -> bool:
    if _key(nested) == _key(anchor):
        return False
    if nested.depth != anchor.depth + 1:
        return False
    return (
        anchor.start_line <= nested.start_line
        and anchor.end_line >= nested.end_line
    )


def _is_constructor(
    method: MethodContext, anchor: ClassContext, language: Language
) -> bool:
    if language is Language.PYTHON:
        return method.name == "__init__"
    return method.name == anchor.name


def _fields_of(
    path: str,
    anchor: ClassContext,
    reason: RelatedReason,
    scan: _Scan,
    classes: list[ClassContext],
) -> list[RelatedCodeContext]:
    candidates = (
        _java_fields(path, anchor, reason, scan, classes)
        if scan.language is Language.JAVA
        else _python_fields(path, anchor, reason, scan, classes)
    )
    return [
        item
        for item in candidates
        if not _is_changed(item.start_line, item.end_line, scan)
    ]


def _java_fields(
    path: str,
    anchor: ClassContext,
    reason: RelatedReason,
    scan: _Scan,
    classes: list[ClassContext],
) -> list[RelatedCodeContext]:
    """Field declarations sitting directly in the body of one type.

    A candidate must be at the brace depth of that body and must end with a
    semicolon instead of opening a block, which is what separates a field
    from a method, an initializer block or a local variable.
    """
    if not _inside_file(anchor, scan.lines):
        return []

    body_depth = scan.depths[anchor.start_line - 1] + 1
    last_index = min(anchor.end_line - 1, len(scan.lines) - 1)
    items: list[RelatedCodeContext] = []
    index = anchor.start_line

    while index <= last_index:
        if scan.depths[index] != body_depth:
            index += 1
            continue
        if not _is_direct_member(index + 1, anchor, scan, classes):
            index += 1
            continue

        match = _JAVA_FIELD_RE.match(scan.masked[index])
        if match is None:
            index += 1
            continue

        declaration_end = java_declaration_end(scan.masked, index, 0)
        if declaration_end is None:
            index += 1
            continue
        end_index, _, has_body = declaration_end
        if has_body:
            index += 1
            continue

        start_index = java_annotation_start(scan.masked, index)
        items.append(
            RelatedCodeContext(
                path=path,
                name=match.group("name"),
                start_line=start_index + 1,
                end_line=end_index + 1,
                reason=reason,
                kind=RelatedKind.FIELD,
                owner_class=anchor.name,
                code=code_slice(scan.lines, start_index, end_index),
                source=SymbolSource.HEURISTIC,
                confidence=CONFIDENCE_JAVA_FIELD,
            )
        )
        index = max(end_index, index) + 1

    return items


def _python_fields(
    path: str,
    anchor: ClassContext,
    reason: RelatedReason,
    scan: _Scan,
    classes: list[ClassContext],
) -> list[RelatedCodeContext]:
    """Class level assignments and annotations of one type.

    Scanning starts after the class header, so the parameter lines of a
    multi line header are never read as attributes, and every class level
    statement is consumed as a whole, so the continuation lines of a multi
    line initializer cannot become attributes of their own. Statements
    inside a method, a nested class or a triple quoted string are skipped,
    which keeps local variables and inner types out of the owner.
    """
    if not _inside_file(anchor, scan.lines):
        return []

    body_start = _python_body_start(anchor, scan)
    if body_start is None:
        return []

    decl_indent = indent_width(scan.lines[anchor.start_line - 1])
    method_ranges = [
        (method.start_line, method.end_line) for method in scan.methods
    ]
    last_index = min(anchor.end_line - 1, len(scan.lines) - 1)
    items: list[RelatedCodeContext] = []
    index = body_start

    while index <= last_index:
        if scan.in_triple[index] or not scan.lines[index].strip():
            index += 1
            continue
        if indent_width(scan.lines[index]) <= decl_indent:
            index += 1
            continue
        line_no = index + 1
        if _inside_any(method_ranges, line_no):
            index += 1
            continue
        if not _is_direct_member(line_no, anchor, scan, classes):
            index += 1
            continue

        statement_end = _python_statement_end(scan.masked, index)
        text = scan.masked[index].lstrip(" \t")
        match = _PYTHON_ASSIGN_RE.match(text) or _PYTHON_ANNOTATION_RE.match(text)
        if match is not None and match.group("name") not in _PYTHON_KEYWORDS:
            items.append(
                RelatedCodeContext(
                    path=path,
                    name=match.group("name"),
                    start_line=index + 1,
                    end_line=statement_end + 1,
                    reason=reason,
                    kind=RelatedKind.FIELD,
                    owner_class=anchor.name,
                    code=code_slice(scan.lines, index, statement_end),
                    source=SymbolSource.HEURISTIC,
                    confidence=CONFIDENCE_PYTHON_ATTRIBUTE,
                )
            )
        index = statement_end + 1

    return items


def _python_body_start(anchor: ClassContext, scan: _Scan) -> int | None:
    """0-based index of the first line after the class header, or None."""
    decl_index = _python_class_statement(anchor, scan)
    if decl_index is None:
        return None

    header_end = python_header_end(scan.masked, decl_index)
    if header_end is None:
        return None

    return header_end[0] + 1


def _python_class_statement(anchor: ClassContext, scan: _Scan) -> int | None:
    """Line index of the class statement, skipping its decorators."""
    limit = min(anchor.end_line, len(scan.lines))

    for index in range(anchor.start_line - 1, limit):
        if scan.in_triple[index]:
            continue
        match = _PYTHON_CLASS_STATEMENT_RE.match(scan.masked[index])
        if match is not None and match.group("name") == anchor.name:
            return index

    return None


def _python_statement_end(masked: list[str], index: int) -> int:
    """Last line of a statement, following open brackets."""
    depth = 0
    limit = min(len(masked), index + _MAX_STATEMENT_LINES)

    for cursor in range(index, limit):
        for char in masked[cursor]:
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
        if depth <= 0:
            return cursor

    return index


def _finalize(items: list[RelatedCodeContext]) -> list[RelatedCodeContext]:
    """Drop duplicate symbols and apply the stable kind, line, name order."""
    unique: dict[tuple[str, int, int], RelatedCodeContext] = {}
    for item in items:
        unique.setdefault((item.name, item.start_line, item.end_line), item)

    return sorted(
        unique.values(),
        key=lambda item: (KIND_PRIORITY[item.kind], item.start_line, item.name),
    )


def _key(item: ClassContext) -> tuple[str, int, int]:
    return (item.name, item.start_line, item.end_line)


def _inside_file(anchor: ClassContext, lines: list[str]) -> bool:
    return 1 <= anchor.start_line <= len(lines)


def _inside_any(ranges: list[tuple[int, int]], line: int) -> bool:
    return any(start <= line <= end for start, end in ranges)
