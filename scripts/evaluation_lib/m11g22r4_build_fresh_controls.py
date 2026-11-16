"""Milestone 11-G22-R4 -- freeze the FRESH README validation set (separately authored; run once).

    python scripts/evaluation_lib/m11g22r4_build_fresh_controls.py <part1.json> <part2.json> <part3.json>

The cases were written by a SEPARATE author (a fresh Claude subagent instance, same model family as the policy
author) that was given only the classification task, the declared evidence-validity policy, the registry vocabulary,
the artifact rules and the output schema -- never the R4 (or D / R3) rules, code, tests, design sets or results, and
it was restricted to the Write tool (no repository access). Its raw files were hashed on receipt, BEFORE the R4 policy
design freeze; this script runs only AFTER that freeze.

This script RE-SHAPES each case into the G22-R2 harness schema (`family` <- category, `probe` <- target, `concepts`
<- mentions, `note` <- rationale) and carries the Phase-7 fields verbatim (`occurrences`, `corroborated`,
`expected_target_status`). Labels, texts and artifacts are copied verbatim; nothing is edited. Pre-freeze checks
(schema, concept-level label completeness against a plain registry alias scan, occurrence-count alignment) are
RECORDED, never used to change a label. The frozen file and its G14 portable freeze record are written once.
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
OUT = REPO_ROOT / "evaluation" / "m11g22r4"
CLASSES = {"use", "ordinary", "reference", "historical", "future", "negated", "ambiguous"}
AMBIGUOUS_CONCEPTS = {"framework.react", "framework.express", "language.swift", "language.rust", "language.ruby",
                      "language.shell", "ml.framework.pytorch", "language.python", "language.java", "framework.flask",
                      "data.library.pandas"}
DISCLOSURE = ("Authored by a separate Claude subagent instance given only the task, the declared evidence-validity "
              "policy, the registry vocabulary, the artifact rules and the output schema; it was never shown any R4, "
              "D or R3 rule, code, test, design set or result, and it could use only the Write tool. It is the same "
              "model family as the policy author, so this is NOT human-independent validation. Labels are frozen "
              "exactly as authored.")


def _scan(readme: str) -> set[str]:
    reg = default_registry()
    return {c.concept_id for c in reg.all_concepts() for a in c.readme_safe_aliases() if alias_pattern(a).search(readme)}


def convert(cases: list[dict]) -> tuple[dict, dict]:
    known = {c.concept_id for c in default_registry().all_concepts()}
    controls, checks = [], Counter()
    issues = []
    for case in cases:
        mentions = dict(case["mentions"])
        assert case["target"] in known, case["id"]
        assert case["target"] in AMBIGUOUS_CONCEPTS, case["id"]
        assert set(mentions) <= known and set(mentions.values()) <= CLASSES, case["id"]
        assert set(case["used"]) <= known and set(case["uncertain"]) <= known, case["id"]
        assert set(case.get("corroborated", [])) <= known, case["id"]
        exp = {"SUPPORTED", "NOT_SUPPORTED", "UNCERTAIN"}
        assert case["expected_target_status"] in exp, case["id"]
        derived = ("UNCERTAIN" if case["target"] in case["uncertain"] else
                   "SUPPORTED" if case["target"] in case["used"] else "NOT_SUPPORTED")
        if derived != case["expected_target_status"]:
            issues.append([case["id"], "expected_target_status disagrees with used/uncertain", derived])
        scanned = set().union(*(_scan(r["readme"] or "") for r in case["repos"]))
        unlabelled, phantom = sorted(scanned - set(mentions)), sorted(set(mentions) - scanned)
        checks["unlabelled_mentions"] += len(unlabelled)
        checks["labels_without_mention"] += len(phantom)
        if unlabelled or phantom:
            issues.append([case["id"], "concept label completeness", {"unlabelled": unlabelled, "phantom": phantom}])
        for o in case.get("occurrences", []):
            assert o["class"] in CLASSES and o["concept"] in known, case["id"]
        controls.append({
            "id": f"m11g22r4-{case['id']}", "split": "fresh", "family": case["category"], "probe": case["target"],
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
    checks["cases"] = len(controls)
    return controls, {"counts": dict(checks), "issues": issues}


def main() -> None:
    target, record, prov = OUT / "fresh_validation_controls.json", OUT / "fresh_hash_freeze.json", \
        OUT / "fresh_author_provenance.json"
    if target.exists() or record.exists() or prov.exists():
        raise SystemExit("REFUSING to overwrite an existing freeze")
    raw, cases, notes = {}, [], []
    for path in sys.argv[1:4]:
        data = Path(path).read_bytes()
        raw[Path(path).name] = gi.sha256(data)
        doc = json.loads(data.decode("utf-8"))
        assert doc["set"] == "fresh"
        cases += doc["cases"]
        notes.append(doc.get("author_note", ""))
    assert len({c["id"] for c in cases}) == len(cases)
    controls, checks = convert(cases)
    design = json.loads((OUT / "policy_design_freeze.json").read_text(encoding="utf-8"))
    assert design["fresh_raw_author_files_sha256_before_freeze"] == raw, "raw author files changed since receipt"
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {"schema_version": 1, "milestone": "M11-G22-R4 (high-recall README evidence guard research)",
           "split": "fresh", "provenance": "author-created synthetic READMEs and repository artifacts; no real README, "
                                           "posting, employer or private material",
           "authorship_disclosure": DISCLOSURE, "author_notes": notes,
           "declared_evidence_validity_policy": "valid iff (1) the word refers to the technology in context and (2) "
                                                "the text attributes CURRENT use to THIS repository (written in / "
                                                "built with / depends on / requires / ships code in / is a library, "
                                                "plugin, client or bindings for it maintained here); not valid: "
                                                "ordinary sense, negation, historical, future / hypothetical, other "
                                                "projects' use, comparison / inspiration / reference",
           "label_timing": "labels frozen BEFORE any GitScore extractor, matcher or README policy ran on this set; "
                           "AFTER the R4 policy design freeze",
           "label_classes": sorted(CLASSES), "controls": controls}
    data = (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    target.write_bytes(data)
    sha = gi.sha256(gi.canonical_bytes(data))
    record.write_bytes((json.dumps({
        "frozen_file": "evaluation/m11g22r4/fresh_validation_controls.json", "sha256": sha,
        "sha256_lf_normalized": sha, "length_bytes": len(data), "canonical_contract": gi.CONTRACT,
        "frozen_at_utc": now,
        "note": "Labels frozen BEFORE any GitScore extractor, matcher or README policy ran on this set, and AFTER the "
                "R4 policy design freeze. NOT registered in the canonical manifest (pending authorization).",
    }, indent=2) + "\n").encode("utf-8"))
    prov.write_bytes((json.dumps({
        "author": "separate Claude subagent instance (same model family as the policy author; NOT "
                  "human-independent)",
        "author_inputs": "classification task, declared evidence-validity policy, registry vocabulary with matching "
                         "semantics, artifact rules (5% language floor; parsed root manifests; Docker presence), output "
                         "schema, coverage targets; NO R4/D/R3 rules, code, tests, design sets or results",
        "author_tool_calls": "Write x3 (one per part file); no read/search/command; author reported no post-write "
                             "edits",
        "raw_author_files_sha256": raw,
        "raw_hashes_recorded_at_utc": "2026-11-15T23:22:01Z (before the policy design freeze)",
        "policy_design_frozen_at_utc": design["frozen_at_utc"],
        "fresh_converted_and_frozen_at_utc": now,
        "leakage_disclosure": "the author's hand-back message (read by the policy author before the design freeze) "
                              "named about ten case-level details; no policy change was made after it",
        "pre_freeze_checks": checks,
    }, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print("fresh", len(controls), sha, checks["counts"], len(checks["issues"]), "issues")


if __name__ == "__main__":
    main()
