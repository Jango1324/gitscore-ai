"""Milestone 11-G19 -- actual scoring v1 versus v2 comparison.

    python scripts/evaluate_m11g19_v1_v2.py [--private-corpora]

v1 is the REAL committed scoring at `V1_REF` -- the last scoring-v1 commit
(M11-G18, `github_evidence_alignment:v1`) -- run inside a throwaway local
clone, so the comparison stays reproducible after G19 is committed; v2 is this working tree. Both run
`m11g19_scoring_dump.py` (real parser, matcher, assessor and API
serializer) over identical corpora. Nothing is simulated. Frozen
historical reports and gold are read, never written.

Writes `evaluation/m11g19/v1_v2_comparison.json` (publication-safe:
synthetic controls, tracked fixtures, counts) and, with
`--private-corpora`, `evaluation/m11g19/private_v1_v2_aggregates.json`
(integer counts only; no posting text, file name or id).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DUMP = REPO_ROOT / "scripts" / "evaluation_lib" / "m11g19_scoring_dump.py"
OUT_DIR = REPO_ROOT / "evaluation" / "m11g19"
G18_REPORT = REPO_ROOT / "evaluation" / "m11g18" / "eligibility_report.json"
V1_REF = "ac4a15ed25380f556f99e4a6a6c26c75cd1902a5"
MATCH_FIELDS = ("status", "necessity", "members", "matched", "evidence", "interpretation_status", "text_len")


def _dump(root: Path, out: Path, private: bool) -> dict:
    env = {**os.environ, "M11G19_PRIVATE_ROOT": str(REPO_ROOT)}
    args = [sys.executable, str(root / "scripts" / "evaluation_lib" / "m11g19_scoring_dump.py"), str(root), str(out)]
    if private:
        args.append("--private")
    subprocess.run(args, check=True, env=env, cwd=root)
    return json.loads(out.read_text(encoding="utf-8"))


def direction(a: dict, b: dict) -> str:
    if (a["score"], a["assessable"]) == (b["score"], b["assessable"]):
        return "unchanged"
    if a["score"] is not None and b["score"] is None:
        return "became_undefined"
    if a["score"] is None:
        return "became_defined"
    if b["score"] > a["score"]:
        return "increased"
    if b["score"] < a["score"]:
        return "decreased"
    return "denominator_only"


def _match_view(o: dict) -> list:
    return sorted(json.dumps({k: r[k] for k in MATCH_FIELDS}, sort_keys=True) for r in o["rows"])


def compare_corpus(v1: dict, v2: dict) -> dict:
    dirs: dict[str, list] = {}
    evidence_changed, reconcile_bad, reason_bad = [], [], []
    for key, a in v1.items():
        b = v2[key]
        dirs.setdefault(direction(a, b), []).append(key)
        if _match_view(a) != _match_view(b):
            evidence_changed.append(key)
        if b["n_supported"] + b["n_not_observed"] != b["assessable"] + b["excluded"]:
            reconcile_bad.append(key)
        for r in b["rows"]:
            if r["counts"] != (r["reason"] is None) or (r["status"] == "not_assessable" and r["reason"] != "not_assessable"):
                reason_bad.append(key)
                break
    out = {"outcomes": len(v1), "by_direction": {k: len(v) for k, v in sorted(dirs.items())},
           "ids_by_direction": {k: sorted(v) for k, v in sorted(dirs.items()) if k != "unchanged"},
           "match_status_or_evidence_changed": evidence_changed,
           "count_reconciliation_failures": reconcile_bad, "reason_consistency_failures": reason_bad}
    out["changes"] = {k: {"v1": [v1[k]["score"], v1[k]["assessable"]], "v2": [v2[k]["score"], v2[k]["assessable"]],
                          "excluded_v2": v2[k]["excluded"],
                          "reasons_v2": sorted(r["reason"] for r in v2[k]["rows"]
                                               if r["reason"] not in (None, "not_assessable"))}
                      for k in v1 if direction(v1[k], v2[k]) != "unchanged"}
    return out


def g18_equivalence(v2: dict) -> dict:
    sim = json.loads(G18_REPORT.read_text(encoding="utf-8"))["g18_controls"]["results"]
    mismatches = []
    for key, o in v2["g18"].items():
        cid, cand = key.split("/", 1)
        c = sim[cid]["candidates"][cand]["policies"]["C_capability_declared"]
        eligible_supported = sum(1 for r in o["rows"] if r["counts"] and r["status"] == "supported")
        if (o["score"], eligible_supported, o["assessable"]) != (c["score"], c["supported"], c["eligible"]):
            mismatches.append(key)
    return {"candidate_pairs": len(v2["g18"]), "equal_to_g18_simulated_policy_c": len(v2["g18"]) - len(mismatches),
            "mismatches": mismatches}


def private_compare(v1: dict, v2: dict) -> dict:
    out = {"note": "previously inspected private postings -- not independent holdouts; integer counts only"}
    for name, posts in v2["private"].items():
        before = v1["private"][name]
        reasons = Counter(r for p in posts for r, t in zip(p["reasons"], p["technical"]) if t and r is not None)
        out[name] = {
            "postings": len(posts),
            "technical_rows": sum(sum(p["technical"]) for p in posts),
            "denominator_rows_v1": sum(p["assessable"] for p in before),
            "denominator_rows_v2": sum(p["assessable"] for p in posts),
            "technical_rows_excluded_v2": sum(p["excluded"] for p in posts),
            "postings_with_any_exclusion_v2": sum(1 for p in posts if p["excluded"]),
            "postings_with_no_eligible_requirement_v1": sum(1 for p in before if not p["assessable"]),
            "postings_with_no_eligible_requirement_v2": sum(1 for p in posts if not p["assessable"]),
            "excluded_by_reason_v2": dict(sorted(reasons.items())),
        }
    return out


def main() -> None:
    private = "--private-corpora" in sys.argv
    with tempfile.TemporaryDirectory(prefix="m11g19-v1-") as tmp:
        clone = Path(tmp) / "v1"
        subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(REPO_ROOT), str(clone)], check=True,
                       capture_output=True)
        subprocess.run(["git", "checkout", "--quiet", V1_REF], cwd=clone, check=True, capture_output=True)
        shutil.copyfile(DUMP, clone / "scripts" / "evaluation_lib" / "m11g19_scoring_dump.py")
        v1 = _dump(clone, Path(tmp) / "v1.json", private)
        v2 = _dump(REPO_ROOT, Path(tmp) / "v2.json", private)
    assert v1["scoring_version"].endswith(":v1") and v2["scoring_version"].endswith(":v2"), \
        (v1["scoring_version"], v2["scoring_version"])
    assert v1["parser_version"] == v2["parser_version"] and v1["matcher_version"] == v2["matcher_version"]
    report = {"versions": {"v1": [v1["scoring_version"], v1["parser_version"], v1["matcher_version"]],
                           "v2": [v2["scoring_version"], v2["parser_version"], v2["matcher_version"]]},
              "note": "actual production v1 (HEAD clone) vs v2 (working tree); real parser/matcher/assessor/API "
                      "serializer; frozen historical reports untouched"}
    for corpus in ("g18", "g15", "g16"):
        report[corpus] = compare_corpus(v1[corpus], v2[corpus])
    report["frozen_8c"] = {label: compare_corpus(v1["8c"][label], v2["8c"][label]) for label in v1["8c"]}
    report["m10_soti_manulife"] = compare_corpus(v1["m10"], v2["m10"])
    report["g18_live_v2_vs_simulated_policy_c"] = g18_equivalence(v2)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "v1_v2_comparison.json").write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    for corpus in ("g18", "g15", "g16", "m10_soti_manulife"):
        r = report[corpus]
        print(corpus, r["by_direction"], "| evidence changed:", len(r["match_status_or_evidence_changed"]),
              "| reconcile bad:", len(r["count_reconciliation_failures"]))
    for label, r in report["frozen_8c"].items():
        print(label, r["by_direction"], {k: v for k, v in r["changes"].items()})
    print("G18 live v2 == simulated C:", report["g18_live_v2_vs_simulated_policy_c"])
    if private:
        agg = private_compare(v1, v2)
        (OUT_DIR / "private_v1_v2_aggregates.json").write_bytes((json.dumps(agg, indent=2) + "\n").encode("utf-8"))
        for k, v in agg.items():
            if k != "note":
                print("[private]", k, v)


if __name__ == "__main__":
    main()
