"""Evaluation foundation for review quality (Phase 8.8).

Not part of the production pipeline: these modules define the minimal
case format, the loader and the metric computation used to measure
review quality (Precision / Recall / false positive share / rule match)
against curated cases. No LLM is called here and no quality threshold is
encoded anywhere in this package.
"""