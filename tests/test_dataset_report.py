"""Tests for gitscore.dataset.report (Milestone 4)."""
from datetime import datetime

from gitscore.dataset import schema
from gitscore.dataset.builder import build_dataset
from gitscore.dataset.report import dataset_quality_report, format_report


def test_report_on_empty_dataset_is_well_formed(snapshot_db):
    result = build_dataset(snapshot_db.session_factory)
    report = dataset_quality_report(result)
    assert report["unique_users"] == 0
    assert report["rows_before_latest_selection"] == 0
    assert report["rows_after_latest_selection"] == 0
    assert report["row_count"] == 0
    assert report["total_missing_values"] == 0
    assert report["target"] == {}
    assert report["most_used_language_distribution"] == {}
    # formatter must not blow up on the empty case
    assert "empty dataset" in format_report(report)


def test_report_counts_rows_before_and_after_latest_selection(snapshot_db):
    snapshot_db.add_snapshot("bob", collected_at=datetime(2026, 1, 1))
    snapshot_db.add_snapshot("bob", collected_at=datetime(2026, 2, 1))
    snapshot_db.add_snapshot("carol", collected_at=datetime(2026, 1, 1))

    report = dataset_quality_report(build_dataset(snapshot_db.session_factory))
    assert report["rows_before_latest_selection"] == 3
    assert report["rows_after_latest_selection"] == 2
    assert report["unique_users"] == 2
    assert report["duplicate_user_count"] == 1
    assert report["duplicate_usernames"] == ["bob"]


def test_report_target_distribution(snapshot_db):
    for i, name in enumerate(("a", "b", "c", "d")):
        snapshot_db.add_snapshot(name, readiness_score=10 * (i + 1))
    report = dataset_quality_report(build_dataset(snapshot_db.session_factory))
    tgt = report["target"]
    assert tgt["min"] == 10.0
    assert tgt["max"] == 40.0
    assert tgt["mean"] == 25.0
    assert sum(tgt["histogram"].values()) == 4


def test_report_language_distribution_includes_unknown_sentinel(snapshot_db):
    snapshot_db.add_snapshot("a", most_used_language="Python")
    snapshot_db.add_snapshot("b", most_used_language="Python")
    snapshot_db.add_snapshot("c", most_used_language="")
    report = dataset_quality_report(build_dataset(snapshot_db.session_factory))
    dist = report["most_used_language_distribution"]
    assert dist["Python"] == 2
    assert dist[""] == 1


def test_report_flags_constant_and_near_constant_features(snapshot_db):
    # 20 users: total_repos constant at 1; total_stars is 0 for 19, 500 for 1
    # (dominant share 0.95 -> near-constant, not constant).
    for i in range(20):
        stars = 500 if i == 0 else 0
        snapshot_db.add_snapshot(f"user{i:02d}", total_repos=1, total_stars=stars,
                                 readiness_score=i)
    report = dataset_quality_report(build_dataset(snapshot_db.session_factory))

    assert "total_repos" in report["constant_features"]
    near = {item["feature"] for item in report["near_constant_features"]}
    assert "total_stars" in near
    assert "total_repos" not in near  # constant, reported separately


def test_report_dtypes_cover_every_dataset_column(snapshot_db):
    snapshot_db.add_snapshot("bob")
    report = dataset_quality_report(build_dataset(snapshot_db.session_factory))
    assert set(report["feature_dtypes"]) == set(schema.DATASET_COLUMNS)
    assert "category" in report["feature_dtypes"]["most_used_language"]


def test_report_has_no_missing_values_for_clean_data(snapshot_db):
    snapshot_db.add_snapshot("bob", most_used_language="Python")
    snapshot_db.add_snapshot("carol", most_used_language="")
    report = dataset_quality_report(build_dataset(snapshot_db.session_factory))
    assert report["total_missing_values"] == 0
    assert all(v == 0 for v in report["missing_values"].values())


def test_format_report_mentions_versions_and_counts(snapshot_db):
    snapshot_db.add_snapshot("bob", readiness_score=42)
    text = format_report(dataset_quality_report(build_dataset(snapshot_db.session_factory)))
    assert "dataset=v1" in text
    assert "feature_schema=1" in text
    assert "scoring_rubric=1" in text
    assert "unique users:" in text
