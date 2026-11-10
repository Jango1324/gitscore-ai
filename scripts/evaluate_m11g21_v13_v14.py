"""Milestone 11-G21 -- actual parser v13 versus v14 comparison.

    python scripts/evaluate_m11g21_v13_v14.py [--private-corpora]

v13 is the REAL committed parser at `V13_REF` (the G20 research commit, the last
parser-v13 commit) run inside a throwaway local clone; v14 is this working tree.
Both run `scripts/evaluation_lib/m11g21_parser_dump.py` (real parser, matcher,
scoring v2 and API serializer) over identical corpora. Nothing is simulated.
Frozen gold and frozen research reports are read, never written.

Writes `evaluation/m11g21/v13_v14_comparison.json` (publication-safe: synthetic
controls, tracked fixtures, counts) and, with --private-corpora,
`evaluation/m11g21/private_v13_v14_aggregates.json` (integer counts only).

    python scripts/evaluate_m11g21_v13_v14.py --label revised [--private-corpora]

writes the same two reports with a `_revised` suffix instead, so the ORIGINAL v14
(pre negation-scope correction) outputs stay preserved beside the revised ones.
Running without a label is refused: the unsuffixed files are a preserved record.

    python scripts/evaluate_m11g21_v13_v14.py --reproduce-original [--private-corpora] [--from-working-tree]

rebuilds that never-committed FIRST v14 by applying `evaluation/m11g21/first_v14_reverse.patch`
to the three production files of a throwaway clone and checks the preserved original
outputs are reproduced byte-identically (exit status 1 otherwise).

The v13 baseline is ALWAYS the pinned commit `V13_REF`, never a moving HEAD.
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
DUMP = REPO_ROOT / "scripts" / "evaluation_lib" / "m11g21_parser_dump.py"
OUT_DIR = REPO_ROOT / "evaluation" / "m11g21"
G20_REPORT = REPO_ROOT / "evaluation" / "m11g20" / "admission_report.json"
V13_REF = "a2602820b21d521c7ac4006b6738224fde716e2c"
B1NR = "B1NR_admission_necessity_posthoc"


def _dump(root: Path, out: Path, private: bool) -> dict:
    cache = os.environ.get("M11G21_DUMP_CACHE")  # optional: reuse dumps while iterating on this script
    if cache:
        cached = Path(cache) / f"{'v14' if root == REPO_ROOT else 'v13'}.json"
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))
    env = {**os.environ, "M11G21_DATA_ROOT": str(REPO_ROOT)}
    args = [sys.executable, str(root / "scripts" / "evaluation_lib" / "m11g21_parser_dump.py"), str(root), str(out)]
    if private:
        args.append("--private")
    subprocess.run(args, check=True, env=env, cwd=root)
    if cache:
        Path(cache).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, Path(cache) / f"{'v14' if root == REPO_ROOT else 'v13'}.json")
    return json.loads(out.read_text(encoding="utf-8"))


def _row_key(r: dict) -> tuple:
    return tuple(r["members"]), r.get("category"), tuple(r["span"])


def parse_delta(a: dict, b: dict) -> dict:
    ka = {_row_key(r): r["necessity"] for r in a["rows"]}
    kb = {_row_key(r): r["necessity"] for r in b["rows"]}
    return {"removed": sorted(set(ka) - set(kb)), "added": sorted(set(kb) - set(ka)),
            "necessity_changed": sorted(k for k in set(ka) & set(kb) if ka[k] != kb[k]),
            "newly_declined": sorted(set(map(tuple, b["unparsed"])) - set(map(tuple, a["unparsed"]))),
            "no_longer_declined": sorted(set(map(tuple, a["unparsed"])) - set(map(tuple, b["unparsed"]))),
            "span_text_ok": all(r["text_ok"] for r in b["rows"]) and b["unparsed_text_ok"]}


def _admitted(rows: list, s: int, e: int) -> bool:
    return any(min(r["span"][1], e) - max(r["span"][0], s) > 0 for r in rows)


def corpus_delta(v13: dict, v14: dict) -> dict:
    out = Counter()
    changed, fixed, regressed, details = [], [], [], {}
    for iid, a in v13.items():
        b = v14[iid]
        d = parse_delta(a, b)
        out["items"] += 1
        out["rows_v13"] += len(a["rows"])
        out["rows_v14"] += len(b["rows"])
        out["rows_removed"] += len(d["removed"])
        out["rows_added"] += len(d["added"])
        out["necessity_changed"] += len(d["necessity_changed"])
        out["newly_declined_claims"] += len(d["newly_declined"])
        out["unparsed_v13"] += len(a["unparsed"])
        out["unparsed_v14"] += len(b["unparsed"])
        out["span_text_errors_v14"] += int(not d["span_text_ok"])
        if d["removed"] or d["added"] or d["necessity_changed"]:
            changed.append(iid)
            details[iid] = json.loads(json.dumps({k: v for k, v in d.items() if k != "span_text_ok" and v}))
        for s, e, should in a.get("gold", []):
            if should is None:
                continue
            x, y = _admitted(a["rows"], s, e), _admitted(b["rows"], s, e)
            if x != should and y == should:
                fixed.append(iid)
            elif x == should and y != should:
                regressed.append(iid)
    return {**dict(out), "changed_ids": changed, "gold_fixed_ids": sorted(set(fixed)),
            "gold_regressed_ids": sorted(set(regressed)), "changes": details}


def scoring_delta(v13: dict, v14: dict) -> dict:
    out = Counter()
    ids = {k: [] for k in ("score_changed", "denominator_changed", "became_undefined", "became_defined",
                           "status_changed_on_kept_rows", "eligibility_changed_on_kept_rows",
                           "new_false_supported_candidates")}
    changes = {}
    for key, a in v13.items():
        b = v14[key]
        out["outcomes"] += 1
        if a["score"] != b["score"]:
            ids["score_changed"].append(key)
        if a["assessable"] != b["assessable"]:
            ids["denominator_changed"].append(key)
        if a["score"] is not None and b["score"] is None:
            ids["became_undefined"].append(key)
        if a["score"] is None and b["score"] is not None:
            ids["became_defined"].append(key)
        ra = {(tuple(r["span"]), tuple(r["members"])): r for r in a["rows"]}
        rb = {(tuple(r["span"]), tuple(r["members"])): r for r in b["rows"]}
        for k in set(ra) & set(rb):
            if ra[k]["status"] != rb[k]["status"]:
                ids["status_changed_on_kept_rows"].append(key)
            if (ra[k]["counts"], ra[k]["reason"]) != (rb[k]["counts"], rb[k]["reason"]):
                ids["eligibility_changed_on_kept_rows"].append(key)
        if any(r["status"] == "supported" and r["counts"] for k, r in rb.items() if k not in ra):
            ids["new_false_supported_candidates"].append(key)
        out["numerator_v13"] += a["supported_counted"]
        out["numerator_v14"] += b["supported_counted"]
        out["denominator_v13"] += a["assessable"]
        out["denominator_v14"] += b["assessable"]
        out["unparsed_claims_v13"] += a["unparsed_claim_count"]
        out["unparsed_claims_v14"] += b["unparsed_claim_count"]
        if (a["score"], a["assessable"]) != (b["score"], b["assessable"]):
            changes[key] = {"v13": [a["supported_counted"], a["assessable"], a["score"]],
                            "v14": [b["supported_counted"], b["assessable"], b["score"]]}
    return {**dict(out), **{k: sorted(set(v)) for k, v in ids.items()}, "changes": changes}


def _summary(agg: dict) -> dict:
    return {"false_admission_units": agg["1_false_admissions"]["units_with_any_row"],
            "non_qualification_units": agg["units"]["non_qualification"],
            "false_required_rows": agg["2_false_required"]["rows_on_non_qualifications"],
            "preferred_marked_required_units": agg["2_false_required"]["units_preferred_gold_marked_required"],
            "fabricated_concepts": agg["3_fabricated_concepts"]["total"],
            "false_supported_counted_full_evidence": agg["4_false_supported_counted_full_evidence"],
            "missed_entirely": agg["6_missed"]["qualification_units_missed_entirely"],
            "declined_visible": agg["7_declined"]["declined_visible_unparsed"],
            "unit_precision": agg["precision"]["unit_admission_precision"],
            "row_precision": agg["precision"]["row_precision"],
            "unit_recall": agg["recall"]["unit_recall"], "concept_recall": agg["recall"]["concept_recall"],
            "necessity": [agg["necessity_accuracy"]["correct"], agg["necessity_accuracy"]["scored"]],
            "source_spans_within_unit": agg["8_source_spans"]["rows_within_one_unit"]}


def _pairs(units: list) -> list:
    pairs: dict = {}
    for u in units:
        if u["pair"]:
            pairs.setdefault(u["pair"], []).append(u)
    ok = sum(1 for us in pairs.values()
             if all(u["outcome"] == ("represented" if u["qual"] else "correctly_not_admitted") for u in us))
    return [ok, len(pairs)]


def control_set_delta(a: dict, b: dict) -> dict:
    ua = {(u["id"], u["uid"]): u for u in a["units"]}
    ub = {(u["id"], u["uid"]): u for u in b["units"]}
    corrected = sorted(f"{k[0]}/{k[1]}" for k, u in ua.items() if not u["qual"] and u["outcome"] != "correctly_not_admitted"
                       and ub[k]["outcome"] == "correctly_not_admitted")
    lost = sorted(f"{k[0]}/{k[1]}" for k, u in ua.items() if u["qual"] and u["outcome"] == "represented"
                  and ub[k]["outcome"] != "represented")
    new_false = sorted(f"{k[0]}/{k[1]}" for k, u in ua.items() if not u["qual"] and u["outcome"] == "correctly_not_admitted"
                       and ub[k]["outcome"] != "correctly_not_admitted")
    nec = sorted(f"{k[0]}/{k[1]}" for k, u in ua.items() if u["row_necessities"] != ub[k]["row_necessities"]
                 and u["rows"] and ub[k]["rows"])
    residual_false = sorted(f"{k[0]}/{k[1]}" for k, u in ub.items() if not u["qual"]
                            and u["outcome"] != "correctly_not_admitted")
    missed = sorted(f"{k[0]}/{k[1]}" for k, u in ub.items() if u["qual"] and not u["ambiguous"]
                    and u["outcome"] != "represented")
    wrong_nec = sorted(f"{k[0]}/{k[1]}" for k, u in ub.items() if u["qual"] and u["gold_nec"] in ("required", "preferred")
                       and u["rows"] and u["row_necessities"] != [u["gold_nec"]])
    return {"v13": _summary(a["aggregate"]), "v14": _summary(b["aggregate"]),
            "near_neighbour_pairs_correct": {"v13": _pairs(a["units"]), "v14": _pairs(b["units"])},
            "corrected_false_admissions": corrected, "lost_genuine_qualifications": lost,
            "new_false_admissions": new_false, "necessity_changed_units": nec,
            "v14_residual_false_admissions": residual_false, "v14_qualifications_not_represented": missed,
            "v14_wrong_necessity": wrong_nec,
            "scoring_full_evidence": {
                "score_or_denominator_changed": sorted(
                    cid for cid in a["scoring"] if (a["scoring"][cid]["full"]["score"], a["scoring"][cid]["full"]["denominator"])
                    != (b["scoring"][cid]["full"]["score"], b["scoring"][cid]["full"]["denominator"])),
                "became_undefined": sorted(cid for cid in a["scoring"] if a["scoring"][cid]["full"]["score"] is not None
                                           and b["scoring"][cid]["full"]["score"] is None)},
            "parse": {cid: d for cid, d in ((cid, parse_delta(a["parse"][cid], b["parse"][cid])) for cid in a["parse"])
                      if d["removed"] or d["added"] or d["necessity_changed"] or not d["span_text_ok"]}}


def g17_guard(v13: dict, v14: dict) -> dict:
    """Every G16 control still admitted under v14 keeps v13's exact alternative/placeholder rows."""
    checked, violations = 0, []
    for iid, a in v13["corpora"]["g16"].items():
        b = v14["corpora"]["g16"][iid]
        alt = lambda rows: [(r["members"], r["category"], r["span"]) for r in rows  # noqa: E731
                            if len(r["members"]) > 1 or r["category"] == "alternative_requirement"]
        if alt(a["rows"]) and b["rows"]:
            checked += 1
            if alt(a["rows"]) != alt(b["rows"]):
                violations.append(iid)
    return {"g16_controls_with_alternative_rows_still_admitted": checked, "violations": violations}


