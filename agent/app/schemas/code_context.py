"""Code Context data contract (Phase 6).

Internal Pydantic models describing parsed Git diff data and the code
context derived from it. The contract is intentionally layered so later
Phase 6 steps can fill in structure and snippets without changing the
diff level:

    Diff -> File Context -> Method/Class Context -> Related Code -> LLM
"""

from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    JAVA = "JAVA"
    PYTHON = "PYTHON"
    OTHER = "OTHER"


class FileStatus(str, Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    REMOVED = "REMOVED"
    RENAMED = "RENAMED"
    COPIED = "COPIED"
    UNKNOWN = "UNKNOWN"


class DiffLineKind(str, Enum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    CONTEXT = "CONTEXT"


class SymbolKind(str, Enum):
    CLASS = "CLASS"
    METHOD = "METHOD"
    FUNCTION = "FUNCTION"


class SymbolSource(str, Enum):
    """How a symbol location was determined.

    AST means the language parser confirmed the boundaries, HEURISTIC
    means a text-based strategy produced it and it may be imprecise.
    Downstream consumers must not treat both as equally reliable.
    """

    AST = "AST"
    HEURISTIC = "HEURISTIC"


class SnippetReason(str, Enum):
    SURROUNDING = "SURROUNDING"
    SYMBOL = "SYMBOL"


class DiffLine(BaseModel):
    """One line of a diff hunk.

    old_line_no is set for removed and context lines, new_line_no is set
    for added and context lines. Line numbers are 1-based; None means the
    line does not exist on that side of the diff.
    """

    kind: DiffLineKind
    text: str = ""
    old_line_no: int | None = None
    new_line_no: int | None = None


class Hunk(BaseModel):
    """A single unified diff hunk with resolved line numbers."""

    header: str
    old_start: int = 0
    old_count: int = 0
    new_start: int = 0
    new_count: int = 0
    lines: list[DiffLine] = Field(default_factory=list)


class ChangedRange(BaseModel):
    """An inclusive range of changed lines on the new side of the diff."""

    start_line: int
    end_line: int


class SymbolRef(BaseModel):
    """A class, method or function located inside a file."""

    kind: SymbolKind
    name: str
    start_line: int
    end_line: int
    signature: str = ""
    source: SymbolSource = SymbolSource.HEURISTIC
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class FileStructure(BaseModel):
    """Structural view of one file at the reviewed revision."""

    language: Language = Language.OTHER
    namespace: str = ""
    imports: list[str] = Field(default_factory=list)
    symbols: list[SymbolRef] = Field(default_factory=list)
    parse_ok: bool = False
    notes: list[str] = Field(default_factory=list)


class CodeSnippet(BaseModel):
    """A slice of file content provided to the LLM as evidence."""

    start_line: int
    end_line: int
    lines: list[str] = Field(default_factory=list)
    reason: SnippetReason = SnippetReason.SURROUNDING


class FileDiff(BaseModel):
    """Parsed diff of one changed file.

    patch_available is False when the producer had no textual patch, for
    example for binary files, pure renames or oversized diffs. notes keeps
    every degradation explicit instead of dropping data silently.
    """

    path: str
    status: FileStatus = FileStatus.UNKNOWN
    language: Language = Language.OTHER
    previous_path: str | None = None
    additions: int = 0
    deletions: int = 0
    hunks: list[Hunk] = Field(default_factory=list)
    changed_ranges: list[ChangedRange] = Field(default_factory=list)
    patch_available: bool = False
    notes: list[str] = Field(default_factory=list)


class FileContent(BaseModel):
    """Full source of one file at the reviewed revision.

    path is the new-side path used to join this content with a FileDiff.
    content is None whenever the source could not be read, and error then
    carries the reason so the builder can record it instead of failing.
    Callers must never log content: it is untrusted user source code.
    """

    path: str
    revision: str | None = None
    content: str | None = None
    error: str | None = None


class FileContext(BaseModel):
    """Everything known about one changed file.

    structure, snippets and changed_symbols stay empty until the file
    content is available; skipped_reason explains why a file was not
    analyzed at all. line_count follows the Git line model and is the
    basis for locating symbols in later Phase 6 steps.
    """

    file_diff: FileDiff
    structure: FileStructure | None = None
    content: FileContent | None = None
    line_count: int = 0
    content_available: bool = False
    changed_symbols: list[SymbolRef] = Field(default_factory=list)
    enclosing_class: str | None = None
    snippets: list[CodeSnippet] = Field(default_factory=list)
    skipped_reason: str | None = None
    notes: list[str] = Field(default_factory=list)


class CodeContext(BaseModel):
    """Code context of one pull request review."""

    repository: str
    pr_number: int
    base_sha: str | None = None
    head_sha: str | None = None
    files: list[FileContext] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
