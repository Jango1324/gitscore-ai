"""Milestone 11-G15 Phase 3 -- frozen controls for mixed-observability OR
scoring integrity.

Writes `evaluation/m11g15/or_scoring_controls.json` and its freeze record.
Every job text and candidate here is ORIGINAL synthetic material (no real
posting, no private corpus). Expected outcomes are DERIVED by the written
semantic rule `expected_outcome()` below from annotated FACTS only --
which members GitHub evidence can ever speak to, which evidence the
synthetic candidate has, what the candidate truly knows, and the
annotator's reading of the logical structure. Production behaviour is
never consulted: this file is frozen before the production matcher, the
assessor or any policy simulation runs on a single control.

Member evidenceability (annotated gold, NOT inferred from production):
* "registry"       -- a registered TechnicalConcept the evidence extractors can emit;
* "language_stats" -- an unregistered programming language: GitHub language statistics
                      produce `unresolved:<language>` evidence for it;
* "none"           -- unregistered tool/platform: no extractor ever emits evidence for it;
* "non_technical"  -- not a technology at all.

Freeze convention (M11-G14): raw `sha256` plus `sha256_lf_normalized`
(contract crlf-to-lf/v1); verification compares the LF-normalized hash.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gold_integrity as gi  # noqa: E402

OUT_DIR = REPO_ROOT / "evaluation" / "m11g15"
OUT_PATH = OUT_DIR / "or_scoring_controls.json"
FREEZE_PATH = OUT_DIR / "controls_hash_freeze.json"

EVIDENCEABLE = ("registry", "language_stats")

CATEGORIES = {
    "satisfied_by_observed_evidence": "an acceptable alternative has observed GitHub evidence",
    "not_observed_fully_assessable": "every alternative is evidenceable and none has evidence",
    "partially_observable_no_positive_evidence": "some alternative can never be evidenced and no evidenceable "
                                                 "alternative has evidence -- absence proves nothing",
    "completely_non_assessable": "no alternative can ever be evidenced",
    "structurally_ambiguous": "the logical grouping itself cannot be determined from the text",
    "unsupported_related_evidence_only": "evidence exists only for a related concept that is NOT an acceptable "
                                         "alternative (related is never entailment)",
}

# Can the current three-state public MatchStatus express the category
# without overclaiming in either direction?
STATUS_REPRESENTABLE = {
    "satisfied_by_observed_evidence": (True, "SUPPORTED"),
    "not_observed_fully_assessable": (True, "NOT_OBSERVED"),
    "partially_observable_no_positive_evidence": (
        False, "NOT_OBSERVED overclaims a decidable negative; NOT_ASSESSABLE hides that part is checkable"),
    "completely_non_assessable": (True, "NOT_ASSESSABLE"),
    "structurally_ambiguous": (False, "no status for 'grouping undetermined'; NOT_ASSESSABLE is the closest safe one"),
    "unsupported_related_evidence_only": (True, "NOT_OBSERVED (the related evidence must not count)"),
}


def M(concept_id, surface, evidenceability):  # noqa: N802
    return {"concept_id": concept_id, "surface": surface, "evidenceability": evidenceability}


def G(gid, span_text, members, *, structure="or", necessity="required", related_only=()):  # noqa: N802
    return {"gid": gid, "span_text": span_text, "members": members, "structure": structure,
            "necessity": necessity, "related_only_concepts": list(related_only)}


def C(name, evidence, true_competencies):  # noqa: N802
    return {"name": name, "evidence": list(evidence), "true_competencies": list(true_competencies)}


def expected_outcome(gold: dict, cand: dict) -> dict:
    """The frozen semantic rule. Uses annotated facts only."""
    members = gold["members"]
    ids = {m["concept_id"] for m in members}
    truth = bool(ids & set(cand["true_competencies"])) if gold["structure"] != "ambiguous_list" else None
    if gold["structure"] == "ambiguous_list":
        cat = "structurally_ambiguous"
    else:
        observed = any(m["concept_id"] in cand["evidence"] and m["evidenceability"] in EVIDENCEABLE for m in members)
        evid = [m for m in members if m["evidenceability"] in EVIDENCEABLE]
        if observed:
            cat = "satisfied_by_observed_evidence"
        elif not evid:
            cat = "completely_non_assessable"
        elif len(evid) == len(members):
            related = set(gold["related_only_concepts"]) & set(cand["evidence"])
            cat = "unsupported_related_evidence_only" if related else "not_observed_fully_assessable"
        else:
            cat = "partially_observable_no_positive_evidence"
    representable, how = STATUS_REPRESENTABLE[cat]
    return {
        "category": cat,
        "truth_satisfied": truth,
        "negative_decidable": cat in ("not_observed_fully_assessable", "unsupported_related_evidence_only"),
        "positive_observed": cat == "satisfied_by_observed_evidence",
        "match_status_representable": representable,
        "closest_public_status": how,
    }


DOCKER = M("infra.docker", "Docker", "registry")
K8S = M("infra.kubernetes", "Kubernetes", "registry")
AWS = M("cloud.aws", "AWS", "registry")
PY = M("language.python", "Python", "registry")
GO = M("language.go", "Go", "registry")
PG = M("database.postgresql", "PostgreSQL", "registry")
AZURE = M("unresolved:azure", "Azure", "none")
GCP = M("unresolved:gcp", "GCP", "none")
TERRAFORM = M("unresolved:terraform", "Terraform", "none")
ELIXIR = M("unresolved:elixir", "Elixir", "language_stats")
ZIG = M("unresolved:zig", "Zig", "language_stats")
CLEARANCE = M("non_technical:security_clearance", "a security clearance", "non_technical")

RAW_CONTROLS = [
    ("A", "A1", "Two assessable alternatives, one supported.",
     "Experience with Docker or Kubernetes is required.",
     [G("g1", "Experience with Docker or Kubernetes", [DOCKER, K8S])],
     [C("docker_evidence", ["infra.docker"], ["infra.docker"])]),
    ("B", "B1", "Two assessable alternatives, neither supported.",
     "Experience with Docker or Kubernetes is preferred.",
     [G("g1", "Experience with Docker or Kubernetes", [DOCKER, K8S], necessity="preferred")],
     [C("no_evidence", [], []), C("knows_k8s_no_evidence", [], ["infra.kubernetes"])]),
    ("C", "C1", "Assessable + non-assessable; assessable branch supported.",
     "Experience with AWS or Azure is required.",
     [G("g1", "Experience with AWS or Azure", [AWS, AZURE])],
     [C("aws_evidence", ["cloud.aws"], ["cloud.aws"])]),
    ("D", "D1", "Assessable + non-assessable; no evidence for the assessable branch.",
     "Experience with AWS or Azure is required.",
     [G("g1", "Experience with AWS or Azure", [AWS, AZURE])],
     [C("azure_only_truth", [], ["unresolved:azure"]), C("neither", [], [])]),
    ("E", "E1", "Two non-assessable alternatives.",
     "Experience with Azure or GCP is required.",
     [G("g1", "Experience with Azure or GCP", [AZURE, GCP])],
     [C("azure_truth", [], ["unresolved:azure"]), C("neither", [], [])]),
    ("F", "F1", "Three alternatives with mixed observability (registry, none, language statistics).",
     "Experience with at least one of AWS, Azure, or Elixir is required.",
     [G("g1", "at least one of AWS, Azure, or Elixir", [AWS, AZURE, ELIXIR])],
     [C("elixir_language_evidence", ["unresolved:elixir"], ["unresolved:elixir"]),
      C("azure_only_truth", [], ["unresolved:azure"]), C("neither", [], [])]),
    ("G", "G1", "Single unresolved, non-evidenceable concept.",
     "Experience with Terraform is required.",
     [G("g1", "Experience with Terraform", [TERRAFORM], structure="single")],
     [C("terraform_truth", [], ["unresolved:terraform"])]),
    ("G", "G2", "Single unresolved concept that IS evidenceable through language statistics.",
     "Experience with Elixir is required.",
     [G("g1", "Experience with Elixir", [ELIXIR], structure="single")],
     [C("elixir_language_evidence", ["unresolved:elixir"], ["unresolved:elixir"]), C("neither", [], [])]),
    ("G", "G3", "OR group of two unresolved languages, both evidenceable through language statistics.",
     "Experience with Elixir or Zig is required.",
     [G("g1", "Experience with Elixir or Zig", [ELIXIR, ZIG])],
     [C("zig_language_evidence", ["unresolved:zig"], ["unresolved:zig"]), C("neither", [], [])]),
    ("H", "H1", "PREFERRED mixed-observability group (sub-score tier).",
     "Experience with AWS or Azure is preferred.",
     [G("g1", "Experience with AWS or Azure", [AWS, AZURE], necessity="preferred")],
     [C("azure_only_truth", [], ["unresolved:azure"]), C("aws_evidence", ["cloud.aws"], ["cloud.aws"])]),
    ("I", "I1", "Equivalent aliases of one concept (not distinct alternatives).",
     "Experience with Kubernetes or k8s is required.",
     [G("g1", "Experience with Kubernetes or k8s", [K8S], structure="alias")],
     [C("k8s_evidence", ["infra.kubernetes"], ["infra.kubernetes"]), C("neither", [], [])]),
    ("I", "I2", "Non-technical alternative beside a technical one.",
     "Experience with Docker or a security clearance is required.",
     [G("g1", "Experience with Docker or a security clearance", [DOCKER, CLEARANCE])],
     [C("docker_evidence", ["infra.docker"], ["infra.docker"]),
      C("clearance_only_truth", [], ["non_technical:security_clearance"])]),
    ("J", "J1", "AND requirement: two separate requirements.",
     "Experience with Python and Docker is required.",
     [G("g1", "Python", [PY], structure="single"), G("g2", "Docker", [DOCKER], structure="single")],
     [C("python_only", ["language.python"], ["language.python"])]),
    ("K", "K1", "Nested AND/OR: (Docker or Kubernetes) AND Python.",
     "Experience with Docker or Kubernetes, and Python, is required.",
     [G("g1", "Docker or Kubernetes", [DOCKER, K8S], structure="or"),
      G("g2", "Python", [PY], structure="single")],
     [C("python_only", ["language.python"], ["language.python"]),
      C("docker_and_python", ["infra.docker", "language.python"], ["infra.docker", "language.python"])]),
    ("L", "L1", "'A, B or C' list whose grouping is ambiguous.",
     "Experience with Docker, Kubernetes or Terraform is required.",
     [G("g1", "Docker, Kubernetes or Terraform", [DOCKER, K8S, TERRAFORM], structure="ambiguous_list")],
     [C("docker_evidence", ["infra.docker"], ["infra.docker"])]),
    ("M", "M1", "Evidence belongs to a different, related requirement.",
     "Kubernetes experience is required. Docker experience is a plus.",
     [G("g1", "Kubernetes experience", [K8S], structure="single", related_only=("infra.docker",)),
      G("g2", "Docker experience", [DOCKER], structure="single", necessity="preferred")],
     [C("docker_only", ["infra.docker"], ["infra.docker"])]),
    ("N", "N1", "Duplicate alternative and duplicate evidence.",
     "Experience with Python or Go or Python is required.",
     [G("g1", "Experience with Python or Go or Python", [PY, GO])],
     [C("python_duplicate_evidence", ["language.python", "language.python"], ["language.python"])]),
    ("O", "O1", "Mixed-observability OR group alongside unrelated fully assessable requirements.",
     "Required:\n- Python\n- Docker\n- PostgreSQL\n- AWS or Azure",
     [G("g1", "Python", [PY], structure="single"), G("g2", "Docker", [DOCKER], structure="single"),
      G("g3", "PostgreSQL", [PG], structure="single"), G("g4", "AWS or Azure", [AWS, AZURE])],
     [C("three_plus_azure_truth", ["language.python", "infra.docker", "database.postgresql"],
        ["language.python", "infra.docker", "database.postgresql", "unresolved:azure"]),
      C("all_four_with_aws", ["language.python", "infra.docker", "database.postgresql", "cloud.aws"],
        ["language.python", "infra.docker", "database.postgresql", "cloud.aws"])]),
    ("P", "P1", "Identical job, varying candidate evidence.",
     "Required:\n- Go\n- Kubernetes\n- AWS, Azure or GCP experience",
     [G("g1", "Go", [GO], structure="single"), G("g2", "Kubernetes", [K8S], structure="single"),
      G("g3", "AWS, Azure or GCP experience", [AWS, AZURE, GCP])],
     [C("nothing", [], []),
      C("go_only", ["language.go"], ["language.go"]),
      C("go_k8s", ["language.go", "infra.kubernetes"], ["language.go", "infra.kubernetes"]),
      C("go_k8s_aws", ["language.go", "infra.kubernetes", "cloud.aws"],
        ["language.go", "infra.kubernetes", "cloud.aws"]),
      C("go_k8s_gcp_truth", ["language.go", "infra.kubernetes"],
        ["language.go", "infra.kubernetes", "unresolved:gcp"])]),
]


def main() -> None:
    controls = []
    for case, cid, desc, text, golds, cands in RAW_CONTROLS:
        for g in golds:
            assert text.count(g["span_text"]) == 1, (cid, g["span_text"])
        controls.append({
            "id": f"m11g15-{cid}",
            "case": case,
            "description": desc,
            "job_text": text,
            "gold_requirements": golds,
            "candidates": cands,
            "expected": {c["name"]: {g["gid"]: expected_outcome(g, c) for g in golds} for c in cands},
        })
    out = {
        "schema_version": 1,
        "milestone": "M11-G15",
        "provenance": "original synthetic text and candidates authored for M11-G15; no real or private posting",
        "authorship_disclosure": "same author as the G10-G14 research; not independently annotated",
        "categories": CATEGORIES,
        "member_evidenceability_vocabulary": ["registry", "language_stats", "none", "non_technical"],
        "controls": controls,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(out, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    OUT_PATH.write_bytes(payload)
    freeze = {
        "frozen_file": "evaluation/m11g15/or_scoring_controls.json",
        "sha256": gi.sha256(payload),
        "sha256_lf_normalized": gi.sha256(gi.canonical_bytes(payload)),
        "length_bytes": len(payload),
        "canonical_contract": gi.CONTRACT,
        "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Frozen BEFORE the production matcher/assessor or any policy simulation ran on these controls.",
    }
    FREEZE_PATH.write_bytes((json.dumps(freeze, indent=2) + "\n").encode("utf-8"))
    n_pairs = sum(len(c["candidates"]) for c in controls)
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)}: {len(controls)} controls, {n_pairs} candidate variants; "
          f"sha256={freeze['sha256']}")


if __name__ == "__main__":
    main()