def _label() -> str:
    if "--label" in sys.argv:
        label = sys.argv[sys.argv.index("--label") + 1]
        assert label.isidentifier(), label
        return f"_{label}"
    return ""


def negation_scope_delta(v13: dict, v14: dict) -> dict:
    path = REPO_ROOT / "evaluation" / "m11g21" / "negation_scope_controls.json"
    controls = json.loads(path.read_text(encoding="utf-8"))["controls"]
    rows, ok13, ok14 = {}, 0, 0
    for c in controls:
        expected = sorted(c["expected_rows"])
        a, b = v13["negation_scope"][c["id"]], v14["negation_scope"][c["id"]]
        ok13 += a["labels"] == expected
        ok14 += b["labels"] == expected
        rows[c["id"]] = {"text": c["text"], "family": c["family"], "expected": expected,
                         "expected_limitation": c["expected_limitation"], "v13": a["labels"], "v14": b["labels"],
                         "v14_correct": b["labels"] == expected,
                         "v14_span_text_ok": b["unparsed_text_ok"] and all(r["text_ok"] for r in b["rows"])}
    return {"controls": len(controls), "correct_v13": ok13, "correct_v14": ok14,
            "label": "author-created validation, frozen before the revised implementation; NOT independent",
            "results": rows}


ORIGINAL_ADVERSARIAL_LABEL = "newly authored synthetic (G21); not independent external validation"
REVISED_ADVERSARIAL_LABEL = ("DEVELOPMENT data since the negation-scope correction (its first-v14 failures informed "
                             "it); newly authored synthetic; not independent external validation")
