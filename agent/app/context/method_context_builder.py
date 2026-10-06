"""Method Context location (Phase 6.3).

Turns the changed line ranges of a FileContext into the methods and
functions they hit, so later phases can reason about a change inside its
declaration instead of a bare diff.

The implementation is deliberately lightweight: line scanning over a
string and comment aware mask, brace depth for Java and indentation for
Python. No parser, no AST and no third party dependency. Locations are
therefore heuristic, which is why every MethodContext carries source and
confidence, and why every failure mode degrades to "no method found"
instead of raising.

Line numbers are 1-based and use the diff numbering of the head revision
produced by diff_parser, so a MethodContext can be compared against
changed_ranges directly. Content is untrusted user source code and must
never be written to logs.
"""

import re

from app.context.file_context_builder import split_lines
from app.schemas.code_context import (
    ChangedRange,
    FileContext,
    Language,
    MethodContext,
    SymbolKind,
    SymbolRef,
    SymbolSource,
)

CONFIDENCE_JAVA_BODY = 0.9
CONFIDENCE_JAVA_CONSTRUCTOR = 0.7
CONFIDENCE_JAVA_DECLARATION = 0.6
CONFIDENCE_PYTHON_BLOCK = 0.85

NOTE_NO_METHOD_MATCH = "matched no method"

_MAX_DECLARATION_SCAN_LINES = 200
_MAX_BODY_SCAN_LINES = 5000
_MAX_ANNOTATION_LINES = 10

_CODE = "code"
_BLOCK_COMMENT = "block_comment"
_TEXT_BLOCK = "text_block"

_JAVA_BLOCK_KEYWORDS = frozenset(
    {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "try",
        "do",
        "else",
        "return",
        "new",
        "throw",
        "case",
        "synchronized",
        "assert",
        "super",
        "this",
        "instanceof",
        "yield",
        "break",
        "continue",
    }
)

_JAVA_FORBIDDEN_PREFIX_TOKENS = frozenset(
    {
        "class",
        "interface",
        "enum",
        "record",
        "new",
        "return",
        "throw",
        "else",
        "case",
        "assert",
        "yield",
        "super",
        "this",
        "instanceof",
        "package",
        "import",
    }
)

_JAVA_GENERIC_INNER = r"[^;{}()<>()]*"

_JAVA_TYPE = (
    r"[\w$][\w$.]*"
    r"(?:<"
    + _JAVA_GENERIC_INNER
    + r"(?:<"
    + _JAVA_GENERIC_INNER
    + r"(?:<"
    + _JAVA_GENERIC_INNER
    + r">)?"
    + _JAVA_GENERIC_INNER
    + r">)?"
    + _JAVA_GENERIC_INNER
    + r">)?"
    r"(?:\[[ \t]*\])*"
)

_JAVA_INLINE_ANNOTATION = r"(?:@[\w$.]+(?:\([^()]*\))?[ \t]+)*"

_JAVA_METHOD_RE = re.compile(
    r"^[ \t]*"
    + _JAVA_INLINE_ANNOTATION
    + r"(?P<decl>"
    r"(?:(?:public|protected|private|static|final|abstract|synchronized"
    r"|native|strictfp|default)[ \t]+)*"
    r"(?:<[^;{}()]*>[ \t]+)?"
    r"(?:" + _JAVA_TYPE + r"[ \t]+)?"
    r")"
    r"(?P<name>[\w$]+)[ \t]*\("
)

_JAVA_WORD_RE = re.compile(r"[\w$]+")

_JAVA_PARAMETER_RE = re.compile(r"[\w$.<>\[\]]+(?:\.\.\.)?[ \t]+[\w$]+$")

_SIGNATURE_SPACING = (
    (re.compile(r"\(\s+"), "("),
    (re.compile(r"\s+\)"), ")"),
    (re.compile(r"\s+,"), ","),
)

_PYTHON_DEF_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<async>async[ \t]+)?"
    r"def[ \t]+(?P<name>[A-Za-z_]\w*)[ \t]*\("
)

_PYTHON_CLASS_RE = re.compile(r"^class\b")


