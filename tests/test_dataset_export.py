"""Tests for gitscore.dataset.export.export_dataset (Milestone 4)."""
import json
from datetime import datetime

import pytest

from gitscore.dataset import schema
from gitscore.dataset.builder import build_dataset
from gitscore.dataset.export import export_dataset


def _populate(snapshot_db):
    snapshot_db.add_snapshot("alice", collected_at=datetime(2026, 1, 1), readiness_score=15,
                             most_used_language="Python", total_repos=4, average_stars=1.5)
    snapshot_db.add_snapshot("bob", collected_at=datetime(2026, 1, 2), readiness_score=62,
                             most_used_language="Rust", total_repos=9, has_python=True)
    snapshot_db.add_snapshot("bob", collected_at=datetime(2026, 3, 2), readiness_score=70,
                             most_used_language="Rust", total_repos=11, has_python=True)


def test_export_writes_csv_and_meta(snapshot_db, tmp_path):
    _populate(snapshot_db)
    result = build_dataset(snapshot_db.session_factory)
    out = tmp_path / "ds.csv"

    written = export_dataset(result, out)

    assert written == out
    assert out.exists()
    meta = out.with_suffix(".meta.json")
    assert meta.exists()
    meta_obj = json.loads(meta.read_text())
    assert meta_obj["dataset_version"] == schema.DATASET_VERSION
    assert meta_obj["feature_schema_version"] == schema.FEATURE_SCHEMA_VERSION
    assert meta_obj["scoring_rubric_version"] == schema.SCORING_RUBRIC_VERSION
    assert meta_obj["n_rows"] == 2
    assert meta_obj["feature_columns"] == schema.FEATURE_COLUMNS
    assert meta_obj["target_column"] == schema.TARGET_COLUMN


def test_csv_header_is_exactly_the_schema_columns(snapshot_db, tmp_path):
    _populate(snapshot_db)
    result = build_dataset(snapshot_db.session_factory)
    out = tmp_path / "ds.csv"
    export_dataset(result, out, write_meta=False)

    header = out.read_text().splitlines()[0]
    assert header.split(",") == schema.DATASET_COLUMNS


def test_csv_export_is_byte_for_byte_deterministic(snapshot_db, tmp_path):
    _populate(snapshot_db)
    result = build_dataset(snapshot_db.session_factory)

    first = tmp_path / "a.csv"
    second = tmp_path / "b.csv"
    export_dataset(result, first, write_meta=False)
    export_dataset(build_dataset(snapshot_db.session_factory), second, write_meta=False)

    assert first.read_bytes() == second.read_bytes()


def test_csv_uses_lf_line_endings(snapshot_db, tmp_path):
    _populate(snapshot_db)
    result = build_dataset(snapshot_db.session_factory)
    out = tmp_path / "ds.csv"
    export_dataset(result, out, write_meta=False)
    assert b"\r\n" not in out.read_bytes()


def test_export_contains_no_identifier_columns(snapshot_db, tmp_path):
    _populate(snapshot_db)
    result = build_dataset(snapshot_db.session_factory)
    out = tmp_path / "ds.csv"
    export_dataset(result, out, write_meta=False)
    header = out.read_text().splitlines()[0].split(",")
    for leaky in ("user_id", "snapshot_id", "github_username", "collected_at", "id"):
        assert leaky not in header


def test_export_empty_dataset_writes_header_only(snapshot_db, tmp_path):
    result = build_dataset(snapshot_db.session_factory)
    out = tmp_path / "empty.csv"
    export_dataset(result, out, write_meta=False)
    lines = out.read_text().splitlines()
    assert lines == [",".join(schema.DATASET_COLUMNS)]
