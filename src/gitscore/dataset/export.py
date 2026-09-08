"""Deterministic export of a built Dataset V1 frame.

Writes:

- ``<name>.csv``       -- the dataset. Deterministic: fixed column order
  (``schema.DATASET_COLUMNS``), fixed row order (ascending
  ``github_username``, applied in the builder), ``\\n`` line endings, no
  index. Two exports of the same snapshot database produce byte-identical
  CSVs.
- ``<name>.meta.json`` -- informational sidecar (versions, counts, column
  lists, build timestamp). The timestamp makes the *meta* file
  non-deterministic; the CSV is the reproducible artifact. Pass
  ``write_meta=False`` to skip it.

Both land under ``data/processed/`` which is gitignored -- the CSV is a
derived artifact, the SQLite database remains the source of truth.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from gitscore.dataset import schema
from gitscore.dataset.builder import DatasetBuildResult
from gitscore.dataset.schema import validate_frame

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXPORT_DIR = _PROJECT_ROOT / "data" / "processed"
DEFAULT_DATASET_PATH = DEFAULT_EXPORT_DIR / f"gitscore_dataset_{schema.DATASET_VERSION}.csv"


def _frame_of(result_or_frame) -> pd.DataFrame:
    if isinstance(result_or_frame, DatasetBuildResult):
        return result_or_frame.frame
    return result_or_frame


def _build_meta(result_or_frame, csv_path: Path) -> dict:
    frame = _frame_of(result_or_frame)
    meta: dict = {
        **schema.versions(),
        "row_grain": schema.ROW_GRAIN,
        "source": "profile_features table, latest valid snapshot per user",
        "csv_filename": csv_path.name,
        "n_rows": int(len(frame)),
        "n_feature_columns": len(schema.FEATURE_COLUMNS),
        "feature_columns": list(schema.FEATURE_COLUMNS),
        "categorical_columns": list(schema.CATEGORICAL_FEATURE_COLUMNS),
        "boolean_columns": list(schema.BOOLEAN_FEATURE_COLUMNS),
        "target_column": schema.TARGET_COLUMN,
        "excluded_columns": dict(schema.EXCLUDED_COLUMNS),
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if isinstance(result_or_frame, DatasetBuildResult):
        meta.update(
            raw_snapshot_count=result_or_frame.raw_snapshot_count,
            selected_row_count=result_or_frame.selected_row_count,
            unique_user_count=result_or_frame.unique_user_count,
            duplicate_user_count=result_or_frame.duplicate_user_count,
        )
    return meta


def export_dataset(result_or_frame, path=None, *, write_meta: bool = True) -> Path:
    """Write the dataset CSV (and, by default, its ``.meta.json`` sidecar).

    ``result_or_frame`` is a ``DatasetBuildResult`` or a bare frame.
    ``path`` defaults to
    ``data/processed/gitscore_dataset_<DATASET_VERSION>.csv``. Returns the
    CSV path.
    """
    frame = _frame_of(result_or_frame)
    validate_frame(frame, allow_empty=True)

    csv_path = Path(path) if path is not None else DEFAULT_DATASET_PATH
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    frame.to_csv(csv_path, index=False, lineterminator="\n")

    if write_meta:
        meta_path = csv_path.with_suffix(".meta.json")
        meta_path.write_text(
            json.dumps(_build_meta(result_or_frame, csv_path), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return csv_path
