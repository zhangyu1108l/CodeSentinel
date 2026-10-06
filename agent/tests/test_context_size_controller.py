"""Tests for the Phase 6.6 token estimator and size controller."""

from app.context.context_size_controller import (
    DEFAULT_BUDGET,
    REASON_CHANGED_OVERFLOW,
    REASON_FILE_BUDGET,
    REASON_ITEM_OVERFLOW,
    REASON_RELATED_BUDGET,
    apply_context_budget,
    estimate_tokens,
    measure_context,
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
):
    if code is None:
        code = "\n".join(LINES[start - 1 : end])
    return RelatedCodeContext(
        path=PATH,
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

    def test_module_has_no_multi_file_api(self):
        from app.context import context_size_controller as module

        for name in (
            "plan_file_budgets",
            "apply_context_budget_to_files",
            "aggregate_stats",
        ):
            assert not hasattr(module, name)


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