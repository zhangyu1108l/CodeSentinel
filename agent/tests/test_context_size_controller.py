"""Tests for the Phase 6.6 token estimator and size controller."""

import pathlib

from app.context.context_size_controller import (
    DEFAULT_BUDGET,
    REASON_CHANGED_OVERFLOW,
    REASON_CHANGED_TOTAL_OVERFLOW,
    REASON_FILE_BUDGET,
    REASON_ITEM_OVERFLOW,
    REASON_RELATED_BUDGET,
    REASON_TOTAL_BUDGET,
    aggregate_stats,
    aggregate_truncation,
    apply_context_budget,
    apply_context_budget_to_files,
    budget_from_tokens,
    chars_for_tokens,
    estimate_tokens,
    measure_context,
    plan_file_budgets,
    tokens_for_chars,
)
from app.context.related_code_builder import KIND_PRIORITY
from app.schemas.code_context import (
    ChangedRange,
    ClassContext,
    ContextBudget,
    ContextStats,
    DiffLine,
    DiffLineKind,
    FileContent,
    FileContext,
    FileDiff,
    FileStatus,
    Hunk,
    Language,
    MethodContext,
    RelatedCodeContext,
    RelatedKind,
    RelatedReason,
    Truncation,
)

LINES = [
    "class A {",
    "    int helper() { return 1; }",
    "    static class Nested {",
    "        void run() { }",
    "    }",
    "    int changed() { return 2; }",
    "}",
]
SOURCE = "\n".join(LINES)
PATH = "a/A.java"
METADATA = "a/A.java MODIFIED JAVA 1 1"

PAYLOAD_ORDER = ("metadata", "diff", "changed_methods", "related")


def make_diff(hunks=(), changed=(), path=PATH, additions=1, deletions=1):
    return FileDiff(
        path=path,
        status=FileStatus.MODIFIED,
        language=Language.JAVA,
        hunks=list(hunks),
        changed_ranges=list(changed),
        additions=additions,
        deletions=deletions,
        patch_available=True,
    )


def make_item(
    name,
    kind=RelatedKind.METHOD,
    start=1,
    end=1,
    code=None,
    reason=RelatedReason.SIBLING_OF_CHANGED_METHOD,
    confidence=0.9,
    truncated=False,
    owner="A",
    path=PATH,
):
    if code is None:
        code = "\n".join(LINES[start - 1 : end])
    return RelatedCodeContext(
        path=path,
        name=name,
        start_line=start,
        end_line=end,
        reason=reason,
        kind=kind,
        owner_class=owner,
        code=code,
        confidence=confidence,
        truncated=truncated,
    )


def make_multi_file(path, related=(), methods=(), content=None, changed=()):
    return FileContext(
        file_diff=FileDiff(
            path=path,
            status=FileStatus.MODIFIED,
            language=Language.JAVA,
            changed_ranges=list(changed),
            additions=1,
            deletions=1,
            patch_available=True,
        ),
        content=FileContent(path=path, content=content)
        if content is not None
        else None,
        content_available=content is not None,
        methods=list(methods),
        related_code=list(related),
    )


def make_method(name="changed", start=6, end=6, code=None, enclosing="A"):
    if code is None:
        code = LINES[start - 1]
    return MethodContext(
        name=name,
        start_line=start,
        end_line=end,
        enclosing_class=enclosing,
        code=code,
    )


def make_class(name="Nested", start=3, end=5, code=None, header_end=3, depth=1):
    if code is None:
        code = "\n".join(LINES[start - 1 : end])
    return ClassContext(
        name=name,
        start_line=start,
        end_line=end,
        header_end_line=header_end,
        depth=depth,
        code=code,
    )


def make_context(
    related=(),
    methods=(),
    classes=(),
    content=None,
    hunks=(),
    changed=(),
    enclosing=None,
):
    return FileContext(
        file_diff=make_diff(hunks=hunks, changed=changed),
        content=FileContent(path=PATH, content=content)
        if content is not None
        else None,
        content_available=content is not None,
        methods=list(methods),
        classes=list(classes),
        related_code=list(related),
        enclosing_class=enclosing,
    )


def payload_text(context):
    """Documented prompt payload rule, recomputed independently."""
    file_diff = context.file_diff
    chunks = []
    for hunk in file_diff.hunks:
        chunks.append(hunk.header)
        chunks.extend(line.text for line in hunk.lines)
    metadata = [
        file_diff.path,
        file_diff.status.value,
        file_diff.language.value,
        str(file_diff.additions),
        str(file_diff.deletions),
    ]
    if context.enclosing_class:
        metadata.append(context.enclosing_class)
    return {
        "metadata": " ".join(metadata),
        "diff": "\n".join(chunks),
        "changed_methods": "\n".join(m.code for m in context.methods),
        "related": "\n".join(i.code for i in context.related_code),
    }


def expected_prompt_chars(context, related=None):
    probe = context
    if related is not None:
        probe = context.model_copy(update={"related_code": list(related)})
    payloads = payload_text(probe)
    return sum(len(payloads[kind]) for kind in PAYLOAD_ORDER)


def tight_budget(**overrides):
    data = {
        "max_item_chars": 10**6,
        "max_related_chars": 10**6,
        "max_file_chars": 10**6,
    }
    data.update(overrides)
    return ContextBudget(**data)


class TestDefaultBudget:
    def test_matches_schema_defaults(self):
        assert DEFAULT_BUDGET == ContextBudget()
        assert DEFAULT_BUDGET.max_item_chars == 6000
        assert DEFAULT_BUDGET.max_related_chars == 12000
        assert DEFAULT_BUDGET.max_file_chars == 24000
        assert DEFAULT_BUDGET.max_total_chars is None

    def test_kind_rank_matches_related_code_builder(self):
        from app.context import context_size_controller as module

        assert module._KIND_RANK == {
            kind: KIND_PRIORITY[kind] for kind in RelatedKind
        }


class TestMeasureContext:
    def test_empty_context(self):
        stats = measure_context(make_context())
        assert stats.prompt_chars == len(METADATA)
        assert stats.prompt_chars_by_kind == {
            "metadata": len(METADATA),
            "diff": 0,
            "changed_methods": 0,
            "related": 0,
        }
        assert stats.estimated_tokens == estimate_tokens(METADATA)
        assert stats.related_total == 0
        assert stats.related_kept == 0
        assert stats.related_dropped == 0
        assert stats.truncated_items == 0
        assert stats.retained_source_chars == 0

    def test_metadata_uses_known_fields(self):
        context = make_context(enclosing="A")
        stats = measure_context(context)
        assert stats.prompt_chars_by_kind["metadata"] == len(f"{METADATA} A")

    def test_no_related(self):
        stats = measure_context(make_context(methods=[make_method()]))
        assert stats.prompt_chars_by_kind["related"] == 0
        assert stats.related_total == 0

    def test_with_related(self):
        items = [make_item("helper", start=2, end=2)]
        stats = measure_context(make_context(related=items))
        assert stats.prompt_chars_by_kind["related"] == len(items[0].code)
        assert stats.related_total == 1
        assert stats.related_kept == 1
        assert stats.related_dropped == 0

    def test_related_separators_count(self):
        items = [
            make_item("a", code="aaa"),
            make_item("b", code="bbb"),
        ]
        stats = measure_context(make_context(related=items))
        assert stats.prompt_chars_by_kind["related"] == len("aaa\nbbb")

    def test_changed_methods(self):
        methods = [make_method(), make_method("other", start=2, end=2)]
        stats = measure_context(make_context(methods=methods))
        expected = len("\n".join(m.code for m in methods))
        assert stats.prompt_chars_by_kind["changed_methods"] == expected

    def test_diff_hunks(self):
        hunk = Hunk(
            header="@@ -1,2 +1,2 @@",
            old_start=1,
            old_count=2,
            new_start=1,
            new_count=2,
            lines=[
                DiffLine(kind=DiffLineKind.CONTEXT, text="class A {"),
                DiffLine(kind=DiffLineKind.ADDED, text="    int x = 1;"),
            ],
        )
        stats = measure_context(make_context(hunks=[hunk]))
        expected = len("\n".join([hunk.header, "class A {", "    int x = 1;"]))
        assert stats.prompt_chars_by_kind["diff"] == expected

    def test_prompt_chars_is_the_sum_of_kinds(self):
        context = make_context(
            methods=[make_method()],
            related=[make_item("helper", start=2, end=2)],
            enclosing="A",
        )
        stats = measure_context(context)
        assert stats.prompt_chars == sum(stats.prompt_chars_by_kind.values())
        assert stats.prompt_chars == expected_prompt_chars(context)

    def test_estimated_tokens_matches_documented_concatenation(self):
        context = make_context(
            methods=[make_method()],
            related=[make_item("helper", start=2, end=2)],
        )
        payloads = payload_text(context)
        joined = "".join(payloads[kind] for kind in PAYLOAD_ORDER)
        assert measure_context(context).estimated_tokens == estimate_tokens(joined)

    def test_truncated_items_are_counted(self):
        items = [
            make_item("nested", kind=RelatedKind.NESTED_TYPE, truncated=True),
            make_item("helper", start=2, end=2),
        ]
        assert measure_context(make_context(related=items)).truncated_items == 1

    def test_retained_source_chars(self):
        context = make_context(
            classes=[make_class()], content=SOURCE
        )
        expected = len(SOURCE) + len("\n".join(LINES[2:5]))
        assert measure_context(context).retained_source_chars == expected

    def test_retained_without_content(self):
        context = make_context(classes=[make_class()])
        assert measure_context(context).retained_source_chars == len(
            "\n".join(LINES[2:5])
        )

    def test_measure_does_not_change_the_context(self):
        context = make_context(
            methods=[make_method()], related=[make_item("helper", start=2, end=2)]
        )
        before = context.model_dump()
        measure_context(context)
        assert context.model_dump() == before


