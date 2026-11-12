"""Milestone 11-G22-R2 -- README evidence context and confidence (research only).

    python scripts/evaluate_m11g22r2_readme_context.py [--private-corpora] [--skip-test-runs]

Real parser v15, real evidence pipeline (readme:v4 + language / Docker / manifest extractors), matcher v1 and
scoring v2. Candidate README policies are offline adapters (`scripts/evaluation_lib/m11g22r2_policies.py`); no
production code is changed, no registry data is changed and no LLM is called.

Writes `evaluation/m11g22r2/readme_context_report.json` (public: synthetic controls, tracked public 8c fixtures,
counts) and, with --private-corpora, `evaluation/m11g22r2/private_readme_context_aggregates.json` (integer counts
only; the private material is job postings, which README policies cannot reach -- verified, not assumed).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import evaluate_m11g22_concept_precision as g22  # noqa: E402
import evaluate_m11g22r_alias_evidence as g22r_runner  # noqa: E402
import gold_integrity as gi  # noqa: E402
import m11g22_concepts as g22h  # noqa: E402
import m11g22_policies as g22pol  # noqa: E402
import m11g22r2_harness as h  # noqa: E402
import m11g22r2_policies as p2  # noqa: E402
import m11g22r2_posthoc as ph  # noqa: E402
import m11g22r_harness as h22r  # noqa: E402
import m11g22r_policies as rpol  # noqa: E402
from evaluation_lib import end_to_end_eval  # noqa: E402
from evaluation_lib.loaders import list_candidate_names, load_candidate_fixture, load_job  # noqa: E402
from gitscore.assessment import SCORING_VERSION, assess_job  # noqa: E402
from gitscore.concepts.registry import CONCEPT_REGISTRY_VERSION, default_registry  # noqa: E402
from gitscore.evidence.capability import concept_capability  # noqa: E402
from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION, evidence_from_readme  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION, parse_job_description_with_diagnostics  # noqa: E402
from gitscore.matching import MATCHER_VERSION, match_job  # noqa: E402

OUT = REPO_ROOT / "evaluation" / "m11g22r2"
ALL = (*p2.POLICIES, *ph.POSTHOC)  # D2 is POST-HOC (after EVAL), reported separately

# POST-HOC manual review of every README item a policy removes from the frozen 8c fixtures (public READMEs). Written
# AFTER seeing the removals; it judges whether the removed occurrence claimed THIS repository's use. Not gold.
REVIEW_8C = {
    ("torvalds", "libgit2", "language.java"): "reference: other projects' language bindings list",
    ("torvalds", "libgit2", "language.python"): "reference: other projects' language bindings list",
    ("torvalds", "libgit2", "language.ruby"): "reference: other projects' language bindings list",
    ("torvalds", "libgit2", "language.rust"): "reference: other projects' language bindings list",
    ("torvalds", "libgit2", "language.swift"): "reference: other projects' language bindings list",
    ("sindresorhus", "file-type", "language.java"): "reference: a file format ('Java class file')",
    ("karpathy", "char-rnn", "language.python"): "reference: a separate gist, not this repository",
    ("sindresorhus", "Gifski", "language.rust"): "use: build requirement of this app",
    ("torvalds", "AudioNoise", "language.python"): "use: the repository ships a python visualizer",
    ("karpathy", "llm-council", "framework.react"): "use: '**Frontend:** React + Vite' stack line",
}


# ---- freezes ------------------------------------------------------------------------------------
def freezes() -> dict:
    out = {}
    for split in ("dev", "eval"):
        rec = json.loads((OUT / f"{split}_hash_freeze.json").read_text(encoding="utf-8"))
        raw = (OUT / f"readme_context_controls_{split}.json").read_bytes()
        out[split] = {"sha256": rec["sha256"],
                      "verified": gi.sha256(gi.canonical_bytes(raw)) == rec["sha256_lf_normalized"] == rec["sha256"]}
    design = json.loads((OUT / "policy_design_freeze.json").read_text(encoding="utf-8"))
    out["policy_design"] = {f: {"sha256": s, "verified": gi.sha256(gi.canonical_bytes((REPO_ROOT / f).read_bytes())) == s}
                            for f, s in design["files"].items()}
    return out


# ---- new controls -----------------------------------------------------------------------------------
_KEYS = ("readme_concepts", "probe_status", "probe_evidence_types", "outcome", "numerator", "denominator", "score")


def controls() -> dict:
    out = {}
    for split in ("dev", "eval"):
        base, base_agg = h.run_split(split, p2.A)
        by_id = {r["id"]: r for r in base}
        base_agg.pop("_ids_with_unregistered")
        out[split] = {p2.A.name: {"aggregate": base_agg, "results": base}}
        for p in ALL[1:]:
            res, agg = h.run_split(split, p)
            agg.pop("_ids_with_unregistered")
            changed = [{"id": r["id"], **{k: [by_id[r["id"]][k], r[k]] for k in _KEYS if r[k] != by_id[r["id"]][k]}}
                       for r in res if any(r[k] != by_id[r["id"]][k] for k in _KEYS)]
            out[split][p.name] = {"aggregate": agg, "changed_controls": changed,
                                  "residual_false_supported": [r["id"] for r in res if r["outcome"] == "false_supported"],
                                  "missed_true_supported": [r["id"] for r in res if r["outcome"] == "missed"]}
    return out


# ---- G22-R frozen controls under the R2 policies -----------------------------------------------------------
@contextmanager
def _g22r_profile_hook(policy):
    saved = h22r.candidate_profile

    def hooked(control, rp):
        return p2.interpret(saved(control, rp), policy)
    h22r.candidate_profile = hooked
    try:
        yield
    finally:
        h22r.candidate_profile = saved


def g22r_controls() -> dict:
    out = {"reproduced_g22r": {}}
    for split in ("dev", "eval"):
        for rp in (rpol.BASE, rpol.D, rpol.R):
            res, a = h22r.run_split(split, rp)
            out["reproduced_g22r"][f"{split}:{rp.name}"] = {
                "false_supported": a["false_supported"], "readme_genuine_recall": a["readme_genuine_recall"],
                "readme_false_extractions_raw": a["readme_false_extractions"],
                "readme_false_extractions_errata_adjusted": g22r_runner._errata_adjusted(res)}
    for p in ALL:
        rp = rpol.Policy(p.name, readme_rule=p.rule)
        out[p.name] = {}
        for split in ("dev", "eval"):
            with _g22r_profile_hook(p):
                res, a = h22r.run_split(split, rp)
            out[p.name][split] = {k: a[k] for k in ("readme_false_extractions", "readme_mention_without_use_extractions",
                                                     "readme_genuine_recall", "false_supported", "false_supported_by_cause",
                                                     "true_supported", "missed_true_supported", "numerator", "denominator")}
            out[p.name][split]["readme_false_extractions_errata_adjusted"] = g22r_runner._errata_adjusted(res)
    return out


# ---- frozen 8c fixtures (real public READMEs) ------------------------------------------------------
def _8c_profiles(policy):
    with p2.applied(policy):
        prof = end_to_end_eval.build_candidate_profiles({n: load_candidate_fixture(n) for n in list_candidate_names()})
    return {n: p2.interpret(p, policy) for n, p in prof.items()}


def _readme_items(profs):
    return {(n, e.repository.name, e.concept_id): e.raw_observation for n, p in profs.items() for e in p.evidence
            if e.evidence_type.value == "readme"}


def _matrix_scores(profs) -> dict:
    names = {n.lower(): n for n in list_candidate_names()}
    out = {}
    for label, rel in (("8c_v1", "evaluation/gold/matrix.json"), ("8c_v1_1", "evaluation/gold_v1_1/matrix.json")):
        for pair in json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))["pairs"]:
            a = assess_job(match_job(profs[names[pair["candidate"].lower()]],
                                     parse_job_description_with_diagnostics(load_job(pair["job_id"])["raw_text"]).profile))
            ms = a.match_analysis.requirement_matches
            out[f"{label}:{pair['candidate']}/{pair['job_id']}"] = {
                "score": a.alignment_score, "denominator": a.assessable_count,
                "numerator": sum(1 for m in ms if m.status.value == "supported" and a.counts_toward_alignment(m)),
                "statuses": sorted([list(h22r._members(m.requirement)), m.status.value] for m in ms)}
    return out


def history_8c() -> dict:
    base = _8c_profiles(p2.A)
    b_items = _readme_items(base)
    b_concepts = {(n, e.concept_id) for n, p in base.items() for e in p.evidence}
    b_scores = _matrix_scores(base)
    out = {"readme_items_base": len(b_items), "policies": {}}
    for p in ALL[1:]:
        prof = _8c_profiles(p)
        n_items = _readme_items(prof)
        n_concepts = {(n, e.concept_id) for n, pr in prof.items() for e in pr.evidence}
        removed = sorted(set(b_items) - set(n_items))
        s = _matrix_scores(prof)
        out["policies"][p.name] = {
            "readme_items_removed": [[*k, REVIEW_8C.get(k, "unreviewed"), (k[0], k[2]) not in n_concepts] for k in removed],
            "readme_items_added": sorted([*k] for k in set(n_items) - set(b_items)),
            "readme_items_moved_to_another_occurrence": sum(1 for k in set(b_items) & set(n_items) if b_items[k] != n_items[k]),
            "concepts_lost_entirely": sorted([*k] for k in b_concepts - n_concepts),
            "removed_reviewed_reference": sum(1 for k in removed if REVIEW_8C.get(k, "").startswith("reference")),
            "removed_reviewed_use": sum(1 for k in removed if REVIEW_8C.get(k, "").startswith("use")),
            "removed_unreviewed": sum(1 for k in removed if k not in REVIEW_8C),
            "score_changes": {k: [[b_scores[k]["numerator"], b_scores[k]["denominator"], b_scores[k]["score"]],
                                  [v["numerator"], v["denominator"], v["score"]]]
                              for k, v in s.items() if (v["score"], v["denominator"], v["numerator"]) !=
                              (b_scores[k]["score"], b_scores[k]["denominator"], b_scores[k]["numerator"])},
            "status_changed_pairs": sorted(k for k, v in s.items() if v["statuses"] != b_scores[k]["statuses"]),
            "became_undefined": sorted(k for k, v in s.items() if v["score"] is None and b_scores[k]["score"] is not None),
        }
    return out


def readme_semantics_8c() -> dict:
    """Phase 8: what the uniform MODERATE README label covers on the real fixtures (current readme:v4)."""
    base = _8c_profiles(p2.A)
    kinds = Counter()
    for n, p in base.items():
        other = {(e.repository.name, e.concept_id) for e in p.evidence if e.evidence_type.value != "readme"}
        anywhere = {e.concept_id for e in p.evidence if e.evidence_type.value != "readme"}
        for e in p.evidence:
            if e.evidence_type.value != "readme":
                continue
            frame = p2.readme_item_has_use_frame(e.raw_observation)
            corr = "same_repo" if (e.repository.name, e.concept_id) in other else (
                "other_repo" if e.concept_id in anywhere else "none")
            kinds[f"use_frame={frame}|corroboration={corr}"] += 1
    return {"readme_items": sum(kinds.values()), "by_use_frame_and_corroboration": dict(sorted(kinds.items())),
            "confidence_levels": sorted({e.confidence.name for p in base.values() for e in p.evidence
                                         if e.evidence_type.value == "readme"})}


# ---- difficult cases (Phase 6) -----------------------------------------------------------------------
DIFFICULT = [
    ("free of rust (ordinary)", "Keeps bike chains free of rust.", "language.rust", False),
    ("free of unsafe code (use)", "Written in Rust, free of unsafe code.", "language.rust", True),
    ("local and express trains", "Timetables for local and express trains.", "framework.express", False),
    ("Node and Express (use)", "A Node and Express backend.", "framework.express", True),
    ("capitalised Ruby, ordinary", "Shows the Ruby gemstone collection.", "language.ruby", False),
    ("capitalised Ruby + app collocate (TRAP)", "Ruby, our app's mascot, says hello.", "language.ruby", False),
    ("capitalised Java, ordinary", "Travel notes: Java is an island.", "language.java", False),
    ("capitalised Java + app collocate (TRAP)", "A Java coffee app for our cafe.", "language.java", False),
    ("python visualizer (use)", "Includes a python visualizer for the audio.", "language.python", True),
    ("python plotting helper (use)", "Ships a small python plotting helper.", "language.python", True),
    ("inspired by React (reference)", "A tiny view layer inspired by React.", "framework.react", False),
    ("borrowed from Express (reference)", "API design borrowed from Express.", "framework.express", False),
    ("bindings can be generated (future)", "Rust bindings can be generated with bindgen.", "language.rust", False),
    ("bindings are planned (future)", "Bindings for Rust are planned.", "language.rust", False),
    ("in Rust (use, no frame/collocate)", "Fast image diffing in Rust.", "language.rust", True),
    ("in Java, ordinary (D2 TRAP)", "Photos taken in Java last summer.", "language.java", False),
    ("trained with torch (use)", "Image classifier trained with torch.", "ml.framework.pytorch", True),
    ("with a torch, ordinary (D2 TRAP)", "Explore the cave with a torch.", "ml.framework.pytorch", False),
]


def difficult_cases() -> list:
    out = []
    for label, sentence, concept, genuine_use in DIFFICULT:
        text = f"# x\n\n{sentence}\n"
        row = {"case": label, "text": sentence, "concept": concept, "genuine_use": genuine_use, "extracted": {}}
        for p in ALL:
            with p2.applied(p):
                row["extracted"][p.name] = concept in {e.concept_id for e in evidence_from_readme("o", "r", text, "README.md")}
        out.append(row)
    return out


def g21_n10() -> dict:
    c = next(x for x in json.loads((REPO_ROOT / "evaluation/m11g21/negation_scope_controls.json").read_text(
        encoding="utf-8"))["controls"] if x["id"] == "m11g21-n10")
    return {"text": c["text"], "expected_rows": c["expected_rows"],
            "job_side_rows": {p.name: [[list(g22h.members(r)), r.necessity.value] for r in g22h.parse(c["text"], p)
                                       .profile.requirements] for p in (g22pol.BASE, g22pol.A, g22pol.B)},
            "readme_policies_affect_it": False,
            "diagnosis": "job-side only: claim-initial capital gives no casing cue and 'knowledge' is not in G22 B's "
                         "head-noun list; README policies never touch job parsing"}


# ---- invariants ----------------------------------------------------------------------------------------
def capability_and_job_side_unaffected() -> dict:
    reg = default_registry()
    cap_before = {c.concept_id: concept_capability(c.concept_id) for c in reg.all_concepts()}
    corp = g22.corpora()
    job_before = {n: g22.parse_corpus(items, g22pol.BASE) for n, items in corp.items()}
    out = {}
    for p in ALL[1:]:
        with p2.applied(p):
            cap_same = all(concept_capability(c.concept_id) == cap_before[c.concept_id] for c in reg.all_concepts())
            job_same = all(g22.parse_corpus(items, g22pol.BASE) == job_before[n] for n, items in corp.items())
        out[p.name] = {"capability_identical_for_all_concepts": cap_same, "job_parsing_identical_on_all_corpora": job_same}
    return out


TEST_FILES = ["tests/test_evidence_extraction_readme.py", "tests/test_evidence_extraction_readme_context.py",
              "tests/test_pipeline_evidence.py", "tests/test_candidate_evidence_profile.py",
              "tests/test_m11g19_observability_scoring_v2.py", "tests/test_evaluation_harness.py",
              "tests/test_m11g3_end_to_end_pathway.py", "tests/test_m11g22r_ambiguous_alias_evidence.py"]


def existing_tests_under_policies() -> dict:
    files = [f for f in TEST_FILES if (REPO_ROOT / f).exists()]
    out = {"files": files}
    for p in ALL:
        if p.corroboration_interpretation:
            continue  # profile reinterpretation is not an extractor patch
        env = {**os.environ, "M11G22R2_POLICY": p.name,
               "PYTHONPATH": os.pathsep.join([str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"),
                                              str(REPO_ROOT / "scripts" / "evaluation_lib")])}
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "m11g22r2_pytest_policy",
                               "--tb=no", "-rf", *files], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        tail = [l for l in proc.stdout.splitlines() if re.search(r"\d+ (passed|failed)", l)]
        out[p.name] = {"summary": re.sub(r"\s+in\s+[\d.]+s.*$", "", tail[-1] if tail else proc.stdout[-300:]).strip(),
                       "failed": sorted(l.split(" - ")[0].replace("FAILED ", "") for l in proc.stdout.splitlines()
                                        if l.startswith("FAILED"))}
    return out


def build_private() -> dict:
    base = g22.private_counts(g22pol.BASE)
    agg = {"note": "previously inspected private postings -- NOT independent validation; integer counts only; job "
                   "postings only (README policies cannot reach job parsing)"}
    for p in ALL[1:]:
        with p2.applied(p):
            n = g22.private_counts(g22pol.BASE)
        agg[p.name] = {k: {"postings": b["postings"],
                           "postings_changed": sum(1 for x, y in zip(b["_per"], n[k]["_per"]) if x != y)}
                       for k, b in base.items()}
    g22._assert_ints({k: v for k, v in agg.items() if k != "note"})
    return agg


def encode(obj) -> bytes:
    return (json.dumps(obj, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def build_report(run_tests: bool = True) -> dict:
    return {
        "versions": {"parser": JOB_DESCRIPTION_PARSER_VERSION, "scoring": SCORING_VERSION, "matcher": MATCHER_VERSION,
                     "readme_extractor": EXTRACTOR_VERSION, "registry": CONCEPT_REGISTRY_VERSION},
        "note": "research only: real parser v15 / evidence pipeline readme:v4 / matcher v1 / scoring v2; README "
                "policies are offline adapters; no production or registry change; no LLM",
        "freezes": freezes(),
        "labels": {"dev": "design set", "eval": "same author, run only after the policy design freeze: weakly held "
                                                "out, NOT independent",
                   "review_8c": "post-hoc manual review of removed public-fixture README items; not gold"},
        "policies": {p.name: p.description for p in ALL},
        "post_hoc_policies": {"names": [p.name for p in ph.POSTHOC],
                              "caveat": "written AFTER the EVAL run; EVAL, the G22-R controls and the 8c fixtures "
                                        "informed it, so its numbers are NOT validation"},
        "controls": controls(),
        "g22r_frozen_controls": g22r_controls(),
        "historical_8c": history_8c(),
        "readme_semantics_8c": readme_semantics_8c(),
        "difficult_cases": difficult_cases(),
        "g21_n10": g21_n10(),
        "invariants": capability_and_job_side_unaffected(),
        "existing_tests_under_policies": existing_tests_under_policies() if run_tests else "skipped",
    }


def main() -> None:
    if (JOB_DESCRIPTION_PARSER_VERSION, SCORING_VERSION, EXTRACTOR_VERSION, MATCHER_VERSION) != \
            ("job_description_parser:v15", "github_evidence_alignment:v2", "readme:v4", "requirement_matcher:v1"):
        raise SystemExit("G22-R2 describes parser v15 / scoring v2 / readme:v4 / matcher v1")
    report = build_report(run_tests="--skip-test-runs" not in sys.argv)
    (OUT / "readme_context_report.json").write_bytes(encode(report))
    for split in ("dev", "eval"):
        for name, v in report["controls"][split].items():
            a = v["aggregate"]
            print(split, name.ljust(32), "FS", a["false_supported"], "falseREADME", a["false_readme_evidence_ordinary"],
                  "nonuse", a["nonuse_readme_evidence"], "use", a["use_claims_retained"], "trueSUP", a["true_supported"],
                  "missed", a["missed_true_supported"], "corr", a["corroborated_supported"], "unc", a["uncertain"])
    for name, v in report["g22r_frozen_controls"].items():
        print("g22r", name, v)
    for name, v in report["historical_8c"]["policies"].items():
        print("8c", name, "removed", len(v["readme_items_removed"]), "ref", v["removed_reviewed_reference"], "use",
              v["removed_reviewed_use"], "unrev", v["removed_unreviewed"], "lost", len(v["concepts_lost_entirely"]),
              "score changes", len(v["score_changes"]), "undefined", v["became_undefined"])
    print("semantics", report["readme_semantics_8c"])
    for row in report["difficult_cases"]:
        print("case", row["case"].ljust(40), "genuine" if row["genuine_use"] else "nonuse ",
              {k.split("_")[0]: v for k, v in row["extracted"].items()})
    print("n10", report["g21_n10"]["job_side_rows"])
    print("invariants", report["invariants"])
    if report["existing_tests_under_policies"] != "skipped":
        for name, v in report["existing_tests_under_policies"].items():
            if name != "files":
                print("tests", name, v["summary"], v["failed"][:8])
    if "--private-corpora" in sys.argv:
        agg = build_private()
        (OUT / "private_readme_context_aggregates.json").write_bytes((json.dumps(agg, indent=1) + "\n").encode("utf-8"))
        print("[private]", {k: {kk: vv["postings_changed"] for kk, vv in v.items()} for k, v in agg.items() if k != "note"})


if __name__ == "__main__":
    main()
