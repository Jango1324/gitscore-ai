"""Milestone 11-G20 -- historical / regression impact of candidate admission policies.

Read-only over every frozen corpus (no gold is rewritten). For each text the
v13 replica (== production, asserted) is compared with a policy:
rows added / removed, necessity changes, placeholder changes, UnparsedClaim
deltas, and -- where the corpus carries admission gold -- fixes and
regressions against that gold. Private postings yield integer counts only.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import m11g20_admission as adm

ROOT = adm.REPO_ROOT


def _rows_key(rows) -> Counter:
    return Counter((adm.row_members(r), r.category, r.necessity.value, r.source_span.start, r.source_span.end)
                   for r in rows)


def _whole(text: str, admit: bool | None) -> list[tuple[int, int, bool | None]]:
    return [(0, len(text), admit)]


def tracked_corpora() -> dict[str, list[tuple[str, str, list]]]:
    """corpus -> [(item_id, text, gold_spans)], gold_spans = [(start, end, should_admit | None)]."""
    out: dict[str, list] = {}
    g16 = json.loads((ROOT / "evaluation/m11g16/compound_logic_controls.json").read_text(encoding="utf-8"))["controls"]
    out["g16"] = [(c["id"], c["text"], _whole(c["text"], c["is_qualification"])) for c in g16]
    for name, rel in (("g15", "evaluation/m11g15/or_scoring_controls.json"),
                      ("g18", "evaluation/m11g18/eligibility_controls.json")):
        cs = json.loads((ROOT / rel).read_text(encoding="utf-8"))["controls"]
        out[name] = [(c["id"], c["job_text"], _whole(c["job_text"], any(
            g["structure"] != "non_requirement" for g in c["gold_requirements"]))) for c in cs]
    m10d = json.loads((ROOT / "evaluation/m10d/alternative_controls.json").read_text(encoding="utf-8"))["controls"]
    out["m10d"] = [(c["id"], c["text"], _whole(c["text"], c["has_candidate_qualification"])) for c in m10d if c["text"]]
    m10e = json.loads((ROOT / "evaluation/m10e/narrative_controls.json").read_text(encoding="utf-8"))["controls"]
    items = []
    for c in m10e:
        if not c["text"]:
            continue
        doc = f"{c['section_context']}\n{c['text']}" if c["section_context"] else c["text"]
        start = len(doc) - len(c["text"])
        items.append((c["id"], doc, [(start, len(doc), c["should_create_job_requirement"])]))
    out["m10e"] = items
    for name, rel in (("g6", "evaluation/m11g6/heading_controls.json"), ("g7", "evaluation/m11g7/boundary_controls.json")):
        cs = json.loads((ROOT / rel).read_text(encoding="utf-8"))["controls"]
        items = []
        for c in cs:
            lines = ([c["heading_line"]] if c["heading_line"] is not None else []) + list(c["body_lines"])
            doc = "\n".join(lines) + "\n"
            spans, cursor = [], 0
            quals = {q["text"]: q for q in c.get("body_qualifications", [])}
            for line in lines:
                s = doc.index(line, cursor)
                cursor = s + len(line)
                q = quals.get(line)
                if q is not None:
                    spans.append((s, s + len(line), q["should_enter_assessment"]))
            items.append((c["id"], doc, spans))
        out[name] = items
    jobs = []
    for p in sorted((ROOT / "evaluation/jobs").glob("*.json")):
        jobs.append((p.stem, json.loads(p.read_text(encoding="utf-8"))["raw_text"], []))
    out["8c_jobs"] = jobs
    out["m10_soti_manulife"] = [(p.stem, p.read_bytes().decode("utf-8"), [])
                                for p in sorted((ROOT / "evaluation/m10/source").glob("*.txt"))]
    return out


def private_texts() -> dict[str, list[str]]:
    """Previously inspected private postings (untracked). Texts never leave this process."""
    out = {}
    for name, rel in (("m11d", "evaluation/m11d/source"), ("m11f", "evaluation/m11f/source"),
                      ("m11g5", "evaluation/m11g5/source"), ("m11g9", "evaluation/m11g9/source")):
        src = ROOT / rel
        out[name] = [p.read_bytes().decode("utf-8") for p in sorted(src.rglob("*.txt"))] if src.is_dir() else []
    return out


def _admitted_in(rows, start: int, end: int) -> bool:
    return any(adm._overlap(r.source_span.start, r.source_span.end, start, end) for r in rows)


def compare_text(text: str, policy: adm.Policy, gold_spans: list) -> dict:
    v13 = adm.parse(text, adm.POLICY_V13)
    pol = adm.parse(text, policy)
    k0, k1 = _rows_key(v13.rows), _rows_key(pol.rows)
    removed, added = k0 - k1, k1 - k0
    nec0 = {(m, c, s, e): n for (m, c, n, s, e) in k0}
    nec_changed = sum(1 for (m, c, n, s, e) in added if (m, c, s, e) in nec0 and nec0[(m, c, s, e)] != n)
    ph0 = sum(1 for r in v13.rows if adm.row_kind(r) == "placeholder")
    ph1 = sum(1 for r in pol.rows if adm.row_kind(r) == "placeholder")
    out = {"rows_removed": sum(removed.values()) - nec_changed, "rows_added": sum(added.values()) - nec_changed,
           "necessity_changed": nec_changed, "placeholders_delta": ph1 - ph0,
           "unparsed_delta": len(pol.unparsed) - len(v13.unparsed), "changed": k0 != k1,
           "gold_fixed": 0, "gold_regressed": 0, "gold_wrong_both": 0, "gold_spans": 0}
    for s, e, should in gold_spans:
        if should is None:
            continue
        out["gold_spans"] += 1
        a0, a1 = _admitted_in(v13.rows, s, e), _admitted_in(pol.rows, s, e)
        if a0 != should and a1 == should:
            out["gold_fixed"] += 1
        elif a0 == should and a1 != should:
            out["gold_regressed"] += 1
        elif a0 != should and a1 != should:
            out["gold_wrong_both"] += 1
    return out


def corpus_impact(items, policy: adm.Policy, keep_ids: bool = True) -> dict:
    agg = Counter()
    changed_ids, regressed_ids, fixed_ids = [], [], []
    for item_id, text, gold in items:
        r = compare_text(text, policy, gold)
        for k, v in r.items():
            agg[k] += int(v)
        if r["changed"]:
            changed_ids.append(item_id)
        if r["gold_regressed"]:
            regressed_ids.append(item_id)
        if r["gold_fixed"]:
            fixed_ids.append(item_id)
    out = {"items": len(items), **{k: agg[k] for k in ("changed", "rows_removed", "rows_added", "necessity_changed",
                                                        "placeholders_delta", "unparsed_delta", "gold_spans",
                                                        "gold_fixed", "gold_regressed", "gold_wrong_both")}}
    if keep_ids:
        out.update(changed_ids=changed_ids, gold_regressed_ids=regressed_ids, gold_fixed_ids=fixed_ids)
    return out


def g17_containment_preserved(policy: adm.Policy) -> dict:
    """Every G16 control whose claim the policy still admits must keep v13's exact
    alternative-group / placeholder rows (G17 containment untouched)."""
    items = tracked_corpora()["g16"]
    checked = violations = 0
    bad = []
    for item_id, text, _ in items:
        v13 = adm.parse(text, adm.POLICY_V13)
        pol = adm.parse(text, policy)
        alt0 = [r for r in v13.rows if r.alternative_concept_ids or r.category == "alternative_requirement"]
        if not alt0 or not pol.rows:
            continue
        checked += 1
        alt1 = [r for r in pol.rows if r.alternative_concept_ids or r.category == "alternative_requirement"]
        if [(adm.row_members(r), r.category, r.source_span) for r in alt0] != \
           [(adm.row_members(r), r.category, r.source_span) for r in alt1]:
            violations += 1
            bad.append(item_id)
    return {"g16_controls_with_alternative_rows_still_admitted": checked, "violations": violations, "ids": bad}


def score_impact_8c(policy: adm.Policy) -> dict:
    """Frozen 8c matrices: v2 score / denominator per pair under v13 vs `policy`."""
    from evaluation_lib import end_to_end_eval
    from evaluation_lib.loaders import list_candidate_names, load_candidate_fixture, load_job
    from gitscore.assessment import assess_job
    from gitscore.matching import match_job

    names = list_candidate_names()
    out = {}
    profiles = {}
    for label, rel in (("8c:v1", "evaluation/gold/matrix.json"), ("8c:v1.1", "evaluation/gold_v1_1/matrix.json")):
        matrix = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        need = {p["candidate"]: load_candidate_fixture(next(n for n in names if n.lower() == p["candidate"].lower()))
                for p in matrix["pairs"] if p["candidate"] not in profiles}
        profiles.update(end_to_end_eval.build_candidate_profiles(need))
        changes = {}
        for pair in matrix["pairs"]:
            text = load_job(pair["job_id"])["raw_text"]
            cand = profiles[pair["candidate"]]
            a0 = assess_job(match_job(cand, adm.parse(text, adm.POLICY_V13).profile))
            a1 = assess_job(match_job(cand, adm.parse(text, policy).profile))
            if (a0.alignment_score, a0.assessable_count) != (a1.alignment_score, a1.assessable_count):
                changes[f"{pair['candidate']}/{pair['job_id']}"] = {
                    "v13": [a0.alignment_score, a0.assessable_count], "policy": [a1.alignment_score, a1.assessable_count]}
        out[label] = {"pairs": len(matrix["pairs"]), "changed": len(changes), "changes": changes}
    return out


def private_impact(policy: adm.Policy) -> dict:
    """Integer counts only -- no text, file name, id or span leaves this function."""
    from gitscore.assessment import assess_job
    from gitscore.matching import match_job

    empty = adm.candidate_profile([])
    out = {"note": "previously inspected private postings -- NOT held out, NOT independent; integer counts only"}
    for name, texts in private_texts().items():
        agg = Counter()
        for text in texts:
            r = compare_text(text, policy, [])
            for k in ("rows_removed", "rows_added", "necessity_changed", "placeholders_delta", "unparsed_delta"):
                agg[k] += r[k]
            agg["postings_changed"] += int(r["changed"])
            p0 = adm.parse(text, adm.POLICY_V13)
            p1 = adm.parse(text, policy)
            agg["rows_v13"] += len(p0.rows)
            agg["rows_policy"] += len(p1.rows)
            agg["required_rows_v13"] += sum(1 for x in p0.rows if x.necessity.value == "required")
            agg["required_rows_policy"] += sum(1 for x in p1.rows if x.necessity.value == "required")
            d0 = assess_job(match_job(empty, p0.profile)).assessable_count
            d1 = assess_job(match_job(empty, p1.profile)).assessable_count
            agg["denominator_rows_v13"] += d0
            agg["denominator_rows_policy"] += d1
            agg["postings_with_no_eligible_requirement_v13"] += int(d0 == 0)
            agg["postings_with_no_eligible_requirement_policy"] += int(d1 == 0)
            agg["postings_losing_all_rows"] += int(bool(p0.rows) and not p1.rows)
        out[name] = {"postings": len(texts), **dict(sorted(agg.items()))}
    return out


def private_available() -> bool:
    return all((ROOT / rel).is_dir() for rel in ("evaluation/m11d/source", "evaluation/m11f/source",
                                                 "evaluation/m11g5/source", "evaluation/m11g9/source"))


__all__ = ["tracked_corpora", "corpus_impact", "g17_containment_preserved", "score_impact_8c", "private_impact",
           "private_available"]


PRIVATE_ANNOTATIONS = (
    ("m11d", "evaluation/m11d/holdout_annotations.json", "claims", "evaluation/m11d/source"),
    ("m11f", "evaluation/m11f/holdout_annotations.json", "controls", "evaluation/m11f/source"),
    ("m11g5", "evaluation/m11g5/holdout_annotations.json", "controls", "evaluation/m11g5/source"),
    ("m11g9_dev", "evaluation/m11g9/dev_annotations.json", "controls", "evaluation/m11g9/source"),
    ("m11g9_holdout", "evaluation/m11g9/holdout_annotations.json", "controls", "evaluation/m11g9/source"),
)


def private_labeled_impact(policies) -> dict:
    """Pre-existing private claim annotations (written in M11-D/F/G5/G9, independently of
    G20) give `is_applicant_qualification` / `necessity` per claim. Each claim is located
    in its source posting by exact unique substring; admission = any row overlapping it.
    Integer counts only: no text, id, file name or span is returned."""
    out = {"note": "previously inspected private postings with pre-existing claim annotations; NOT independent of "
                   "the repository's history, but not used to design any G20 policy; integer counts only"}
    pols = [adm.POLICY_V13, *policies]
    for name, ann_rel, key, src_rel in PRIVATE_ANNOTATIONS:
        ann_path, src = ROOT / ann_rel, ROOT / src_rel
        if not ann_path.exists() or not src.is_dir():
            out[name] = {"available": False}
            continue
        claims = json.loads(ann_path.read_text(encoding="utf-8"))[key]
        texts = [p.read_bytes().decode("utf-8") for p in sorted(src.rglob("*.txt"))]
        parsed = {pol.name: [adm.parse(t, pol) for t in texts] for pol in pols}
        agg = {pol.name: Counter() for pol in pols}
        located = 0
        for c in claims:
            hits = [i for i, t in enumerate(texts) if c["text"] in t]
            if len(hits) != 1:
                continue
            located += 1
            i = hits[0]
            s = texts[i].index(c["text"])
            e = s + len(c["text"])
            qual = bool(c["is_applicant_qualification"])
            gold_nec = (c.get("necessity") or "").lower() or None
            for pol in pols:
                rows = [r for r in parsed[pol.name][i].rows
                        if adm._overlap(r.source_span.start, r.source_span.end, s, e)]
                a = agg[pol.name]
                a["qual_claims" if qual else "nonqual_claims"] += 1
                if rows:
                    a["qual_admitted" if qual else "nonqual_admitted"] += 1
                    if not qual and any(r.necessity.value == "required" for r in rows):
                        a["nonqual_admitted_required"] += 1
                    if qual and gold_nec in ("required", "preferred"):
                        a["qual_nec_scored"] += 1
                        a["qual_nec_correct"] += int({r.necessity.value for r in rows} == {gold_nec})
                        a["qual_preferred_marked_required"] += int(
                            gold_nec == "preferred" and any(r.necessity.value == "required" for r in rows))
        res = {"claims": len(claims), "located": located}
        for pol in pols:
            a = agg[pol.name]
            adm_total = a["qual_admitted"] + a["nonqual_admitted"]
            res[pol.name] = {
                **dict(sorted(a.items())),
                "admission_precision": None if not adm_total else round(a["qual_admitted"] / adm_total, 4),
                "qualification_recall": None if not a["qual_claims"] else round(a["qual_admitted"] / a["qual_claims"], 4),
                "false_admission_rate": None if not a["nonqual_claims"] else
                round(a["nonqual_admitted"] / a["nonqual_claims"], 4),
            }
        out[name] = res
    return out
