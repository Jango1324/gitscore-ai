"""Dataset V1 contract.

Single source of truth for the shape of the GitScore training dataset:
which persisted columns become features, which are excluded as
leakage/identifiers, what the target is, and the three version stamps.

``builder.py``, ``export.py``, ``report.py`` and the tests all import
their column lists from here -- nothing re-derives them, and nothing does
``SELECT *`` + arbitrary column dropping.
"""
from __future__ import annotations

import pandas as pd

from gitscore.dataset.exceptions import DatasetSchemaError, DatasetValidationError

# ---------------------------------------------------------------------------
# Versioning (lightweight: plain constants, captured into the export
# metadata sidecar -- see export.py. Not stored in the DB; the DB schema is
# unchanged this milestone.)
# ---------------------------------------------------------------------------

#: Bump when the *meaning of a row* changes: different source table, a
#: different row-selection policy, or a redefined target.
DATASET_VERSION = "v1"

#: Bump on ANY change to ``FEATURE_COLUMNS`` (add / remove / rename /
#: reorder / retype). Two datasets with different values here are not
#: column-compatible and must not be concatenated.
FEATURE_SCHEMA_VERSION = 1

#: Mirrors the rule set in ``src/gitscore/scoring/readiness.py``. Bump this
#: ONLY when that file's weights / thresholds / ladders change. ``readiness_score``
#: is the target and is NOT comparable across rubric versions -- rows built
#: under different values here must not be mixed. Changing the rubric is out
#: of scope for this milestone; this constant just records "which rubric".
SCORING_RUBRIC_VERSION = 1

#: Human-readable statement of the row grain, echoed into metadata/reports.
ROW_GRAIN = "one row per GitHub user (latest valid ProfileFeature snapshot)"


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------

#: Categorical feature(s). Kept as strings; the extractor's "no data"
#: sentinel is the empty string ``""`` (never null) -- see
#: features/languages.py and docs/ARCHITECTURE.md 5a.
CATEGORICAL_FEATURE_COLUMNS = ["most_used_language"]

#: Boolean features (0/1). Reported separately from the continuous numerics.
BOOLEAN_FEATURE_COLUMNS = [
    "has_python",
    "has_typescript",
    "has_pytorch",
    "has_huggingface",
    "has_pandas",
    "has_catboost",
]

#: Continuous / count features. Order is part of FEATURE_SCHEMA_VERSION.
NUMERIC_FEATURE_COLUMNS = [
    "total_repos",
    "original_repos",
    "forked_repos",
    "unique_language_count",
    "ml_repository_count",
    "readme_coverage_ratio",
    "python_repository_count",
    "typescript_repository_count",
    "total_stars",
    "average_stars",
    "total_forks",
    "average_forks",
    "repositories_with_description",
    "description_coverage_ratio",
    "ml_keyword_total",
    "repositories_with_readme",
    "average_readme_length",
    "repositories_with_installation",
    "repositories_with_usage",
    "repositories_with_demo",
    "repositories_with_badges",
    "repositories_with_license",
    "repositories_with_contributing",
]

#: The full, ORDERED feature list exactly as written to the CSV. The
#: categorical column sits in a fixed, documented position (index 6).
FEATURE_COLUMNS = [
    "total_repos",
    "original_repos",
    "forked_repos",
    "unique_language_count",
    "ml_repository_count",
    "readme_coverage_ratio",
    "most_used_language",
    "python_repository_count",
    "typescript_repository_count",
    "has_python",
    "has_typescript",
    "total_stars",
    "average_stars",
    "total_forks",
    "average_forks",
    "repositories_with_description",
    "description_coverage_ratio",
    "has_pytorch",
    "has_huggingface",
    "has_pandas",
    "has_catboost",
    "ml_keyword_total",
    "repositories_with_readme",
    "average_readme_length",
    "repositories_with_installation",
    "repositories_with_usage",
    "repositories_with_demo",
    "repositories_with_badges",
    "repositories_with_license",
    "repositories_with_contributing",
]

#: The supervised target. A deterministic rule-based label
#: (``scoring/readiness.py``); see docs/ML_NOTES.md 3 for why a model
#: trained on it mostly re-derives the rubric.
TARGET_COLUMN = "readiness_score"

#: Feature columns + target, in CSV order.
DATASET_COLUMNS = FEATURE_COLUMNS + [TARGET_COLUMN]

