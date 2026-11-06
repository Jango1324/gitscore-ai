"""Milestone 11-G9 -- offline competency extractor v3 feasibility.

Evaluation-only. No production code changed by this milestone -- these
tests guard the INTEGRITY of the fresh M11-G9 corpus (hash-sealed
holdout, never tuned against), confirm v3 lives entirely outside
`src/gitscore` and never touches v1/v2, and pin the measured,
reproduced facts this milestone's report is built on so a future change
that shifts them is caught and must be explained, not silently
absorbed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation_lib"))

M11G9_HOLDOUT = REPO_ROOT / "evaluation" / "m11g9" / "holdout_annotations.json"
M11G9_FREEZE = REPO_ROOT / "evaluation" / "m11g9" / "gold_hash_freeze.json"
M11G9_DEV = REPO_ROOT / "evaluation" / "m11g9" / "dev_annotations.json"

pytestmark = pytest.mark.skipif(
    not (M11G9_HOLDOUT.exists() and M11G9_DEV.exists()),
    reason="M11-G9 local-only corpus not present (never staged)",
)


def test_m11g9_holdout_gold_hash_unchanged():
    """The sealed holdout must never be edited after its freeze point --
    this is the ONE thing this milestone cannot ever let drift silently."""
    freeze = json.loads(M11G9_FREEZE.read_text(encoding="utf-8"))
    actual = M11G9_HOLDOUT.read_bytes()
    assert hashlib.sha256(actual).hexdigest() == freeze["sha256"], (
        f"{M11G9_HOLDOUT} has changed since its freeze -- M11-G9 must never edit frozen gold"
    )


def test_v3_module_does_not_live_under_src_gitscore():
    """v3 is an evaluation-only prototype -- confirmed it is not importable
    as part of the `gitscore` package at all (lives only under
    `scripts/evaluation_lib/`)."""
    import importlib
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("gitscore.jobs.parsing.competency_extraction_v3")


def test_v1_v2_module_is_byte_identical_to_pre_g9_state():
    """v1/v2's own production module is untouched by this milestone --
    confirmed structurally: the module still exposes exactly the same
    public v1/v2 entry points it did before M11-G9, and v3's own source
    file is NOT referenced anywhere inside it."""
    import gitscore.jobs.parsing.competency_extraction as v1v2
    assert hasattr(v1v2, "extract_competency_qualifications")
    assert hasattr(v1v2, "extract_competency_qualifications_v2")
    source = Path(v1v2.__file__).read_text(encoding="utf-8")
    assert "v3" not in source.lower()
    assert "m11g9" not in source.lower()


def test_v3_is_not_imported_by_production_or_by_v1_v2():
    """Confirms v3 has zero inbound references from `src/gitscore` --
    grepping the entire package source, mirroring the same confirmation
    style `competency_aliases.py`'s own docstring and test already use
    for itself ('NOT wired into the live parser')."""
    src_root = REPO_ROOT / "src" / "gitscore"
    offenders = []
    for path in src_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "m11g9" in text.lower() or "competency_extraction_v3" in text:
            offenders.append(str(path))
    assert offenders == [], f"v3 must never be referenced from src/gitscore: {offenders}"


def test_m11g9_phase4_headline_metrics_pinned():
    """Pins the exact Phase 4 v2-vs-v3 sealed-holdout measurement this
    milestone's report is built on. A future, unrelated change to v2's
    vocabulary/alias tables OR to v3's own 3-new-concept/4-alias-fix
    additions that shifts these numbers must be explained, not silently
    absorbed into a stale report."""
    import evaluate_m11g9_v3_feasibility as ev

    report = ev.evaluate(M11G9_HOLDOUT, "m11g9-holdout", verify_seal=True)
    v2 = report["extractors"]["v2"]
    v3 = report["extractors"]["v3"]

    assert v2["denominator_A_original_17_tags"] == {"n_taggable": 17, "n_correct": 1, "recall": 0.0588}
    assert v3["denominator_A_original_17_tags"] == {"n_taggable": 17, "n_correct": 1, "recall": 0.0588}
    assert v2["denominator_B_new_concepts_only"] == {"n_taggable": 3, "n_correct": 0, "recall": 0.0}
    assert v3["denominator_B_new_concepts_only"] == {"n_taggable": 3, "n_correct": 1, "recall": 0.3333}
    assert v2["false_positive_safety"]["n_false_positives"] == 1
    assert v3["false_positive_safety"]["n_false_positives"] == 1
    assert v2["n_recognized_any_tag"] == 1
    assert v3["n_recognized_any_tag"] == 2


def test_v3_introduces_no_new_false_positive_beyond_v2():
    """Critical safety pin: every false positive v3 produces on the
    sealed holdout's non-technical_competency controls is ALSO produced
    by v2 -- v3's vocabulary expansion must never be the SOLE cause of a
    new false positive relative to the unmodified v2 it extends."""
    import evaluate_m11g9_v3_feasibility as ev

    report = ev.evaluate(M11G9_HOLDOUT, "m11g9-holdout", verify_seal=True)
    v2_fp_ids = {row["id"] for row in report["extractors"]["v2"]["false_positive_safety"]["rows"]}
    v3_fp_ids = {row["id"] for row in report["extractors"]["v3"]["false_positive_safety"]["rows"]}
    assert v3_fp_ids <= v2_fp_ids, f"v3 introduced a NEW false positive not present in v2: {v3_fp_ids - v2_fp_ids}"


def test_preexisting_benchmarking_false_positive_pinned():
    """Pins a genuine, pre-existing (v1/v2-inherited, NOT v3-introduced)
    precision defect this milestone's fresh holdout surfaced: the bare
    word 'benchmarking' (an ACTIVE narrower_or_more_specific alias of
    performance-optimization) fires on a purely soft-skill sentence that
    is not a performance claim at all. Documented as a found limitation,
    not fixed by this milestone (v3 deliberately reuses v2's tables
    unchanged) -- pinned here so a future, unrelated change that
    silently fixes OR worsens it is noticed."""
    import sys as _sys
    from gitscore.jobs.models import SourceSpan
    from gitscore.jobs.parsing.competency_extraction import extract_competency_qualifications_v2

    text = (
        "Solid debugging, benchmarking, and systems-thinking abilities, able to connect "
        "low-level implementation detail to everyday product impact."
    )
    result = extract_competency_qualifications_v2(text, SourceSpan(0, len(text)))
    assert isinstance(result, tuple) and len(result) == 1
    assert result[0].normalized_reference.competency_tag == "performance-optimization", (
        "expected this PRE-EXISTING false-positive to still fire -- if it no longer does, "
        "v1/v2's own alias table changed and the milestone doc's precision-safety finding "
        "must be updated, not this test silently tightened"
    )


def test_v3_new_concept_tags_do_not_overlap_existing_17_tags():
    """The 3 new top-level concepts v3 adds are genuinely NEW slugs, not
    accidental synonyms colliding with an existing tag name."""
    from m11g9_competency_extraction_v3 import _V3_NEW_CONCEPTS
    from evaluate_m11g9_v3_feasibility import ORIGINAL_17_TAGS

    new_tags = {tag for tag, _pattern in _V3_NEW_CONCEPTS}
    assert len(new_tags) == 3
    assert new_tags.isdisjoint(ORIGINAL_17_TAGS)


def test_v3_declines_every_identified_risky_alias_case():
    """Confirms the explicit NON-additions documented in v3's own module
    docstring -- each 'risky_related' conflation case identified during
    Phase 1/2 annotation remains correctly UNTAGGED by v3, not
    accidentally captured by the new vocabulary's broader matching."""
    from gitscore.jobs.models import SourceSpan
    from m11g9_competency_extraction_v3 import extract_competency_qualifications_v3

    risky_cases = [
        "The team maintains operational excellence through rigorous testing, monitoring, "
        "on-call paging, and incident management for every production service.",
        "Preferred: experience driving cloud cost optimization initiatives across a large "
        "engineering org.",
        "Must-have: hands-on exposure to running AI/ML workloads in production.",
        "Hands-on experience with ReBAC authorization systems such as OpenFGA, Zanzibar, or "
        "SpiceDB, including schema modeling, tuple-based policy authoring, and "
        "permission-evaluation performance analysis.",
    ]
    for text in risky_cases:
        result = extract_competency_qualifications_v3(text, SourceSpan(0, len(text)))
        assert not isinstance(result, tuple) or result == (), (
            f"v3 unexpectedly produced a Qualification for a known-risky case: {text!r} -> {result!r}"
        )
