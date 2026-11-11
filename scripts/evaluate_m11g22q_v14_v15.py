"""Milestone 11-G22-Q -- actual parser v14 versus v15 comparison.

    python scripts/evaluate_m11g22q_v14_v15.py [--private-corpora]

v14 is the REAL committed parser at `V14_REF` -- the G22 research commit, which is the
parent of G22-Q and whose src/ is identical to the G21 commit de2a906 (checked) -- run
inside a throwaway local clone; v15 is this working tree. Both run
`scripts/evaluation_lib/m11g22q_parser_dump.py` (real parser, matcher, scoring v2, API
serializer) over identical corpora. Nothing is simulated. Frozen gold and frozen research
outputs (including G22's) are read, never written.

The pinned clone also re-runs G22's own report builder and checks that the committed
G22 report (`evaluation/m11g22/concept_precision_report.json`) is reproduced
byte-identically (G14 canonical contract) by real parser v14.

Writes `evaluation/m11g22q/v14_v15_comparison.json` (publication-safe: synthetic and
tracked controls, fixture ids, counts) and, with --private-corpora,
`evaluation/m11g22q/private_v14_v15_aggregates.json` (integer counts only).

The delta helpers are G21's (`evaluate_m11g21_v13_v14.py`), reused unchanged; their
version-named keys are relabelled old -> "v14", new -> "v15".
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
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import evaluate_m11g21_v13_v14 as g21  # noqa: E402
import evaluate_m11g22_concept_precision as g22  # noqa: E402
import gold_integrity as gi  # noqa: E402

DUMP = REPO_ROOT / "scripts" / "evaluation_lib" / "m11g22q_parser_dump.py"
OUT_DIR = REPO_ROOT / "evaluation" / "m11g22q"
V14_REF = "fad7c6dc3dd8608e382478ed10156b414d86b7ae"   # G22 research commit (last parser-v14 commit)
G21_REF = "de2a906a0d98c3b2c19a8f5a49299f147468ade2"   # G21 commit that introduced revised v14
PRODUCTION = ("src/gitscore/jobs/parsing/alternatives.py", "src/gitscore/jobs/parsing/parser.py")


def relabel(obj):
    """G21 helper keys are named v13 (old) / v14 (new); here old = v14 and new = v15."""
    if isinstance(obj, dict):
        return {k.replace("v14", "v15").replace("v13", "v14"): relabel(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [relabel(v) for v in obj]
    return obj


def _git(*args: str, cwd: Path = REPO_ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True).stdout.decode("utf-8")


def _dump(root: Path, out: Path, private: bool) -> dict:
    env = {**os.environ, "M11G21_DATA_ROOT": str(REPO_ROOT)}
    args = [sys.executable, str(root / "scripts" / "evaluation_lib" / "m11g22q_parser_dump.py"), str(root), str(out)]
    if private:
        args.append("--private")
    subprocess.run(args, check=True, env=env, cwd=root)
    return json.loads(out.read_text(encoding="utf-8"))


def _identical_tracked_inputs(clone: Path) -> dict:
    """Every tracked evaluation/ and fixture file is identical under the G14 canonical newline contract,
    and every span-bearing .txt input is byte-identical (the clone is checked out with core.autocrlf=false,
    i.e. LF index blobs; this working tree holds a mix of LF and CRLF copies of JSON/Markdown files), so
    v14/v15 differences can only come from code."""
    files = _git("ls-files", "evaluation", "tests/fixtures", cwd=clone).splitlines()
    canonical = all(gi.canonical_bytes((clone / f).read_bytes()) == gi.canonical_bytes((REPO_ROOT / f).read_bytes())
                    for f in files)
    txt = [f for f in files if f.endswith(".txt")]
    raw_txt = all((clone / f).read_bytes() == (REPO_ROOT / f).read_bytes() for f in txt)
    return {"tracked_files": len(files), "identical_modulo_newlines": canonical,
            "txt_files": len(txt), "txt_byte_identical": raw_txt}


def _g22_report_reproduced(clone: Path) -> bool:
    code = ("import sys; sys.path[:0]=['src','scripts','scripts/evaluation_lib']; "
            "import evaluate_m11g22_concept_precision as r; sys.stdout.buffer.write(r.encode(r.build_report()))")
    out = subprocess.run([sys.executable, "-c", code], cwd=clone, check=True, capture_output=True).stdout
    committed = gi.canonical_bytes((REPO_ROOT / "evaluation" / "m11g22" / "concept_precision_report.json").read_bytes())
    return gi.canonical_bytes(out) == committed


def _v14(tmp: Path, private: bool) -> tuple[dict, dict]:
    clone = tmp / "v14"
    subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", "-c", "core.autocrlf=false", str(REPO_ROOT),
                    str(clone)], check=True, capture_output=True)
    subprocess.run(["git", "checkout", "--quiet", V14_REF], cwd=clone, check=True, capture_output=True)
    pins = {"v14_ref": V14_REF, "clone_head": _git("rev-parse", "HEAD", cwd=clone).strip(),
            "v14_src_identical_to_g21_commit": subprocess.run(
                ["git", "diff", "--quiet", G21_REF, V14_REF, "--", "src"], cwd=REPO_ROOT).returncode == 0,
            "tracked_inputs": _identical_tracked_inputs(clone),
            "g22_committed_report_reproduced_by_pinned_v14": _g22_report_reproduced(clone)}
    shutil.copyfile(DUMP, clone / "scripts" / "evaluation_lib" / "m11g22q_parser_dump.py")
    return _dump(clone, tmp / "v14.json", private), pins


# ---- G22-Q specific measurements ------------------------------------------------------------------
def _parse_sets(d: dict) -> dict[str, dict]:
    sets = {f"corpus:{n}": items for n, items in d["corpora"].items()}
    sets.update({f"controls:{n}": c["parse"] for n, c in d["controls"].items()})
    sets["g13_or_contract"] = {k: {kk: v[kk] for kk in ("rows", "unparsed", "unparsed_text_ok")}
                               for k, v in d["g13_or_contract"].items()}
    return sets


def _key(r: dict) -> tuple:
    return tuple(r["members"]), r.get("category"), r["necessity"], tuple(r["span"])


def alias_recoveries(v14: dict, v15: dict) -> dict:
    """Placeholder -> one canonical concept row at the SAME span with the SAME necessity; plus every
    other row change, which must be none."""
    recovered, other_changes, or_total, or_kept = [], [], 0, 0
    for name, items in _parse_sets(v14).items():
        new_items = _parse_sets(v15)[name]
        for iid, a in items.items():
            b = new_items[iid]
            ka, kb = {_key(r) for r in a["rows"]}, {_key(r) for r in b["rows"]}
            for r in a["rows"]:
                if len(r["members"]) > 1:
                    or_total += 1
                    or_kept += _key(r) in kb
            removed, added = ka - kb, kb - ka
            pairs = [(x, y) for x in removed for y in added
                     if x[1] == "alternative_requirement" and len(y[0]) == 1 and (x[2], x[3]) == (y[2], y[3])]
            for x, y in pairs:
                recovered.append([name, iid, list(y[0]), y[2]])
            rest = (removed - {x for x, _ in pairs}) | (added - {y for _, y in pairs})
            if rest or a["unparsed"] != b["unparsed"]:
                other_changes.append([name, iid])
    return {"same_concept_placeholders_recovered": len(recovered), "recovered": sorted(recovered),
            "unique_texts_recovered": len({(r[1].split("/")[0], tuple(r[2])) for r in recovered}),
            "genuine_or_groups_v14": or_total, "genuine_or_groups_preserved_v15": or_kept,
            "other_row_or_unparsed_changes": sorted(other_changes)}


def status_transitions(v14: dict, v15: dict) -> dict:
    """MatchStatus / eligibility at every requirement span, v14 -> v15, over every scored fixture."""
    moves: Counter = Counter()
    newly_scoreable, examples = 0, {}
    for name, fixtures in v14["scoring"].items():
        for key, a in fixtures.items():
            b = v15["scoring"][name][key]
            sa = {tuple(r["span"]): r for r in a["rows"]}
            sb = {tuple(r["span"]): r for r in b["rows"]}
            for span in sorted(set(sa) | set(sb)):
                x, y = sa.get(span), sb.get(span)
                fx = None if x is None else f"{x['status']}{'+counted' if x['counts'] else ''}"
                fy = None if y is None else f"{y['status']}{'+counted' if y['counts'] else ''}"
                if fx != fy:
                    moves[f"{fx} -> {fy}"] += 1
                    examples.setdefault(f"{fx} -> {fy}", []).append(f"{name}:{key}")
                    newly_scoreable += bool(y and y["counts"] and not (x and x["counts"]))
    return {"transitions": dict(sorted(moves.items())), "fixtures": {k: sorted(v) for k, v in examples.items()},
            "newly_counted_requirement_fixtures": newly_scoreable}


def _truth(rel: str) -> dict:
    cs = json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))["controls"]
    return {f"{c['id']}/{k['name']}": set(k["true_competencies"]) for c in cs for k in c["candidates"]}


def new_supported_judged(v14: dict, v15: dict) -> dict:
    """Every counted SUPPORTED row that is new in v15, judged against the fixture's frozen truth."""
    truth = {"g15": _truth("evaluation/m11g15/or_scoring_controls.json"),
             "g18": _truth("evaluation/m11g18/eligibility_controls.json")}
    true_s, false_s, unjudged = [], [], []
    for name, fixtures in v15["scoring"].items():
        for key, b in fixtures.items():
            old = {(tuple(r["span"]), tuple(r["members"])) for r in v14["scoring"][name][key]["rows"]
                   if r["status"] == "supported" and r["counts"]}
            for r in b["rows"]:
                if r["status"] == "supported" and r["counts"] and (tuple(r["span"]), tuple(r["members"])) not in old:
                    t = truth.get(name, {}).get(key)
                    (unjudged if t is None else true_s if set(r["members"]) & t else false_s).append(
                        f"{name}:{key}:{'|'.join(r['members'])}")
    return {"new_true_supported": sorted(true_s), "new_false_supported": sorted(false_s),
            "new_supported_without_frozen_truth": sorted(unjudged)}