#: Columns that exist in the DB (``profile_features`` / ``users``) and are
#: DELIBERATELY excluded, each with the reason. Documented so a reader
#: knows the omission is a decision, not an oversight.
EXCLUDED_COLUMNS = {
    "profile_features.id": (
        "snapshot primary key -- pure row identifier, no signal, would leak "
        "row identity across a split"
    ),
    "profile_features.user_id": (
        "user identifier / FK -- leaks user identity; splits must be BY this "
        "column, never trained ON it"
    ),
    "profile_features.collected_at": (
        "snapshot timestamp -- collection metadata; can leak temporal ordering "
        "of collection into the model"
    ),
    "users.id": "user primary key -- identifier",
    "users.github_username": "user handle -- free-text identity / identifier",
    "users.name": "display name -- identity / PII-ish, no generalizable signal",
    "users.followers": (
        "not an input to the V1 scoring rubric; revisit only alongside an "
        "independent (non-rubric) target"
    ),
    "users.public_repos": "not a rubric input; near-duplicate of total_repos",
    "users.collected_at": "collection metadata timestamp",
}

#: Pulled from the ORM for row-selection / diagnostics inside the builder,
#: then dropped before the frame is returned. Named here so tests can
#: assert none of them survive into the dataset.
INTERNAL_ONLY_COLUMNS = [
    "snapshot_id",
    "user_id",
    "github_username",
    "collected_at",
]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def expected_columns() -> list[str]:
    """The exact ordered column list a Dataset V1 frame must have."""
    return list(DATASET_COLUMNS)


def versions() -> dict[str, object]:
    """The three version stamps, as a plain dict (for metadata/reports)."""
    return {
        "dataset_version": DATASET_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "scoring_rubric_version": SCORING_RUBRIC_VERSION,
    }


def validate_frame(df: pd.DataFrame, *, allow_empty: bool = True) -> None:
    """Raise if ``df`` is not a well-formed Dataset V1 frame.

    Checks, in order:

    1. exact column set **and order** (``DatasetSchemaError``)
    2. no forbidden identifier / timestamp columns (``DatasetSchemaError``)
    3. row count vs ``allow_empty`` (``DatasetValidationError``)
    4. no nulls in any dataset column (``DatasetValidationError``)
    5. numeric columns hold numeric values (``DatasetValidationError``)
    6. boolean columns hold only {True, False, 0, 1} (``DatasetValidationError``)
    7. categorical column holds only strings (``DatasetValidationError``)

    An empty frame with the right columns passes when ``allow_empty`` is
    True (steps 4-7 are skipped -- there is nothing to check).
    """
    actual = list(df.columns)
    if actual != DATASET_COLUMNS:
        missing = [c for c in DATASET_COLUMNS if c not in actual]
        extra = [c for c in actual if c not in DATASET_COLUMNS]
        if missing or extra:
            raise DatasetSchemaError(
                "dataset columns do not match the V1 schema "
                f"(feature_schema_version={FEATURE_SCHEMA_VERSION}): "
                f"missing={missing} extra={extra}"
            )
        raise DatasetSchemaError(
            "dataset columns match the V1 set but are in the wrong order; "
            f"expected {DATASET_COLUMNS!r}, got {actual!r}"
        )

    forbidden = [c for c in INTERNAL_ONLY_COLUMNS if c in actual]
    if forbidden:
        raise DatasetSchemaError(
            f"identifier/timestamp columns must never be in the dataset: {forbidden}"
        )

    if len(df) == 0:
        if allow_empty:
            return
        raise DatasetValidationError("dataset is empty but allow_empty=False")

    null_counts = {
        c: int(df[c].isna().sum()) for c in DATASET_COLUMNS if df[c].isna().any()
    }
    if null_counts:
        raise DatasetValidationError(
            f"nulls found in required dataset columns: {null_counts}"
        )

    non_numeric = []
    for col in NUMERIC_FEATURE_COLUMNS + [TARGET_COLUMN]:
        if pd.to_numeric(df[col], errors="coerce").isna().any():
            non_numeric.append(col)
    if non_numeric:
        raise DatasetValidationError(
            f"numeric columns contain non-numeric values: {non_numeric}"
        )

    bad_bool = [
        c
        for c in BOOLEAN_FEATURE_COLUMNS
        if not set(df[c].dropna().unique()).issubset({True, False, 0, 1})
    ]
    if bad_bool:
        raise DatasetValidationError(
            f"boolean columns contain non-boolean values: {bad_bool}"
        )

    for col in CATEGORICAL_FEATURE_COLUMNS:
        if any(not isinstance(v, str) for v in df[col].tolist()):
            raise DatasetValidationError(
                f"categorical column {col!r} must contain only strings "
                '(use "" as the "unknown" sentinel, never null)'
            )
