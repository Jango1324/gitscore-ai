"""Milestone 11-G16 -- compound AND/OR requirement logic: production
reproduction and candidate-fix simulation.

Evaluation-only. No production file is modified: production behaviour
comes from CALLING the real parser/matcher/assessor; candidate fixes are
simulated by temporarily rebinding `gitscore.jobs.parsing.parser.
classify_alternative_claim` in memory (restored on exit) and, for the
decomposition option, by post-processing the real parser's own fallback
rows with real production helpers (`classify_alternative_claim`,
`find_concept_mentions`, `infer_necessity`).

Modes:
* production -- the live parser v12, unchanged.
* A_lexical_guard -- an OR claim containing any conjunction token (and,
  &, as well as, plus, along with, both, all of, at least two..., ';')
  is routed to the parser's EXISTING 6B.1 "unsafe" fallback.
* D_structural_guard -- route to the same fallback only when the OR claim
  is structurally mixed: some OR segment resolves to >= 2 concepts, a
  comma item begins with a conjunction, or a k>=2-of / both / all-of
  lead-in is present.
* C_decompose -- D's detection, then split ONLY shapes representable with
  existing structures (an AND of single concepts / OR-groups) into
  separate rows; everything else stays declined.
* B (internal Boolean tree, public schema unchanged) yields exactly C's
  public rows for representable shapes and must decline the rest, so its
  observable outputs are C's by construction.
"""
from __future__ import annotations



import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import gitscore.jobs.parsing.parser as parser_mod  # noqa: E402
from gitscore.assessment import assess_job  # noqa: E402
from gitscore.concepts.registry import default_registry, is_unresolved_concept_id  # noqa: E402
from gitscore.jobs import JobRequirement  # noqa: E402
from gitscore.jobs.parsing import alternatives as alt  # noqa: E402
from gitscore.jobs.parsing.concepts import find_concept_mentions  # noqa: E402
from gitscore.jobs.parsing.confidence import confidence_for  # noqa: E402
from gitscore.jobs.parsing.necessity import infer_necessity  # noqa: E402
from gitscore.jobs.parsing.observability import observability_for_technical  # noqa: E402

from gitscore.matching import MatchStatus, match_job  # noqa: E402

import gold_integrity as gi  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402

CONTROLS_PATH = _REPO_ROOT / "evaluation" / "m11g16" / "compound_logic_controls.json"
FREEZE_PATH = _REPO_ROOT / "evaluation" / "m11g16" / "controls_hash_freeze.json"
MODES = ("production", "A_lexical_guard", "D_structural_guard", "C_decompose")

_LEXICAL = re.compile(r"\b(?:and|as\s+well\s+as|plus|along\s+with|both|all\s+of)\b|&|;", re.IGNORECASE)
_KOF_GE2 = re.compile(r"\bat\s+least\s+(?:two|three|four|five|[2-9])\b", re.IGNORECASE)
_LEAD_IN = re.compile(r"\b(?:both|all\s+of)\b", re.IGNORECASE)
_CONJ_ITEM = re.compile(r",\s*(?:and|as\s+well\s+as|plus|along\s+with)\b", re.IGNORECASE)
_CONDITION = re.compile(r"\b(?:if|unless|when)\b|\bfor\s+\w+\s+(?:roles?|positions?|teams?)\b", re.IGNORECASE)
_SPLIT = re.compile(
    r";|,\s*(?:and|as\s+well\s+as|plus|along\s+with)\s+(?:also\s+)?|\s+(?:as\s+well\s+as|plus|along\s+with)\s+"
    r"|\)\s+and\s+|\s+and\s+(?=(?:either|one\s+of)\b)", re.IGNORECASE)
_LEADING_WORDS = re.compile(r"^\s*(?:either|one\s+of|also|\()\s*", re.IGNORECASE)


def load_frozen_controls() -> dict:
    raw = CONTROLS_PATH.read_bytes()
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if gi.sha256(gi.canonical_bytes(raw)) != freeze["sha256_lf_normalized"]:
        raise SystemExit("M11-G16 FROZEN CONTROLS CHANGED (LF-normalized comparison)")
    return json.loads(raw.decode("utf-8"))


