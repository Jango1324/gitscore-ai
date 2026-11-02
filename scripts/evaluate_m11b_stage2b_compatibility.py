"""Milestone 11-B Stage 2B -- Path A offline compatibility harness.

Evaluation-only, additive, read-only against production code and
against every corpus it reads -- see
`docs/evaluation/MILESTONE_11_B_STAGE_2A_SHADOW_INTEGRATION.md`'s own
Phase 3 ("Option A -- Offline evaluation-only runner... the smallest
safe option") for the architecture this script implements.

For every raw job-description text drawn from the project's EXISTING,
already-committed evaluation fixtures (never new, never-before-seen
text -- see `_load_all_fixture_texts()` below for the exact seven
sources), this script:

1. Runs the real, UNMODIFIED `parse_job_description_with_diagnostics()`
   -- the authoritative parser, never touched by this script.
2. Converts every resulting `JobRequirement`/`UnparsedClaim` into a
   `Qualification` via `jobs.parsing.qualification_adapter` (Path A).
3. Projects each `Qualification` back via `project_qualification()`.
4. Compares the reconstructed `JobRequirement`/`UnparsedClaim` against
   the original on the CORE PRESERVED FIELD SET (`original_text`,
   `necessity`, `concept_id`, `alternative_concept_ids`,
   `github_observability`, `parser_confidence`, `source_span` for a
   requirement; `text`, `source_span` for an `UnparsedClaim`) -- a
   mismatch here is a genuine ADAPTER BUG and must be reported with
   exact source location and affected fields.
5. SEPARATELY tallies the two KNOWN, documented, by-design structural
   gaps (`importance`, `category`'s raw string) -- see
   `qualification_adapter.py`'s own module docstring -- never counted
   as a core-field mismatch, always reported with exact counts so
   nothing is silently swept in either direction.
6. Distinguishes an `UnsupportedAdapterCase` (the adapter correctly
   refused to construct a `Qualification` at all -- e.g. a hand-built
   `JobRequirement` with no `source_span`) from an actual semantic
   mismatch (the adapter constructed something, but the round trip
   does not match) -- two different findings, reported separately,
   per this milestone's own Phase 2 instruction.

Writes `evaluation/reports/m11b_stage2b_compatibility_report.json`.
Never calls any network/LLM service; never reroutes the production
parser; never modifies `evaluation/gold`/`evaluation/gold_v1_1` or any
other committed fixture -- every file under `evaluation/` is opened
read-only.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib.loaders import JOBS_DIR, list_job_ids, load_job  # noqa: E402

from gitscore.api.serialization import _interpretation_status, serialize_requirement_match, serialize_unparsed_claim  # noqa: E402
from gitscore.evidence.profile import build_candidate_evidence_profile  # noqa: E402
from gitscore.jobs.models import JobRequirement  # noqa: E402
from gitscore.jobs.parsing.parser import (  # noqa: E402
    UnparsedClaim,
    parse_job_description_with_diagnostics,
)
from gitscore.jobs.parsing.qualification import project_qualification  # noqa: E402
from gitscore.jobs.parsing.qualification_adapter import (  # noqa: E402
    UnsupportedAdapterCase,
    adapt_job_requirement,
    job_requirement_from_adapted,
    qualification_from_unparsed_claim,
)
from gitscore.matching.engine import match_requirement  # noqa: E402

REPORT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11b_stage2b_compatibility_report.json"

_CORE_REQUIREMENT_FIELDS = (
    "original_text",
    "necessity",
    "concept_id",
    "alternative_concept_ids",
    "github_observability",
    "parser_confidence",
    "source_span",
)

# An empty candidate evidence profile -- used only to run the SAME
# `match_requirement()` the real matcher already calls, identically,
# against the original and the reconstructed requirement, so a
# "scoring-denominator difference" is a MEASURED fact (same
# `MatchStatus` or not), never inferred from field equality alone.
_EMPTY_CANDIDATE_PROFILE = build_candidate_evidence_profile("stage2b-harness", [], [], [])


def _load_all_fixture_texts() -> list[tuple[str, str, str]]:
    """Every raw job-description-shaped text drawn from the project's
    SEVEN existing, already-committed evaluation sources -- never a
    newly-authored sentence. Returns `(source_label, fixture_id, text)`
    tuples. See each block below for exactly which committed file is
    read and why its own field holds raw description text.
    """
    texts: list[tuple[str, str, str]] = []

    # 1. evaluation/jobs/*.json -- the 15 raw postings `evaluation/gold`
    #    and `evaluation/gold_v1_1` are both scored against (frozen gold
    #    itself holds no raw text, only expected_requirements).
    for job_id in list_job_ids():
        job = load_job(job_id)
        texts.append(("gold_jobs", job_id, job["raw_text"]))

    # 2. evaluation/m10/corpus.json -- the two real M10A postings
    #    (SOTI/Manulife), raw text in a sibling evaluation/m10/source/*.txt file.
    m10_corpus = json.loads((REPO_ROOT / "evaluation" / "m10" / "corpus.json").read_text(encoding="utf-8"))
    for posting in m10_corpus["postings"]:
        source_path = REPO_ROOT / posting["source_file"]
        texts.append(("m10a_realworld", posting["id"], source_path.read_text(encoding="utf-8")))

    # 3. evaluation/m9b/corpus.json -- per-claim sentences (M9B preservation).
    m9b_corpus = json.loads((REPO_ROOT / "evaluation" / "m9b" / "corpus.json").read_text(encoding="utf-8"))
    for entry in m9b_corpus["entries"]:
        texts.append(("m9b_preservation", entry["id"], entry["source_text"]))

    # 4. evaluation/m10d/alternative_controls.json -- per-claim sentences
    #    (M10D alternative-requirement semantics).
    m10d_corpus = json.loads((REPO_ROOT / "evaluation" / "m10d" / "alternative_controls.json").read_text(encoding="utf-8"))
    for control in m10d_corpus["controls"]:
        texts.append(("m10d_alternatives", control["id"], control["text"]))

    # 5. evaluation/m11a2/line_wrap_controls.json -- BOTH the unwrapped
    #    and wrapped variant of each control are genuinely distinct
    #    existing fixture texts the current parser treats differently.
    m11a2_corpus = json.loads((REPO_ROOT / "evaluation" / "m11a2" / "line_wrap_controls.json").read_text(encoding="utf-8"))
    for control in m11a2_corpus["controls"]:
        if control["unwrapped_text"] is not None:
            texts.append(("m11a2_line_wrap", f"{control['id']}:unwrapped", control["unwrapped_text"]))
        if control["wrapped_text"] is not None:
            texts.append(("m11a2_line_wrap", f"{control['id']}:wrapped", control["wrapped_text"]))

    # 6. evaluation/m11/corpus.json -- the 9 held-out M11 postings.
    m11_corpus = json.loads((REPO_ROOT / "evaluation" / "m11" / "corpus.json").read_text(encoding="utf-8"))
    for posting in m11_corpus["postings"]:
        texts.append(("m11_generalization", posting["id"], posting["raw_text"]))

    # 7. evaluation/m11b/structured_qualification_controls.json -- the 21
    #    Stage 1 development controls, run through the REAL parser here
    #    (not through the Qualification model directly -- this script
    #    only ever exercises Path A's own JobRequirement/UnparsedClaim
    #    round trip, never the hand-annotated Qualification shape those
    #    controls describe).
    m11b_corpus = json.loads((REPO_ROOT / "evaluation" / "m11b" / "structured_qualification_controls.json").read_text(encoding="utf-8"))
    for control in m11b_corpus["controls"]:
        texts.append(("m11b_development", control["id"], control["text"]))

    return texts


def _requirement_mismatches(original: JobRequirement, reconstructed: JobRequirement) -> dict:
    mismatches = {}
    for field in _CORE_REQUIREMENT_FIELDS:
        original_value = getattr(original, field)
        reconstructed_value = getattr(reconstructed, field)
        if original_value != reconstructed_value:
            mismatches[field] = {"original": repr(original_value), "reconstructed": repr(reconstructed_value)}
    return mismatches


def _evaluate_requirement(source_label: str, fixture_id: str, requirement: JobRequirement) -> dict:
    row = {
        "source": source_label,
        "fixture_id": fixture_id,
        "text": requirement.original_text,
        "span": [requirement.source_span.start, requirement.source_span.end] if requirement.source_span else None,
    }
    try:
        adapted = adapt_job_requirement(requirement)
    except UnsupportedAdapterCase as exc:
        row["outcome"] = "unsupported_adapter_case"
        row["reason"] = exc.reason
        row["detail"] = exc.detail
        return row

    try:
        reconstructed = job_requirement_from_adapted(adapted)
    except UnsupportedAdapterCase as exc:
        row["outcome"] = "unsupported_adapter_case"
        row["reason"] = exc.reason
        row["detail"] = exc.detail
        return row

    # 1. Full dataclass equality -- the corrected acceptance bar.
    row["full_object_equality"] = reconstructed == requirement

    # 2. Core-field equality -- reported separately, per instruction,
    #    even though it is now implied by (1) whenever (1) holds.
    core_mismatches = _requirement_mismatches(requirement, reconstructed)
    row["core_field_equality"] = not core_mismatches
    if core_mismatches:
        row["core_mismatches"] = core_mismatches

    # 3. importance/category equality -- explicit, never silently
    #    folded into "core" (these were the two previously-disclosed
    #    gaps; now expected to match exactly, same as every other
    #    field, via the AdaptedQualification envelope).
    row["importance_equality"] = requirement.importance == reconstructed.importance
    row["category_equality"] = requirement.category == reconstructed.category
    if not row["importance_equality"]:
        row["importance_mismatch"] = {"original": requirement.importance.name, "reconstructed": reconstructed.importance.name}
    if not row["category_equality"]:
        row["category_mismatch"] = {"original": requirement.category, "reconstructed": reconstructed.category}

    # 4. Placeholder-category identity -- a named, explicit check for
    #    the two existing non-fabricating placeholder categories, since
    #    this was the category whose collapse previously changed
    #    `interpretation_status` silently.
    is_placeholder = requirement.category in ("unresolved_requirement", "alternative_requirement")
    row["is_placeholder_category"] = is_placeholder
    if is_placeholder:
        row["placeholder_identity_preserved"] = reconstructed.category == requirement.category

    # 5. Serialized public output equality, for BOTH possible match
    #    outcomes this requirement could reach (NOT_OBSERVED when it
    #    has no candidate evidence; NOT_ASSESSABLE is exercised
    #    separately below for the placeholder-category check since
    #    MatchStatus itself does not change with legacy field values).
    match_original = match_requirement(requirement, _EMPTY_CANDIDATE_PROFILE)
    match_reconstructed = match_requirement(reconstructed, _EMPTY_CANDIDATE_PROFILE)
    row["scoring_denominator_equal"] = match_original.status == match_reconstructed.status
    out_original = serialize_requirement_match(match_original)
    out_reconstructed = serialize_requirement_match(match_reconstructed)
    row["serialized_equality"] = out_original == out_reconstructed
    if is_placeholder:
        row["interpretation_status_original"] = _interpretation_status(match_original)
        row["interpretation_status_reconstructed"] = _interpretation_status(match_reconstructed)

    row["outcome"] = "full_match" if row["full_object_equality"] else "reconstruction_mismatch"
    return row


def _evaluate_unparsed_claim(source_label: str, fixture_id: str, claim: UnparsedClaim) -> dict:
    row = {
        "source": source_label,
        "fixture_id": fixture_id,
        "text": claim.text,
        "span": [claim.source_span.start, claim.source_span.end],
    }
    try:
        qualification = qualification_from_unparsed_claim(claim)
    except UnsupportedAdapterCase as exc:
        row["outcome"] = "unsupported_adapter_case"
        row["reason"] = exc.reason
        row["detail"] = exc.detail
        return row

    result = project_qualification(qualification)
    reconstructed = result.unparsed_claim
    row["full_object_equality"] = reconstructed is not None and reconstructed == claim
    row["core_field_equality"] = row["full_object_equality"]  # UnparsedClaim has only these 2 fields
    row["serialized_equality"] = reconstructed is not None and serialize_unparsed_claim(claim) == serialize_unparsed_claim(reconstructed)
    if not row["full_object_equality"]:
        row["core_mismatches"] = {"unparsed_claim": {"original": repr(claim), "reconstructed": repr(reconstructed)}}

    row["outcome"] = "full_match" if row["full_object_equality"] else "reconstruction_mismatch"
    return row


def main() -> None:
    texts = _load_all_fixture_texts()

    requirement_rows: list[dict] = []
    unparsed_rows: list[dict] = []
    fixtures_processed = 0

    for source_label, fixture_id, text in texts:
        if not text.strip():
            continue
        fixtures_processed += 1
        parsed = parse_job_description_with_diagnostics(text)
        for requirement in parsed.profile.requirements:
            requirement_rows.append(_evaluate_requirement(source_label, fixture_id, requirement))
        for claim in parsed.unparsed_claims:
            unparsed_rows.append(_evaluate_unparsed_claim(source_label, fixture_id, claim))

    def _count(rows: list[dict], key: str) -> int:
        return sum(1 for r in rows if r.get(key) is True)

    def _count_outcome(rows: list[dict], outcome: str) -> int:
        return sum(1 for r in rows if r["outcome"] == outcome)

    non_unsupported_requirements = [r for r in requirement_rows if r["outcome"] != "unsupported_adapter_case"]
    placeholder_rows = [r for r in requirement_rows if "placeholder_identity_preserved" in r]

    report = {
        "fixtures_processed": fixtures_processed,
        "requirements": {
            "total": len(requirement_rows),
            "full_object_equality": _count(non_unsupported_requirements, "full_object_equality"),
            "core_field_equality": _count(non_unsupported_requirements, "core_field_equality"),
            "serialized_equality": _count(non_unsupported_requirements, "serialized_equality"),
            "scoring_denominator_equal": _count(non_unsupported_requirements, "scoring_denominator_equal"),
            "unsupported_adapter_case": _count_outcome(requirement_rows, "unsupported_adapter_case"),
            "reconstruction_mismatch": _count_outcome(requirement_rows, "reconstruction_mismatch"),
            "placeholder_category_total": len(placeholder_rows),
            "placeholder_identity_preserved": _count(placeholder_rows, "placeholder_identity_preserved"),
            "mismatches": [r for r in requirement_rows if r["outcome"] == "reconstruction_mismatch"],
            "unsupported_cases": [r for r in requirement_rows if r["outcome"] == "unsupported_adapter_case"],
        },
        "unparsed_claims": {
            "total": len(unparsed_rows),
            "full_object_equality": _count(unparsed_rows, "full_object_equality"),
            "serialized_equality": _count(unparsed_rows, "serialized_equality"),
            "unsupported_adapter_case": _count_outcome(unparsed_rows, "unsupported_adapter_case"),
            "reconstruction_mismatch": _count_outcome(unparsed_rows, "reconstruction_mismatch"),
            "mismatches": [r for r in unparsed_rows if r["outcome"] == "reconstruction_mismatch"],
            "unsupported_cases": [r for r in unparsed_rows if r["outcome"] == "unsupported_adapter_case"],
        },
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    req = report["requirements"]
    unp = report["unparsed_claims"]
    print(f"Fixtures processed: {fixtures_processed}")
    print(f"Requirements: {req['total']} total ({req['unsupported_adapter_case']} unsupported-adapter-case, excluded from the ratios below)")
    denom = req["total"] - req["unsupported_adapter_case"]
    print(f"  full_object_equality:      {req['full_object_equality']}/{denom}")
    print(f"  core_field_equality:       {req['core_field_equality']}/{denom}")
    print(f"  serialized_equality:       {req['serialized_equality']}/{denom}")
    print(f"  scoring_denominator_equal: {req['scoring_denominator_equal']}/{denom}")
    print(f"  reconstruction_mismatch:   {req['reconstruction_mismatch']}")
    print(f"  placeholder_identity_preserved: {req['placeholder_identity_preserved']}/{req['placeholder_category_total']}")
    print(f"UnparsedClaims: {unp['total']} total ({unp['unsupported_adapter_case']} unsupported-adapter-case)")
    print(f"  full_object_equality: {unp['full_object_equality']}/{unp['total'] - unp['unsupported_adapter_case']}")
    print(f"  serialized_equality:  {unp['serialized_equality']}/{unp['total'] - unp['unsupported_adapter_case']}")
    print(f"  reconstruction_mismatch: {unp['reconstruction_mismatch']}")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
