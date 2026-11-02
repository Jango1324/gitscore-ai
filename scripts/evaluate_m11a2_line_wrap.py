"""Milestone 11-A2 Phases 3/4 -- line-wrap candidate comparison and
regression evaluation.

Evaluation-only, additive, read-only against production code. Loads
`evaluation/m11a2/line_wrap_controls.json` (38 independently-annotated
unwrapped/wrapped pairs) and re-runs every candidate in
`scripts/evaluation_lib/line_wrap_classifiers.py` LIVE against the
unmodified production detectors, then checks the same candidates
against every pre-existing frozen/regression corpus named in the
mission brief, to confirm Candidate C (the recommended design) fixes
the real residual fabrication without disturbing anything previously
correct.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from evaluation_lib.line_wrap_classifiers import run_candidate  # noqa: E402

M11A2_CORPUS_PATH = ROOT / "evaluation" / "m11a2" / "line_wrap_controls.json"
CANDIDATES = ("baseline", "a_naive", "b_structural_only", "c_recommended")


def _req_key(r):
    return (r.necessity.name, r.concept_id or "", r.alternative_concept_ids, r.category or "")


def _outcome_set(description: str, candidate: str, harden: bool) -> tuple:
    """A MULTISET (sorted tuple, duplicates preserved) of requirement
    keys plus the unparsed count -- a `frozenset` would silently
    collapse two IDENTICALLY-SHAPED-but-semantically-different
    requirements (same necessity/concept_id/category, different
    original_text) into one, hiding a real count difference. Found via
    this exact methodology bug while measuring `m11a2-ambiguous-01`:
    the wrapped variant's two separate, ordinary-shaped `category=
    "experience"` rows collapsed to the SAME single set element as the
    unwrapped variant's one row, falsely reporting "equivalent."
    """
    reqs, unparsed = run_candidate(description, candidate, harden_regexes=harden)
    keys = sorted(_req_key(r) for r in reqs)
    keys.append(("UNPARSED_COUNT", len(unparsed), None, None))
    return tuple(keys)


def part3_paired_corpus() -> dict:
    corpus = json.loads(M11A2_CORPUS_PATH.read_text(encoding="utf-8"))
    report = {c: {"equivalent": 0, "total": 0, "mismatches": []} for c in CANDIDATES}
    report["c_recommended_hardened"] = {"equivalent": 0, "total": 0, "mismatches": []}

    for control in corpus["controls"]:
        unwrapped = control["unwrapped_text"]
        wrapped = control["wrapped_text"]
        heading = control["section_context"]
        expect = control["expect_equivalent"]
        if unwrapped is None or wrapped is None:
            continue  # standalone stability controls (bullets/one-per-line/paragraph) checked separately below

        doc_u = (heading + "\n" + unwrapped) if heading else unwrapped
        doc_w = (heading + "\n" + wrapped) if heading else wrapped

        for cand in CANDIDATES:
            unwrapped_set = _outcome_set(doc_u, cand, harden=False)
            wrapped_set = _outcome_set(doc_w, cand, harden=False)
            actual_equivalent = unwrapped_set == wrapped_set
            report[cand]["total"] += 1
            if (actual_equivalent and expect is True) or (not actual_equivalent and expect != True):
                report[cand]["equivalent"] += 1
            else:
                report[cand]["mismatches"].append(
                    {"id": control["id"], "expected": expect, "actual_equivalent": actual_equivalent}
                )

        unwrapped_set_h = _outcome_set(doc_u, "c_recommended", harden=True)
        wrapped_set_h = _outcome_set(doc_w, "c_recommended", harden=True)
        actual_equivalent_h = unwrapped_set_h == wrapped_set_h
        report["c_recommended_hardened"]["total"] += 1
        if (actual_equivalent_h and expect is True) or (not actual_equivalent_h and expect != True):
            report["c_recommended_hardened"]["equivalent"] += 1
        else:
            report["c_recommended_hardened"]["mismatches"].append(
                {"id": control["id"], "expected": expect, "actual_equivalent": actual_equivalent_h}
            )

    return report


def part3_standalone_stability() -> dict:
    """Controls with no wrapped counterpart (bullets, one-per-line
    lists, paragraph boundaries) -- confirms each candidate's OWN
    output for these structurally-sensitive shapes is sane: never
    merges independent bullets/list items into one claim.
    """
    corpus = json.loads(M11A2_CORPUS_PATH.read_text(encoding="utf-8"))
    report = {c: [] for c in CANDIDATES}
    for control in corpus["controls"]:
        if control["wrapped_text"] is not None:
            continue  # has a paired counterpart -- handled by part3_paired_corpus()
        heading = control["section_context"]
        text = control["unwrapped_text"]
        doc = (heading + "\n" + text) if heading else text
        for cand in CANDIDATES:
            reqs, unparsed = run_candidate(doc, cand)
            n_claims = len(reqs) + len(unparsed)
            report[cand].append({"id": control["id"], "n_logical_claims": n_claims, "n_requirements": len(reqs)})
    return report


def part4_regression(corpus_name: str, texts: list[tuple[str, str]]) -> dict:
    report = {}
    for cand in CANDIDATES:
        total_baseline = 0
        total_candidate = 0
        removed = []
        added = []
        for item_id, text in texts:
            if not text.strip():
                continue
            base_reqs, _ = run_candidate(text, "baseline")
            cand_reqs, _ = run_candidate(text, cand)
            base_keys = {_req_key(r) for r in base_reqs}
            cand_keys = {_req_key(r) for r in cand_reqs}
            total_baseline += len(base_reqs)
            total_candidate += len(cand_reqs)
            for k in base_keys - cand_keys:
                removed.append((item_id, k))
            for k in cand_keys - base_keys:
                added.append((item_id, k))
        report[cand] = {
            "baseline_total": total_baseline,
            "candidate_total": total_candidate,
            "removed_count": len(removed),
            "added_count": len(added),
            "removed_examples": removed[:10],
            "added_examples": added[:10],
        }
    return report


def _load_m11_postings():
    corpus = json.loads((ROOT / "evaluation" / "m11" / "corpus.json").read_text(encoding="utf-8"))
    return [(p["id"], p["raw_text"]) for p in corpus["postings"]]


def _load_m10a_postings():
    out = []
    for name, path in (
        ("SOTI", ROOT / "evaluation" / "m10" / "source" / "soti_raw.txt"),
        ("MANULIFE", ROOT / "evaluation" / "m10" / "source" / "manulife_raw.txt"),
    ):
        out.append((name, path.read_text(encoding="utf-8")))
    return out


def _load_m10d_fragments():
    data = json.loads((ROOT / "evaluation" / "m10d" / "alternative_controls.json").read_text(encoding="utf-8"))
    return [(c["id"], c["text"]) for c in data["controls"]]


def _load_m9b_fragments():
    data = json.loads((ROOT / "evaluation" / "m9b" / "corpus.json").read_text(encoding="utf-8"))
    return [(e["id"], e["source_text"]) for e in data["entries"]]


def _load_gold_fragments(dirname: str):
    out = []
    seen = set()
    for path in sorted((ROOT / dirname / "jobs").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for i, req in enumerate(data.get("expected_requirements", [])):
            claim_text = req.get("claim_text")
            if claim_text and claim_text not in seen:
                seen.add(claim_text)
                out.append((f"{data['job_id']}#{i}", claim_text))
    return out


def main():
    print("=" * 80)
    print("PART 3a -- M11-A2 paired corpus: wrapped/unwrapped equivalence by candidate")
    print("=" * 80)
    p3 = part3_paired_corpus()
    for cand, stats in p3.items():
        print(f"  {cand:28s} {stats['equivalent']}/{stats['total']} match expectation")
        for m in stats["mismatches"]:
            print(f"      MISMATCH {m['id']}: expected_equivalent={m['expected']} actual_equivalent={m['actual_equivalent']}")

    print()
    print("=" * 80)
    print("PART 3b -- standalone stability controls (bullets / one-per-line / paragraph)")
    print("=" * 80)
    p3b = part3_standalone_stability()
    for cand, rows in p3b.items():
        print(f"  {cand}:")
        for row in rows:
            print(f"      {row['id']}: n_logical_claims={row['n_logical_claims']} n_requirements={row['n_requirements']}")

    print()
    print("=" * 80)
    print("PART 4 -- regression corpora (baseline vs candidate requirement counts)")
    print("=" * 80)
    regression_corpora = {
        "m10a_real_postings": _load_m10a_postings(),
        "m11_held_out_postings": _load_m11_postings(),
        "m10d_alternative_controls": _load_m10d_fragments(),
        "m9b_preservation": _load_m9b_fragments(),
        "gold_8c_v1": _load_gold_fragments("evaluation/gold"),
        "gold_8c_v1_1": _load_gold_fragments("evaluation/gold_v1_1"),
    }
    p4 = {}
    for name, texts in regression_corpora.items():
        print(f"  {name} ({len(texts)} items):")
        result = part4_regression(name, texts)
        p4[name] = result
        for cand, stats in result.items():
            print(
                f"      {cand:28s} baseline={stats['baseline_total']:4d} candidate={stats['candidate_total']:4d} "
                f"removed={stats['removed_count']} added={stats['added_count']}"
            )
            for item_id, key in stats["added_examples"]:
                print(f"          ADDED   [{item_id}] {key}")
            for item_id, key in stats["removed_examples"]:
                print(f"          REMOVED [{item_id}] {key}")

    out_path = ROOT / "evaluation" / "reports" / "m11a2_line_wrap_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _serialize_mismatch_list(lst):
        return lst

    serializable_p4 = {}
    for name, result in p4.items():
        serializable_p4[name] = {
            cand: {
                "baseline_total": stats["baseline_total"],
                "candidate_total": stats["candidate_total"],
                "removed_count": stats["removed_count"],
                "added_count": stats["added_count"],
                "removed_examples": [[i, list(k)] for i, k in stats["removed_examples"]],
                "added_examples": [[i, list(k)] for i, k in stats["added_examples"]],
            }
            for cand, stats in result.items()
        }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "part3a_paired_corpus": p3,
                "part3b_standalone_stability": p3b,
                "part4_regression": serializable_p4,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
