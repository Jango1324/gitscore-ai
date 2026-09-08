"""Tests for gitscore.dataset.builder.build_dataset (Milestone 4).

All against a throwaway SQLite database (the `snapshot_db` fixture in
conftest.py) -- no live GitHub calls, no touch of data/gitscore.db.
"""
from datetime import datetime

import pandas as pd
import pytest

from gitscore.dataset import schema
from gitscore.dataset.builder import build_dataset
from gitscore.dataset.exceptions import DatasetValidationError


# --- empty database ----------------------------------------------------

def test_empty_database_yields_empty_but_valid_frame(snapshot_db):
    result = build_dataset(snapshot_db.session_factory)
    assert result.raw_snapshot_count == 0
    assert result.selected_row_count == 0
    assert result.unique_user_count == 0
    assert result.duplicate_user_count == 0
    assert list(result.frame.columns) == schema.DATASET_COLUMNS
    assert len(result.frame) == 0
    # must not raise
    schema.validate_frame(result.frame, allow_empty=True)


# --- latest-snapshot selection --------------------------------------

def test_one_row_per_user_selecting_the_latest_snapshot(snapshot_db):
    snapshot_db.add_snapshot("bob", collected_at=datetime(2026, 1, 1), readiness_score=10)
    snapshot_db.add_snapshot("bob", collected_at=datetime(2026, 3, 1), readiness_score=30)
    snapshot_db.add_snapshot("bob", collected_at=datetime(2026, 2, 1), readiness_score=20)

    result = build_dataset(snapshot_db.session_factory)

    assert result.raw_snapshot_count == 3
    assert result.selected_row_count == 1
    assert result.frame.loc[0, "readiness_score"] == 30  # the 2026-03-01 row


def test_latest_selection_breaks_collected_at_ties_by_snapshot_id(snapshot_db):
    same_time = datetime(2026, 1, 1, 12, 0, 0)
    first = snapshot_db.add_snapshot("bob", collected_at=same_time, readiness_score=11)
    second = snapshot_db.add_snapshot("bob", collected_at=same_time, readiness_score=22)
    assert second > first

    result = build_dataset(snapshot_db.session_factory)
    assert result.selected_row_count == 1
    assert result.frame.loc[0, "readiness_score"] == 22  # higher id wins the tie


# --- duplicate users --------------------------------------------------

def test_duplicate_users_are_detected_and_reported(snapshot_db):
    snapshot_db.add_snapshot("bob", collected_at=datetime(2026, 1, 1))
    snapshot_db.add_snapshot("bob", collected_at=datetime(2026, 2, 1))
    snapshot_db.add_snapshot("carol", collected_at=datetime(2026, 1, 1))
    snapshot_db.add_snapshot("carol", collected_at=datetime(2026, 2, 1))
    snapshot_db.add_snapshot("dave", collected_at=datetime(2026, 1, 1))

    result = build_dataset(snapshot_db.session_factory)

    assert result.unique_user_count == 3
    assert result.selected_row_count == 3
    assert result.duplicate_user_count == 2
    assert result.duplicate_usernames == ["bob", "carol"]


def test_no_duplicates_when_each_user_has_one_snapshot(snapshot_db):
    snapshot_db.add_snapshot("bob")
    snapshot_db.add_snapshot("carol")
    result = build_dataset(snapshot_db.session_factory)
    assert result.duplicate_user_count == 0
    assert result.duplicate_usernames == []


# --- deterministic output ------------------------------------------

def test_row_order_is_deterministic_ascending_username(snapshot_db):
    # Give each user a unique score so row order is observable after the
    # username column is dropped. Insert in non-sorted order.
    snapshot_db.add_snapshot("charlie", readiness_score=3)
    snapshot_db.add_snapshot("alice", readiness_score=1)
    snapshot_db.add_snapshot("bob", readiness_score=2)

    frame = build_dataset(snapshot_db.session_factory).frame
    # alice, bob, charlie -> 1, 2, 3
    assert frame["readiness_score"].tolist() == [1, 2, 3]


def test_repeated_builds_produce_identical_frames(snapshot_db):
    snapshot_db.add_snapshot("alice", collected_at=datetime(2026, 1, 1), readiness_score=15,
                             most_used_language="Python", total_repos=4)
    snapshot_db.add_snapshot("bob", collected_at=datetime(2026, 1, 2), readiness_score=61,
                             most_used_language="Rust", total_repos=9, has_python=True)

    first = build_dataset(snapshot_db.session_factory).frame
    second = build_dataset(snapshot_db.session_factory).frame

    pd.testing.assert_frame_equal(first, second)


def test_ordering_is_stable_regardless_of_insertion_order(snapshot_db):
    snapshot_db.add_snapshot("zoe", readiness_score=5, most_used_language="Go")
    snapshot_db.add_snapshot("amy", readiness_score=7, most_used_language="C")
    forward = build_dataset(snapshot_db.session_factory).frame.reset_index(drop=True)

    # amy < zoe -> amy's row first
    assert forward.loc[0, "most_used_language"] == "C"
    assert forward.loc[1, "most_used_language"] == "Go"


