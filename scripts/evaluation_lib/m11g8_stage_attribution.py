"""Milestone 11-G8 Phase 2 -- per-stage failure attribution for every
missing gold competency across the two preserved, already-inspected
corpora (M11-F's 85-control technical_competency set, M11-G5's
57-control technical_competency set).

Evaluation-only. Instruments the existing offline pipeline by calling
its REAL, already-shipped internal functions directly, in the SAME
order the real `extract_competency_qualifications_v2` already calls
them -- never re-implementing or changing any decision. This is
read-only inspection of intermediate state (which existing decline
reason "no_competency_language" currently collapses two genuinely
different causes into), not a new algorithm.

Stage taxonomy (mission-specified):
  A. Source segment discarded by segmentation (never admitted, never
     recovered by M11-G4's recovery pass).
  B. Segment survived; `_QUALIFYING_INTENT_V2` (the qualifying-intent
     gate) rejected it before vocabulary matching was even attempted.
  C. Intent gate passed; `find_competency_mentions_v2` found NO
     canonical/alias term at all.
  D. A tag WAS found, but not gold's expected one (wrong tag, or an
     incomplete multi-tag representation).
  E. Vocabulary matched; a downstream content-validation gate
     (negation / narrative-cue / responsibility-lead / missing-contract
     OR-group safety) declined the extraction anyway.
  F. Projection discarded/transformed a valid result -- confirmed
     architecturally NOT APPLICABLE to tag-level recall:
     `project_qualification()` only ever decides JobRequirement-vs-
     UnparsedClaim ROUTING; it never reads or alters
     `Qualification.normalized_reference.competency_tag`, so it cannot
     be the cause of a tag-level false negative. Reported as 0 by
     construction, not by absence of looking.
  G. Not applicable within the TAGGABLE subset by definition (gold
     already assigned a real 17-tag-vocabulary tag) -- reported
     separately for the UNTAGGABLE subset, where it legitimately means
     "gold itself declared no tag exists for this competency."
  H. Another explicitly documented cause (catch-all; reported with its
     own decline reason string if any row lands here unexpectedly).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation_lib"))

from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.competency_extraction import (  # noqa: E402
    DeclinedExtraction,
    _NEGATION_PATTERNS,
    _QUALIFYING_INTENT_V2,
    _RESPONSIBILITY_LEAD,
    _stemmed_text_v2,
    _STEMMED_ACTIVE_ALIAS_PATTERNS_V2,
    _STEMMED_COMPETENCY_PATTERNS_V2,
    extract_competency_qualifications_v2,
    find_competency_mentions_v2,
)
from gitscore.jobs.parsing.narrative import contains_narrative_cue  # noqa: E402
from gitscore.jobs.parsing.qualification_admission_recovery import (  # noqa: E402
    recover_unadmitted_qualification_claims,
)
from gitscore.jobs.parsing.segmentation import segment_description  # noqa: E402


def _was_admitted_or_recovered(full_text: str, claim_text: str) -> bool:
    """Category A check: did this exact sentence ever become a `Claim`
    at all, via EITHER the real segmenter or M11-G4's real recovery
    pass -- reusing both functions verbatim, never re-implementing
    their own admission logic. Substring match in both directions
    (not exact set equality) because the real sentence splitter may
    trim/merge whitespace slightly differently than gold's own
    annotated span boundaries."""
    admitted = [c.text for c in segment_description(full_text)]
    if any(claim_text in t or t in claim_text for t in admitted):
        return True
    recovered = [r.claim.text for r in recover_unadmitted_qualification_claims(full_text)]
    return any(claim_text in t or t in claim_text for t in recovered)


def attribute_one_control(control: dict, full_text: str | None) -> dict:
    """Returns the stage attribution for ONE taggable technical_competency
    control whose gold expected tag was NOT recovered (a confirmed
    tag-level FN), by calling the real pipeline's own internal
    functions in their real order."""
    text = control["text"]
    expected_tag = control.get("expected_competency_tag")
    sibling_tags = set(control.get("sibling_tags", []) or [])

    admitted = True
    if full_text is not None:
        admitted = _was_admitted_or_recovered(full_text, text)
    if not admitted:
        return {"stage": "A", "detail": "never admitted by segmentation, never recovered by M11-G4"}

    intent_match = _QUALIFYING_INTENT_V2.search(text) is not None
    if not intent_match:
        return {"stage": "B", "detail": "_QUALIFYING_INTENT_V2 gate rejected before vocabulary matching"}

    tag_relations = find_competency_mentions_v2(text)
    if not tag_relations:
        return {"stage": "C", "detail": "intent gate passed; zero canonical/alias terms matched"}

    found_tags = set(tag_relations.keys())
    accepted = ({expected_tag} if expected_tag else set()) | sibling_tags
    if found_tags and not (found_tags & accepted):
        return {
            "stage": "D",
            "detail": f"wrong tag(s) found: {sorted(found_tags)!r}, expected one of {sorted(accepted)!r}",
        }

    # A tag in `accepted` WAS found by find_competency_mentions_v2 --
    # the only way this is still a confirmed FN is a downstream
    # content-validation decline. Re-run the exact checks
    # extract_competency_qualifications_v2 itself runs, in its own
    # real order, to name which one fired.
    if any(pattern.search(text) for pattern in _NEGATION_PATTERNS):
        return {"stage": "E", "detail": "negation"}
    if contains_narrative_cue(text):
        return {"stage": "E", "detail": "narrative_cue"}
    if _RESPONSIBILITY_LEAD.match(text.strip()):
        return {"stage": "E", "detail": "responsibility_lead"}

    span = SourceSpan(0, len(text))
    result = extract_competency_qualifications_v2(text, span)
    if isinstance(result, DeclinedExtraction):
        if result.reason == "missing_contract":
            return {"stage": "E", "detail": "missing_contract (OR-group representation safety)"}
        return {"stage": "H", "detail": f"unexpected decline reason: {result.reason}"}

    produced_tags = {
        q.normalized_reference.competency_tag for q in result if q.normalized_reference is not None
    }
    if produced_tags & accepted:
        return {"stage": "NONE", "detail": "expected tag WAS produced -- this control is not actually an FN"}
    return {"stage": "H", "detail": f"produced tags {sorted(produced_tags)!r} did not match {sorted(accepted)!r} for an unexplained reason"}


def _load_posting_body(path: Path) -> str:
    """Mirrors `m11g5_phase4_run_comparison.load_posting_body`'s own
    header-stripping convention (Company/Title/URL/Domain/Collected +
    blank line, then the body) -- reused logic, not re-derived, since
    both G5 and F's source files share the identical header format."""
    raw = path.read_text(encoding="utf-8")
    lines = raw.split("\n")
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "" and i > 0 and lines[i - 1].startswith("Collected:"):
            body_start = i + 1
            break
    return "\n".join(lines[body_start:]).strip("\n")