def g22_scoring(v14: dict, v15: dict) -> dict:
    out = {}
    for name, a in v14["g22_scoring"].items():
        b = v15["g22_scoring"][name]
        items = [(fid, None, None, gold) for fid, gold, _ in a]
        assert [x[0] for x in a] == [x[0] for x in b]
        d = g22.scoring_delta([x[2] for x in a], [x[2] for x in b], items)
        ev_a, ev_b = sum(x[2]["evidence_items"] for x in a), sum(x[2]["evidence_items"] for x in b)
        d["evidence_items"] = [ev_a, ev_b]
        d["evidence_changed"] = sorted(x[0] for x, y in zip(a, b)
                                       if (x[2]["evidence_items"], x[2]["matched_concepts"])
                                       != (y[2]["evidence_items"], y[2]["matched_concepts"]))
        out[name] = d
    return out


def g22_controls(v14: dict, v15: dict) -> dict:
    out = {}
    for split in ("dev", "eval"):
        a, b = v14["g22_controls"][split], v15["g22_controls"][split]
        out[split] = {"v14": a["aggregate"], "v15": b["aggregate"],
                      "changed_controls": {cid: {"v14": x, "v15": b["controls"][cid]}
                                           for cid, x in a["controls"].items() if x != b["controls"][cid]}}
    return out