# --- correct feature inclusion -----------------------------------------

def test_frame_contains_exactly_the_declared_columns_in_order(snapshot_db):
    snapshot_db.add_snapshot("bob")
    frame = build_dataset(snapshot_db.session_factory).frame
    assert list(frame.columns) == schema.DATASET_COLUMNS


def test_feature_values_round_trip_from_the_database(snapshot_db):
    snapshot_db.add_snapshot(
        "bob",
        total_repos=12,
        original_repos=9,
        forked_repos=3,
        ml_repository_count=4,
        ml_keyword_total=6,
        readme_coverage_ratio=0.75,
        average_stars=3.5,
        has_pytorch=True,
        readiness_score=58,
        most_used_language="Python",
    )
    row = build_dataset(snapshot_db.session_factory).frame.iloc[0]
    assert row["total_repos"] == 12
    assert row["original_repos"] == 9
    assert row["forked_repos"] == 3
    assert row["ml_repository_count"] == 4
    assert row["ml_keyword_total"] == 6
    assert row["readme_coverage_ratio"] == 0.75
    assert row["average_stars"] == 3.5
    assert bool(row["has_pytorch"]) is True
    assert row["readiness_score"] == 58


# --- identifier / timestamp leakage prevention -----------------------

def test_no_identifier_columns_leak_into_the_frame(snapshot_db):
    snapshot_db.add_snapshot("bob")
    snapshot_db.add_snapshot("carol")
    frame = build_dataset(snapshot_db.session_factory).frame
    for leaky in schema.INTERNAL_ONLY_COLUMNS:
        assert leaky not in frame.columns
    for leaky in ("id", "user_id", "snapshot_id", "github_username",
                  "name", "followers", "public_repos"):
        assert leaky not in frame.columns


def test_no_timestamp_columns_leak_into_the_frame(snapshot_db):
    snapshot_db.add_snapshot("bob", collected_at=datetime(2026, 5, 4))
    frame = build_dataset(snapshot_db.session_factory).frame
    assert "collected_at" not in frame.columns
    # and no column holds datetime-like data
    for col in frame.columns:
        assert not pd.api.types.is_datetime64_any_dtype(frame[col])


def test_username_only_affects_ordering_never_becomes_a_column(snapshot_db):
    snapshot_db.add_snapshot("aaa", readiness_score=1)
    snapshot_db.add_snapshot("zzz", readiness_score=2)
    frame = build_dataset(snapshot_db.session_factory).frame
    assert "github_username" not in frame.columns
    assert frame["readiness_score"].tolist() == [1, 2]  # aaa before zzz


# --- categorical preservation --------------------------------------

def test_most_used_language_is_preserved_as_a_categorical_string(snapshot_db):
    snapshot_db.add_snapshot("bob", most_used_language="Python")
    snapshot_db.add_snapshot("carol", most_used_language="TypeScript")
    frame = build_dataset(snapshot_db.session_factory).frame
    assert isinstance(frame["most_used_language"].dtype, pd.CategoricalDtype)
    assert set(frame["most_used_language"].astype(str)) == {"Python", "TypeScript"}


def test_empty_string_language_sentinel_survives_as_empty_string(snapshot_db):
    snapshot_db.add_snapshot("bob", most_used_language="")
    frame = build_dataset(snapshot_db.session_factory).frame
    assert frame.loc[0, "most_used_language"] == ""
    assert frame["most_used_language"].isna().sum() == 0


# --- null validation / malformed data --------------------------------

def test_build_validates_its_output_and_raises_on_a_malformed_frame(snapshot_db, monkeypatch):
    """The builder runs schema.validate_frame on its result; a null that
    slipped through coercion must surface as DatasetValidationError, not a
    silently-broken dataset.
    """
    snapshot_db.add_snapshot("bob")
    import gitscore.dataset.builder as builder_mod

    real_coerce = builder_mod._coerce_dtypes

    def coerce_then_corrupt(df):
        out = real_coerce(df)
        out.loc[out.index[0], "readme_coverage_ratio"] = float("nan")
        return out

    monkeypatch.setattr(builder_mod, "_coerce_dtypes", coerce_then_corrupt)

    with pytest.raises(DatasetValidationError):
        build_dataset(snapshot_db.session_factory)


def test_build_result_exposes_version_stamps(snapshot_db):
    snapshot_db.add_snapshot("bob")
    result = build_dataset(snapshot_db.session_factory)
    assert result.dataset_version == schema.DATASET_VERSION
    assert result.feature_schema_version == schema.FEATURE_SCHEMA_VERSION
    assert result.scoring_rubric_version == schema.SCORING_RUBRIC_VERSION