def _build_g5_body_loader(source_dir: Path):
    cache: dict[str, str] = {}

    def loader(control: dict) -> str | None:
        posting = control.get("posting")
        if posting is None:
            return None
        if posting not in cache:
            cache[posting] = _load_posting_body(source_dir / posting)
        return cache[posting]

    return loader


def _build_m11f_body_loader(source_dir: Path):
    bodies = {p.name: _load_posting_body(p) for p in source_dir.glob("*.txt")}

    def loader(control: dict) -> str | None:
        text = control["text"]
        for body in bodies.values():
            if text in body:
                return body
        return None

    return loader


def _vocab_match_ignoring_intent(text: str) -> set[str]:
    """Replicates `find_competency_mentions_v2`'s own POST-intent-gate
    logic exactly (same stemmed patterns, same precedence), skipping
    ONLY the `_QUALIFYING_INTENT_V2` check -- used exclusively for the
    Phase 2 'is a Category-B row ALSO blocked downstream' check below.
    Never used to change any real decision; read-only diagnostic."""
    stemmed = _stemmed_text_v2(text)
    found: set[str] = set()
    for tag, pattern in _STEMMED_COMPETENCY_PATTERNS_V2:
        if pattern.search(stemmed):
            found.add(tag)
    for tag, pattern, _relation in _STEMMED_ACTIVE_ALIAS_PATTERNS_V2:
        if pattern.search(stemmed):
            found.add(tag)
    return found


def _e_stage_would_block(text: str) -> bool:
    """Replicates the three content-validation checks
    `extract_competency_qualifications_v2` runs immediately after a
    successful vocabulary match (negation / narrative-cue /
    responsibility-lead) -- used exclusively for the Phase 2 'if
    Category C's vocabulary match were hypothetically fixed, would a
    downstream safeguard block it anyway' check below. Does not
    include the `missing_contract` OR-group check, which depends on
    the SPECIFIC tag(s) a real alias match would produce and cannot be
    evaluated hypothetically without assuming which alias would be
    added -- disclosed, not silently approximated."""
    if any(p.search(text) for p in _NEGATION_PATTERNS):
        return True
    if contains_narrative_cue(text):
        return True
    if _RESPONSIBILITY_LEAD.match(text.strip()):
        return True
    return False


