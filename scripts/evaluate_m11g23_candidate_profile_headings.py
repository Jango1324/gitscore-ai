"""Milestone 11-G23 -- candidate-profile heading recovery: research runner (OFFLINE, research only).

    python scripts/evaluate_m11g23_candidate_profile_headings.py            # DEV + historical (design phase)
    python scripts/evaluate_m11g23_candidate_profile_headings.py --eval     # + the single frozen EVAL run

Writes `evaluation/m11g23/candidate_profile_report.json` (public: synthetic controls, public historical ids,
counts) and `evaluation/m11g23/private_candidate_profile_aggregates.json` (integer totals only; private texts
never leave the process). Real parser v15 / matcher v1 / scoring v2 throughout; only segmentation is replaced,
inside `m11g23_harness.active()`. No LLM, no network. The report carries no timestamps, absolute paths or G14
manifest counts, so it reproduces byte for byte.

`ACCEPTANCE_GATES` and `SELECTED` are part of the policy design freeze
(`evaluation/m11g23/policy_design_freeze.json`) and were fixed from DEV + historical results before EVAL ran.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import m11g23_eval as ev  # noqa: E402
import m11g23_harness as hz  # noqa: E402
import m11g23_historical as hi  # noqa: E402
import m11g23_policies as pol  # noqa: E402

from gitscore.assessment import SCORING_VERSION  # noqa: E402
from gitscore.concepts.registry import CONCEPT_REGISTRY_VERSION, default_registry  # noqa: E402
from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION  # noqa: E402
from gitscore.matching import MATCHER_VERSION  # noqa: E402

OUT_DIR = REPO_ROOT / "evaluation" / "m11g23"
REPORT = OUT_DIR / "candidate_profile_report.json"
PRIVATE = OUT_DIR / "private_candidate_profile_aggregates.json"
FROZEN_FILES = ("evaluation/m11g23/labelling_guide.md", "evaluation/m11g23/controls_dev.json",
                "evaluation/m11g23/controls_eval.json")
DESIGN_FILES = ("scripts/evaluation_lib/m11g23_policies.py", "scripts/evaluation_lib/m11g23_harness.py",
                "scripts/evaluation_lib/m11g23_eval.py", "scripts/evaluate_m11g23_candidate_profile_headings.py")

# ---- acceptance gates (frozen with the policy design; justified in the milestone document §6) ------------------
ACCEPTANCE_GATES = {
    "G1_recall_gain_abs_min": 0.20,          # selected strict recall - P0 strict recall (EVAL qualification units)
    "G1_units_gained_min": 15,               # newly recovered qualification units on EVAL
    "G2a_new_severe_false_admissions_max": 0,  # new duty/employer/benefits/process units with a registry row
    "G2b_new_false_admissions_per_recovered_max": 0.10,
    "G3_necessity_accuracy_min": 0.90,       # represented qualification units with gold required/preferred
    "G4_units_regressed_max": 0,             # units strictly recovered by P0 but not by the selected policy
    "G5_counted_non_technical_rows_max": 0,  # G19 capability: v2 never counts a non-technical row
    "G6_historical_sections_unchanged": [
        "corpora/g15", "corpora/g16", "corpora/g18", "corpora/m10d", "corpora/m10e", "corpora/g7",
        "corpora/8c_jobs", "scoring", "g13_or_contract", "controls/g21_adversarial", "negation_scope",
        "g22_controls", "g22_scoring", "m10e_g3", "m10e_row_existence_mismatches"],
    "G7_g20_false_admission_units_not_increased": True,
}
SEVERE_KINDS = {"responsibility", "company", "product", "stack", "team_practice", "tech_discussion", "benefits",
                "process"}
PRIVATE_SECTIONS = ("private_labeled", "private_unlabeled", "g22_private")


def _sha(rel: str) -> str:
    """Canonical (CRLF -> LF) SHA-256, so the recorded hash does not depend on core.autocrlf. Post-EVAL amendment
    (see `post_eval_amendments` in policy_design_freeze.json): the frozen runner hashed raw bytes."""
    return hashlib.sha256((REPO_ROOT / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _strip_per_posting(o):
    """Private dump sections reduced to integer / ratio TOTALS (no per-posting vectors)."""
    if isinstance(o, dict):
        return {k: _strip_per_posting(v) for k, v in o.items() if k not in ("per_posting", "_per")}
    return o


def _dump(policy_name: str, tmp: Path) -> dict:
    out = tmp / f"{policy_name}.json"
    subprocess.run([sys.executable, str(REPO_ROOT / "scripts/evaluation_lib/m11g23_dump_under_policy.py"),
                    policy_name, str(out), "--private"], cwd=REPO_ROOT, check=True, capture_output=True)
    return json.loads(out.read_text(encoding="utf-8"))


def _section_counts(paths: list[str]) -> dict:
    out: dict[str, int] = {}
    for p in paths:
        key = "/".join(p.split("/")[1:3]).split("[")[0]
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def _unit_ids(run: dict) -> dict:
    return {(r["id"], u["uid"]): u for r in run["results"] for u in r["units"]}


def _policy_view(run: dict, base: dict | None) -> dict:
    view = {"metrics": run["metrics"]}
    if base is not None:
        view["vs_P0_scoring"] = ev.compare_scores(base, run)
        b, o = _unit_ids(base), _unit_ids(run)
        view["vs_P0_units"] = {
            "newly_recovered": sorted(f"{c}/{u}" for (c, u), x in o.items()
                                      if x["strict"]["recovered"] and not b[(c, u)]["strict"]["recovered"]),
            "regressed": sorted(f"{c}/{u}" for (c, u), x in o.items()
                                if b[(c, u)]["strict"]["recovered"] and not x["strict"]["recovered"]),
            "newly_false_admitted": sorted(f"{c}/{u}" for (c, u), x in o.items()
                                           if not x["qual"] and x["rows"] and not b[(c, u)]["rows"]),
        }
    return view


def _gates(split_runs: dict, sel: str, dumps: dict) -> dict:
    g = ACCEPTANCE_GATES
    base, run = split_runs["P0_v15"], split_runs[sel]
    mb, ms = base["metrics"]["1_recall_strict"], run["metrics"]["1_recall_strict"]
    b, o = _unit_ids(base), _unit_ids(run)
    gained = [k for k, x in o.items() if x["strict"]["recovered"] and not b[k]["strict"]["recovered"]]
    regressed = [k for k, x in o.items() if b[k]["strict"]["recovered"] and not x["strict"]["recovered"]]
    new_false = [k for k, x in o.items() if not x["qual"] and x["rows"] and not b[k]["rows"]]
    registry = default_registry()
    severe = [k for k in new_false if o[k]["kind"] in SEVERE_KINDS and any(
        r["members"] and all(registry.get(m) is not None for m in r["members"]) for r in o[k]["rows"])]
    nec = run["metrics"]["4_necessity"]
    gain = round(ms["recovered"] / ms["of"] - mb["recovered"] / mb["of"], 4)
    paths = hi.diff_dumps(dumps["P0_v15"], dumps[sel])
    changed_sections = sorted({s for s in g["G6_historical_sections_unchanged"]
                               if any(p.startswith("/" + s + "/") or p == "/" + s or p.startswith("/" + s + "[")
                                      for p in paths)})
    g20 = {s: (dumps["P0_v15"]["controls"][s]["aggregate"]["1_false_admissions"]["units_with_any_row"],
               dumps[sel]["controls"][s]["aggregate"]["1_false_admissions"]["units_with_any_row"])
           for s in ("g20_dev", "g20_holdout")}
    counted_nt = run["metrics"]["scoring_full_evidence"]["counted_non_technical_rows"]
    results = {
        "G1_recall": {"p0": [mb["recovered"], mb["of"]], "selected": [ms["recovered"], ms["of"]], "gain_abs": gain,
                      "units_gained": len(gained),
                      "pass": gain >= g["G1_recall_gain_abs_min"] and len(gained) >= g["G1_units_gained_min"]},
        "G2a_severe_false_admissions": {"new": len(severe), "units": sorted(f"{c}/{u}" for c, u in severe),
                                        "pass": len(severe) <= g["G2a_new_severe_false_admissions_max"]},
        "G2b_false_admissions": {"new": len(new_false), "units": sorted(f"{c}/{u}" for c, u in new_false),
                                 "per_recovered": None if not gained else round(len(new_false) / len(gained), 4),
                                 "pass": bool(gained) and len(new_false) / len(gained)
                                 <= g["G2b_new_false_admissions_per_recovered_max"]},
        "G3_necessity": {"correct": nec["correct"], "of": nec["of"],
                         "accuracy": None if not nec["of"] else round(nec["correct"] / nec["of"], 4),
                         "pass": bool(nec["of"]) and nec["correct"] / nec["of"] >= g["G3_necessity_accuracy_min"]},
        "G4_no_regression": {"regressed": len(regressed), "units": sorted(f"{c}/{u}" for c, u in regressed),
                             "pass": len(regressed) <= g["G4_units_regressed_max"]},
        "G5_g19_capability": {"counted_non_technical_rows": counted_nt,
                              "pass": counted_nt <= g["G5_counted_non_technical_rows_max"]},
        "G6_historical": {"changed_sections": changed_sections, "pass": not changed_sections},
        "G7_g20_false_admissions": {"p0_vs_selected": g20,
                                    "pass": all(after <= before for before, after in g20.values())},
    }
    results["all_pass"] = all(v["pass"] for v in results.values() if isinstance(v, dict))
    return results


def main() -> None:
    with_eval = "--eval" in sys.argv
    registry_ids = len(default_registry().all_concepts())
    report = {
        "milestone": "M11-G23", "scope": "research only; production unchanged",
        "versions": {"parser": JOB_DESCRIPTION_PARSER_VERSION, "scoring": SCORING_VERSION, "matcher": MATCHER_VERSION,
                     "readme": EXTRACTOR_VERSION, "registry": CONCEPT_REGISTRY_VERSION,
                     "registry_concepts": registry_ids},
        "frozen_inputs": {rel: _sha(rel) for rel in FROZEN_FILES if (REPO_ROOT / rel).exists()},
        "selected_policy": pol.SELECTED.name,
        "policies": {p.name: p.description for p in pol.POLICIES},
        "acceptance_gates": ACCEPTANCE_GATES,
    }
    dev_texts = [c["text"] for c in ev.load("dev")]
    report["fidelity"] = {"dev_p0_replica_mismatches": len(hz.fidelity_mismatches(dev_texts, pol.P0))}

    dev = {p.name: ev.run("dev", p) for p in pol.POLICIES}
    report["dev"] = {name: _policy_view(r, None if name == "P0_v15" else dev["P0_v15"]) for name, r in dev.items()}

    import dataclasses
    ablations = {"+curly_all": dataclasses.replace(pol.P1, name="abl_curly", normalize_curly_all=True),
                 "+bare_cp_lines": dataclasses.replace(pol.P1, name="abl_bare", bare_cp_lines=True),
                 "+wrapped": dataclasses.replace(pol.P1, name="abl_wrapped", wrapped_headings=True),
                 "+inherit": dataclasses.replace(pol.P1, name="abl_inherit", inherit_subheadings=True),
                 "+paragraph_reset": dataclasses.replace(pol.P1, name="abl_reset", paragraph_reset=True)}
    report["dev_p2_component_ablation_on_P1"] = {
        k: {"recovered": m["1_recall_strict"]["recovered"], "false_admitted_units": m["2_incorrect_admissions"]["units"]}
        for k, m in ((k, ev.run("dev", p)["metrics"]) for k, p in ablations.items())}

    with tempfile.TemporaryDirectory() as tmp:
        dumps = {"production": _dump("none", Path(tmp))}
        for p in pol.POLICIES:
            dumps[p.name] = _dump(p.name, Path(tmp))
    report["historical"] = {"p0_replica_dump_equals_production": dumps["production"] == dumps["P0_v15"]}
    private = {"note": "integer / ratio totals only; no posting text, ids, paths or per-posting vectors",
               "P0_v15": {s: _strip_per_posting(dumps["P0_v15"][s]) for s in PRIVATE_SECTIONS}}
    for p in pol.POLICIES[1:]:
        paths = hi.diff_dumps(dumps["P0_v15"], dumps[p.name])
        public_paths = [x for x in paths if not x.startswith(tuple("/" + s for s in PRIVATE_SECTIONS))]
        report["historical"][p.name] = {
            "changed_public_sections": _section_counts(public_paths),
            "g20_aggregate_p0_vs_policy": {
                s: {k: [dumps["P0_v15"]["controls"][s]["aggregate"][k], dumps[p.name]["controls"][s]["aggregate"][k]]
                    for k in ("1_false_admissions", "recall", "precision", "necessity_accuracy")}
                for s in ("g20_dev", "g20_holdout")},
            "m10e_g3_live_unchanged": dumps["P0_v15"]["m10e_g3"] == dumps[p.name]["m10e_g3"],
            "frozen_8c_and_fixture_scoring_unchanged": dumps["P0_v15"]["scoring"] == dumps[p.name]["scoring"],
            "g6_g7_frozen_label_divergence": hi.g6_g7_divergence(p, pol.P0),
            "universal_tracked_text_parse_diff": hi.universal_parse_diff(p),
        }
        private[p.name] = {s: _strip_per_posting(dumps[p.name][s]) for s in PRIVATE_SECTIONS}
    report["historical"]["P0_v15_g6_g7_frozen_label_divergence"] = hi.g6_g7_divergence(pol.P0, pol.P0)

    if with_eval:
        eval_texts = [c["text"] for c in ev.load("eval")]
        report["fidelity"]["eval_p0_replica_mismatches"] = len(hz.fidelity_mismatches(eval_texts, pol.P0))
        evr = {p.name: ev.run("eval", p) for p in pol.POLICIES}
        report["eval"] = {name: _policy_view(r, None if name == "P0_v15" else evr["P0_v15"])
                          for name, r in evr.items()}
        report["eval_gates_selected"] = _gates(evr, pol.SELECTED.name, dumps)
        report["eval_gates_note"] = ("Gates apply to the SELECTED policy only; the other frozen policies are "
                                     "reported for information and were not used to choose after EVAL.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_bytes((json.dumps(report, indent=1, ensure_ascii=False, sort_keys=False) + "\n").encode("utf-8"))
    PRIVATE.write_bytes((json.dumps(private, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    print(f"wrote {REPORT.relative_to(REPO_ROOT)} and {PRIVATE.relative_to(REPO_ROOT)}"
          + (f"; gates all_pass={report['eval_gates_selected']['all_pass']}" if with_eval else ""))


if __name__ == "__main__":
    main()