def g13(v14: dict, v15: dict) -> dict:
    changed = {}
    for cid, a in v14["g13_or_contract"].items():
        b = v15["g13_or_contract"][cid]
        if (a["rows"], a["score"]) != (b["rows"], b["score"]):
            changed[cid] = {v: {"rows": [[r["members"], r["category"], r["necessity"]] for r in d["rows"]],
                                "score": d["score"]["score"], "assessable": d["score"]["assessable"],
                                "supported_counted": d["score"]["supported_counted"]}
                            for v, d in (("v14", a), ("v15", b))}
    return {"controls": len(v14["g13_or_contract"]), "changed": changed}


def m10e(v14: dict, v15: dict) -> dict:
    return {"g3_frozen_gold": v15["m10e_g3"]["frozen_gold"],
            "g3_live": {"v14": v14["m10e_g3"]["live"]["BASE"], "v15": v15["m10e_g3"]["live"]["BASE"]},
            "row_existence_mismatches_outside_known_list": {"v14": v14["m10e_row_existence_mismatches"],
                                                            "v15": v15["m10e_row_existence_mismatches"]}}


def build_report(v14: dict, v15: dict, pins: dict) -> dict:
    assert v14["parser_version"] == "job_description_parser:v14", v14["parser_version"]
    assert v15["parser_version"] == "job_description_parser:v15", v15["parser_version"]
    assert v14["scoring_version"] == v15["scoring_version"] == "github_evidence_alignment:v2"
    assert v14["matcher_version"] == v15["matcher_version"]
    assert v14["gitscore_imported_from_repo_root"] and v15["gitscore_imported_from_repo_root"]
    return {
        "versions": {"v14": [v14["parser_version"], v14["scoring_version"], v14["matcher_version"], V14_REF],
                     "v15": [v15["parser_version"], v15["scoring_version"], v15["matcher_version"], "working tree"]},
        "pins": pins,
        "production_files_changed": list(PRODUCTION),
        "note": "actual production v14 (pinned clone) vs v15 (working tree); real parser/matcher/scoring v2/API "
                "serializer; frozen gold and frozen research outputs untouched; no LLM",
        "labels": {"g20_dev": "development set (designed against)", "g20_holdout": "weakly held-out synthetic",
                   "g21_adversarial": g21.REVISED_ADVERSARIAL_LABEL,
                   "g22_dev": "G22 design set; synthetic, same author; NOT independent",
                   "g22_eval": "G22 weakly held-out synthetic; same author; NOT independent",
                   "g13_or_contract": "frozen G13 OR-contract controls (synthetic)"},
        "alias_equivalence": alias_recoveries(v14, v15),
        "match_status": status_transitions(v14, v15),
        "new_supported_rows": new_supported_judged(v14, v15),
        "g22_controls": g22_controls(v14, v15),
        "g22_fixture_scoring": g22_scoring(v14, v15),
        "g13_or_contract": g13(v14, v15),
        "m10e": m10e(v14, v15),
        "controls": relabel({name: g21.control_set_delta(v14["controls"][name], v15["controls"][name])
                             for name in v14["controls"]}),
        "corpora": relabel({name: g21.corpus_delta(v14["corpora"][name], v15["corpora"][name])
                            for name in v14["corpora"]}),
        "scoring": relabel({name: g21.scoring_delta(v14["scoring"][name], v15["scoring"][name])
                            for name in v14["scoring"]}),
        "g17_guard": relabel(g21.g17_guard(v14, v15)),
        "negation_scope": relabel({k: v for k, v in g21.negation_scope_delta(v14, v15).items() if k != "results"}),
    }