def find_methods(content: str, language: Language) -> list[MethodContext]:
    """Locate every method or function declared in one file.

    Returns an empty list for unsupported languages, empty content and
    content that contains no recognizable declaration. Ranges are
    inclusive and 1-based; start_line covers leading decorators or
    annotations, end_line is the last line of the declaration or body.
    """
    if not content or language is Language.OTHER:
        return []

    lines = split_lines(content)
    if not lines:
        return []

    if language is Language.JAVA:
        return _find_java_methods(lines, _mask_java(lines))

    masked, in_triple = _mask_python(lines)
    return _find_python_methods(lines, masked, in_triple)


def match_methods(
    methods: list[MethodContext], changed_ranges: list[ChangedRange]
) -> list[MethodContext]:
    """Keep the methods a changed range overlaps.

    Overlap is used instead of containment, so a range that only touches
    a signature, a range that spans several methods and several ranges
    inside one method are all handled. Each method yields exactly one
    MethodContext carrying every range that hit it.
    """
    ranges = _dedupe_ranges(changed_ranges)
    matched: dict[tuple[str, int, int], MethodContext] = {}

    for method in methods:
        hits = [item for item in ranges if _overlaps(item, method)]
        if not hits:
            continue
        key = (method.name, method.start_line, method.end_line)
        existing = matched.get(key)
        if existing is None:
            matched[key] = method.model_copy(update={"changed_ranges": hits})
        else:
            merged = _dedupe_ranges(list(existing.changed_ranges) + hits)
            matched[key] = existing.model_copy(update={"changed_ranges": merged})

    return list(matched.values())


def build_method_contexts(file_context: FileContext) -> list[MethodContext]:
    """Methods of one FileContext that are hit by its changed ranges.

    A file without usable content simply has no method context; the diff
    level of the FileContext stays intact.
    """
    content = file_context.content
    if (
        not file_context.content_available
        or content is None
        or content.content is None
    ):
        return []

    methods = find_methods(content.content, file_context.file_diff.language)
    return match_methods(methods, file_context.file_diff.changed_ranges)


def attach_method_contexts(file_context: FileContext) -> FileContext:
    """Return a copy of file_context with method level context filled in.

    The input is never mutated. changed_symbols mirrors methods so later
    phases can consume a flat symbol view, and a changed range that no
    method covers is recorded as a note instead of being dropped.
    """
    methods = build_method_contexts(file_context)
    symbols = [
        SymbolRef(
            kind=method.kind,
            name=method.name,
            start_line=method.start_line,
            end_line=method.end_line,
            signature=method.signature,
            source=method.source,
            confidence=method.confidence,
        )
        for method in methods
    ]

    notes = list(file_context.notes)
    if file_context.content_available:
        unmatched = [
            changed
            for changed in file_context.file_diff.changed_ranges
            if not any(_overlaps(changed, method) for method in methods)
        ]
        if unmatched and not any(
            NOTE_NO_METHOD_MATCH in note for note in notes
        ):
            notes.append(
                f"{len(unmatched)} changed range(s) {NOTE_NO_METHOD_MATCH}"
            )

    return file_context.model_copy(
        update={
            "methods": methods,
            "changed_symbols": symbols,
            "notes": notes,
        }
    )


def _mask_quoted(line: str, index: int, quote: str, out: list[str]) -> int:
    index += 1
    out.append(" ")
    length = len(line)
    while index < length:
        char = line[index]
        if char == "\\":
            out.append("  ")
            index += 2
            continue
        out.append(" ")
        index += 1
        if char == quote:
            break
    return index


def _mask_java(lines: list[str]) -> list[str]:
    """Blank out comments, string and char literals and text blocks.

    Masked characters become spaces so columns, braces and parentheses
    keep their original position while literals can no longer influence
    brace depth or declaration matching.
    """
    masked: list[str] = []
    state = _CODE

    for line in lines:
        out: list[str] = []
        index = 0
        length = len(line)
        while index < length:
            if state == _CODE:
                if line.startswith('"""', index):
                    state = _TEXT_BLOCK
                    out.append("   ")
                    index += 3
                    continue
                if line.startswith("//", index):
                    out.append(" " * (length - index))
                    index = length
                    continue
                if line.startswith("/*", index):
                    state = _BLOCK_COMMENT
                    out.append("  ")
                    index += 2
                    continue
                char = line[index]
                if char == '"' or char == "'":
                    index = _mask_quoted(line, index, char, out)
                    continue
                out.append(char)
                index += 1
                continue

            if state == _BLOCK_COMMENT:
                if line.startswith("*/", index):
                    state = _CODE
                    out.append("  ")
                    index += 2
                    continue
                out.append(" ")
                index += 1
                continue

            if line.startswith('"""', index):
                state = _CODE
                out.append("   ")
                index += 3
                continue
            out.append(" ")
            index += 1

        masked.append("".join(out))

    return masked


