"""Milestone 11-G22-R4 -- high-recall (inverse) README evidence guard research (readme:v5 NOT implemented).

    python scripts/evaluate_m11g22r4_high_recall_guard.py [--fresh] [--private-corpora] [--skip-test-runs]

Real parser v15, real evidence pipeline (readme:v4 + language / Docker / manifest extractors), matcher v1 and scoring
v2. README policies are offline adapters: production readme:v4 (P0), the R4 inverse candidates P1-P4
(`scripts/evaluation_lib/m11g22r4_policies.py`), and G22-R2's D and G22-R3's R3, unchanged, for comparison. No
production code, registry data or LLM is used; nothing here calls a model.

Sets: seen design data (G22-R DEV/EVAL, G22-R2 DEV/EVAL, G22-R3 VAL-1/VAL-2, 8c, R4 DEV) and, with --fresh, the
separately authored fresh validation set, which is frozen after the R4 policy design freeze and evaluated against
the gates declared in `evaluation/m11g22r4/policy_design_freeze.json`. Before anything runs, every file hash in that
freeze is re-verified: a policy edited after the freeze cannot be evaluated here.

Writes `evaluation/m11g22r4/high_recall_guard_report.json` (public: synthetic controls, public 8c fixtures, counts)
and, with --private-corpora, `private_high_recall_guard_aggregates.json` (integer counts only).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import evaluate_m11g22r2_readme_context as r2  # noqa: E402
import gold_integrity as gi  # noqa: E402
import m11g22r2_harness as h  # noqa: E402
import m11g22r2_policies as p2  # noqa: E402
import m11g22r3_policies as p3  # noqa: E402
import m11g22r4_policies as p4  # noqa: E402
import m11g22r_harness as h22r  # noqa: E402
import m11g22r_policies as rpol  # noqa: E402
from evaluation_lib.loaders import list_candidate_names, load_candidate_fixture  # noqa: E402
from gitscore.assessment import SCORING_VERSION  # noqa: E402
from gitscore.concepts.registry import CONCEPT_REGISTRY_VERSION, default_registry  # noqa: E402
from gitscore.evidence.capability import concept_capability  # noqa: E402
from gitscore.evidence.extraction import readme_context as rc  # noqa: E402
import readme_v4_pin  # noqa: E402
from gitscore.evidence.extraction.readme import evidence_from_readme  # noqa: E402
from readme_v4_pin import EXTRACTOR_VERSION  # noqa: E402  (measured: readme:v4)
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION  # noqa: E402
from gitscore.matching import MATCHER_VERSION  # noqa: E402

OUT = REPO_ROOT / "evaluation" / "m11g22r4"
R3_OUT = REPO_ROOT / "evaluation" / "m11g22r3"
CHOSEN = p4.P4
POLICIES = (p2.A, *p4.CANDIDATES, p2.D, p3.R3)
NON_USE = ("ordinary", "reference", "historical", "future", "negated")
AGG_KEYS = ("false_supported", "false_supported_by_probe_class", "false_readme_evidence_ordinary",
            "nonuse_readme_evidence", "ordinary_correctly_rejected", "use_claims_retained", "genuine_use_lost",
            "corroborated_supported", "true_supported", "missed_true_supported", "true_not_supported", "uncertain",
            "numerator", "denominator", "readme_items_by_label_class", "unlabelled_readme_concepts")


@contextmanager
def r2_policies(policies):
    saved = r2.ALL
    r2.ALL = tuple(policies)
    try:
        yield
    finally:
        r2.ALL = saved


def _ambiguous_concepts() -> set[str]:
    return {c.concept_id for c in default_registry().all_concepts()
            if any(a in p4.AMBIGUOUS for a in c.readme_safe_aliases())}


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["controls"]


SEEN_SETS = {
    "r4_dev": lambda: _load(OUT / "dev_controls.json"),
    "g22r2_dev": lambda: h.load_controls("dev"),
    "g22r2_eval": lambda: h.load_controls("eval"),
    "g22r3_val1": lambda: _load(R3_OUT / "validation_controls_val1.json"),
    "g22r3_val2": lambda: _load(R3_OUT / "validation_controls_val2.json"),
}


# ---- freezes ------------------------------------------------------------------------------------------
def verify_design_unchanged() -> dict:
    design = json.loads((OUT / "policy_design_freeze.json").read_text(encoding="utf-8"))
    now = {f: gi.sha256(gi.canonical_bytes((REPO_ROOT / f).read_bytes())) for f in design["files"]}
    if now != design["files"]:
        raise SystemExit(f"R4 policy files changed after the design freeze: "
                         f"{sorted(f for f in now if now[f] != design['files'][f])}")
    return design


def freezes() -> dict:
    out = {}
    for name, rel_file, rel_rec in (("r4_dev", "dev_controls.json", "dev_hash_freeze.json"),
                                    ("r4_fresh", "fresh_validation_controls.json", "fresh_hash_freeze.json")):
        rec = json.loads((OUT / rel_rec).read_text(encoding="utf-8"))
        raw = (OUT / rel_file).read_bytes()
        out[name] = {"sha256": rec["sha256"], "frozen_at_utc": rec["frozen_at_utc"],
                     "verified": gi.sha256(gi.canonical_bytes(raw)) == rec["sha256"],
                     "controls": len(json.loads(raw)["controls"]),
                     "registered_in_manifest": rec["frozen_file"] in _manifest()["entries"]}
    design = verify_design_unchanged()
    raw_design = (OUT / "policy_design_freeze.json").read_bytes()
    out["policy_design"] = {"frozen_at_utc": design["frozen_at_utc"],
                            "sha256": gi.sha256(gi.canonical_bytes(raw_design)), "files_verified": True,
                            "chosen_candidate": design["chosen_candidate"],
                            "after_dev_freeze": design["frozen_at_utc"] > out["r4_dev"]["frozen_at_utc"],
                            "before_fresh_freeze": design["frozen_at_utc"] < out["r4_fresh"]["frozen_at_utc"]}
    out["historical_manifest"] = verify_manifest()
    return out


def _manifest() -> dict:
    return json.loads(gi.DEFAULT_MANIFEST.read_text(encoding="utf-8"))


def verify_manifest() -> dict:
    entries = _manifest()["entries"]
    ok = {}
    for frozen, e in entries.items():
        try:
            ok[frozen] = gi.verify_frozen_file(frozen, e["freeze_record"]).method
        except gi.FreezeIntegrityError as exc:  # never raised in a healthy tree; recorded, not hidden
            ok[frozen] = f"FAILED: {exc}"
    return {"entries": len(entries), "verified": sum(1 for v in ok.values() if not v.startswith("FAILED")),
            "failures": {k: v for k, v in ok.items() if v.startswith("FAILED")}}


# ---- Phase 2: historical false-SUPPORTED taxonomy -----------------------------------------------------
TAXONOMY = {
    "A": "ordinary English mistaken for a technology (concept identity error)",
    "B": "genuine technology mention without demonstrated project use",
    "C": "negated technology use",
    "D": "historical or deprecated technology use",
    "E": "future or hypothetical technology use",
    "F": "third-party project, reference or dependency documentation",
    "G": "quotation or comparison without project attribution",
    "H": "ambiguous, not confidently classifiable",
    "J": "job-side false concept (job text, not README; out of README-guard scope)",
}
# G22-R labels only "mentioned / used", so its mention-without-use rows are classified here by reading the text
# (public synthetic controls); every other row follows its frozen author label class and family.
_G22R_OVERRIDES = {"m11g22r-d21": ("E", "'A Rust port would be a fun future project'"),
                   "m11g22r-d22": ("G", "'component model is inspired by React'"),
                   "m11g22r-d38": ("E", "'Bindings for Rust can be generated'"),
                   "m11g22r-e19": ("E", "'Clients can be generated for Swift or Kotlin'"),
                   "m11g22r-e20": ("B", "'works with React, Vue or Svelte': real React mention, no use claim"),
                   "m11g22r-e34": ("G", "'Notes comparing React and Vue'")}


def _category(label: str, family: str) -> str:
    if label == "ordinary":
        return "A"
    if label in ("negated",):
        return "C"
    if label == "historical":
        return "D"
    if label == "future":
        return "E"
    if label == "reference":
        return "F" if family == "other_project_docs" else "G"
    return "H"


def _g22r_policy(p):
    return rpol.Policy(p.name, readme_rule=p.rule)


def taxonomy() -> dict:
    rows = []
    sets = [(k, SEEN_SETS[k]()) for k in ("g22r2_dev", "g22r2_eval", "g22r3_val1", "g22r3_val2")]
    for set_name, ctrl in sets:
        res = {p.name: {r["id"]: r for r in (h.run_control(c, p) for c in ctrl)} for p in POLICIES}
        for c in ctrl:
            base = res[p2.A.name][c["id"]]
            if base["outcome"] != "false_supported":
                continue
            rows.append({"set": set_name, "id": c["id"], "probe": c["probe"], "label": base["probe_class"],
                         "family": c["family"], "category": _category(base["probe_class"], c["family"]),
                         "fixed_by": sorted(p.name for p in POLICIES[1:]
                                            if res[p.name][c["id"]]["outcome"] != "false_supported")})
    for split in ("dev", "eval"):
        ctrl = h22r.load_controls(split)
        res = {p.name: {r["id"]: r for r in (h22r.run_control(c, _g22r_policy(p) if p is not p2.A else rpol.BASE)
                                            for c in ctrl)} for p in POLICIES}
        for c in ctrl:
            for f in res[p2.A.name][c["id"]]["false_supported"]:
                if f["cause"] == "job_false_concept":
                    cat, basis = "J", "job text concept"
                elif c["id"] in _G22R_OVERRIDES:
                    cat, basis = _G22R_OVERRIDES[c["id"]]
                else:
                    cat, basis = "A", "G22-R 'not mentioned': ordinary English"
                still = {p.name for p in POLICIES[1:]
                         if any(g["members"] == f["members"] for g in res[p.name][c["id"]]["false_supported"])}
                rows.append({"set": f"g22r_{split}", "id": c["id"], "probe": ",".join(f["members"]),
                             "label": f["cause"], "family": c["family"], "category": cat, "basis": basis,
                             "fixed_by": sorted(p.name for p in POLICIES[1:] if p.name not in still)})
    by_cat = Counter(r["category"] for r in rows)
    fixed = {p.name: Counter(r["category"] for r in rows if p.name in r["fixed_by"]) for p in POLICIES[1:]}
    return {"categories": TAXONOMY, "rows": rows, "count_by_category": dict(sorted(by_cat.items())),
            "fixed_by_policy_and_category": {k: dict(sorted(v.items())) for k, v in fixed.items()},
            "concept_identity_errors": by_cat["A"],
            "project_attribution_errors": sum(by_cat[k] for k in "BCDEFG"),
            "unresolved_by_chosen": sorted([r["set"], r["id"], r["probe"], r["category"]] for r in rows
                                           if CHOSEN.name not in r["fixed_by"] and r["category"] != "J")}


# ---- per-set evaluation ---------------------------------------------------------------------------------
def _row_diff(a: dict, r: dict, amb: set[str]) -> dict:
    return {"id": r["id"], "family": r["family"], "probe": r["probe"],
            "outcome": [a["outcome"], r["outcome"]], "status": [a["probe_status"], r["probe_status"]],
            "score": [a["score"], r["score"]], "numerator": [a["numerator"], r["numerator"]],
            "denominator": [a["denominator"], r["denominator"]],
            "readme_items_removed": {k: v for k, v in a["readme_concepts"].items() if k not in r["readme_concepts"]},
            "readme_items_added": {k: v for k, v in r["readme_concepts"].items() if k not in a["readme_concepts"]},
            "non_ambiguous_item_changed": any(k not in amb for k in set(a["readme_concepts"]) ^ set(r["readme_concepts"]))}


def _reject_reason(policy, text: str, start: int, end: int) -> str | None:
    if policy.name in p4.LEVEL:
        return p4.explain(text, start, end, p4.LEVEL[policy.name])
    if policy.rule is not None and policy.rule(text, start, end):
        return "rule"
    return None


def rejected_occurrences(ctrl: list[dict], policy) -> list:
    """Every ambiguous occurrence the policy rejects beyond readme:v4's own 8D.3 filter, with its reason."""
    out = []
    for c in ctrl:
        for repo in c["repos"]:
            t = repo["readme"] or ""
            ctx = rc.build_context(t)
            for o in p4.occurrences(t):
                if rc.is_non_implementation_mention(t, o.start, o.end, ctx):
                    continue
                why = _reject_reason(policy, t, o.start, o.end)
                if why:
                    s, a, b = p4._occurrence(t, o.start, o.end)
                    out.append([c["id"], t[o.start:o.end], why, re.sub(r"\s+", " ", s).strip()[:160]])
    return out


