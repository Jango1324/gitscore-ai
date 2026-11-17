"""Milestone 11-G22-R5 -- freeze the FRESH attribution validation set (separately authored; run once).

    python scripts/evaluation_lib/m11g22r5_build_fresh_controls.py <part1.json> <part2.json> <part3.json>

The cases were written by a SEPARATE author (a fresh Claude subagent instance, same model family as the policy
author) that was given only the task, a declared evidence-validity policy, the registry vocabulary, the artifact
rules and the output schema -- never any G22-R/R2/R3/R4/R5 rule, code, test, control or result -- and was restricted
to the Write tool. Its reply was restricted to file paths and case counts (no case content). This script runs only
AFTER the R5 policy design freeze (`policy_design_freeze.json`), and records the raw author files' hashes.

Re-shapes each case into the G22-R2 harness schema (`family` <- category, `probe` <- target, `concepts` <- mentions,
`note` <- rationale) and carries the per-occurrence labels (incl. `attribution_kind`), `corroborated` and
`expected_target_status` verbatim. Pre-freeze checks (schema, concept-level label completeness against a plain
registry alias scan, status consistency) are RECORDED and never used to change a label. Written once.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parents[1] / "src"))

import gold_integrity as gi  # noqa: E402
from gitscore.concepts.matching import alias_pattern  # noqa: E402
from gitscore.concepts.registry import default_registry  # noqa: E402

REPO_ROOT = _HERE.parents[1]
OUT = REPO_ROOT / "evaluation" / "m11g22r5"
CLASSES = {"use", "ordinary", "reference", "historical", "future", "negated", "ambiguous"}
KINDS = {"this_project", "third_party_project", "third_party_docs", "reference_or_comparison", "quotation",
         "historical", "future_or_hypothetical", "negation", "not_technology", "unclear"}
DISCLOSURE = ("Authored by a separate Claude subagent instance given only the task, the declared evidence-validity "
              "policy, the registry vocabulary, the artifact rules and the output schema. It was never shown any "
              "G22-R/R2/R3/R4/R5 rule, code, test, control set or result, could use only the Write tool, and was "
              "instructed to reply with file paths and case counts only. It is the same model family as the policy "
              "author, so this is NOT human-independent validation. Labels are frozen exactly as authored.")


def _scan(readme: str) -> set[str]:
    reg = default_registry()
    return {c.concept_id for c in reg.all_concepts() for a in c.readme_safe_aliases() if alias_pattern(a).search(readme)}


def convert(cases: list[dict]) -> tuple[list[dict], dict]:
    known = {c.concept_id for c in default_registry().all_concepts()}
    controls, counts, issues = [], Counter(), []
    for case in cases:
        mentions = dict(case["mentions"])
        assert case["target"] in known and case["target"] not in {"language.c", "language.go"}, case["id"]
        assert set(mentions) <= known and set(mentions.values()) <= CLASSES, case["id"]
        assert set(case["used"]) <= known and set(case["uncertain"]) <= known, case["id"]
        assert set(case.get("corroborated", [])) <= known, case["id"]
        assert case["expected_target_status"] in {"SUPPORTED", "NOT_SUPPORTED", "UNCERTAIN"}, case["id"]
        for o in case.get("occurrences", []):
            assert o["class"] in CLASSES and o["concept"] in known, case["id"]
            if o.get("attribution_kind") not in KINDS:
                counts["occurrences_with_unknown_attribution_kind"] += 1
        derived = ("UNCERTAIN" if case["target"] in case["uncertain"] else
                   "SUPPORTED" if case["target"] in case["used"] else "NOT_SUPPORTED")
        if derived != case["expected_target_status"]:
            issues.append([case["id"], "expected_target_status disagrees with used/uncertain", derived])
        scanned = set().union(*(_scan(r["readme"] or "") for r in case["repos"]))
        unlabelled, phantom = sorted(scanned - set(mentions)), sorted(set(mentions) - scanned)
        counts["unlabelled_mentions"] += len(unlabelled)
        counts["labels_without_mention"] += len(phantom)
        if unlabelled or phantom:
            issues.append([case["id"], "concept label completeness", {"unlabelled": unlabelled, "phantom": phantom}])
        controls.append({
            "id": f"m11g22r5-{case['id']}", "split": "fresh", "family": case["category"], "probe": case["target"],
            "pair": case.get("pair"),
            "repos": [{"name": r["name"], "readme": r["readme"], "languages": r.get("languages") or {},
                       "files": r.get("files") or {}} for r in case["repos"]],
            "concepts": mentions, "used": list(case["used"]), "uncertain": list(case["uncertain"]),
            "corroborated": list(case.get("corroborated", [])), "occurrences": list(case.get("occurrences", [])),
            "expected_target_status": case["expected_target_status"],
            "expected_effect": {"probe_status": {"SUPPORTED": "supported", "NOT_SUPPORTED": "not_observed",
                                                 "UNCERTAIN": "uncertain"}[case["expected_target_status"]],
                                "score": {"SUPPORTED": 100, "NOT_SUPPORTED": 0, "UNCERTAIN": None}[
                                    case["expected_target_status"]]},
            "note": case.get("rationale", ""),
        })
    counts["cases"] = len(controls)
    return controls, {"counts": dict(sorted(counts.items())), "issues": issues}


def main() -> None:
    target, record, prov = (OUT / "fresh_validation_controls.json", OUT / "fresh_hash_freeze.json",
                            OUT / "fresh_author_provenance.json")
    if target.exists() or record.exists() or prov.exists():
        raise SystemExit("REFUSING to overwrite an existing freeze")
    design = json.loads((OUT / "policy_design_freeze.json").read_text(encoding="utf-8"))
    raw, cases, notes = {}, [], []
    for path in sys.argv[1:4]:
        data = Path(path).read_bytes()
        raw[Path(path).name] = gi.sha256(data)
        doc = json.loads(data.decode("utf-8"))
        assert doc["set"] == "r5_fresh"
        cases += doc["cases"]
        notes.append(doc.get("author_note", ""))
    assert len({c["id"] for c in cases}) == len(cases)
    controls, checks = convert(cases)
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert now > design["frozen_at_utc"]
    doc = {"schema_version": 1, "milestone": "M11-G22-R5 (attribution-aware README evidence research)",
           "split": "fresh", "provenance": "author-created synthetic READMEs and repository artifacts; no real README, "
                                           "posting, employer or private material",
           "authorship_disclosure": DISCLOSURE, "author_notes": notes,
           "declared_evidence_validity_policy": "valid iff (1) the word refers to the technology and (2) the text "
                                                "attributes CURRENT use to THIS repository; not valid: other "
                                                "projects' use, third-party documentation or quotations, comparison "
                                                "/ inspiration, historical, future / hypothetical, negation, "
                                                "ordinary sense",
           "label_timing": "labels frozen BEFORE any GitScore extractor, matcher or README policy ran on this set; "
                           "AFTER the R5 policy design freeze",
           "label_classes": sorted(CLASSES), "attribution_kinds": sorted(KINDS), "controls": controls}
    data = (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    target.write_bytes(data)
    sha = gi.sha256(gi.canonical_bytes(data))
    record.write_bytes((json.dumps({
        "frozen_file": "evaluation/m11g22r5/fresh_validation_controls.json", "sha256": sha,
        "sha256_lf_normalized": sha, "length_bytes": len(data), "canonical_contract": gi.CONTRACT,
        "frozen_at_utc": now,
        "note": "Labels frozen BEFORE any GitScore extractor, matcher or README policy ran on this set, and AFTER the "
                "R5 policy design freeze. NOT registered in the canonical manifest (pending authorization).",
    }, indent=2) + "\n").encode("utf-8"))
    prov.write_bytes((json.dumps({
        "author": "separate Claude subagent instance (same model family as the policy author; NOT "
                  "human-independent)",
        "author_saw_previous_examples": False,
        "author_inputs": "classification task, declared evidence-validity policy, registry vocabulary with matching "
                         "semantics, artifact rules, output schema, coverage targets; NO G22-R/R2/R3/R4/R5 rules, "
                         "code, tests, control sets or results",
        "author_reply_restriction": "file paths and case counts only; no case content",
        "raw_author_files_sha256": raw,
        "policy_design_frozen_at_utc": design["frozen_at_utc"],
        "fresh_converted_and_frozen_at_utc": now,
        "pre_freeze_checks": checks,
    }, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print("fresh", len(controls), sha, checks["counts"], len(checks["issues"]), "issues")


if __name__ == "__main__":
    main()