PRODUCTION = ("src/gitscore/jobs/parsing/qualification_intent.py", "src/gitscore/jobs/parsing/necessity.py",
              "src/gitscore/jobs/parsing/parser.py")
FIRST_V14_PATCH = OUT_DIR / "first_v14_reverse.patch"


def build_report(v13: dict, v14: dict, adversarial_label: str) -> dict:
    assert v13["parser_version"] == "job_description_parser:v13", v13["parser_version"]
    assert v14["parser_version"] == "job_description_parser:v14", v14["parser_version"]
    assert v13["scoring_version"] == v14["scoring_version"] == "github_evidence_alignment:v2"
    assert v13["matcher_version"] == v14["matcher_version"]
    g20 = json.loads(G20_REPORT.read_text(encoding="utf-8"))["controls"]
    return {
        "versions": {"v13": [v13["parser_version"], v13["scoring_version"], v13["matcher_version"], V13_REF],
                     "v14": [v14["parser_version"], v14["scoring_version"], v14["matcher_version"], "working tree"]},
        "note": "actual production v13 (pinned clone) vs v14 (working tree); real parser/matcher/scoring v2/API "
                "serializer; frozen gold and frozen G20 research outputs untouched",
        "controls": {name: control_set_delta(v13["controls"][name], v14["controls"][name])
                     for name in v13["controls"]},
        "research_adapter_vs_live": {
            split: {"v13_live_equals_g20_frozen_v13": v13["controls"][f"g20_{split}"]["aggregate"]
                    == g20[split]["v13"]["aggregate"],
                    "v14_live_equals_g20_frozen_b1nr": v14["controls"][f"g20_{split}"]["aggregate"]
                    == g20[split][B1NR]["aggregate"]}
            for split in ("dev", "holdout")},
        "corpora": {name: corpus_delta(v13["corpora"][name], v14["corpora"][name]) for name in v13["corpora"]},
        "scoring": {name: scoring_delta(v13["scoring"][name], v14["scoring"][name]) for name in v13["scoring"]},
        "g17_guard": g17_guard(v13, v14),
        **({"negation_scope": negation_scope_delta(v13, v14)}
           if "negation_scope" in v13 and "negation_scope" in v14 else {}),
        "labels": {"g20_dev": "development set (designed against)", "g20_holdout": "weakly held-out synthetic",
                   "g21_adversarial": adversarial_label},
    }