def run_set(ctrl: list[dict]) -> dict:
    amb = _ambiguous_concepts()
    results = {p.name: [h.run_control(c, p) for c in ctrl] for p in POLICIES}
    base = {r["id"]: r for r in results[p2.A.name]}
    out = {}
    for p in POLICIES:
        agg = h.aggregate(results[p.name], ctrl)
        entry = {"aggregate": {k: agg[k] for k in AGG_KEYS}}
        if p is not p2.A:
            changed = [_row_diff(base[r["id"]], r, amb) for r in results[p.name]
                       if base[r["id"]]["readme_concepts"] != r["readme_concepts"] or base[r["id"]]["outcome"] != r["outcome"]]
            entry.update({
                "changed_controls": changed,
                "status_changes": dict(sorted(Counter(f"{row['status'][0]}->{row['status'][1]}" for row in changed
                                                      if row["status"][0] != row["status"][1]).items())),
                "numerator_change": agg["numerator"] - h.aggregate(results[p2.A.name], ctrl)["numerator"],
                "denominator_change": agg["denominator"] - h.aggregate(results[p2.A.name], ctrl)["denominator"],
                "became_undefined": sorted(r["id"] for r in results[p.name]
                                           if r["score"] is None and base[r["id"]]["score"] is not None),
                "new_false_supported_vs_readme_v4": sorted(r["id"] for r in results[p.name]
                                                           if r["outcome"] == "false_supported"
                                                           and base[r["id"]]["outcome"] != "false_supported"),
                "residual_false_supported": sorted([r["id"], r["probe"], r["probe_class"]] for r in results[p.name]
                                                   if r["outcome"] == "false_supported"),
                "missed_true_supported": sorted([r["id"], r["probe"]] for r in results[p.name] if r["outcome"] == "missed"),
                "genuine_use_items_lost": sorted([row["id"], cid, row["outcome"][1]] for row in changed
                                                 for cid, cls in row["readme_items_removed"].items() if cls == "use"),
                "non_ambiguous_items_changed": sum(1 for row in changed if row["non_ambiguous_item_changed"]),
            })
            if p.name in p4.LEVEL:
                entry["rejected_occurrences_with_reasons"] = rejected_occurrences(ctrl, p)
        out[p.name] = entry
    return out