def _ints_only(obj):
    """G21's label-backed private view also carries derived ratios (floats); G22-Q publishes integer counts
    only, so every non-integer leaf is dropped (each ratio is derivable from the kept counts)."""
    if isinstance(obj, dict):
        return {k: v2 for k, v2 in ((k, _ints_only(v)) for k, v in obj.items()) if v2 is not None}
    if isinstance(obj, list):
        return [_ints_only(v) for v in obj]
    return obj if isinstance(obj, int) and not isinstance(obj, bool) else None


def build_private(v14: dict, v15: dict) -> dict:
    agg = _ints_only(relabel(g21.build_private(v14, v15)))
    agg["note"] = "previously inspected private postings -- NOT independent validation; integer counts only"
    concept = {}
    for name, a in v14["g22_private"].items():
        b = v15["g22_private"][name]
        concept[name] = {"postings": a["postings"],
                         **{f"{k}_v14": a[k] for k in a if k not in ("postings", "_per")},
                         **{f"{k}_v15": b[k] for k in b if k not in ("postings", "_per")},
                         "postings_changed": sum(1 for x, y in zip(a["_per"], b["_per"]) if x != y)}
    agg["concept_view"] = concept
    g22._assert_ints({k: v for k, v in agg.items() if k != "note"})
    return agg