class TestApplyUnderBudget:
    def test_no_items(self):
        context = make_context()
        result = apply_context_budget(context, tight_budget())
        assert result.related_code == []
        assert result.truncation == Truncation()
        assert result.stats == measure_context(context)

    def test_items_under_caps_are_kept(self):
        items = [
            make_item("helper", start=2, end=2),
            make_item("field", kind=RelatedKind.FIELD, start=1, end=1),
        ]
        context = make_context(related=items)
        result = apply_context_budget(context, tight_budget())
        assert [item.name for item in result.related_code] == ["helper", "field"]
        assert result.truncation.applied is False
        assert result.truncation.dropped_items == []
        assert result.truncation.trimmed_items == []
        assert result.truncation.removed_chars == 0
        assert result.stats.prompt_chars == measure_context(context).prompt_chars

    def test_exact_related_budget_is_kept(self):
        item = make_item("helper", start=2, end=2)
        context = make_context(related=[item])
        budget = tight_budget(max_related_chars=len(item.code))
        result = apply_context_budget(context, budget)
        assert result.truncation.applied is False
        assert len(result.related_code) == 1

    def test_one_char_over_related_budget_drops(self):
        item = make_item("helper", start=2, end=2)
        context = make_context(related=[item])
        budget = tight_budget(max_related_chars=len(item.code) - 1)
        result = apply_context_budget(context, budget)
        assert result.related_code == []
        assert result.truncation.applied is True
        assert result.truncation.reasons == [REASON_RELATED_BUDGET]

    def test_exact_file_budget_is_kept(self):
        item = make_item("helper", start=2, end=2)
        context = make_context(related=[item], content=SOURCE)
        budget = tight_budget(max_file_chars=expected_prompt_chars(context))
        result = apply_context_budget(context, budget)
        assert result.truncation.applied is False
        assert len(result.related_code) == 1

    def test_one_char_over_file_budget_drops(self):
        item = make_item("helper", start=2, end=2)
        context = make_context(related=[item], content=SOURCE)
        budget = tight_budget(
            max_file_chars=expected_prompt_chars(context) - 1
        )
        result = apply_context_budget(context, budget)
        assert result.related_code == []
        assert result.truncation.applied is True
        assert result.truncation.reasons == [REASON_FILE_BUDGET]


class TestPriority:
    def keep_one(self, items, budget):
        context = make_context(related=items)
        result = apply_context_budget(context, budget)
        return [item.name for item in result.related_code]

    def test_method_beats_nested_type(self):
        method = make_item("helper", code="mmmmm")
        nested = make_item(
            "nested", kind=RelatedKind.NESTED_TYPE, code="nnnnn"
        )
        assert self.keep_one(
            [nested, method], tight_budget(max_related_chars=5)
        ) == ["helper"]

    def test_sibling_beats_member_of_changed_class(self):
        sibling = make_item(
            "sibling", reason=RelatedReason.SIBLING_OF_CHANGED_METHOD, code="sssss"
        )
        member = make_item(
            "member", reason=RelatedReason.MEMBER_OF_CHANGED_CLASS, code="mmmmm"
        )
        assert self.keep_one(
            [member, sibling], tight_budget(max_related_chars=5)
        ) == ["sibling"]

    def test_higher_confidence_wins(self):
        changed = [ChangedRange(start_line=6, end_line=6)]
        high = make_item("high", start=5, end=5, code="hhhhh", confidence=0.95)
        low = make_item("low", start=7, end=7, code="lllll", confidence=0.5)
        context = make_context(related=[low, high], changed=changed)
        result = apply_context_budget(context, tight_budget(max_related_chars=5))
        assert [item.name for item in result.related_code] == ["high"]

    def test_closer_to_changed_range_wins(self):
        changed = [ChangedRange(start_line=6, end_line=6)]
        near = make_item("near", start=7, end=7, code="nnnnn", confidence=0.9)
        far = make_item("far", start=20, end=20, code="fffff", confidence=0.9)
        context = make_context(related=[far, near], changed=changed)
        result = apply_context_budget(context, tight_budget(max_related_chars=5))
        assert [item.name for item in result.related_code] == ["near"]

    def test_overlapping_item_is_closest(self):
        changed = [ChangedRange(start_line=6, end_line=6)]
        inside = make_item("inside", start=5, end=7, code="iiiii", confidence=0.9)
        before = make_item("before", start=4, end=4, code="bbbbb", confidence=0.9)
        context = make_context(related=[before, inside], changed=changed)
        result = apply_context_budget(context, tight_budget(max_related_chars=5))
        assert [item.name for item in result.related_code] == ["inside"]

    def test_start_line_then_name_breaks_ties(self):
        alpha = make_item("alpha", start=5, end=5, code="aaaaa")
        beta = make_item("beta", start=5, end=5, code="bbbbb")
        context = make_context(related=[beta, alpha])
        result = apply_context_budget(context, tight_budget(max_related_chars=5))
        assert [item.name for item in result.related_code] == ["alpha"]

    def test_lower_start_line_breaks_ties(self):
        later = make_item("a", start=6, end=6, code="xxxxx")
        earlier = make_item("z", start=5, end=5, code="yyyyy")
        context = make_context(related=[later, earlier])
        result = apply_context_budget(context, tight_budget(max_related_chars=5))
        assert [item.name for item in result.related_code] == ["z"]

    def test_ordering_is_deterministic(self):
        items = [
            make_item("b", start=5, end=5, code="bbbbb"),
            make_item("a", start=5, end=5, code="aaaaa"),
            make_item("c", start=7, end=7, code="ccccc"),
        ]
        budget = tight_budget(max_related_chars=15)
        first = [
            item.name
            for item in apply_context_budget(
                make_context(related=items), budget
            ).related_code
        ]
        second = [
            item.name
            for item in apply_context_budget(
                make_context(related=items), budget
            ).related_code
        ]
        assert first == second
        assert first == ["b", "a", "c"]

    def test_kept_items_preserve_input_order(self):
        items = [
            make_item("later", start=9, end=9, code="lllll"),
            make_item("first", start=1, end=1, code="fffff"),
            make_item("middle", start=5, end=5, code="mmmmm"),
        ]
        result = apply_context_budget(
            make_context(related=items), tight_budget()
        )
        assert [item.name for item in result.related_code] == [
            "later",
            "first",
            "middle",
        ]


