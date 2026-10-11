# Evaluation cases (Phase 8.8)

Curated, minimal review-quality cases shared by the Java and Python
review pipelines. They exist to measure review quality (Precision /
Recall / false positive share / rule match) before any production switch;
**no quality threshold is defined anywhere in the repository** and no
case may be interpreted as a benchmark claim.

## Layout

```
test-cases/
  <language>/<category>/<case>.json
```

- `language`: `java` or `python`
- `category`: `bug` / `security` / `performance` / `quality` directories
  (case field values are `BUG` / `SECURITY` / `PERFORMANCE` / `QUALITY`)

## Case format

```json
{
  "case_id": "python-bug-001",
  "language": "python",
  "category": "BUG",
  "source": {
    "file_path": "sample.py",
    "code": "<the full code sample>"
  },
  "expected_findings": [
    {
      "rule_id": "CS-PY-BUG-001",
      "category": "BUG",
      "severity": "HIGH",
      "file_path": "sample.py",
      "start_line": 2,
      "end_line": 2,
      "description": "why this is a real issue"
    }
  ],
  "notes": "optional"
}
```

Schema rules (enforced by `app/evaluation/models.py`):

- `case_id` unique across the tree, matching the file name.
- `source.file_path` and every expected `file_path` are repository
  relative and must be the same file.
- every expected finding must use the case category;
  `end_line >= start_line >= 1`;
  `expected_findings` is not empty.

## Matching and metrics

Metric computation lives in `app/evaluation/metrics.py`; no LLM is called
and no tool runs.

- A predicted finding matches one expected finding when **category is
  equal, file path is equal and the inclusive line ranges intersect**.
  Rule ids do not take part in the match.
- Matching is one-to-one and deterministic.
- `TP` matched predictions, `FP` unmatched predictions, `FN` unmatched
  expectations.
- `precision = TP / (TP + FP)` (None when nothing was predicted)
- `recall = TP / (TP + FN)` (None when nothing was expected)
- `false_positive_share = FP / (TP + FP)` (share of reported findings
  that are false positives; None when nothing was predicted)
- `rule_match_rate = rule matches / TP` (rule matches are counted
  separately; None when TP is 0)

## Usage (development only, no online calls)

```python
from app.evaluation.loader import load_cases
from app.evaluation.metrics import evaluate_cases, PredictedFinding

cases = load_cases()
metrics = evaluate_cases(cases, predictions)  # predictions produced offline
```

Replaying real reviewer outputs against these cases (recorded fixtures or
an explicit live run) is the next evaluation step; this phase only
provides the format, loader and metric calculation.