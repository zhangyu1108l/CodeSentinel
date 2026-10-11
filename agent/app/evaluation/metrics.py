"""Evaluation metric computation (Phase 8.8).

Matching definition (fixed, testable, no thresholds):

- A predicted finding matches one expected finding when the category is
  equal, the file path is equal and the two inclusive line ranges
  intersect. Rule ids are NOT part of the match; a matching prediction
  whose rule id equals the expected rule id (case-insensitive) is counted
  separately as a rule match.
- Matching is one-to-one and deterministic: expectations are matched in
  order, each prediction is consumed at most once.
- Unmatched predictions are false positives, unmatched expectations are
  false negatives.

Metrics over a set of cases:

- precision       = TP / (TP + FP), None when nothing was predicted
- recall          = TP / (TP + FN), None when nothing was expected
- false_positive_share = FP / (TP + FP), the share of reported findings
  that are false positives (None when nothing was predicted)
- rule_match_rate = rule matches / TP, None when TP is 0

This module encodes no quality threshold and makes no claim about which
reviewer implementation is better; it only computes the numbers.
"""

from dataclasses import dataclass

from pydantic import BaseModel

from app.evaluation.models import EvalCase
from app.schemas.report import AnalysisFinding
from app.schemas.review import Category, ReviewFinding, Severity


@dataclass(frozen=True)
class PredictedFinding:
    """Minimal finding shape consumed by the metrics."""

    category: Category
    severity: Severity
    rule_id: str
    file_path: str
    start_line: int
    end_line: int

    @classmethod
    def from_review_finding(
        cls, finding: ReviewFinding
    ) -> "PredictedFinding":
        return cls(
            category=finding.category,
            severity=finding.severity,
            rule_id=finding.rule_id,
            file_path=finding.file_path,
            start_line=finding.start_line,
            end_line=finding.end_line,
        )

    @classmethod
    def from_analysis_finding(
        cls, finding: AnalysisFinding
    ) -> "PredictedFinding":
        return cls(
            category=finding.category,
            severity=finding.severity,
            rule_id=finding.rule_id,
            file_path=finding.file_path,
            start_line=finding.start_line,
            end_line=finding.end_line,
        )


class CaseMatch(BaseModel):
    """Per case matching outcome."""

    case_id: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    rule_matches: int = 0

    @property
    def rule_match_applicable(self) -> int:
        return self.true_positives


class EvalMetrics(BaseModel):
    """Aggregated metrics over a case set; None means undefined."""

    cases: int
    expected_total: int
    predicted_total: int
    true_positives: int
    false_positives: int
    false_negatives: int
    rule_matches: int
    precision: float | None = None
    recall: float | None = None
    false_positive_share: float | None = None
    rule_match_rate: float | None = None


def ranges_intersect(
    start_a: int, end_a: int, start_b: int, end_b: int
) -> bool:
    """Inclusive line range intersection."""
    return start_a <= end_b and start_b <= end_a


def evaluate_case(
    case: EvalCase, predicted: list[PredictedFinding]
) -> CaseMatch:
    """Match one case against the predicted findings, one-to-one."""
    used = [False] * len(predicted)
    true_positives = 0
    rule_matches = 0
    for expected in case.expected_findings:
        match_index = None
        for index, candidate in enumerate(predicted):
            if used[index]:
                continue
            if candidate.category is not expected.category:
                continue
            if candidate.file_path != expected.file_path:
                continue
            if not ranges_intersect(
                candidate.start_line,
                candidate.end_line,
                expected.start_line,
                expected.end_line,
            ):
                continue
            match_index = index
            break
        if match_index is None:
            continue
        used[match_index] = True
        true_positives += 1
        if (
            predicted[match_index].rule_id.strip().lower()
            == expected.rule_id.strip().lower()
        ):
            rule_matches += 1

    false_negatives = len(case.expected_findings) - true_positives
    false_positives = sum(1 for flagged in used if not flagged)
    return CaseMatch(
        case_id=case.case_id,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        rule_matches=rule_matches,
    )


def aggregate_metrics(matches: list[CaseMatch]) -> EvalMetrics:
    """Aggregate per case matches into global metrics."""
    true_positives = sum(match.true_positives for match in matches)
    false_positives = sum(match.false_positives for match in matches)
    false_negatives = sum(match.false_negatives for match in matches)
    rule_matches = sum(match.rule_matches for match in matches)
    expected_total = true_positives + false_negatives
    predicted_total = true_positives + false_positives

    precision = (
        true_positives / predicted_total if predicted_total else None
    )
    recall = true_positives / expected_total if expected_total else None
    false_positive_share = (
        false_positives / predicted_total if predicted_total else None
    )
    rule_match_rate = (
        rule_matches / true_positives if true_positives else None
    )
    return EvalMetrics(
        cases=len(matches),
        expected_total=expected_total,
        predicted_total=predicted_total,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        rule_matches=rule_matches,
        precision=precision,
        recall=recall,
        false_positive_share=false_positive_share,
        rule_match_rate=rule_match_rate,
    )


def evaluate_cases(
    cases: list[EvalCase],
    predictions: dict[str, list[PredictedFinding]],
) -> EvalMetrics:
    """Evaluate a case set from a case_id -> predictions mapping."""
    matches = [
        evaluate_case(case, list(predictions.get(case.case_id, [])))
        for case in cases
    ]
    return aggregate_metrics(matches)