"""Milestone 11-G22 -- technical-concept recognition precision controls (builder).

    python scripts/evaluation_lib/m11g22_build_controls.py

Writes two DISTINCT synthetic control sets and their G14-portable freeze records:

  evaluation/m11g22/concept_controls_dev.json   (+ dev_hash_freeze.json)
  evaluation/m11g22/concept_controls_eval.json  (+ eval_hash_freeze.json)

and refuses to overwrite a frozen file whose content would change. The freeze records
keep their freeze-time note ("NOT registered ... pending authorization"); both freezes were
registered in `evaluation/integrity/canonical_hash_manifest.json` at the authorized G22
research commit, with these original hashes.

Provenance and honesty:
  * Every text is AUTHOR-CREATED synthetic wording; no real posting text, employer,
    or private material.
  * Labels (`is_qualification`, `expected_concepts`, necessity) record the TRUE
    reading decided from first principles, written and frozen BEFORE the live parser
    or any candidate policy was run on these controls.
  * DEV is the design set (candidate policies are designed against it). EVAL was
    authored separately, with different surfaces/aliases, and is run only after the
    policy design is frozen (`evaluation/m11g22/policy_design_freeze.json`).
  * Both sets are written by the same researcher who designs the policies: neither is
    an independent validation set.

`expected_concepts` is the exact multiset of TECHNICAL rows a correct parser emits:
`members` is one registry concept id, one `unresolved:<term>` id, or (for an OR
group) the sorted member ids; `necessity` is required / preferred. Non-technical rows
(experience, soft_skill, education, ...) are outside G22 and are ignored by the
evaluator. An empty list means no technical concept may be produced.
`identity_only` controls are scored only for false / fabricated identities (their
row structure belongs to another milestone, e.g. G16 cross-sentence alternatives).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import gold_integrity as gi  # noqa: E402
from gitscore.concepts.registry import unresolved_concept_id as U  # noqa: E402,N812

OUT_DIR = REPO_ROOT / "evaluation" / "m11g22"
R, P = "required", "preferred"
REQ, NICE, RESP = "Requirements:\n- ", "Nice to have:\n- ", "Responsibilities:\n- "

PY, GO, JAVA, KT, SWIFT, RUST, RUBY, PHP = ("language.python", "language.go", "language.java", "language.kotlin",
                                            "language.swift", "language.rust", "language.ruby", "language.php")
TS, SQL, SHELL, CPP, CS, C = "language.typescript", "language.sql", "language.shell", "language.cpp", \
    "language.csharp", "language.c"
REACT, RN, EXPRESS, FLASK, FASTAPI, NEXT = ("framework.react", "framework.react_native", "framework.express",
                                            "framework.flask", "framework.fastapi", "framework.nextjs")
DOCKER, K8S, AWS, PG, TORCH, TF, PANDAS, CUDA, FREERTOS = (
    "infra.docker", "infra.kubernetes", "cloud.aws", "database.postgresql", "ml.framework.pytorch",
    "ml.framework.tensorflow", "data.library.pandas", "platform.cuda", "embedded.rtos.freertos")


def K(*members, nec=R):  # noqa: N802 -- one expected technical row
    return {"members": sorted(members), "necessity": nec}


def X(cid, split, family, text, qual, concepts, *, pair=None, identity_only=False, limitation=False, note=""):  # noqa: N802
    return {"id": cid, "split": split, "family": family, "pair": f"m11g22-{pair}" if pair else None, "text": text,
            "is_qualification": qual,
            "expected_concepts": concepts, "identity_only": identity_only, "expected_limitation": limitation,
            "note": note}


def D(n, *a, **k):  # noqa: N802
    return X(f"m11g22-d{n:02d}", "dev", *a, **k)


def E(n, *a, **k):  # noqa: N802
    return X(f"m11g22-e{n:02d}", "eval", *a, **k)


DEV = [
    # ordinary English usage vs the registered technology (near-neighbour pairs)
    D(1, "ordinary_verb", REQ + "Ability to react quickly to production incidents.", True, [], pair="d02",
      note="'react' is a verb"),
    D(2, "clear_registered", REQ + "Experience with React and modern frontend tooling.", True, [K(REACT)], pair="d01"),
    D(3, "ordinary_verb", REQ + "Ability to express complex technical ideas clearly.", True, [], pair="d04"),
    D(4, "clear_registered", REQ + "Experience building REST APIs with Express.", True, [K(EXPRESS)], pair="d03"),
    D(5, "ordinary_adjective", REQ + "Swift decision-making in a fast-paced environment.", True, [], pair="d06",
      note="claim-initial capital carries no technical signal"),
    D(6, "clear_registered", REQ + "Experience building iOS applications in Swift.", True, [K(SWIFT)], pair="d05"),
    D(7, "ordinary_adjective", REQ + "A swift learner who adapts to new codebases.", True, []),
    D(8, "ordinary_verb", REQ + "Comfortable responding to incidents and able to react calmly under pressure.", True, []),
    D(9, "genuine_unknown", REQ + "Proficiency in React, Redux, and TypeScript.", True, [K(REACT), K(U("Redux")), K(TS)]),
    # single-word fragments next to a confirmed concept
    D(10, "fragment_abstract_noun", REQ + "Experience with SQL, attention to detail, and curiosity.", True, [K(SQL)],
      pair="d11"),
    D(11, "genuine_unknown", REQ + "Experience with SQL, dbt, and Airflow.", True,
      [K(SQL), K(U("dbt")), K(U("Airflow"))], pair="d10"),
    D(12, "fragment_discourse_adverb", "Experience with AWS is required. Alternatively, Docker experience is acceptable.",
      True, [K(AWS), K(DOCKER)], identity_only=True,
      note="G16-058 shape; the cross-sentence OR structure is G16's, only identities are scored here"),
    D(13, "fragment_soft_skill", REQ + "Python, teamwork, and Docker.", True, [K(PY), K(DOCKER)], pair="d14"),
    D(14, "genuine_unknown", REQ + "Python, Terraform, and Docker.", True, [K(PY), K(U("Terraform")), K(DOCKER)],
      pair="d13"),
    D(15, "fragment_abstract_noun", REQ + "Experience with Java, communication, and leadership.", True, [K(JAVA)]),
    D(16, "fragment_discourse_adverb", REQ + "Additionally, experience with Python, Kubernetes, and Helm.", True,
      [K(PY), K(K8S), K(U("Helm"))]),
    D(17, "genuine_unknown_lowercase", REQ + "Experience with Python, numpy, and scipy.", True,
      [K(PY), K(U("numpy")), K(U("scipy"))], note="lowercase package names must stay recognised"),
    # Go
    D(18, "go_language", REQ + "Experience with Go.", True, [K(GO)], pair="d21"),
    D(19, "equivalent_alias", REQ + "Experience with Go or Golang.", True, [K(GO)], note="two aliases, one concept"),
    D(20, "or_alternative", REQ + "Experience with Python or Go.", True, [K(GO, PY)]),
    D(21, "go_ordinary", REQ + "A go-getter attitude and willingness to go the extra mile.", True, [], pair="d18"),
    D(22, "go_language", REQ + "Strong Go programming skills.", True, [K(GO)]),
    D(23, "go_language", REQ + "Golang experience.", True, [K(GO)]),
    # narratives / responsibilities / negation
    D(24, "company_narrative", "Our platform is built with React, Python, and PostgreSQL.", False, []),
    D(25, "company_narrative", REQ + "Our frontend team uses React and TypeScript.", False, []),
    D(26, "responsibility", RESP + "Build REST APIs with Express and PostgreSQL.", False, []),
    D(27, "responsibility", RESP + "React quickly to customer escalations.", False, []),
    D(28, "negative_qualification", REQ + "Experience with React is not required.", False, []),
    D(29, "negative_qualification", REQ + "No Swift experience needed; we will teach you.", False, []),
    # mixed technical / non-technical wording
    D(30, "mixed", REQ + "Experience with Python and strong communication skills.", True, [K(PY)]),
    D(31, "mixed", REQ + "Ability to react to changing priorities and experience with Kubernetes.", True, [K(K8S)]),
    # bare technical lists
    D(32, "bare_list", REQ + "Python, Docker, Kubernetes", True, [K(PY), K(DOCKER), K(K8S)]),
    D(33, "bare_list_ambiguous", NICE + "React, Express, Swift", True,
      [K(REACT, nec=P), K(EXPRESS, nec=P), K(SWIFT, nec=P)], note="genuine bare list of ambiguous aliases"),
    D(34, "bare_list", REQ + "Rust, C++, and Zephyr", True, [K(RUST), K(CPP), K(U("Zephyr"))]),
    # acronyms / punctuation variants
    D(35, "punctuation_variant", REQ + "Experience with React.js and Express.js.", True, [K(REACT), K(EXPRESS)]),
    D(36, "acronym", REQ + "Hands-on experience with K8s and AWS.", True, [K(K8S), K(AWS)]),
    D(37, "punctuation_variant", REQ + "Strong C++ and C# skills.", True, [K(CPP), K(CS)]),
    # ordinary nouns that are registry aliases
    D(38, "ordinary_noun", REQ + "Willingness to pass the torch to junior engineers through mentoring.", True, [],
      pair="d39"),
    D(39, "clear_registered", REQ + "Experience training deep learning models with Torch.", True, [K(TORCH)],
      pair="d38"),
    D(40, "lowercase_genuine", REQ + "Experience writing shell scripts for automation.", True, [K(SHELL)], pair="d41"),
    D(41, "ordinary_noun", REQ + "Ability to come out of your shell and present to clients.", True, [], pair="d40"),
    # OR alternatives
    D(42, "or_alternative", REQ + "Experience with React or Vue.", True, [K(REACT, U("Vue"))]),
    D(43, "ordinary_verb_or", REQ + "Ability to react or adapt quickly to incidents.", True, []),
    D(44, "or_alternative", REQ + "Experience with Express or Flask.", True, [K(EXPRESS, FLASK)]),
    D(45, "language_ordinary_meaning", REQ + "Experience with Ruby on Rails.", True, [K(RUBY)]),
    D(46, "go_ordinary", REQ + "Python, SQL, and a go-to attitude for debugging.", True, [K(PY), K(SQL)]),
]

EVAL = [
    E(1, "ordinary_verb", REQ + "Must be able to react to shifting priorities without losing focus.", True, [],
      pair="e02"),
    E(2, "clear_registered", REQ + "Solid React experience, including hooks and context.", True, [K(REACT)],
      pair="e01"),
    E(3, "ordinary_adjective", REQ + "Comfortable working in an express delivery environment with tight deadlines.",
      True, [], pair="e04"),
    E(4, "clear_registered", REQ + "Production experience with Express.", True, [K(EXPRESS)], pair="e03"),
    E(5, "or_alternative", NICE + "Swift or Kotlin for mobile development.", True, [K(KT, SWIFT, nec=P)], pair="e06"),
    E(6, "ordinary_adjective", REQ + "Swift turnaround on code reviews.", True, [], pair="e05"),
    E(7, "or_alternative", REQ + "Experience with Rust or C++.", True, [K(CPP, RUST)], pair="e08"),
    E(8, "ordinary_noun", REQ + "Experience inspecting steel structures for rust and corrosion.", True, [], pair="e07"),
    E(9, "language_ordinary_meaning", REQ + "Ruby and Rails experience.", True, [K(RUBY)]),
    E(10, "genuine_unknown_lowercase", REQ + "Proficiency with pandas, scikit-learn, and Python.", True,
      [K(PANDAS), K(U("scikit-learn")), K(PY)]),
    E(11, "fragment_abstract_noun", REQ + "Experience with Python, creativity, and ownership.", True, [K(PY)],
      pair="e12"),
    E(12, "genuine_unknown", REQ + "Experience with Python, Spark, and Kafka.", True,
      [K(PY), K(U("Spark")), K(U("Kafka"))], pair="e11"),
    E(13, "fragment_discourse_adverb", REQ + "Additionally, experience with AWS, Terraform, and Docker.", True,
      [K(AWS), K(U("Terraform")), K(DOCKER)]),
    E(14, "fragment_discourse_adverb", REQ + "Preferably, familiarity with Docker, Helm, and Kubernetes.", True,
      [K(DOCKER, nec=P), K(U("Helm"), nec=P), K(K8S, nec=P)], note="'Preferably' makes the claim PREFERRED"),
    E(15, "genuine_unknown_suffix", REQ + "Experience with C#, Unity, and Blender.", True,
      [K(CS), K(U("Unity")), K(U("Blender"))], note="'Unity' carries an abstract-noun suffix but is a technology"),
    E(16, "go_language", REQ + "Go experience in production systems.", True, [K(GO)], pair="e19"),
    E(17, "equivalent_alias", REQ + "Golang or Go experience.", True, [K(GO)]),
    E(18, "go_language", REQ + "Experience with Go, Docker, and Kubernetes.", True, [K(GO), K(DOCKER), K(K8S)]),
    E(19, "go_ordinary", REQ + "Ready to go above and beyond for customers.", True, [], pair="e16"),
    E(20, "equivalent_alias", REQ + "Experience with Postgres or PostgreSQL.", True, [K(PG)]),
    E(21, "equivalent_alias", REQ + "Experience with K8s or Kubernetes.", True, [K(K8S)]),
    E(22, "company_narrative", "Our services run on Kubernetes and are written in Rust.", False, []),
    E(23, "responsibility", RESP + "Maintain our Flask services and Redis caches.", False, []),
    E(24, "negative_qualification", REQ + "Experience with Flask is not required.", False, []),
    E(25, "equivalent_alias", REQ + "Bash or shell scripting experience.", True, [K(SHELL)]),
    E(26, "mixed", REQ + "Experience with Java, plus strong written communication.", True, [K(JAVA)]),
    E(27, "bare_list", REQ + "Java, Kotlin, Gradle", True, [K(JAVA), K(KT), K(U("Gradle"))]),
    E(28, "clear_registered", REQ + "Hands-on experience with PyTorch and CUDA.", True, [K(TORCH), K(CUDA)]),
    E(29, "ordinary_noun", REQ + "Carry the torch for engineering quality across teams.", True, []),
    E(30, "punctuation_variant", REQ + "Experience with Next.js and React.", True, [K(NEXT), K(REACT)]),
    E(31, "ordinary_verb", REQ + "Ability to express trade-offs to non-technical stakeholders.", True, []),
    E(32, "or_alternative", REQ + "REST API development with Express.js or FastAPI.", True, [K(EXPRESS, FASTAPI)]),
    E(33, "genuine_unknown", REQ + "Experience with SQL, ETL pipelines, and Tableau.", True, [K(SQL), K(U("Tableau"))]),
    E(34, "fragment_abstract_noun", REQ + "Python, adaptability, and Docker.", True, [K(PY), K(DOCKER)]),
    E(35, "or_alternative", REQ + "Experience in Ruby, PHP, or Python.", True, [K(PHP, PY, RUBY)]),
    E(36, "acronym", REQ + "Embedded C and FreeRTOS experience.", True, [K(C), K(FREERTOS)]),
    E(37, "genuine_unknown", REQ + "Comfortable with Linux, Bash, and Git.", True,
      [K(U("Linux")), K(SHELL), K(U("Git"))]),
    E(38, "clear_registered", NICE + "Exposure to React Native.", True, [K(RN, nec=P)]),
    E(39, "or_alternative", REQ + "React Native or Swift experience.", True, [K(RN, SWIFT)]),
    E(40, "ordinary_verb", REQ + "Ability to react constructively to feedback.", True, []),
    E(41, "fragment_abstract_noun", REQ + "Experience with TensorFlow, Keras, and patience.", True,
      [K(TF), K(U("Keras"))]),
    E(42, "fragment_discourse_adverb", REQ + "Similarly, experience with GCP, Azure, and AWS.", True,
      [K(U("GCP")), K(U("Azure")), K(AWS)]),
    E(43, "genuine_unknown_suffix", REQ + "Plotly, Dash, and Python.", True,
      [K(U("Plotly")), K(U("Dash")), K(PY)], note="claim-initial '-ly' word followed by a comma is a technology"),
    E(44, "company_narrative", REQ + "We built our data platform on Spark, Python, and AWS.", False, []),
]


def _write(controls: list[dict], split: str, label_timing: str) -> None:
    name = f"concept_controls_{split}.json"
    out, freeze = OUT_DIR / name, OUT_DIR / f"{split}_hash_freeze.json"
    doc = {
        "schema_version": 1, "milestone": "M11-G22 (technical concept recognition precision)", "split": split,
        "provenance": "author-created synthetic examples; no real posting text, employer or private material",
        "authorship_disclosure": ("Written by the same researcher who designs the G22 candidate policies; NOT an "
                                  "independent validation set."),
        "label_timing": label_timing,
        "controls": controls,
    }
    payload = (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if out.exists():
        if out.read_bytes() != payload:
            raise SystemExit(f"{out} is frozen and its content would change; refusing to overwrite")
        print(split, "unchanged", gi.sha256(payload))
        return
    out.write_bytes(payload)
    freeze.write_bytes((json.dumps({
        "frozen_file": out.relative_to(REPO_ROOT).as_posix(), "sha256": gi.sha256(payload),
        "sha256_lf_normalized": gi.sha256(gi.canonical_bytes(payload)), "length_bytes": len(payload),
        "canonical_contract": "crlf-to-lf/v1",
        "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Labels frozen BEFORE the live parser or any G22 candidate policy ran on this set. NOT registered in "
                "the canonical manifest (pending authorization).",
    }, indent=2) + "\n").encode("utf-8"))
    print(f"wrote {len(controls)} {split} controls; sha256={gi.sha256(payload)} bytes={len(payload)}")


def main() -> None:
    ids = [c["id"] for c in DEV + EVAL]
    assert len(ids) == len(set(ids))
    _write(DEV, "dev", "labels frozen before any parser run; candidate policies are designed against this set")
    _write(EVAL, "eval", "authored separately from DEV; labels frozen before any parser run; run only after the "
                         "G22 policy design freeze")


if __name__ == "__main__":
    main()
