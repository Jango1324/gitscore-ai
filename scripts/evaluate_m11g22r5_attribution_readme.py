"""Milestone 11-G22-R5 -- attribution-aware README evidence research (readme:v5 NOT implemented).

    python scripts/evaluate_m11g22r5_attribution_readme.py [--fresh] [--private-corpora] [--skip-test-runs]

Real parser v15, real evidence pipeline (readme:v4 + language / Docker / manifest extractors), matcher v1 and scoring
v2. README policies are offline adapters: production readme:v4, the R5 attribution-only candidates A -> B -> C -> D and
D_S (`scripts/evaluation_lib/m11g22r5_policies.py`), D restricted to the ambiguous aliases, the overlap finding O, and
G22-R4's P4 (unchanged) for comparison. No production code, registry data or LLM is used; nothing calls a model.

The public report is a MEASUREMENT record: it deliberately contains no canonical-manifest registration state, so
registering freezes later cannot change it. Before anything runs, every file hash in
`evaluation/m11g22r5/policy_design_freeze.json` is re-verified.

Writes `evaluation/m11g22r5/attribution_readme_report.json` (public: synthetic controls, public 8c fixtures, counts)
and, with --private-corpora, `private_attribution_readme_aggregates.json` (integer counts only).
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
import m11g22r4_policies as p4  # noqa: E402
import m11g22r5_policies as p5  # noqa: E402
import m11g22r_policies as rpol  # noqa: E402
from evaluation_lib.loaders import load_candidate_fixture  # noqa: E402
from gitscore.assessment import SCORING_VERSION  # noqa: E402
from gitscore.concepts.matching import alias_pattern  # noqa: E402
from gitscore.concepts.registry import CONCEPT_REGISTRY_VERSION, default_registry  # noqa: E402
from gitscore.evidence.capability import concept_capability  # noqa: E402
from gitscore.evidence.extraction import readme as readme_mod  # noqa: E402
from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION, evidence_from_readme  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION  # noqa: E402
from gitscore.matching import MATCHER_VERSION  # noqa: E402

OUT = REPO_ROOT / "evaluation" / "m11g22r5"
SELECTED = p5.D_S
POLICIES = (p2.A, *p5.CANDIDATES, *p5.COMPARISON, p4.P4)
ATTRIBUTION = {"reference", "historical", "future"}
NON_USE = ("ordinary", "reference", "historical", "future", "negated")
REG = default_registry()
AGG_KEYS = ("false_supported", "false_supported_by_probe_class", "false_readme_evidence_ordinary",
            "nonuse_readme_evidence", "use_claims_retained", "genuine_use_lost", "corroborated_supported",
            "true_supported", "missed_true_supported", "true_not_supported", "uncertain", "numerator", "denominator",
            "readme_items_by_label_class", "unlabelled_readme_concepts")


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["controls"]


SEEN_SETS = {
    "r5_dev": lambda: _load(OUT / "dev_controls.json"),
    "g22r2_dev": lambda: h.load_controls("dev"),
    "g22r2_eval": lambda: h.load_controls("eval"),
    "g22r3_val1": lambda: _load(REPO_ROOT / "evaluation/m11g22r3/validation_controls_val1.json"),
    "g22r3_val2": lambda: _load(REPO_ROOT / "evaluation/m11g22r3/validation_controls_val2.json"),
    "g22r4_dev": lambda: _load(REPO_ROOT / "evaluation/m11g22r4/dev_controls.json"),
    "g22r4_fresh_seen": lambda: _load(REPO_ROOT / "evaluation/m11g22r4/fresh_validation_controls.json"),
}


@contextmanager
def r2_policies(policies):
    saved = r2.ALL
    r2.ALL = tuple(policies)
    try:
        yield
    finally:
        r2.ALL = saved


@contextmanager
def g22r_setext_hook():
    """The G22-R harness applies README rules through `rpol.applied`; give D_S its heading-index swap there too."""
    saved = rpol.applied

    @contextmanager
    def applied(policy):
        with saved(policy):
            if policy.name in p5.SETEXT_POLICIES:
                old = readme_mod.build_context
                readme_mod.build_context = p5.SetextContext
                try:
                    yield policy
                finally:
                    readme_mod.build_context = old
            else:
                yield policy
    rpol.applied = applied
    try:
        yield
    finally:
        rpol.applied = saved


# ---- freezes ------------------------------------------------------------------------------------------------
def verify_design_unchanged() -> dict:
    design = json.loads((OUT / "policy_design_freeze.json").read_text(encoding="utf-8"))
    now = {f: gi.sha256(gi.canonical_bytes((REPO_ROOT / f).read_bytes())) for f in design["files"]}
    if now != design["files"]:
        raise SystemExit(f"R5 policy files changed after the design freeze: "
                         f"{sorted(f for f in now if now[f] != design['files'][f])}")
    return design


def freezes(fresh: bool) -> dict:
    """Freeze records and their verification -- NOT the canonical-manifest registration state (kept out on purpose)."""
    out = {}
    pairs = [("r5_dev", "dev_controls.json", "dev_hash_freeze.json")]
    if fresh:
        pairs.append(("r5_fresh", "fresh_validation_controls.json", "fresh_hash_freeze.json"))
    for name, data, rec in pairs:
        record = json.loads((OUT / rec).read_text(encoding="utf-8"))
        raw = (OUT / data).read_bytes()
        out[name] = {"sha256": record["sha256"], "frozen_at_utc": record["frozen_at_utc"],
                     "verified": gi.sha256(gi.canonical_bytes(raw)) == record["sha256"],
                     "controls": len(json.loads(raw)["controls"])}
    design = verify_design_unchanged()
    out["policy_design"] = {"frozen_at_utc": design["frozen_at_utc"],
                            "sha256": gi.sha256(gi.canonical_bytes((OUT / "policy_design_freeze.json").read_bytes())),
                            "selected_candidate": design["selected_candidate"], "files_verified": True,
                            "after_dev_freeze": design["frozen_at_utc"] > out["r5_dev"]["frozen_at_utc"]}
    if fresh:
        out["policy_design"]["before_fresh_freeze"] = design["frozen_at_utc"] < out["r5_fresh"]["frozen_at_utc"]
    return out


# ---- per-set evaluation ----------------------------------------------------------------------------------------
def run_control(c: dict, policy) -> dict:
    """G22-R2 harness run; a probe the job parser cannot resolve is 'unscoreable' (README items still counted)."""
    try:
        return h.run_control(c, policy)
    except ValueError:
        prof = h.profile_for(c["repos"], policy)
        return {"id": c["id"], "family": c["family"], "pair": c.get("pair"), "probe": c["probe"],
                "evidence": sorted([e.repository.name, e.evidence_type.value, e.concept_id, e.confidence.name]
                                   for e in prof.evidence),
                "readme_concepts": {e.concept_id: c["concepts"].get(e.concept_id, "unlabelled") for e in prof.evidence
                                    if e.evidence_type.value == "readme"},
                "probe_class": c["concepts"].get(c["probe"]), "probe_status": None, "probe_counts": False,
                "probe_evidence_types": [], "probe_truth": None, "score": None, "numerator": 0, "denominator": 0,
                "outcome": "unscoreable"}


def _snippets(c: dict, policy) -> dict:
    out = {}
    with p2.applied(policy):
        for r in c["repos"]:
            for e in evidence_from_readme("o", r["name"], r["readme"], "README.md"):
                out[(r["name"], e.concept_id)] = e.raw_observation
    return out


def _att_fs(results) -> int:
    return sum(1 for r in results if r["outcome"] == "false_supported" and r["probe_class"] in ATTRIBUTION)


def run_set(ctrl: list[dict]) -> dict:
    results = {p.name: [run_control(c, p) for c in ctrl] for p in POLICIES}
    base = {r["id"]: r for r in results[p2.A.name]}
    base_snip = {c["id"]: _snippets(c, p2.A) for c in ctrl}
    out = {}
    for p in POLICIES:
        res = results[p.name]
        agg = h.aggregate(res, ctrl)
        entry = {"aggregate": {k: agg[k] for k in AGG_KEYS},
                 "attribution_false_supported": _att_fs(res),
                 "attribution_false_readme_evidence": sum(v for k, v in agg["readme_items_by_label_class"].items()
                                                          if k in ATTRIBUTION),
                 "unscoreable": sorted(r["id"] for r in res if r["outcome"] == "unscoreable")}
        if p is not p2.A:
            removed, added, moved, non_readme, rows = Counter(), Counter(), [], [], []
            for r in res:
                b = base[r["id"]]
                for cid, cls in b["readme_concepts"].items():
                    if cid not in r["readme_concepts"]:
                        removed[cls] += 1
                for cid, cls in r["readme_concepts"].items():
                    if cid not in b["readme_concepts"]:
                        added[cls] += 1
                if [e for e in b["evidence"] if e[1] != "readme"] != [e for e in r["evidence"] if e[1] != "readme"]:
                    non_readme.append(r["id"])
                if r["outcome"] != b["outcome"] or r["readme_concepts"] != b["readme_concepts"]:
                    rows.append({"id": r["id"], "probe": r["probe"], "label": r["probe_class"],
                                 "outcome": [b["outcome"], r["outcome"]], "status": [b["probe_status"], r["probe_status"]],
                                 "score": [b["score"], r["score"]],
                                 "readme_removed": {k: v for k, v in b["readme_concepts"].items()
                                                    if k not in r["readme_concepts"]},
                                 "readme_added": {k: v for k, v in r["readme_concepts"].items()
                                                  if k not in b["readme_concepts"]}})
            for c in ctrl:
                if p.name in p5.LAYER or p is p5.O:
                    snip = _snippets(c, p)
                    moved += [[c["id"], k[1]] for k in snip if k in base_snip[c["id"]] and snip[k] != base_snip[c["id"]][k]]
            entry.update({
                "changed_controls": rows,
                "readme_items_removed_by_label": dict(sorted(removed.items())),
                "readme_items_added_by_label": dict(sorted(added.items())),
                "provenance_moved_to_another_occurrence": moved,
                "non_readme_evidence_changed": non_readme,
                "status_changes": dict(sorted(Counter(f"{x['status'][0]}->{x['status'][1]}" for x in rows
                                                      if x["status"][0] != x["status"][1]).items())),
                "numerator_change": agg["numerator"] - h.aggregate(results[p2.A.name], ctrl)["numerator"],
                "denominator_change": agg["denominator"] - h.aggregate(results[p2.A.name], ctrl)["denominator"],
                "became_undefined": sorted(r["id"] for r in res if r["score"] is None and base[r["id"]]["score"] is not None
                                           and r["outcome"] != "unscoreable"),
                "new_false_supported_vs_readme_v4": sorted(r["id"] for r in res if r["outcome"] == "false_supported"
                                                           and base[r["id"]]["outcome"] != "false_supported"),
                "residual_false_supported": sorted([r["id"], r["probe"], r["probe_class"]] for r in res
                                                   if r["outcome"] == "false_supported"),
                "missed_true_supported": sorted([r["id"], r["probe"]] for r in res if r["outcome"] == "missed"),
            })
            if p.name in p5.LAYER or p is p5.O:
                entry["rejected_occurrences_with_reasons"] = rejected_occurrences(ctrl, p)
        out[p.name] = entry
    return out


def _occurrences(text: str) -> list[tuple[str, str, int, int]]:
    """Every registry alias occurrence, minus those strictly inside a longer one ("react" in "React Native")."""
    found = [(c.concept_id, a, m.start(), m.end()) for c in REG.all_concepts() for a in c.readme_safe_aliases()
             for m in alias_pattern(a).finditer(text)]
    keep = [o for o in found if not any(x[2] <= o[2] and o[3] <= x[3] and (x[2], x[3]) != (o[2], o[3]) for x in found)]
    return sorted(set(keep), key=lambda o: (o[2], o[3]))


def _rejected(policy, text: str, s: int, e: int) -> str | None:
    if policy is p2.A:
        return "production 8D.3" if p5.production_rejects(p2.A, text, s, e) else None
    if p5.production_rejects(policy, text, s, e):
        return "production 8D.3" + (" (setext-aware index)" if policy.name in p5.SETEXT_POLICIES else "")
    if policy is p4.P4:
        return p4.explain(text, s, e, 4)
    return p5.explain_policy(policy, text, s, e)


def rejected_occurrences(ctrl: list[dict], policy) -> list:
    out = []
    for c in ctrl:
        for repo in c["repos"]:
            t = repo["readme"] or ""
            for cid, alias, s, e in _occurrences(t):
                base, why = _rejected(p2.A, t, s, e), _rejected(policy, t, s, e)
                if why != base and (why or base):
                    sent = p4._occurrence(t, s, e)[0]
                    out.append([c["id"], cid, t[s:e], why or f"re-admitted (was: {base})",
                                re.sub(r"\s+", " ", sent).strip()[:160]])
    return out


def occurrence_audit(ctrl: list[dict]) -> dict:
    aligned, unaligned = [], []
    for c in ctrl:
        auth = defaultdict(list)
        for o in c.get("occurrences", []):
            auth[(o["repo"], o["concept"])].append(o)
        for repo in c["repos"]:
            t = repo["readme"] or ""
            mine = defaultdict(list)
            for occ in _occurrences(t):
                mine[occ[0]].append(occ)
            for cid in sorted(set(mine) | {k[1] for k in auth if k[0] == repo["name"]}):
                a, m = auth.get((repo["name"], cid), []), mine.get(cid, [])
                if len(a) != len(m):
                    unaligned.append([c["id"], repo["name"], cid, len(a), len(m)])
                    continue
                aligned += [(c["id"], t, occ, lab) for lab, occ in zip(a, m)]
    out = {"aligned_occurrences": len(aligned), "unaligned_groups": unaligned,
           "by_class": dict(sorted(Counter(x[3]["class"] for x in aligned).items())),
           "by_attribution_kind": dict(sorted(Counter(x[3].get("attribution_kind", "n/a") for x in aligned).items())),
           "policies": {}}
    for p in POLICIES:
        use_rej, inval_rej, inval_kept, kind_rej, kind_tot = [], Counter(), Counter(), Counter(), Counter()
        for cid, t, occ, lab in aligned:
            why = _rejected(p, t, occ[2], occ[3])
            kind = lab.get("attribution_kind", "n/a")
            if lab["class"] == "use":
                if why:
                    use_rej.append([cid, occ[0], t[occ[2]:occ[3]], why, lab.get("sentence", "")[:160]])
            elif lab["class"] in NON_USE:
                (inval_rej if why else inval_kept)[lab["class"]] += 1
                kind_tot[kind] += 1
                if why:
                    kind_rej[kind] += 1
        out["policies"][p.name] = {
            "use_occurrences": sum(1 for x in aligned if x[3]["class"] == "use"),
            "use_occurrences_rejected": len(use_rej), "use_occurrences_rejected_detail": use_rej,
            "invalid_occurrences_rejected_by_class": dict(sorted(inval_rej.items())),
            "invalid_occurrences_kept_by_class": dict(sorted(inval_kept.items())),
            "invalid_rejected_by_attribution_kind": {k: [kind_rej[k], kind_tot[k]] for k in sorted(kind_tot)},
        }
    return out


# ---- Phase 3 / 4 probes -------------------------------------------------------------------------------------------
MARKDOWN_PROBES = [
    ("setext 'Development' after ATX 'Related projects'", "# g\n\n## Related projects\n\n- ripgrep (Rust)\n\n"
     "Development\n-----------\n\nThis tool is written in Rust.\n", "language.rust", True),
    ("setext 'Related projects' section only", "# g\n\nA grep in Go.\n\nRelated projects\n================\n\n"
     "- ripgrep (Rust)\n", "language.rust", False),
    ("ATX 'Development' after 'Related projects'", "# g\n\n## Related projects\n\n- ripgrep (Rust)\n\n## Development\n\n"
     "This tool is written in Rust.\n", "language.rust", True),
    ("'###' subsection of '## Alternatives' (no level inheritance)", "# m\n\n## Alternatives\n\n### FastAPI\n\nMore "
     "mature.\n", "framework.fastapi", False),
    ("'### Why we chose X' under '## Alternatives'", "# m\n\n## Alternatives\n\n### Why we chose FastAPI\n\nThis "
     "service is built on FastAPI.\n", "framework.fastapi", True),
    ("heading-like line inside a fence is not a heading", "# x\n\n## Related\n\n```\n# not a heading\n```\n\nBuilt "
     "with Flask.\n", "framework.flask", False),
    ("fenced code copied from another project", "# r\n\nA Go tool.\n\nFrom the polars docs:\n\n```python\nimport "
     "pandas as pd\n```\n", "data.library.pandas", False),
    ("blockquote: project note", "# f\n\nCSV tools.\n\n> **Note:** this project requires Python 3.11.\n",
     "language.python", True),
    ("blockquote: attributed third-party text", "# n\n\nNotices.\n\nFrom the cachelib README:\n\n> cachelib stores "
     "entries in Redis.\n", "database.redis", False),
    ("inline link annotation", "# l\n\nBindings like [pyfoo](https://example.invalid/pyfoo) (Python) exist.\n",
     "language.python", False),
    ("reference-style link annotation", "# l\n\nBindings like [pyfoo][1] (Python) exist.\n\n[1]: "
     "https://example.invalid/pyfoo\n", "language.python", False),
    ("unchecked task under Roadmap", "# t\n\n## Roadmap\n\n- [ ] TypeScript definitions\n", "language.typescript",
     False),
    ("unchecked task in a setup checklist", "# t\n\n## Database\n\n- [ ] `schema.sql` has been run in the SQL editor\n",
     "language.sql", True),
    ("overlap: 'React Native' then 'uses React'", "# a\n\nA React Native app. The web dashboard uses React.\n",
     "framework.react", True),
]


def markdown_probes() -> list:
    rows = []
    for label, text, concept, use in MARKDOWN_PROBES:
        row = {"case": label, "concept": concept, "genuine_use": use, "extracted": {}}
        for p in (p2.A, p5.D, p5.D_S, p5.O):
            with p2.applied(p):
                row["extracted"][p.name] = concept in {e.concept_id for e in evidence_from_readme("o", "r", text, "README.md")}
        rows.append(row)
    return rows


def multi_occurrence_table() -> list:
    rows = []
    for c in SEEN_SETS["r5_dev"]():
        row = {"id": c["id"], "scenario": c["scenario"], "probe": c["probe"], "label": c["concepts"].get(c["probe"]),
               "used": c["probe"] in c["used"], "outcome": {}}
        for p in (p2.A, p5.D, p5.D_S, p5.O):
            row["outcome"][p.name] = run_control(c, p)["outcome"]
        rows.append(row)
    return rows


# ---- Phase 8 / capability ---------------------------------------------------------------------------------------
def readme_selection_8c() -> dict:
    out = {}
    for cand, repo in (("torvalds", "libgit2"), ("sindresorhus", "Gifski")):
        text = load_candidate_fixture(cand)["selected"][repo]["readme"][0]
        for p in (p2.A, p5.D, p5.D_S, p4.P4):
            with p2.applied(p):
                ev = evidence_from_readme(cand, repo, text, "README.md")
            out.setdefault(f"{cand}/{repo}", {})[p.name] = {
                e.concept_id: re.sub(r"^README mentions '[^']+': \.\.\.|\.\.\.$", "", e.raw_observation)[:120] for e in ev}
    return out


def capability_contract() -> dict:
    out = {}
    for p in POLICIES:
        lost = []
        with p2.applied(p):
            for c in REG.all_concepts():
                for alias in c.readme_safe_aliases():
                    text = f"# demo\n\nThis project is built with {alias}.\n"
                    if c.concept_id not in {e.concept_id for e in evidence_from_readme("o", "r", text, "README.md")}:
                        lost.append([c.concept_id, alias])
        out[p.name] = {"aliases_checked": sum(len(c.readme_safe_aliases()) for c in REG.all_concepts()),
                       "concepts": len(REG.all_concepts()), "valid_context_not_extracted": lost}
    out["capability"] = {c.concept_id: [concept_capability(c.concept_id).capability.value,
                                        sorted(x.value for x in concept_capability(c.concept_id).pathways)]
                         for c in REG.all_concepts()}
    return out


def existing_tests_under_policies() -> dict:
    files = [f for f in r2.TEST_FILES if (REPO_ROOT / f).exists()]
    out = {"files": files}
    for p in (p2.A, *p5.CANDIDATES):
        env = {**os.environ, "M11G22R5_POLICY": p.name,
               "PYTHONPATH": os.pathsep.join([str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"),
                                              str(REPO_ROOT / "scripts" / "evaluation_lib")])}
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p",
                               "m11g22r5_pytest_policy", "--tb=no", "-rf", *files], cwd=REPO_ROOT, env=env,
                              capture_output=True, text=True)
        tail = [line for line in proc.stdout.splitlines() if re.search(r"\d+ (passed|failed)", line)]
        out[p.name] = {"summary": re.sub(r"\s+in\s+[\d.]+s.*$", "", tail[-1] if tail else proc.stdout[-300:]).strip(),
                       "failed": sorted(line.split(" - ")[0].replace("FAILED ", "") for line in proc.stdout.splitlines()
                                        if line.startswith("FAILED"))}
    return out


def acceptance(fresh: dict, invariants: dict, contract: dict) -> dict:
    a, s = fresh[p2.A.name], fresh[SELECTED.name]
    aa, sa = a["aggregate"], s["aggregate"]
    use_a, use_s = aa["use_claims_retained"][0], sa["use_claims_retained"][0]
    added_ok = set(s["readme_items_added_by_label"]) <= {"use"}
    checks = {
        "G1_genuine_readme_use_retention": [use_s, use_a, use_s >= 0.95 * use_a],
        "G2_true_supported_retention": [sa["true_supported"], aa["true_supported"],
                                        sa["true_supported"] >= 0.95 * aa["true_supported"]],
        "G3_no_new_false_supported": [len(s["new_false_supported_vs_readme_v4"]), 0,
                                      not s["new_false_supported_vs_readme_v4"]],
        "G4_corroborated": [sa["corroborated_supported"][0], sa["corroborated_supported"][1],
                            sa["corroborated_supported"][0] == sa["corroborated_supported"][1]],
        "G5_no_non_attribution_change": [{"non_readme_changed": len(s["non_readme_evidence_changed"]),
                                          "added_labels": s["readme_items_added_by_label"]}, "0 / only 'use'",
                                         not s["non_readme_evidence_changed"] and added_ok],
        "G6_g19_capability": [len(contract[SELECTED.name]["valid_context_not_extracted"]), 0,
                              not contract[SELECTED.name]["valid_context_not_extracted"]
                              and invariants[SELECTED.name]["capability_identical_for_all_concepts"]],
        "G7_no_parser_regression": [invariants[SELECTED.name]["job_parsing_identical_on_all_corpora"], True,
                                    invariants[SELECTED.name]["job_parsing_identical_on_all_corpora"]],
        "G8_attribution_false_supported_reduction": [s["attribution_false_supported"], a["attribution_false_supported"],
                                                     s["attribution_false_supported"]
                                                     <= 0.5 * a["attribution_false_supported"]],
    }
    return {"policy": SELECTED.name, "checks": checks, "passed": all(v[2] for v in checks.values()),
            "documented_exceptions": {"readme_items_removed_by_label": s["readme_items_removed_by_label"]},
            "overall_false_supported": [sa["false_supported"], aa["false_supported"]]}


def encode(obj) -> bytes:
    return (json.dumps(obj, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def build_report(fresh: bool, run_tests: bool) -> dict:
    with p5.mechanism(), g22r_setext_hook():
        report = {
            "versions": {"parser": JOB_DESCRIPTION_PARSER_VERSION, "scoring": SCORING_VERSION,
                         "matcher": MATCHER_VERSION, "readme_extractor": EXTRACTOR_VERSION,
                         "registry": CONCEPT_REGISTRY_VERSION},
            "note": "research only: real parser v15 / evidence pipeline readme:v4 / matcher v1 / scoring v2; README "
                    "policies are offline adapters; no production or registry change; no LLM call anywhere; this "
                    "report records no canonical-manifest state",
            "freezes": freezes(fresh),
            "policies": {p.name: p.description for p in POLICIES},
            "seen_sets": {k: run_set(v()) for k, v in SEEN_SETS.items()},
            "multi_occurrence_r5_dev": multi_occurrence_table(),
            "markdown_probes": markdown_probes(),
            "readme_selection_8c": readme_selection_8c(),
            "capability_contract": capability_contract(),
        }
        with r2_policies(POLICIES):
            report["g22r_frozen_controls"] = r2.g22r_controls()
            report["historical_8c_simulated"] = r2.history_8c()
            report["difficult_cases"] = r2.difficult_cases()
            report["invariants"] = r2.capability_and_job_side_unaffected()
        report["occurrence_audit_g22r4_fresh_seen"] = occurrence_audit(SEEN_SETS["g22r4_fresh_seen"]())
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
    with p5.mechanism(), r2_policies((p2.A, *p5.CANDIDATES)):
        return r2.build_private()


def main() -> None:
    if (JOB_DESCRIPTION_PARSER_VERSION, SCORING_VERSION, EXTRACTOR_VERSION, MATCHER_VERSION, CONCEPT_REGISTRY_VERSION) != \
            ("job_description_parser:v15", "github_evidence_alignment:v2", "readme:v4", "requirement_matcher:v1", 4):
        raise SystemExit("G22-R5 describes parser v15 / scoring v2 / readme:v4 / matcher v1 / registry 4")
    verify_design_unchanged()
    fresh = "--fresh" in sys.argv
    report = build_report(fresh=fresh, run_tests="--skip-test-runs" not in sys.argv)
    target = OUT / ("attribution_readme_report.json" if fresh else "_seen_only_report.json")
    target.write_bytes(encode(report))
    sets = [*report["seen_sets"].items(), *([("FRESH", report["fresh"]["results"])] if fresh else [])]
    for name, res in sets:
        for pol, v in res.items():
            a = v["aggregate"]
            print(name.ljust(17), pol.ljust(24), "FS", a["false_supported"], "attFS", v["attribution_false_supported"],
                  "use", a["use_claims_retained"], "trueSUP", a["true_supported"], "corr", a["corroborated_supported"])
    if "acceptance" in report:
        print("acceptance", report["acceptance"]["passed"], report["acceptance"]["checks"])
    if "--private-corpora" in sys.argv:
        agg = build_private()
        (OUT / "private_attribution_readme_aggregates.json").write_bytes((json.dumps(agg, indent=1) + "\n").encode("utf-8"))
        print("[private]", {k: {kk: vv["postings_changed"] for kk, vv in v.items()} for k, v in agg.items() if k != "note"})


if __name__ == "__main__":
    main()
