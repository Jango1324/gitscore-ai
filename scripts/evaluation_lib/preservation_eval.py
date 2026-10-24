"""Milestone 9B Phase 1 -- requirement-preservation benchmark.

Evaluates `parse_job_description()` against `evaluation/m9b/corpus.json`,
an ADDITIVE corpus independent of (and never touching) the frozen
`evaluation/gold/` (8c:v1) and `evaluation/gold_v1_1/` (8c:v1.1)
benchmarks. See that corpus file's own `notes`/`schema` fields for the
annotation policy, and
`docs/evaluation/MILESTONE_9B_EVALUATION_INTEGRITY.md` Section 2 for the
full writeup.

Each corpus entry names exactly one claim (`source_text`) and declares,
independently of any parser run:
  - `is_requirement` / `is_technical` -- what KIND of claim this is
  - `ideal_outcome` -- what a maximally correct, non-fabricating parser
    SHOULD produce
  - `acceptable_fallback` -- an honest but degraded outcome this corpus
    does not count as a failure, or `None` if no such outcome is
    distinguished from a genuine gap

This module wraps each entry's `source_text` into a minimal, realistic
job-description context (`wrap_entry`), runs the REAL parser, finds the
produced `JobRequirement` row(s) whose `original_text` is an EXACT match
for `source_text` (ignoring any other filler claim in the same wrapped
text), and classifies the result into one of a small set of per-entry
verdicts. `aggregate_metrics()` then computes the ten DISTINCT measures
the milestone brief requires, kept deliberately separate -- a valid,
expected placeholder and a fabricated wrong technology are never merged
into one misleading "precision" number (see that function's own
docstring for exactly which raw counts feed which named metric).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from gitscore.jobs import JobRequirement, parse_job_description
from gitscore.jobs.types import GithubObservability

# --- per-entry verdict labels (distinct from the 8c:v1 CORRECT/MISSING
# taxonomy in scripts/evaluation_lib/taxonomy.py -- this benchmark asks a
# different question, "was this claim preserved honestly", not "does
# this match a fixed expected row", so it earns its own small vocabulary
# rather than overloading the existing one). ---------------------------
IDEAL_MATCH = "IDEAL_MATCH"                     # exactly the ideal_outcome
FALLBACK_MATCH = "FALLBACK_MATCH"               # the declared acceptable_fallback, not ideal
SILENT_DROP_ACCEPTED = "SILENT_DROP_ACCEPTED"   # zero rows, and the corpus accepts that for this entry
SILENT_DROP_GAP = "SILENT_DROP_GAP"             # zero rows, and the corpus does NOT accept that
WRONG_STRUCTURE = "WRONG_STRUCTURE"             # something produced, but neither ideal nor fallback shape
FABRICATED_CONCEPT = "FABRICATED_CONCEPT"       # a real, wrong concept_id/alternative id attached
SPURIOUS_ROW = "SPURIOUS_ROW"                   # a row produced for an is_requirement=false entry
CORRECTLY_EXCLUDED = "CORRECTLY_EXCLUDED"       # zero rows, and is_requirement=false (the correct outcome)

_WRAPPERS = {
    "requirements_bullet": lambda text: f"Requirements:\n- {text}\n",
    "preferred_bullet": lambda text: f"Preferred Qualifications:\n- {text}\n",
    "benefits_bullet": lambda text: f"Requirements:\n- Experience with Python\n\nBenefits:\n- {text}\n",
    "bare_heading": lambda text: f"{text}\n- Build internal tools\n- Ship features to production\n",
    "intro_prose": lambda text: f"{text}\n\nRequirements:\n- Experience with Python\n",
    "outside_section_sentence": lambda text: f"{text}\n",
}


def wrap_entry(entry: dict) -> str:
    wrapper = _WRAPPERS.get(entry["wrapping"])
    if wrapper is None:
        raise ValueError(f"{entry['id']}: unknown wrapping kind {entry['wrapping']!r}")
    return wrapper(entry["source_text"])


def _rows_for_claim(requirements: tuple[JobRequirement, ...], claim_text: str) -> list[JobRequirement]:
    return [r for r in requirements if r.original_text == claim_text]


def _is_placeholder_row(row: JobRequirement, category: str) -> bool:
    return row.concept_id is None and not row.is_alternative_group and row.category == category


def _observability_name(observability: GithubObservability) -> str:
    return observability.name.lower()


@dataclass
class EntryVerdict:
    entry_id: str
    category: str
    is_requirement: bool
    is_technical: bool
    verdict: str
    actual_row_count: int
    actual_summary: str
    span_correct: bool | None  # None when there is no row to check a span on
    notes: str = ""


@dataclass
class PreservationReport:
    verdicts: list[EntryVerdict] = field(default_factory=list)


def _summarize_rows(rows: list[JobRequirement]) -> str:
    parts = []
    for row in rows:
        if row.is_alternative_group:
            parts.append(f"ALT{sorted(row.alternative_concept_ids)}")
        elif row.concept_id is not None:
            parts.append(row.concept_id)
        else:
            parts.append(f"category={row.category!r}")
    return "; ".join(parts) if parts else "(none)"


def _matches_ideal(rows: list[JobRequirement], ideal: dict) -> bool:
    outcome_type = ideal["type"]

    if outcome_type in ("recognized_concepts", "unresolved_concept", "unresolved_concepts", "mixed_concepts"):
        expected_ids = set(ideal["concept_ids"])
        actual_ids = {r.concept_id for r in rows if r.concept_id is not None and not r.is_alternative_group}
        if actual_ids != expected_ids:
            return False
        expected_observability = ideal.get("github_observability")
        if expected_observability is None:
            return True
        return all(_observability_name(r.github_observability) == expected_observability for r in rows)

    if outcome_type == "unresolved_alternative_group":
        expected_ids = tuple(sorted(ideal["concept_ids"]))
        return any(r.is_alternative_group and tuple(sorted(r.alternative_concept_ids)) == expected_ids for r in rows)

    if outcome_type in ("competency_placeholder", "alternative_group_with_unsafe_segment"):
        category = ideal.get("category", "unresolved_requirement") or "alternative_requirement"
        if outcome_type == "alternative_group_with_unsafe_segment":
            category = "alternative_requirement"
        if not any(_is_placeholder_row(r, category) for r in rows):
            return False
        expected_observability = ideal.get("github_observability")
        if expected_observability is None:
            return True
        matching = [r for r in rows if _is_placeholder_row(r, category)]
        return any(_observability_name(r.github_observability) == expected_observability for r in matching)

    if outcome_type == "non_technical":
        expected_category = ideal.get("category")
        candidates = [r for r in rows if r.concept_id is None and not r.is_alternative_group]
        if not candidates:
            return False
        if expected_category is None:
            return True  # category string unspecified by design -- only concept_id=None matters
        return any(r.category == expected_category for r in candidates)

    if outcome_type == "excluded":
        return len(rows) == 0

    raise ValueError(f"unknown ideal_outcome type {outcome_type!r}")


def _matches_fallback(rows: list[JobRequirement], fallback: dict) -> bool:
    outcome_type = fallback["type"]
    if outcome_type == "silent_drop":
        return len(rows) == 0
    if outcome_type in ("unresolved_requirement_placeholder", "alternative_requirement_placeholder"):
        category = "unresolved_requirement" if outcome_type == "unresolved_requirement_placeholder" else "alternative_requirement"
        return any(_is_placeholder_row(r, category) for r in rows)
    raise ValueError(f"unknown acceptable_fallback type {outcome_type!r}")


def _has_fabricated_concept(rows: list[JobRequirement], ideal: dict, is_technical: bool) -> bool:
    """A row attaches a REAL (not `unresolved:*`, not `None`) concept id
    that is wrong -- i.e. the parser invented a specific, named
    technology attribution this claim never supports. Only meaningful to
    check for non-technical / no-named-product entries, where ANY real
    concept_id is by construction wrong; for technical entries with a
    real expected concept_id set, a non-expected real id is also
    fabrication, but an expected one is correct and excluded here.
    """
    expected_real_ids: set[str] = set()
    if ideal["type"] in ("recognized_concepts", "mixed_concepts"):
        expected_real_ids = {cid for cid in ideal["concept_ids"] if not cid.startswith("unresolved:")}
    if ideal["type"] == "unresolved_alternative_group":
        expected_real_ids = {cid for cid in ideal["concept_ids"] if not cid.startswith("unresolved:")}

    for row in rows:
        real_ids: set[str] = set()
        if row.is_alternative_group:
            real_ids = {cid for cid in row.alternative_concept_ids if not cid.startswith("unresolved:")}
        elif row.concept_id is not None and not row.concept_id.startswith("unresolved:"):
            real_ids = {row.concept_id}
        if real_ids - expected_real_ids:
            return True
    return False


def _span_correct(rows: list[JobRequirement], wrapped_text: str, claim_text: str) -> bool | None:
    if not rows:
        return None
    expected_start = wrapped_text.find(claim_text)
    if expected_start == -1:
        return False
    expected_end = expected_start + len(claim_text)
    return all(
        r.source_span is not None and r.source_span.start == expected_start and r.source_span.end == expected_end
        for r in rows
    )


def evaluate_entry(entry: dict) -> EntryVerdict:
    wrapped_text = wrap_entry(entry)
    profile = parse_job_description(wrapped_text, title="Milestone 9B Phase 1 corpus entry")
    rows = _rows_for_claim(profile.requirements, entry["source_text"])

    ideal = entry["ideal_outcome"]
    fallback = entry.get("acceptable_fallback")
    is_requirement = entry["is_requirement"]
    is_technical = entry["is_technical"]

    span_ok = _span_correct(rows, wrapped_text, entry["source_text"])

    if not is_requirement:
        verdict = CORRECTLY_EXCLUDED if not rows else SPURIOUS_ROW
        return EntryVerdict(
            entry_id=entry["id"], category=entry["category"], is_requirement=is_requirement,
            is_technical=is_technical, verdict=verdict, actual_row_count=len(rows),
            actual_summary=_summarize_rows(rows), span_correct=span_ok,
        )

    if _matches_ideal(rows, ideal):
        verdict = IDEAL_MATCH
    elif fallback is not None and _matches_fallback(rows, fallback):
        verdict = FALLBACK_MATCH
    elif not rows:
        verdict = SILENT_DROP_ACCEPTED if (fallback and fallback["type"] == "silent_drop") else SILENT_DROP_GAP
    elif _has_fabricated_concept(rows, ideal, is_technical):
        verdict = FABRICATED_CONCEPT
    else:
        verdict = WRONG_STRUCTURE

    return EntryVerdict(
        entry_id=entry["id"], category=entry["category"], is_requirement=is_requirement,
        is_technical=is_technical, verdict=verdict, actual_row_count=len(rows),
        actual_summary=_summarize_rows(rows), span_correct=span_ok,
    )


def evaluate_corpus(entries: list[dict]) -> PreservationReport:
    return PreservationReport(verdicts=[evaluate_entry(entry) for entry in entries])


def aggregate_metrics(report: PreservationReport, entries_by_id: dict[str, dict]) -> dict:
    """The ten metrics the Milestone 9B brief requires, each computed
    from its own clearly-scoped subset of verdicts -- never collapsed
    into one combined score. See each key's `definition` for the exact
    denominator.
    """
    verdicts = report.verdicts
    requirement_verdicts = [v for v in verdicts if v.is_requirement]
    technical_verdicts = [v for v in requirement_verdicts if v.is_technical]
    non_requirement_verdicts = [v for v in verdicts if not v.is_requirement]

    def _rate(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 3) if denominator else None

    # 1. Genuine requirement preservation recall: among real requirements,
    # how many produced >=1 row at all (any honest shape), regardless of
    # whether that shape was the ideal one.
    preserved = [v for v in requirement_verdicts if v.actual_row_count > 0]
    recall_any_trace = _rate(len(preserved), len(requirement_verdicts))

    # 2. Correctly structured technical requirements: full-credit
    # (IDEAL_MATCH) rate among technical requirements only.
    technical_ideal = [v for v in technical_verdicts if v.verdict == IDEAL_MATCH]
    technical_structure_rate = _rate(len(technical_ideal), len(technical_verdicts))

    # 3. Unknown-concept preservation: among entries whose ideal (or
    # fallback) outcome names a specific unresolved:<term> id, how many
    # actually produced that exact id (IDEAL_MATCH only -- a generic
    # placeholder fallback does NOT count here, since the whole point of
    # this metric is whether the SPECIFIC unknown concept survived).
    unresolved_target_ids = {"unresolved_concept", "unresolved_concepts", "mixed_concepts", "unresolved_alternative_group"}
    unresolved_entries = [
        v for v in requirement_verdicts
        if entries_by_id[v.entry_id]["ideal_outcome"]["type"] in unresolved_target_ids
        and any(cid.startswith("unresolved:") for cid in entries_by_id[v.entry_id]["ideal_outcome"].get("concept_ids", []))
    ]
    unresolved_preserved = [v for v in unresolved_entries if v.verdict == IDEAL_MATCH]
    unknown_concept_preservation_rate = _rate(len(unresolved_preserved), len(unresolved_entries))

    # 4. Unknown OR/AND structural correctness: among unresolved-concept
    # entries that are explicitly OR- or AND-structured (>=2 ids), the
    # same IDEAL_MATCH rate, isolated from the single-term case above.
    structural_entries = [v for v in unresolved_entries if entries_by_id[v.entry_id]["or_and_structure"] in ("or", "and_list")]
    structural_correct = [v for v in structural_entries if v.verdict == IDEAL_MATCH]
    unknown_structure_rate = _rate(len(structural_correct), len(structural_entries))

    # 5. Correct unparsed placeholder preservation: among entries whose
    # IDEAL or FALLBACK outcome is itself a placeholder shape, how many
    # landed on exactly that placeholder (IDEAL_MATCH when the ideal IS
    # the placeholder, or FALLBACK_MATCH when it's a declared fallback).
    placeholder_ideal_types = {"competency_placeholder", "alternative_group_with_unsafe_segment"}
    placeholder_fallback_types = {"unresolved_requirement_placeholder", "alternative_requirement_placeholder"}
    placeholder_entries = [
        v for v in requirement_verdicts
        if entries_by_id[v.entry_id]["ideal_outcome"]["type"] in placeholder_ideal_types
        or (entries_by_id[v.entry_id].get("acceptable_fallback") or {}).get("type") in placeholder_fallback_types
    ]
    placeholder_correct = [v for v in placeholder_entries if v.verdict in (IDEAL_MATCH, FALLBACK_MATCH)]
    placeholder_preservation_rate = _rate(len(placeholder_correct), len(placeholder_entries))

    # 6. Spurious requirement creation: raw count of rows produced for an
    # is_requirement=false entry -- these should never exist at all.
    spurious_entries = [v for v in non_requirement_verdicts if v.verdict == SPURIOUS_ROW]
    spurious_count = sum(v.actual_row_count for v in spurious_entries)

    # 7. Incorrect technology fabrication: count of entries (requirement
    # or not) where a REAL, wrong concept id was attached -- strictly
    # worse than a spurious NON-fabricating row, and tracked completely
    # separately per the brief's explicit instruction never to merge the
    # two into one number.
    fabrication_count = len([v for v in verdicts if v.verdict == FABRICATED_CONCEPT])

    # 8. Exact source-span correctness: among every entry that produced
    # at least one row, the fraction whose span exactly matches the
    # claim's true position in the wrapped text.
    span_checkable = [v for v in verdicts if v.span_correct is not None]
    span_correct = [v for v in span_checkable if v.span_correct]
    span_correctness_rate = _rate(len(span_correct), len(span_checkable))

    # 9. Silent-drop count: raw count of real requirements that produced
    # ZERO rows, split into corpus-accepted vs. flagged-as-a-real-gap --
    # never reported as one undifferentiated number.
    silent_drop_accepted = len([v for v in requirement_verdicts if v.verdict == SILENT_DROP_ACCEPTED])
    silent_drop_gap = len([v for v in requirement_verdicts if v.verdict == SILENT_DROP_GAP])

    # 10. Correctly excluded non-requirement prose: recall-style fraction
    # over is_requirement=false entries only.
    correctly_excluded = [v for v in non_requirement_verdicts if v.verdict == CORRECTLY_EXCLUDED]
    exclusion_rate = _rate(len(correctly_excluded), len(non_requirement_verdicts))

    verdict_counts = Counter(v.verdict for v in verdicts)

    return {
        "total_entries": len(verdicts),
        "total_requirement_entries": len(requirement_verdicts),
        "total_non_requirement_entries": len(non_requirement_verdicts),
        "verdict_counts": dict(verdict_counts),
        "metrics": {
            "1_genuine_requirement_preservation_recall": {
                "value": recall_any_trace,
                "numerator": len(preserved), "denominator": len(requirement_verdicts),
                "definition": "fraction of real requirements that produced >=1 JobRequirement row, of any honest shape",
            },
            "2_correctly_structured_technical_requirements": {
                "value": technical_structure_rate,
                "numerator": len(technical_ideal), "denominator": len(technical_verdicts),
                "definition": "fraction of technical requirements matching their ideal_outcome exactly (full structural credit)",
            },
            "3_unknown_concept_preservation": {
                "value": unknown_concept_preservation_rate,
                "numerator": len(unresolved_preserved), "denominator": len(unresolved_entries),
                "definition": "fraction of entries whose ideal outcome names a specific unresolved:<term> id that actually produced that exact id",
            },
            "4_unknown_or_and_structural_correctness": {
                "value": unknown_structure_rate,
                "numerator": len(structural_correct), "denominator": len(structural_entries),
                "definition": "of metric 3's entries that are OR- or AND-structured, fraction with the fully correct group/list structure",
            },
            "5_correct_unparsed_placeholder_preservation": {
                "value": placeholder_preservation_rate,
                "numerator": len(placeholder_correct), "denominator": len(placeholder_entries),
                "definition": "of entries whose ideal or accepted-fallback outcome is a non-fabricating placeholder, fraction that landed on exactly that placeholder",
            },
            "6_spurious_requirement_creation": {
                "value": spurious_count,
                "definition": "raw count of JobRequirement rows produced for an is_requirement=false entry (should always be 0)",
            },
            "7_incorrect_technology_fabrication": {
                "value": fabrication_count,
                "definition": "raw count of entries where a REAL, wrong concept id was attached -- kept separate from metric 6 and from any placeholder metric by design",
            },
            "8_exact_source_span_correctness": {
                "value": span_correctness_rate,
                "numerator": len(span_correct), "denominator": len(span_checkable),
                "definition": "of entries producing >=1 row, fraction whose source_span exactly matches the claim's true position in the wrapped text",
            },
            "9_silent_drop_count": {
                "value": {"accepted_by_corpus": silent_drop_accepted, "flagged_as_gap": silent_drop_gap},
                "definition": "raw counts of real requirements producing zero rows, split by whether this corpus's own annotation accepts that as non-failure",
            },
            "10_correctly_excluded_non_requirement_prose": {
                "value": exclusion_rate,
                "numerator": len(correctly_excluded), "denominator": len(non_requirement_verdicts),
                "definition": "fraction of is_requirement=false entries (headings/prose) that correctly produced zero rows for that exact text",
            },
        },
    }
