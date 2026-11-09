"""Milestone 11-G17 -- actual parser v12 versus v13 comparison.

    python scripts/evaluate_m11g17_v12_v13.py [--private-corpora]

v12 is the REAL committed parser at HEAD, run inside a throwaway local
clone; v13 is this working tree. Both run `m11g17_parse_dump.py` (real
parser, matcher, assessor) over identical corpora. Nothing is simulated.

Writes `evaluation/m11g17/v12_v13_comparison.json` (publication-safe:
synthetic controls, tracked fixtures, counts) and, with
`--private-corpora`, `evaluation/m11g17/private_v12_v13_aggregates.json`
(counts only; no posting text, file name or id).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DUMP = REPO_ROOT / "scripts" / "evaluation_lib" / "m11g17_parse_dump.py"
OUT_DIR = REPO_ROOT / "evaluation" / "m11g17"


def _dump(root: Path, out: Path, private: bool) -> dict:
    import os
    env = {**os.environ, "M11G17_PRIVATE_ROOT": str(REPO_ROOT)}
    args = [sys.executable, str(root / "scripts" / "evaluation_lib" / "m11g17_parse_dump.py"), str(root), str(out)]
    if private:
        args.append("--private")
    subprocess.run(args, check=True, env=env, cwd=root)
    return json.loads(out.read_text(encoding="utf-8"))


def compare(v12: dict, v13: dict, g16_controls: list[dict]) -> dict:
    gold = {c["id"]: c for c in g16_controls}
    out: dict = {"parser_versions": [v12["parser_version"], v13["parser_version"]]}

    false_sup = {"v12": [], "v13": []}
    lost_genuine, newly_declined, changed_rows, unparsed_changes = [], [], [], []
    span_exact = True
    for cid, a in v12["g16"].items():
        b = v13["g16"][cid]
        if a["rows"] != b["rows"]:
            changed_rows.append(cid)
            if any(r["category"] == "alternative_requirement" for r in b["rows"]) and \
                    not any(r["category"] == "alternative_requirement" for r in a["rows"]):
                newly_declined.append(cid)
        if a["unparsed"] != b["unparsed"]:
            unparsed_changes.append(cid)
        for r in b["rows"]:
            if r["span_text"] is not None and r["category"] == "alternative_requirement" \
                    and r["span_text"] != r["original_text"]:
                span_exact = False
        for fx, exp in gold[cid]["expected"]["per_fixture"].items():
            for ver, d in (("v12", a), ("v13", b)):
                if d["fixtures"][fx]["claim_satisfied"] and exp["gold_truth"] != "T":
                    false_sup[ver].append(f"{cid}/{fx}")
            if a["fixtures"][fx]["claim_satisfied"] and exp["gold_truth"] == "T" \
                    and not b["fixtures"][fx]["claim_satisfied"]:
                lost_genuine.append(f"{cid}/{fx}")
    n_fx = sum(len(c["expected"]["per_fixture"]) for c in g16_controls)
    fixtures = [(cid, fx) for cid in v12["g16"] for fx in v12["g16"][cid]["fixtures"]]
    denom_changes = sum(1 for cid, fx in fixtures
                        if v12["g16"][cid]["fixtures"][fx]["assessable"] != v13["g16"][cid]["fixtures"][fx]["assessable"])
    score_changes = sum(1 for cid, fx in fixtures
                        if v12["g16"][cid]["fixtures"][fx]["score"] != v13["g16"][cid]["fixtures"][fx]["score"])
    more_favorable = [f"{cid}/{fx}" for cid, fx in fixtures
                      if (v13["g16"][cid]["fixtures"][fx]["score"] or 0) > (v12["g16"][cid]["fixtures"][fx]["score"] or 0)]
    out["g16_414"] = {
        "false_supported": {"v12": len(false_sup["v12"]), "v13": len(false_sup["v13"]), "denominator": n_fx,
                            "v13_residual_ids": false_sup["v13"]},
        "false_supported_eliminated": len(set(false_sup["v12"]) - set(false_sup["v13"])),
        "new_false_supported_introduced": sorted(set(false_sup["v13"]) - set(false_sup["v12"])),
        "genuine_satisfied_outcomes_no_longer_scored": len(lost_genuine),
        "controls_with_changed_rows": changed_rows,
        "controls_newly_declined": newly_declined,
        "controls_with_changed_unparsed_claims": unparsed_changes,
        "declined_placeholder_span_equals_original_text": span_exact,
        "fixture_outcomes_with_changed_denominator": denom_changes,
        "fixture_outcomes_with_changed_score": score_changes,
        "fixture_outcomes_scored_more_favorably_in_v13": more_favorable,
    }
    g15_changed = [cid for cid in v12["g15"] if v12["g15"][cid] != v13["g15"][cid]]
    out["g15_controls"] = {
        "controls": len(v12["g15"]), "changed": g15_changed,
        "changes": {cid: {"v12": v12["g15"][cid], "v13": v13["g15"][cid]} for cid in g15_changed},
    }
    out["frozen_8c"] = {label: {"pairs": len(v12["8c"][label]),
                                "changed": [k for k in v12["8c"][label] if v12["8c"][label][k] != v13["8c"][label][k]]}
                        for label in v12["8c"]}
    out["m10_soti_manulife"] = {k: {"identical": v12["m10"][k] == v13["m10"][k],
                                    "rows_v12": len(v12["m10"][k]["rows"]), "rows_v13": len(v13["m10"][k]["rows"])}
                                for k in v12["m10"]}
    return out


def private_compare(v12: dict, v13: dict) -> dict:
    out = {"note": "previously inspected private postings -- not independent; counts only"}
    for name, posts in v12["private"].items():
        other = v13["private"][name]
        changed = [i for i, (a, b) in enumerate(zip(posts, other)) if a != b]
        out[name] = {
            "postings": len(posts),
            "postings_changed": len(changed),
            "placeholders_v12": sum(r["category"] == "alternative_requirement" for p in posts for r in p["rows"]),
            "placeholders_v13": sum(r["category"] == "alternative_requirement" for p in other for r in p["rows"]),
            "scoreable_rows_v12": sum(bool(r["members"]) for p in posts for r in p["rows"]),
            "scoreable_rows_v13": sum(bool(r["members"]) for p in other for r in p["rows"]),
        }
    return out


def main() -> None:
    private = "--private-corpora" in sys.argv
    with tempfile.TemporaryDirectory(prefix="m11g17-v12-") as tmp:
        clone = Path(tmp) / "v12"
        subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(REPO_ROOT), str(clone)], check=True,
                       capture_output=True)
        shutil.copyfile(DUMP, clone / "scripts" / "evaluation_lib" / "m11g17_parse_dump.py")
        v12 = _dump(clone, Path(tmp) / "v12.json", private)
        v13 = _dump(REPO_ROOT, Path(tmp) / "v13.json", private)
    assert v12["parser_version"].endswith("v12") and v13["parser_version"].endswith("v13"), \
        (v12["parser_version"], v13["parser_version"])
    g16 = json.loads((REPO_ROOT / "evaluation/m11g16/compound_logic_controls.json").read_text(encoding="utf-8"))
    report = compare(v12, v13, g16["controls"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "v12_v13_comparison.json").write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({k: v for k, v in report["g16_414"].items()
                      if k not in ("controls_with_changed_rows", "v13_residual_ids")}, indent=1))
    print("G15 controls changed:", report["g15_controls"]["changed"])
    print("8c changed:", {k: v["changed"] for k, v in report["frozen_8c"].items()})
    print("SOTI/Manulife:", report["m10_soti_manulife"])
    if private:
        agg = private_compare(v12, v13)
        (OUT_DIR / "private_v12_v13_aggregates.json").write_bytes((json.dumps(agg, indent=2) + "\n").encode("utf-8"))
        for k, v in agg.items():
            if k != "note":
                print("[private]", k, v)


if __name__ == "__main__":
    main()