def structurally_mixed(text: str) -> bool:
    """Option D's detector (pure function of the claim text)."""
    if _KOF_GE2.search(text) or _LEAD_IN.search(text) or _CONJ_ITEM.search(text):
        return True
    registry = default_registry()
    for segment in alt._split_alternative_segments(text):
        ids = alt._resolve_segment(segment, registry)
        if ids is not None and len(set(ids)) >= 2:
            return True
    return False


def lexically_mixed(text: str) -> bool:
    return bool(_LEXICAL.search(text) or _KOF_GE2.search(text))


def install(mode: str):
    """Rebind the parser's module-level helpers IN MEMORY for one option
    and return an `uninstall()` callable. Used identically by the
    in-process evaluation and by the throwaway-clone regression probe."""
    if mode == "production":
        return lambda: None
    original_classify = parser_mod.classify_alternative_claim
    original_rows = parser_mod._requirements_from_claim
    detector = lexically_mixed if mode == "A_lexical_guard" else structurally_mixed
    flagged: set[str] = set()

    def guarded(text, registry=None):
        result = original_classify(text, registry=registry)
        if result.kind == "technical" and detector(text):
            flagged.add(text)
            return alt.AlternativeClaim(kind="unsafe")
        return result

    def decomposing_rows(claim, registry, **kwargs):
        rows = original_rows(claim, registry, **kwargs)
        out = []
        for r in rows:
            pieces = decompose(r.original_text) if (r.category == "alternative_requirement"
                                                    and r.original_text in flagged) else None
            if not pieces:
                out.append(r)
                continue
            for conj_text, ids in pieces:
                out.append(JobRequirement(
                    original_text=conj_text.strip(),
                    necessity=infer_necessity(conj_text, r.necessity),
                    importance=r.importance,
                    github_observability=observability_for_technical(),
                    concept_id=ids[0] if len(ids) == 1 else None,
                    alternative_concept_ids=ids if len(ids) > 1 else (),
                    parser_confidence=confidence_for("resolved_concept"),
                    source_span=r.source_span,
                ))
        return out

    parser_mod.classify_alternative_claim = guarded
    if mode == "C_decompose":
        parser_mod._requirements_from_claim = decomposing_rows

    def uninstall():
        parser_mod.classify_alternative_claim = original_classify
        parser_mod._requirements_from_claim = original_rows

    return uninstall


def decompose(text: str) -> list[tuple[str, tuple[str, ...]]] | None:
    """Conjuncts of a representable AND-of-(single | OR-group), or None."""
    if _KOF_GE2.search(text) or _LEAD_IN.search(text) or _CONDITION.search(text):
        return None
    parts = [p for p in _SPLIT.split(text) if p and p.strip(" ,.")]
    if len(parts) < 2:
        return None
    registry = default_registry()
    out = []
    for part in parts:
        conj = _LEADING_WORDS.sub("", part).strip()
        if re.search(r"\band\b", conj, re.IGNORECASE):
            return None  # an un-split AND inside a conjunct: precedence undetermined
        if alt.contains_alternative_marker(conj):
            res = alt.classify_alternative_claim(conj, registry=registry)
            if res.kind != "technical":
                return None
            out.append((part, tuple(res.concept_ids)))
        else:
            ids = sorted({m.concept_id for m in find_concept_mentions(conj, registry=registry)})
            if len(ids) != 1:
                return None
            out.append((part, (ids[0],)))
    return out


def parse(text: str, mode: str):
    uninstall = install(mode)
    try:
        return parser_mod.parse_job_description(text)
    finally:
        uninstall()


def row_members(r) -> list[str]:
    return sorted(r.alternative_concept_ids) if r.alternative_concept_ids else ([r.concept_id] if r.concept_id else [])


