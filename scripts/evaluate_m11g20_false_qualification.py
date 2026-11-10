"""Milestone 11-G20 -- false qualification admission & parser precision (RESEARCH ONLY).

    python scripts/evaluate_m11g20_false_qualification.py [--private-corpora]

Runs the REAL v13 parser (via an asserted-identical replica that exposes
policy hooks), the real matcher and the real scoring v2 over:

* the frozen G20 synthetic controls (dev / held-out, separate files);
* the Phase-2 known-defect reproductions;
* every frozen historical corpus (G15, G16, G18, M10D, M10E, G6, G7, 8c
  job fixtures, M10 postings) -- read-only, gold never rewritten;
* with --private-corpora: previously inspected private postings, both the
  unlabeled impact and the pre-existing claim annotations -- INTEGER
  COUNTS ONLY, written to a separate file.

Writes `evaluation/m11g20/admission_report.json` (publication-safe) and,
with --private-corpora, `evaluation/m11g20/private_admission_aggregates.json`.
No production code is modified or imported for writing; no LLM; no network.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import gold_integrity as gi  # noqa: E402
import m11g20_admission as adm  # noqa: E402
import m11g20_historical as hist  # noqa: E402
import m11g20_policies as pol  # noqa: E402
import m11g20_posthoc as post  # noqa: E402
from gitscore.assessment import SCORING_VERSION, assess_job  # noqa: E402
from gitscore.jobs.parsing import segmentation as seg  # noqa: E402
from gitscore.matching import MATCHER_VERSION, match_job  # noqa: E402

OUT_DIR = REPO_ROOT / "evaluation" / "m11g20"
REPORT = OUT_DIR / "admission_report.json"
PRIVATE_OUT = OUT_DIR / "private_admission_aggregates.json"
POLICY_FREEZE = OUT_DIR / "policy_design_freeze.json"

FROZEN_POLICIES = (adm.POLICY_V13, *pol.POLICIES)
POSTHOC = post.POSTHOC_POLICIES
RECOMMENDED = post.POLICY_B1NR  # smallest safe first slice (see the milestone document)
DETAIL_POLICIES = (adm.POLICY_V13, post.POLICY_B1NR, pol.POLICY_C, post.POLICY_CR)

# Phase 2: (case number, label, source, control id or literal text, candidate evidence, is_qualification)
G18 = json.loads((REPO_ROOT / "evaluation/m11g18/eligibility_controls.json").read_text(encoding="utf-8"))["controls"]
G16 = json.loads((REPO_ROOT / "evaluation/m11g16/compound_logic_controls.json").read_text(encoding="utf-8"))["controls"]
PHASE2 = (
    (1, "G18 control 25: narrative text becoming REQUIRED requirements", "m11g18-25"),
    (2, "G17 control 053: responsibility sentence assigned REQUIRED necessity", "m11g16-053"),
    (3, "Generic words / fragments becoming unresolved technology identifiers", "m11g20-d018"),
    (3, "Generic words / fragments becoming unresolved technology identifiers", "m11g20-d023"),
    (3, "Generic words / fragments becoming unresolved technology identifiers", "m11g16-058"),
    (3, "Generic English words matching registry aliases", "m11g20-d016"),
    (4, "Technology names extracted from fragments without qualification intent", "m11g20-d060"),
    (4, "Technology names extracted from fragments without qualification intent", "m11g20-d011b"),
    (5, "Non-technical narrative inside a qualifications section", "m11g20-d038"),
    (5, "Non-technical narrative inside a qualifications section", "m11g20-d037"),
    (6, "Responsibilities under misleading headings", "m11g20-d039"),
    (6, "Responsibilities under misleading headings", "m11g20-d006"),
    (7, "Qualification statements embedded within narrative paragraphs", "m11g20-d025"),
    (8, "Legitimate REQUIRED qualifications under unconventional headings", "m11g20-d030"),
    (8, "Legitimate REQUIRED qualifications under unconventional headings", "m11g20-d028"),
    (8, "Legitimate REQUIRED qualifications under unconventional headings", "m11g20-d029"),
    (9, "Legitimate PREFERRED qualifications", "m11g20-d043"),
    (9, "Legitimate PREFERRED qualifications", "m11g20-d009a"),
    (10, "Legitimate technical requirements written as prose", "m11g20-d026"),
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def verify_freezes() -> dict:
    out = {}
    for split in ("dev", "holdout"):
        res = gi.verify_frozen_file(adm.CONTROLS[split], adm.FREEZES[split])
        out[split] = {"file": res.frozen_file, "method": res.method, "sha256": res.historical_raw_sha256}
    rec = json.loads(POLICY_FREEZE.read_text(encoding="utf-8"))
    for rel, digest in rec["sources"].items():
        actual = _sha(REPO_ROOT / rel)
        if actual != digest:
            raise SystemExit(f"policy design freeze violated: {rel} sha256 {actual} != frozen {digest}")
    out["policy_design"] = {"verified": True, "frozen_at_utc": rec["frozen_at_utc"], "sources": rec["sources"]}
    return out


def _control_by_id() -> dict:
    out = {}
    for split in ("dev", "holdout"):
        for c in adm.load_controls(split):
            out[c["id"]] = c
    return out


def _stage(trace, is_qual: bool, has_heading: bool) -> str:
    """Earliest production stage at which a (non-)qualification was accepted / lost."""
    sec = trace.section_kind
    if not trace.rows and trace.necessity is None:
        if sec in ("UNKNOWN", "LEARNING"):
            return "segmentation._classify_heading_line -> UNKNOWN/LEARNING section, necessity unresolved"
        return "necessity.resolve_necessity_hint step 2 (section-origin not eligible)"
    if is_qual:
        return "accepted (correct admission)"
    if sec in ("REQUIRED", "PREFERRED"):
        return "segmentation.segment_description: unconditional admission inside a REQUIRED/PREFERRED section"
    if trace.local_marker:
        return "necessity.resolve_necessity_hint step 1: a local REQUIRED/PREFERRED marker always wins"
    if sec is None and not has_heading:
        return ("segmentation._looks_like_requirement gate (concept mention / HR word) + "
                "necessity step 2 unsectioned default REQUIRED; narrative-cue veto (step 3) did not match")
    return "other"


def reproduce(case_no: int, label: str, cid: str, controls: dict) -> dict:
    if cid.startswith("m11g18-"):
        c = next(x for x in G18 if x["id"] == cid)
        text, is_qual = c["job_text"], False
        evidence = c["candidates"][0]["evidence"]
        units = None
    elif cid.startswith("m11g16-"):
        c = next(x for x in G16 if x["id"] == cid)
        text, is_qual = c["text"], c["is_qualification"]
        evidence = sorted({e for f in c["expected"]["per_fixture"].values() for e in f["evidence"]}) or \
            ["language.python", "infra.docker"]
        units = None
    else:
        c = controls[cid]
        text, units = c["text"], c["units"]
        evidence = sorted({t for u in units for t in u["tech"] if not t.startswith("unresolved:")})
        is_qual = None
    res = adm.parse(text, adm.POLICY_V13)
    has_heading = adm.doc_has_heading(text, adm.POLICY_V13)
    cand = adm.candidate_profile(evidence)
    assessment = assess_job(match_job(cand, res.profile))
    matches = {m.requirement: m for m in assessment.match_analysis.requirement_matches}
    claims = []
    for tr in res.claims:
        unit = None
        if units is not None:
            for u in units:
                s = text.index(u["span"])
                if adm._overlap(tr.start, tr.end, s, s + len(u["span"])):
                    unit = u
                    break
        q = unit["qual"] if unit is not None else bool(is_qual)
        rows = []
        for r in tr.rows:
            final = next((x for x in res.rows if x == r), None)
            m = matches.get(final) if final is not None else None
            reason = assessment.alignment_exclusion_reason(m) if m is not None else None
            rows.append({"category": r.category, "kind": adm.row_kind(r), "concept_ids": list(adm.row_members(r)),
                         "necessity": r.necessity.value, "source_span": [r.source_span.start, r.source_span.end],
                         "matcher_status": None if m is None else m.status.value,
                         "counts_toward_alignment_v2": None if m is None else assessment.counts_toward_alignment(m),
                         "alignment_exclusion_reason": None if reason is None else reason.value})
        claims.append({"text": tr.text, "source_span": [tr.start, tr.end], "section_kind": tr.section_kind,
                       "gold_is_qualification": q, "local_marker": tr.local_marker, "narrative_cue": tr.narrative_cue,
                       "necessity_hint": tr.necessity_hint, "effective_hint": tr.effective_hint,
                       "necessity": tr.necessity, "alternative_kind": tr.alternative_kind,
                       "admission": "JobRequirement" if tr.rows else "UnparsedClaim",
                       "earliest_stage": _stage(tr, q, has_heading), "rows": rows})
    clean = tuple(r for r in res.rows if any(
        cl["gold_is_qualification"] and adm._overlap(r.source_span.start, r.source_span.end, *cl["source_span"])
        for cl in claims))
    if clean:
        from gitscore.jobs.profile import JobRequirementProfile
        ca = assess_job(match_job(cand, JobRequirementProfile(raw_text=text, requirements=clean,
                                                              parser_version=res.profile.parser_version)))
        clean_score, clean_den = ca.alignment_score, ca.assessable_count
    else:
        clean_score, clean_den = None, 0
    unclaimed = []
    for u in units or ():
        s = text.index(u["span"])
        if not any(adm._overlap(tr.start, tr.end, s, s + len(u["span"])) for tr in res.claims):
            unclaimed.append({"span_text": u["span"], "source_span": [s, s + len(u["span"])],
                              "gold_is_qualification": u["qual"], "governing_heading_kind": _governing_kind(text, s),
                              "earliest_stage": "segmentation.segment_description: no Claim produced (SKIP section "
                                                "suppresses every line, or the _looks_like_requirement gate failed)"})
    return {"case": case_no, "label": label, "id": cid, "input": text, "document_has_recognized_heading": has_heading,
            "candidate_evidence": evidence, "claims": claims, "units_without_any_claim": unclaimed,
            "v2_score": assessment.alignment_score, "v2_denominator": assessment.assessable_count,
            "v2_score_with_only_gold_qualification_rows": clean_score,
            "v2_denominator_with_only_gold_qualification_rows": clean_den}


def _governing_kind(text: str, offset: int) -> str | None:
    import re
    kind = None
    for m in re.finditer(r"[^\r\n]+", text[:offset]):
        span = seg._line_content_span(m.group(), m.start())
        if span is None:
            continue
        k = seg._classify_heading_line(m.group(), text[span[0]:span[1]])
        if k is not None:
            kind = k.name
    return kind


def heading_kind_divergence(policy) -> dict:
    out = {}
    for name, rel in (("g6", "evaluation/m11g6/heading_controls.json"), ("g7", "evaluation/m11g7/boundary_controls.json")):
        cs = json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))["controls"]
        agree0 = agree1 = n = 0
        changed = []
        for c in cs:
            line = c["heading_line"]
            if line is None:
                continue
            n += 1
            span = seg._line_content_span(line, 0)
            content = line[span[0]:span[1]] if span else ""
            k0 = seg._classify_heading_line(line, content)
            k1 = policy.heading(line, content, k0) if policy.heading else k0
            n0, n1 = (k0.name if k0 else "NOT_A_HEADING"), (k1.name if k1 else "NOT_A_HEADING")
            agree0 += n0 == c["expected_heading_kind"]
            agree1 += n1 == c["expected_heading_kind"]
            if n0 != n1:
                changed.append(c["id"])
        out[name] = {"headings": n, "gold_agreement_v13": agree0, "gold_agreement_policy": agree1,
                     "changed_ids": changed}
    return out


def main() -> None:
    private = "--private-corpora" in sys.argv
    freezes = verify_freezes()
    controls = _control_by_id()
    corp = hist.tracked_corpora()
    texts = [c["text"] for c in controls.values()] + [t for items in corp.values() for _, t, _ in items]
    fidelity = adm.fidelity_check(texts)
    if fidelity:
        raise SystemExit(f"v13 replica differs from production on {len(fidelity)} texts")

    report = {
        "milestone": "M11-G20",
        "versions": {"parser": adm.JOB_DESCRIPTION_PARSER_VERSION, "scoring": SCORING_VERSION, "matcher": MATCHER_VERSION},
        "note": "research only; v13 replica asserted identical to production on every text below; no production "
                "code changed; synthetic controls are targeted probes, NOT prevalence estimates",
        "freezes": freezes,
        "replica_fidelity": {"texts_checked": len(texts), "mismatches": 0},
        "phase2_reproductions": [reproduce(n, label, cid, controls) for n, label, cid in PHASE2],
    }
    splits = {}
    for split in ("dev", "holdout"):
        per_policy = {}
        for p in (*FROZEN_POLICIES, *POSTHOC):
            results, agg = adm.run_split(split, p)
            entry = {"description": p.description, "posthoc": p in POSTHOC, "aggregate": agg}
            if p in DETAIL_POLICIES:
                entry["units"] = [{"id": r["id"], "family": r["family"], "pair": r["pair"], **{
                    k: u[k] for k in ("uid", "span", "kind", "qual", "gold_nec", "gold_section", "ambiguous",
                                      "outcome", "attribution", "section_kind", "row_necessities",
                                      "fabricated_concepts", "represented_tech", "policy_reason")},
                    "rows": [{k: x[k] for k in ("kind", "members", "category", "necessity", "span")} for x in u["rows"]],
                    "scoring_full_evidence": r["scoring"]["full"]} for r in results for u in r["units"]]
            per_policy[p.name] = entry
        splits[split] = per_policy
    report["controls"] = splits
    report["near_neighbor_pairs"] = _pairs(splits)
    hist_out = {}
    for p in (*pol.POLICIES, *POSTHOC):
        hist_out[p.name] = {
            "posthoc": p in POSTHOC,
            "corpora": {name: hist.corpus_impact(items, p) for name, items in corp.items()},
            "g17_containment": hist.g17_containment_preserved(p),
            "g6_g7_heading_kind_gold": heading_kind_divergence(p),
            "frozen_8c_v2_scores": hist.score_impact_8c(p),
        }
    report["historical_impact"] = hist_out
    report["result_provenance"] = {
        "production_behaviour": "only policy 'v13' (an asserted byte-identical replica of the production parser)",
        "simulation": "every other policy is an OFFLINE research simulation; none is implemented in src/gitscore",
        "development": "controls.dev -- the set the policies were designed against",
        "weakly_held_out_synthetic": "controls.holdout -- run once after policy_design_freeze.json; same author, "
                                     "could be recalled, NOT independent",
        "previously_inspected_private": "private_admission_aggregates.json -- previously inspected postings with "
                                        "pre-existing labels; NOT independent validation",
        "posthoc_policies": [p.name for p in POSTHOC],
        "posthoc_adjustments": [
            "EMPLOYER_SUBJECT was case-insensitive, so the country abbreviation 'US' matched the pronoun 'us'",
            "a concessive negation ('while not required, ... is a plus') was treated as a general negation",
        ],
        "posthoc_consequence": "both defects were found on the private label-backed postings, so B1NR/B1R/CR "
                               "results on those postings are post-hoc, not unseen; known risk for G21",
        "known_holdout_failure": "m11g20-h003 ('You must be on call ...') is admitted by every policy",
    }
    report["design_sets"] = {
        "designed_against": ["G20 dev controls", "G15", "G16", "G18", "M10D", "M10E", "G6", "G7", "8c job fixtures",
                             "M10 postings"],
        "held_out_from_design": ["G20 holdout controls (weakly: same author)",
                                 "private label-backed claim annotations (first run only; post-hoc variants were "
                                 "corrected after that run and are labelled posthoc)"],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_bytes((json.dumps(report, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
    for split in ("dev", "holdout"):
        for name, e in splits[split].items():
            a = e["aggregate"]
            print(f"{split:8s} {name:36s} falseAdm={a['1_false_admissions']['units_with_any_row']:2d}/"
                  f"{a['units']['non_qualification']} fab={a['3_fabricated_concepts']['total']} "
                  f"P={a['precision']['unit_admission_precision']} R={a['recall']['unit_recall']} "
                  f"nec={a['necessity_accuracy']['correct']}/{a['necessity_accuracy']['scored']}")
    if private:
        if not hist.private_available():
            raise SystemExit("--private-corpora requested but private sources are missing")
        priv = {"unlabeled_impact": {p.name: hist.private_impact(p) for p in (*pol.POLICIES, *POSTHOC)},
                "label_backed": hist.private_labeled_impact((*pol.POLICIES, *POSTHOC))}
        _assert_counts_only(priv)
        PRIVATE_OUT.write_bytes((json.dumps(priv, indent=1) + "\n").encode("utf-8"))
        print("private aggregates written (integer counts only)")


def _pairs(splits: dict) -> dict:
    out = {}
    for split, per in splits.items():
        for pname in ("v13", RECOMMENDED.name, pol.POLICY_C.name):
            units = per[pname]["units"]
            pairs: dict[str, list] = {}
            for u in units:
                if u["pair"]:
                    pairs.setdefault(u["pair"], []).append(u)
            ok = sum(1 for us in pairs.values()
                     if all(u["outcome"] == ("represented" if u["qual"] else "correctly_not_admitted") for u in us))
            out.setdefault(split, {})[pname] = {"pairs": len(pairs), "both_members_correct": ok}
    return out


def _assert_counts_only(obj, path="") -> None:
    allowed_str_keys = {"note", "description"}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and k not in allowed_str_keys:
                raise SystemExit(f"private aggregate field {path}/{k} is a string -- counts only")
            _assert_counts_only(v, f"{path}/{k}")
    elif isinstance(obj, list):
        raise SystemExit(f"private aggregate field {path} is a list -- counts only")


if __name__ == "__main__":
    main()