def near_neighbour_pairs() -> list:
    ctrl = [c for c in SEEN_SETS["r4_dev"]() if c["pair"]]
    rows = []
    for c in ctrl:
        row = {"id": c["id"], "pair": c["pair"], "probe": c["probe"], "label": c["concepts"].get(c["probe"]),
               "used": c["probe"] in c["used"], "text": c["repos"][0]["readme"].split("\n\n", 1)[1].strip(),
               "outcome": {}}
        for p in POLICIES:
            row["outcome"][p.name] = h.run_control(c, p)["outcome"]
        rows.append(row)
    return rows


# ---- Phase 7: fresh set (occurrence-level labels) ----------------------------------------------------------
def occurrence_audit(ctrl: list[dict]) -> dict:
    """Align the author's per-occurrence labels with the ambiguous-alias occurrences (by repo, word, order)."""
    aligned, unaligned_groups = [], []
    for c in ctrl:
        auth = defaultdict(list)
        for o in c.get("occurrences", []):
            if o["word"].lower() in p4.AMBIGUOUS:
                auth[(o["repo"], o["word"].lower())].append(o)
        for repo in c["repos"]:
            t = repo["readme"] or ""
            mine = defaultdict(list)
            for o in p4.occurrences(t):
                mine[o.alias].append(o)
            for word in sorted(set(mine) | {w for (rn, w) in auth if rn == repo["name"]}):
                a, m = auth.get((repo["name"], word), []), mine.get(word, [])
                if len(a) != len(m):
                    unaligned_groups.append([c["id"], repo["name"], word, len(a), len(m)])
                    continue
                ctx = rc.build_context(t)
                for lab, occ in zip(a, m):
                    aligned.append((c["id"], t, occ, lab, rc.is_non_implementation_mention(t, occ.start, occ.end, ctx)))
    out = {"aligned_occurrences": len(aligned), "unaligned_groups": unaligned_groups,
           "by_class": dict(sorted(Counter(x[3]["class"] for x in aligned).items())), "policies": {}}
    for p in POLICIES[1:]:
        use_rej, inval_rej, inval_kept = [], Counter(), Counter()
        for cid, t, occ, lab, prod in aligned:
            if prod:
                continue
            why = _reject_reason(p, t, occ.start, occ.end)
            if lab["class"] == "use":
                if why:
                    use_rej.append([cid, t[occ.start:occ.end], why, lab["sentence"][:160]])
            elif lab["class"] in NON_USE:
                (inval_rej if why else inval_kept)[lab["class"]] += 1
        use_total = sum(1 for x in aligned if x[3]["class"] == "use" and not x[4])
        out["policies"][p.name] = {
            "use_occurrences": use_total, "use_occurrences_rejected": len(use_rej),
            "use_occurrences_rejected_detail": use_rej,
            "invalid_occurrences_rejected_by_class": dict(sorted(inval_rej.items())),
            "invalid_occurrences_kept_by_class": dict(sorted(inval_kept.items())),
        }
    out["production_excluded"] = dict(sorted(Counter(x[3]["class"] for x in aligned if x[4]).items()))
    return out


