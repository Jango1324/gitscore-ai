"""Milestone 11-G22-S2 -- real-pipeline comparison: readme:v5 (pinned) vs readme:v6 (occurrence-overlap correction).

    python scripts/evaluate_m11g22s2_occurrence_overlap.py

Runs the REAL pipeline (README extractor, evidence aggregation / 8c end-to-end profiles, matcher v1, scoring v2) under
production readme:v6 and pinned to readme:v5 (`scripts/evaluation_lib/readme_v5_pin.py`), reusing G22-S1's
measurement code (`evaluate_m11g22s1_setext_boundaries.measure / compare`). Adds an inventory of every React / React
Native occurrence in the frozen 8c READMEs. Writes `evaluation/m11g22s2/occurrence_overlap_comparison.json` (public
synthetic controls and public 8c fixtures only). No LLM, no network, no private data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import evaluate_m11g22s1_setext_boundaries as s1  # noqa: E402
import readme_v5_pin  # noqa: E402
from evaluation_lib.loaders import list_candidate_names, load_candidate_fixture  # noqa: E402
from gitscore.concepts.matching import alias_pattern  # noqa: E402
from gitscore.evidence.extraction import readme as readme_mod  # noqa: E402

OUT = REPO_ROOT / "evaluation" / "m11g22s2"
OVERLAP_ALIASES = ("react", "react.js", "reactjs", "react native", "react-native", "reactnative")


def react_inventory() -> dict:
    """Every React / React Native alias occurrence in the frozen 8c READMEs, and the README items it yields."""
    out = {}
    for name in list_candidate_names():
        for repo, sel in load_candidate_fixture(name)["selected"].items():
            text = (sel.get("readme") or [None])[0]
            if not text:
                continue
            occ = sorted({(m.start(), m.end(), alias) for alias in OVERLAP_ALIASES
                          for m in alias_pattern(alias).finditer(text)})
            if occ:
                out[f"{name}/{repo}"] = {"occurrences": [[s, e, a] for s, e, a in occ],
                                         "readme_items": sorted(cid for cid in s1._readme_items(text, name, repo)
                                                                if cid in ("framework.react", "framework.react_native"))}
    return out


def main() -> None:
    if readme_mod.EXTRACTOR_VERSION != "readme:v6":
        raise SystemExit("G22-S2 compares readme:v5 (pinned) against production readme:v6")
    v6, inv6 = s1.measure(), react_inventory()
    with readme_v5_pin.pinned():
        v5, inv5 = s1.measure(), react_inventory()
    report = s1.compare(v5, v6)
    report["note"] = report["note"].replace("readme:v4 via readme_v4_pin (production's unchanged ATX-only heading index)",
                                            "readme:v5 via readme_v5_pin (v6 minus the occurrence-overlap predicate)")
    report["react_occurrences_8c"] = {k: {"occurrences": inv6[k]["occurrences"], "readme_items_v5": inv5[k]["readme_items"],
                                          "readme_items_v6": inv6[k]["readme_items"]} for k in sorted(inv6)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "occurrence_overlap_comparison.json").write_bytes(
        (json.dumps(report, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
    for name, s in report["labelled_sets"].items():
        print(name.ljust(12), "recovered", len(s["readme_items_recovered"]), "excluded", len(s["readme_items_newly_excluded"]),
              "moved", len(s["provenance_moved"]), "status", len(s["match_status_changes"]), "FS", s["false_supported"],
              "trueSUP", s["true_supported"])
    print("g22r changed", report["g22r_controls"]["changed_controls"])
    print("8c", {n: v for n, v in report["fixtures_8c"].items() if v["added"] or v["removed"] or v["provenance_moved"]})
    print("8c matrix changes", report["matrix_8c_changes"], "undefined", report["undefined_score_changes"])
    print("capability identical", report["capability_identical"])
    print("8c React/React Native occurrences", json.dumps(report["react_occurrences_8c"]))


if __name__ == "__main__":
    main()