def _mask_python(lines: list[str]) -> tuple[list[str], list[bool]]:
    """Blank out comments and strings, and flag triple quoted interiors.

    in_triple tells whether a line starts inside a triple quoted string,
    where indentation carries no block meaning and a line such as
    "def example():" must not be read as a declaration.
    """
    masked: list[str] = []
    in_triple: list[bool] = []
    delimiter = ""

    for line in lines:
        in_triple.append(bool(delimiter))
        out: list[str] = []
        index = 0
        length = len(line)
        while index < length:
            if delimiter:
                if line.startswith(delimiter, index):
                    delimiter = ""
                    out.append("   ")
                    index += 3
                    continue
                out.append(" ")
                index += 1
                continue

            if line.startswith('"""', index):
                delimiter = '"""'
                out.append("   ")
                index += 3
                continue
            if line.startswith("'''", index):
                delimiter = "'''"
                out.append("   ")
                index += 3
                continue

            char = line[index]
            if char == "#":
                out.append(" " * (length - index))
                index = length
                continue
            if char == '"' or char == "'":
                index = _mask_quoted(line, index, char, out)
                continue
            out.append(char)
            index += 1

        masked.append("".join(out))

    return masked, in_triple


def _find_java_methods(lines: list[str], masked: list[str]) -> list[MethodContext]:
    depths = _java_depths(masked)
    methods: list[MethodContext] = []

    for index, text in enumerate(masked):
        if depths[index] < 1:
            continue
        match = _JAVA_METHOD_RE.match(text)
        if match is None:
            continue

        name = match.group("name")
        if name in _JAVA_BLOCK_KEYWORDS:
            continue
        tokens = _JAVA_WORD_RE.findall(match.group("decl"))
        if any(token in _JAVA_FORBIDDEN_PREFIX_TOKENS for token in tokens):
            continue
        if tokens:
            confidence = CONFIDENCE_JAVA_BODY
        elif (
            depths[index] == 1
            and name[:1].isupper()
            and _looks_like_parameter_list(lines, index, match.end() - 1)
        ):
            confidence = CONFIDENCE_JAVA_CONSTRUCTOR
        else:
            continue

        declaration_end = _find_java_declaration_end(
            masked, index, match.end() - 1
        )
        if declaration_end is None:
            continue
        end_index, end_column, has_body = declaration_end

        if has_body:
            body_end = _find_java_body_end(masked, end_index, end_column)
            if body_end is None:
                continue
        elif depths[index] == 1:
            body_end = end_index
            confidence = CONFIDENCE_JAVA_DECLARATION
        else:
            continue

        start_index = _java_declaration_start(masked, index)
        methods.append(
            _make_method(
                lines=lines,
                name=name,
                kind=SymbolKind.METHOD,
                language=Language.JAVA,
                start_index=start_index,
                decl_index=index,
                signature_end_index=end_index,
                signature_end_column=end_column,
                include_terminator=False,
                end_index=body_end,
                confidence=confidence,
            )
        )

    return _dedupe_methods(methods)


def _java_depths(masked: list[str]) -> list[int]:
    depths: list[int] = []
    depth = 0
    for text in masked:
        depths.append(depth)
        depth += text.count("{") - text.count("}")
        if depth < 0:
            depth = 0
    return depths


def _find_java_declaration_end(
    masked: list[str], line_index: int, start_column: int
) -> tuple[int, int, bool] | None:
    """Locate the brace or semicolon that ends a Java signature.

    Returns (line index, column, has body) or None when the declaration
    never completes, which happens for truncated or malformed sources.
    """
    paren = 0
    limit = min(len(masked), line_index + _MAX_DECLARATION_SCAN_LINES)

    for index in range(line_index, limit):
        text = masked[index]
        column = start_column if index == line_index else 0
        while column < len(text):
            char = text[column]
            if char == "(":
                paren += 1
            elif char == ")":
                paren -= 1
                if paren < 0:
                    return None
            elif paren == 0 and char == "{":
                return index, column, True
            elif paren == 0 and char == ";":
                return index, column, False
            column += 1

    return None