class TestSingleItemLimit:
    def test_method_over_limit_is_dropped(self):
        item = make_item("method", start=2, end=2)
        context = make_context(related=[item])
        result = apply_context_budget(context, tight_budget(max_item_chars=5))
        assert result.related_code == []
        assert result.truncation.dropped_items == ["related:METHOD:method (2-2)"]
        assert result.truncation.reasons == [REASON_ITEM_OVERFLOW]
        assert result.truncation.removed_chars == len(item.code)

    def test_constructor_over_limit_is_dropped(self):
        item = make_item("A", kind=RelatedKind.CONSTRUCTOR, start=2, end=2)
        result = apply_context_budget(
            make_context(related=[item]), tight_budget(max_item_chars=5)
        )
        assert result.related_code == []
        assert result.truncation.dropped_items == [
            "related:CONSTRUCTOR:A (2-2)"
        ]

    def test_field_over_limit_is_dropped(self):
        item = make_item("field", kind=RelatedKind.FIELD, start=2, end=2)
        result = apply_context_budget(
            make_context(related=[item]), tight_budget(max_item_chars=5)
        )
        assert result.related_code == []
        assert result.truncation.dropped_items == ["related:FIELD:field (2-2)"]

    def test_nested_type_over_limit_degrades_to_header(self):
        nested = make_item(
            "Nested", kind=RelatedKind.NESTED_TYPE, start=3, end=5
        )
        context = make_context(
            related=[nested], classes=[make_class()], content=SOURCE
        )
        budget = tight_budget(max_item_chars=len(LINES[2]) + 2)
        result = apply_context_budget(context, budget)
        item = result.related_code[0]
        assert item.name == "Nested"
        assert (item.start_line, item.end_line) == (3, 3)
        assert item.code == LINES[2]
        assert item.truncated is True
        assert result.truncation.trimmed_items == [
            "related:NESTED_TYPE:Nested (3-5 -> 3-3)"
        ]
        assert result.truncation.reasons == [REASON_ITEM_OVERFLOW]
        assert result.truncation.removed_chars == len(nested.code) - len(LINES[2])
        assert result.stats.truncated_items == 1
        assert result.stats.related_total == 1
        assert result.stats.related_kept == 1
        assert result.stats.related_dropped == 0

    def test_nested_type_without_header_degradation_is_dropped(self):
        nested = make_item(
            "Nested", kind=RelatedKind.NESTED_TYPE, start=3, end=5
        )
        context = make_context(
            related=[nested], classes=[make_class()], content=SOURCE
        )
        budget = tight_budget(
            max_item_chars=len(LINES[2]) + 2, allow_nested_header_only=False
        )
        result = apply_context_budget(context, budget)
        assert result.related_code == []
        assert result.truncation.dropped_items == [
            "related:NESTED_TYPE:Nested (3-5)"
        ]
        assert result.truncation.trimmed_items == []

    def test_nested_type_without_recorded_header_is_dropped(self):
        nested = make_item(
            "Nested", kind=RelatedKind.NESTED_TYPE, start=3, end=5
        )
        context = make_context(
            related=[nested],
            classes=[make_class(header_end=0)],
            content=SOURCE,
        )
        result = apply_context_budget(context, tight_budget(max_item_chars=30))
        assert result.related_code == []

    def test_nested_type_without_matching_class_is_dropped(self):
        nested = make_item(
            "Nested", kind=RelatedKind.NESTED_TYPE, start=3, end=5
        )
        context = make_context(related=[nested], content=SOURCE)
        result = apply_context_budget(context, tight_budget(max_item_chars=30))
        assert result.related_code == []

    def test_nested_type_without_content_is_dropped(self):
        nested = make_item(
            "Nested", kind=RelatedKind.NESTED_TYPE, start=3, end=5
        )
        context = make_context(related=[nested], classes=[make_class()])
        result = apply_context_budget(context, tight_budget(max_item_chars=30))
        assert result.related_code == []

    def test_trim_that_still_exceeds_the_cap_is_dropped(self):
        nested = make_item(
            "Nested", kind=RelatedKind.NESTED_TYPE, start=3, end=5
        )
        context = make_context(
            related=[nested], classes=[make_class()], content=SOURCE
        )
        result = apply_context_budget(context, tight_budget(max_item_chars=10))
        assert result.related_code == []
        assert result.truncation.trimmed_items == []

    def test_trim_does_not_apply_to_already_truncated_items(self):
        nested = make_item(
            "Nested",
            kind=RelatedKind.NESTED_TYPE,
            start=3,
            end=3,
            code=LINES[2],
            truncated=True,
        )
        context = make_context(
            related=[nested], classes=[make_class()], content=SOURCE
        )
        result = apply_context_budget(context, tight_budget(max_item_chars=5))
        assert result.related_code == []
        assert result.truncation.trimmed_items == []


class TestChangedCodeProtection:
    def test_related_yields_before_changed_code(self):
        method = make_method(code="m" * 200)
        item = make_item("helper", start=2, end=2, code="h" * 50)
        context = make_context(related=[item], methods=[method])
        result = apply_context_budget(context, tight_budget(max_file_chars=100))
        assert result.related_code == []
        assert [m.code for m in result.methods] == ["m" * 200]
        assert REASON_FILE_BUDGET in result.truncation.reasons

    def test_all_related_can_be_dropped(self):
        items = [
            make_item("a", code="aaaaa"),
            make_item("b", code="bbbbb"),
        ]
        context = make_context(related=items, methods=[make_method()])
        result = apply_context_budget(context, tight_budget(max_related_chars=0))
        assert result.related_code == []
        assert result.stats.related_dropped == 2
        assert result.stats.related_kept == 0
        assert result.stats.related_total == 2

    def test_oversized_changed_code_is_kept_and_recorded(self):
        method = make_method(code="m" * 500)
        item = make_item("helper", start=2, end=2, code="h" * 20)
        context = make_context(related=[item], methods=[method])
        result = apply_context_budget(context, tight_budget(max_file_chars=100))
        assert [m.code for m in result.methods] == ["m" * 500]
        assert REASON_CHANGED_OVERFLOW in result.truncation.reasons
        assert result.truncation.applied is True
        assert result.stats.prompt_chars > 100

    def test_oversized_changed_code_records_reason_without_drops(self):
        method = make_method(code="m" * 500)
        context = make_context(methods=[method])
        result = apply_context_budget(context, tight_budget(max_file_chars=100))
        assert result.truncation.dropped_items == []
        assert result.truncation.trimmed_items == []
        assert result.truncation.reasons == [REASON_CHANGED_OVERFLOW]
        assert result.truncation.applied is True

    def test_keep_changed_code_false_still_protects_changed_code(self):
        method = make_method(code="m" * 200)
        context = make_context(methods=[method])
        budget = tight_budget(max_file_chars=50, keep_changed_code=False)
        result = apply_context_budget(context, budget)
        assert [m.code for m in result.methods] == ["m" * 200]
        assert REASON_CHANGED_OVERFLOW in result.truncation.reasons


class TestTruncationRecord:
    def test_no_truncation_means_no_fabricated_record(self):
        context = make_context(related=[make_item("helper", start=2, end=2)])
        result = apply_context_budget(context, tight_budget())
        assert result.truncation.applied is False
        assert result.truncation.reasons == []
        assert result.truncation.dropped_items == []
        assert result.truncation.trimmed_items == []
        assert result.truncation.removed_chars == 0

    def test_dropped_items_are_described(self):
        helper = make_item("helper", start=2, end=2)
        other = make_item("other", start=1, end=1)
        context = make_context(related=[helper, other])
        result = apply_context_budget(context, tight_budget(max_related_chars=10))
        assert [item.name for item in result.related_code] == ["other"]
        assert result.truncation.dropped_items == ["related:METHOD:helper (2-2)"]
        assert result.truncation.removed_chars == len(helper.code)

    def test_reasons_are_not_duplicated(self):
        items = [
            make_item("a", code="a" * 50),
            make_item("b", code="b" * 50),
        ]
        context = make_context(related=items)
        result = apply_context_budget(context, tight_budget(max_item_chars=5))
        assert result.truncation.reasons == [REASON_ITEM_OVERFLOW]
        assert len(result.truncation.dropped_items) == 2

    def test_removed_chars_sums_drops_and_trims(self):
        helper = make_item("helper", start=2, end=2)
        nested = make_item(
            "Nested", kind=RelatedKind.NESTED_TYPE, start=3, end=5
        )
        field = make_item("field", kind=RelatedKind.FIELD, start=1, end=1)
        context = make_context(
            related=[helper, nested, field],
            classes=[make_class()],
            content=SOURCE,
        )
        budget = tight_budget(
            max_item_chars=len(LINES[2]) + 2, max_related_chars=10**6
        )
        result = apply_context_budget(context, budget)
        expected = len(helper.code) + (
            len(nested.code) - len(LINES[2])
        )
        assert result.truncation.removed_chars == expected
        assert result.truncation.dropped_items == ["related:METHOD:helper (2-2)"]
        assert result.truncation.trimmed_items == [
            "related:NESTED_TYPE:Nested (3-5 -> 3-3)"
        ]

    def test_stats_reflect_the_trim(self):
        nested = make_item(
            "Nested", kind=RelatedKind.NESTED_TYPE, start=3, end=5
        )
        context = make_context(
            related=[nested], classes=[make_class()], content=SOURCE
        )
        result = apply_context_budget(context, tight_budget(max_item_chars=len(LINES[2]) + 2))
        assert result.stats.related_total == 1
        assert result.stats.related_kept == 1
        assert result.stats.related_dropped == 0
        assert result.stats.truncated_items == 1
        assert result.stats.prompt_chars == expected_prompt_chars(result)
        assert result.stats.estimated_tokens == estimate_tokens(
            "".join(payload_text(result)[kind] for kind in PAYLOAD_ORDER)
        )


