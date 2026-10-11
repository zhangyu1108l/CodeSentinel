"""Tests for the Phase 8.8 evaluation foundation.

The cases are static fixtures, the metrics are pure functions: no LLM,
no tools, no network. No test asserts a quality threshold; only the
matching and arithmetic definitions are locked.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.evaluation.loader import (
    default_cases_root,
    load_case,
    load_cases,
)
from app.evaluation.metrics import (
    PredictedFinding,
    aggregate_metrics,
    evaluate_case,
    evaluate_cases,
    ranges_intersect,
)
from app.evaluation.models import (
    EvalCase,
    EvalLanguage,
    EvalSource,
    ExpectedFinding,
)
from app.schemas.report import AnalysisFinding, FindingSource
from app.schemas.review import Category, ReviewFinding, Severity


def make_expected(
    category=Category.BUG,
    rule_id="R1",
    file_path="sample.py",
    start=2,
    end=2,
):
    return ExpectedFinding(
        rule_id=rule_id,
        category=category,
        severity=Severity.HIGH,
        file_path=file_path,
        start_line=start,
        end_line=end,
    )


def make_case(
    case_id="case-1",
    category=Category.BUG,
    language=EvalLanguage.PYTHON,
    expected=None,
    file_path="sample.py",
):
    return EvalCase(
        case_id=case_id,
        language=language,
        category=category,
        source=EvalSource(file_path=file_path, code="x = 1\n"),
        expected_findings=expected or [make_expected(category=category)],
    )


def predicted(
    category=Category.BUG,
    rule_id="R1",
    file_path="sample.py",
    start=2,
    end=2,
):
    return PredictedFinding(
        category=category,
        severity=Severity.HIGH,
        rule_id=rule_id,
        file_path=file_path,
        start_line=start,
        end_line=end,
    )


class TestLoader:
    def test_shipped_cases_load(self):
        cases = load_cases()

        assert len(cases) >= 8
        languages = {case.language for case in cases}
        categories = {case.category for case in cases}
        assert languages == {EvalLanguage.JAVA, EvalLanguage.PYTHON}
        assert categories == {
            Category.BUG,
            Category.SECURITY,
            Category.PERFORMANCE,
            Category.QUALITY,
        }

    def test_every_language_category_combination_has_a_case(self):
        cases = load_cases()

        combinations = {
            (case.language, case.category) for case in cases
        }
        assert combinations == {
            (language, category)
            for language in EvalLanguage
            for category in Category
        }

    def test_default_root_is_the_repository_directory(self):
        root = default_cases_root()

        assert root.name == "test-cases"
        assert (root / "README.md").is_file()

    def test_case_ids_are_unique(self):
        cases = load_cases()

        assert len({case.case_id for case in cases}) == len(cases)

    def test_duplicate_ids_are_rejected(self, tmp_path):
        case = make_case(case_id="dup")
        for name in ("a.json", "b.json"):
            (tmp_path / name).write_text(
                case.model_dump_json(), encoding="utf-8"
            )

        with pytest.raises(ValueError, match="duplicate"):
            load_cases(tmp_path)

    def test_missing_directory_is_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            load_cases(tmp_path / "missing")

    def test_invalid_case_reports_its_path(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not json", encoding="utf-8")

        with pytest.raises(ValueError, match="bad.json"):
            load_case(path)


class TestCaseSchema:
    def test_inverted_range_is_rejected(self):
        with pytest.raises(ValidationError):
            ExpectedFinding(
                rule_id="R1",
                category=Category.BUG,
                severity=Severity.HIGH,
                file_path="sample.py",
                start_line=5,
                end_line=3,
            )

    def test_absolute_path_is_rejected(self):
        with pytest.raises(ValidationError):
            EvalSource(file_path="/etc/passwd", code="x = 1\n")

    def test_category_must_match_findings(self):
        with pytest.raises(ValidationError):
            make_case(
                category=Category.BUG,
                expected=[
                    make_expected(category=Category.SECURITY)
                ],
            )

    def test_finding_must_target_the_source_file(self):
        with pytest.raises(ValidationError):
            make_case(
                expected=[make_expected(file_path="other.py")]
            )

    def test_expected_findings_must_not_be_empty(self):
        data = make_case().model_dump()
        data["expected_findings"] = []

        with pytest.raises(ValidationError):
            EvalCase.model_validate(data)


class TestMatching:
    def test_exact_match_counts_tp_and_rule_match(self):
        match = evaluate_case(make_case(), [predicted()])

        assert match.true_positives == 1
        assert match.false_positives == 0
        assert match.false_negatives == 0
        assert match.rule_matches == 1

    def test_rule_id_is_not_part_of_the_match(self):
        match = evaluate_case(
            make_case(), [predicted(rule_id="OTHER-1")]
        )

        assert match.true_positives == 1
        assert match.rule_matches == 0

    def test_touching_ranges_intersect(self):
        assert ranges_intersect(2, 3, 3, 4) is True
        assert ranges_intersect(2, 3, 4, 5) is False

        match = evaluate_case(
            make_case(expected=[make_expected(start=2, end=3)]),
            [predicted(start=3, end=4)],
        )
        assert match.true_positives == 1

    def test_category_mismatch_is_fp_and_fn(self):
        match = evaluate_case(
            make_case(),
            [predicted(category=Category.SECURITY)],
        )

        assert match.true_positives == 0
        assert match.false_positives == 1
        assert match.false_negatives == 1

    def test_extra_prediction_is_a_false_positive(self):
        match = evaluate_case(
            make_case(),
            [predicted(), predicted(rule_id="R2", start=9, end=9)],
        )

        assert match.true_positives == 1
        assert match.false_positives == 1

    def test_missing_prediction_is_a_false_negative(self):
        match = evaluate_case(make_case(), [])

        assert match.true_positives == 0
        assert match.false_negatives == 1

    def test_matching_is_one_to_one(self):
        match = evaluate_case(
            make_case(), [predicted(), predicted()]
        )

        assert match.true_positives == 1
        assert match.false_positives == 1


class TestMetrics:
    def test_precision_recall_and_fp_share(self):
        metrics = aggregate_metrics(
            [
                evaluate_case(make_case("c1"), [predicted()]),
                evaluate_case(
                    make_case("c2"), [predicted(rule_id="OTHER")]
                ),
                evaluate_case(make_case("c3"), [predicted()]),
                evaluate_case(
                    make_case("c4"),
                    [
                        predicted(),
                        predicted(rule_id="R2", start=9, end=9),
                    ],
                ),
            ]
        )

        assert metrics.true_positives == 4
        assert metrics.false_positives == 1
        assert metrics.false_negatives == 0
        assert metrics.precision == pytest.approx(4 / 5)
        assert metrics.recall == pytest.approx(1.0)
        assert metrics.false_positive_share == pytest.approx(1 / 5)
        assert metrics.rule_matches == 3
        assert metrics.rule_match_rate == pytest.approx(3 / 4)

    def test_missing_predictions_define_recall_only(self):
        metrics = aggregate_metrics(
            [evaluate_case(make_case(), [])]
        )

        assert metrics.precision is None
        assert metrics.false_positive_share is None
        assert metrics.rule_match_rate is None
        assert metrics.recall == 0.0

    def test_empty_case_set_yields_all_none(self):
        metrics = aggregate_metrics([])

        assert metrics.cases == 0
        assert metrics.precision is None
        assert metrics.recall is None
        assert metrics.false_positive_share is None
        assert metrics.rule_match_rate is None

    def test_evaluate_cases_uses_the_prediction_mapping(self):
        cases = [make_case("c1"), make_case("c2")]

        metrics = evaluate_cases(
            cases, {"c1": [predicted()]}
        )

        assert metrics.true_positives == 1
        assert metrics.false_negatives == 1
        assert metrics.cases == 2


class TestAdapters:
    def test_review_finding_adapter(self):
        finding = ReviewFinding(
            category=Category.BUG,
            severity=Severity.HIGH,
            confidence=0.5,
            rule_id="R1",
            title="title",
            file_path="sample.py",
            start_line=2,
            end_line=2,
            description="description",
            reason="reason",
            suggestion="suggestion",
            references=[],
        )

        converted = PredictedFinding.from_review_finding(finding)

        assert converted.rule_id == "R1"
        assert converted.start_line == 2

    def test_analysis_finding_adapter(self):
        finding = AnalysisFinding(
            sources=[FindingSource.AGENT],
            category=Category.BUG,
            severity=Severity.HIGH,
            rule_id="R1",
            message="message",
            file_path="sample.py",
            start_line=2,
            end_line=2,
        )

        converted = PredictedFinding.from_analysis_finding(finding)

        assert converted.category is Category.BUG
        assert converted.end_line == 2