def _find_java_body_end(
    masked: list[str], open_line: int, open_column: int
) -> int | None:
    depth = 0
    limit = min(len(masked), open_line + _MAX_BODY_SCAN_LINES)

    for index in range(open_line, limit):
        text = masked[index]
        column = open_column if index == open_line else 0
        while column < len(text):
            char = text[column]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index
            column += 1

    return None


def _java_declaration_start(masked: list[str], index: int) -> int:
    """Extend a declaration upwards over its annotation block."""
    candidate = index
    limit = max(0, index - _MAX_ANNOTATION_LINES)

    while candidate - 1 >= limit:
        previous = masked[candidate - 1].strip()
        if not previous:
            break
        if previous.startswith("@"):
            window = "\n".join(masked[candidate - 1 : index])
            if window.count("(") == window.count(")"):
                return candidate - 1
            break
        if previous.endswith(("{", "}", ";")):
            break
        candidate -= 1

    return index


def _find_python_methods(
    lines: list[str], masked: list[str], in_triple: list[bool]
) -> list[MethodContext]:
    methods: list[MethodContext] = []

    for index, text in enumerate(lines):
        if in_triple[index]:
            continue
        match = _PYTHON_DEF_RE.match(text)
        if match is None:
            continue

        header_end = _find_python_header_end(masked, index)
        if header_end is None:
            continue
        header_index, header_column = header_end

        indent = _indent_width(match.group("indent"))
        end_index = _python_block_end(lines, in_triple, header_index, indent)
        start_index = _python_declaration_start(lines, masked, in_triple, index)
        methods.append(
            _make_method(
                lines=lines,
                name=match.group("name"),
                kind=_python_symbol_kind(lines, masked, in_triple, index, indent),
                language=Language.PYTHON,
                start_index=start_index,
                decl_index=index,
                signature_end_index=header_index,
                signature_end_column=header_column,
                include_terminator=True,
                end_index=end_index,
                confidence=CONFIDENCE_PYTHON_BLOCK,
            )
        )

    return _dedupe_methods(methods)


def _python_symbol_kind(
    lines: list[str],
    masked: list[str],
    in_triple: list[bool],
    index: int,
    indent: int,
) -> SymbolKind:
    """METHOD when the declaration sits in a class body, FUNCTION otherwise.

    Only the nearest enclosing block header is inspected; no class symbol
    is produced here because Class Context is a later phase.
    """
    if indent == 0:
        return SymbolKind.FUNCTION

    for cursor in range(index - 1, -1, -1):
        if in_triple[cursor] or not masked[cursor].strip():
            continue
        if _indent_width(lines[cursor]) >= indent:
            continue
        if _PYTHON_CLASS_RE.match(masked[cursor].strip()):
            return SymbolKind.METHOD
        return SymbolKind.FUNCTION

    return SymbolKind.FUNCTION


def _find_python_header_end(
    masked: list[str], line_index: int
) -> tuple[int, int] | None:
    """Find the colon that closes a def header, honoring parentheses."""
    paren = 0
    limit = min(len(masked), line_index + _MAX_DECLARATION_SCAN_LINES)

    for index in range(line_index, limit):
        for column, char in enumerate(masked[index]):
            if char == "(":
                paren += 1
            elif char == ")":
                paren -= 1
                if paren < 0:
                    return None
            elif char == ":" and paren == 0:
                return index, column

    return None


def _python_block_end(
    lines: list[str], in_triple: list[bool], header_index: int, indent: int
) -> int:
    """Last line of an indented block.

    Blank lines and lines inside a triple quoted string carry no block
    meaning and are skipped, so a docstring line at column zero cannot
    terminate the block. Comment lines do belong to the block.
    """
    last_code = header_index

    for index in range(header_index + 1, len(lines)):
        if in_triple[index] or not lines[index].strip():
            continue
        if _indent_width(lines[index]) <= indent:
            break
        last_code = index

    return last_code