def evaluate(control: dict, mode: str) -> dict:
    profile = parse(control["text"], mode)
    rows = profile.requirements
    out = {"rows": [{"members": row_members(r), "necessity": r.necessity.value, "category": r.category,
                     "span_ok": r.source_span is not None and 0 <= r.source_span.start < r.source_span.end
                     <= len(control["text"])} for r in rows],
           "fixtures": {}}
    fixtures = control["expected"]["per_fixture"] or {"none": {"evidence": []},
                                                      "irrelevant": {"evidence": ["framework.react"]},
                                                      "all_named": {"evidence": ["language.python", "language.go",
                                                                                 "infra.docker", "infra.kubernetes",
                                                                                 "language.java", "language.rust"]}}
    for name, fx in fixtures.items():
        analysis = match_job(candidate_profile(fx["evidence"]), profile)
        assessment = assess_job(analysis)
        matches = analysis.requirement_matches
        scored = [m for m in matches if m.status != MatchStatus.NOT_ASSESSABLE]
        supported = [m for m in scored if m.status == MatchStatus.SUPPORTED]
        out["fixtures"][name] = {
            "statuses": [m.status.value for m in matches],
            "matched": [list(m.matched_concept_ids) for m in matches],
            "assessable": assessment.assessable_count,
            "supported": len(supported),
            "score": assessment.alignment_score,
            "claim_satisfied": bool(scored) and len(supported) == len(scored),
            "unresolved_positive": any(is_unresolved_concept_id(c) and not c.startswith("unresolved:elixir")
                                       for m in supported for c in m.matched_concept_ids),
        }
    return out


def _frac(ids, denom):
    return {"count": len(ids), "denominator": denom, "ids": ids}


def metrics(controls: list[dict], results: dict) -> dict:
    out = {}
    for mode in MODES:
        false_sup, scored_bad, false_decl, exact, nec_ok, over, under, narrative_scored = ([] for _ in range(8))
        span_bad, unstable, unresolved_pos = [], [], []
        fx_total = 0
        rep = [c for c in controls if c["expected"]["behavior"] == "represent"]
        dec = [c for c in controls if c["expected"]["behavior"] == "decline"]
        for c in controls:
            res = results[c["id"]][mode]
            if any(not r["span_ok"] for r in res["rows"]):
                span_bad.append(c["id"])
            if len({f["assessable"] for f in res["fixtures"].values()}) > 1:
                unstable.append(c["id"])
            for name, f in res["fixtures"].items():
                if f["unresolved_positive"]:
                    unresolved_pos.append(f"{c['id']}/{name}")
            if c["expected"]["behavior"] == "not_qualification":
                if any(f["assessable"] for f in res["fixtures"].values()):
                    narrative_scored.append(c["id"])
                continue
            for name, exp in c["expected"]["per_fixture"].items():
                fx_total += 1
                f = res["fixtures"][name]
                if f["claim_satisfied"] and exp["gold_truth"] != "T":
                    false_sup.append(f"{c['id']}/{name}")
            assessable = res["fixtures"]["none"]["assessable"]
            if c["expected"]["behavior"] == "decline" and assessable:
                scored_bad.append(c["id"])
            if c["expected"]["behavior"] == "represent":
                got = sorted((tuple(r["members"]) for r in res["rows"] if r["members"]))
                want = sorted(tuple(r["members"]) for r in c["expected"]["rows"])
                if not assessable:
                    false_decl.append(c["id"])
                if got == want:
                    exact.append(c["id"])
                    gotn = sorted((tuple(r["members"]), r["necessity"]) for r in res["rows"] if r["members"])
                    wantn = sorted((tuple(r["members"]), r["necessity"]) for r in c["expected"]["rows"])
                    if gotn == wantn:
                        nec_ok.append(c["id"])
                if assessable > len(c["expected"]["rows"]):
                    over.append(c["id"])
                if 0 < assessable < len(c["expected"]["rows"]):
                    under.append(c["id"])
        out[mode] = {
            "1_false_supported_claim_level": _frac(false_sup, fx_total),
            "2_ambiguous_or_unrepresentable_scored": _frac(scored_bad, len(dec)),
            "3_genuine_represented_exactly": _frac(exact, len(rep)),
            "3b_exact_with_correct_necessity": _frac(nec_ok, len(rep)),
            "4_false_declines_of_representable": _frac(false_decl, len(rep)),
            "5_denominator_overcount": _frac(over, len(rep)),
            "5b_denominator_undercount_merged": _frac(under, len(rep)),
            "6_narrative_scored": _frac(narrative_scored, 3),
            "7_rows_without_valid_source_span": _frac(span_bad, len(controls)),
            "8_eligibility_unstable_across_candidates": _frac(unstable, len(controls)),
            "9_unevidenceable_concept_as_positive": _frac(unresolved_pos, fx_total),
        }
    return out