def double_blocking_analysis(gold_rows: list[dict], gold_lookup: dict[str, dict]) -> dict:
    """For every Category-B row: would vocabulary matching ALSO
    succeed if the intent gate were bypassed (genuinely recoverable by
    an intent-gate-only fix), or is it double-blocked? For every
    Category-C row: would a hypothetical successful vocabulary match
    ALSO be blocked by a downstream E-stage safeguard (meaning the
    47-count ceiling is not achievable even with perfect aliases), or
    does it pass through cleanly?"""
    b_only_intent_blocked = []
    b_double_blocked = []
    for r in gold_rows:
        if r["stage"] != "B":
            continue
        control = gold_lookup[r["id"]]
        text = control["text"]
        expected = control.get("expected_competency_tag")
        accepted = ({expected} if expected else set()) | set(control.get("sibling_tags", []) or [])
        found = _vocab_match_ignoring_intent(text)
        if found & accepted:
            b_only_intent_blocked.append(r["id"])
        else:
            b_double_blocked.append(r["id"])

    c_clears_e = []
    c_blocked_by_e = []
    for r in gold_rows:
        if r["stage"] != "C":
            continue
        control = gold_lookup[r["id"]]
        if _e_stage_would_block(control["text"]):
            c_blocked_by_e.append(r["id"])
        else:
            c_clears_e.append(r["id"])

    return {
        "b_recoverable_by_intent_fix_alone": b_only_intent_blocked,
        "b_double_blocked_needs_vocab_too": b_double_blocked,
        "n_b_recoverable_by_intent_fix_alone": len(b_only_intent_blocked),
        "n_b_double_blocked": len(b_double_blocked),
        "c_would_clear_downstream_if_vocab_fixed": c_clears_e,
        "c_would_still_be_blocked_by_e": c_blocked_by_e,
        "n_c_would_clear_downstream": len(c_clears_e),
        "n_c_would_still_be_blocked_by_e": len(c_blocked_by_e),
    }


def run_corpus(name: str, gold_path: Path, source_dir: Path | None, load_body) -> dict:
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    tech = [c for c in gold["controls"] if c.get("qualification_kind") == "technical_competency"
            or c.get("text_category") == "technical_competency"]
    taggable = [c for c in tech if c.get("expected_competency_tag")]
    untaggable = [c for c in tech if not c.get("expected_competency_tag")]

    rows = []
    stage_counts: dict[str, int] = {}
    body_lookup_failures = []
    for control in taggable:
        full_text = load_body(control) if load_body else None
        if full_text is None:
            body_lookup_failures.append(control["id"])
        attribution = attribute_one_control(control, full_text)
        stage = attribution["stage"]
        if stage != "NONE":
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        rows.append({"id": control["id"], "expected_tag": control.get("expected_competency_tag"),
                     "sibling_tags": control.get("sibling_tags", []), **attribution})

    gold_lookup = {c["id"]: c for c in taggable}
    double_blocking = double_blocking_analysis(rows, gold_lookup)

    return {
        "corpus": name,
        "n_technical_competency_total": len(tech),
        "n_taggable": len(taggable),
        "n_untaggable_category_g": len(untaggable),
        "untaggable_ids": [c["id"] for c in untaggable],
        "body_lookup_failures": body_lookup_failures,
        "stage_counts_among_confirmed_fn": stage_counts,
        "n_confirmed_fn": sum(stage_counts.values()),
        "n_confirmed_tp_not_fn": sum(1 for r in rows if r["stage"] == "NONE"),
        "double_blocking_analysis": double_blocking,
        "rows": rows,
    }


def main() -> None:
    m11g5_path = REPO_ROOT / "evaluation" / "m11g5" / "holdout_annotations.json"
    m11f_path = REPO_ROOT / "evaluation" / "m11f" / "holdout_annotations.json"
    m11g5_source = REPO_ROOT / "evaluation" / "m11g5" / "source"
    m11f_source = REPO_ROOT / "evaluation" / "m11f" / "source"

    g5_result = run_corpus("m11g5", m11g5_path, m11g5_source, _build_g5_body_loader(m11g5_source))
    f_result = run_corpus("m11f", m11f_path, m11f_source, _build_m11f_body_loader(m11f_source))

    out = {"m11g5": g5_result, "m11f": f_result}
    out_path = REPO_ROOT / "evaluation" / "reports" / "m11g8_stage_attribution.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"M11-G5: {g5_result['n_confirmed_fn']} confirmed FN, stage counts: {g5_result['stage_counts_among_confirmed_fn']}")
    print(f"M11-F:  {f_result['n_confirmed_fn']} confirmed FN, stage counts: {f_result['stage_counts_among_confirmed_fn']}")
    n_b_intent_only = g5_result["double_blocking_analysis"]["n_b_recoverable_by_intent_fix_alone"] + \
        f_result["double_blocking_analysis"]["n_b_recoverable_by_intent_fix_alone"]
    n_b_double = g5_result["double_blocking_analysis"]["n_b_double_blocked"] + \
        f_result["double_blocking_analysis"]["n_b_double_blocked"]
    n_c_clears = g5_result["double_blocking_analysis"]["n_c_would_clear_downstream"] + \
        f_result["double_blocking_analysis"]["n_c_would_clear_downstream"]
    n_c_blocked = g5_result["double_blocking_analysis"]["n_c_would_still_be_blocked_by_e"] + \
        f_result["double_blocking_analysis"]["n_c_would_still_be_blocked_by_e"]
    print(f"Combined B double-blocking: recoverable-by-intent-fix-alone={n_b_intent_only}, double-blocked={n_b_double}")
    print(f"Combined C downstream-clearance: would-clear={n_c_clears}, would-still-be-blocked-by-E={n_c_blocked}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
