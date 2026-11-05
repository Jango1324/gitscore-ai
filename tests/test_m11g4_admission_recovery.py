"""Milestone 11-G4 -- offline-only admission-recovery for the
qualification-understanding pathway.

`segmentation.py` itself is byte-unchanged -- `recover_unadmitted_qualification_claims()`
is a NEW, additive function that reuses every one of its real, private
helpers via import (never duplicating their logic), producing
ADDITIONAL claims for exactly the gap M11-G3 disclosed: content
outside a recognized REQUIRED/PREFERRED/RESPONSIBILITY section that
fails segmentation's own `_looks_like_requirement` gate but passes
`competency_extraction.py`'s own, already-approved `_QUALIFYING_INTENT_V2`
gate.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.competency_extraction import (  # noqa: E402
    DeclinedExtraction,
    extract_competency_qualifications_v2,
)
from gitscore.jobs.parsing.qualification import project_qualification  # noqa: E402
from gitscore.jobs.parsing.qualification_admission_recovery import (  # noqa: E402
    recover_unadmitted_qualification_claims,
)
from gitscore.jobs.parsing.segmentation import (  # noqa: E402
    document_has_any_recognized_heading,
    segment_description,
)


def _recovered_texts(description: str) -> set[str]:
    return {r.claim.text for r in recover_unadmitted_qualification_claims(description)}


def _admitted_texts(description: str) -> set[str]:
    return {c.text for c in segment_description(description)}


# ---------------------------------------------------------------------------
# The core fix: genuinely unsectioned "strong understanding of X" is
# recovered.
# ---------------------------------------------------------------------------


def test_recovers_strong_understanding_phrasing_outside_any_section():
    description = "Strong understanding of distributed systems.\n"
    assert "Strong understanding of distributed systems." not in _admitted_texts(description)
    assert "Strong understanding of distributed systems." in _recovered_texts(description)


def test_does_not_recover_text_failing_both_gates():
    description = "Our company offers great perks.\n"
    assert _recovered_texts(description) == set()


# ---------------------------------------------------------------------------
# Never duplicates an already-admitted claim.
# ---------------------------------------------------------------------------


def test_never_duplicates_an_already_admitted_claim():
    description = "Requirements:\nExperience with distributed systems is required.\n"
    admitted = _admitted_texts(description)
    recovered = _recovered_texts(description)
    assert admitted & recovered == set()
    assert "Experience with distributed systems is required." in admitted
    assert "Experience with distributed systems is required." not in recovered


def test_never_recovers_content_inside_a_recognized_section():
    description = "Requirements:\nStrong understanding of signal processing.\n"
    # Already admitted unconditionally (in_recognized_section bypass) --
    # recovery must never ALSO produce this claim.
    assert "Strong understanding of signal processing." in _admitted_texts(description)
    assert "Strong understanding of signal processing." not in _recovered_texts(description)


def test_never_recovers_content_under_a_skip_section():
    description = "Benefits:\nStrong understanding of distributed systems.\n"
    # "Benefits:" classifies as SKIP -- content under it must never be
    # recovered, mirroring segment_description()'s own unconditional
    # suppression there.
    assert _recovered_texts(description) == set()


# ---------------------------------------------------------------------------
# Recovering admission is never the same as confident acceptance --
# every existing downstream safety check still applies unchanged.
# ---------------------------------------------------------------------------


def _run(description: str, target_text: str):
    claims = {c.text: c for c in segment_description(description)}
    recovered = {r.claim.text: r.claim for r in recover_unadmitted_qualification_claims(description)}
    claim = claims.get(target_text) or recovered[target_text]
    doc_heading = document_has_any_recognized_heading(description)
    span = SourceSpan(claim.start, claim.end)
    return extract_competency_qualifications_v2(
        claim.text, span, section_kind=claim.section_kind,
        document_has_recognized_heading=doc_heading, has_section_context=True,
    )


def test_recovered_responsibility_lead_still_declines():
    description = "Additional Information:\nDesign and build strong distributed systems architecture.\n"
    result = _run(description, "Design and build strong distributed systems architecture.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "responsibility_lead"


def test_recovered_narrative_still_declines():
    description = "Our team has deep expertise in distributed systems.\n"
    result = _run(description, "Our team has deep expertise in distributed systems.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "narrative_cue"


def test_recovered_negation_still_declines():
    description = "No prior knowledge with control systems is necessary.\n"
    result = _run(description, "No prior knowledge with control systems is necessary.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "negation"


def test_recovered_or_list_safety_still_declines():
    description = "Strong understanding of concurrency or distributed systems.\n"
    result = _run(description, "Strong understanding of concurrency or distributed systems.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"


def test_recovered_claim_without_tag_vocabulary_never_fabricates_a_tag():
    description = "A strong technical aptitude is expected.\n"
    result = _run(description, "A strong technical aptitude is expected.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "no_competency_language"


# ---------------------------------------------------------------------------
# A recovered claim correctly composes with M11-G2's section-aware
# necessity resolution: UNKNOWN for a preamble/UNKNOWN/LEARNING origin,
# REQUIRED for a genuinely unsectioned whole document.
# ---------------------------------------------------------------------------


def test_recovered_preamble_claim_stays_unknown_necessity():
    description = "Strong understanding of concurrency.\n\nRequirements:\nKnowledge of distributed systems.\n"
    result = _run(description, "Strong understanding of concurrency.")
    assert not isinstance(result, DeclinedExtraction)
    assert result[0].necessity is None
    assert project_qualification(result[0]).unsafe_reason == "necessity_unknown"


def test_recovered_claim_in_genuinely_unsectioned_document_defaults_required():
    description = "Strong understanding of concurrency.\n"
    result = _run(description, "Strong understanding of concurrency.")
    assert not isinstance(result, DeclinedExtraction)
    assert result[0].necessity is not None and result[0].necessity.value.upper() == "REQUIRED"


# ---------------------------------------------------------------------------
# Source-span fidelity: the recovered Claim's span is exactly traceable
# into the original description, identical to how segment_description()
# itself guarantees this for admitted claims.
# ---------------------------------------------------------------------------


def test_recovered_claim_span_is_exact():
    description = "Preamble text.\nStrong understanding of distributed systems.\n"
    recovered = recover_unadmitted_qualification_claims(description)
    [r] = [x for x in recovered if x.claim.text == "Strong understanding of distributed systems."]
    assert description[r.claim.start:r.claim.end] == r.claim.text


# ---------------------------------------------------------------------------
# Not wired into the live parser.
# ---------------------------------------------------------------------------


def test_not_wired_into_the_live_parser():
    import inspect

    import gitscore.jobs.parsing.parser as parser_module
    import gitscore.jobs.parsing.segmentation as segmentation_module

    assert "qualification_admission_recovery" not in inspect.getsource(parser_module)
    assert "qualification_admission_recovery" not in inspect.getsource(segmentation_module)


def test_segmentation_module_is_byte_unchanged():
    """A regression guard distinct from the 'not wired in' check above:
    confirms this milestone did not even touch segmentation.py's own
    file, which M11-G3's own disclosed finding explicitly said would
    require a STOP if it were necessary."""
    import subprocess

    result = subprocess.run(
        ["git", "diff", "--quiet", "--", "src/gitscore/jobs/parsing/segmentation.py"],
        cwd=str(REPO_ROOT), check=False,
    )
    assert result.returncode == 0, "segmentation.py has uncommitted changes -- M11-G4 must never touch it"
