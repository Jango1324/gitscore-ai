"""Milestone 11-G21 -- fresh adversarial synthetic controls (builder).

    python scripts/evaluation_lib/m11g21_build_adversarial.py

Writes `evaluation/m11g21/adversarial_controls.json` and its G14-portable freeze
record `evaluation/m11g21/adversarial_hash_freeze.json`; refuses to overwrite a
frozen file whose content would change.

Provenance: NEWLY AUTHORED synthetic text (no real posting text, no real
employer), written for G21 AFTER the B1NR design was known and BEFORE parser v14
(or the v13-vs-v14 comparison) ran on any of it. Same author as G20 and the
implementation, so these are targeted adversarial probes, NOT independent
external validation. Several cases were written expecting B1NR to fail them;
labels record the truth, not the predicted output.

Unit schema and gold rules are identical to G20's
(`scripts/evaluation_lib/m11g20_build_controls.py`), so the same evaluator scores
both sets.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import gold_integrity as gi  # noqa: E402
from m11g20_build_controls import (  # noqa: E402
    AWS, CUDA, DOCKER, FASTAPI, GO, JAVA, K8S, KOTLIN, P, PG, PY, R, REACT, REDIS, RUST, SQL, TORCH, TS, C, U,
    _validate)

OUT_DIR = REPO_ROOT / "evaluation" / "m11g21"
OUT = OUT_DIR / "adversarial_controls.json"
FREEZE = OUT_DIR / "adversarial_hash_freeze.json"

CONTROLS = [
    # --- hiring-process obligations ---------------------------------------------------------
    C("m11g21-a01", "hiring_process_obligation", "Applicants must complete a 60-minute Python coding test.",
      [U("Applicants must complete a 60-minute Python coding test.", "process", False, tech=[PY])]),
    C("m11g21-a02", "hiring_process_obligation",
      "Shortlisted applicants will complete a take-home exercise in Golang.",
      [U("Shortlisted applicants will complete a take-home exercise in Golang.", "process", False, tech=[GO])]),
    C("m11g21-a03", "hiring_process_obligation",
      "Candidates will be asked to present a past project built with React.",
      [U("Candidates will be asked to present a past project built with React.", "process", False, tech=[REACT])]),
    # --- on-call / incident response --------------------------------------------------------------
    C("m11g21-a04", "on_call", "Participate in a weekly on-call rotation for our Kubernetes clusters.",
      [U("Participate in a weekly on-call rotation for our Kubernetes clusters.", "responsibility", False,
         tech=[K8S])]),
    C("m11g21-a05", "on_call", "You will be on call for AWS outages twice a month.",
      [U("You will be on call for AWS outages twice a month.", "responsibility", False, tech=[AWS])]),
    C("m11g21-a06", "on_call",
      "Requirements:\n- Experience with PostgreSQL.\n- Respond to PostgreSQL incidents within 30 minutes.",
      [U("Experience with PostgreSQL.", "qualification", True, R, [PG], section="required"),
       U("Respond to PostgreSQL incidents within 30 minutes.", "responsibility", False, tech=[PG],
         section="responsibility", note="duty bullet under a requirements heading; 'respond' is not a listed duty verb")]),
    C("m11g21-a07", "on_call", "Must be available for on-call shifts supporting our Redis infrastructure.",
      [U("Must be available for on-call shifts supporting our Redis infrastructure.", "responsibility", False,
         tech=[REDIS])]),
    # --- mandatory attendance / travel -------------------------------------------------------------
    C("m11g21-a08", "attendance_travel", "Attendance at the quarterly Kubernetes summit in Berlin is mandatory.",
      [U("Attendance at the quarterly Kubernetes summit in Berlin is mandatory.", "team_practice", False,
         tech=[K8S])]),
    C("m11g21-a09", "attendance_travel", "Travel to client sites to install our Docker appliances is required.",
      [U("Travel to client sites to install our Docker appliances is required.", "responsibility", False,
         tech=[DOCKER])]),
    # --- required to perform vs required to know (near-neighbours) ------------------------------------
    C("m11g21-a10a", "perform_vs_know", "You are required to know SQL.",
      [U("You are required to know SQL.", "qualification", True, R, [SQL])], pair="A1"),
    C("m11g21-a10b", "perform_vs_know", "You are required to deploy changes to AWS every Friday.",
      [U("You are required to deploy changes to AWS every Friday.", "responsibility", False, tech=[AWS])],
      pair="A1"),
    C("m11g21-a11a", "perform_vs_know", "Strong Kotlin skills are required.",
      [U("Strong Kotlin skills are required.", "qualification", True, R, [KOTLIN])], pair="A2"),
    C("m11g21-a11b", "perform_vs_know", "Kotlin is required for all new Android modules.",
      [U("Kotlin is required for all new Android modules.", "team_practice", False, tech=[KOTLIN])], pair="A2"),
    # --- actual experience requirements -------------------------------------------------------------
    C("m11g21-a12", "experience_requirement",
      "Requirements:\n- At least 4 years of experience operating Kubernetes in production.",
      [U("At least 4 years of experience operating Kubernetes in production.", "qualification", True, R, [K8S],
         ["experience"], "required")]),
    C("m11g21-a13", "experience_requirement", "We need someone who has shipped FastAPI services at scale.",
      [U("We need someone who has shipped FastAPI services at scale.", "qualification", True, R, [FASTAPI])]),
    C("m11g21-a14", "experience_requirement", "Hands-on CUDA programming experience is a must.",
      [U("Hands-on CUDA programming experience is a must.", "qualification", True, R, [CUDA])]),
    # --- U.S. / US ------------------------------------------------------------------------------------
    C("m11g21-a15", "us_capitalization", "US citizenship is required for this role.",
      [U("US citizenship is required for this role.", "qualification", True, R, nt=["legal"])]),
    C("m11g21-a16", "us_capitalization", "Requirements:\n- Must be eligible to work in the U.S.",
      [U("Must be eligible to work in the U.S.", "qualification", True, R, nt=["legal"], section="required")]),
    C("m11g21-a17", "us_capitalization", "Join us to build TypeScript tooling for developers.",
      [U("Join us to build TypeScript tooling for developers.", "company", False, tech=[TS])]),
    # --- negated requirements and preferences ----------------------------------------------------------
    C("m11g21-a18", "negation", "Kubernetes knowledge is not necessary.",
      [U("Kubernetes knowledge is not necessary.", "negation", False, tech=[K8S])]),
    C("m11g21-a19", "negation", "A degree is not required; strong Python skills are.",
      [U("A degree is not required; strong Python skills are.", "qualification", True, R, [PY],
         note="negated degree + required Python in one sentence")]),
    C("m11g21-a20", "negation", "Requirements:\n- TypeScript is preferred but not essential.",
      [U("TypeScript is preferred but not essential.", "qualification", True, P, [TS], section="required")]),
    C("m11g21-a21", "negation", "Even if not required, PyTorch experience is a plus.",
      [U("Even if not required, PyTorch experience is a plus.", "qualification", True, P, [TORCH])]),
    # --- compound qualifications --------------------------------------------------------------------------
    C("m11g21-a22", "compound", "Requirements:\n- Python and either AWS or Docker experience.",
      [U("Python and either AWS or Docker experience.", "qualification", True, R, [PY, AWS, DOCKER],
         section="required", ambiguous=True, note="compound AND/OR (G17 containment territory)")]),
    C("m11g21-a23", "compound", "Requirements:\n- Experience with Java or Kotlin is required.",
      [U("Experience with Java or Kotlin is required.", "qualification", True, R, [JAVA, KOTLIN],
         section="required")]),
    # --- bare technical lists ------------------------------------------------------------------------------
    C("m11g21-a24", "bare_list", "Requirements:\n- Rust\n- Redis\n- Docker",
      [U("Rust", "qualification", True, R, [RUST], section="required"),
       U("Redis", "qualification", True, R, [REDIS], section="required"),
       U("Docker", "qualification", True, R, [DOCKER], section="required")]),
    C("m11g21-a25", "bare_list", "Nice to have:\n- PyTorch, CUDA",
      [U("PyTorch, CUDA", "qualification", True, P, [TORCH, CUDA], section="preferred")]),
    C("m11g21-a26", "bare_list", "Python, SQL and Docker",
      [U("Python, SQL and Docker", "qualification", True, R, [PY, SQL, DOCKER],
         note="unsectioned bare list -- v13 default REQUIRED kept")]),
    # --- technical terms in company descriptions --------------------------------------------------------------
    C("m11g21-a27", "company_description", "Founded in 2012, Lumen Labs runs its analytics on Python and PostgreSQL.",
      [U("Founded in 2012, Lumen Labs runs its analytics on Python and PostgreSQL.", "company", False,
         tech=[PY, PG])]),
    C("m11g21-a28", "company_description", "Every team here ships TypeScript and React daily.",
      [U("Every team here ships TypeScript and React daily.", "company", False, tech=[TS, REACT])]),
    C("m11g21-a29", "company_description", "Our customers rely on our Kubernetes operator.",
      [U("Our customers rely on our Kubernetes operator.", "company", False, tech=[K8S])]),
    C("m11g21-a30", "company_description",
      "About the company:\nWe are a fintech startup. Our backend is written in Golang.\n\n"
      "Requirements:\n- Professional Golang experience.",
      [U("We are a fintech startup.", "company", False, section="company"),
       U("Our backend is written in Golang.", "company", False, tech=[GO], section="company"),
       U("Professional Golang experience.", "qualification", True, R, [GO], section="required")]),
    # --- mixed qualification / responsibility paragraphs -----------------------------------------------------------
    C("m11g21-a31", "mixed_paragraph",
      "In this role you will build pipelines in Python. You should have 3+ years of SQL experience. "
      "Our office is in Austin.",
      [U("In this role you will build pipelines in Python.", "responsibility", False, tech=[PY]),
       U("You should have 3+ years of SQL experience.", "qualification", True, R, [SQL], ["experience"]),
       U("Our office is in Austin.", "company", False)]),
    C("m11g21-a32", "mixed_paragraph",
      "Responsibilities:\n- Build React dashboards; solid React experience is essential.\n"
      "- Mentor two junior engineers.",
      [U("Build React dashboards; solid React experience is essential.", "qualification", True, R, [REACT],
         section="responsibility"),
       U("Mentor two junior engineers.", "responsibility", False, section="responsibility")]),
    C("m11g21-a33", "mixed_paragraph",
      "Requirements:\n- Experience with Docker; you will also maintain our Kubernetes cluster.",
      [U("Experience with Docker; you will also maintain our Kubernetes cluster.", "qualification", True, R,
         [DOCKER, K8S], section="required",
         note="qualification clause + duty clause; v14 keeps the whole claim (no clause scoping)")]),
]


def main() -> None:
    _validate(CONTROLS)
    doc = {
        "schema_version": 1, "milestone": "M11-G21", "split": "fresh_adversarial",
        "provenance": "newly authored synthetic controls; no real posting text or employer",
        "authorship_disclosure": ("Written by the same author as G20 and the G21 implementation, after B1NR's design "
                                  "was known; targeted adversarial probes, NOT independent external validation."),
        "label_timing": "gold labels written and frozen BEFORE parser v14 or the v13-v14 comparison ran on this text",
        "gold_rules": "identical to evaluation/m11g20/admission_controls_dev.json gold_rules",
        "controls": CONTROLS,
    }
    payload = (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        if OUT.read_bytes() != payload:
            raise SystemExit(f"{OUT} is frozen and its content would change; refusing to overwrite")
        print("unchanged")
        return
    OUT.write_bytes(payload)
    FREEZE.write_bytes((json.dumps({
        "frozen_file": OUT.relative_to(REPO_ROOT).as_posix(), "sha256": gi.sha256(payload),
        "sha256_lf_normalized": gi.sha256(gi.canonical_bytes(payload)), "length_bytes": len(payload),
        "canonical_contract": "crlf-to-lf/v1",
        "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Frozen BEFORE parser v14 or the v13-vs-v14 comparison ran on these controls. NOT registered in "
                "the canonical manifest (pending authorization).",
    }, indent=2) + "\n").encode("utf-8"))
    print(f"wrote {len(CONTROLS)} controls / {sum(len(c['units']) for c in CONTROLS)} units; sha256={gi.sha256(payload)}")


if __name__ == "__main__":
    main()