def acceptance(fresh: dict, invariants: dict, contract: dict) -> dict:
    a, p = fresh[p2.A.name]["aggregate"], fresh[CHOSEN.name]["aggregate"]
    e = fresh[CHOSEN.name]
    use_a, use_p = a["use_claims_retained"][0], p["use_claims_retained"][0]
    checks = {
        "G1_genuine_readme_use_retention": [use_p, use_a, use_p >= 0.95 * use_a],
        "G2_true_supported_retention": [p["true_supported"], a["true_supported"],
                                        p["true_supported"] >= 0.95 * a["true_supported"]],
        "G3_false_supported_reduction": [p["false_supported"], a["false_supported"],
                                         p["false_supported"] <= 0.5 * a["false_supported"]],
        "G4_no_new_false_supported": [len(e["new_false_supported_vs_readme_v4"]), 0,
                                      not e["new_false_supported_vs_readme_v4"]],
        "G5_corroborated": [p["corroborated_supported"][0], p["corroborated_supported"][1],
                            p["corroborated_supported"][0] == p["corroborated_supported"][1]],
        "G6_non_ambiguous": [e["non_ambiguous_items_changed"], 0, e["non_ambiguous_items_changed"] == 0],
        "G7_g19_capability": [len(contract[CHOSEN.name]["valid_context_not_extracted"]), 0,
                              not contract[CHOSEN.name]["valid_context_not_extracted"]
                              and invariants[CHOSEN.name]["capability_identical_for_all_concepts"]],
        "G8_no_job_side_regression": [invariants[CHOSEN.name]["job_parsing_identical_on_all_corpora"], True,
                                      invariants[CHOSEN.name]["job_parsing_identical_on_all_corpora"]],
    }
    return {"policy": CHOSEN.name, "checks": checks, "passed": all(v[2] for v in checks.values())}


