"""Milestone 11-G22-R3 -- README context guard validation (research; readme:v5 NOT implemented).

    python scripts/evaluate_m11g22r3_readme_guard.py [--private-corpora]

Real parser v15, real evidence pipeline (readme:v4 + language / Docker / manifest extractors), matcher v1 and
scoring v2. README policies are offline adapters: G22-R2's A (production), D (unchanged), D2 (post-hoc) and G22-R3's
revised R3 (`scripts/evaluation_lib/m11g22r3_policies.py`). No production code, registry data or LLM.

Validation sets (`evaluation/m11g22r3/`): VAL-1 and VAL-2, written by a separate author blind to Policy D and frozen
before anything ran on them. VAL-1 validates D unchanged and then became R3's design set; VAL-2 was run once, after
R3 and its acceptance criteria were frozen. Writes `readme_guard_report.json` and, with --private-corpora,
`private_readme_guard_aggregates.json` (integer counts only; job postings, which README policies cannot reach).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import evaluate_m11g22r2_readme_context as r2  # noqa: E402
import gold_integrity as gi  # noqa: E402
import m11g22r2_harness as h  # noqa: E402
import m11g22r2_policies as p2  # noqa: E402
import m11g22r2_posthoc as ph  # noqa: E402
import m11g22r3_policies as p3  # noqa: E402
from gitscore.assessment import SCORING_VERSION  # noqa: E402
from gitscore.concepts.registry import CONCEPT_REGISTRY_VERSION, default_registry  # noqa: E402
from gitscore.evidence.capability import concept_capability  # noqa: E402
from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION, evidence_from_readme  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION  # noqa: E402
from gitscore.matching import MATCHER_VERSION  # noqa: E402

OUT = REPO_ROOT / "evaluation" / "m11g22r3"
VAL_POLICIES = (p2.A, p2.D, ph.D2, p3.R3)
ROLES = {
    "val1": {"D_hybrid_use_frames": "validation (unseen by D's design)",
             "D2_posthoc_d_plus_lead_ins": "comparison only (D2 is post-hoc from G22-R2; never authorized)",
             "R3_context_guard": "DESIGN SET for R3 (R3 was written after D's VAL-1 run): NOT validation"},
    "val2": {"D_hybrid_use_frames": "unseen", "D2_posthoc_d_plus_lead_ins": "comparison only (post-hoc, unauthorized)",
             "R3_context_guard": "held-out validation: run once after R3 and its acceptance criteria were frozen"},
}
AGG_KEYS = ("false_supported", "false_supported_by_probe_class", "false_readme_evidence_ordinary",
            "nonuse_readme_evidence", "ordinary_correctly_rejected", "use_claims_retained", "genuine_use_lost",
            "corroborated_supported", "true_supported", "missed_true_supported", "true_not_supported", "uncertain",
            "numerator", "denominator", "readme_items_by_label_class", "unlabelled_readme_concepts")


@contextmanager
def r2_policies(policies):
    saved = r2.ALL
    r2.ALL = tuple(policies)
    try:
        yield
    finally:
        r2.ALL = saved


def _ambiguous_concepts() -> set[str]:
    return {c.concept_id for c in default_registry().all_concepts()
            if any(a in p2.AMBIGUOUS for a in c.readme_safe_aliases())}


def load(split: str) -> list[dict]:
    return json.loads((OUT / f"validation_controls_{split}.json").read_text(encoding="utf-8"))["controls"]


# ---- freezes ----------------------------------------------------------------------------------------
def freezes() -> dict:
    out = {}
    for split in ("val1", "val2"):
        rec = json.loads((OUT / f"{split}_hash_freeze.json").read_text(encoding="utf-8"))
        raw = (OUT / f"validation_controls_{split}.json").read_bytes()
        out[split] = {"sha256": rec["sha256"], "frozen_at_utc": rec["frozen_at_utc"],
                      "verified": gi.sha256(gi.canonical_bytes(raw)) == rec["sha256"],
                      "controls": len(json.loads(raw)["controls"])}
    design = json.loads((OUT / "policy_design_freeze.json").read_text(encoding="utf-8"))
    out["policy_design"] = {"frozen_at_utc": design["frozen_at_utc"],
                            "files_verified": all(gi.sha256(gi.canonical_bytes((REPO_ROOT / f).read_bytes())) == s
                                                  for f, s in design["files"].items()),
                            "val2_hash_matches": design["val2_controls_sha256"] == out["val2"]["sha256"],
                            "frozen_after_val_sets": design["frozen_at_utc"] > out["val2"]["frozen_at_utc"]}
    out["g22r2"] = r2.freezes()
    return out


# ---- validation sets ----------------------------------------------------------------------------------
def _row_diff(a: dict, r: dict, amb: set[str]) -> dict:
    return {"id": r["id"], "family": r["family"], "probe": r["probe"],
            "outcome": [a["outcome"], r["outcome"]], "status": [a["probe_status"], r["probe_status"]],
            "score": [a["score"], r["score"]], "numerator": [a["numerator"], r["numerator"]],
            "denominator": [a["denominator"], r["denominator"]],
            "readme_items_removed": {k: v for k, v in a["readme_concepts"].items() if k not in r["readme_concepts"]},
            "readme_items_added": {k: v for k, v in r["readme_concepts"].items() if k not in a["readme_concepts"]},
            "non_ambiguous_item_changed": any(k not in amb for k in set(a["readme_concepts"]) ^ set(r["readme_concepts"]))}


def run_val(split: str) -> dict:
    ctrl = load(split)
    amb = _ambiguous_concepts()
    results = {p.name: [h.run_control(c, p) for c in ctrl] for p in VAL_POLICIES}
    base = {r["id"]: r for r in results[p2.A.name]}
    out = {}
    for p in VAL_POLICIES:
        agg = h.aggregate(results[p.name], ctrl)
        entry = {"role": ROLES[split].get(p.name, "baseline (production readme:v4)"),
                 "aggregate": {k: agg[k] for k in AGG_KEYS}}
        if p is not p2.A:
            changed = [_row_diff(base[r["id"]], r, amb) for r in results[p.name]
                       if base[r["id"]]["readme_concepts"] != r["readme_concepts"] or base[r["id"]]["outcome"] != r["outcome"]]
            removed = Counter(f"{cid}|{cls}" for row in changed for cid, cls in row["readme_items_removed"].items())
            entry.update({
                "changed_controls": changed,
                "readme_items_removed_by_concept_and_label": dict(sorted(removed.items())),
                "status_changes": dict(sorted(Counter(f"{row['status'][0]}->{row['status'][1]}" for row in changed
                                                      if row["status"][0] != row["status"][1]).items())),
                "new_false_supported_vs_readme_v4": sorted(r["id"] for r in results[p.name]
                                                           if r["outcome"] == "false_supported"
                                                           and base[r["id"]]["outcome"] != "false_supported"),
                "residual_false_supported": sorted([r["id"], r["probe"], r["probe_class"]] for r in results[p.name]
                                                   if r["outcome"] == "false_supported"),
                "missed_true_supported": sorted([r["id"], r["probe"]] for r in results[p.name] if r["outcome"] == "missed"),
                "genuine_use_items_lost": sorted([row["id"], cid, row["outcome"][1]] for row in changed
                                                 for cid, cls in row["readme_items_removed"].items() if cls == "use"),
                "non_ambiguous_items_changed": sum(1 for row in changed if row["non_ambiguous_item_changed"]),
            })
        out[p.name] = entry
    return out


def acceptance(val: dict, policy: str) -> dict:
    """The criteria frozen in policy_design_freeze.json BEFORE VAL-2 ran, evaluated exactly as declared."""
    a, d, p = (val[n]["aggregate"] for n in (p2.A.name, p2.D.name, policy))
    entry = val[policy]
    use_a, use_d, use_p = a["use_claims_retained"][0], d["use_claims_retained"][0], p["use_claims_retained"][0]
    checks = {
        "1_false_supported_reduction": [p["false_supported"], a["false_supported"],
                                        p["false_supported"] <= 0.5 * a["false_supported"]],
        "2_no_new_false_supported": [len(entry["new_false_supported_vs_readme_v4"]), 0,
                                     not entry["new_false_supported_vs_readme_v4"]],
        "3_corroborated": [p["corroborated_supported"][0], p["corroborated_supported"][1],
                           p["corroborated_supported"][0] == p["corroborated_supported"][1]],
        "4_genuine_use_items": [use_p, use_a, use_p >= 0.85 * use_a and use_p >= use_d],
        "5_requirement_recall": [p["true_supported"], a["true_supported"], p["true_supported"] >= 0.9 * a["true_supported"]],
        "6_ordinary": [p["false_supported_by_probe_class"].get("ordinary", 0), 1,
                       p["false_supported_by_probe_class"].get("ordinary", 0) <= 1],
        "7_non_ambiguous": [entry["non_ambiguous_items_changed"], 0, entry["non_ambiguous_items_changed"] == 0],
    }
    return {"checks": checks, "passed": all(v[2] for v in checks.values())}


def named_phrases() -> list:
    rows = []
    phrases = ("image diffing in Rust", "python plotting helper", "Analysis with pandas", "trained with torch",
               "store in Rust", "API design borrowed from Express", "free of rust", "local and express trains")
    ctrl = [c for c in load("val1") if c["family"] == "named_phrase"]
    for phrase in phrases:
        (c,) = [x for x in ctrl if any(phrase in r["readme"] for r in x["repos"])]
        row = {"phrase": phrase, "id": c["id"], "probe": c["probe"], "author_label": c["concepts"].get(c["probe"]),
               "used": c["probe"] in c["used"], "outcome": {}, "readme_item_kept": {}}
        for p in VAL_POLICIES:
            r = h.run_control(c, p)
            row["outcome"][p.name] = r["outcome"]
            row["readme_item_kept"][p.name] = c["probe"] in r["readme_concepts"]
        rows.append(row)
    return rows


# ---- capability contract (Phase 9) -----------------------------------------------------------------------
def capability_contract() -> dict:
    """Every registered concept with a README-safe alias, in a valid technical context, under every policy."""
    reg = default_registry()
    out = {}
    for p in (p2.A, p2.D, p3.R3):
        lost = []
        with p2.applied(p):
            for c in reg.all_concepts():
                for alias in c.readme_safe_aliases():
                    text = f"# demo\n\nThis project is built with {alias}.\n"
                    if c.concept_id not in {e.concept_id for e in evidence_from_readme("o", "r", text, "README.md")}:
                        lost.append([c.concept_id, alias])
        out[p.name] = {"aliases_checked": sum(len(c.readme_safe_aliases()) for c in reg.all_concepts()),
                       "valid_context_not_extracted": lost,
                       "capability": {c.concept_id: [concept_capability(c.concept_id).capability.value,
                                      sorted(p.value for p in concept_capability(c.concept_id).pathways)]
                                     for c in reg.all_concepts()}}
    return out


def encode(obj) -> bytes:
    return (json.dumps(obj, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def build_report() -> dict:
    val1, val2 = run_val("val1"), run_val("val2")
    acc = {"R3_on_val2": acceptance(val2, p3.R3.name), "D_on_val2": acceptance(val2, p2.D.name),
           "D_on_val1": acceptance(val1, p2.D.name)}
    # the recorded decision below is only true while the frozen criteria fail; never let it drift from the measurement
    assert not acc["R3_on_val2"]["passed"] and not acc["D_on_val2"]["passed"] and not acc["D_on_val1"]["passed"]
    with r2_policies((p2.A, p2.D, p3.R3)):
        g22r = r2.g22r_controls()
        hist = r2.history_8c()
        inv = r2.capability_and_job_side_unaffected()
    with r2_policies((p2.A, p2.D, ph.D2, p3.R3)):
        difficult = r2.difficult_cases()
    r2_controls = {s: {p.name: {k: v for k, v in h.run_split(s, p)[1].items() if k in AGG_KEYS}
                       for p in (p2.A, p2.D, p3.R3)} for s in ("dev", "eval")}
    return {
        "versions": {"parser": JOB_DESCRIPTION_PARSER_VERSION, "scoring": SCORING_VERSION, "matcher": MATCHER_VERSION,
                     "readme_extractor": EXTRACTOR_VERSION, "registry": CONCEPT_REGISTRY_VERSION},
        "note": "research only: real parser v15 / evidence pipeline readme:v4 / matcher v1 / scoring v2; README "
                "policies are offline adapters; no production or registry change; no LLM",
        "decision": {
            "readme_v5_implemented": False,
            "reason": "Neither D unchanged nor the revised R3 met the recall criteria frozen before VAL-2 ran "
                      "(>= 85% of readme:v4's genuine README use items and >= 90% of its true SUPPORTED probes). "
                      "Precision criteria passed. Per the frozen rule, readme:v5 is not implemented.",
        },
        "freezes": freezes(),
        "provenance": json.loads((OUT / "author_provenance.json").read_text(encoding="utf-8")),
        "policies": {p.name: p.description for p in VAL_POLICIES},
        "val1": val1,
        "val2": val2,
        "acceptance": acc,
        "named_phrases": named_phrases(),
        "g22r2_controls": r2_controls,
        "g22r_frozen_controls": g22r,
        "historical_8c_simulated": hist,
        "difficult_cases": difficult,
        "capability_contract": capability_contract(),
        "invariants": inv,
    }


def build_private() -> dict:
    with r2_policies((p2.A, p2.D, p3.R3)):
        return r2.build_private()


def main() -> None:
    if (JOB_DESCRIPTION_PARSER_VERSION, SCORING_VERSION, EXTRACTOR_VERSION, MATCHER_VERSION) != \
            ("job_description_parser:v15", "github_evidence_alignment:v2", "readme:v4", "requirement_matcher:v1"):
        raise SystemExit("G22-R3 describes parser v15 / scoring v2 / readme:v4 / matcher v1")
    report = build_report()
    (OUT / "readme_guard_report.json").write_bytes(encode(report))
    for split in ("val1", "val2"):
        for name, v in report[split].items():
            a = v["aggregate"]
            print(split, name.ljust(28), "FS", a["false_supported"], "ordinaryREADME", a["false_readme_evidence_ordinary"],
                  "use", a["use_claims_retained"], "trueSUP", a["true_supported"], "missed", a["missed_true_supported"],
                  "corr", a["corroborated_supported"], "|", v["role"])
    for k, v in report["acceptance"].items():
        print("acceptance", k, v["passed"], {c: x[2] for c, x in v["checks"].items()})
    print("decision", report["decision"])
    if "--private-corpora" in sys.argv:
        agg = build_private()
        (OUT / "private_readme_guard_aggregates.json").write_bytes((json.dumps(agg, indent=1) + "\n").encode("utf-8"))
        print("[private]", {k: {kk: vv["postings_changed"] for kk, vv in v.items()} for k, v in agg.items() if k != "note"})


if __name__ == "__main__":
    main()
