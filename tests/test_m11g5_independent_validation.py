"""Milestone 11-G5 -- independent full-pipeline qualification
validation.

This is an EVALUATION-ONLY milestone: nothing here imports a new
production module, and nothing in `src/gitscore` changed to produce
these results (confirmed separately by Phase 0/Phase 7's unchanged
`git status` on tracked files). These tests guard the INTEGRITY of the
evaluation harness itself:

1. the frozen gold (`evaluation/m11g5/holdout_annotations.json`) and
   the frozen sources (`evaluation/m11g5/source/*.txt`) have not been
   altered since their hash-freeze point -- any future edit to either
   file (accidental or a later milestone tuning against this corpus)
   will fail these tests loudly;
2. the Phase 1 dual-path reconciliation harness
   (`m11g5_dual_path_comparison.run_dual_path`) never silently
   concatenates Path A and Path B output -- every comparison it
   produces carries exactly one of the four named, mutually exclusive
   relationship labels the milestone's reconciliation design commits
   to;
3. one discovered, pre-existing Path A (live parser v10) gap is
   characterized and pinned so it is never silently "fixed" by a
   future change without that change being deliberate and reviewed.

`evaluation/m11g5/*` and `scripts/evaluation_lib/m11g5_*.py` are
local-only, never staged (see this milestone's own `provenance.json`)
-- these tests skip gracefully if that local-only data is absent
(e.g. a fresh clone that never ran the Phase 2/3 acquisition step),
exactly like M11-D/M11-F's own tests before them.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation_lib"))

M11G5_DIR = REPO_ROOT / "evaluation" / "m11g5"
GOLD_PATH = M11G5_DIR / "holdout_annotations.json"
FREEZE_PATH = M11G5_DIR / "gold_hash_freeze.json"
SOURCE_HASHES_PATH = M11G5_DIR / "source_hashes.json"
SOURCE_DIR = M11G5_DIR / "source"

pytestmark = pytest.mark.skipif(
    not GOLD_PATH.exists(),
    reason="M11-G5 local-only corpus/gold not present (never staged -- see provenance.json)",
)


# ---------------------------------------------------------------------------
# 1. Hash-freeze integrity -- gold and sources are unaltered since freeze.
# ---------------------------------------------------------------------------


def test_gold_hash_matches_freeze_record():
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    actual = GOLD_PATH.read_bytes()
    assert len(actual) == freeze["length_bytes"]
    assert hashlib.sha256(actual).hexdigest() == freeze["sha256"], (
        "evaluation/m11g5/holdout_annotations.json has changed since its Phase 3 "
        "freeze point -- gold must never be edited after inference began"
    )


def test_every_source_file_matches_its_frozen_hash():
    recorded = json.loads(SOURCE_HASHES_PATH.read_text(encoding="utf-8"))
    for posting_id, meta in recorded.items():
        actual = (SOURCE_DIR / posting_id).read_bytes()
        assert len(actual) == meta["length_bytes"], posting_id
        assert hashlib.sha256(actual).hexdigest() == meta["sha256"], (
            f"{posting_id} has changed since its Phase 2 acquisition hash was recorded"
        )


def test_gold_hash_freeze_was_computed_before_any_inference_is_not_assumed_but_the_corpus_is_frozen():
    """Does not re-derive the freeze timestamp (no inference-timing oracle
    exists to check against) -- asserts the one thing this test CAN check:
    the freeze record names the exact file this milestone's harness reads,
    so a future rename cannot silently point the freeze at the wrong file."""
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    assert freeze["frozen_file"] == "evaluation/m11g5/holdout_annotations.json"


# ---------------------------------------------------------------------------
# 2. Reconciliation never silently concatenates -- every comparison carries
#    one of exactly four named relationships.
# ---------------------------------------------------------------------------

_VALID_RELATIONSHIPS = {
    "path_b_only_recovered",
    "path_b_adds_competency_to_already_admitted",
    "path_b_declines_already_admitted",
    "contradictory",
}


def test_every_reconciled_comparison_has_a_valid_named_relationship():
    from m11g5_dual_path_comparison import run_dual_path

    description = (
        "Requirements:\n"
        "Strong understanding of distributed systems is required.\n"
        "Experience with Python preferred.\n"
    )
    result = run_dual_path(description)
    assert result["comparisons"], "expected at least one admitted claim from this fixture"
    for comp in result["comparisons"]:
        assert comp.relationship in _VALID_RELATIONSHIPS, comp.relationship


def test_reconciliation_is_deterministic_across_repeated_runs():
    from m11g5_dual_path_comparison import run_dual_path

    description = "Requirements:\nStrong understanding of distributed systems is required.\n"
    first = run_dual_path(description)
    second = run_dual_path(description)
    first_shape = [(c.span, c.relationship) for c in first["comparisons"]]
    second_shape = [(c.span, c.relationship) for c in second["comparisons"]]
    assert first_shape == second_shape


def test_recovered_claim_is_labeled_path_b_only_recovered_not_silently_merged():
    from m11g5_dual_path_comparison import run_dual_path

    description = "Strong understanding of distributed systems.\n"
    result = run_dual_path(description)
    assert any(c.relationship == "path_b_only_recovered" for c in result["comparisons"])


# ---------------------------------------------------------------------------
# 3. A characterized, pre-existing Path A gap -- pinned, not fixed.
#
# Root cause (confirmed directly against `segmentation.py`): the SKIP/
# NON_QUALIFICATION heading root `\bwho we are\b` is intended to suppress
# "Who We Are" company-narrative headings, but also matches the unrelated,
# authentic qualifications-section heading style "Who We Are Looking
# For:" (seen verbatim in this milestone's p03-alluxio-distributed.txt).
# The effect: `_classify_heading_line` returns `_SectionKind.SKIP` for
# that heading, and the ENTIRE section under it -- here, seven genuine
# REQUIRED qualifications, not a single phrasing edge case -- is admitted
# as zero claims (not even as diagnostic `unparsed_claim`s). This predates
# M11-G5 and is NOT a regression introduced by G1-G4; it is reported here,
# pinned by a characterization test, because the milestone instructions
# forbid changing `segmentation.py` in this evaluation-only pass. See
# `docs/evaluation/MILESTONE_11_G5_FULL_PIPELINE_VALIDATION.md` Phase 6.
# ---------------------------------------------------------------------------


def test_who_we_are_looking_for_heading_is_a_known_false_positive_skip_collision():
    from gitscore.jobs.parsing.segmentation import _classify_heading_line, _SectionKind

    assert _classify_heading_line(
        "Who We Are Looking For:", "Who We Are Looking For"
    ) is _SectionKind.SKIP


def test_entire_qualifications_section_under_that_heading_is_admitted_as_zero_claims():
    from gitscore.jobs.parsing.segmentation import segment_description

    description = (
        "Who We Are Looking For:\n"
        "A four-year degree in a relevant field.\n"
        "Several years of hands-on experience with a general-purpose programming language.\n"
    )
    assert segment_description(description) == ()