# ---- Phase 8 / 9 ------------------------------------------------------------------------------------------
NAMED = [("Pure Python", "Pure Python TOML parser.", "language.python", True),
         ("Pure Python, no third-party dependencies", "Pure Python, no third-party dependencies.", "language.python", True),
         ("One-line Swift API", "One-line Swift API for the keychain.", "language.swift", True),
         ("image diffing in Rust", "Fast image diffing in Rust.", "language.rust", True),
         ("python plotting helper", "Ships a small python plotting helper.", "language.python", True),
         ("trained with torch", "Image classifier trained with torch.", "ml.framework.pytorch", True),
         ("store in Rust", "A tiny key-value store in Rust.", "language.rust", True),
         ("Like the Rust compiler (reference)", "Like the Rust compiler, it explains every error.", "language.rust", False),
         ("Streaming CSV reader, in Swift", "Streaming CSV reader, in Swift.", "language.swift", True)]


def named_phrases() -> list:
    rows = []
    for label, sentence, concept, use in NAMED:
        text = f"# x\n\n{sentence}\n"
        row = {"phrase": label, "text": sentence, "concept": concept, "genuine_use": use, "extracted": {}}
        for p in POLICIES:
            with p2.applied(p):
                row["extracted"][p.name] = concept in {e.concept_id for e in evidence_from_readme("o", "r", text, "README.md")}
        rows.append(row)
    return rows


