"""Milestone 11-G8 -- competency-recall bottleneck decomposition.

Evaluation-only. No production code changed by this milestone --
these tests guard the INTEGRITY of the diagnostic instrumentation
(`scripts/evaluation_lib/m11g8_stage_attribution.py`) and pin the
measured, reproduced facts this milestone's report is built on, so a
future change to the offline pipeline that shifts these numbers is
caught and must be explained, not silently absorbed.

Both corpora (`evaluation/m11f`, `evaluation/m11g5`) are preserved,
already-inspected, local-only material -- never fresh holdouts, never
tuned against by this milestone. Frozen gold hash integrity is
verified directly; nothing in either corpus was edited.
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

M11G5_GOLD = REPO_ROOT / "evaluation" / "m11g5" / "holdout_annotations.json"
M11F_GOLD = REPO_ROOT / "evaluation" / "m11f" / "holdout_annotations.json"

pytestmark = pytest.mark.skipif(
    not (M11G5_GOLD.exists() and M11F_GOLD.exists()),
    reason="M11-F/M11-G5 local-only corpora not present (never staged)",
)


def _verify_hash(gold_path: Path, freeze_path: Path) -> None:
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    actual = gold_path.read_bytes()
    assert hashlib.sha256(actual).hexdigest() == freeze["sha256"], (
        f"{gold_path} has changed since its freeze -- M11-G8 must never edit frozen gold"
    )


def test_m11g5_gold_hash_unchanged():
    _verify_hash(M11G5_GOLD, REPO_ROOT / "evaluation" / "m11g5" / "gold_hash_freeze.json")


def test_m11f_gold_hash_unchanged():
    _verify_hash(M11F_GOLD, REPO_ROOT / "evaluation" / "m11f" / "gold_hash_freeze.json")


def test_stage_attribution_reconciles_with_known_historical_recall():
    """Phase 1 reproduction: the stage-attribution script's own
    TP/FN split must reconcile exactly with the previously-reported
    M11-G5 recall (5/40) -- a control-level convention, confirmed
    different from M11-F's own per-tag-set convention (12/74) by
    construction, not by coincidence (see the milestone doc's own
    Phase 1 denominator-definition analysis)."""
    import m11g8_stage_attribution as attribution

    m11g5_source = REPO_ROOT / "evaluation" / "m11g5" / "source"
    result = attribution.run_corpus(
        "m11g5", M11G5_GOLD, m11g5_source, attribution._build_g5_body_loader(m11g5_source)
    )
    assert result["n_taggable"] == 40
    assert result["n_confirmed_tp_not_fn"] == 5
    assert result["n_confirmed_fn"] == 35
    assert result["n_confirmed_tp_not_fn"] + result["n_confirmed_fn"] == result["n_taggable"]


def test_stage_attribution_categories_sum_to_confirmed_fn():
    """No double-counting across stages (explicit Phase 2 requirement):
    every confirmed FN lands in EXACTLY one stage bucket."""
    import m11g8_stage_attribution as attribution

    m11g5_source = REPO_ROOT / "evaluation" / "m11g5" / "source"
    result = attribution.run_corpus(
        "m11g5", M11G5_GOLD, m11g5_source, attribution._build_g5_body_loader(m11g5_source)
    )
    assert sum(result["stage_counts_among_confirmed_fn"].values()) == result["n_confirmed_fn"]
    # Each row contributes to exactly one stage or "NONE" (not an FN at all).
    stages_seen = {r["stage"] for r in result["rows"]}
    assert stages_seen <= {"A", "B", "C", "D", "E", "F", "H", "NONE"}


def test_category_e_validation_safeguards_are_not_the_measured_bottleneck():
    """Experiment C's headline finding: among confirmed FNs in BOTH
    corpora, zero were caused by the existing negation/narrative-cue/
    responsibility-lead/missing-contract validation safeguards --
    pinned here so a future change that starts rejecting valid
    competencies at this stage is caught, not silently absorbed."""
    import m11g8_stage_attribution as attribution

    m11g5_source = REPO_ROOT / "evaluation" / "m11g5" / "source"
    m11f_source = REPO_ROOT / "evaluation" / "m11f" / "source"
    g5 = attribution.run_corpus(
        "m11g5", M11G5_GOLD, m11g5_source, attribution._build_g5_body_loader(m11g5_source)
    )
    f = attribution.run_corpus(
        "m11f", M11F_GOLD, m11f_source, attribution._build_m11f_body_loader(m11f_source)
    )
    assert g5["stage_counts_among_confirmed_fn"].get("E", 0) == 0
    assert f["stage_counts_among_confirmed_fn"].get("E", 0) == 0


def test_earliest_stage_is_not_sole_blocker_double_blocking_pinned():
    """Critical correctness pin: the 39 Category-B (intent-gate)
    failures are NOT 39 recoverable tags -- only 7 would also succeed
    at vocabulary matching if the intent gate were bypassed; 32 are
    double-blocked (fail vocabulary matching too, regardless of the
    intent gate). Conversely, all 47 Category-C failures would clear
    the downstream validation safeguards if vocabulary matching
    hypothetically succeeded -- that ceiling is not secondarily
    blocked, unlike B's. Pinned so a future, unrelated change to the
    vocabulary tables or validation safeguards that shifts this split
    is noticed and explained, not silently absorbed into an overstated
    'B is cheaply fixable' claim."""
    import m11g8_stage_attribution as attribution

    m11g5_source = REPO_ROOT / "evaluation" / "m11g5" / "source"
    m11f_source = REPO_ROOT / "evaluation" / "m11f" / "source"
    g5 = attribution.run_corpus(
        "m11g5", M11G5_GOLD, m11g5_source, attribution._build_g5_body_loader(m11g5_source)
    )
    f = attribution.run_corpus(
        "m11f", M11F_GOLD, m11f_source, attribution._build_m11f_body_loader(m11f_source)
    )
    db_g5 = g5["double_blocking_analysis"]
    db_f = f["double_blocking_analysis"]
    total_b_intent_only = db_g5["n_b_recoverable_by_intent_fix_alone"] + db_f["n_b_recoverable_by_intent_fix_alone"]
    total_b_double = db_g5["n_b_double_blocked"] + db_f["n_b_double_blocked"]
    total_c_clears = db_g5["n_c_would_clear_downstream"] + db_f["n_c_would_clear_downstream"]
    total_c_blocked = db_g5["n_c_would_still_be_blocked_by_e"] + db_f["n_c_would_still_be_blocked_by_e"]

    assert total_b_intent_only == 7
    assert total_b_double == 32
    assert total_b_intent_only + total_b_double == 39
    assert total_c_clears == 47
    assert total_c_blocked == 0


def test_experiment_a_oracle_admission_recovers_zero_additional_cases():
    """Experiment A's headline finding: the sole confirmed admission
    failure (stage A, m11g5-p03-05) still fails downstream even when
    admission is bypassed entirely and the real extractor is called
    directly on the gold text -- oracle admission recovers ZERO
    additional cases. Pinned so a future, unrelated downstream change
    that happens to start recognizing this specific sentence is
    noticed and explained, not silently absorbed."""
    import sys as _sys
    from gitscore.jobs.models import SourceSpan
    from gitscore.jobs.parsing.competency_extraction import (
        DeclinedExtraction,
        extract_competency_qualifications_v2,
    )

    gold = json.loads(M11G5_GOLD.read_text(encoding="utf-8"))
    control = next(c for c in gold["controls"] if c["id"] == "m11g5-p03-05")
    span = SourceSpan(0, len(control["text"]))
    result = extract_competency_qualifications_v2(control["text"], span)
    assert isinstance(result, DeclinedExtraction), (
        "expected this control to still be declined under oracle admission -- "
        "if it now succeeds, the Experiment A 'zero additional recall' finding "
        "no longer holds and the milestone doc must be updated, not this test "
        "silently loosened"
    )
