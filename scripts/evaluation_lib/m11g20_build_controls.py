"""Milestone 11-G20 -- frozen false-qualification-admission controls (builder).

    python scripts/evaluation_lib/m11g20_build_controls.py

Writes two SEPARATE synthetic control sets and one G14-portable freeze
record per file:

* `evaluation/m11g20/admission_controls_dev.json`      -- development
  controls; the ONLY set candidate policies were designed against.
* `evaluation/m11g20/admission_controls_holdout.json`  -- held-out
  synthetic controls; evaluated once, after policy design was finished.

Refuses to overwrite an existing frozen file whose content would change.

Provenance / honesty
--------------------
Every control is SELF-AUTHORED synthetic text (no real posting text, no
employer name). The author had already read the v13 parser source before
writing them, so these are NOT blind or independently validated
controls: they are targeted probes plus near-neighbor pairs. "Held-out"
means only "not used while designing the G20 policies", never
"independent". Gold labels were written, and both files frozen, BEFORE
the production parser was run on any of this text.

Gold, per annotated unit (one sentence / list item / mixed clause):
* `span`       exact, unique substring of the control text.
* `kind`       qualification | responsibility | company | product |
               benefits | process | tech_discussion | learning |
               team_practice | stack | negation.
* `qual`       is this unit a CANDIDATE QUALIFICATION (something the
               applicant is expected to have)?  A unit that mixes a duty
               with an explicit qualification clause is a qualification.
* `nec`        required | preferred | unknown (qualifications only).
               Rules: an explicit marker in the unit wins ("required",
               "must", "essential" -> required; "preferred", "a plus",
               "bonus", "ideally", "would be great", "helpful",
               "beneficial", "an advantage", "appreciated" -> preferred);
               a negated required marker with an appreciative tail ->
               preferred; otherwise the governing heading's meaning
               (requirements / candidate-profile headings -> required,
               nice-to-have headings -> preferred); an unsectioned
               candidate-attribute sentence ("You have...", "You should
               have...", "Candidates must...") -> required.
* `tech`       technologies GENUINELY named in the unit, as production
               concept ids (registered ids, or `unresolved:<slug>` via the
               production `unresolved_concept_id`). For qualification
               units these are the expected technical rows.
* `nt`         ACCEPTABLE non-technical row categories for the unit
               (education / experience / legal / leadership / soft_skill).
* `section`    the TRUE governing context of the unit: required |
               preferred | responsibility | company | benefits | process |
               learning | stack | none (no heading governs it).
* `ambiguous`  genuinely ambiguous qualification language: declining is
               acceptable and the unit is excluded from precision/recall
               denominators (reported separately).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import gold_integrity as gi  # noqa: E402
from gitscore.concepts.registry import default_registry  # noqa: E402

OUT_DIR = REPO_ROOT / "evaluation" / "m11g20"
SETS = {
    "dev": (OUT_DIR / "admission_controls_dev.json", OUT_DIR / "controls_dev_hash_freeze.json"),
    "holdout": (OUT_DIR / "admission_controls_holdout.json", OUT_DIR / "controls_holdout_hash_freeze.json"),
}

KINDS = {"qualification", "responsibility", "company", "product", "benefits", "process", "tech_discussion",
         "learning", "team_practice", "stack", "negation"}
SECTIONS = {"required", "preferred", "responsibility", "company", "benefits", "process", "learning", "stack", "none"}
NECESSITIES = {"required", "preferred", "unknown"}
NT = {"education", "experience", "legal", "leadership", "soft_skill"}

PY, JS, TS, JAVA = "language.python", "language.javascript", "language.typescript", "language.java"
CPP, GO, RUST, RUBY, SQL = "language.cpp", "language.go", "language.rust", "language.ruby", "language.sql"
SWIFT, KOTLIN, SHELL = "language.swift", "language.kotlin", "language.shell"
PG, REDIS, TORCH, TF = "database.postgresql", "database.redis", "ml.framework.pytorch", "ml.framework.tensorflow"
REACT, RN, NEXT, FASTAPI = "framework.react", "framework.react_native", "framework.nextjs", "framework.fastapi"
DOCKER, K8S, AWS, CUDA = "infra.docker", "infra.kubernetes", "cloud.aws", "platform.cuda"


def U(span, kind, qual, nec=None, tech=(), nt=(), section="none", ambiguous=False, note=""):  # noqa: N802
    return {"span": span, "kind": kind, "qual": qual, "nec": nec, "tech": list(tech), "nt": list(nt),
            "section": section, "ambiguous": ambiguous, "note": note}


def C(cid, family, text, units, pair=None, phase2_case=None):  # noqa: N802
    return {"id": cid, "family": family, "pair": pair, "phase2_case": phase2_case, "text": text, "units": units}


R, P = "required", "preferred"

DEV = [
    # --- company / product narrative --------------------------------------------------------
    C("m11g20-d001", "company_description",
      "About us: our engineers ship features daily with React and TypeScript.",
      [U("About us: our engineers ship features daily with React and TypeScript.", "company", False,
         tech=[REACT, TS], section="company", note="inline 'About us:' prefix")], phase2_case=1),
    C("m11g20-d002", "company_description", "We use Kafka, Python and Snowflake to power analytics for retailers.",
      [U("We use Kafka, Python and Snowflake to power analytics for retailers.", "company", False,
         tech=["unresolved:kafka", PY, "unresolved:snowflake"])], phase2_case=1),
    C("m11g20-d003", "product_description",
      "Our mobile app is written in Swift and Kotlin and serves two million riders.",
      [U("Our mobile app is written in Swift and Kotlin and serves two million riders.", "product", False,
         tech=[SWIFT, KOTLIN])]),
    C("m11g20-d052", "company_description",
      "About the company:\nWe build observability tools in Golang and Rust.",
      [U("We build observability tools in Golang and Rust.", "company", False, tech=[GO, RUST],
         section="company")]),
    # --- responsibilities -------------------------------------------------------------------
    C("m11g20-d004", "responsibility_unsectioned", "You will build REST APIs in Python and deploy them to AWS.",
      [U("You will build REST APIs in Python and deploy them to AWS.", "responsibility", False, tech=[PY, AWS])],
      phase2_case=2),
    C("m11g20-d005", "mixed_sections",
      "Responsibilities:\n- Design data pipelines in Python and SQL.\n- Maintain our PostgreSQL clusters.\n\n"
      "Requirements:\n- 3+ years of experience with Python.\n- Strong SQL skills.",
      [U("Design data pipelines in Python and SQL.", "responsibility", False, tech=[PY, SQL], section="responsibility"),
       U("Maintain our PostgreSQL clusters.", "responsibility", False, tech=[PG], section="responsibility"),
       U("3+ years of experience with Python.", "qualification", True, R, [PY], ["experience"], "required"),
       U("Strong SQL skills.", "qualification", True, R, [SQL], section="required")]),
    C("m11g20-d006", "responsibility_local_marker",
      "What you'll do:\n- You will be required to deploy services to AWS and Kubernetes.\n- Participate in code reviews.",
      [U("You will be required to deploy services to AWS and Kubernetes.", "responsibility", False, tech=[AWS, K8S],
         section="responsibility", note="duty sentence carrying a local 'required' marker"),
       U("Participate in code reviews.", "responsibility", False, section="responsibility")], phase2_case=6),
    C("m11g20-d039", "misleading_heading",
      "Role requirements:\n- Design and ship APIs in Golang.\n- Own the on-call rotation for our Redis clusters.",
      [U("Design and ship APIs in Golang.", "responsibility", False, tech=[GO], section="responsibility",
         note="duties listed under a heading named 'requirements'"),
       U("Own the on-call rotation for our Redis clusters.", "responsibility", False, tech=[REDIS],
         section="responsibility")], phase2_case=6),
    C("m11g20-d040", "misleading_heading",
      "Key Requirements:\n- Lead the migration from Java to Kotlin.\n- Expert knowledge of Kotlin.",
      [U("Lead the migration from Java to Kotlin.", "responsibility", False, tech=[JAVA, KOTLIN],
         section="responsibility"),
       U("Expert knowledge of Kotlin.", "qualification", True, R, [KOTLIN], section="required")], phase2_case=6),
    C("m11g20-d053", "product_description",
      "Responsibilities:\n- Our platform handles payments for 4,000 merchants using Java and PostgreSQL.",
      [U("Our platform handles payments for 4,000 merchants using Java and PostgreSQL.", "product", False,
         tech=[JAVA, PG], section="responsibility")]),
    C("m11g20-d024", "mixed_responsibility_qualification",
      "Responsibilities:\n- Maintain our Python services; strong Python experience is required.",
      [U("Maintain our Python services; strong Python experience is required.", "qualification", True, R, [PY],
         section="responsibility", note="duty clause + explicit qualification clause")]),
    # --- near-neighbor pairs ----------------------------------------------------------------
    C("m11g20-d007a", "near_neighbor", "Candidates must be proficient in TypeScript.",
      [U("Candidates must be proficient in TypeScript.", "qualification", True, R, [TS])], pair="P01"),
    C("m11g20-d007b", "near_neighbor", "All services must be written in TypeScript.",
      [U("All services must be written in TypeScript.", "team_practice", False, tech=[TS])], pair="P01"),
    C("m11g20-d008a", "near_neighbor", "Experience with Python is required.",
      [U("Experience with Python is required.", "qualification", True, R, [PY])], pair="P02"),
    C("m11g20-d008b", "near_neighbor", "Our team uses Python.",
      [U("Our team uses Python.", "company", False, tech=[PY])], pair="P02"),
    C("m11g20-d009a", "near_neighbor", "Knowledge of Docker is a plus.",
      [U("Knowledge of Docker is a plus.", "qualification", True, P, [DOCKER])], pair="P03"),
    C("m11g20-d009b", "near_neighbor", "We deploy everything with Docker.",
      [U("We deploy everything with Docker.", "company", False, tech=[DOCKER])], pair="P03"),
    C("m11g20-d010a", "near_neighbor", "You have hands-on experience with Kubernetes.",
      [U("You have hands-on experience with Kubernetes.", "qualification", True, R, [K8S])], pair="P04"),
    C("m11g20-d010b", "near_neighbor", "You will get hands-on experience with Kubernetes.",
      [U("You will get hands-on experience with Kubernetes.", "learning", False, tech=[K8S])], pair="P04"),
    C("m11g20-d011a", "near_neighbor", "Proficiency in Rust is essential.",
      [U("Proficiency in Rust is essential.", "qualification", True, R, [RUST])], pair="P05"),
    C("m11g20-d011b", "near_neighbor", "Rust is gaining popularity for systems programming.",
      [U("Rust is gaining popularity for systems programming.", "tech_discussion", False, tech=[RUST])], pair="P05"),
    C("m11g20-d012a", "near_neighbor", "Familiarity with PyTorch or TensorFlow is preferred.",
      [U("Familiarity with PyTorch or TensorFlow is preferred.", "qualification", True, P, [TORCH, TF])], pair="P06"),
    C("m11g20-d012b", "near_neighbor", "Our research team trains models in PyTorch or TensorFlow.",
      [U("Our research team trains models in PyTorch or TensorFlow.", "company", False, tech=[TORCH, TF])],
      pair="P06"),
    C("m11g20-d013a", "near_neighbor", "Requirements:\n- Bachelor's degree in Computer Science or a related field.",
      [U("Bachelor's degree in Computer Science or a related field.", "qualification", True, R, nt=["education"],
         section="required")], pair="P07"),
    C("m11g20-d013b", "near_neighbor", "Many of our engineers hold a degree in physics.",
      [U("Many of our engineers hold a degree in physics.", "company", False)], pair="P07"),
    C("m11g20-d014a", "near_neighbor", "Strong communication skills are required.",
      [U("Strong communication skills are required.", "qualification", True, R, nt=["soft_skill"])], pair="P08"),
    C("m11g20-d014b", "near_neighbor", "We value open communication and collaboration across teams.",
      [U("We value open communication and collaboration across teams.", "company", False)], pair="P08"),
    C("m11g20-d015a", "near_neighbor", "Requirements:\n- Experience mentoring junior engineers.",
      [U("Experience mentoring junior engineers.", "qualification", True, R, nt=["leadership"], section="required")],
      pair="P09"),
    C("m11g20-d015b", "near_neighbor", "You'll be mentored by senior engineers from day one.",
      [U("You'll be mentored by senior engineers from day one.", "learning", False)], pair="P09"),
    C("m11g20-d056a", "near_neighbor", "You are fluent in SQL.",
      [U("You are fluent in SQL.", "qualification", True, R, [SQL])], pair="P10"),
    C("m11g20-d056b", "near_neighbor", "Our analysts are fluent in SQL.",
      [U("Our analysts are fluent in SQL.", "company", False, tech=[SQL])], pair="P10"),
    C("m11g20-d057a", "near_neighbor", "Experience with React Native is a must.",
      [U("Experience with React Native is a must.", "qualification", True, R, [RN])], pair="P11"),
    C("m11g20-d057b", "near_neighbor", "React Native powers our customer app.",
      [U("React Native powers our customer app.", "product", False, tech=[RN])], pair="P11"),
    C("m11g20-d058a", "near_neighbor", "Requirements:\n- Hands-on AWS experience.",
      [U("Hands-on AWS experience.", "qualification", True, R, [AWS], section="required")], pair="P12"),
    C("m11g20-d058b", "near_neighbor", "Hands-on AWS training is provided to all new hires.",
      [U("Hands-on AWS training is provided to all new hires.", "benefits", False, tech=[AWS])], pair="P12"),
    # --- generic words / fragments as technical concepts --------------------------------------
    C("m11g20-d016", "generic_word", "Requirements:\n- Ability to react quickly to production incidents.",
      [U("Ability to react quickly to production incidents.", "qualification", True, R, section="required",
         note="'react' is a verb here")], phase2_case=3),
    C("m11g20-d017", "generic_word", "Requirements:\n- Able to express complex ideas clearly to non-technical audiences.",
      [U("Able to express complex ideas clearly to non-technical audiences.", "qualification", True, R,
         nt=["soft_skill"], section="required", note="'express' is a verb here")], phase2_case=3),
    C("m11g20-d018", "generic_word", "Requirements:\n- Experience with SQL, attention to detail, and curiosity.",
      [U("Experience with SQL, attention to detail, and curiosity.", "qualification", True, R, [SQL],
         section="required")], phase2_case=3),
    C("m11g20-d019", "generic_word", "Requirements:\n- Strong Java, communication, and problem-solving skills.",
      [U("Strong Java, communication, and problem-solving skills.", "qualification", True, R, [JAVA],
         nt=["soft_skill"], section="required")], phase2_case=3),
    C("m11g20-d022", "generic_word", "Requirements:\n- A swift learner who adapts to new tools.",
      [U("A swift learner who adapts to new tools.", "qualification", True, R, section="required",
         note="'swift' is an adjective here")], phase2_case=3),
    C("m11g20-d023", "cross_sentence_fragment",
      "Requirements:\n- Hands-on PostgreSQL experience. Alternatively, strong Redis experience will be considered.",
      [U("Hands-on PostgreSQL experience.", "qualification", True, R, [PG], section="required"),
       U("Alternatively, strong Redis experience will be considered.", "qualification", True, "unknown", [REDIS],
         section="required", ambiguous=True, note="cross-sentence alternative")], phase2_case=3),
    # --- legitimate technical terms ---------------------------------------------------------
    C("m11g20-d020", "legitimate_technical", "Requirements:\n- Proficiency in Python, Git, and Linux.",
      [U("Proficiency in Python, Git, and Linux.", "qualification", True, R, [PY, "unresolved:git", "unresolved:linux"],
         section="required")]),
    C("m11g20-d021", "legitimate_technical", "Preferred:\n- Experience with Excel, Tableau, and SQL.",
      [U("Experience with Excel, Tableau, and SQL.", "qualification", True, P,
         ["unresolved:excel", "unresolved:tableau", SQL], section="preferred")]),
    C("m11g20-d041", "inherited_list",
      "Required skills:\n- Python\n- SQL\n- Docker\n\nPreferred skills:\n- Kubernetes\n- AWS",
      [U("Python", "qualification", True, R, [PY], section="required"),
       U("SQL", "qualification", True, R, [SQL], section="required"),
       U("Docker", "qualification", True, R, [DOCKER], section="required"),
       U("Kubernetes", "qualification", True, P, [K8S], section="preferred"),
       U("AWS", "qualification", True, P, [AWS], section="preferred")], phase2_case=8),
    C("m11g20-d042", "inherited_list",
      "Requirements:\n- Experience building data pipelines with\n  Python and PostgreSQL.\n- Familiarity with Docker.",
      [U("Experience building data pipelines with\n  Python and PostgreSQL.", "qualification", True, R, [PY, PG],
         section="required"),
       U("Familiarity with Docker.", "qualification", True, R, [DOCKER], section="required")]),
    C("m11g20-d043", "inherited_list",
      "Qualifications:\n1. Experience with React.\n2. Experience with Next.js.\nBonus:\n1. Experience with React Native.",
      [U("Experience with React.", "qualification", True, R, [REACT], section="required"),
       U("Experience with Next.js.", "qualification", True, R, [NEXT], section="required"),
       U("Experience with React Native.", "qualification", True, P, [RN], section="preferred")], phase2_case=9),
    C("m11g20-d054", "non_technical_qualification",
      "Requirements:\n- 5+ years of software development experience.\n- Master's degree preferred.",
      [U("5+ years of software development experience.", "qualification", True, R, nt=["experience"],
         section="required"),
       U("Master's degree preferred.", "qualification", True, P, nt=["education"], section="required")]),
    C("m11g20-d055", "non_technical_qualification", "Requirements:\n- Must be legally authorized to work in Canada.",
      [U("Must be legally authorized to work in Canada.", "qualification", True, R, nt=["legal"], section="required")]),
    # --- prose / embedded qualifications ------------------------------------------------------
    C("m11g20-d025", "embedded_in_prose",
      "We are a logistics startup in Montreal. Candidates must have strong experience with Python and PostgreSQL. "
      "We offer flexible hours and a learning budget.",
      [U("We are a logistics startup in Montreal.", "company", False),
       U("Candidates must have strong experience with Python and PostgreSQL.", "qualification", True, R, [PY, PG]),
       U("We offer flexible hours and a learning budget.", "benefits", False)], phase2_case=7),
    C("m11g20-d026", "prose_qualification",
      "We're hiring a backend developer. You should have solid experience with Golang and Redis. "
      "Knowledge of Kubernetes is a plus.",
      [U("We're hiring a backend developer.", "company", False),
       U("You should have solid experience with Golang and Redis.", "qualification", True, R, [GO, REDIS]),
       U("Knowledge of Kubernetes is a plus.", "qualification", True, P, [K8S])], phase2_case=10),
    C("m11g20-d027", "prose_qualification",
      "Acme Robotics is hiring an embedded engineer. We're looking for someone with deep C++ experience.\n\n"
      "Responsibilities:\n- Write firmware for motor controllers.",
      [U("Acme Robotics is hiring an embedded engineer.", "company", False),
       U("We're looking for someone with deep C++ experience.", "qualification", True, R, [CPP],
         note="qualification in a preamble before the first heading"),
       U("Write firmware for motor controllers.", "responsibility", False, section="responsibility")],
      phase2_case=10),
    # --- unconventional / candidate-profile headings ------------------------------------------
    C("m11g20-d028", "unconventional_heading",
      "About you:\n- 4+ years of experience with Java.\n- Experience with Kafka and Kubernetes.",
      [U("4+ years of experience with Java.", "qualification", True, R, [JAVA], ["experience"], "required"),
       U("Experience with Kafka and Kubernetes.", "qualification", True, R, ["unresolved:kafka", K8S],
         section="required")], phase2_case=8),
    C("m11g20-d029", "unconventional_heading",
      "What you bring:\n- Production experience with TypeScript and React.\n- A degree in a technical field.",
      [U("Production experience with TypeScript and React.", "qualification", True, R, [TS, REACT],
         section="required"),
       U("A degree in a technical field.", "qualification", True, R, nt=["education"], section="required")],
      phase2_case=8),
    C("m11g20-d030", "unconventional_heading",
      "Must-haves:\n- Experience with FastAPI.\n- Experience with PostgreSQL.\n\nNice-to-haves:\n- Experience with Redis.",
      [U("Experience with FastAPI.", "qualification", True, R, [FASTAPI], section="required"),
       U("Experience with PostgreSQL.", "qualification", True, R, [PG], section="required"),
       U("Experience with Redis.", "qualification", True, P, [REDIS], section="preferred")], phase2_case=8),
    C("m11g20-d031", "stack_listing", "Our stack:\n- Python\n- PostgreSQL\n- Kubernetes",
      [U("Python", "stack", False, tech=[PY], section="stack"),
       U("PostgreSQL", "stack", False, tech=[PG], section="stack"),
       U("Kubernetes", "stack", False, tech=[K8S], section="stack")]),
    C("m11g20-d032", "section_leak",
      "Requirements:\n- Experience with AWS.\n\nWe are a remote-first team that ships with Docker and Kubernetes every day.",
      [U("Experience with AWS.", "qualification", True, R, [AWS], section="required"),
       U("We are a remote-first team that ships with Docker and Kubernetes every day.", "company", False,
         tech=[DOCKER, K8S], note="un-headed paragraph after a list section")], phase2_case=5),
    # --- benefits / process / learning / tech discussion --------------------------------------
    C("m11g20-d033", "benefits", "We provide a yearly budget for AWS certification courses.",
      [U("We provide a yearly budget for AWS certification courses.", "benefits", False, tech=[AWS])]),
    C("m11g20-d034", "hiring_process",
      "Our interview process includes a take-home exercise in Python or JavaScript.",
      [U("Our interview process includes a take-home exercise in Python or JavaScript.", "process", False,
         tech=[PY, JS])]),
    C("m11g20-d035", "hiring_process", "How to apply:\n- Send a link to a GitHub project written in Rust or C++.",
      [U("Send a link to a GitHub project written in Rust or C++.", "process", False, tech=[RUST, CPP],
         section="process")]),
    C("m11g20-d036", "hiring_process",
      "Hiring process:\n1. A 30-minute call with a recruiter.\n2. A live coding session in Python.",
      [U("A 30-minute call with a recruiter.", "process", False, section="process"),
       U("A live coding session in Python.", "process", False, tech=[PY], section="process")]),
    C("m11g20-d037", "tech_discussion_in_qualifications",
      "Requirements:\n- Experience with machine learning in production.\n"
      "- PyTorch has become the industry standard for research.",
      [U("Experience with machine learning in production.", "qualification", True, R, section="required"),
       U("PyTorch has become the industry standard for research.", "tech_discussion", False, tech=[TORCH],
         section="required")], phase2_case=5),
    C("m11g20-d038", "narrative_in_qualifications",
      "Qualifications:\n- Experience with Docker.\n- Our team has grown to 40 engineers across Python and Golang services.",
      [U("Experience with Docker.", "qualification", True, R, [DOCKER], section="required"),
       U("Our team has grown to 40 engineers across Python and Golang services.", "company", False,
         tech=[PY, GO], section="required")], phase2_case=5),
    C("m11g20-d050", "learning", "What you'll learn:\n- How to operate Kubernetes clusters at scale.",
      [U("How to operate Kubernetes clusters at scale.", "learning", False, tech=[K8S], section="learning")]),
    C("m11g20-d051", "learning", "This role offers the chance to learn Rust from experienced engineers.",
      [U("This role offers the chance to learn Rust from experienced engineers.", "learning", False, tech=[RUST])]),
    C("m11g20-d060", "tech_discussion", "Kubernetes adoption has grown rapidly across the industry.",
      [U("Kubernetes adoption has grown rapidly across the industry.", "tech_discussion", False, tech=[K8S])]),
    # --- necessity --------------------------------------------------------------------------
    C("m11g20-d044", "necessity",
      "Requirements:\n- Experience with Python.\n- Familiarity with Rust would be great.",
      [U("Experience with Python.", "qualification", True, R, [PY], section="required"),
       U("Familiarity with Rust would be great.", "qualification", True, P, [RUST], section="required")]),
    C("m11g20-d045", "necessity", "Requirements:\n- Exposure to CUDA is helpful but not essential.",
      [U("Exposure to CUDA is helpful but not essential.", "qualification", True, P, [CUDA], section="required",
         note="negated required marker")]),
    C("m11g20-d046", "necessity", "Requirements:\n- Experience with Redis is not required, but appreciated.",
      [U("Experience with Redis is not required, but appreciated.", "qualification", True, P, [REDIS],
         section="required", note="negated required marker")]),
    C("m11g20-d047", "negation", "No prior experience with Kubernetes is necessary.",
      [U("No prior experience with Kubernetes is necessary.", "negation", False, tech=[K8S])]),
    # --- ambiguous --------------------------------------------------------------------------
    C("m11g20-d048", "ambiguous", "Requirements:\n- Python, ideally with some exposure to FastAPI.",
      [U("Python, ideally with some exposure to FastAPI.", "qualification", True, "unknown", [PY, FASTAPI],
         section="required", ambiguous=True, note="two necessities in one clause")]),
    C("m11g20-d049", "ambiguous", "It would help if you have touched Terraform before.",
      [U("It would help if you have touched Terraform before.", "qualification", True, P, ["unresolved:terraform"],
         ambiguous=True)]),
]

HOLDOUT = [
    C("m11g20-h001", "company_description", "At Northwind we rely on Python and Airflow for every data workflow.",
      [U("At Northwind we rely on Python and Airflow for every data workflow.", "company", False,
         tech=[PY, "unresolved:airflow"])]),
    C("m11g20-h002", "responsibility_unsectioned", "You'll own the migration of our services from Java to Kotlin.",
      [U("You'll own the migration of our services from Java to Kotlin.", "responsibility", False,
         tech=[JAVA, KOTLIN])]),
    C("m11g20-h003", "responsibility_local_marker",
      "Day-to-day:\n- You must be on call one week per month for our AWS infrastructure.",
      [U("You must be on call one week per month for our AWS infrastructure.", "responsibility", False, tech=[AWS],
         section="responsibility")]),
    C("m11g20-h004a", "near_neighbor", "Strong knowledge of PostgreSQL is required.",
      [U("Strong knowledge of PostgreSQL is required.", "qualification", True, R, [PG])], pair="Q1"),
    C("m11g20-h004b", "near_neighbor", "Our data lives in PostgreSQL and Redis.",
      [U("Our data lives in PostgreSQL and Redis.", "company", False, tech=[PG, REDIS])], pair="Q1"),
    C("m11g20-h005a", "near_neighbor", "Experience with Docker would be a bonus.",
      [U("Experience with Docker would be a bonus.", "qualification", True, P, [DOCKER])], pair="Q2"),
    C("m11g20-h005b", "near_neighbor", "Docker images are rebuilt nightly by our CI pipeline.",
      [U("Docker images are rebuilt nightly by our CI pipeline.", "product", False, tech=[DOCKER])], pair="Q2"),
    C("m11g20-h006a", "near_neighbor", "You have shipped production code in TypeScript.",
      [U("You have shipped production code in TypeScript.", "qualification", True, R, [TS])], pair="Q3"),
    C("m11g20-h006b", "near_neighbor", "You will ship production code in TypeScript.",
      [U("You will ship production code in TypeScript.", "responsibility", False, tech=[TS])], pair="Q3"),
    C("m11g20-h007a", "near_neighbor", "Requirements:\n- Proficiency with TensorFlow.",
      [U("Proficiency with TensorFlow.", "qualification", True, R, [TF], section="required")], pair="Q4"),
    C("m11g20-h007b", "near_neighbor", "Requirements:\n- TensorFlow is used across all of our research teams.",
      [U("TensorFlow is used across all of our research teams.", "tech_discussion", False, tech=[TF],
         section="required")], pair="Q4"),
    C("m11g20-h008", "unconventional_heading",
      "About the role:\nYou will build ML pipelines.\n\nWhat we need from you:\n- Experience with PyTorch.\n"
      "- Experience with CUDA.",
      [U("You will build ML pipelines.", "responsibility", False, section="responsibility"),
       U("Experience with PyTorch.", "qualification", True, R, [TORCH], section="required"),
       U("Experience with CUDA.", "qualification", True, R, [CUDA], section="required")]),
    C("m11g20-h009", "unconventional_heading",
      "About You\n- Solid experience with Ruby.\n- Experience with PostgreSQL.",
      [U("Solid experience with Ruby.", "qualification", True, R, [RUBY], section="required"),
       U("Experience with PostgreSQL.", "qualification", True, R, [PG], section="required")]),
    C("m11g20-h010", "unconventional_heading",
      "Your profile:\n- Experience with C++ and CUDA.\n- A PhD in a quantitative field is a plus.",
      [U("Experience with C++ and CUDA.", "qualification", True, R, [CPP, CUDA], section="required"),
       U("A PhD in a quantitative field is a plus.", "qualification", True, P, nt=["education"],
         section="required")]),
    C("m11g20-h011", "generic_word", "Requirements:\n- Able to react calmly under pressure during outages.",
      [U("Able to react calmly under pressure during outages.", "qualification", True, R, section="required")]),
    C("m11g20-h012", "generic_word", "Nice to have:\n- Willingness to express opinions in design reviews.",
      [U("Willingness to express opinions in design reviews.", "qualification", True, P, section="preferred")]),
    C("m11g20-h013", "generic_word", "Requirements:\n- Experience with Python, creativity, and ownership.",
      [U("Experience with Python, creativity, and ownership.", "qualification", True, R, [PY], section="required")]),
    C("m11g20-h014", "legitimate_technical", "Requirements:\n- Experience with Python, Spark, and Airflow.",
      [U("Experience with Python, Spark, and Airflow.", "qualification", True, R,
         [PY, "unresolved:spark", "unresolved:airflow"], section="required")]),
    C("m11g20-h015", "legitimate_technical", "Nice to have:\n- Exposure to Rust, Zig, or Golang.",
      [U("Exposure to Rust, Zig, or Golang.", "qualification", True, P, [RUST, "unresolved:zig", GO],
         section="preferred")]),
    C("m11g20-h016", "benefits", "Every engineer receives a stipend for Kubernetes and AWS certifications.",
      [U("Every engineer receives a stipend for Kubernetes and AWS certifications.", "benefits", False,
         tech=[K8S, AWS])]),
    C("m11g20-h017", "hiring_process", "The technical interview includes a pairing session in Java or Python.",
      [U("The technical interview includes a pairing session in Java or Python.", "process", False,
         tech=[JAVA, PY])]),
    C("m11g20-h018", "hiring_process", "Shortlisted candidates complete a short SQL assessment.",
      [U("Shortlisted candidates complete a short SQL assessment.", "process", False, tech=[SQL])]),
    C("m11g20-h019", "tech_discussion_in_qualifications",
      "Requirements:\n- Experience with React.\n- React remains the most popular frontend library.",
      [U("Experience with React.", "qualification", True, R, [REACT], section="required"),
       U("React remains the most popular frontend library.", "tech_discussion", False, tech=[REACT],
         section="required")]),
    C("m11g20-h020", "negation", "Prior experience with Rust is not required.",
      [U("Prior experience with Rust is not required.", "negation", False, tech=[RUST])]),
    C("m11g20-h021", "necessity", "Qualifications:\n- Knowledge of Redis is beneficial.",
      [U("Knowledge of Redis is beneficial.", "qualification", True, P, [REDIS], section="required")]),
    C("m11g20-h022", "necessity", "Qualifications:\n- Some familiarity with Kotlin helps.",
      [U("Some familiarity with Kotlin helps.", "qualification", True, P, [KOTLIN], section="required")]),
    C("m11g20-h023", "embedded_in_prose",
      "We are building a payments platform. The successful candidate will have strong Java and SQL skills. "
      "Experience with Kafka is an advantage.",
      [U("We are building a payments platform.", "company", False),
       U("The successful candidate will have strong Java and SQL skills.", "qualification", True, R, [JAVA, SQL]),
       U("Experience with Kafka is an advantage.", "qualification", True, P, ["unresolved:kafka"])]),
    C("m11g20-h024", "learning", "New hires get to learn Terraform and AWS through guided projects.",
      [U("New hires get to learn Terraform and AWS through guided projects.", "learning", False,
         tech=["unresolved:terraform", AWS])]),
    C("m11g20-h025", "learning", "Senior engineers will mentor you through your first quarter.",
      [U("Senior engineers will mentor you through your first quarter.", "learning", False)]),
    C("m11g20-h026", "mixed_responsibility_qualification",
      "Responsibilities:\n- Build dashboards in React; prior React experience is essential.",
      [U("Build dashboards in React; prior React experience is essential.", "qualification", True, R, [REACT],
         section="responsibility")]),
    C("m11g20-h027", "section_leak",
      "Preferred:\n- Experience with FastAPI.\n\nOur engineering team ships to production with Docker multiple times a day.",
      [U("Experience with FastAPI.", "qualification", True, P, [FASTAPI], section="preferred"),
       U("Our engineering team ships to production with Docker multiple times a day.", "company", False,
         tech=[DOCKER])]),
    C("m11g20-h028", "inherited_list", "Must have:\n- Python\n- PyTorch\nNice to have:\n- CUDA",
      [U("Python", "qualification", True, R, [PY], section="required"),
       U("PyTorch", "qualification", True, R, [TORCH], section="required"),
       U("CUDA", "qualification", True, P, [CUDA], section="preferred")]),
    C("m11g20-h029", "inherited_list",
      "Requirements:\n- Hands-on experience deploying services on\n  AWS with Docker.",
      [U("Hands-on experience deploying services on\n  AWS with Docker.", "qualification", True, R, [AWS, DOCKER],
         section="required")]),
    C("m11g20-h030", "company_description", "We use Redis for caching and PostgreSQL for storage.",
      [U("We use Redis for caching and PostgreSQL for storage.", "company", False, tech=[REDIS, PG])]),
    C("m11g20-h031", "ambiguous", "Knowing a bit of Bash would not hurt.",
      [U("Knowing a bit of Bash would not hurt.", "qualification", True, P, [SHELL], ambiguous=True)]),
    C("m11g20-h032", "mixed_responsibility_qualification",
      "Strong Python is essential; our backend is built entirely in Python.",
      [U("Strong Python is essential; our backend is built entirely in Python.", "qualification", True, R, [PY])]),
]


def _validate(controls: list[dict]) -> None:
    registry = default_registry()
    ids = [c["id"] for c in controls]
    assert len(ids) == len(set(ids)), "duplicate control id"
    for c in controls:
        assert c["units"], c["id"]
        for u in c["units"]:
            assert c["text"].count(u["span"]) == 1, (c["id"], u["span"])
            assert u["kind"] in KINDS and u["section"] in SECTIONS, (c["id"], u)
            assert set(u["nt"]) <= NT, (c["id"], u)
            if u["qual"]:
                assert u["nec"] in NECESSITIES, (c["id"], u)
            else:
                assert u["nec"] is None and u["kind"] != "qualification", (c["id"], u)
            for t in u["tech"]:
                assert t.startswith("unresolved:") or registry.get(t) is not None, (c["id"], t)


def _payload(split: str, controls: list[dict]) -> bytes:
    doc = {
        "schema_version": 1,
        "milestone": "M11-G20",
        "split": split,
        "provenance": "self-authored synthetic controls; no real posting text or employer names",
        "authorship_disclosure": (
            "Written by the same author who read the v13 parser source; targeted probes and near-neighbor pairs, "
            "not blind or independently validated. 'holdout' means only: not used while designing G20 policies."
        ),
        "label_timing": "gold labels written and frozen BEFORE the production parser ran on any of this text",
        "gold_rules": __doc__.split("Gold, per annotated unit")[1].strip(),
        "controls": controls,
    }
    return (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for split, controls in (("dev", DEV), ("holdout", HOLDOUT)):
        _validate(controls)
        out_path, freeze_path = SETS[split]
        payload = _payload(split, controls)
        if out_path.exists():
            if out_path.read_bytes() != payload:
                raise SystemExit(f"{out_path} is frozen and its content would change; refusing to overwrite")
            print(f"{split}: unchanged ({len(controls)} controls)")
            continue
        out_path.write_bytes(payload)
        freeze = {
            "frozen_file": out_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": gi.sha256(payload),
            "sha256_lf_normalized": gi.sha256(gi.canonical_bytes(payload)),
            "length_bytes": len(payload),
            "canonical_contract": "crlf-to-lf/v1",
            "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": "Frozen BEFORE the production parser or any G20 policy simulation ran on these controls. "
                    "NOT registered in evaluation/integrity/canonical_hash_manifest.json (pending authorization).",
        }
        freeze_path.write_bytes((json.dumps(freeze, indent=2) + "\n").encode("utf-8"))
        units = sum(len(c["units"]) for c in controls)
        print(f"{split}: wrote {len(controls)} controls / {units} units; sha256={freeze['sha256']}")


if __name__ == "__main__":
    main()