class TestExactSlices:
    def test_every_kept_item_matches_the_source(self):
        helper = make_item("helper", start=2, end=2)
        nested = make_item(
            "Nested", kind=RelatedKind.NESTED_TYPE, start=3, end=5
        )
        fields = make_item("field", kind=RelatedKind.FIELD, start=1, end=1)
        context = make_context(
            related=[helper, nested, fields],
            classes=[make_class()],
            content=SOURCE,
        )
        result = apply_context_budget(
            context, tight_budget(max_item_chars=len(LINES[2]) + 2)
        )
        for item in result.related_code:
            assert item.code == "\n".join(
                LINES[item.start_line - 1 : item.end_line]
            )

    def test_trimmed_item_range_is_the_header(self):
        nested = make_item(
            "Nested", kind=RelatedKind.NESTED_TYPE, start=3, end=5
        )
        context = make_context(
            related=[nested], classes=[make_class()], content=SOURCE
        )
        result = apply_context_budget(
            context, tight_budget(max_item_chars=len(LINES[2]) + 2)
        )
        item = result.related_code[0]
        assert item.code == LINES[item.start_line - 1 : item.end_line][0]
        assert item.code == "\n".join(
            LINES[item.start_line - 1 : item.end_line]
        )


class TestImmutability:
    def make_tight_context(self):
        return make_context(
            related=[
                make_item("helper", start=2, end=2),
                make_item("Nested", kind=RelatedKind.NESTED_TYPE, start=3, end=5),
            ],
            methods=[make_method()],
            classes=[make_class()],
            content=SOURCE,
        )

    def test_result_is_an_independent_copy(self):
        context = self.make_tight_context()
        result = apply_context_budget(context, tight_budget(max_related_chars=10))
        assert result is not context
        assert result.related_code is not context.related_code

    def test_original_is_not_mutated(self):
        context = self.make_tight_context()
        before = context.model_dump()
        apply_context_budget(context, tight_budget(max_related_chars=10))
        assert context.model_dump() == before
        assert context.stats is None
        assert context.truncation is None

    def test_original_methods_classes_content_untouched(self):
        context = self.make_tight_context()
        related_before = [item.model_dump() for item in context.related_code]
        methods_before = [method.model_dump() for method in context.methods]
        classes_before = [item.model_dump() for item in context.classes]
        content_before = context.content
        apply_context_budget(context, tight_budget(max_related_chars=10))
        assert [item.model_dump() for item in context.related_code] == related_before
        assert [method.model_dump() for method in context.methods] == methods_before
        assert [item.model_dump() for item in context.classes] == classes_before
        assert context.content is content_before


class TestIdempotency:
    def make_context_with_trim_and_drop(self):
        helper = make_item("helper", start=2, end=2)
        nested = make_item(
            "Nested", kind=RelatedKind.NESTED_TYPE, start=3, end=5
        )
        field = make_item("field", kind=RelatedKind.FIELD, start=1, end=1)
        return make_context(
            related=[helper, nested, field],
            classes=[make_class()],
            content=SOURCE,
        )

    def test_repeated_apply_is_stable(self):
        context = self.make_context_with_trim_and_drop()
        budget = tight_budget(
            max_item_chars=len(LINES[2]) + 2, max_related_chars=55
        )
        first = apply_context_budget(context, budget)
        second = apply_context_budget(first, budget)
        assert second == first
        assert [item.name for item in second.related_code] == [
            item.name for item in first.related_code
        ]

    def test_truncated_nested_type_is_not_shrunk_further(self):
        context = self.make_context_with_trim_and_drop()
        budget = tight_budget(max_item_chars=len(LINES[2]) + 2)
        first = apply_context_budget(context, budget)
        trimmed = next(item for item in first.related_code if item.truncated)
        second = apply_context_budget(first, budget)
        again = next(item for item in second.related_code if item.truncated)
        assert (again.start_line, again.end_line) == (
            trimmed.start_line,
            trimmed.end_line,
        )
        assert again.code == trimmed.code

    def test_no_op_apply_is_stable(self):
        context = make_context(related=[make_item("helper", start=2, end=2)])
        first = apply_context_budget(context, tight_budget())
        second = apply_context_budget(first, tight_budget())
        assert second == first

    def test_records_survive_a_second_call(self):
        context = self.make_context_with_trim_and_drop()
        budget = tight_budget(
            max_item_chars=len(LINES[2]) + 2, max_related_chars=55
        )
        first = apply_context_budget(context, budget)
        second = apply_context_budget(first, budget)
        assert second.truncation == first.truncation
        assert second.stats == first.stats


class TestIntegrationWithBuilders:
    def test_real_pipeline_context_can_be_trimmed(self):
        from app.context.class_context_builder import attach_class_contexts
        from app.context.file_context_builder import build_file_context
        from app.context.method_context_builder import attach_method_contexts
        from app.context.related_code_builder import build_related_code

        source = (
            "public class Outer {\n"
            "    private int field;\n"
            "\n"
            "    public static class Nested {\n"
            "        void run() { }\n"
            "    }\n"
            "\n"
            "    public void changed() {\n"
            "        field++;\n"
            "    }\n"
            "}\n"
        )
        path = "src/main/java/cn/Outer.java"
        diff = FileDiff(
            path=path,
            status=FileStatus.MODIFIED,
            language=Language.JAVA,
            changed_ranges=[ChangedRange(start_line=9, end_line=9)],
            additions=1,
            deletions=1,
            patch_available=True,
        )
        context = attach_class_contexts(
            attach_method_contexts(
                build_file_context(diff, FileContent(path=path, content=source))
            )
        )
        context = context.model_copy(
            update={"related_code": build_related_code(context)}
        )
        stats_before = measure_context(context)
        assert stats_before.related_total >= 1

        budget = ContextBudget(
            max_item_chars=len("    public static class Nested {") + 2,
            max_related_chars=10**6,
            max_file_chars=10**6,
        )
        result = apply_context_budget(context, budget)
        lines = source.split("\n")
        for item in result.related_code:
            assert item.code == "\n".join(
                lines[item.start_line - 1 : item.end_line]
            )
        for method in result.methods:
            assert method.code == "\n".join(
                lines[method.start_line - 1 : method.end_line]
            )
        assert result.truncation.applied is True
        assert result.truncation.trimmed_items == [
            "related:NESTED_TYPE:Nested (4-6 -> 4-4)"
        ]
        trimmed = next(
            item for item in result.related_code if item.truncated
        )
        assert trimmed.end_line == 4

    def test_multi_file_api_is_available(self):
        from app.context import context_size_controller as module

        for name in (
            "plan_file_budgets",
            "apply_context_budget_to_files",
            "aggregate_stats",
        ):
            assert callable(getattr(module, name))


class TestEstimateTokensEmpty:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_none_is_tolerated(self):
        assert estimate_tokens(None) == 0


class TestEstimateTokensAscii:
    def test_single_character(self):
        assert estimate_tokens("a") == 1

    def test_exact_multiple_of_three(self):
        assert estimate_tokens("abc") == 1
        assert estimate_tokens("abcdef") == 2
        assert estimate_tokens("a" * 9) == 3

    def test_ceil_boundary(self):
        assert estimate_tokens("a" * 3) == 1
        assert estimate_tokens("a" * 4) == 2
        assert estimate_tokens("a" * 6) == 2
        assert estimate_tokens("a" * 7) == 3

    def test_whitespace_counts_as_other_characters(self):
        assert estimate_tokens("   ") == 1
        assert estimate_tokens("    ") == 2

    def test_long_ascii_text(self):
        assert estimate_tokens("a" * 30000) == 10000

    def test_code_snippet(self):
        text = "public class Demo {\n    void run() {}\n}\n"
        assert estimate_tokens(text) == (len(text) + 2) // 3


class TestEstimateTokensCjk:
    def test_single_cjk_character(self):
        assert estimate_tokens("中") == 1

    def test_multiple_cjk_characters(self):
        assert estimate_tokens("中文") == 2
        assert estimate_tokens("中文代码") == 4

    def test_cjk_punctuation(self):
        assert estimate_tokens("。") == 1
        assert estimate_tokens("，") == 1

    def test_fullwidth_forms(self):
        assert estimate_tokens("：") == 1
        assert estimate_tokens("（）") == 2

    def test_kana(self):
        assert estimate_tokens("あ") == 1

    def test_cjk_extension_a(self):
        assert estimate_tokens("\u3400") == 1

    def test_cjk_dominates_the_ratio(self):
        assert estimate_tokens("中" * 100) == 100