def readme_selection_8c() -> dict:
    """Which occurrence each policy selects for torvalds/libgit2 and sindresorhus/Gifski (public fixtures)."""
    out = {}
    for cand, repo in (("torvalds", "libgit2"), ("sindresorhus", "Gifski")):
        text = load_candidate_fixture(cand)["selected"][repo]["readme"][0]
        for p in POLICIES:
            with p2.applied(p):
                ev = evidence_from_readme(cand, repo, text, "README.md")
            out.setdefault(f"{cand}/{repo}", {})[p.name] = {
                e.concept_id: re.sub(r"^README mentions '[^']+': \.\.\.|\.\.\.$", "", e.raw_observation)[:120]
                for e in ev if e.concept_id in _ambiguous_concepts()}
    return out


# Post-inspection judgments made AFTER seeing R4's 8c behaviour. NOT gold, kept apart from frozen labels.
POST_INSPECTION_8C = {
    "torvalds/libgit2 language.python": "use: 'Python is used by our test framework, and should be installed' "
                                        "(Quick Start prerequisites). G22-R2's REVIEW_8C judged libgit2 python a "
                                        "'reference' from its FIRST occurrence ('[pygit2](...) (Python)'); the README "
                                        "also contains this genuine build/test requirement.",
    "torvalds/libgit2 java|ruby|rust|swift": "reference: other projects' language-bindings list (agrees with "
                                             "REVIEW_8C)",
    "sindresorhus/Gifski language.rust": "use: build requirement (agrees with REVIEW_8C); kept by P0-P4",
}


def capability_contract() -> dict:
    reg = default_registry()
    out = {}
    for p in POLICIES:
        lost = []
        with p2.applied(p):
            for c in reg.all_concepts():
                for alias in c.readme_safe_aliases():
                    text = f"# demo\n\nThis project is built with {alias}.\n"
                    if c.concept_id not in {e.concept_id for e in evidence_from_readme("o", "r", text, "README.md")}:
                        lost.append([c.concept_id, alias])
        out[p.name] = {"aliases_checked": sum(len(c.readme_safe_aliases()) for c in reg.all_concepts()),
                       "concepts": len(reg.all_concepts()), "valid_context_not_extracted": lost,
                       "capability": {c.concept_id: [concept_capability(c.concept_id).capability.value,
                                      sorted(x.value for x in concept_capability(c.concept_id).pathways)]
                                     for c in reg.all_concepts()}}
    return out


def existing_tests_under_policies() -> dict:
    files = [f for f in r2.TEST_FILES if (REPO_ROOT / f).exists()]
    out = {"files": files}
    for p in (p2.A, *p4.CANDIDATES):
        env = {**os.environ, "M11G22R4_POLICY": p.name,
               "PYTHONPATH": os.pathsep.join([str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"),
                                              str(REPO_ROOT / "scripts" / "evaluation_lib")])}
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p",
                               "m11g22r4_pytest_policy", "--tb=no", "-rf", *files], cwd=REPO_ROOT, env=env,
                              capture_output=True, text=True)
        tail = [line for line in proc.stdout.splitlines() if re.search(r"\d+ (passed|failed)", line)]
        out[p.name] = {"summary": re.sub(r"\s+in\s+[\d.]+s.*$", "", tail[-1] if tail else proc.stdout[-300:]).strip(),
                       "failed": sorted(line.split(" - ")[0].replace("FAILED ", "") for line in proc.stdout.splitlines()
                                        if line.startswith("FAILED"))}
    return out


