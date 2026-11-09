"""Milestone 11-G18 -- frozen score-eligibility controls (builder).

    python scripts/evaluation_lib/m11g18_build_controls.py

Writes `evaluation/m11g18/eligibility_controls.json` and its G14-portable
freeze record `evaluation/m11g18/controls_hash_freeze.json`. Refuses to
overwrite an existing frozen file whose content would change.

Schema is a strict superset of M11-G15's (`or_scoring_controls.json`), so
one evaluator runs both corpora. Every expectation is DERIVED from
annotated facts by the written rule `expected_contract()` below; no
expectation is hand-entered, and none is derived from any production run.

Annotated facts per gold requirement:
* `members[].evidenceability` -- can ANY existing GitScore extractor ever
  emit evidence for this concept? `registry` (a registered concept: README
  mention / dependency manifest / language stats / Docker files),
  `language_stats` (outside the registry, but a GitHub-reported language
  that `evidence/extraction/languages.py` emits as `unresolved:<name>`),
  `none` (no extractor can ever emit it: cloud vendors outside the
  registry, unknown tools, unknown packages -- the dependency extractor
  SKIPS unknown packages -- and hardware interfaces), `non_technical`.
* `structure` -- `single`, `or`, `alias` (one concept, several spellings),
  `ambiguous_list`, `compound` (mixed AND/OR; G17 contract: contained),
  `non_technical`, `non_requirement` (narrative, not a qualification).
* `necessity` -- the posting's own necessity (`required` / `preferred` /
  `unknown`).
* per candidate: `evidence` (what the extractors would emit) and
  `true_competencies` (including what GitHub cannot show).

Two eligibility readings are frozen, both candidate-independent:
* `eligible_ideal` -- every member is evidenceable (registry OR
  language_stats). What a capability contract with a complete, declared
  GitHub-language vocabulary could achieve.
* `eligible_declared` -- every member is a REGISTERED concept. What a
  capability contract can establish from what the repository declares
  today (no language vocabulary exists in the repository).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation_lib"))

import gold_integrity as gi  # noqa: E402

OUT_DIR = REPO_ROOT / "evaluation" / "m11g18"
OUT_PATH = OUT_DIR / "eligibility_controls.json"
FREEZE_PATH = OUT_DIR / "controls_hash_freeze.json"

EVIDENCEABLE = ("registry", "language_stats")
SCOREABLE_STRUCTURES = ("single", "or", "alias")

CATEGORIES = {
    "satisfied_by_observed_evidence": "an acceptable alternative has observed GitHub evidence",
    "not_observed_fully_assessable": "every alternative is evidenceable and none has evidence",
    "partially_observable_no_positive_evidence": "some alternative can never be evidenced and no evidenceable "
                                                 "alternative has evidence -- absence proves nothing",
    "completely_non_assessable": "no alternative can ever be evidenced",
    "structurally_ambiguous": "the logical grouping itself cannot be determined from the text",
    "unsupported_related_evidence_only": "evidence exists only for a related concept that is NOT an acceptable "
                                         "alternative (related is never entailment)",
    "compound_logic_contained": "mixed AND/OR claim; G17 contract routes it to a non-scoreable placeholder",
    "non_technical_claim": "education / soft skill / other claim GitHub evidence cannot speak to",
    "not_a_requirement": "narrative or company text, not a candidate qualification",
}


def M(concept_id, surface, evidenceability):  # noqa: N802
    return {"concept_id": concept_id, "surface": surface, "evidenceability": evidenceability}


def G(gid, span_text, members, *, structure="single", necessity="required", related_only=(), groups=None):  # noqa: N802
    g = {"gid": gid, "span_text": span_text, "members": members, "structure": structure,
         "necessity": necessity, "related_only_concepts": list(related_only)}
    if groups is not None:
        g["groups"] = groups
    return g


def C(name, evidence, true_competencies):  # noqa: N802
    return {"name": name, "evidence": list(evidence), "true_competencies": list(true_competencies)}


def expected_contract(gold: dict, cand: dict) -> dict:
    """THE FROZEN RULE. Annotated facts in, contract out. Never sees production."""
    members = gold["members"]
    ids = [m["concept_id"] for m in members]
    struct = gold["structure"]
    true = set(cand["true_competencies"])
    if struct == "non_requirement":
        cat, truth = "not_a_requirement", None
    elif struct == "non_technical":
        cat, truth = "non_technical_claim", bool(set(ids) & true)
    elif struct == "ambiguous_list":
        cat, truth = "structurally_ambiguous", None
    elif struct == "compound":
        cat = "compound_logic_contained"
        truth = all(any(i in true for i in grp) for grp in gold["groups"])
    else:
        truth = bool(set(ids) & true)
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
    scoreable = struct in SCOREABLE_STRUCTURES and bool(members)
    eligible_ideal = scoreable and all(m["evidenceability"] in EVIDENCEABLE for m in members)
    eligible_declared = scoreable and all(m["evidenceability"] == "registry" for m in members)
    observed_ev = any(m["concept_id"] in cand["evidence"] and m["evidenceability"] in EVIDENCEABLE for m in members)

    def counted(eligible: bool) -> str:
        if not eligible:
            return "excluded"
        return "supported" if observed_ev else "not_observed"

    return {
        "category": cat,
        "truth_satisfied": truth,
        "eligible_ideal": eligible_ideal,
        "eligible_declared": eligible_declared,
        "counted_status_ideal": counted(eligible_ideal),
        "counted_status_declared": counted(eligible_declared),
        "positive_evidence_observed": observed_ev and struct in SCOREABLE_STRUCTURES + ("ambiguous_list",),
        "negative_decidable": cat in ("not_observed_fully_assessable", "unsupported_related_evidence_only"),
        "necessity": gold["necessity"],
    }


def expected_scores(golds: list[dict], cand: dict) -> dict:
    # Integer half-up: the same identity production's `_round_half_up_percentage` uses.
    out = {}
    for variant in ("ideal", "declared"):
        statuses = [expected_contract(g, cand)[f"counted_status_{variant}"] for g in golds]
        sup, elig = statuses.count("supported"), sum(s != "excluded" for s in statuses)
        out[variant] = {"supported": sup, "eligible": elig,
                        "score": None if elig == 0 else (2 * 100 * sup + elig) // (2 * elig)}
    return out


PY = M("language.python", "Python", "registry")
DOCKER = M("infra.docker", "Docker", "registry")
K8S = M("infra.kubernetes", "Kubernetes", "registry")
AWS = M("cloud.aws", "AWS", "registry")
PG = M("database.postgresql", "PostgreSQL", "registry")
PANDAS = M("data.library.pandas", "Pandas", "registry")
REACT = M("framework.react", "React", "registry")
VERILOG = M("hdl.verilog", "Verilog", "registry")
LANG_C = M("language.c", "C", "registry")
AZURE = M("unresolved:azure", "Azure", "none")
GCP = M("unresolved:gcp", "GCP", "none")
TERRAFORM = M("unresolved:terraform", "Terraform", "none")
ANSIBLE = M("unresolved:ansible", "Ansible", "none")
NUMPY = M("unresolved:numpy", "NumPy", "none")
KAFKA = M("unresolved:kafka", "Kafka", "none")
SPI = M("unresolved:spi", "SPI", "none")
I2C = M("unresolved:i2c", "I2C", "none")
UART = M("unresolved:uart", "UART", "none")
ELIXIR = M("unresolved:elixir", "Elixir", "language_stats")
ZIG = M("unresolved:zig", "Zig", "language_stats")
VUE = M("unresolved:vue", "Vue", "language_stats")
MATLAB = M("unresolved:matlab", "MATLAB", "language_stats")
EDU = M("non_technical:education", "Bachelor's degree", "non_technical")
COMM = M("non_technical:communication", "communication skills", "non_technical")
CLEARANCE = M("non_technical:security_clearance", "a security clearance", "non_technical")

# (family, id, description, job_text, golds, candidates)
RAW_CONTROLS = [
    ("or_fully_assessable", "01", "OR of two registered concepts.",
     "Requirements:\n- Experience with Docker or Kubernetes",
     [G("g1", "Docker or Kubernetes", [DOCKER, K8S], structure="or")],
     [C("docker", ["infra.docker"], ["infra.docker"]),
      C("none", [], []),
      C("k8s_true_no_evidence", [], ["infra.kubernetes"])]),
    ("aws_or_azure", "02", "Mixed OR: registered AWS + unregistered, never-evidenceable Azure (REQUIRED).",
     "Requirements:\n- Experience with AWS or Azure",
     [G("g1", "AWS or Azure", [AWS, AZURE], structure="or")],
     [C("aws", ["cloud.aws"], ["cloud.aws"]),
      C("azure_true_no_evidence", [], ["unresolved:azure"]),
      C("none", [], [])]),
    ("aws_or_azure", "03", "Mixed OR, PREFERRED.",
     "Nice to have:\n- Experience with AWS or Azure",
     [G("g1", "AWS or Azure", [AWS, AZURE], structure="or", necessity="preferred")],
     [C("aws", ["cloud.aws"], ["cloud.aws"]),
      C("azure_true_no_evidence", [], ["unresolved:azure"])]),
    ("azure_or_gcp", "04", "OR of two never-evidenceable cloud vendors.",
     "Requirements:\n- Experience with Azure or GCP",
     [G("g1", "Azure or GCP", [AZURE, GCP], structure="or")],
     [C("azure_true_no_evidence", [], ["unresolved:azure"]),
      C("none", [], [])]),
    ("two_non_assessable", "05", "OR of two unknown tools no extractor emits.",
     "Requirements:\n- Experience with Terraform or Ansible",
     [G("g1", "Terraform or Ansible", [TERRAFORM, ANSIBLE], structure="or")],
     [C("terraform_true_no_evidence", [], ["unresolved:terraform"]),
      C("none", [], [])]),
    ("unregistered_languages_or", "06", "OR of two GitHub languages outside the registry (language-stats fallback).",
     "Requirements:\n- Experience with Elixir or Zig",
     [G("g1", "Elixir or Zig", [ELIXIR, ZIG], structure="or")],
     [C("zig_language_evidence", ["unresolved:zig"], ["unresolved:zig"]),
      C("none", [], [])]),
    ("mixed_registered_and_language", "07", "OR of a registered framework and an unregistered GitHub language.",
     "Requirements:\n- Experience with Vue or React",
     [G("g1", "Vue or React", [VUE, REACT], structure="or")],
     [C("vue_language_evidence", ["unresolved:vue"], ["unresolved:vue"]),
      C("react", ["framework.react"], ["framework.react"]),
      C("none", [], [])]),
    ("standalone_supported", "08", "Standalone registered technology.",
     "Requirements:\n- Experience with PostgreSQL",
     [G("g1", "PostgreSQL", [PG])],
     [C("postgres", ["database.postgresql"], ["database.postgresql"]),
      C("none", [], [])]),
    ("standalone_unsupported_tool", "09", "Enumeration with an unknown tool no extractor emits.",
     "Requirements:\n- Python, Terraform, Docker",
     [G("g1", "Python", [PY]), G("g2", "Terraform", [TERRAFORM]), G("g3", "Docker", [DOCKER])],
     [C("python_docker_terraform_true", ["language.python", "infra.docker"],
        ["language.python", "infra.docker", "unresolved:terraform"]),
      C("none", [], [])]),
    ("standalone_unregistered_language", "10", "Enumeration with a GitHub language outside the registry.",
     "Requirements:\n- Python, Elixir, Docker",
     [G("g1", "Python", [PY]), G("g2", "Elixir", [ELIXIR]), G("g3", "Docker", [DOCKER])],
     [C("python_elixir_evidence", ["language.python", "unresolved:elixir"], ["language.python", "unresolved:elixir"]),
      C("python_docker_elixir_true_no_evidence", ["language.python", "infra.docker"],
        ["language.python", "infra.docker", "unresolved:elixir"]),
      C("none", [], [])]),
    ("package_without_detector", "11", "Enumeration with a package the dependency extractor skips.",
     "Requirements:\n- Proficiency in Python, NumPy, and Pandas",
     [G("g1", "Python", [PY]), G("g2", "NumPy", [NUMPY]), G("g3", "Pandas", [PANDAS])],
     [C("python_pandas_numpy_true", ["language.python", "data.library.pandas"],
        ["language.python", "data.library.pandas", "unresolved:numpy"]),
      C("none", [], [])]),
    ("hardware_interfaces", "12", "Hardware communication interfaces (never evidenceable).",
     "Requirements:\n- Python, SPI, I2C, UART",
     [G("g1", "Python", [PY]), G("g2", "SPI", [SPI]), G("g3", "I2C", [I2C]), G("g4", "UART", [UART])],
     [C("python_and_interfaces_true", ["language.python"],
        ["language.python", "unresolved:spi", "unresolved:i2c", "unresolved:uart"]),
      C("none", [], [])]),
    ("hardware_with_prose_unsafe_alias", "13",
     "Bare 'C' in an enumeration (a prose-unsafe registered alias) next to Verilog and SPI.",
     "Requirements:\n- C, Verilog, SPI",
     [G("g1", "C", [LANG_C]), G("g2", "Verilog", [VERILOG]), G("g3", "SPI", [SPI])],
     [C("c_verilog_evidence", ["language.c", "hdl.verilog"], ["language.c", "hdl.verilog", "unresolved:spi"]),
      C("none", [], [])]),
    ("non_technical_and_education", "14", "Education and soft skill next to one technology.",
     "Requirements:\n- Bachelor's degree in Computer Science\n- Strong communication skills\n- Experience with Docker",
     [G("g1", "Bachelor's degree in Computer Science", [EDU], structure="non_technical"),
      G("g2", "Strong communication skills", [COMM], structure="non_technical"),
      G("g3", "Docker", [DOCKER])],
     [C("docker", ["infra.docker"], ["infra.docker", "non_technical:education"]),
      C("none", [], ["non_technical:education"])]),
    ("duplicate_alternatives", "15", "Two spellings of one never-evidenceable vendor.",
     "Requirements:\n- Experience with Azure or Microsoft Azure",
     [G("g1", "Azure or Microsoft Azure", [AZURE], structure="alias")],
     [C("azure_true_no_evidence", [], ["unresolved:azure"])]),
    ("duplicate_alternatives", "16", "Two spellings of one registered language.",
     "Requirements:\n- Experience with Go or Golang",
     [G("g1", "Go or Golang", [M("language.go", "Go", "registry")], structure="alias")],
     [C("go", ["language.go"], ["language.go"]),
      C("none", [], [])]),
    ("ambiguous_combination", "17", "'A, B or C' list whose grouping is ambiguous, with an unknown tool.",
     "Requirements:\n- Python, Docker or Terraform",
     [G("g1", "Python, Docker or Terraform", [PY, DOCKER, TERRAFORM], structure="ambiguous_list")],
     [C("python", ["language.python"], ["language.python"]),
      C("none", [], [])]),
    ("multiple_independent", "18", "Four independent requirements, one mixed OR; evidence varies, job fixed.",
     "Requirements:\n- Python\n- Docker\n- Experience with AWS or Azure\n- PostgreSQL",
     [G("g1", "Python", [PY]), G("g2", "Docker", [DOCKER]), G("g3", "AWS or Azure", [AWS, AZURE], structure="or"),
      G("g4", "PostgreSQL", [PG])],
     [C("all_four_with_aws", ["language.python", "infra.docker", "cloud.aws", "database.postgresql"],
        ["language.python", "infra.docker", "cloud.aws", "database.postgresql"]),
      C("three_plus_azure_true", ["language.python", "infra.docker", "database.postgresql"],
        ["language.python", "infra.docker", "database.postgresql", "unresolved:azure"]),
      C("python_only", ["language.python"], ["language.python"]),
      C("none", [], [])]),
    ("g17_placeholder_interaction", "19", "G17-contained compound claim next to an independent requirement.",
     "Requirements:\n- Experience with Docker or Kubernetes, and Python\n- Experience with PostgreSQL",
     [G("g1", "Docker or Kubernetes, and Python", [DOCKER, K8S, PY], structure="compound",
        groups=[["infra.docker", "infra.kubernetes"], ["language.python"]]),
      G("g2", "PostgreSQL", [PG])],
     [C("python_docker_postgres", ["language.python", "infra.docker", "database.postgresql"],
        ["language.python", "infra.docker", "database.postgresql"]),
      C("python_postgres", ["language.python", "database.postgresql"], ["language.python", "database.postgresql"])]),
    ("single_sentence_unknown", "20", "Single-sentence unknown tool (existing unresolved_requirement placeholder).",
     "Experience with Terraform is required.",
     [G("g1", "Terraform", [TERRAFORM])],
     [C("terraform_true_no_evidence", [], ["unresolved:terraform"])]),
    ("preferred_enumeration_unknown", "21", "PREFERRED enumeration with an unknown tool.",
     "Preferred qualifications:\n- Python, Kafka, Docker",
     [G("g1", "Python", [PY], necessity="preferred"), G("g2", "Kafka", [KAFKA], necessity="preferred"),
      G("g3", "Docker", [DOCKER], necessity="preferred")],
     [C("python_only_kafka_true", ["language.python"], ["language.python", "unresolved:kafka"]),
      C("python_docker", ["language.python", "infra.docker"], ["language.python", "infra.docker"])]),
    ("or_with_non_technical", "22", "OR of a technology and a non-technical alternative.",
     "Requirements:\n- Experience with Docker or a security clearance",
     [G("g1", "Docker or a security clearance", [DOCKER, CLEARANCE], structure="or")],
     [C("docker", ["infra.docker"], ["infra.docker"]),
      C("clearance_true", [], ["non_technical:security_clearance"])]),
    ("standalone_unregistered_language", "23", "Enumeration with MATLAB (GitHub language outside the registry).",
     "Requirements:\n- Python, MATLAB, Docker",
     [G("g1", "Python", [PY]), G("g2", "MATLAB", [MATLAB]), G("g3", "Docker", [DOCKER])],
     [C("python_matlab_evidence", ["language.python", "unresolved:matlab"], ["language.python", "unresolved:matlab"]),
      C("none", [], [])]),
    ("related_only_evidence", "24", "Related-concept evidence only (never entailment).",
     "Requirements:\n- Experience with Kubernetes",
     [G("g1", "Kubernetes", [K8S], related_only=["infra.docker"])],
     [C("docker_only", ["infra.docker"], ["infra.docker"])]),
    ("narrative_non_requirement", "25", "Company narrative naming technologies -- not a qualification.",
     "About us: we use Python, Terraform and Docker.",
     [G("g1", "Python", [PY], structure="non_requirement", necessity="unknown"),
      G("g2", "Terraform", [TERRAFORM], structure="non_requirement", necessity="unknown"),
      G("g3", "Docker", [DOCKER], structure="non_requirement", necessity="unknown")],
     [C("python_docker", ["language.python", "infra.docker"], ["language.python", "infra.docker"])]),
    ("standalone_registered_cloud", "26", "Standalone registered AWS; Azure-only candidate.",
     "Requirements:\n- Experience with AWS",
     [G("g1", "AWS", [AWS])],
     [C("aws", ["cloud.aws"], ["cloud.aws"]),
      C("azure_only_true", [], ["unresolved:azure"])]),
]


def build() -> dict:
    controls = []
    for family, cid, desc, text, golds, cands in RAW_CONTROLS:
        for g in golds:
            assert text.count(g["span_text"]) == 1, (cid, g["span_text"])
        controls.append({
            "id": f"m11g18-{cid}",
            "family": family,
            "description": desc,
            "job_text": text,
            "gold_requirements": golds,
            "candidates": cands,
            "expected": {c["name"]: {g["gid"]: expected_contract(g, c) for g in golds} for c in cands},
            "expected_scores": {c["name"]: expected_scores(golds, c) for c in cands},
        })
    return {
        "schema_version": 1,
        "milestone": "M11-G18",
        "provenance": "original synthetic text and candidates authored for M11-G18; no real or private posting",
        "authorship_disclosure": "same author as the G10-G17 research; not independently annotated. Job texts were "
                                 "parsed while authoring to confirm each phrasing produces rows; the matcher, "
                                 "assessor and every policy ran only after the freeze.",
        "categories": CATEGORIES,
        "member_evidenceability_vocabulary": ["registry", "language_stats", "none", "non_technical"],
        "structure_vocabulary": ["single", "or", "alias", "ambiguous_list", "compound", "non_technical",
                                 "non_requirement"],
        "controls": controls,
    }


def main() -> None:
    payload = (json.dumps(build(), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if OUT_PATH.exists():
        if gi.canonical_bytes(OUT_PATH.read_bytes()) != gi.canonical_bytes(payload):
            raise SystemExit("REFUSING to overwrite frozen M11-G18 controls with different content")
        print("frozen controls already present and identical; nothing written")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_bytes(payload)
    freeze = {
        "frozen_file": "evaluation/m11g18/eligibility_controls.json",
        "sha256": gi.sha256(payload),
        "sha256_lf_normalized": gi.sha256(gi.canonical_bytes(payload)),
        "length_bytes": len(payload),
        "canonical_contract": gi.CONTRACT,
        "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Frozen BEFORE the production matcher/assessor or any policy simulation ran on these controls.",
    }
    FREEZE_PATH.write_bytes((json.dumps(freeze, indent=2) + "\n").encode("utf-8"))
    n = sum(len(c["candidates"]) for c in build()["controls"])
    outcomes = sum(len(c["candidates"]) * len(c["gold_requirements"]) for c in build()["controls"])
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)}: {len(RAW_CONTROLS)} controls, {n} candidate variants, "
          f"{outcomes} outcomes; sha256={freeze['sha256']}")


if __name__ == "__main__":
    main()
