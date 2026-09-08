"""Tests for gitscore.dataset.schema (Milestone 4).

The schema module is the dataset contract: column lists, version stamps,
and validate_frame(). These tests pin the contract and every failure mode
of the validator.
"""
import pandas as pd
import pytest

from gitscore.dataset import schema
from gitscore.dataset.exceptions import DatasetSchemaError, DatasetValidationError


def _valid_row():
    """One fully-populated, correctly-typed dataset row as a dict."""
    row = {c: 0 for c in schema.NUMERIC_FEATURE_COLUMNS}
    row.update({c: False for c in schema.BOOLEAN_FEATURE_COLUMNS})
    row["most_used_language"] = "Python"
    row[schema.TARGET_COLUMN] = 42
    return row


def _valid_frame(n=2):
    frame = pd.DataFrame([_valid_row() for _ in range(n)], columns=schema.DATASET_COLUMNS)
    for col in schema.BOOLEAN_FEATURE_COLUMNS:
        frame[col] = frame[col].astype("bool")
    frame["most_used_language"] = pd.Categorical(frame["most_used_language"].astype(str))
    return frame


# --- contract shape -------------------------------------------------------

def test_feature_columns_are_features_plus_target():
    assert schema.DATASET_COLUMNS == schema.FEATURE_COLUMNS + [schema.TARGET_COLUMN]
    assert schema.TARGET_COLUMN not in schema.FEATURE_COLUMNS


def test_column_partition_is_complete_and_disjoint():
    numeric = set(schema.NUMERIC_FEATURE_COLUMNS)
    boolean = set(schema.BOOLEAN_FEATURE_COLUMNS)
    categorical = set(schema.CATEGORICAL_FEATURE_COLUMNS)
    assert numeric | boolean | categorical == set(schema.FEATURE_COLUMNS)
    assert numeric.isdisjoint(boolean)
    assert numeric.isdisjoint(categorical)
    assert boolean.isdisjoint(categorical)


def test_no_duplicate_feature_columns():
    assert len(schema.FEATURE_COLUMNS) == len(set(schema.FEATURE_COLUMNS))


def test_identifier_and_timestamp_columns_are_not_features():
    for leaky in ("id", "user_id", "snapshot_id", "github_username", "collected_at",
                  "name", "followers", "public_repos"):
        assert leaky not in schema.DATASET_COLUMNS


def test_excluded_columns_document_ids_timestamps_and_metadata():
    keys = set(schema.EXCLUDED_COLUMNS)
    assert {"profile_features.id", "profile_features.user_id",
            "profile_features.collected_at", "users.github_username",
            "users.collected_at"} <= keys
    assert all(isinstance(reason, str) and reason for reason in schema.EXCLUDED_COLUMNS.values())


def test_versions_helper_matches_constants():
    assert schema.versions() == {
        "dataset_version": schema.DATASET_VERSION,
        "feature_schema_version": schema.FEATURE_SCHEMA_VERSION,
        "scoring_rubric_version": schema.SCORING_RUBRIC_VERSION,
    }


# --- validate_frame: happy paths ---------------------------------------

def test_validate_frame_accepts_a_valid_frame():
    schema.validate_frame(_valid_frame())


def test_validate_frame_accepts_empty_frame_with_right_columns():
    empty = _valid_frame(0)
    schema.validate_frame(empty, allow_empty=True)


def test_validate_frame_rejects_empty_frame_when_not_allowed():
    with pytest.raises(DatasetValidationError):
        schema.validate_frame(_valid_frame(0), allow_empty=False)


# --- validate_frame: schema errors ------------------------------------

def test_validate_frame_rejects_missing_column():
    frame = _valid_frame().drop(columns=["total_repos"])
    with pytest.raises(DatasetSchemaError):
        schema.validate_frame(frame)


def test_validate_frame_rejects_extra_column():
    frame = _valid_frame()
    frame["surprise"] = 1
    with pytest.raises(DatasetSchemaError):
        schema.validate_frame(frame)


def test_validate_frame_rejects_wrong_column_order():
    frame = _valid_frame()
    reordered = frame[list(reversed(schema.DATASET_COLUMNS))]
    with pytest.raises(DatasetSchemaError):
        schema.validate_frame(reordered)


def test_validate_frame_rejects_identifier_column_even_if_everything_else_ok():
    frame = _valid_frame()
    frame.insert(0, "user_id", [1, 2])
    with pytest.raises(DatasetSchemaError):
        schema.validate_frame(frame)


# --- validate_frame: value errors ------------------------------------

def test_validate_frame_rejects_nulls_in_required_columns():
    frame = _valid_frame()
    frame.loc[0, "total_repos"] = None
    with pytest.raises(DatasetValidationError):
        schema.validate_frame(frame)


def test_validate_frame_rejects_non_numeric_in_numeric_column():
    frame = _valid_frame()
    frame["total_repos"] = frame["total_repos"].astype("object")
    frame.loc[0, "total_repos"] = "lots"
    with pytest.raises(DatasetValidationError):
        schema.validate_frame(frame)


def test_validate_frame_rejects_null_categorical():
    frame = _valid_frame()
    frame["most_used_language"] = frame["most_used_language"].astype("object")
    frame.loc[0, "most_used_language"] = None
    with pytest.raises(DatasetValidationError):
        schema.validate_frame(frame)


def test_validate_frame_allows_empty_string_categorical_sentinel():
    frame = _valid_frame()
    frame["most_used_language"] = frame["most_used_language"].astype("object")
    frame.loc[0, "most_used_language"] = ""
    frame["most_used_language"] = pd.Categorical(frame["most_used_language"].astype(str))
    schema.validate_frame(frame)
