"""Milestone 11-G22-R3 -- freeze the fresh README-context validation sets (VAL-1, VAL-2 reserve).

    python scripts/evaluation_lib/m11g22r3_build_controls.py <val1_raw.json> <val2_raw.json>

The cases were written by a SEPARATE author (a fresh Claude subagent instance) that was given only the classification
task, the alias / concept list, the artifact rules and the output schema -- never Policy D's rules, collocates,
non-use frames, code, tests or results, and no repository access. Same model family as the policy author, so this is
NOT human-independent validation; see `authorship_disclosure`.

This script only RE-SHAPES each author case into the G22-R2 harness schema (`family` <- category, `probe` <- target,
`concepts` <- mentions, `note` <- rationale). Labels, texts and artifacts are copied verbatim; nothing is edited. The
frozen file and its G14 portable freeze record are written once and never overwritten. VAL-2 is frozen at the same
time and is NOT run by anything until a revised policy (if any) is itself frozen.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parents[1] / "src"))

import gold_integrity as gi  # noqa: E402
from gitscore.concepts.registry import default_registry  # noqa: E402

REPO_ROOT = _HERE.parents[1]
OUT = REPO_ROOT / "evaluation" / "m11g22r3"
CLASSES = {"use", "ordinary", "reference", "historical", "future", "negated", "ambiguous"}
DISCLOSURE = ("Authored by a separate Claude subagent instance given only the task, the alias/concept list, the "
              "artifact rules and the output schema; it was never shown Policy D's rules, collocates, non-use frames, "
              "code, tests or results and had no repository access. It is the same model family as the policy "
              "author, so this is NOT human-independent validation. Labels are frozen exactly as authored.")


def convert(raw: dict, split: str) -> dict:
    reg = default_registry()
    known = {c.concept_id for c in reg.all_concepts()}
    controls = []
    for case in raw["cases"]:
        mentions = dict(case["mentions"])
        assert case["target"] in known, case["id"]
        assert set(mentions) <= known and set(mentions.values()) <= CLASSES, case["id"]
        assert set(case["used"]) <= known and set(case["uncertain"]) <= known, case["id"]
        controls.append({
            "id": f"m11g22r3-{case['id']}", "split": split, "family": case["category"], "probe": case["target"],
            "pair": case.get("pair"), "repos": [{"name": r["name"], "readme": r["readme"],
                                                  "languages": r.get("languages") or {}, "files": r.get("files") or {}}
                                                 for r in case["repos"]],
            "concepts": mentions, "used": list(case["used"]), "uncertain": list(case["uncertain"]),
            "note": case.get("rationale", ""),
        })
    return {
        "schema_version": 1,
        "milestone": "M11-G22-R3 (README context guard validation)",
        "split": split,
        "provenance": "author-created synthetic READMEs and repository artifacts; no real README, posting, employer or "
                      "private material",
        "authorship_disclosure": DISCLOSURE,
        "author_note": raw.get("author_note", ""),
        "label_timing": "labels frozen BEFORE any GitScore extractor, matcher or README policy ran on this set",
        "label_classes": sorted(CLASSES),
        "controls": controls,
    }


def freeze(doc: dict, split: str, now: str) -> None:
    target = OUT / f"validation_controls_{split}.json"
    record = OUT / f"{split}_hash_freeze.json"
    if target.exists() or record.exists():
        raise SystemExit(f"REFUSING to overwrite an existing freeze: {target.name}")
    data = (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    sha = gi.sha256(gi.canonical_bytes(data))
    record.write_bytes((json.dumps({
        "frozen_file": f"evaluation/m11g22r3/{target.name}",
        "sha256": sha, "sha256_lf_normalized": sha, "length_bytes": len(data),
        "canonical_contract": gi.CONTRACT, "frozen_at_utc": now,
        "note": "Labels frozen BEFORE any GitScore extractor, matcher or README policy ran on this set. NOT registered "
                "in the canonical manifest (pending authorization).",
    }, indent=2) + "\n").encode("utf-8"))
    print(split, len(doc["controls"]), sha)


def main() -> None:
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for path, split in zip(sys.argv[1:3], ("val1", "val2")):
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        assert raw["set"] == split
        freeze(convert(raw, split), split, now)


if __name__ == "__main__":
    main()
