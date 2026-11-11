"""Milestone 11-G22-R -- ambiguous alias and README evidence audit (research only).

    python scripts/evaluate_m11g22r_alias_evidence.py [--private-corpora] [--skip-test-runs]

Real parser v15, real evidence pipeline (readme:v4 and the language/Docker/manifest extractors),
real matcher and scoring v2. Candidate policies are offline adapters
(`scripts/evaluation_lib/m11g22r_policies.py`); no production code is changed and no LLM is called.

Writes `evaluation/m11g22r/alias_evidence_report.json` (public: synthetic controls, tracked public
fixtures, counts) and, with --private-corpora, `evaluation/m11g22r/private_alias_aggregates.json`
(integer counts only; previously inspected private postings -- job side only, there are no private
repositories).
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import evaluate_m11g22_concept_precision as g22  # noqa: E402
import gold_integrity as gi  # noqa: E402
import m11g22_concepts as g22h  # noqa: E402
import m11g22_policies as g22pol  # noqa: E402
import m11g22r_harness as h  # noqa: E402
import m11g22r_policies as rpol  # noqa: E402
from evaluation_lib import end_to_end_eval  # noqa: E402
from evaluation_lib.loaders import list_candidate_names, load_candidate_fixture, load_job  # noqa: E402
from gitscore.assessment import SCORING_VERSION, assess_job  # noqa: E402
from gitscore.concepts.registry import default_registry  # noqa: E402
from gitscore.evidence.capability import concept_capability  # noqa: E402
from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION as README_EXTRACTOR_VERSION  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION, parse_job_description_with_diagnostics  # noqa: E402
from gitscore.matching import MATCHER_VERSION, match_job  # noqa: E402

OUT = REPO_ROOT / "evaluation" / "m11g22r"
JOB_SIDE = {"BASE": g22pol.BASE, "A_job_generic_usage": g22pol.A, "C_shared_generic_usage": g22pol.A,
            "D_alias_metadata_split": g22pol.B, "DR_metadata_plus_corroboration": g22pol.B}
ERRATA = {"m11g22r-d22": "language.javascript"}  # see policy_design_freeze.json label_errata


# ---- freezes ------------------------------------------------------------------------------------
def freezes() -> dict:
    out = {}
    for split in ("dev", "eval"):
        rec = json.loads((OUT / f"{split}_hash_freeze.json").read_text(encoding="utf-8"))
        raw = (OUT / f"alias_evidence_controls_{split}.json").read_bytes()
        out[split] = {"sha256": rec["sha256"], "verified": gi.sha256(gi.canonical_bytes(raw)) == rec["sha256_lf_normalized"]}
    design = json.loads((OUT / "policy_design_freeze.json").read_text(encoding="utf-8"))
    out["policy_design"] = {f: {"sha256": s, "verified": gi.sha256(gi.canonical_bytes((REPO_ROOT / f).read_bytes())) == s}
                            for f, s in design["files"].items()}
    return out


# ---- controls -------------------------------------------------------------------------------------
def _errata_adjusted(results: list[dict]) -> int:
    return sum(len([i for i in r["readme_false_extraction"] if ERRATA.get(r["id"]) != i]) for r in results)


def controls() -> dict:
    out = {}
    for split in ("dev", "eval"):
        base_res, base_agg = h.run_split(split, rpol.BASE)
        by_id = {r["id"]: r for r in base_res}
        out[split] = {"BASE": {"aggregate": {**base_agg, "readme_false_extractions_errata_adjusted":
                                             _errata_adjusted(base_res)}, "results": base_res}}
        for p in rpol.POLICIES[1:]:
            res, agg = h.run_split(split, p)
            changed = []
            for r in res:
                b = by_id[r["id"]]
                keys = ("readme_false_extraction", "readme_genuine_extracted", "readme_mention_without_use",
                        "job_false_concepts", "job_missed_concepts", "false_supported", "score", "numerator",
                        "denominator")
                if any(r[k] != b[k] for k in keys):
                    changed.append({"id": r["id"], **{k: [b[k], r[k]] for k in keys if r[k] != b[k]}})
            out[split][p.name] = {"aggregate": {**agg, "readme_false_extractions_errata_adjusted": _errata_adjusted(res)},
                                  "changed_controls": changed}
    return out


def paired_matrix(results_by_split: dict) -> dict:
    cells: dict = {}
    for split, res in results_by_split.items():
        for r in res["BASE"]["results"]:
            if r["cell"] is None:
                continue
            cells.setdefault(str(r["cell"]), []).append(
                {"id": r["id"], "rows": [[x["members"], x["status"], x["counts"]] for x in r["rows"]],
                 "score": r["score"], "false_supported": [f["cause"] for f in r["false_supported"]]})
    return dict(sorted(cells.items(), key=lambda kv: int(kv[0])))


# ---- G19 capability what-if (alias-table approach) ----------------------------------------------
class _Reg:
    def __init__(self, override):
        self._r, self._o = default_registry(), override

    def get(self, cid):
        return self._o.get(cid) or self._r.get(cid)


def capability_whatif() -> dict:
    reg = default_registry()
    out = {}
    for alias in sorted(rpol.README_AMBIGUOUS_ALIASES):
        concept = next(c for c in reg.all_concepts() if alias in c.readme_safe_aliases())
        changed = dataclasses.replace(concept, readme_unsafe_aliases=concept.readme_unsafe_aliases | {alias})
        now = concept_capability(concept.concept_id)
        after = concept_capability(concept.concept_id, _Reg({concept.concept_id: changed}))
        sentence = f"Requirements:\n- Experience with {concept.display_name}."
        out[alias] = {"concept": concept.concept_id, "category": concept.category,
                      "capability_now": [now.capability.value, [p.value for p in now.pathways]],
                      "capability_if_alias_marked_unsafe": [after.capability.value, [p.value for p in after.pathways]],
                      "remaining_readme_safe_aliases": list(changed.readme_safe_aliases()),
                      "job_parser_would_still_recognise_display_name": any(
                          a.lower() == concept.display_name.lower() for a in changed.readme_safe_aliases()),
                      "probe_requirement": sentence}
    return out


def occurrence_guard_capability_unchanged() -> bool:
    """Occurrence guards (B, C, D) never touch the alias table, so G19 capability is identical."""
    reg = default_registry()
    before = {c.concept_id: concept_capability(c.concept_id) for c in reg.all_concepts()}
    ok = True
    for p in rpol.POLICIES:
        with rpol.applied(p):
            ok &= all(concept_capability(c.concept_id) == before[c.concept_id] for c in reg.all_concepts())
    return ok


# ---- historical: evidence side on the frozen 8c candidate fixtures -------------------------------
def _8c_profiles(policy) -> dict:
    names = list_candidate_names()
    with rpol.applied(policy):
        return end_to_end_eval.build_candidate_profiles({n: load_candidate_fixture(n) for n in names})


def _readme_set(profile) -> set:
    return {(e.repository.name, e.concept_id, e.raw_observation[:200]) for e in profile.evidence
            if e.evidence_type.value == "readme"}


def evidence_history() -> dict:
    base = _8c_profiles(rpol.BASE)
    matrices = {label: json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))["pairs"]
                for label, rel in (("8c_v1", "evaluation/gold/matrix.json"), ("8c_v1_1", "evaluation/gold_v1_1/matrix.json"))}
    names = {n.lower(): n for n in list_candidate_names()}

    def score(profiles, policy):
        out = {}
        for label, pairs in matrices.items():
            for p in pairs:
                prof = profiles[names[p["candidate"].lower()]]
                if policy.readme_only_insufficient:
                    prof = _corroborated(prof)
                with rpol.applied(policy):
                    parsed = parse_job_description_with_diagnostics(load_job(p["job_id"])["raw_text"])
                a = assess_job(match_job(prof, parsed.profile))
                out[f"{label}:{p['candidate']}/{p['job_id']}"] = {
                    "score": a.alignment_score, "denominator": a.assessable_count,
                    "statuses": sorted([list(h._members(m.requirement)), m.status.value, a.counts_toward_alignment(m)]
                                       for m in a.match_analysis.requirement_matches)}
        return out

    base_scores = score(base, rpol.BASE)
    out = {"readme_evidence_items_base": sum(len(_readme_set(p)) for p in base.values()), "policies": {}}
    for p in rpol.POLICIES[1:]:
        prof = _8c_profiles(p)
        removed = sorted([n, r, c] for n in base for (r, c, _) in _readme_set(base[n]) - _readme_set(prof[n]))
        added = sorted([n, r, c] for n in base for (r, c, _) in _readme_set(prof[n]) - _readme_set(base[n]))
        s = score(prof, p)
        changes = {k: {"base": [base_scores[k]["score"], base_scores[k]["denominator"]], "policy": [v["score"], v["denominator"]]}
                   for k, v in s.items() if (v["score"], v["denominator"]) != (base_scores[k]["score"], base_scores[k]["denominator"])}
        status_changed = sorted(k for k, v in s.items() if v["statuses"] != base_scores[k]["statuses"])
        if p.readme_only_insufficient:
            corr = {n: _corroborated(prof[n]) for n in prof}
            removed += sorted([n, r, c, "readme_only_dropped"] for n in base
                              for (r, c, _) in _readme_set(prof[n]) - _readme_set(corr[n]))
        out["policies"][p.name] = {"readme_evidence_removed": removed, "readme_evidence_added": added,
                                   "score_or_denominator_changed": changes, "status_changed_pairs": status_changed,
                                   "pairs": len(s)}
    return out


def _corroborated(profile):
    from gitscore.evidence.profile import build_candidate_evidence_profile
    from gitscore.evidence.types import EvidenceType
    corr = {e.concept_id for e in profile.evidence if e.evidence_type != EvidenceType.README}
    kept = [e for e in profile.evidence if e.evidence_type != EvidenceType.README or e.concept_id in corr]
    return build_candidate_evidence_profile(profile.candidate, profile.coverage.discovered, profile.coverage.analyzed,
                                            kept, collected_at=profile.collected_at)


# ---- historical: job side on v15 (G22's own functions; G22 policy objects) ------------------------
def job_history() -> dict:
    corp = g22.corpora()
    base = {n: g22.parse_corpus(items, g22pol.BASE) for n, items in corp.items()}
    inputs = g22.scoring_inputs()
    base_scores = {n: [g22._score_view(prof, text, g22pol.BASE) for _, prof, text, _ in items] for n, items in inputs.items()}
    out = {}
    for name, jp in (("G22_A (A, C job side)", g22pol.A), ("G22_B (D job side)", g22pol.B)):
        parsed = {n: g22.parse_corpus(items, jp) for n, items in corp.items()}
        out[name] = {
            "corpora": {n: g22.corpus_delta(base[n], parsed[n]) for n in corp},
            "g17_guard": g22.g17_guard(base["g16"], parsed["g16"], [i for i, _ in corp["g16"]]),
            "scoring": {n: g22.scoring_delta(base_scores[n], [g22._score_view(prof, text, jp) for _, prof, text, _ in items],
                                             items) for n, items in inputs.items()},
            "m10e_row_existence_mismatches": g22.m10e_row_existence(jp),
            "g22_controls": {split: g22h.run_split(split, jp)[1] for split in ("dev", "eval")},
        }
    out["BASE"] = {"m10e_row_existence_mismatches": g22.m10e_row_existence(g22pol.BASE),
                   "g22_controls": {split: g22h.run_split(split, g22pol.BASE)[1] for split in ("dev", "eval")}}
    return out


def g22q_equivalence_under_policies() -> dict:
    texts = {"G15-I1": "Experience with Kubernetes or k8s is required.", "G18-16": "Requirements:\n- Experience with Go or Golang",
             "React-or-reactjs": "Requirements:\n- Experience with React or ReactJS.",
             "Express-or-expressjs": "Requirements:\n- Experience with Express or Express.js."}
    out = {}
    for p in rpol.POLICIES:
        with rpol.applied(p):
            out[p.name] = {k: [[list(h._members(r)), r.category] for r in parse_job_description_with_diagnostics(t).profile.requirements]
                           for k, t in texts.items()}
    return out


# ---- regression risk: existing deterministic tests under each policy ------------------------------
TEST_FILES = ["tests/test_evidence_extraction_readme.py", "tests/test_evidence_extraction_readme_context.py",
              "tests/test_pipeline_evidence.py", "tests/test_candidate_evidence_profile.py",
              "tests/test_m11g19_observability_scoring_v2.py", "tests/test_evaluation_harness.py",
              "tests/test_m11g3_end_to_end_pathway.py", "tests/test_job_parser.py", "tests/test_job_parser_extraction.py",
              "tests/test_m11g22q_canonical_alias_equivalence.py"]


def existing_tests_under_policies() -> dict:
    files = [f for f in TEST_FILES if (REPO_ROOT / f).exists()]
    out = {"files": files}
    for p in rpol.POLICIES:
        if p.readme_only_insufficient:
            continue  # R is a matcher-semantics study applied to profiles, not an extractor patch
        env = {**os.environ, "M11G22R_POLICY": p.name,
               "PYTHONPATH": os.pathsep.join([str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"),
                                              str(REPO_ROOT / "scripts" / "evaluation_lib")])}
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "m11g22r_pytest_policy",
                               "--tb=no", "-rf", *files], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        tail = [l for l in proc.stdout.splitlines() if re.search(r"\d+ (passed|failed)", l)]
        summary = tail[-1] if tail else proc.stdout[-300:]
        out[p.name] = {"summary": re.sub(r"\s+in\s+[\d.]+s.*$", "", summary).strip(),  # timing is not reproducible
                       "failed": sorted(l.split(" - ")[0].replace("FAILED ", "") for l in proc.stdout.splitlines()
                                        if l.startswith("FAILED"))}
    return out


# ---- private (counts only; job side) -------------------------------------------------------------
def build_private() -> dict:
    base = g22.private_counts(g22pol.BASE)
    agg = {"note": "previously inspected private postings -- NOT independent validation; integer counts only; job side "
                   "only (no private repositories exist)"}
    for label, jp in (("G22_A", g22pol.A), ("G22_B", g22pol.B)):
        n = g22.private_counts(jp)
        agg[label] = {k: {"postings": b["postings"], **{f"{kk}_base": b[kk] for kk in b if kk not in ("postings", "_per")},
                          **{f"{kk}_policy": n[k][kk] for kk in n[k] if kk not in ("postings", "_per")},
                          "postings_changed": sum(1 for x, y in zip(b["_per"], n[k]["_per"]) if x != y)}
                      for k, b in base.items()}
    g22._assert_ints({k: v for k, v in agg.items() if k != "note"})
    return agg


def encode(obj) -> bytes:
    return (json.dumps(obj, indent=1, ensure_ascii=False, default=lambda o: dict(o) if isinstance(o, Counter) else str(o))
            + "\n").encode("utf-8")


def build_report(run_tests: bool = True) -> dict:
    ctl = controls()
    return {
        "versions": {"parser": JOB_DESCRIPTION_PARSER_VERSION, "scoring": SCORING_VERSION, "matcher": MATCHER_VERSION,
                     "readme_extractor": README_EXTRACTOR_VERSION},
        "note": "research only: real parser v15 / evidence pipeline / matcher / scoring v2; candidate policies are offline "
                "adapters (scripts/evaluation_lib/m11g22r_policies.py); no production code changed; no LLM",
        "freezes": freezes(),
        "labels": {"dev": "design set (policies designed against it)",
                   "eval": "same author; run only after the policy design freeze: weakly held out, NOT independent",
                   "errata": {k: f"genuine mention of {v} omitted from the frozen label" for k, v in ERRATA.items()}},
        "policies": {p.name: p.description for p in rpol.POLICIES},
        "controls": ctl,
        "paired_matrix_base": paired_matrix(ctl),
        "capability": {"occurrence_guards_leave_capability_unchanged": occurrence_guard_capability_unchanged(),
                       "alias_table_whatif": capability_whatif()},
        "g22q_equivalence_under_policies": g22q_equivalence_under_policies(),
        "historical_evidence_8c": evidence_history(),
        "historical_job_side_v15": job_history(),
        "existing_tests_under_policies": existing_tests_under_policies() if run_tests else "skipped",
    }


def main() -> None:
    if JOB_DESCRIPTION_PARSER_VERSION != "job_description_parser:v15" or SCORING_VERSION != "github_evidence_alignment:v2":
        raise SystemExit("G22-R describes parser v15 / scoring v2")
    report = build_report(run_tests="--skip-test-runs" not in sys.argv)
    (OUT / "alias_evidence_report.json").write_bytes(encode(report))
    for split in ("dev", "eval"):
        for name, v in report["controls"][split].items():
            a = v["aggregate"]
            print(split, name.ljust(32), {k: a[k] for k in ("readme_false_extractions", "readme_false_extractions_errata_adjusted",
                                                            "readme_mention_without_use_extractions", "readme_genuine_recall",
                                                            "job_false_concepts", "false_supported", "true_supported",
                                                            "missed_true_supported")})
    print("capability unchanged by occurrence guards:", report["capability"]["occurrence_guards_leave_capability_unchanged"])
    for alias, v in report["capability"]["alias_table_whatif"].items():
        print("  whatif", alias, v["capability_now"], "->", v["capability_if_alias_marked_unsafe"],
              "job still recognises display name:", v["job_parser_would_still_recognise_display_name"])
    for name, v in report["historical_evidence_8c"]["policies"].items():
        print("8c", name, "readme removed", len(v["readme_evidence_removed"]), "added", len(v["readme_evidence_added"]),
              "score changes", len(v["score_or_denominator_changed"]), "status changes", len(v["status_changed_pairs"]))
    for name, v in report["historical_job_side_v15"].items():
        if "corpora" in v:
            print("job", name, {n: (d["texts_changed"], d["registry_ids_removed"]) for n, d in v["corpora"].items() if d["texts_changed"]},
                  "g17", v["g17_guard"]["alternative_rows_changed"],
                  "scoring", {n: (len(d["score_changed"]), d["g16_claim_false_supported"]) for n, d in v["scoring"].items()})
    if report["existing_tests_under_policies"] != "skipped":
        for name, v in report["existing_tests_under_policies"].items():
            if name != "files":
                print("tests", name, v["summary"], v["failed"][:12])
    if "--private-corpora" in sys.argv:
        agg = build_private()
        (OUT / "private_alias_aggregates.json").write_bytes((json.dumps(agg, indent=1) + "\n").encode("utf-8"))
        for label in ("G22_A", "G22_B"):
            print("[private]", label, {k: v["postings_changed"] for k, v in agg[label].items()})


if __name__ == "__main__":
    main()