def _python_declaration_start(
    lines: list[str], masked: list[str], in_triple: list[bool], index: int
) -> int:
    """Extend a declaration upwards over its decorator block."""
    candidate = index
    limit = max(0, index - _MAX_ANNOTATION_LINES)

    while candidate - 1 >= limit:
        previous = candidate - 1
        if in_triple[previous]:
            break
        stripped = lines[previous].strip()
        if not stripped:
            break
        if stripped.startswith("@"):
            window = "\n".join(masked[previous:index])
            if window.count("(") == window.count(")"):
                return previous
            break
        if stripped.endswith(":"):
            break
        candidate -= 1

    return index


def _looks_like_parameter_list(
    lines: list[str], line_index: int, open_column: int
) -> bool:
    """Tell a constructor parameter list from enum constant arguments.

    Used for declarations without modifiers, where `Point(int x)` is a
    constructor but `VALUE(1)` and `CODE("x")` are enum constants with a
    body. The original text is inspected on purpose: masking would turn
    `CODE("x")` into an empty list, which is indistinguishable from a
    no argument constructor. An empty list still counts as a constructor
    because enum constants only carry parentheses when passing arguments.
    """
    text = _java_parameter_text(lines, line_index, open_column)
    if text is None:
        return False
    if not text.strip():
        return True
    return all(
        _JAVA_PARAMETER_RE.search(part.strip())
        for part in _split_parameters(text)
        if part.strip()
    )


def _java_parameter_text(
    lines: list[str], line_index: int, open_column: int
) -> str | None:
    """Text between the outer parentheses of a declaration, or None."""
    paren = 0
    parts: list[str] = []
    limit = min(len(lines), line_index + _MAX_DECLARATION_SCAN_LINES)

    for index in range(line_index, limit):
        text = lines[index]
        column = open_column if index == line_index else 0
        while column < len(text):
            char = text[column]
            if char == "(":
                paren += 1
                if paren > 1:
                    parts.append(char)
            elif char == ")":
                paren -= 1
                if paren == 0:
                    return "".join(parts)
                parts.append(char)
            elif paren >= 1:
                parts.append(char)
            column += 1

    return None


def _split_parameters(text: str) -> list[str]:
    """Split on commas that are not nested in brackets or parentheses."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0

    for char in text:
        if char in "([<":
            depth += 1
        elif char in ")]>":
            depth -= 1
        if char == "," and depth <= 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)

    parts.append("".join(current))
    return parts


def _make_method(
    lines: list[str],
    name: str,
    kind: SymbolKind,
    language: Language,
    start_index: int,
    decl_index: int,
    signature_end_index: int,
    signature_end_column: int,
    include_terminator: bool,
    end_index: int,
    confidence: float,
) -> MethodContext:
    end_column = signature_end_column + (1 if include_terminator else 0)
    signature_parts = list(lines[decl_index:signature_end_index])
    signature_parts.append(lines[signature_end_index][:end_column])

    return MethodContext(
        name=name,
        start_line=start_index + 1,
        end_line=end_index + 1,
        kind=kind,
        language=language,
        signature=_normalize_signature(" ".join(signature_parts)),
        code="\n".join(lines[start_index : end_index + 1]),
        source=SymbolSource.HEURISTIC,
        confidence=confidence,
    )


def _indent_width(line: str) -> int:
    stripped = line.lstrip(" \t")
    return len(line[: len(line) - len(stripped)].expandtabs(8))


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _normalize_signature(text: str) -> str:
    """Collapse a possibly multi line declaration into one clean line."""
    normalized = _collapse(text)
    for pattern, replacement in _SIGNATURE_SPACING:
        normalized = pattern.sub(replacement, normalized)
    return normalized.strip()


def _overlaps(changed: ChangedRange, method: MethodContext) -> bool:
    return (
        changed.start_line <= method.end_line
        and changed.end_line >= method.start_line
    )


def _dedupe_methods(
    methods: list[MethodContext],
) -> list[MethodContext]:
    unique: dict[tuple[str, int, int], MethodContext] = {}
    for method in methods:
        unique.setdefault(
            (method.name, method.start_line, method.end_line), method
        )
    return list(unique.values())


def _dedupe_ranges(ranges: list[ChangedRange]) -> list[ChangedRange]:
    seen: set[tuple[int, int]] = set()
    unique: list[ChangedRange] = []
    for item in ranges:
        key = (item.start_line, item.end_line)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
