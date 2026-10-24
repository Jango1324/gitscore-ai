"""Milestone 9C -- tests for `parse_job_description_with_diagnostics()`
and `UnparsedClaim` (`jobs/parsing/parser.py`).

Two invariants matter above all others here:

1. `parse_job_description()` itself must be COMPLETELY unaffected --
   every existing caller (including every `scripts/evaluate_*.py`
   harness and the whole Milestone 9B preservation benchmark) must see
   byte-for-byte identical behavior. Pinned by comparing its output
   against `parse_job_description_with_diagnostics(...).profile` across
   a wide range of real job-description fixtures already used
   elsewhere in this test suite.
2. `unparsed_claims` must report EXACTLY the claims Milestone 9B's own
   corpus already identified as silent drops -- no more (a false
   positive would mean ordinary prose is being flagged as a missed
   requirement) and no fewer (a false negative would silently re-hide
   exactly the gap this milestone exists to surface).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from gitscore.jobs import parse_job_description, parse_job_description_with_diagnostics
from gitscore.jobs.parsing.parser import UnparsedClaim

from evaluation_lib.preservation_eval import wrap_entry

CORPUS_PATH = REPO_ROOT / "evaluation" / "m9b" / "corpus.json"

BACKEND_JD = """Backend Software Engineer

We are a fast-growing startup revolutionizing how teams ship software.

Requirements:
- 3+ years of experience building Python backend services
- Experience with PostgreSQL
- Familiarity with Docker
- Excellent written and verbal communication

Preferred Qualifications:
- Experience with AWS
- Experience with Next.js
"""

ML_JD = """Machine Learning Engineer

About the team: we are passionate about building next-generation AI products.

Requirements:
- Expert-level Python
- Deep experience with PyTorch
- 5+ years of professional software engineering experience
- Experience with Docker or Kubernetes

Preferred Qualifications:
- Experience deploying models to AWS or Azure
- Experience mentoring junior engineers
"""

EMBEDDED_JD = """Embedded Firmware Engineer

Requirements:
- Strong C experience in embedded, resource-constrained environments
- Familiarity with microcontroller peripherals such as SPI, I2C, and UART
"""

KNOWN_SILENT_DROP_IDS = {"m9b-005", "m9b-006", "m9b-008", "m9b-014", "m9b-015", "m9b-016"}


def _load_corpus_entries() -> list[dict]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["entries"]


# ---------------------------------------------------------------------------
# Invariant 1: parse_job_description() is byte-for-byte unaffected
# ---------------------------------------------------------------------------


def test_diagnostics_profile_matches_plain_parse_exactly_for_real_fixtures():
    for jd in (BACKEND_JD, ML_JD, EMBEDDED_JD):
        plain = parse_job_description(jd)
        with_diag = parse_job_description_with_diagnostics(jd)
        assert plain == with_diag.profile


def test_diagnostics_profile_matches_plain_parse_across_the_full_m9b_corpus():
    for entry in _load_corpus_entries():
        wrapped = wrap_entry(entry)
        plain = parse_job_description(wrapped)
        with_diag = parse_job_description_with_diagnostics(wrapped)
        assert plain == with_diag.profile, entry["id"]


def test_title_and_company_are_forwarded_identically():
    plain = parse_job_description(BACKEND_JD, title="Backend Engineer", company="Acme")
    with_diag = parse_job_description_with_diagnostics(BACKEND_JD, title="Backend Engineer", company="Acme")
    assert plain.title == with_diag.profile.title == "Backend Engineer"
    assert plain.company == with_diag.profile.company == "Acme"


# ---------------------------------------------------------------------------
# Invariant 2: unparsed_claims matches M9B's own corpus exactly
# ---------------------------------------------------------------------------


def test_unparsed_claims_reproduces_every_m9b_known_silent_drop():
    entries_by_id = {e["id"]: e for e in _load_corpus_entries()}
    for entry_id in KNOWN_SILENT_DROP_IDS:
        entry = entries_by_id[entry_id]
        wrapped = wrap_entry(entry)
        result = parse_job_description_with_diagnostics(wrapped)
        unparsed_texts = {c.text for c in result.unparsed_claims}
        assert entry["source_text"] in unparsed_texts, (
            f"{entry_id} ({entry['source_text']!r}) was expected to be an UnparsedClaim "
            f"but was not -- got {unparsed_texts!r}"
        )


def test_unparsed_claims_never_includes_a_recognized_or_placeholder_claim():
    """Zero false positives: every entry in the M9B corpus that DID
    produce >=1 JobRequirement row (recognized concept, non-technical
    match, or the Milestone 9A placeholder) must NEVER also appear in
    `unparsed_claims` -- a claim is either preserved as a real row or
    reported as unparsed, never both.
    """
    for entry in _load_corpus_entries():
        wrapped = wrap_entry(entry)
        result = parse_job_description_with_diagnostics(wrapped)
        produced_rows = [r for r in result.profile.requirements if r.original_text == entry["source_text"]]
        unparsed_texts = {c.text for c in result.unparsed_claims}
        if produced_rows:
            assert entry["source_text"] not in unparsed_texts, entry["id"]


def test_unparsed_claims_never_flags_ordinary_prose_or_headings():
    """Segmentation's own existing, unmodified gate decides what counts
    as a candidate claim at all -- a heading or marketing-prose line
    never becomes a `Claim` in the first place, so it can never appear
    in `unparsed_claims` either. No new, looser trigger was introduced.
    """
    result = parse_job_description_with_diagnostics(BACKEND_JD)
    unparsed_texts = {c.text for c in result.unparsed_claims}
    assert "We are a fast-growing startup revolutionizing how teams ship software." not in unparsed_texts
    assert not any("Backend Software Engineer" in text for text in unparsed_texts)


def test_unparsed_claim_source_span_is_exact():
    text = "Requirements:\n- Experience designing distributed systems\n"
    result = parse_job_description_with_diagnostics(text)
    assert len(result.unparsed_claims) == 1
    claim = result.unparsed_claims[0]
    assert claim.text == "Experience designing distributed systems"
    assert text[claim.source_span.start : claim.source_span.end] == claim.text


def test_unparsed_claim_is_frozen_and_hashable():
    from gitscore.jobs.models import SourceSpan

    claim = UnparsedClaim(text="x", source_span=SourceSpan(0, 1))
    hash(claim)  # must not raise
    import pytest

    with pytest.raises(AttributeError):
        claim.text = "y"  # type: ignore[misc]