class TestEstimateTokensMixed:
    def test_ascii_then_cjk(self):
        assert estimate_tokens("abc中") == 2

    def test_cjk_then_ascii(self):
        assert estimate_tokens("中abc") == 2

    def test_interleaved(self):
        assert estimate_tokens("中a文b") == 3

    def test_short_ascii_with_cjk(self):
        assert estimate_tokens("ab中") == 2

    def test_mixed_code_and_comment(self):
        text = "int count = 0; // 计数器"
        cjk = 3
        other = len(text) - cjk
        assert estimate_tokens(text) == (other + 2) // 3 + cjk


class TestEstimateTokensProperties:
    def test_deterministic(self):
        text = "public void run() { /* 运行 */ }"
        assert estimate_tokens(text) == estimate_tokens(text)

    def test_monotonic_for_ascii_prefixes(self):
        base = "a" * 500
        previous = 0
        for length in range(0, len(base) + 1, 17):
            current = estimate_tokens(base[:length])
            assert current >= previous
            previous = current

    def test_monotonic_for_mixed_prefixes(self):
        base = "代码code" * 100
        previous = 0
        for length in range(0, len(base) + 1, 13):
            current = estimate_tokens(base[:length])
            assert current >= previous
            previous = current

    def test_input_is_not_mutated(self):
        text = "demo 演示"
        before = str(text)
        estimate_tokens(text)
        assert text == before

    def test_returns_int(self):
        assert isinstance(estimate_tokens("abc"), int)

    def test_never_negative(self):
        for text in ("", "a", "中", "a中b"):
            assert estimate_tokens(text) >= 0


class TestEstimateTokensNoDependencies:
    def test_module_imports_only_standard_library(self):
        import app.context.context_size_controller as module

        source = module.__dict__
        for forbidden in (
            "httpx",
            "requests",
            "openai",
            "tiktoken",
            "tokenizers",
            "transformers",
            "langchain",
            "langgraph",
        ):
            assert forbidden not in source
            assert not hasattr(module, forbidden)


