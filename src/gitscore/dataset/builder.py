"""Turn persisted ``ProfileFeature`` snapshots into a clean Dataset V1 frame.

One row per GitHub user = that user's **latest valid snapshot**
(``max(collected_at)``, snapshot ``id`` as the deterministic tie-break).

Explicit column selection throughout -- the ORM query names every column
it wants; there is no ``SELECT *`` and no post-hoc "drop whatever looks
like an id". Identifier / timestamp columns are pulled only for row
selection and diagnostics and are removed before the frame is returned
(``schema.INTERNAL_ONLY_COLUMNS``).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import select

from gitscore.db.database import SessionLocal
from gitscore.db.models import ProfileFeature, User
from gitscore.dataset import schema
from gitscore.dataset.schema import DATASET_COLUMNS, FEATURE_COLUMNS, TARGET_COLUMN, validate_frame

# Feature + target columns to read straight off ProfileFeature. Explicit.
_PROFILE_VALUE_COLUMNS = FEATURE_COLUMNS + [TARGET_COLUMN]

# Internal-only columns, in the order the raw frame carries them.
_INTERNAL_COLUMNS = ["snapshot_id", "user_id", "github_username", "collected_at"]


@dataclass
class DatasetBuildResult:
    """The built dataset plus the counts a quality report needs."""

    frame: pd.DataFrame
    raw_snapshot_count: int
    selected_row_count: int
    unique_user_count: int
    duplicate_user_count: int
    duplicate_usernames: list[str] = field(default_factory=list)

    @property
    def dataset_version(self) -> str:
        return schema.DATASET_VERSION

    @property
    def feature_schema_version(self) -> int:
        return schema.FEATURE_SCHEMA_VERSION

    @property
    def scoring_rubric_version(self) -> int:
        return schema.SCORING_RUBRIC_VERSION


def _coerce_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column dtypes to the V1 contract.

    Numerics -> float/int via ``to_numeric`` (raises on genuinely
    non-numeric data), booleans -> ``bool``, categoricals -> pandas
    ``category`` over strings with ``""`` for any missing value. Safe on an
    empty frame. Returns columns in ``DATASET_COLUMNS`` order.
    """
    out = df.copy()
    for col in schema.NUMERIC_FEATURE_COLUMNS + [schema.TARGET_COLUMN]:
        out[col] = pd.to_numeric(out[col], errors="raise")
    for col in schema.BOOLEAN_FEATURE_COLUMNS:
        out[col] = out[col].astype("bool")
    for col in schema.CATEGORICAL_FEATURE_COLUMNS:
        as_str = out[col].astype("object")
        as_str = as_str.where(as_str.notna(), "")
        out[col] = pd.Categorical(as_str.astype(str))
    return out[list(DATASET_COLUMNS)]


def _empty_frame() -> pd.DataFrame:
    return _coerce_dtypes(
        pd.DataFrame({c: pd.Series(dtype="object") for c in DATASET_COLUMNS})
    )


def build_dataset(session_factory=SessionLocal) -> DatasetBuildResult:
    """Build the Dataset V1 frame from the snapshot database.

    ``session_factory`` is any zero-arg callable returning a SQLAlchemy
    ``Session`` (defaults to the app's ``SessionLocal``). Tests pass a
    factory bound to a throwaway SQLite database -- this function never
    hard-codes the real engine.

    Raises ``DatasetSchemaError`` / ``DatasetValidationError`` (from
    ``schema.validate_frame``) if the assembled frame is malformed. An
    empty database yields an empty-but-valid frame, not an error.
    """
    stmt = (
        select(
            ProfileFeature.id.label("snapshot_id"),
            ProfileFeature.user_id.label("user_id"),
            User.github_username.label("github_username"),
            ProfileFeature.collected_at.label("collected_at"),
            *[getattr(ProfileFeature, name) for name in _PROFILE_VALUE_COLUMNS],
        )
        .join(User, ProfileFeature.user_id == User.id)
    )

    session = session_factory()
    try:
        rows = session.execute(stmt).all()
    finally:
        session.close()

    raw = pd.DataFrame(
        [tuple(row) for row in rows],
        columns=_INTERNAL_COLUMNS + _PROFILE_VALUE_COLUMNS,
    )
    raw_snapshot_count = len(raw)

    if raw_snapshot_count == 0:
        frame = _empty_frame()
        validate_frame(frame, allow_empty=True)
        return DatasetBuildResult(
            frame=frame,
            raw_snapshot_count=0,
            selected_row_count=0,
            unique_user_count=0,
            duplicate_user_count=0,
            duplicate_usernames=[],
        )

    # --- duplicate detection (before any selection) ---
    counts_per_user = raw.groupby("user_id")["snapshot_id"].transform("size")
    dup_rows = raw.loc[counts_per_user > 1]
    duplicate_user_ids = sorted(dup_rows["user_id"].unique().tolist())
    duplicate_usernames = sorted(dup_rows["github_username"].unique().tolist())

    # --- latest snapshot per user (deterministic) ---
    ordered = raw.sort_values(["collected_at", "snapshot_id"], kind="stable")
    selected = ordered.groupby("user_id", as_index=False, sort=False).tail(1)

    # --- deterministic dataset row order: ascending github_username ---
    selected = selected.sort_values("github_username", kind="stable").reset_index(drop=True)

    frame = _coerce_dtypes(selected[list(DATASET_COLUMNS)])
    validate_frame(frame, allow_empty=True)

    return DatasetBuildResult(
        frame=frame,
        raw_snapshot_count=raw_snapshot_count,
        selected_row_count=len(frame),
        unique_user_count=int(raw["user_id"].nunique()),
        duplicate_user_count=len(duplicate_user_ids),
        duplicate_usernames=duplicate_usernames,
    )