def build_private(v13: dict, v14: dict) -> dict:
    agg = {"note": "previously inspected private postings -- NOT independent validation; integer counts only"}
    for name in v14["private_unlabeled"]:
        a, b = v13["private_unlabeled"][name], v14["private_unlabeled"][name]
        per_a, per_b = a["per_posting"], b["per_posting"]
        agg[name] = {"postings": a["postings"],
                     **{f"{k}_v13": a[k] for k in a if k not in ("postings", "per_posting")},
                     **{f"{k}_v14": b[k] for k in b if k not in ("postings", "per_posting")},
                     "postings_changed": sum(1 for x, y in zip(per_a, per_b) if x != y),
                     "postings_losing_all_rows": sum(1 for x, y in zip(per_a, per_b) if x[0] and not y[0])}
    lab = {}
    for name in v14["private_labeled"]:
        if name == "note":
            continue
        a, b = v13["private_labeled"][name], v14["private_labeled"][name]
        lab[name] = {"claims": a.get("claims"), "located": a.get("located"), "v13": a.get("live"), "v14": b.get("live")}
    agg["label_backed"] = lab
    return agg


def _encode(report: dict) -> bytes:
    return (json.dumps(report, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def _encode_private(agg: dict) -> bytes:
    return (json.dumps(agg, indent=1) + "\n").encode("utf-8")


def _v13_dump(tmp: Path, private: bool) -> dict:
    clone = tmp / "v13"
    subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(REPO_ROOT), str(clone)], check=True,
                   capture_output=True)
    subprocess.run(["git", "checkout", "--quiet", V13_REF], cwd=clone, check=True, capture_output=True)
    shutil.copyfile(DUMP, clone / "scripts" / "evaluation_lib" / "m11g21_parser_dump.py")
    return _dump(clone, tmp / "v13.json", private)