class TestEstimateTokensContract:
    def test_matches_documented_formula(self):
        for text in (
            "",
            "abc",
            "中文",
            "abc中文",
            "public class A {}",
            "中文注释",
            "混合 mixed 内容",
        ):
            cjk = sum(
                1
                for char in text
                if "\u2e80" <= char <= "\u2fff"
                or "\u3000" <= char <= "\u303f"
                or "\u3040" <= char <= "\u30ff"
                or "\u31f0" <= char <= "\u31ff"
                or "\u3400" <= char <= "\u4dbf"
                or "\u4e00" <= char <= "\u9fff"
                or "\uf900" <= char <= "\ufaff"
                or "\ufe30" <= char <= "\ufe4f"
                or "\uff00" <= char <= "\uffef"
            )
            other = len(text) - cjk
            expected = -(-other // 3) + cjk
            assert estimate_tokens(text) == expected

    def test_ascii_is_never_underestimated_for_code(self):
        text = "public class Demo { private int count = 0; }"
        assert estimate_tokens(text) >= len(text) // 4


class TestEstimateTokensStability:
    def test_repeated_calls_are_stable(self):
        text = "中文" * 50 + "abc" * 50
        assert len({estimate_tokens(text) for _ in range(5)}) == 1


def multi_budget(**overrides):
    data = {
        "max_item_chars": 10**6,
        "max_related_chars": 10**6,
        "max_file_chars": 10**6,
        "min_file_chars": 100,
        "max_total_chars": None,
    }
    data.update(overrides)
    return ContextBudget(**data)


def make_file_with_items(path, item_names, item_code="i" * 20, method_code=None):
    related = [
        make_item(name, code=item_code, path=path, start=1, end=1)
        for name in item_names
    ]
    methods = []
    if method_code is not None:
        methods = [
            MethodContext(
                name="changed",
                start_line=1,
                end_line=2,
                enclosing_class="A",
                code=method_code,
            )
        ]
    return make_multi_file(path, related=related, methods=methods)


class TestPlanFileBudgets:
    def test_empty_weights(self):
        assert plan_file_budgets([], DEFAULT_BUDGET) == []

    def test_without_total_every_file_gets_the_per_file_cap(self):
        plans = plan_file_budgets([1, 2, 3], DEFAULT_BUDGET)
        assert [plan.max_file_chars for plan in plans] == [24000, 24000, 24000]
        assert [plan.max_related_chars for plan in plans] == [12000] * 3

    def test_equal_weights_share_the_total_equally(self):
        plans = plan_file_budgets(
            [1, 1, 1, 1], multi_budget(max_total_chars=30000)
        )
        assert [plan.max_file_chars for plan in plans] == [7500] * 4
        assert sum(plan.max_file_chars for plan in plans) == 30000

    def test_heavier_files_get_more(self):
        plans = plan_file_budgets(
            [1, 2, 3], multi_budget(max_total_chars=30000)
        )
        caps = [plan.max_file_chars for plan in plans]
        assert caps == sorted(caps)
        assert caps[0] < caps[1] < caps[2]
        assert sum(caps) == 30000

    def test_floor_is_honored_when_the_total_allows_it(self):
        plans = plan_file_budgets(
            [1, 2, 3], multi_budget(max_total_chars=30000, min_file_chars=4000)
        )
        assert all(plan.max_file_chars >= 4000 for plan in plans)
        assert all(plan.max_file_chars <= 24000 for plan in plans)

    def test_total_is_never_exceeded(self):
        for total in (1000, 5000, 12345, 60000):
            plans = plan_file_budgets(
                [1, 2, 3], multi_budget(max_total_chars=total)
            )
            assert sum(plan.max_file_chars for plan in plans) <= total

    def test_per_file_cap_is_never_exceeded(self):
        plans = plan_file_budgets(
            [1, 1], multi_budget(max_total_chars=10**6, max_file_chars=5000)
        )
        assert all(plan.max_file_chars == 5000 for plan in plans)

    def test_too_small_total_degrades_deterministically(self):
        budget = multi_budget(max_total_chars=5000, min_file_chars=4000)
        first = [plan.max_file_chars for plan in plan_file_budgets([1, 2, 3], budget)]
        second = [plan.max_file_chars for plan in plan_file_budgets([1, 2, 3], budget)]
        assert first == second == [0, 1000, 4000]
        assert sum(first) == 5000

    def test_degradation_gives_floors_to_heavier_files_first(self):
        budget = multi_budget(max_total_chars=100, min_file_chars=100)
        plans = plan_file_budgets([1, 3], budget)
        assert [plan.max_file_chars for plan in plans] == [0, 100]

    def test_output_order_matches_input(self):
        plans = plan_file_budgets(
            [3, 1, 2], multi_budget(max_total_chars=30000)
        )
        caps = [plan.max_file_chars for plan in plans]
        assert caps[0] > caps[1]
        assert caps[2] > caps[1]

    def test_zero_and_negative_weights_are_treated_as_one(self):
        plans = plan_file_budgets(
            [0, -5], multi_budget(max_total_chars=20000)
        )
        assert plans[0].max_file_chars == plans[1].max_file_chars

    def test_related_is_capped_by_the_file_cap(self):
        plans = plan_file_budgets(
            [1], multi_budget(max_total_chars=500, min_file_chars=100)
        )
        assert plans[0].max_file_chars == 500
        assert plans[0].max_related_chars == 500

    def test_related_stays_at_its_own_limit_when_roomier(self):
        plans = plan_file_budgets(
            [1], multi_budget(max_total_chars=30000, max_related_chars=2000)
        )
        assert plans[0].max_related_chars == 2000

    def test_input_budget_is_not_modified(self):
        budget = multi_budget(max_total_chars=30000)
        before = budget.model_dump()
        plan_file_budgets([1, 2], budget)
        assert budget.model_dump() == before

    def test_limits_other_than_file_caps_are_copied(self):
        budget = multi_budget(
            max_total_chars=30000,
            max_item_chars=123,
            keep_changed_code=False,
        )
        plan = plan_file_budgets([1], budget)[0]
        assert plan.max_item_chars == 123
        assert plan.keep_changed_code is False
        assert plan.max_total_chars == 30000


def make_heavy_file(path, method_code="m" * 400, method_count=2):
    methods = [
        MethodContext(
            name=f"changed{index}",
            start_line=1,
            end_line=2,
            enclosing_class="A",
            code=method_code,
        )
        for index in range(method_count)
    ]
    return make_multi_file(path, methods=methods)


class TestApplyBudgetToFiles:
    def test_empty_list(self):
        assert apply_context_budget_to_files([], multi_budget()) == []

    def test_single_file_matches_the_single_file_controller(self):
        file_context = make_file_with_items("a/A.java", ["a1", "a2"])
        budget = multi_budget()
        expected = apply_context_budget(
            file_context, plan_file_budgets([1], budget)[0]
        )
        assert apply_context_budget_to_files([file_context], budget) == [expected]

    def test_without_total_phase_three_does_not_run(self):
        files = [
            make_file_with_items("a/A.java", ["a1"]),
            make_file_with_items("b/B.java", ["b1"]),
        ]
        results = apply_context_budget_to_files(files, multi_budget())
        assert [len(f.related_code) for f in results] == [1, 1]
        assert all(f.truncation.applied is False for f in results)

    def test_generous_total_changes_nothing(self):
        files = [
            make_file_with_items("a/A.java", ["a1"]),
            make_file_with_items("b/B.java", ["b1"]),
        ]
        results = apply_context_budget_to_files(
            files, multi_budget(max_total_chars=10**6)
        )
        assert [len(f.related_code) for f in results] == [1, 1]

    def test_lower_weight_file_drops_first(self):
        low = make_file_with_items("a/A.java", ["low1", "low2"])
        high = make_heavy_file("b/B.java")
        results = apply_context_budget_to_files(
            [low, high], multi_budget(min_file_chars=50, max_total_chars=400)
        )
        assert results[0].related_code == []
        assert results[0].truncation.dropped_items == [
            "related:METHOD:low1 (1-1)",
            "related:METHOD:low2 (1-1)",
        ]
        assert REASON_TOTAL_BUDGET in results[0].truncation.reasons
        assert [method.code for method in results[1].methods] == [
            "m" * 400,
            "m" * 400,
        ]
        assert REASON_CHANGED_TOTAL_OVERFLOW in results[1].truncation.reasons

    def test_within_a_file_the_lowest_priority_drops_first(self):
        items = [
            make_item(
                "nested",
                kind=RelatedKind.NESTED_TYPE,
                code="n" * 20,
                path="a/A.java",
            ),
            make_item("helper", code="h" * 20, path="a/A.java"),
        ]
        files = [make_multi_file("a/A.java", related=items)]
        results = apply_context_budget_to_files(
            files, multi_budget(min_file_chars=50, max_total_chars=50)
        )
        assert [item.name for item in results[0].related_code] == ["helper"]

    def test_group_fits_the_total_when_items_were_available(self):
        files = [
            make_file_with_items("a/A.java", ["a1", "a2", "a3"]),
            make_file_with_items("b/B.java", ["b1", "b2", "b3"]),
        ]
        grouped = aggregate_stats(files).prompt_chars
        limit = grouped - 60
        results = apply_context_budget_to_files(
            files, multi_budget(min_file_chars=50, max_total_chars=limit)
        )
        assert aggregate_stats(results).prompt_chars <= limit

    def test_changed_code_is_protected(self):
        method_code = "m" * 400
        files = [
            make_file_with_items("a/A.java", ["a1"], method_code=method_code),
            make_file_with_items("b/B.java", ["b1"], method_code=method_code),
        ]
        results = apply_context_budget_to_files(
            files, multi_budget(min_file_chars=50, max_total_chars=500)
        )
        assert [f.methods[0].code for f in results] == [method_code, method_code]

    def test_diff_hunks_are_never_trimmed(self):
        hunk = Hunk(
            header="@@ -1,2 +1,2 @@",
            old_start=1,
            old_count=2,
            new_start=1,
            new_count=2,
            lines=[
                DiffLine(kind=DiffLineKind.CONTEXT, text="class A {"),
                DiffLine(kind=DiffLineKind.ADDED, text="    int x = 1;"),
            ],
        )
        file_context = make_file_with_items("a/A.java", ["a1"])
        file_context = file_context.model_copy(
            update={
                "file_diff": file_context.file_diff.model_copy(
                    update={"hunks": [hunk]}
                )
            }
        )
        results = apply_context_budget_to_files(
            [file_context], multi_budget(min_file_chars=10, max_total_chars=10)
        )
        assert results[0].file_diff.hunks == [hunk]

    def test_changed_only_overflow_is_recorded_not_broken(self):
        method_code = "m" * 400
        files = [
            make_file_with_items("a/A.java", ["a1"], method_code=method_code),
            make_file_with_items("b/B.java", ["b1"], method_code=method_code),
        ]
        results = apply_context_budget_to_files(
            files, multi_budget(min_file_chars=50, max_total_chars=500)
        )
        for file_context in results:
            assert file_context.related_code == []
            assert REASON_CHANGED_TOTAL_OVERFLOW in file_context.truncation.reasons
            assert file_context.truncation.applied is True
        assert aggregate_stats(results).prompt_chars > 500

    def test_output_order_matches_input(self):
        files = [
            make_file_with_items("c/C.java", ["c1"]),
            make_file_with_items("a/A.java", ["a1"]),
            make_file_with_items("b/B.java", ["b1"]),
        ]
        results = apply_context_budget_to_files(
            files, multi_budget(max_total_chars=10**6)
        )
        assert [f.file_diff.path for f in results] == [
            "c/C.java",
            "a/A.java",
            "b/B.java",
        ]

    def test_inputs_are_not_mutated(self):
        files = [
            make_file_with_items("a/A.java", ["a1", "a2"]),
            make_file_with_items("b/B.java", ["b1"]),
        ]
        before = [f.model_dump() for f in files]
        grouped = aggregate_stats(files).prompt_chars
        apply_context_budget_to_files(
            files, multi_budget(min_file_chars=50, max_total_chars=grouped - 30)
        )
        assert [f.model_dump() for f in files] == before
        assert files[0].stats is None
        assert files[0].truncation is None

    def test_repeated_execution_is_stable(self):
        files = [
            make_file_with_items("a/A.java", ["a1", "a2", "a3"]),
            make_file_with_items("b/B.java", ["b1", "b2", "b3"]),
        ]
        budget = multi_budget(
            min_file_chars=50,
            max_total_chars=aggregate_stats(files).prompt_chars - 60,
        )
        first = apply_context_budget_to_files(files, budget)
        second = apply_context_budget_to_files(first, budget)
        assert second == first

    def test_changed_overflow_is_stable_on_repeat(self):
        method_code = "m" * 400
        files = [make_file_with_items("a/A.java", [], method_code=method_code)]
        budget = multi_budget(min_file_chars=50, max_total_chars=100)
        first = apply_context_budget_to_files(files, budget)
        second = apply_context_budget_to_files(first, budget)
        assert second == first
        assert REASON_CHANGED_TOTAL_OVERFLOW in first[0].truncation.reasons

    def test_stats_reflect_the_group_cuts(self):
        low = make_file_with_items("a/A.java", ["low1", "low2"])
        high = make_heavy_file("b/B.java")
        results = apply_context_budget_to_files(
            [low, high], multi_budget(min_file_chars=50, max_total_chars=400)
        )
        assert results[0].stats.related_total == 2
        assert results[0].stats.related_kept == 0
        assert results[0].stats.related_dropped == 2
        assert results[0].stats.truncated_items == 0
        assert results[0].stats.prompt_chars == measure_context(
            results[0]
        ).prompt_chars
        assert results[1].stats.related_total == 0
        assert results[1].stats.prompt_chars == measure_context(
            results[1]
        ).prompt_chars


class TestAggregateStats:
    def test_empty_list(self):
        stats = aggregate_stats([])
        assert stats.prompt_chars == 0
        assert stats.prompt_chars_by_kind == {}
        assert stats.estimated_tokens == 0
        assert stats.related_total == 0
        assert stats.related_kept == 0
        assert stats.related_dropped == 0
        assert stats.truncated_items == 0
        assert stats.retained_source_chars == 0

    def test_sums_every_field(self):
        first = make_multi_file("a/A.java").model_copy(
            update={
                "stats": ContextStats(
                    prompt_chars=100,
                    prompt_chars_by_kind={"diff": 40, "metadata": 60},
                    estimated_tokens=30,
                    related_total=2,
                    related_kept=1,
                    related_dropped=1,
                    truncated_items=1,
                    retained_source_chars=500,
                )
            }
        )
        second = make_multi_file("b/B.java").model_copy(
            update={
                "stats": ContextStats(
                    prompt_chars=50,
                    prompt_chars_by_kind={"diff": 10, "related": 40},
                    estimated_tokens=15,
                    related_total=1,
                    related_kept=1,
                    related_dropped=0,
                    truncated_items=0,
                    retained_source_chars=200,
                )
            }
        )
        stats = aggregate_stats([first, second])
        assert stats.prompt_chars == 150
        assert stats.estimated_tokens == 45
        assert stats.related_total == 3
        assert stats.related_kept == 2
        assert stats.related_dropped == 1
        assert stats.truncated_items == 1
        assert stats.retained_source_chars == 700

    def test_kind_keys_merge_in_first_seen_order(self):
        first = make_multi_file("a/A.java").model_copy(
            update={
                "stats": ContextStats(
                    prompt_chars=10,
                    prompt_chars_by_kind={"diff": 4, "metadata": 6},
                )
            }
        )
        second = make_multi_file("b/B.java").model_copy(
            update={
                "stats": ContextStats(
                    prompt_chars=4,
                    prompt_chars_by_kind={"related": 3, "diff": 1},
                )
            }
        )
        stats = aggregate_stats([first, second])
        assert stats.prompt_chars_by_kind == {
            "diff": 5,
            "metadata": 6,
            "related": 3,
        }
        assert list(stats.prompt_chars_by_kind) == ["diff", "metadata", "related"]

    def test_missing_stats_are_measured(self):
        files = [make_file_with_items("a/A.java", ["a1"])]
        expected = measure_context(files[0])
        stats = aggregate_stats(files)
        assert stats.prompt_chars == expected.prompt_chars
        assert stats.prompt_chars_by_kind == expected.prompt_chars_by_kind
        assert stats.related_total == 1

    def test_mixed_missing_and_present_stats(self):
        measured_file = make_file_with_items("a/A.java", ["a1"])
        measured = measure_context(measured_file)
        with_stats = make_multi_file("b/B.java").model_copy(
            update={"stats": ContextStats(prompt_chars=10)}
        )
        stats = aggregate_stats([with_stats, measured_file])
        assert stats.prompt_chars == 10 + measured.prompt_chars

    def test_measurement_does_not_attach_stats(self):
        files = [make_file_with_items("a/A.java", ["a1"])]
        aggregate_stats(files)
        assert files[0].stats is None

    def test_inputs_are_not_modified(self):
        file_context = make_file_with_items("a/A.java", ["a1"]).model_copy(
            update={"stats": ContextStats(prompt_chars=10)}
        )
        before = file_context.model_dump()
        aggregate_stats([file_context])
        assert file_context.model_dump() == before

    def test_prompt_chars_equals_the_kind_sum(self):
        files = [
            make_file_with_items("a/A.java", ["a1"]),
            make_file_with_items("b/B.java", ["b1"]),
        ]
        stats = aggregate_stats(files)
        assert stats.prompt_chars == sum(stats.prompt_chars_by_kind.values())


class TestAggregateTruncation:
    def test_empty_list(self):
        assert aggregate_truncation([]) == Truncation()

    def test_files_without_records_contribute_nothing(self):
        files = [make_multi_file("a/A.java"), make_multi_file("b/B.java")]
        assert aggregate_truncation(files) == Truncation()

    def test_sums_and_ors_records_in_file_order(self):
        first = make_multi_file("a/A.java").model_copy(
            update={
                "truncation": Truncation(
                    applied=True,
                    reasons=["related budget exceeded"],
                    dropped_items=["related:METHOD:a (1-1)"],
                    removed_chars=10,
                )
            }
        )
        second = make_multi_file("b/B.java").model_copy(
            update={
                "truncation": Truncation(
                    applied=False,
                    reasons=["total budget exceeded"],
                    trimmed_items=["related:NESTED_TYPE:N (2-3 -> 2-2)"],
                    removed_chars=5,
                )
            }
        )

        record = aggregate_truncation([first, second])

        assert record.applied is True
        assert record.reasons == [
            "related budget exceeded",
            "total budget exceeded",
        ]
        assert record.dropped_items == ["related:METHOD:a (1-1)"]
        assert record.trimmed_items == ["related:NESTED_TYPE:N (2-3 -> 2-2)"]
        assert record.removed_chars == 15

    def test_reasons_are_deduplicated_first_seen(self):
        first = make_multi_file("a/A.java").model_copy(
            update={
                "truncation": Truncation(
                    applied=True, reasons=["related budget exceeded"]
                )
            }
        )
        second = make_multi_file("b/B.java").model_copy(
            update={
                "truncation": Truncation(
                    applied=True,
                    reasons=["related budget exceeded", "file budget exceeded"],
                )
            }
        )

        record = aggregate_truncation([first, second])

        assert record.reasons == [
            "related budget exceeded",
            "file budget exceeded",
        ]

    def test_inputs_are_not_modified(self):
        files = [
            make_multi_file("a/A.java").model_copy(
                update={
                    "truncation": Truncation(applied=True, removed_chars=3)
                }
            )
        ]
        before = files[0].model_dump()
        aggregate_truncation(files)
        assert files[0].model_dump() == before


class TestMultiFileIntegration:
    def build_real_files(self, paths):
        from app.context.class_context_builder import attach_class_contexts
        from app.context.file_context_builder import build_file_context
        from app.context.method_context_builder import (
            attach_method_contexts,
            find_methods,
        )
        from app.context.related_code_builder import build_related_code

        root = pathlib.Path(__file__).resolve().parents[2]
        files = []
        for relative in paths:
            source = (root / relative).read_text(encoding="utf-8")
            language = (
                Language.PYTHON if relative.endswith(".py") else Language.JAVA
            )
            methods = find_methods(source, language)
            target = methods[len(methods) // 2]
            line = (target.start_line + target.end_line) // 2
            diff = FileDiff(
                path=relative,
                status=FileStatus.MODIFIED,
                language=language,
                changed_ranges=[ChangedRange(start_line=line, end_line=line)],
                additions=1,
                deletions=1,
                patch_available=True,
            )
            context = attach_class_contexts(
                attach_method_contexts(
                    build_file_context(
                        diff, FileContent(path=relative, content=source)
                    )
                )
            )
            files.append(
                context.model_copy(
                    update={"related_code": build_related_code(context)}
                )
            )
        return files

    def test_real_multi_file_pipeline(self):
        files = self.build_real_files(
            [
                "agent/app/context/related_code_builder.py",
                "agent/app/context/class_context_builder.py",
            ]
        )
        results = apply_context_budget_to_files(files, DEFAULT_BUDGET)
        assert [f.file_diff.path for f in results] == [
            f.file_diff.path for f in files
        ]
        assert aggregate_stats(results).prompt_chars > 0
        for file_context in results:
            assert file_context.methods

    def test_real_multi_file_tight_total(self):
        files = self.build_real_files(
            [
                "agent/app/context/related_code_builder.py",
                "agent/app/context/class_context_builder.py",
            ]
        )
        grouped = aggregate_stats(files).prompt_chars
        budget = multi_budget(
            min_file_chars=200, max_total_chars=grouped // 2
        )
        results = apply_context_budget_to_files(files, budget)
        total = aggregate_stats(results).prompt_chars
        exhausted = all(f.related_code == [] for f in results)
        assert total <= budget.max_total_chars or exhausted
        assert all(f.methods for f in results)
        again = apply_context_budget_to_files(results, budget)
        assert again == results


class TestTokenControlConversions:
    def test_tokens_for_chars_zero(self):
        assert tokens_for_chars(0) == 0

    def test_tokens_for_chars_none(self):
        assert tokens_for_chars(None) == 0

    def test_tokens_for_chars_negative(self):
        assert tokens_for_chars(-10) == 0

    def test_tokens_for_chars_ceil(self):
        assert tokens_for_chars(1) == 1
        assert tokens_for_chars(3) == 1
        assert tokens_for_chars(4) == 2
        assert tokens_for_chars(9) == 3
        assert tokens_for_chars(10) == 4

    def test_tokens_for_chars_custom_rate(self):
        assert tokens_for_chars(10, chars_per_token=2) == 5
        assert tokens_for_chars(10, chars_per_token=4) == 3

    def test_tokens_for_chars_rate_is_clamped(self):
        assert tokens_for_chars(10, chars_per_token=0) == 10
        assert tokens_for_chars(10, chars_per_token=-3) == 10

    def test_chars_for_tokens_zero(self):
        assert chars_for_tokens(0) == 0

    def test_chars_for_tokens_none(self):
        assert chars_for_tokens(None) == 0

    def test_chars_for_tokens_negative(self):
        assert chars_for_tokens(-5) == 0

    def test_chars_for_tokens_multiple(self):
        assert chars_for_tokens(1) == 3
        assert chars_for_tokens(8) == 24

    def test_chars_for_tokens_custom_rate(self):
        assert chars_for_tokens(5, chars_per_token=4) == 20
        assert chars_for_tokens(5, chars_per_token=0) == 5

    def test_round_trip_is_exact(self):
        for tokens in range(0, 60):
            assert tokens_for_chars(chars_for_tokens(tokens)) == tokens

    def test_char_round_trip_never_shrinks(self):
        for chars in (0, 1, 2, 3, 7, 100, 1000):
            assert chars_for_tokens(tokens_for_chars(chars)) >= chars

    def test_matches_estimate_tokens_for_ascii(self):
        for text in (
            "",
            "a",
            "abcd",
            "public class Demo {}",
            "def run():\n    return 1\n",
            " " * 17,
            "{}();,",
        ):
            assert tokens_for_chars(len(text)) == estimate_tokens(text)

    def test_large_conversion(self):
        assert tokens_for_chars(30000) == 10000
        assert chars_for_tokens(10000) == 30000

    def test_deterministic(self):
        assert len({tokens_for_chars(12345) for _ in range(5)}) == 1
        assert len({chars_for_tokens(1234) for _ in range(5)}) == 1

    def test_strings_are_not_modified(self):
        text = "public class A {}"
        before = str(text)
        tokens_for_chars(len(text))
        chars_for_tokens(5)
        assert text == before


class TestBudgetFromTokens:
    def test_without_arguments_matches_default_budget(self):
        assert budget_from_tokens() == ContextBudget()

    def test_returns_a_context_budget(self):
        assert isinstance(budget_from_tokens(), ContextBudget)

    def test_file_tokens_convert_to_file_chars(self):
        budget = budget_from_tokens(max_file_tokens=8000)
        assert budget.max_file_chars == 24000
        assert budget.max_related_chars == DEFAULT_BUDGET.max_related_chars

    def test_total_tokens_convert_to_total_chars(self):
        budget = budget_from_tokens(max_total_tokens=24000)
        assert budget.max_total_chars == 72000

    def test_related_and_item_tokens_convert(self):
        budget = budget_from_tokens(
            max_related_tokens=4000, max_item_tokens=2000
        )
        assert budget.max_related_chars == 12000
        assert budget.max_item_chars == 6000

    def test_min_file_tokens_convert(self):
        budget = budget_from_tokens(min_file_tokens=1000)
        assert budget.min_file_chars == 3000

    def test_all_limits_together(self):
        budget = budget_from_tokens(
            max_file_tokens=1000,
            max_total_tokens=2000,
            max_related_tokens=500,
            max_item_tokens=100,
            min_file_tokens=50,
        )
        assert budget.max_file_chars == 3000
        assert budget.max_total_chars == 6000
        assert budget.max_related_chars == 1500
        assert budget.max_item_chars == 300
        assert budget.min_file_chars == 150

    def test_unspecified_limits_stay_from_the_base(self):
        base = ContextBudget(
            keep_changed_code=False,
            allow_nested_header_only=False,
            max_total_chars=1234,
        )
        budget = budget_from_tokens(max_file_tokens=1000, base=base)
        assert budget.max_file_chars == 3000
        assert budget.max_total_chars == 1234
        assert budget.keep_changed_code is False
        assert budget.allow_nested_header_only is False

    def test_custom_rate(self):
        budget = budget_from_tokens(max_file_tokens=1000, chars_per_token=4)
        assert budget.max_file_chars == 4000

    def test_negative_tokens_become_zero(self):
        budget = budget_from_tokens(
            max_file_tokens=-5, max_total_tokens=-1
        )
        assert budget.max_file_chars == 0
        assert budget.max_total_chars == 0

    def test_base_is_not_modified(self):
        base = ContextBudget()
        before = base.model_dump()
        budget_from_tokens(max_file_tokens=1000, base=base)
        assert base.model_dump() == before

    def test_result_feeds_the_single_file_controller(self):
        method = make_method(code="abc")
        item = make_item("helper", start=2, end=2, code="h" * 60)
        context = make_context(methods=[method], related=[item])
        budget = budget_from_tokens(max_file_tokens=20)
        assert budget.max_file_chars == 60
        result = apply_context_budget(context, budget)
        assert result.related_code == []
        assert [m.code for m in result.methods] == ["abc"]

    def test_result_feeds_plan_file_budgets(self):
        budget = budget_from_tokens(max_total_tokens=10000)
        plans = plan_file_budgets([1, 1], budget)
        assert len(plans) == 2
        assert sum(plan.max_file_chars for plan in plans) <= 30000

    def test_result_feeds_the_multi_file_controller(self):
        low = make_file_with_items("a/A.java", ["low1", "low2"])
        high = make_heavy_file("b/B.java")
        budget = budget_from_tokens(
            max_total_tokens=200, base=multi_budget(min_file_chars=0)
        )
        results = apply_context_budget_to_files([low, high], budget)
        assert [f.file_diff.path for f in results] == ["a/A.java", "b/B.java"]
        for file_context in results:
            assert file_context.stats.estimated_tokens == measure_context(
                file_context
            ).estimated_tokens

    def test_ascii_context_fits_the_token_cap(self):
        method = make_method(code="abc")
        item = make_item("helper", start=2, end=2, code="h" * 60)
        context = make_context(methods=[method], related=[item])
        budget = budget_from_tokens(max_file_tokens=20)
        result = apply_context_budget(context, budget)
        assert measure_context(result).estimated_tokens <= 20

    def test_estimator_and_stats_stay_consistent(self):
        context = make_context(
            methods=[make_method()], related=[make_item("helper", start=2, end=2)]
        )
        result = apply_context_budget(
            context, budget_from_tokens(max_file_tokens=1000)
        )
        assert result.stats.estimated_tokens == measure_context(
            result
        ).estimated_tokens


class TestTokenControlScenarios:
    def test_english_text(self):
        assert estimate_tokens("public class A") == 5
        assert estimate_tokens("hello world!") == 4

    def test_chinese_text(self):
        assert estimate_tokens("中文") == 2
        assert estimate_tokens("代码审查") == 4

    def test_java_code(self):
        text = "public class Demo {\n    void run() {}\n}\n"
        assert estimate_tokens(text) == (len(text) + 2) // 3

    def test_python_code(self):
        text = "def run():\n    return 1\n"
        assert estimate_tokens(text) == (len(text) + 2) // 3

    def test_mixed_language(self):
        text = "int count = 0; // 计数器"
        cjk = 3
        assert estimate_tokens(text) == (len(text) - cjk + 2) // 3 + cjk

    def test_whitespace_and_punctuation(self):
        assert estimate_tokens("    ") == 2
        assert estimate_tokens("\t\n") == 1
        assert estimate_tokens("{}();,") == 2

    def test_empty_and_tiny(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens(None) == 0
        assert estimate_tokens("a") == 1
        assert estimate_tokens("中") == 1

    def test_large_text(self):
        assert estimate_tokens("x" * 30000) == 10000
        assert estimate_tokens("中" * 3000) == 3000

    def test_boundary_between_ceil_steps(self):
        assert estimate_tokens("x" * 3) == 1
        assert estimate_tokens("x" * 4) == 2

    def test_deterministic_repeats(self):
        text = "混合 mixed 代码 code"
        assert len({estimate_tokens(text) for _ in range(10)}) == 1


class TestTokenControlBoundary:
    def test_token_api_is_available(self):
        from app.context import context_size_controller as module

        for name in (
            "estimate_tokens",
            "tokens_for_chars",
            "chars_for_tokens",
            "budget_from_tokens",
        ):
            assert callable(getattr(module, name))

    def test_no_tokenizer_sdk_is_used(self):
        from app.context import context_size_controller as module

        for name in ("tiktoken", "tokenizers", "transformers", "sentencepiece"):
            assert name not in module.__dict__
            assert not hasattr(module, name)

    def test_no_pr_or_llm_integration(self):
        from app.context import context_size_controller as module

        for name in (
            "fetch_pr",
            "PrContext",
            "CodeContextBuilder",
            "build_code_context",
            "chat",
            "invoke",
        ):
            assert not hasattr(module, name)

    def test_module_imports_are_local(self):
        from app.context import context_size_controller as module

        source = module.__dict__
        for forbidden in ("httpx", "requests", "openai", "langchain", "langgraph"):
            assert forbidden not in source

    def test_token_conversion_does_not_modify_the_base_budget(self):
        base = ContextBudget()
        before = base.model_dump()
        budget_from_tokens(
            max_file_tokens=1,
            max_total_tokens=1,
            base=base,
        )
        assert base.model_dump() == before

    def test_original_context_is_unchanged_by_a_token_budget(self):
        method = make_method(code="abc")
        item = make_item("helper", start=2, end=2, code="h" * 60)
        context = make_context(methods=[method], related=[item])
        before = context.model_dump()
        apply_context_budget(context, budget_from_tokens(max_file_tokens=20))
        assert context.model_dump() == before
        assert context.stats is None
        assert context.truncation is None