def encode(obj) -> bytes:
    return (json.dumps(obj, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def main() -> None:
    private = "--private-corpora" in sys.argv
    with tempfile.TemporaryDirectory(prefix="m11g22q-v14-") as tmpdir:
        tmp = Path(tmpdir)
        v14, pins = _v14(tmp, private)
        v15 = _dump(REPO_ROOT, tmp / "v15.json", private)
    report = build_report(v14, v15, pins)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "v14_v15_comparison.json").write_bytes(encode(report))
    print("pins", pins)
    ae = report["alias_equivalence"]
    print("recovered", ae["same_concept_placeholders_recovered"], ae["recovered"])
    print("OR groups preserved", ae["genuine_or_groups_preserved_v15"], "/", ae["genuine_or_groups_v14"],
          "other changes", ae["other_row_or_unparsed_changes"])
    print("status", report["match_status"]["transitions"], "newly counted",
          report["match_status"]["newly_counted_requirement_fixtures"])
    print("new supported", report["new_supported_rows"])
    for split, d in report["g22_controls"].items():
        print("g22", split, {k: (d["v14"][k], d["v15"][k]) for k in (
            "exact_controls", "false_registered", "fabricated_unresolved", "concept_recall", "registry_concept_recall",
            "false_supported_counted", "necessity")}, "changed", sorted(d["changed_controls"]))
    for name, d in report["g22_fixture_scoring"].items():
        print("scoring", name, "score", d["score_changed"], "den", d["denominator_changed"], "undef",
              d["became_undefined"], "defined", d["became_defined"], "g16 false", d["g16_claim_false_supported"],
              "evidence", d["evidence_items"], d["evidence_changed"])
    print("g13", report["g13_or_contract"]["changed"])
    print("m10e", report["m10e"]["g3_live"], report["m10e"]["row_existence_mismatches_outside_known_list"])
    print("g17", report["g17_guard"], "negation", report["negation_scope"])
    for name, d in report["corpora"].items():
        print(name, {k: d[k] for k in ("rows_removed", "rows_added", "necessity_changed", "newly_declined_claims")},
              "fixed", d["gold_fixed_ids"], "REGRESSED", d["gold_regressed_ids"])
    for name, d in report["controls"].items():
        print(name, "lost", d["lost_genuine_qualifications"], "new false", d["new_false_admissions"],
              "nec", d["necessity_changed_units"], "parse changes", sorted(d["parse"]))
    if private:
        agg = build_private(v14, v15)
        (OUT_DIR / "private_v14_v15_aggregates.json").write_bytes((json.dumps(agg, indent=1) + "\n").encode("utf-8"))
        for name, v in agg["concept_view"].items():
            print("[private]", name, "postings", v["postings"], "changed", v["postings_changed"])
        for name, v in agg.items():
            if isinstance(v, dict) and "postings_changed" in v and name != "concept_view":
                print("[private g21-view]", name, "changed", v["postings_changed"])


if __name__ == "__main__":
    main()