def reproduce_original(private: bool) -> int:
    """Rebuild the FIRST v14 (before the negation-scope correction, never committed) by applying
    `first_v14_reverse.patch` to the three production files of a throwaway clone of HEAD (or of the
    working tree with --from-working-tree), re-run the comparison exactly as recorded (no
    negation-scope set; original adversarial label) and require byte-identical output."""
    from_wt = "--from-working-tree" in sys.argv
    with tempfile.TemporaryDirectory(prefix="m11g21-first-v14-") as tmpdir:
        tmp = Path(tmpdir)
        v13 = _v13_dump(tmp, private)
        first = tmp / "first_v14"
        subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", "-c", "core.autocrlf=false", str(REPO_ROOT),
                        str(first)], check=True, capture_output=True)
        if from_wt:
            for rel in PRODUCTION:
                (first / rel).write_bytes((REPO_ROOT / rel).read_bytes().replace(b"\r\n", b"\n"))
        lf_patch = tmp / "first_v14_reverse.lf.patch"  # autocrlf checkouts give the patch CRLF endings
        lf_patch.write_bytes(FIRST_V14_PATCH.read_bytes().replace(b"\r\n", b"\n"))
        subprocess.run(["git", "apply", str(lf_patch)], cwd=first, check=True)
        shutil.copyfile(DUMP, first / "scripts" / "evaluation_lib" / "m11g21_parser_dump.py")
        os.environ["M11G21_SKIP_NEGATION_SCOPE"] = "1"
        try:
            v14 = _dump(first, tmp / "first_v14.json", private)
        finally:
            os.environ.pop("M11G21_SKIP_NEGATION_SCOPE", None)
    ok = _encode(build_report(v13, v14, ORIGINAL_ADVERSARIAL_LABEL)) == (OUT_DIR / "v13_v14_comparison.json").read_bytes()
    print("original comparison reproduced byte-identically:", ok)
    if private:
        okp = _encode_private(build_private(v13, v14)) == (OUT_DIR / "private_v13_v14_aggregates.json").read_bytes()
        print("original private aggregates reproduced byte-identically:", okp)
        ok = ok and okp
    return 0 if ok else 1


