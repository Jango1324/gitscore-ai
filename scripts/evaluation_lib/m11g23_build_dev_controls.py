"""Milestone 11-G23 -- builds the DEV candidate-profile heading control set (research only).

    python scripts/evaluation_lib/m11g23_build_dev_controls.py

Writes `evaluation/m11g23/controls_dev.json`. Labels follow `evaluation/m11g23/labelling_guide.md` and were
written before any G23 candidate policy existed and before the parser ran on this text. The DEV author had read
the v15 parser source (see the authorship disclosure), so DEV is a design set, never independent validation.
All text is synthetic.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "evaluation" / "m11g23" / "controls_dev.json"

PY, GO, TS, JSL, RS, JAVA, KT = ("language.python", "language.go", "language.typescript", "language.javascript",
                                 "language.rust", "language.java", "language.kotlin")
SQL, PG, REDIS, DOCKER, K8S, AWS = ("language.sql", "database.postgresql", "database.redis", "infra.docker",
                                    "infra.kubernetes", "cloud.aws")
REACT, RN, FASTAPI, DJ_PT, TF, CPP = ("framework.react", "framework.react_native", "framework.fastapi",
                                      "ml.framework.pytorch", "ml.framework.tensorflow", "language.cpp")
PANDAS, SHELL, SWIFT, CSHARP, RUBY, CUDA = ("data.library.pandas", "language.shell", "language.swift",
                                            "language.csharp", "language.ruby", "platform.cuda")


def Q(span, tech=(), nec="required", nt=(), section="required", ambiguous=False, note=""):
    return {"span": span, "kind": "qualification", "qual": True, "nec": nec, "tech": list(tech), "nt": list(nt),
            "section": section, "ambiguous": ambiguous, "note": note}


def N(span, kind, section, tech=(), note=""):
    return {"span": span, "kind": kind, "qual": False, "nec": None, "tech": list(tech), "nt": [],
            "section": section, "ambiguous": False, "note": note}


def build(cid, family, parts, pair=None):
    """parts: ("h", line) heading line | ("b", unit) bullet | ("l", unit) plain line |
    ("p", [units]) prose paragraph (sentences joined by spaces) | ("blank",)."""
    lines, units = [], []
    for part in parts:
        tag = part[0]
        if tag == "h":
            lines.append(part[1])
        elif tag == "b":
            lines.append("- " + part[1]["span"])
            units.append(part[1])
        elif tag == "l":
            lines.append(part[1]["span"])
            units.append(part[1])
        elif tag == "p":
            lines.append(" ".join(u["span"] for u in part[1]))
            units.extend(part[1])
        elif tag == "blank":
            lines.append("")
    return {"id": f"m11g23-dev-{cid:03d}", "family": family, "pair": pair, "text": "\n".join(lines), "units": units}


C = []
# ---- A: genuine technical qualifications beneath candidate-profile headings ----------------------------------
C.append(build(1, "A", [("h", "About you:"),
                        ("b", Q("Strong experience building backend services in Python.", [PY])),
                        ("b", Q("Hands-on experience with PostgreSQL.", [PG]))]))
C.append(build(2, "A", [("h", "What you bring"),
                        ("b", Q("3+ years of professional Go development.", [GO], nt=["experience"])),
                        ("b", Q("Solid knowledge of Docker and Kubernetes.", [DOCKER, K8S]))]))
C.append(build(3, "A", [("h", "## Who you are"),
                        ("b", Q("Proficient in TypeScript and React.", [TS, REACT])),
                        ("b", Q("Comfortable writing SQL for analytics.", [SQL]))]))
C.append(build(4, "A", [("h", "WHAT WE'RE LOOKING FOR"),
                        ("b", Q("Deep experience with PyTorch model training.", [DJ_PT])),
                        ("b", Q("Working knowledge of CUDA.", [CUDA]))]))
# ---- B: conventional headings (no regression) ------------------------------------------------------------------
C.append(build(5, "B", [("h", "Requirements:"),
                        ("b", Q("Experience with Rust in production.", [RS])),
                        ("b", Q("Familiarity with Redis.", [REDIS]))]))
C.append(build(6, "B", [("h", "Qualifications"),
                        ("b", Q("Bachelor's degree in Computer Science or equivalent.", nt=["education"])),
                        ("b", Q("Experience with Java and Kotlin.", [JAVA, KT]))]))
C.append(build(7, "B", [("h", "**Required Skills**"),
                        ("b", Q("Expertise in C++ and modern build tooling.", [CPP])),
                        ("b", Q("Experience with AWS.", [AWS]))]))
# ---- C: responsibilities beneath "What you'll do" -------------------------------------------------------------
C.append(build(8, "C", [("h", "What you'll do:"),
                        ("b", N("Build and maintain REST APIs in Go.", "responsibility", "responsibility", [GO])),
                        ("b", N("Own the deployment pipeline on Kubernetes.", "responsibility", "responsibility", [K8S])),
                        ("h", "About you:"),
                        ("b", Q("Experience operating Go services in production.", [GO]))]))
C.append(build(9, "C", [("h", "## Your day-to-day"),
                        ("b", N("Design data pipelines with pandas.", "responsibility", "responsibility", [PANDAS])),
                        ("b", N("Review pull requests from teammates.", "responsibility", "responsibility"))]))
C.append(build(10, "C", [("h", "What You Will Do"),
                         ("b", N("Ship mobile features in Swift.", "responsibility", "responsibility", [SWIFT])),
                         ("h", "What you bring:"),
                         ("b", Q("Experience shipping iOS apps in Swift.", [SWIFT]))]))
# ---- D: employer descriptions beneath "About us" ---------------------------------------------------------------
C.append(build(11, "D", [("h", "About us:"),
                         ("p", [N("Acme builds logistics software.", "company", "company"),
                                N("Our platform runs on Python and AWS.", "company", "company", [PY, AWS])]),
                         ("h", "About you:"),
                         ("b", Q("Experience with Python web frameworks.", [PY]))]))
C.append(build(12, "D", [("h", "Who we are"),
                         ("p", [N("Northwind is a small team of engineers.", "company", "company"),
                                N("We have used Ruby since our first release.", "company", "company", [RUBY])])]))
C.append(build(13, "D", [("h", "ABOUT THE COMPANY"),
                         ("p", [N("Brightline helps clinics schedule appointments.", "company", "company"),
                                N("Our services are written in TypeScript.", "company", "company", [TS])]),
                         ("h", "Who you are:"),
                         ("b", Q("You have built production systems in TypeScript.", [TS]))]))
# ---- E: benefits beneath "What we offer" -----------------------------------------------------------------------
C.append(build(14, "E", [("h", "What we offer:"),
                         ("b", N("A yearly learning budget.", "benefits", "benefits")),
                         ("b", N("Remote-first working hours.", "benefits", "benefits"))]))
C.append(build(15, "E", [("h", "What you bring:"),
                         ("b", Q("Experience with Kubernetes operators.", [K8S])),
                         ("h", "What you'll get:"),
                         ("b", N("Health insurance for you and your family.", "benefits", "benefits")),
                         ("b", N("A stipend for home-office equipment.", "benefits", "benefits"))]))
C.append(build(16, "E", [("h", "## Perks"),
                         ("b", N("Free lunches on Fridays.", "benefits", "benefits")),
                         ("b", N("Conference tickets every year.", "benefits", "benefits"))]))
# ---- F: personality mixed with technical qualifications --------------------------------------------------------
C.append(build(17, "F", [("h", "About you:"),
                         ("b", N("You are curious and kind.", "personality", "required")),
                         ("b", Q("You have experience with React Native.", [RN])),
                         ("b", N("You love solving puzzles.", "personality", "required"))]))
C.append(build(18, "F", [("h", "Who you are"),
                         ("b", N("You thrive in a fast-paced environment.", "personality", "required")),
                         ("b", Q("You know Python and pandas well.", [PY, PANDAS]))]))
C.append(build(19, "F", [("h", "The ideal candidate:"),
                         ("p", [N("Is passionate about developer tools.", "personality", "required"),
                                Q("Has written production code in Rust.", [RS])])]))
# ---- G: required versus preferred ------------------------------------------------------------------------------
C.append(build(20, "G", [("h", "What you bring:"),
                         ("b", Q("Experience with Java.", [JAVA])),
                         ("b", Q("Kotlin experience is a plus.", [KT], nec="preferred"))]))
C.append(build(21, "G", [("h", "About you"),
                         ("b", Q("Strong SQL skills are required.", [SQL])),
                         ("b", Q("Familiarity with Redis is preferred.", [REDIS], nec="preferred"))]))
C.append(build(22, "G", [("h", "Who you are:"),
                         ("b", Q("Experience with AWS.", [AWS])),
                         ("h", "Nice to have:"),
                         ("b", Q("Experience with Terraform.", ["unresolved:terraform"], nec="preferred",
                                 section="preferred"))]))
# ---- H: explicitly optional --------------------------------------------------------------------------------
C.append(build(23, "H", [("h", "What we're looking for:"),
                         ("b", Q("Experience with Docker is helpful but not required.", [DOCKER], nec="preferred"))]))
C.append(build(24, "H", [("h", "About you:"),
                         ("b", Q("Go experience would be great.", [GO], nec="preferred")),
                         ("b", Q("Knowledge of C# is optional.", [CSHARP], nec="preferred"))]))
C.append(build(25, "H", [("h", "Bonus points"),
                         ("b", Q("Experience with TensorFlow.", [TF], nec="preferred", section="preferred"))]))
# ---- I: negated, historical, future learning ------------------------------------------------------------------
C.append(build(26, "I", [("h", "About you:"),
                         ("b", Q("Experience with Python.", [PY])),
                         ("b", N("No prior Rust experience is required.", "negation", "required", [RS])),
                         ("b", N("You will learn Terraform on the job.", "learning", "required",
                                 ["unresolved:terraform"]))]))
C.append(build(27, "I", [("h", "What you bring:"),
                         ("b", N("We used Perl until 2019.", "company", "required", ["unresolved:perl"])),
                         ("b", Q("Experience with Go.", [GO]))]))
C.append(build(28, "I", [("h", "Who you are"),
                         ("b", N("Kubernetes knowledge is not necessary.", "negation", "required", [K8S])),
                         ("b", Q("You have shipped services on AWS.", [AWS]))]))
# ---- J: nested headings and inheritance ------------------------------------------------------------------------
C.append(build(29, "J", [("h", "About you:"),
                         ("h", "Technical skills:"),
                         ("b", Q("Python and FastAPI.", [PY, FASTAPI])),
                         ("b", Q("PostgreSQL.", [PG])),
                         ("h", "Nice to have:"),
                         ("b", Q("Redis.", [REDIS], nec="preferred", section="preferred"))]))
C.append(build(30, "J", [("h", "## What you bring"),
                         ("h", "### Languages"),
                         ("b", Q("Go or Rust.", [GO, RS])),
                         ("h", "## Benefits"),
                         ("b", N("Paid parental leave.", "benefits", "benefits"))]))
C.append(build(31, "J", [("h", "Who you are:"),
                         ("h", "Tools:"),
                         ("b", Q("Docker.", [DOCKER])),
                         ("h", "What you'll do:"),
                         ("b", N("Maintain CI pipelines for the Docker images.", "responsibility", "responsibility",
                                 [DOCKER]))]))
# ---- K: multiple qualification sections -----------------------------------------------------------------------
C.append(build(32, "K", [("h", "Requirements:"),
                         ("b", Q("Experience with Java.", [JAVA])),
                         ("h", "What you bring:"),
                         ("b", Q("Experience with Spring.", ["unresolved:spring"])),
                         ("h", "Preferred qualifications:"),
                         ("b", Q("Experience with Kotlin.", [KT], nec="preferred", section="preferred"))]))
C.append(build(33, "K", [("h", "About you:"),
                         ("b", Q("Experience with React.", [REACT])),
                         ("h", "About us:"),
                         ("b", N("We are a remote team of twelve.", "company", "company")),
                         ("h", "Who you are:"),
                         ("b", Q("Experience with TypeScript.", [TS]))]))
C.append(build(34, "K", [("h", "Must have:"),
                         ("b", Q("Experience with C++.", [CPP])),
                         ("h", "The ideal candidate:"),
                         ("b", Q("Has worked with CUDA kernels.", [CUDA]))]))
# ---- L: apostrophes, curly punctuation, wrapped headings ------------------------------------------------------
C.append(build(35, "L", [("h", "What we’re looking for:"),
                         ("b", Q("Experience with Swift and SwiftUI.", [SWIFT, "unresolved:swiftui"]))]))
C.append(build(36, "L", [("h", "What You’ll Bring"),
                         ("b", Q("Strong Ruby skills.", [RUBY])),
                         ("h", "What You’ll Do"),
                         ("b", N("Build internal tools in Ruby.", "responsibility", "responsibility", [RUBY]))]))
C.append(build(37, "L", [("h", "Who we're looking"),
                         ("h", "for:"),
                         ("b", Q("Experience with PHP.", ["language.php"]))]))
# ---- M: long or visually ambiguous headings -------------------------------------------------------------------
C.append(build(38, "M", [("h", "The skills and experience we think will help you succeed in this role:"),
                         ("b", Q("Experience with Python data tooling.", [PY]))]))
C.append(build(39, "M", [("h", "About the role"),
                         ("p", [N("This role sits on the platform team.", "company", "company"),
                                N("You will build tooling in Go.", "responsibility", "responsibility", [GO])])]))
C.append(build(40, "M", [("h", "Who you'll work with:"),
                         ("p", [N("You will join a team of five engineers.", "company", "company"),
                                N("The team maintains services in Java.", "company", "company", [JAVA])])]))
# ---- N: bullets and prose under candidate-profile headings ----------------------------------------------------
C.append(build(41, "N", [("h", "About you:"),
                         ("p", [Q("You have several years of experience with Kotlin.", [KT], nt=["experience"]),
                                Q("You are comfortable with SQL.", [SQL])])]))
C.append(build(42, "N", [("h", "What you bring:"),
                         ("p", [Q("Strong TypeScript skills.", [TS]),
                                N("We care about kindness and clear writing.", "company", "required")])]))
C.append(build(43, "N", [("h", "Who you are:"),
                         ("b", Q("Experience with Flask.", ["framework.flask"])),
                         ("blank",),
                         ("p", [N("Acme is an equal opportunity employer.", "company", "none")])]))
# ---- O: technical concepts inside duties ----------------------------------------------------------------------
C.append(build(44, "O", [("h", "About you:"),
                         ("b", N("You will build REST APIs in Python.", "responsibility", "required", [PY])),
                         ("b", Q("Experience with Python web services.", [PY]))]))
C.append(build(45, "O", [("h", "What you bring:"),
                         ("b", N("Design and ship data pipelines in Go.", "responsibility", "required", [GO])),
                         ("b", Q("Experience with Kafka.", ["unresolved:kafka"]))]))
C.append(build(46, "O", [("h", "What you'll do:"),
                         ("b", N("Migrate services from Ruby to Go.", "responsibility", "responsibility", [RUBY, GO])),
                         ("b", N("Tune PostgreSQL queries.", "responsibility", "responsibility", [PG]))]))
# ---- P: candidate-subject qualifications ----------------------------------------------------------------------
C.append(build(47, "P", [("h", "About you:"),
                         ("b", Q("You have experience with Kubernetes.", [K8S])),
                         ("b", Q("You're familiar with Redis.", [REDIS]))]))
C.append(build(48, "P", [("h", "What we're looking for"),
                         ("b", Q("You've shipped React apps to production.", [REACT])),
                         ("b", Q("You know your way around Docker.", [DOCKER]))]))
C.append(build(49, "P", [("p", [N("Northwind builds payroll tools.", "company", "none"),
                                Q("You should have strong experience with C#.", [CSHARP], section="none")])]))
# ---- Q: compound AND/OR -----------------------------------------------------------------------------------------
C.append(build(50, "Q", [("h", "What you bring:"),
                         ("b", Q("Experience with Python or Go.", [PY, GO])),
                         ("b", Q("Experience with Docker and Kubernetes.", [DOCKER, K8S]))]))
C.append(build(51, "Q", [("h", "About you:"),
                         ("b", Q("Java, Kotlin, or Scala.", [JAVA, KT, "unresolved:scala"]))]))
C.append(build(52, "Q", [("h", "Who you are:"),
                         ("b", Q("Experience with React or Vue.", [REACT, "unresolved:vue"]))]))
# ---- R: alias equivalence ---------------------------------------------------------------------------------------
C.append(build(53, "R", [("h", "What you bring:"),
                         ("b", Q("Experience with Golang.", [GO])),
                         ("b", Q("Experience with Postgres.", [PG]))]))
C.append(build(54, "R", [("h", "About you:"),
                         ("b", Q("Comfortable with k8s.", [K8S])),
                         ("b", Q("Strong JS and TS skills.", [JSL, TS]))]))
C.append(build(55, "R", [("h", "Who you are:"),
                         ("b", Q("Experience with Go and Golang tooling.", [GO]))]))
# ---- S: no GitHub-observable pathway ----------------------------------------------------------------------------
C.append(build(56, "S", [("h", "About you:"),
                         ("b", Q("A bachelor's degree in mathematics.", nt=["education"])),
                         ("b", Q("Eligible to work in Canada.", nt=["legal"]))]))
C.append(build(57, "S", [("h", "What you bring:"),
                         ("b", Q("Fluent written German.", nt=["soft_skill"])),
                         ("b", Q("5+ years of experience in software engineering.", nt=["experience"]))]))
C.append(build(58, "S", [("h", "Who you are:"),
                         ("b", Q("An active security clearance.", nt=["legal"])),
                         ("b", Q("An AWS certification.", [AWS], nt=["education"]))]))
# ---- T: README / repository mentions ----------------------------------------------------------------------------
C.append(build(59, "T", [("h", "About you:"),
                         ("b", Q("Experience writing clear READMEs for Python libraries.", [PY])),
                         ("h", "How to apply:"),
                         ("b", N("Send us a link to a GitHub repository you are proud of.", "process", "process"))]))
C.append(build(60, "T", [("h", "What you bring:"),
                         ("b", Q("Open-source contributions in Rust.", [RS])),
                         ("b", N("Our repositories are public on GitHub.", "company", "required"))]))
C.append(build(61, "T", [("h", "Who you are:"),
                         ("b", Q("You maintain a public repository with tests and a README.", nt=["experience"])),
                         ("b", Q("Experience with Jupyter notebooks.", ["language.jupyter_notebook"]))]))

DATA = {
    "schema_version": 1,
    "milestone": "M11-G23",
    "split": "dev",
    "provenance": "Fully synthetic controls written for M11-G23; no real posting text, employer or product names.",
    "authorship_disclosure": (
        "Written by the same AI author (Claude) who traced the v15 parser source and designed the G23 candidate "
        "policies. Targeted probes and near-neighbour cases; a DESIGN set, never independent validation."),
    "label_timing": ("Labels written from evaluation/m11g23/labelling_guide.md and frozen (SHA-256 in "
                     "controls_dev_hash_freeze.json) before any G23 policy existed and before the parser ran on "
                     "this text."),
    "controls": C,
}


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes((json.dumps(DATA, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"wrote {OUT.relative_to(REPO_ROOT)}: {len(C)} controls")


if __name__ == "__main__":
    main()
