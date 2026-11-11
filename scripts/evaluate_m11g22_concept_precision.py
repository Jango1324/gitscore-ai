"""Milestone 11-G22 -- technical concept recognition precision (RESEARCH ONLY).

    python scripts/evaluate_m11g22_concept_precision.py [--private-corpora]

Runs the REAL production parser v14, matcher and scoring v2 -- optionally under the
offline `m11g22_policies` research adapters -- and writes

  evaluation/m11g22/concept_precision_report.json        (public; synthetic + tracked corpora)
  evaluation/m11g22/private_concept_aggregates.json      (--private-corpora; INTEGER COUNTS ONLY)

No production file is modified; no LLM is called. Refuses to run unless the live parser
is job_description_parser:v14 and scoring is github_evidence_alignment:v2 (the versions
this research describes).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import gold_integrity as gi  # noqa: E402
import m11g20_admission as adm  # noqa: E402
import m11g20_historical as hist  # noqa: E402
import m11g22_concepts as h  # noqa: E402
import m11g22_policies as pol  # noqa: E402
import m11g22_posthoc as ph  # noqa: E402
from evaluation_lib import end_to_end_eval  # noqa: E402
from evaluation_lib.loaders import list_candidate_names, load_candidate_fixture, load_job  # noqa: E402
from gitscore.assessment import SCORING_VERSION, assess_job  # noqa: E402
from gitscore.concepts.registry import is_unresolved_concept_id  # noqa: E402
from gitscore.jobs.parsing.concepts import find_concept_mentions  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION  # noqa: E402
from gitscore.jobs.parsing.qualification_intent import decide_qualification_intent  # noqa: E402
from gitscore.jobs.parsing.segmentation import segment_description  # noqa: E402
from gitscore.matching import MATCHER_VERSION, match_job  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402

OUT = REPO_ROOT / "evaluation" / "m11g22"
CANDIDATES = [p for p in pol.POLICIES if p is not pol.BASE] + list(ph.POSTHOC)

# ---- Phase 2: reproduced cases (live facts are computed; only `expected` / `earliest_incorrect_stage`
# are authored) -------------------------------------------------------------------------------------
REQ = "Requirements:\n- "
PHASE2 = [
    ("react_verb", REQ + "Ability to react quickly to production incidents.", "no technical concept",
     "concepts.find_concept_mentions: readme-safe alias 'react' matched with no usage check"),
    ("react_library", REQ + "Experience with React.", "framework.react REQUIRED", None),
    ("express_verb", REQ + "Ability to express complex ideas clearly.", "no technical concept",
     "concepts.find_concept_mentions: alias 'express' matched as a verb"),
    ("express_framework", REQ + "Experience building REST APIs with Express.", "framework.express REQUIRED", None),
    ("swift_adjective", REQ + "Swift decision-making under pressure.", "no technical concept",
     "concepts.find_concept_mentions: claim-initial 'Swift' (adjective) matched"),
    ("swift_language", REQ + "Experience building iOS apps in Swift.", "language.swift REQUIRED", None),
    ("curiosity_fragment", REQ + "Experience with SQL, attention to detail, and curiosity.", "language.sql only",
     "concepts._consider_fragment: single-word fragments are exempt from the M11-A1 shape gate"),
    ("alternatively_fragment", "Experience with AWS is required. Alternatively, Docker experience is acceptable.",
     "no unresolved:alternatively (cross-sentence OR structure is G16 scope)",
     "concepts._consider_fragment: claim-initial discourse adverb is a capitalised single-word fragment"),
    ("go_language", REQ + "Experience with Go.", "language.go REQUIRED",
     "registry: 'go' is readme_unsafe -> find_concept_mentions never matches; placeholder only"),
    ("go_verb", REQ + "A go-getter attitude and willingness to go the extra mile.", "no technical concept", None),
    ("go_or_golang", REQ + "Experience with Go or Golang.", "language.go REQUIRED",
     "alternatives._classify_segment_list: both segments resolve to ONE concept -> len(ids) < 2 -> 'unsafe'"),
    ("go_in_list", REQ + "Experience with Go, Docker, and Kubernetes.", "language.go, infra.docker, infra.kubernetes",
     "concepts._consider_fragment: unrecognised 'Go' minted as unresolved:go (wrong identity)"),
    ("narrative_inline", "About us: our platform is built with React and Python.", "nothing (company narrative)", None),
    ("narrative_employer", "Our platform is built with React, Python, and PostgreSQL.", "nothing (company narrative)",
     None),
    ("genuine_qualification", REQ + "Proficiency in React, Redux, and TypeScript.",
     "framework.react, unresolved:redux, language.typescript", None),
    ("bare_list", REQ + "Python, Docker, Kubernetes", "python, docker, kubernetes", None),
    ("mixed_list", REQ + "Python, teamwork, and Docker.", "python, docker",
     "concepts._consider_fragment: 'teamwork' single-word fragment minted"),
    ("context_fragment", REQ + "Solid React experience, including hooks and context.", "framework.react only",
     "concepts._consider_fragment: lowercase single common noun 'context' minted"),
    ("g16_018", "Either Python or Go and either Docker or Kubernetes is required.",
     "G16 gold: OR(Python, Go) AND OR(Docker, Kubernetes) -- compound defect, NOT fixed in G22",
     "registry: bare 'Go' unrecognised, so G17's mixed-segment detector misses it (then G16 compound logic)"),
    ("g16_043", "Experience with Python, Docker or Kubernetes is required.",
     "G16 gold: decline (mixed-kind list ambiguity) -- cross-check only",
     "alternatives: mixed-kind list without conjunction (G16 compound defect; no concept-identity error)"),
]


def _members(r):
    return list(h.members(r))


def reproduce(name: str, text: str, expected: str, stage: str | None) -> dict:
    claims = []
    for c in segment_description(text):
        d = decide_qualification_intent(c.text, c.section_kind)
        claims.append({"span": [c.start, c.end], "section_kind": c.section_kind, "admit": d.admit, "role": d.role,
                       "frame": d.frame,
                       "aliases": [[m.matched_alias, m.concept_id] for m in find_concept_mentions(d.scoped_text or c.text)]})
    parsed = h.parse(text)
    ids = sorted({i for r in parsed.profile.requirements for i in h.members(r) if not is_unresolved_concept_id(i)})
    views = {}
    for label, ev in (("no_evidence", []), ("evidence_for_every_registry_concept", ids)):
        a = assess_job(match_job(candidate_profile(ev), parsed.profile))
        views[label] = {"score": a.alignment_score, "rows": [
            {"members": _members(m.requirement), "category": m.requirement.category,
             "necessity": m.requirement.necessity.value,
             "span": [m.requirement.source_span.start, m.requirement.source_span.end],
             "span_text_exact": text[m.requirement.source_span.start:m.requirement.source_span.end]
             == m.requirement.original_text,
             "status": m.status.value, "counts_toward_score": a.counts_toward_alignment(m),
             "exclusion": None if a.alignment_exclusion_reason(m) is None else a.alignment_exclusion_reason(m).value}
            for m in a.match_analysis.requirement_matches]}
    return {"case": name, "text": text, "expected": expected, "correct": stage is None,
            "earliest_incorrect_stage": stage, "claims": claims,
            "unparsed_claims": [[u.source_span.start, u.source_span.end] for u in parsed.unparsed_claims], **views}


# ---- Phase 3: M10E-g3 -------------------------------------------------------------------------------
def m10e_g3() -> dict:
    corpus = json.loads((REPO_ROOT / "evaluation/m10e/narrative_controls.json").read_text(encoding="utf-8"))
    c = next(x for x in corpus["controls"] if x["id"] == "m10e-g3")
    doc = f"{c['section_context']}\n{c['text']}"
    frozen = {k: c[k] for k in ("text", "section_context", "sentence_purpose", "is_candidate_qualification",
                                "necessity_if_justified", "should_create_job_requirement", "should_produce_diagnostic",
                                "technical_concepts_may_enter_scoring", "purpose_rationale", "current_baseline_outcome")}
    live = {}
    for p in (*pol.POLICIES, *ph.POSTHOC):
        parsed = h.parse(doc, p)
        rows = parsed.profile.requirements
        a = assess_job(match_job(candidate_profile(["language.sql"]), parsed.profile))
        live[p.name] = {
            "rows": [[_members(r), r.category, r.necessity.value] for r in rows],
            "unparsed_claims": len(parsed.unparsed_claims),
            "row_existence_test_passes": (len(rows) > 0) == c["should_create_job_requirement"],
            "technical_concept_counted": any(a.counts_toward_alignment(m) for m in a.match_analysis.requirement_matches
                                             if h.members(m.requirement)),
            "sql_candidate_score": a.alignment_score}
    units = [{"text": doc.split("\n", 1)[1][s:e], "role": role, "frame": frame}
             for s, e, role, frame in __import__("gitscore.jobs.parsing.qualification_intent",
                                                 fromlist=["_analyse"])._analyse(c["text"])]
    return {"frozen_gold": frozen, "g21_units": units, "live": live,
            "test_projection": "tests/test_m10e_narrative_requirement_semantics.py asserts ONLY "
                               "len(profile.requirements) > 0 == should_create_job_requirement; "
                               "technical_concepts_may_enter_scoring is not asserted anywhere"}


# ---- Phase 7: historical compatibility ----------------------------------------------------------------
def _row_key(text: str, r) -> tuple:
    return (tuple(h.members(r)), r.category, r.necessity.value, r.source_span.start, r.source_span.end,
            text[r.source_span.start:r.source_span.end] == r.original_text)


def corpora() -> dict[str, list[tuple[str, str]]]:
    hist.ROOT = REPO_ROOT
    out = {name: [(i, t) for i, t, _ in items] for name, items in hist.tracked_corpora().items()}
    out["g20_dev"] = [(c["id"], c["text"]) for c in adm.load_controls("dev")]
    out["g20_holdout"] = [(c["id"], c["text"]) for c in adm.load_controls("holdout")]
    for name, rel in (("g21_adversarial", "adversarial_controls.json"), ("g21_negation_scope",
                                                                         "negation_scope_controls.json")):
        cs = json.loads((REPO_ROOT / "evaluation/m11g21" / rel).read_text(encoding="utf-8"))["controls"]
        out[name] = [(c["id"], c["text"]) for c in cs]
    return out


def parse_corpus(items, policy) -> dict:
    out = {}
    for iid, text in items:
        p = h.parse(text, policy)
        out[iid] = {"rows": Counter(_row_key(text, r) for r in p.profile.requirements),
                    "unparsed": len(p.unparsed_claims)}
    return out


def corpus_delta(base: dict, new: dict, keep_ids: bool = True) -> dict:
    d = {"texts": len(base), "texts_changed": 0, "rows_removed": 0, "rows_added": 0,
         "registry_ids_removed": Counter(), "registry_ids_added": Counter(), "unresolved_ids_removed": Counter(),
         "unresolved_ids_added": Counter(), "placeholders_removed": 0, "placeholders_added": 0,
         "unparsed_delta": 0, "necessity_changed": 0, "span_text_errors": 0, "changed_ids": []}
    for iid, b in base.items():
        n = new[iid]
        d["span_text_errors"] += sum(c for k, c in n["rows"].items() if not k[5])
        d["unparsed_delta"] += n["unparsed"] - b["unparsed"]
        if b["rows"] == n["rows"] and b["unparsed"] == n["unparsed"]:
            continue
        d["texts_changed"] += 1
        d["changed_ids"].append(iid)
        removed, added = b["rows"] - n["rows"], n["rows"] - b["rows"]
        d["rows_removed"] += sum(removed.values())
        d["rows_added"] += sum(added.values())
        for side, rows in (("removed", removed), ("added", added)):
            for k, cnt in rows.items():
                for i in k[0]:
                    bucket = "unresolved" if is_unresolved_concept_id(i) else "registry"
                    d[f"{bucket}_ids_{side}"][i] += cnt
                if k[1] in h.PLACEHOLDERS:
                    d[f"placeholders_{side}"] += cnt
        bn = {(k[0], k[3], k[4]): k[2] for k in b["rows"]}
        d["necessity_changed"] += sum(1 for k in n["rows"] if (k[0], k[3], k[4]) in bn and bn[(k[0], k[3], k[4])] != k[2])
    for key in ("registry_ids_removed", "registry_ids_added", "unresolved_ids_removed", "unresolved_ids_added"):
        d[key] = dict(sorted(d[key].items())) if keep_ids else sum(d[key].values())
    if not keep_ids:
        d.pop("changed_ids")
    return d


def g17_guard(base: dict, new: dict, g16_ids) -> dict:
    """G16 controls: the alternative-group / placeholder rows must be byte-identical (G17 containment)."""
    def alt(rows):
        return sorted(k for k in rows.elements() if len(k[0]) > 1 or k[1] == "alternative_requirement")
    changed = [i for i in g16_ids if alt(base[i]["rows"]) != alt(new[i]["rows"])]
    return {"g16_controls": len(g16_ids), "alternative_rows_changed": changed}


# ---- Phase 7: scoring ---------------------------------------------------------------------------------
def _score_view(profile, text: str, policy) -> dict:
    parsed = h.parse(text, policy)
    a = assess_job(match_job(profile, parsed.profile))
    ms = a.match_analysis.requirement_matches
    return {"score": a.alignment_score, "denominator": a.assessable_count,
            "supported_counted": sum(1 for m in ms if a.counts_toward_alignment(m) and m.status.value == "supported"),
            "statuses": sorted([_members(m.requirement), m.status.value, a.counts_toward_alignment(m)] for m in ms)}


def scoring_inputs() -> dict[str, list]:
    items: dict[str, list] = {}
    for name, rel in (("g15", "evaluation/m11g15/or_scoring_controls.json"),
                      ("g18", "evaluation/m11g18/eligibility_controls.json")):
        cs = json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))["controls"]
        items[name] = [(f"{c['id']}/{k['name']}", candidate_profile(k["evidence"]), c["job_text"], None)
                       for c in cs for k in c["candidates"]]
    g16 = json.loads((REPO_ROOT / "evaluation/m11g16/compound_logic_controls.json").read_text(encoding="utf-8"))
    items["g16"] = [(f"{c['id']}/{fx}", candidate_profile(f["evidence"]), c["text"], f["gold_truth"])
                    for c in g16["controls"] for fx, f in c["expected"]["per_fixture"].items()]
    names = list_candidate_names()
    profiles: dict = {}
    for label, rel in (("8c_v1", "evaluation/gold/matrix.json"), ("8c_v1_1", "evaluation/gold_v1_1/matrix.json")):
        matrix = json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))
        need = {p["candidate"]: load_candidate_fixture(next(n for n in names if n.lower() == p["candidate"].lower()))
                for p in matrix["pairs"] if p["candidate"] not in profiles}
        profiles.update(end_to_end_eval.build_candidate_profiles(need))
        items[label] = [(f"{p['candidate']}/{p['job_id']}", profiles[p["candidate"]], load_job(p["job_id"])["raw_text"],
                         None) for p in matrix["pairs"]]
    empty = candidate_profile([])
    items["m10"] = [(p.stem, empty, p.read_bytes().decode("utf-8"), None)
                    for p in sorted((REPO_ROOT / "evaluation/m10/source").glob("*.txt"))]
    return items


def scoring_delta(base: list, new: list, items: list) -> dict:
    d = {"fixtures": len(items), "score_changed": [], "denominator_changed": [], "became_undefined": [],
         "became_defined": [], "status_changed": [], "supported_counted_delta": 0,
         "g16_claim_false_supported": None, "g16_claim_true_supported": None}
    fs_b = fs_n = ts_b = ts_n = 0

    def satisfied(v):  # G16's claim-level definition: >=1 counted row and every counted row SUPPORTED
        scored = [s for s in v["statuses"] if s[2]]
        return bool(scored) and all(s[1] == "supported" for s in scored)
    for (fid, _, _, gold_truth), b, n in zip(items, base, new):
        if b["score"] != n["score"]:
            d["score_changed"].append([fid, b["score"], n["score"]])
        if b["denominator"] != n["denominator"]:
            d["denominator_changed"].append([fid, b["denominator"], n["denominator"]])
        if b["score"] is not None and n["score"] is None:
            d["became_undefined"].append(fid)
        if b["score"] is None and n["score"] is not None:
            d["became_defined"].append(fid)
        if b["statuses"] != n["statuses"]:
            d["status_changed"].append(fid)
        d["supported_counted_delta"] += n["supported_counted"] - b["supported_counted"]
        if gold_truth is not None:
            fs_b += satisfied(b) and gold_truth != "T"
            fs_n += satisfied(n) and gold_truth != "T"
            ts_b += satisfied(b) and gold_truth == "T"
            ts_n += satisfied(n) and gold_truth == "T"
    if any(it[3] is not None for it in items):
        d["g16_claim_false_supported"] = [fs_b, fs_n]
        d["g16_claim_true_supported"] = [ts_b, ts_n]
    return d


def m10e_row_existence(policy) -> list[str]:
    known = {"m10e-b3", "m10e-b4", "m10e-c1", "m10e-c2", "m10e-c3", "m10e-c4", "m10e-f2", "m10e-f4", "m10e-h3",
             "m10e-h4"}  # tests/test_m10e_narrative_requirement_semantics.py _KNOWN_OUT_OF_SCOPE_MISMATCHES
    corpus = json.loads((REPO_ROOT / "evaluation/m10e/narrative_controls.json").read_text(encoding="utf-8"))
    bad = []
    for c in corpus["controls"]:
        if c["id"] in known or not c["text"]:
            continue
        doc = f"{c['section_context']}\n{c['text']}" if c["section_context"] else c["text"]
        if (len(h.parse(doc, policy).profile.requirements) > 0) != c["should_create_job_requirement"]:
            bad.append(c["id"])
    return bad


# ---- private (counts only) -----------------------------------------------------------------------------
def private_counts(policy) -> dict:
    hist.ROOT = REPO_ROOT
    empty = candidate_profile([])
    out = {}
    for name, texts in hist.private_texts().items():
        per = []
        for t in texts:
            p = h.parse(t, policy)
            rows = p.profile.requirements
            a = assess_job(match_job(empty, p.profile))
            per.append((len(rows), sum(1 for r in rows if h.members(r) and not any(map(is_unresolved_concept_id,
                                                                                           h.members(r)))),
                        sum(1 for r in rows if any(map(is_unresolved_concept_id, h.members(r)))),
                        sum(1 for r in rows if r.category in h.PLACEHOLDERS), len(p.unparsed_claims),
                        a.assessable_count))
        keys = ("rows", "registry_concept_rows", "unresolved_concept_rows", "placeholder_rows", "unparsed_claims",
                "denominator_rows")
        out[name] = {"postings": len(texts), **{k: sum(x[i] for x in per) for i, k in enumerate(keys)},
                     "_per": per}
    return out


def _assert_ints(obj, path="") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _assert_ints(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _assert_ints(v, f"{path}[{i}]")
    elif not (isinstance(obj, int) or (isinstance(obj, str) and path.endswith(".note"))):
        raise AssertionError(f"private aggregate {path} is not an integer count: {obj!r}")


def build_report() -> dict:
    freezes = {}
    for split in ("dev", "eval"):
        res = gi.verify_frozen_file(f"evaluation/m11g22/concept_controls_{split}.json",
                                    f"evaluation/m11g22/{split}_hash_freeze.json")
        # G14 verification passed; its method ("raw" vs "canonical") depends on the checkout's newline form
        # (core.autocrlf), so it is deliberately NOT recorded -- the committed report is checkout-independent.
        freezes[split] = {"sha256": res.historical_raw_sha256, "verified": True}
    controls = {}
    for split in ("dev", "eval"):
        base_res, base_agg = h.run_split(split)
        controls[split] = {"BASE": {"aggregate": base_agg, "results": base_res}}
        by_id = {r["id"]: r for r in base_res}
        for p in CANDIDATES:
            res, agg = h.run_split(split, p)
            changed = [{"id": r["id"], "base": by_id[r["id"]]["produced"], "policy": r["produced"],
                        "base_placeholders": by_id[r["id"]]["placeholders"], "policy_placeholders": r["placeholders"],
                        "exact": [by_id[r["id"]]["exact"], r["exact"]]}
                       for r in res if (r["produced"], r["placeholders"], r["unparsed_claims"]) !=
                       (by_id[r["id"]]["produced"], by_id[r["id"]]["placeholders"], by_id[r["id"]]["unparsed_claims"])]
            controls[split][p.name] = {"aggregate": agg, "changed_controls": changed,
                                       "residual_errors": [{"id": r["id"], "taxonomy": r["taxonomy"]}
                                                           for r in res if r["taxonomy"]]}
    corp = corpora()
    base_parsed = {name: parse_corpus(items, pol.BASE) for name, items in corp.items()}
    hist_out, g17, m10e = {}, {}, {"BASE": m10e_row_existence(pol.BASE)}
    for p in CANDIDATES:
        parsed = {name: parse_corpus(items, p) for name, items in corp.items()}
        hist_out[p.name] = {name: corpus_delta(base_parsed[name], parsed[name]) for name in corp}
        g17[p.name] = g17_guard(base_parsed["g16"], parsed["g16"], [i for i, _ in corp["g16"]])
        m10e[p.name] = m10e_row_existence(p)
    inputs = scoring_inputs()
    base_scores = {name: [_score_view(prof, text, pol.BASE) for _, prof, text, _ in items]
                   for name, items in inputs.items()}
    scoring = {p.name: {name: scoring_delta(base_scores[name], [_score_view(prof, text, p)
                                                                for _, prof, text, _ in items], items)
                        for name, items in inputs.items()} for p in CANDIDATES}
    return {
        "versions": {"parser": JOB_DESCRIPTION_PARSER_VERSION, "scoring": SCORING_VERSION, "matcher": MATCHER_VERSION},
        "note": "research only: real parser v14 / matcher / scoring v2; candidate policies are offline adapters "
                "(scripts/evaluation_lib/m11g22_policies.py); no production code changed; no LLM",
        "policies": {p.name: {"components": list(p.components), "description": p.description}
                     for p in (*pol.POLICIES, *ph.POSTHOC)},
        "post_hoc_policies": {"names": [p.name for p in ph.POSTHOC],
                              "caveat": "written AFTER the EVAL run to address measured recall costs; DEV, EVAL and "
                                        "G21 negation-scope informed them, so their numbers are NOT validation"},
        "control_freezes": freezes,
        "labels": {"dev": "design set (policies designed against it)",
                   "eval": "authored separately before the policy design freeze by the SAME researcher: weakly "
                           "held out, not independent validation"},
        "phase2_reproductions": [reproduce(*c) for c in PHASE2],
        "m10e_g3": m10e_g3(),
        "controls": controls,
        "historical": hist_out,
        "g17_guard": g17,
        "m10e_row_existence_mismatches": m10e,
        "scoring": scoring,
    }


def build_private() -> dict:
    base = private_counts(pol.BASE)
    agg = {"note": "previously inspected private postings -- NOT independent validation; integer counts only"}
    for p in CANDIDATES:
        cur = private_counts(p)
        agg[p.name] = {}
        for name, b in base.items():
            n = cur[name]
            agg[p.name][name] = {"postings": b["postings"],
                                 **{f"{k}_base": b[k] for k in b if k not in ("postings", "_per")},
                                 **{f"{k}_policy": n[k] for k in n if k not in ("postings", "_per")},
                                 "postings_changed": sum(1 for x, y in zip(b["_per"], n["_per"]) if x != y)}
    _assert_ints({k: v for k, v in agg.items() if k != "note"})
    return agg


def encode(obj) -> bytes:
    return (json.dumps(obj, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def main() -> None:
    if JOB_DESCRIPTION_PARSER_VERSION != "job_description_parser:v14" or SCORING_VERSION != \
            "github_evidence_alignment:v2":
        raise SystemExit(f"G22 research describes parser v14 / scoring v2; live is {JOB_DESCRIPTION_PARSER_VERSION} / "
                         f"{SCORING_VERSION}")
    report = build_report()
    (OUT / "concept_precision_report.json").write_bytes(encode(report))
    for split in ("dev", "eval"):
        for name, v in report["controls"][split].items():
            a = v["aggregate"]
            print(split, name.ljust(26), "exact", a["exact_controls"], "/", a["exact_scored"], "falseReg",
                  a["false_registered"], "fabUnres", a["fabricated_unresolved"], "recall", a["concept_recall"],
                  "regRecall", a["registry_concept_recall"], "falseSUP", a["false_supported_counted"],
                  "tax", a["taxonomy"])
    for name, per in report["historical"].items():
        tot = {k: sum(c[k] for c in per.values()) for k in ("texts_changed", "rows_removed", "rows_added",
                                                              "placeholders_removed", "placeholders_added",
                                                              "unparsed_delta", "necessity_changed", "span_text_errors")}
        print("hist", name.ljust(26), tot, "regRemoved", {c: v["registry_ids_removed"] for c, v in per.items()
                                                          if v["registry_ids_removed"]})
    for name, per in report["scoring"].items():
        print("score", name.ljust(26), {c: (len(v["score_changed"]), len(v["denominator_changed"]),
                                            len(v["became_undefined"]), v["supported_counted_delta"],
                                            v["g16_claim_false_supported"], v["g16_claim_true_supported"]) for c, v in per.items()
                                        if v["score_changed"] or v["denominator_changed"] or v["status_changed"]})
    print("G17", {k: v["alternative_rows_changed"] for k, v in report["g17_guard"].items()})
    print("M10E", report["m10e_row_existence_mismatches"])
    if "--private-corpora" in sys.argv:
        priv = build_private()
        (OUT / "private_concept_aggregates.json").write_bytes(encode(priv))
        for p, per in priv.items():
            if p != "note":
                print("[private]", p, {k: (v["postings_changed"], v["rows_base"], v["rows_policy"],
                                          v["registry_concept_rows_base"], v["registry_concept_rows_policy"],
                                          v["unresolved_concept_rows_base"], v["unresolved_concept_rows_policy"],
                                          v["denominator_rows_base"], v["denominator_rows_policy"])
                                       for k, v in per.items()})


if __name__ == "__main__":
    main()