def main() -> None:
    private = "--private-corpora" in sys.argv
    if "--reproduce-original" in sys.argv:
        raise SystemExit(reproduce_original(private))
    suffix = _label()
    if not suffix:
        raise SystemExit("v13_v14_comparison.json is the preserved FIRST-v14 record; regenerate the current "
                         "implementation with --label revised, or verify the record with --reproduce-original")
    with tempfile.TemporaryDirectory(prefix="m11g21-v13-") as tmpdir:
        tmp = Path(tmpdir)
        v13 = _v13_dump(tmp, private)
        v14 = _dump(REPO_ROOT, tmp / "v14.json", private)
    report = build_report(v13, v14, REVISED_ADVERSARIAL_LABEL)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"v13_v14{suffix}_comparison.json").write_bytes(_encode(report))
    for name, d in report["controls"].items():
        print(name, "v13", d["v13"]["false_admission_units"], d["v13"]["necessity"], d["near_neighbour_pairs_correct"]["v13"],
              "| v14", d["v14"]["false_admission_units"], d["v14"]["necessity"], d["near_neighbour_pairs_correct"]["v14"],
              "| lost", d["lost_genuine_qualifications"], "| new false", d["new_false_admissions"])
    print("adapter vs live:", report["research_adapter_vs_live"])
    for name, d in report["corpora"].items():
        print(name, {k: d[k] for k in ("rows_removed", "rows_added", "necessity_changed", "newly_declined_claims")},
              "fixed", d["gold_fixed_ids"], "REGRESSED", d["gold_regressed_ids"])
    for name, d in report["scoring"].items():
        print(name, "score changed", len(d["score_changed"]), "den changed", len(d["denominator_changed"]),
              "undefined", d["became_undefined"], "status", d["status_changed_on_kept_rows"],
              "elig", d["eligibility_changed_on_kept_rows"], "newSupp", d["new_false_supported_candidates"])
    print("G17", report["g17_guard"])
    if "negation_scope" in report:
        ns = report["negation_scope"]
        print("negation-scope correct v13", ns["correct_v13"], "v14", ns["correct_v14"], "of", ns["controls"],
              [k for k, v in ns["results"].items() if not v["v14_correct"]])
    if private:
        agg = build_private(v13, v14)
        (OUT_DIR / f"private_v13_v14{suffix}_aggregates.json").write_bytes(_encode_private(agg))
        for k, v in agg["label_backed"].items():
            print("[private labeled]", k, "v13", {x: v["v13"].get(x) for x in ("nonqual_admitted", "qual_admitted",
                                                                              "qual_nec_correct", "qual_nec_scored")},
                  "v14", {x: v["v14"].get(x) for x in ("nonqual_admitted", "qual_admitted", "qual_nec_correct",
                                                       "qual_nec_scored")})


if __name__ == "__main__":
    main()
