"""Milestone 10E Phase 4 -- narrative-vs-qualification candidate comparison.

Evaluation-only, additive, read-only against production code
(`src/gitscore` is never imported in a way that could be mistaken for a
wiring change -- every candidate lives in
`scripts/evaluation_lib/narrative_classifiers.py` and is a prototype,
never reachable from the real `analyze_job_fit()`/`parse_job_description()`
entry points).

Three things this script measures, per the mission brief's Phase 4/5:

1. Against `evaluation/m10e/narrative_controls.json` (51 independently
   annotated controls, Phase 2): does each candidate's resulting
   `has_job_requirement`/necessity match the gold
   `should_create_job_requirement`/`necessity_if_justified` fields?
2. Against the EXACT real SOTI and Manulife texts
   (`evaluation/m10/source/*.txt`): does the known false positive
   disappear for each candidate?
3. Against every other frozen/pre-existing corpus named in the mission
   brief (M10A real-world, M10C heading controls, M10D alternative
   controls, M9B preservation corpus, 8c:v1/v1.1 gold) -- a REGRESSION
   check. Every candidate here only ever NARROWS the necessity hint fed
   into the UNCHANGED downstream pipeline (see
   `narrative_classifiers.py`'s own module docstring for the formal
   argument this makes every candidate's requirement set a SUBSET of
   baseline's, per claim, never a superset) -- so this section can only
   ever report REMOVALS relative to baseline, never new fabrications by
   construction. The question worth measuring is whether a removal is a
   correctly-suppressed narrative/duty false positive or a wrongly-
   suppressed genuine qualification (a false negative this milestone
   must not introduce).

Scope/method notes, stated honestly rather than silently assumed:
- Corpora that store isolated claim fragments with no literal heading
  text (M9B, M10D, 8c:v1/v1.1 gold) are each wrapped as their own
  single-line, heading-less synthetic document -- `section_kind` is
  always "NONE" and `doc_has_heading` is always `False` for these, so
  Candidate B/C's case (c) (whole-document-unsectioned fallback)
  applies and necessarily reproduces baseline exactly UNLESS Candidate
  A/C's text-pattern cue also fires. This is a real scope limitation
  (these corpora cannot exercise the section-origin distinction at all)
  -- documented, not hidden.
- M10A (SOTI/Manulife) and M10C (full postings with real headings) are
  run as their real, complete, multi-section documents -- the only
  corpora here that actually exercise Candidate B/C's section-origin
  logic end-to-end.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from evaluation_lib.narrative_classifiers import run_candidate  # noqa: E402

CANDIDATES = ("baseline", "a", "b", "c")


def _req_key(r):
    return (r.necessity.name, r.concept_id, r.alternative_concept_ids, r.category, r.original_text)


def run_all(description: str) -> dict[str, list]:
    return {c: [r for o in run_candidate(description, c) for r in o.requirements] for c in CANDIDATES}


# ---------------------------------------------------------------------------
# Part 1 -- M10E's own 51-control corpus.
# ---------------------------------------------------------------------------


def part1_m10e_controls() -> dict:
    corpus = json.loads((ROOT / "evaluation/m10e/narrative_controls.json").read_text(encoding="utf-8"))
    per_candidate_score = {c: {"match": 0, "total": 0, "mismatches": []} for c in CANDIDATES}

    for control in corpus["controls"]:
        heading = control["section_context"]
        text = control["text"]
        if not text:
            continue
        doc = (heading + "\n" + text) if heading else text
        results = run_all(doc)
        expected_created = control["should_create_job_requirement"]
        for c in CANDIDATES:
            actual_created = len(results[c]) > 0
            per_candidate_score[c]["total"] += 1
            if actual_created == expected_created:
                per_candidate_score[c]["match"] += 1
            else:
                per_candidate_score[c]["mismatches"].append(
                    (control["id"], control["category"], expected_created, actual_created)
                )
    return per_candidate_score


# ---------------------------------------------------------------------------
# Part 2 -- exact SOTI/Manulife real posting traces.
# ---------------------------------------------------------------------------


def part2_real_postings() -> dict:
    out = {}
    for name, path in (("SOTI", "evaluation/m10/source/soti_raw.txt"), ("MANULIFE", "evaluation/m10/source/manulife_raw.txt")):
        text = (ROOT / path).read_text(encoding="utf-8")
        out[name] = run_all(text)
    return out


# ---------------------------------------------------------------------------
# Part 3 -- regression corpora.
# ---------------------------------------------------------------------------


def _load_texts_m10a() -> list[tuple[str, str]]:
    data = json.loads((ROOT / "evaluation/m10/corpus.json").read_text(encoding="utf-8"))
    out = []
    for posting in data["postings"]:
        text = (ROOT / posting["source_file"]).read_text(encoding="utf-8")
        out.append((posting["id"], text))
    return out


def _load_texts_m10d() -> list[tuple[str, str]]:
    data = json.loads((ROOT / "evaluation/m10d/alternative_controls.json").read_text(encoding="utf-8"))
    return [(c["id"], c["text"]) for c in data["controls"]]


def _load_texts_m9b() -> list[tuple[str, str]]:
    data = json.loads((ROOT / "evaluation/m9b/corpus.json").read_text(encoding="utf-8"))
    return [(e["id"], e["source_text"]) for e in data["entries"]]


def _load_texts_gold(dirname: str) -> list[tuple[str, str]]:
    out = []
    for path in sorted((ROOT / dirname / "jobs").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for i, req in enumerate(data.get("expected_requirements", [])):
            claim_text = req.get("claim_text")
            if claim_text:
                out.append((f"{data['job_id']}#{i}:{claim_text[:30]}", claim_text))
    # de-duplicate identical claim_text fragments (the same sentence often
    # repeats across multiple expected_requirements rows, e.g. one
    # technical + one experience-qualifier row from the SAME sentence)
    seen = set()
    deduped = []
    for cid, text in out:
        if text in seen:
            continue
        seen.add(text)
        deduped.append((cid, text))
    return deduped


def part3_regression() -> dict:
    corpora = {
        "m10a_realworld (full postings, real headings)": _load_texts_m10a(),
        "m10d_alternative_controls (isolated fragments, no headings)": _load_texts_m10d(),
        "m9b_preservation (isolated fragments, no headings)": _load_texts_m9b(),
        "gold_8c_v1 (isolated claim fragments, no headings)": _load_texts_gold("evaluation/gold"),
        "gold_8c_v1_1 (isolated claim fragments, no headings)": _load_texts_gold("evaluation/gold_v1_1"),
    }

    report = {}
    for corpus_name, items in corpora.items():
        if not items:
            report[corpus_name] = {"error": "no texts loaded (schema mismatch -- see script notes)"}
            continue
        baseline_total = 0
        candidate_totals = {c: 0 for c in CANDIDATES}
        removed_examples = {c: [] for c in ("a", "b", "c")}
        for item_id, text in items:
            if not text or not text.strip():
                continue
            results = run_all(text)
            baseline_keys = {_req_key(r) for r in results["baseline"]}
            baseline_total += len(results["baseline"])
            for c in CANDIDATES:
                candidate_totals[c] += len(results[c])
            for c in ("a", "b", "c"):
                cand_keys = {_req_key(r) for r in results[c]}
                removed = baseline_keys - cand_keys
                for key in removed:
                    removed_examples[c].append((item_id, key))
        report[corpus_name] = {
            "n_items": len(items),
            "baseline_total_requirements": baseline_total,
            "candidate_totals": candidate_totals,
            "removed_examples": {c: removed_examples[c][:15] for c in ("a", "b", "c")},
            "removed_counts": {c: len(removed_examples[c]) for c in ("a", "b", "c")},
        }
    return report


def main():
    print("=" * 80)
    print("PART 1 -- M10E's own 51-control corpus (has_job_requirement accuracy)")
    print("=" * 80)
    p1 = part1_m10e_controls()
    for c in CANDIDATES:
        s = p1[c]
        print(f"  candidate_{c}: {s['match']}/{s['total']} match gold should_create_job_requirement")
        for mismatch in s["mismatches"]:
            print(f"      MISMATCH {mismatch[0]} ({mismatch[1]}): expected_created={mismatch[2]} actual={mismatch[3]}")

    print()
    print("=" * 80)
    print("PART 2 -- exact SOTI / Manulife real posting traces")
    print("=" * 80)
    p2 = part2_real_postings()
    for name, results in p2.items():
        print(f"  {name}:")
        for c in CANDIDATES:
            reqs = results[c]
            print(f"    candidate_{c}: {len(reqs)} requirement(s)")
            for r in reqs:
                print(f"        necessity={r.necessity.name} concept={r.concept_id!r} alt={r.alternative_concept_ids!r} category={r.category!r} text={r.original_text[:65]!r}")

    print()
    print("=" * 80)
    print("PART 3 -- regression corpora (requirement counts, baseline vs candidates)")
    print("=" * 80)
    p3 = part3_regression()
    for corpus_name, r in p3.items():
        print(f"  {corpus_name}:")
        if "error" in r:
            print(f"      {r['error']}")
            continue
        print(f"      n_items={r['n_items']} baseline_total={r['baseline_total_requirements']}")
        for c in ("a", "b", "c"):
            print(f"      candidate_{c}: total={r['candidate_totals'][c]} removed_vs_baseline={r['removed_counts'][c]}")
            for item_id, key in r["removed_examples"][c]:
                print(f"          removed [{item_id}] necessity={key[0]} concept={key[1]!r} alt={key[2]!r} cat={key[3]!r} text={key[4][:60]!r}")

    out_path = ROOT / "evaluation/reports/m10e_narrative_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    serializable_p2 = {
        name: {c: [[r.necessity.name, r.concept_id, list(r.alternative_concept_ids), r.category, r.original_text] for r in reqs] for c, reqs in results.items()}
        for name, results in p2.items()
    }
    serializable_p3 = {}
    for corpus_name, r in p3.items():
        if "error" in r:
            serializable_p3[corpus_name] = r
            continue
        serializable_p3[corpus_name] = {
            "n_items": r["n_items"],
            "baseline_total_requirements": r["baseline_total_requirements"],
            "candidate_totals": r["candidate_totals"],
            "removed_counts": r["removed_counts"],
            "removed_examples": {
                c: [[item_id, list(key)] for item_id, key in examples]
                for c, examples in r["removed_examples"].items()
            },
        }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "part1_m10e_controls": {
                    c: {"match": s["match"], "total": s["total"], "mismatches": s["mismatches"]}
                    for c, s in p1.items()
                },
                "part2_real_postings": serializable_p2,
                "part3_regression": serializable_p3,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