def encode(obj) -> bytes:
    return (json.dumps(obj, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def build_report(fresh: bool, run_tests: bool) -> dict:
    report = {
        "versions": {"parser": JOB_DESCRIPTION_PARSER_VERSION, "scoring": SCORING_VERSION, "matcher": MATCHER_VERSION,
                     "readme_extractor": EXTRACTOR_VERSION, "registry": CONCEPT_REGISTRY_VERSION},
        "note": "research only: real parser v15 / evidence pipeline readme:v4 / matcher v1 / scoring v2; README "
                "policies are offline adapters; no production or registry change; no LLM call anywhere in evaluation",
        "freezes": freezes(),
        "policies": {p.name: p.description for p in POLICIES},
        "taxonomy": taxonomy(),
        "seen_sets": {k: run_set(v()) for k, v in SEEN_SETS.items()},
        "near_neighbour_pairs_dev": near_neighbour_pairs(),
        "named_phrases": named_phrases(),
        "post_inspection_8c_not_gold": POST_INSPECTION_8C,
        "readme_selection_8c": readme_selection_8c(),
        "capability_contract": capability_contract(),
    }
    with r2_policies(POLICIES):
        report["g22r_frozen_controls"] = r2.g22r_controls()
        report["historical_8c_simulated"] = r2.history_8c()
        report["difficult_cases"] = r2.difficult_cases()
        report["invariants"] = r2.capability_and_job_side_unaffected()
    if run_tests:
        report["existing_tests_under_policies"] = existing_tests_under_policies()
    if fresh:
        ctrl = _load(OUT / "fresh_validation_controls.json")
        report["fresh"] = {"role": "held-out: run after the policy design freeze and the label freeze",
                           "provenance": json.loads((OUT / "fresh_author_provenance.json").read_text(encoding="utf-8")),
                           "results": run_set(ctrl), "occurrence_audit": occurrence_audit(ctrl)}
        report["acceptance"] = acceptance(report["fresh"]["results"], report["invariants"],
                                          report["capability_contract"])
    return report


def build_private() -> dict:
    with r2_policies((p2.A, *p4.CANDIDATES)):
        return r2.build_private()


def _main() -> None:
    if (JOB_DESCRIPTION_PARSER_VERSION, SCORING_VERSION, EXTRACTOR_VERSION, MATCHER_VERSION, CONCEPT_REGISTRY_VERSION) != \
            ("job_description_parser:v15", "github_evidence_alignment:v2", "readme:v4", "requirement_matcher:v1", 4):
        raise SystemExit("G22-R4 describes parser v15 / scoring v2 / readme:v4 / matcher v1 / registry 4")
    verify_design_unchanged()
    report = build_report(fresh="--fresh" in sys.argv, run_tests="--skip-test-runs" not in sys.argv)
    target = OUT / ("high_recall_guard_report.json" if "--fresh" in sys.argv else "_seen_only_report.json")
    target.write_bytes(encode(report))
    for name, res in [*report["seen_sets"].items(), *([("FRESH", report["fresh"]["results"])] if "fresh" in report else [])]:
        for pol, v in res.items():
            a = v["aggregate"]
            print(name.ljust(11), pol.ljust(24), "FS", a["false_supported"], "use", a["use_claims_retained"],
                  "trueSUP", a["true_supported"], "missed", a["missed_true_supported"], "corr", a["corroborated_supported"])
    if "acceptance" in report:
        print("acceptance", report["acceptance"]["passed"], {k: v for k, v in report["acceptance"]["checks"].items()})
    if "--private-corpora" in sys.argv:
        agg = build_private()
        (OUT / "private_high_recall_guard_aggregates.json").write_bytes((json.dumps(agg, indent=1) + "\n").encode("utf-8"))
        print("[private]", {k: {kk: vv["postings_changed"] for kk, vv in v.items()} for k, v in agg.items() if k != "note"})


def main() -> None:
    # Milestone 11-G22-S1: production README extraction is readme:v5 (setext heading boundaries only). This research
    # measured readme:v4; it is reproduced exactly by running pinned to readme:v4 (scripts/evaluation_lib/readme_v4_pin.py).
    with readme_v4_pin.pinned():
        _main()


if __name__ == "__main__":
    main()
