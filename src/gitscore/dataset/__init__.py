"""GitScore Dataset V1 layer.

Turns persisted ``ProfileFeature`` snapshots (SQLite) into a clean,
reproducible, one-row-per-user Pandas dataset for later ML work.

Public surface:

- ``gitscore.dataset.schema``  -- the dataset contract (column lists,
  version stamps, ``validate_frame``).
- ``gitscore.dataset.builder.build_dataset`` -- snapshots -> clean frame.
- ``gitscore.dataset.report.dataset_quality_report`` -- data-quality summary.
- ``gitscore.dataset.export.export_dataset`` -- deterministic CSV (+ meta).
- ``gitscore.dataset.collection_input`` -- username-file parsing for
  ``scripts/collect_dataset.py``.

Nothing here trains a model or changes the scoring rubric.
"""
