"""Source scanning primitives shared by the Phase 6 context builders.

Extracted from the Method Context builder so that Method Context and
Class Context run on one scanning strategy instead of two independent
parsers. Everything here is a pure function over lines of text: no IO, no
third party dependency and no knowledge of the Code Context models.

Two invariants matter to callers:

* a masked line has exactly the same length as the original line, so any
  column or line index taken from a mask can be applied to the source;
* line indexes are 0-based here, while Code Context models expose 1-based
  line numbers.

Content is untrusted user source code and must never be written to logs.
"""

import re

MAX_DECLARATION_SCAN_LINES = 200
MAX_BODY_SCAN_LINES = 5000
MAX_ANNOTATION_LINES = 10

_CODE = "code"
_BLOCK_COMMENT = "block_comment"
_TEXT_BLOCK = "text_block"

_SIGNATURE_SPACING = (
    (re.compile(r"\(\s+"), "("),
    (re.compile(r"\s+\)"), ")"),
    (re.compile(r"\s+,"), ","),
)


def mask_java(lines: list[str]) -> list[str]:
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


def mask_python(lines: list[str]) -> tuple[list[str], list[bool]]:
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


def java_declaration_end(
    masked: list[str], line_index: int, start_column: int
) -> tuple[int, int, bool] | None:
    """Locate the brace or semicolon that ends a Java declaration header.

    Returns (line index, column, has body) or None when the declaration
    never completes, which happens for truncated or malformed sources.
    """
    paren = 0
    limit = min(len(masked), line_index + MAX_DECLARATION_SCAN_LINES)

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


def java_body_end(masked: list[str], open_line: int, open_column: int) -> int | None:
    """Line index of the brace closing the block opened at the given place."""
    depth = 0
    limit = min(len(masked), open_line + MAX_BODY_SCAN_LINES)

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


def java_annotation_start(masked: list[str], index: int) -> int:
    """Extend a declaration upwards over its annotation block."""
    candidate = index
    limit = max(0, index - MAX_ANNOTATION_LINES)

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


def python_header_end(masked: list[str], line_index: int) -> tuple[int, int] | None:
    """Find the colon that closes a Python block header, honoring parens."""
    paren = 0
    limit = min(len(masked), line_index + MAX_DECLARATION_SCAN_LINES)

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


def python_block_end(
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
        if indent_width(lines[index]) <= indent:
            break
        last_code = index

    return last_code


def python_decorator_start(
    lines: list[str], masked: list[str], in_triple: list[bool], index: int
) -> int:
    """Extend a declaration upwards over its decorator block."""
    candidate = index
    limit = max(0, index - MAX_ANNOTATION_LINES)

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


def indent_width(line: str) -> int:
    """Leading whitespace width with tabs expanded to 8 columns."""
    stripped = line.lstrip(" \t")
    return len(line[: len(line) - len(stripped)].expandtabs(8))


def collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def normalize_declaration(text: str) -> str:
    """Collapse a possibly multi line declaration into one clean line."""
    normalized = collapse_whitespace(text)
    for pattern, replacement in _SIGNATURE_SPACING:
        normalized = pattern.sub(replacement, normalized)
    return normalized.strip()


def declaration_signature(
    lines: list[str],
    decl_index: int,
    end_index: int,
    end_column: int,
    include_terminator: bool = False,
) -> str:
    """Single line signature of a declaration that may span several lines.

    end_index and end_column point at the terminator, which is "{" or ";"
    for Java and ":" for Python. The terminator is kept only when asked
    for, so Java signatures drop the body brace and Python keeps the colon.
    """
    stop = end_column + (1 if include_terminator else 0)
    parts = list(lines[decl_index:end_index])
    parts.append(lines[end_index][:stop])
    return normalize_declaration(" ".join(parts))


def code_slice(lines: list[str], start_index: int, end_index: int) -> str:
    """Exact source text of an inclusive 0-based line range."""
    return "\n".join(lines[start_index : end_index + 1])


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