def invariants(controls: list[dict], results: dict) -> dict:
    by_id = {c["id"]: c for c in controls}

    def sat(cid, mode, fx):
        return results[cid][mode]["fixtures"][fx]["claim_satisfied"]

    def rows(cid, mode):
        return [tuple(r["members"]) for r in results[cid][mode]["rows"] if r["members"]]

    simple = [c["id"] for c in controls if c["family"] in ("simple_or", "simple_and")] + \
             ["m11g16-022", "m11g16-023", "m11g16-035"]
    ambiguous = [c["id"] for c in controls if c["ambiguous"]]
    out = {}
    for mode in MODES:
        checks = {
            "1_C_alone_cannot_satisfy_(A_or_B)_and_C": not any(
                sat(cid, mode, "only_C") for cid in ("m11g16-007", "m11g16-008", "m11g16-010", "m11g16-011")),
            "2_A_alone_cannot_satisfy_A_and_(B_or_C)": not any(
                sat(cid, mode, "only_A") for cid in ("m11g16-012", "m11g16-014", "m11g16-015")),
            "3_A_and_C_may_satisfy_(A_or_B)_and_C": any(
                sat(cid, mode, "A_and_C") for cid in ("m11g16-007", "m11g16-008", "m11g16-010", "m11g16-011")),
            "4_distinct_alternatives_not_equivalent": not sat("m11g16-056", mode, "only_A"),
            "5_irrelevant_evidence_satisfies_nothing": not any(
                f["supported"] for c in controls for f in [results[c["id"]][mode]["fixtures"].get("irrelevant", {})]
                if f),
            "6_unevidenceable_never_positive": not any(
                f["unresolved_positive"] for c in controls for f in results[c["id"]][mode]["fixtures"].values()),
            "7_ambiguous_never_scored": not any(results[cid][mode]["fixtures"]["none"]["assessable"]
                                                for cid in ambiguous),
            "8_stable_eligibility_across_candidates": all(
                len({f["assessable"] for f in results[c["id"]][mode]["fixtures"].values()}) == 1 for c in controls),
            "9_no_double_counting": all(
                results[c["id"]][mode]["fixtures"]["none"]["assessable"] <= max(1, len(c["expected"]["rows"]))
                for c in controls if c["expected"]["behavior"] == "represent"),
            "10_source_provenance_kept": all(r["span_ok"] for c in controls for r in results[c["id"]][mode]["rows"]),
            "11_no_new_required_by_default": all(
                r["necessity"] == p["necessity"]
                for c in controls
                for r, p in [(r, results[c["id"]]["production"]["rows"][0])
                             for r in results[c["id"]][mode]["rows"] if results[c["id"]]["production"]["rows"]]
                if p["necessity"] != "required" and r["necessity"] == "required"),
            "12_simple_or_and_unchanged": all(rows(cid, mode) == rows(cid, "production") for cid in simple),
        }
        out[mode] = checks
    # invariant 11 is evaluated as: a row may be REQUIRED only if production's own claim
    # necessity (or the conjunct's local marker) already said so -- vacuously true when no
    # mode turns a non-required claim into a required row.
    del by_id
    return out


def run() -> dict:
    data = load_frozen_controls()
    controls = data["controls"]
    results = {c["id"]: {m: evaluate(c, m) for m in MODES} for c in controls}
    return {
        "milestone": "M11-G16",
        "controls_sha256_lf_normalized": gi.sha256(gi.canonical_bytes(CONTROLS_PATH.read_bytes())),
        "modes": list(MODES),
        "option_B_note": "Option B (internal Boolean tree, public schema unchanged) produces C_decompose's public "
                         "rows by construction; it is not simulated separately.",
        "metrics": metrics(controls, results),
        "invariants": invariants(controls, results),
        "results": results,
    }
