"""Milestone 11-G20 -- false-qualification admission: research-only tracing,
gold mapping, metrics and OFFLINE policy simulation.

Nothing here is imported by `src/gitscore`. Production code is never
modified; every decision the v13 parser makes is obtained by calling the
REAL production functions (`segment_description`'s helpers,
`resolve_necessity_hint`, `infer_necessity`, `classify_alternative_claim`,
`_requirements_from_claim`, `deduplicate_requirements`). The only
replicated code is the ~40-line `segment_description()` LOOP and the
~20-line `_parse()` loop, so candidate policies can hook them; with
`POLICY_V13` (no hooks) the replica is asserted equal to production
`parse_job_description_with_diagnostics()` on every corpus
(`fidelity_check`, and `tests/test_m11g20_false_qualification_admission.py`).
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gitscore.assessment import assess_job  # noqa: E402
from gitscore.concepts.registry import default_registry  # noqa: E402
from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing import segmentation as seg  # noqa: E402
from gitscore.jobs.parsing.alternatives import classify_alternative_claim  # noqa: E402
from gitscore.jobs.parsing.dedup import deduplicate_requirements  # noqa: E402
from gitscore.jobs.parsing.narrative import contains_narrative_cue  # noqa: E402
from gitscore.jobs.parsing.necessity import _has_local_marker, infer_necessity, resolve_necessity_hint  # noqa: E402
from gitscore.jobs.parsing.parser import (  # noqa: E402
    JOB_DESCRIPTION_PARSER_VERSION,
    UnparsedClaim,
    _requirements_from_claim,
    parse_job_description_with_diagnostics,
)
from gitscore.jobs.profile import JobRequirementProfile  # noqa: E402
from gitscore.jobs.types import Necessity  # noqa: E402
from gitscore.matching import MatchStatus, match_job  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402

CONTROLS = {
    "dev": REPO_ROOT / "evaluation" / "m11g20" / "admission_controls_dev.json",
    "holdout": REPO_ROOT / "evaluation" / "m11g20" / "admission_controls_holdout.json",
}
FREEZES = {
    "dev": REPO_ROOT / "evaluation" / "m11g20" / "controls_dev_hash_freeze.json",
    "holdout": REPO_ROOT / "evaluation" / "m11g20" / "controls_holdout_hash_freeze.json",
}
QUALIFYING_SECTIONS = ("REQUIRED", "PREFERRED")


# ---------------------------------------------------------------------------------------------
# Policy hooks
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Policy:
    """Offline policy. Every hook defaults to v13 behaviour.

    heading(line, content, prod_kind) -> _SectionKind | None
    paragraph_reset: end a bulleted list section at a blank-line gap followed by un-bulleted prose
    admit(text, section_kind, doc_has_heading, hint) -> (decision, reason)
        decision in {"keep", "decline"}
    necessity(text, section_kind, prod_necessity) -> Necessity | None
    rows(text, rows) -> rows
    """

    name: str
    heading: Callable | None = None
    paragraph_reset: bool = False
    admit: Callable | None = None
    necessity: Callable | None = None
    rows: Callable | None = None
    description: str = ""


POLICY_V13 = Policy("v13", description="production parser v13 (replica, no hooks)")


# ---------------------------------------------------------------------------------------------
# Replica of segment_description()'s loop (helpers are the REAL production functions)
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class RClaim:
    text: str
    start: int
    end: int
    necessity_hint: Necessity | None
    section_kind: str | None


def _classify(policy: Policy, line: str, content: str):
    kind = seg._classify_heading_line(line, content)
    if policy.heading is not None:
        kind = policy.heading(line, content, kind)
    return kind


def segment(description: str, policy: Policy) -> tuple[RClaim, ...]:
    claims: list[RClaim] = []
    current_kind = None
    last_content_bulleted = False
    last_block_end = None
    line_matches = list(re.finditer(r"[^\r\n]+", description))
    i = 0
    while i < len(line_matches):
        line_match = line_matches[i]
        line = line_match.group()
        content_span = seg._line_content_span(line, line_match.start())
        if content_span is None:
            i += 1
            continue
        content_start, content_end = content_span
        content = description[content_start:content_end]

        classified = _classify(policy, line, content)
        if classified is not None:
            current_kind = classified
            last_content_bulleted = False
            last_block_end = None
            i += 1
            continue
        if current_kind is seg._SectionKind.SKIP:
            i += 1
            continue

        is_bulleted = seg._BULLET_PREFIX.match(line) is not None
        if (policy.paragraph_reset and current_kind in (seg._SectionKind.REQUIRED, seg._SectionKind.PREFERRED)
                and not is_bulleted and last_content_bulleted and last_block_end is not None
                and seg._is_paragraph_gap(description, last_block_end, content_start)):
            current_kind = seg._SectionKind.UNKNOWN

        block_end = content_end
        j = i + 1
        while j < len(line_matches) and seg._ends_incomplete(description[content_start:block_end]):
            next_match = line_matches[j]
            next_line = next_match.group()
            next_span = seg._line_content_span(next_line, next_match.start())
            if next_span is None:
                break
            next_content_start, next_content_end = next_span
            if seg._BULLET_PREFIX.match(next_line) is not None:
                break
            if _classify(policy, next_line, description[next_content_start:next_content_end]) is not None:
                break
            if seg._is_paragraph_gap(description, block_end, next_content_start):
                break
            block_end = next_content_end
            j += 1
        content = description[content_start:block_end]

        if current_kind in (seg._SectionKind.UNKNOWN, seg._SectionKind.LEARNING):
            hint = None
        else:
            hint = seg._SECTION_NECESSITY_HINT.get(current_kind, Necessity.REQUIRED)
        in_recognized = current_kind in (seg._SectionKind.REQUIRED, seg._SectionKind.PREFERRED,
                                         seg._SectionKind.RESPONSIBILITY)
        kind_name = current_kind.name if current_kind is not None else None
        for s, e in seg._split_sentences(content, description, content_start):
            sentence = description[s:e]
            if not in_recognized and not seg._looks_like_requirement(sentence):
                continue
            claims.append(RClaim(sentence, s, e, hint, kind_name))
        last_content_bulleted = is_bulleted
        last_block_end = block_end
        i = j
    return tuple(claims)


def doc_has_heading(description: str, policy: Policy) -> bool:
    for m in re.finditer(r"[^\r\n]+", description):
        span = seg._line_content_span(m.group(), m.start())
        if span is not None and _classify(policy, m.group(), description[span[0]:span[1]]) is not None:
            return True
    return False


# ---------------------------------------------------------------------------------------------
# Traced replica parse
# ---------------------------------------------------------------------------------------------
@dataclass
class ClaimTrace:
    text: str
    start: int
    end: int
    section_kind: str | None
    necessity_hint: str | None
    local_marker: bool
    narrative_cue: bool
    effective_hint: str | None
    necessity: str | None
    alternative_kind: str | None
    policy_decision: str = "keep"
    policy_reason: str | None = None
    rows: list = field(default_factory=list)


@dataclass
class ParseResult:
    claims: list[ClaimTrace]
    rows: tuple
    unparsed: tuple
    profile: JobRequirementProfile


def _nv(n) -> str | None:
    return None if n is None else n.value


def parse(description: str, policy: Policy = POLICY_V13) -> ParseResult:
    registry = default_registry()
    has_heading = doc_has_heading(description, policy)
    traces: list[ClaimTrace] = []
    all_rows: list = []
    unparsed: list[UnparsedClaim] = []
    for claim in segment(description, policy):
        eff = resolve_necessity_hint(claim.text, claim.necessity_hint, section_kind=claim.section_kind,
                                     document_has_recognized_heading=has_heading)
        necessity = infer_necessity(claim.text, eff)
        tr = ClaimTrace(claim.text, claim.start, claim.end, claim.section_kind, _nv(claim.necessity_hint),
                        _has_local_marker(claim.text), contains_narrative_cue(claim.text), _nv(eff), _nv(necessity),
                        None)
        if necessity is not None:
            tr.alternative_kind = classify_alternative_claim(claim.text, registry=registry).kind
        rows: list = []
        decision, reason = "keep", None
        if policy.admit is not None:
            decision, reason = policy.admit(claim.text, claim.section_kind, has_heading, claim.necessity_hint)
        if decision == "keep":
            prod_claim = seg.Claim(text=claim.text, start=claim.start, end=claim.end,
                                   necessity_hint=claim.necessity_hint, section_kind=claim.section_kind)
            rows = list(_requirements_from_claim(prod_claim, registry, document_has_recognized_heading=has_heading))
            if rows and policy.necessity is not None:
                new_nec = policy.necessity(claim.text, claim.section_kind, rows[0].necessity)
                if new_nec is None:
                    rows, decision, reason = [], "decline", "necessity_unresolvable"
                elif new_nec != rows[0].necessity:
                    rows = [_with_necessity(r, new_nec) for r in rows]
            if rows and policy.rows is not None:
                rows = list(policy.rows(claim.text, rows))
        tr.policy_decision, tr.policy_reason, tr.rows = decision, reason, rows
        traces.append(tr)
        if not rows:
            unparsed.append(UnparsedClaim(text=claim.text, source_span=SourceSpan(claim.start, claim.end)))
        all_rows.extend(rows)
    final = deduplicate_requirements(all_rows)
    profile = JobRequirementProfile(raw_text=description, requirements=final,
                                    parser_version=f"{JOB_DESCRIPTION_PARSER_VERSION}+research:{policy.name}")
    return ParseResult(traces, final, tuple(unparsed), profile)


def _with_necessity(row, necessity: Necessity):
    from dataclasses import replace

    from gitscore.jobs.parsing.importance import infer_importance
    return replace(row, necessity=necessity, importance=infer_importance(row.original_text, necessity))


def fidelity_check(texts: list[str]) -> list[int]:
    """Indices where the v13 replica differs from production (must be [])."""
    bad = []
    for i, t in enumerate(texts):
        prod = parse_job_description_with_diagnostics(t)
        rep = parse(t, POLICY_V13)
        if prod.profile.requirements != rep.rows or prod.unparsed_claims != rep.unparsed:
            bad.append(i)
    return bad


# ---------------------------------------------------------------------------------------------
# Gold mapping and metrics
# ---------------------------------------------------------------------------------------------
def load_controls(split: str) -> list[dict]:
    return json.loads(CONTROLS[split].read_text(encoding="utf-8"))["controls"]


def row_members(row) -> tuple[str, ...]:
    if row.alternative_concept_ids:
        return tuple(row.alternative_concept_ids)
    return (row.concept_id,) if row.concept_id else ()


def row_kind(row) -> str:
    if row.alternative_concept_ids:
        return "alternative_group"
    if row.category in ("alternative_requirement", "unresolved_requirement"):
        return "placeholder"
    if row.concept_id is None:
        return "non_technical"
    return "unresolved_concept" if row.concept_id.startswith("unresolved:") else "registry_concept"


def _overlap(a0, a1, b0, b1) -> int:
    return max(0, min(a1, b1) - max(a0, b0))


def _unit_spans(control: dict) -> list[tuple[int, int]]:
    return [(control["text"].index(u["span"]), control["text"].index(u["span"]) + len(u["span"])) for u in control["units"]]


def evaluate_control(control: dict, policy: Policy = POLICY_V13) -> dict:
    """Per-unit outcome + attribution for one control under `policy`."""
    text = control["text"]
    res = parse(text, policy)
    spans = _unit_spans(control)
    units = [dict(u, uid=f"u{k}", start=s, end=e, rows=[], claims=[], unparsed=False)
             for k, (u, (s, e)) in enumerate(zip(control["units"], spans))]
    unmapped_rows = []
    for tr in res.claims:
        overlaps = [(_overlap(tr.start, tr.end, u["start"], u["end"]), k) for k, u in enumerate(units)]
        hit = [k for ov, k in overlaps if ov > 0]
        if not hit:
            unmapped_rows.extend(_row_view(r) for r in tr.rows)
            continue
        best = max(overlaps)[1]
        multi = len(hit) > 1
        units[best]["claims"].append({"trace": tr, "multi_unit": multi})
        for r in tr.rows:
            units[best]["rows"].append(_row_view(r))
        if not tr.rows:
            units[best]["unparsed"] = True

    scoring = _scoring(control, res, units)
    out_units = []
    for u in units:
        out_units.append(_unit_outcome(u))
    return {"id": control["id"], "family": control["family"], "pair": control["pair"],
            "phase2_case": control.get("phase2_case"), "units": out_units, "unmapped_rows": unmapped_rows,
            "scoring": scoring, "n_rows": len(res.rows), "n_unparsed": len(res.unparsed)}


def _row_view(r) -> dict:
    return {"kind": row_kind(r), "members": list(row_members(r)), "category": r.category,
            "necessity": r.necessity.value, "span": [r.source_span.start, r.source_span.end],
            "text": r.original_text}


def _unit_outcome(u: dict) -> dict:
    tech = set(u["tech"])
    rows = u["rows"]
    fabricated = sorted({m for r in rows for m in r["members"] if m not in tech})
    legit_rows = [r for r in rows if u["qual"] and (
        (r["members"] and all(m in tech for m in r["members"]))
        or (r["kind"] == "non_technical" and r["category"] in u["nt"])
        or r["kind"] == "placeholder")]
    represented = sorted({m for r in rows for m in r["members"] if m in tech})
    claim = u["claims"][0]["trace"] if u["claims"] else None
    out = {
        "uid": u["uid"], "span": u["span"], "kind": u["kind"], "qual": u["qual"], "gold_nec": u["nec"],
        "gold_section": u["section"], "ambiguous": u["ambiguous"], "gold_tech": u["tech"],
        "admitted_claim": claim is not None, "multi_unit_claim": any(c["multi_unit"] for c in u["claims"]),
        "section_kind": None if claim is None else claim.section_kind,
        "local_marker": None if claim is None else claim.local_marker,
        "narrative_cue": None if claim is None else claim.narrative_cue,
        "alternative_kind": None if claim is None else claim.alternative_kind,
        "policy_decision": None if claim is None else claim.policy_decision,
        "policy_reason": None if claim is None else claim.policy_reason,
        "rows": rows, "unparsed": u["unparsed"],
        "row_necessities": sorted({r["necessity"] for r in rows}),
        "fabricated_concepts": fabricated,
        "fabricated_registry": [c for c in fabricated if not c.startswith("unresolved:")],
        "fabricated_unresolved": [c for c in fabricated if c.startswith("unresolved:")],
        "represented_tech": represented, "legit_row_count": len(legit_rows),
        "span_exact": all(r["text"] == u["span"] or u["span"] in r["text"] or r["text"] in u["span"] for r in rows),
        "span_within_unit": all(u["start"] <= r["span"][0] and r["span"][1] <= u["end"] for r in rows),
    }
    out["outcome"] = _classify_outcome(out)
    out["attribution"] = attribute(out)
    return out


def _classify_outcome(o: dict) -> str:
    rows = o["rows"]
    if not o["qual"]:
        if not rows:
            return "correctly_not_admitted"
        if all(r["kind"] == "placeholder" for r in rows):
            return "false_placeholder_only"
        return "false_admission"
    has_content = any(r["kind"] != "placeholder" for r in rows)
    if not rows:
        return "declined_visible" if o["unparsed"] else "missed_entirely"
    if not has_content:
        return "declined_placeholder"
    if not o["legit_row_count"]:
        return "admitted_wrong_content"
    return "represented"


def attribute(o: dict) -> str | None:
    """Primary root-cause category (Phase 4) for a defective unit, else None.

    Order = earliest pipeline stage at which the defect became accepted.
    """
    sec = o["section_kind"]
    gold = o["gold_section"]
    expected_kind = {"required": "REQUIRED", "preferred": "PREFERRED", "responsibility": "RESPONSIBILITY",
                     "learning": "LEARNING"}.get(gold)
    heading_wrong = (expected_kind is not None and sec != expected_kind) or (
        gold in ("company", "benefits", "process") and sec is not None) or (
        gold in ("company", "benefits", "process") and sec is None and o["admitted_claim"]
        and o["gold_section"] != "none")
    if o["outcome"] in ("false_admission", "false_placeholder_only"):
        if o["multi_unit_claim"]:
            return "C_segmentation"
        if heading_wrong or (gold == "none" and sec in QUALIFYING_SECTIONS):
            return "A_section_heading"
        return "B_qualification_intent"
    if o["qual"] and not o["ambiguous"]:
        if o["outcome"] in ("missed_entirely", "declined_visible"):
            if o["multi_unit_claim"]:
                return "C_segmentation"
            if not o["admitted_claim"] or heading_wrong or (sec is None and o["unparsed"] and gold != "none"):
                return "A_section_heading"
            if o["policy_decision"] == "decline":
                return "B_qualification_intent"
            if o["unparsed"] and sec in (None, "UNKNOWN", "RESPONSIBILITY", "LEARNING"):
                return "A_section_heading" if gold in ("required", "preferred") else "B_qualification_intent"
            return "G_vocabulary_gap"
        if o["outcome"] == "declined_placeholder":
            return "F_alternative_logic" if any(r["category"] == "alternative_requirement" for r in o["rows"]) \
                else "G_vocabulary_gap"
        if o["fabricated_concepts"]:
            return "F_alternative_logic" if any(r["kind"] == "alternative_group" and
                                                set(r["members"]) & set(o["fabricated_concepts"])
                                                for r in o["rows"]) else "E_concept_recognition"
        nec_ok = o["gold_nec"] == "unknown" or o["row_necessities"] in ([o["gold_nec"]], [])
        if not nec_ok:
            return "D_necessity"
    return None


def _scoring(control: dict, res: ParseResult, units: list[dict]) -> dict:
    """v2 impact: actual rows vs the same rows with every false-admission
    row (non-qualification unit, or unmapped) removed -- the score a
    parser with perfect admission (and otherwise identical behaviour)
    would produce. Two candidates: no evidence; evidence for every
    registered concept the control names or the parser emitted."""
    def unit_of(row):
        s, e = row.source_span.start, row.source_span.end
        best = max(((_overlap(s, e, u["start"], u["end"]), k) for k, u in enumerate(units)), default=(0, None))
        return None if best[0] == 0 else units[best[1]]

    def is_false(row) -> bool:
        u = unit_of(row)
        return u is None or not u["qual"]

    def is_fabricated(row) -> bool:
        u = unit_of(row)
        return u is not None and u["qual"] and any(m not in u["tech"] for m in row_members(row))

    registry = default_registry()
    emitted = {m for r in res.rows for m in row_members(r)}
    named = {t for u in units for t in u["tech"]}
    full_ev = sorted(c for c in emitted | named if registry.get(c) is not None)
    clean_rows = tuple(r for r in res.rows if not is_false(r))
    out = {"false_rows": sum(1 for r in res.rows if is_false(r))}
    for cname, ev in (("none", []), ("full", full_ev)):
        cand = candidate_profile(ev)
        a = assess_job(match_job(cand, res.profile))
        ms = a.match_analysis.requirement_matches
        counted_false = [m for m in ms if a.counts_toward_alignment(m) and is_false(m.requirement)]
        if clean_rows:
            clean_profile = JobRequirementProfile(raw_text=res.profile.raw_text, requirements=clean_rows,
                                                  parser_version=res.profile.parser_version)
            ca = assess_job(match_job(cand, clean_profile))
            clean_score, clean_den = ca.alignment_score, ca.assessable_count
        else:
            clean_score, clean_den = None, 0
        out[cname] = {
            "score": a.alignment_score, "denominator": a.assessable_count,
            "false_rows_counted": len(counted_false),
            "false_rows_excluded_by_v2": sum(1 for m in ms if is_false(m.requirement)
                                              and not a.counts_toward_alignment(m)
                                              and m.status != MatchStatus.NOT_ASSESSABLE),
            "false_rows_not_assessable": sum(1 for m in ms if is_false(m.requirement)
                                              and m.status == MatchStatus.NOT_ASSESSABLE),
            "false_supported_counted": sum(1 for m in counted_false if m.status == MatchStatus.SUPPORTED),
            "fabricated_rows_counted": sum(1 for m in ms if a.counts_toward_alignment(m) and is_fabricated(m.requirement)),
            "fabricated_supported_counted": sum(1 for m in ms if a.counts_toward_alignment(m)
                                                and is_fabricated(m.requirement) and m.status == MatchStatus.SUPPORTED),
            "clean_score": clean_score, "clean_denominator": clean_den,
        }
    return out


# ---------------------------------------------------------------------------------------------
# Aggregate metrics (Phase 5)
# ---------------------------------------------------------------------------------------------
def aggregate(results: list[dict]) -> dict:
    units = [u for r in results for u in r["units"]]
    nonqual = [u for u in units if not u["qual"]]
    qual = [u for u in units if u["qual"] and not u["ambiguous"]]
    amb = [u for u in units if u["qual"] and u["ambiguous"]]
    rows = [(u, row) for u in units for row in u["rows"]]
    unmapped = sum(len(r["unmapped_rows"]) for r in results)
    false_rows = [(u, row) for u, row in rows if not u["qual"]]
    req_false = sum(1 for u, row in false_rows if row["necessity"] == "required")
    req_over = sum(1 for u, row in rows if u["qual"] and u["gold_nec"] == "preferred" and row["necessity"] == "required")
    admitted_units = [u for u in units if u["rows"] and not u["ambiguous"]]
    represented_qual = [u for u in qual if u["outcome"] == "represented"]
    gold_tech = sum(len(u["gold_tech"]) for u in qual)
    found_tech = sum(len(u["represented_tech"]) for u in qual)
    legit_row_n = sum(u["legit_row_count"] for u in units if not u["ambiguous"])
    all_row_n = sum(len(u["rows"]) for u in units if not u["ambiguous"]) + unmapped
    nec_scored = [u for u in represented_qual if u["gold_nec"] in ("required", "preferred")]
    nec_correct = [u for u in nec_scored if u["row_necessities"] == [u["gold_nec"]]]
    mixed_controls = [r for r in results if any(u["qual"] and not u["ambiguous"] for u in r["units"])
                      and any(not u["qual"] for u in r["units"])]
    mixed_qual = [u for r in mixed_controls for u in r["units"] if u["qual"] and not u["ambiguous"]]
    fab = [(u, c) for u in units for c in u["fabricated_concepts"]]
    attributions: dict[str, int] = {}
    for u in units:
        if u["attribution"]:
            attributions[u["attribution"]] = attributions.get(u["attribution"], 0) + 1
    score = {k: sum(r["scoring"][c][k] for r in results for c in ("full",))
             for k in ("false_rows_counted", "false_rows_excluded_by_v2", "false_rows_not_assessable",
                       "false_supported_counted", "fabricated_rows_counted", "fabricated_supported_counted")}
    score_changed = sum(1 for r in results if r["scoring"]["full"]["score"] != r["scoring"]["full"]["clean_score"]
                        or r["scoring"]["full"]["denominator"] != r["scoring"]["full"]["clean_denominator"])

    def ratio(a, b):
        return None if b == 0 else round(a / b, 4)

    return {
        "units": {"total": len(units), "non_qualification": len(nonqual), "qualification": len(qual),
                  "ambiguous": len(amb)},
        "1_false_admissions": {
            "units_with_any_row": sum(1 for u in nonqual if u["rows"]),
            "units_with_content_rows": sum(1 for u in nonqual if u["outcome"] == "false_admission"),
            "units_placeholder_only": sum(1 for u in nonqual if u["outcome"] == "false_placeholder_only"),
            "rows": len(false_rows) + unmapped, "unmapped_rows": unmapped,
            "denominator": "non-qualification units", "rate": ratio(sum(1 for u in nonqual if u["rows"]), len(nonqual)),
        },
        "2_false_required": {"rows_on_non_qualifications": req_false, "rows_preferred_gold_marked_required": req_over,
                             "units_preferred_gold_marked_required": sum(
                                 1 for u in qual if u["gold_nec"] == "preferred" and "required" in u["row_necessities"]),
                             "units_non_qualification_marked_required": sum(
                                 1 for u in nonqual if "required" in u["row_necessities"])},
        "3_fabricated_concepts": {
            "total": len(fab),
            "registry_alias_on_generic_word": sum(1 for u, c in fab if not c.startswith("unresolved:")),
            "unresolved": sum(1 for u, c in fab if c.startswith("unresolved:")),
            "on_qualification_units": sum(1 for u, c in fab if u["qual"]),
            "on_non_qualification_units": sum(1 for u, c in fab if not u["qual"]),
            "note": "a concept id emitted for a unit that does not genuinely name that technology",
        },
        "4_false_supported_counted_full_evidence": score["false_supported_counted"],
        "5_denominator": {
            "false_rows_counted_full_evidence": score["false_rows_counted"],
            "false_rows_excluded_by_v2": score["false_rows_excluded_by_v2"],
            "false_rows_not_assessable_placeholder": score["false_rows_not_assessable"],
            "fabricated_concept_rows_counted_full_evidence": score["fabricated_rows_counted"],
            "fabricated_concept_rows_supported_full_evidence": score["fabricated_supported_counted"],
            "controls_whose_score_or_denominator_differs_from_clean": score_changed,
        },
        "6_missed": {"qualification_units_missed_entirely": sum(1 for u in qual if u["outcome"] == "missed_entirely")},
        "7_declined": {
            "declined_visible_unparsed": sum(1 for u in qual if u["outcome"] == "declined_visible"),
            "declined_placeholder": sum(1 for u in qual if u["outcome"] == "declined_placeholder"),
            "admitted_wrong_content": sum(1 for u in qual if u["outcome"] == "admitted_wrong_content"),
        },
        "8_source_spans": {"rows_within_one_unit": sum(1 for u in units if u["span_within_unit"]) == len(units),
                           "units_with_cross_unit_claim": sum(1 for u in units if u["multi_unit_claim"])},
        "9_mixed_content": {"controls": len(mixed_controls), "qualification_units": len(mixed_qual),
                            "represented": sum(1 for u in mixed_qual if u["outcome"] == "represented")},
        "precision": {
            "unit_admission_precision": ratio(sum(1 for u in admitted_units if u["qual"]), len(admitted_units)),
            "unit_admission_precision_definition": "qualification units with >=1 row / all non-ambiguous units with >=1 row",
            "row_precision": ratio(legit_row_n, all_row_n),
            "row_precision_definition": "legit rows (qualification unit; members all genuinely named, or acceptable "
                                        "non-technical category, or placeholder) / all rows on non-ambiguous units "
                                        "+ unmapped rows",
        },
        "recall": {
            "unit_recall": ratio(len(represented_qual), len(qual)),
            "unit_recall_definition": "non-ambiguous qualification units with >=1 legit content row / all such units",
            "concept_recall": ratio(found_tech, gold_tech),
            "concept_recall_definition": "gold technologies on non-ambiguous qualification units present as a row "
                                         "member / all such gold technologies",
        },
        "necessity_accuracy": {"correct": len(nec_correct), "scored": len(nec_scored),
                               "definition": "represented qualification units whose rows all carry the gold necessity"},
        "attribution_counts": dict(sorted(attributions.items())),
    }


def run_split(split: str, policy: Policy = POLICY_V13) -> tuple[list[dict], dict]:
    results = [evaluate_control(c, policy) for c in load_controls(split)]
    return results, aggregate(results)
