"""Milestone 11-G22-R -- ambiguous-alias / README-evidence research controls (builder).

    python scripts/evaluation_lib/m11g22r_build_controls.py

Writes two DISTINCT synthetic control sets and their G14-portable freeze records:

  evaluation/m11g22r/alias_evidence_controls_dev.json   (+ dev_hash_freeze.json)
  evaluation/m11g22r/alias_evidence_controls_eval.json  (+ eval_hash_freeze.json)

and refuses to overwrite a frozen file whose content would change. Freezes are NOT registered
in the G14 manifest (pending a separate research-commit authorization).

Every label is GROUND TRUTH about the synthetic text, recorded here before any production
code ran on it -- never a prediction of what GitScore will do:

  job_concepts  registry concepts the job text genuinely requires (only when `job_text` is set)
  mentioned     registry concepts the repositories' README text genuinely refers to AS A
                TECHNOLOGY (anything else the README extractor emits is a false extraction)
  used          registry concepts the candidate's repositories genuinely USE -- by the README's
                own claim of use ("built with ...", "written in ...") or by a repository artifact
                (language statistics, manifest, Dockerfile). `mentioned` minus `used` is the
                "mentioned without demonstrated use" class (comparisons, roadmaps, FFI notes).
  cell          the Phase-3 paired-matrix cell (1-10) when the control is a paired job/evidence case

A README-only control (no `job_text`) is scored by the harness against a probe requirement
"Experience with <display name>." for its `probe` concept; truth for the probe is `probe in used`.

Authorship: written by the same researcher who designs the G22-R policies -- NOT independent
validation. Provenance: synthetic text only; no real posting, README, employer or private material.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT / "scripts" / "evaluation_lib")]
import gold_integrity as gi  # noqa: E402

OUT_DIR = REPO_ROOT / "evaluation" / "m11g22r"
REQ = "Requirements:\n- "

REACT, EXPRESS, SWIFT, RUST, RUBY = "framework.react", "framework.express", "language.swift", "language.rust", "language.ruby"
SHELL, TORCH, FLASK, PANDAS, PY = "language.shell", "ml.framework.pytorch", "framework.flask", "data.library.pandas", \
    "language.python"
JAVA, GO, DOCKER, JS, TS, K8S = "language.java", "language.go", "infra.docker", "language.javascript", \
    "language.typescript", "infra.kubernetes"
HTML, CSS, C, CPP, KOTLIN, PHP, JUPYTER = "language.html", "language.css", "language.c", "language.cpp", \
    "language.kotlin", "language.php", "language.jupyter_notebook"
NODE_PKG = '{"name": "app", "dependencies": {"express": "^4.19.0"}}'
REACT_PKG = '{"name": "web", "dependencies": {"react": "^18.3.0", "react-dom": "^18.3.0"}}'


def repo(readme=None, languages=None, files=None, name="r1"):
    return {"name": name, "readme": readme, "languages": languages or {}, "files": files or {}}


def X(cid, split, family, *, repos=(), job=None, job_concepts=(), mentioned=(), used=(), probe=None, cell=None,  # noqa: N802
      alias=None, note=""):
    return {"id": f"m11g22r-{cid}", "split": split, "family": family, "alias": alias, "cell": cell,
            "job_text": job, "job_concepts": sorted(job_concepts), "repos": list(repos),
            "mentioned": sorted(mentioned), "used": sorted(used), "probe": probe, "note": note}


def D(n, *a, **k):  # noqa: N802
    return X(f"d{n:02d}", "dev", *a, **k)


def E(n, *a, **k):  # noqa: N802
    return X(f"e{n:02d}", "eval", *a, **k)


DEV = [
    # ---- README: ordinary-English negatives ------------------------------------------------------
    D(1, "readme_ordinary", alias="react", probe=REACT,
      repos=[repo("# triage-bot\n\nA small bot that helps maintainers react quickly to new issues.\n",
                  {"Python": 9000})], used=[PY]),
    D(2, "readme_ordinary", alias="express", probe=EXPRESS,
      repos=[repo("# feedback-form\n\nUsers can express their opinion about each release in one click.\n",
                  {"PHP": 5000})], used=[PHP]),
    D(3, "readme_ordinary", alias="swift", probe=SWIFT,
      repos=[repo("# quickcsv\n\nA swift, dependency-free CSV parser for the command line.\n", {"C": 8000})], used=[C]),
    D(4, "readme_ordinary", alias="rust", probe=RUST,
      repos=[repo("# photo-restore\n\nRemoves rust stains and scratches from scanned photographs.\n",
                  {"Python": 7000})], used=[PY]),
    D(5, "readme_ordinary", alias="ruby", probe=RUBY,
      repos=[repo("# ruby-the-cat\n\nA tiny website about my cat, Ruby, and her favourite toys.\n",
                  {"HTML": 4000, "CSS": 1000})], used=[HTML, CSS]),
    D(6, "readme_ordinary", alias="shell", probe=SHELL,
      repos=[repo("# beach-log\n\nCatalogue every shell you find on the beach, with photos and GPS.\n",
                  {"Kotlin": 6000})], used=[KOTLIN]),
    D(7, "readme_ordinary", alias="torch", probe=TORCH,
      repos=[repo("# handover\n\nWe pass the torch to new maintainers every year; see MAINTAINERS.md.\n",
                  {"Go": 5000})], used=[GO]),
    D(8, "readme_ordinary", alias="flask", probe=FLASK,
      repos=[repo("# lab-inventory\n\nTracks every beaker and flask in the chemistry lab.\n", {"Java": 6000})],
      used=[JAVA]),
    D(9, "readme_ordinary", alias="pandas", probe=PANDAS,
      repos=[repo("# zoo-cams\n\nLive camera links for the red pandas and snow leopards.\n", {"JavaScript": 3000})],
      used=[JS]),
    D(10, "readme_ordinary", alias="python", probe=PY,
       repos=[repo("# reptile-care\n\nFeeding schedule tracker for a ball python and two geckos.\n",
                   {"Dart": 9000})], used=[]),
    D(11, "readme_ordinary", alias="react", probe=REACT,
       repos=[repo("# chemistry-sim\n\nSimulates how acids react with metals, step by step.\n", {"C++": 9000})],
       used=[CPP]),
    D(12, "readme_ordinary", alias="express", probe=EXPRESS,
       repos=[repo("# parcel-tracker\n\nTrack express and standard shipping parcels from one dashboard.\n",
                   {"Python": 9000})], used=[PY]),
    # ---- README: genuine positives ---------------------------------------------------------------
    D(13, "readme_genuine", alias="react", probe=REACT,
      repos=[repo("# dashboard\n\nA dashboard built with React and TypeScript.\n", {"TypeScript": 9000})],
      mentioned=[REACT, TS], used=[REACT, TS]),
    D(14, "readme_genuine", alias="express", probe=EXPRESS,
      repos=[repo("# api\n\nREST API written in Node.js using Express.\n", {"JavaScript": 9000})],
      mentioned=[EXPRESS], used=[EXPRESS, JS]),
    D(15, "readme_genuine", alias="swift", probe=SWIFT,
      repos=[repo("# habit-ios\n\nAn iOS habit tracker written in Swift and SwiftUI.\n", {"Swift": 9000})],
      mentioned=[SWIFT], used=[SWIFT]),
    D(16, "readme_genuine", alias="rust", probe=RUST,
      repos=[repo("# fastgrep\n\nA grep clone written in Rust.\n", {"Rust": 9000})], mentioned=[RUST], used=[RUST]),
    D(17, "readme_genuine", alias="shell", probe=SHELL,
      repos=[repo("# dotfiles\n\nMy dotfiles plus a few shell scripts to bootstrap a new machine.\n",
                  {"Shell": 9000})], mentioned=[SHELL], used=[SHELL]),
    D(18, "readme_genuine", alias="torch", probe=TORCH,
      repos=[repo("# tiny-gpt\n\nA minimal GPT implementation in PyTorch.\n", {"Python": 9000})],
      mentioned=[TORCH], used=[TORCH, PY]),
    D(19, "readme_genuine_lowercase", alias="flask", probe=FLASK,
      repos=[repo("# notes-api\n\nsmall notes api. uses flask and sqlite.\n", {"Python": 9000})],
      mentioned=[FLASK], used=[FLASK, PY]),
    D(20, "readme_genuine", alias="pandas", probe=PANDAS,
      repos=[repo("# sales-eda\n\nExploratory analysis of sales data with pandas and matplotlib.\n",
                  {"Jupyter Notebook": 9000})], mentioned=[PANDAS], used=[PANDAS, JUPYTER]),
    # ---- README: mentioned without demonstrated use ----------------------------------------------
    D(21, "readme_mention_no_use", alias="rust", probe=RUST,
      repos=[repo("# tinyhttp\n\nA tiny HTTP server in C. A Rust port would be a fun future project.\n",
                  {"C": 9000})], mentioned=[RUST], used=[C],
      note="speculative mention, not a roadmap phrase the existing cue list covers"),
    D(22, "readme_mention_no_use", alias="react", probe=REACT,
      repos=[repo("# vanilla-ui\n\nA UI kit in plain JavaScript. Its component model is inspired by React.\n",
                  {"JavaScript": 9000})], mentioned=[REACT], used=[JS]),
    D(23, "readme_mention_negated", alias="express", probe=EXPRESS,
      repos=[repo("# micro-http\n\nA minimal Node HTTP router. It does not use Express or any framework.\n",
                  {"JavaScript": 9000})], mentioned=[EXPRESS], used=[JS],
      note="explicit non-use: covered by the existing 8D.3 adjacency cue"),
    # ---- job side ---------------------------------------------------------------------------------
    D(24, "job_ordinary", alias="react", job=REQ + "Ability to react quickly to production incidents."),
    D(25, "job_ordinary", alias="express", job=REQ + "Ability to express complex ideas clearly to stakeholders."),
    D(26, "job_ordinary", alias="shell", job=REQ + "Confidence to come out of your shell when presenting to clients."),
    D(27, "job_genuine", alias="react", job=REQ + "3+ years of experience with React.", job_concepts=[REACT]),
    D(28, "job_genuine", alias="swift", job=REQ + "Experience building iOS apps in Swift.", job_concepts=[SWIFT]),
    # ---- paired job / evidence matrix ------------------------------------------------------------
    D(29, "paired", cell=1, alias="react", job=REQ + "Experience with React.", job_concepts=[REACT],
      repos=[repo("# shop-ui\n\nStorefront built with React.\n", {"JavaScript": 9000}, {"package.json": REACT_PKG})],
      mentioned=[REACT], used=[REACT, JS]),
    D(30, "paired", cell=2, alias="react", job=REQ + "Experience with React.", job_concepts=[REACT],
      repos=[repo("# alerting\n\nPages the on-call engineer so the team can react within minutes.\n",
                  {"Go": 9000})], used=[GO]),
    D(31, "paired", cell=3, alias="express", job=REQ + "Ability to express ideas clearly in writing.",
      repos=[repo("# api\n\nREST API built with Express.\n", {"JavaScript": 9000}, {"package.json": NODE_PKG})],
      mentioned=[EXPRESS], used=[EXPRESS, JS]),
    D(32, "paired", cell=4, alias="react", job=REQ + "Ability to react quickly to customer feedback.",
      repos=[repo("# support-bot\n\nHelps support staff react faster to customer feedback.\n", {"Python": 9000})],
      used=[PY]),
    D(33, "paired", cell=5, alias="swift", job=REQ + "A swift learner who adapts to new tools.",
      repos=[repo("# cli\n\nA swift little command-line timer.\n", {"C": 9000})], used=[C]),
    D(34, "paired", cell=6, alias="express", job=REQ + "Experience with Express.", job_concepts=[EXPRESS],
      repos=[repo("# api\n\nAPI server using Express.\n", {"JavaScript": 9000}, {"package.json": NODE_PKG})],
      mentioned=[EXPRESS], used=[EXPRESS, JS]),
    D(35, "paired", cell=7, alias="swift", job=REQ + "Experience with Swift.", job_concepts=[SWIFT],
      repos=[repo("# ios-app\n\nAn iOS app written in Swift.\n", {"Swift": 9000})], mentioned=[SWIFT], used=[SWIFT]),
    D(36, "paired", cell=8, alias="react", job=REQ + "Experience with React.", job_concepts=[REACT],
      repos=[repo("# bot-a\n\nLets moderators react quickly to spam.\n", {"Python": 9000}, name="bot-a"),
             repo("# bot-b\n\nHelps teams react quickly to outages.\n", {"Python": 9000}, name="bot-b")],
      used=[PY]),
    D(37, "paired", cell=9, alias="rust", job=REQ + "Experience with Rust.", job_concepts=[RUST],
      repos=[repo("# parser\n\nA JSON parser in C. Unlike Rust, it has no borrow checker.\n", {"C": 9000})],
      mentioned=[RUST], used=[C]),
    D(38, "paired", cell=10, alias="rust", job=REQ + "Experience with Rust.", job_concepts=[RUST],
      repos=[repo("# mathlib\n\nA C math library. Bindings for Rust can be generated with bindgen.\n",
                  {"C": 9000})], mentioned=[RUST], used=[C]),
    D(39, "paired", cell=6, alias="torch", job=REQ + "Experience with PyTorch.", job_concepts=[TORCH],
      repos=[repo("# classifier\n\nImage classifier trained with torch.\n", {"Python": 9000},
                  {"requirements.txt": "torch==2.3.0\nnumpy\n"})], mentioned=[TORCH], used=[TORCH, PY]),
    D(40, "paired", cell=4, alias="torch", job=REQ + "Willingness to carry the torch for code quality.",
      repos=[repo("# lint-rules\n\nWe carry the torch for readable code.\n", {"TypeScript": 9000})], used=[TS]),
]

EVAL = [
    E(1, "readme_ordinary", alias="react", probe=REACT,
      repos=[repo("# incident-notes\n\nTemplates that help on-call teams react calmly during outages.\n",
                  {"Markdown": 100, "Python": 2000})], used=[PY]),
    E(2, "readme_ordinary", alias="express", probe=EXPRESS,
      repos=[repo("# survey\n\nLets students express which topics they found hardest.\n", {"Ruby": 7000})],
      used=[RUBY]),
    E(3, "readme_ordinary", alias="swift", probe=SWIFT,
      repos=[repo("# bird-count\n\nCounts swift and swallow sightings from audio recordings.\n", {"Python": 8000})],
      used=[PY]),
    E(4, "readme_ordinary", alias="rust", probe=RUST,
      repos=[repo("# bike-care\n\nA checklist app to keep your chain free of rust.\n", {"Kotlin": 8000})], used=[KOTLIN]),
    E(5, "readme_ordinary_capitalised", alias="ruby", probe=RUBY,
      repos=[repo("# gem-catalog\n\nPrices for Ruby, Sapphire and Emerald stones from local jewellers.\n",
                  {"PHP": 8000})], used=[PHP]),
    E(6, "readme_ordinary", alias="shell", probe=SHELL,
      repos=[repo("# turtle-tracker\n\nMeasures shell length of rescued sea turtles.\n", {"R": 8000})], used=[]),
    E(7, "readme_ordinary", alias="torch", probe=TORCH,
      repos=[repo("# camping-list\n\nPacking list: tent, torch, stove and water filter.\n", {"Dart": 8000})], used=[]),
    E(8, "readme_ordinary", alias="pandas", probe=PANDAS,
      repos=[repo("# panda-facts\n\nFun facts about giant pandas for a school project.\n", {"HTML": 8000})], used=[HTML]),
    E(9, "readme_ordinary_capitalised", alias="java", probe=JAVA,
      repos=[repo("# cafe-menu\n\nThe menu site for our Java coffee bar in Jakarta.\n", {"HTML": 8000})], used=[HTML]),
    E(10, "readme_ordinary", alias="express", probe=EXPRESS,
       repos=[repo("# train-times\n\nShows departures for local and express trains.\n", {"Swift": 8000})],
       used=[SWIFT]),
    E(11, "readme_ordinary_sentence_initial", alias="react", probe=REACT,
       repos=[repo("# alerts\n\nReact to failed builds automatically with this GitHub Action.\n",
                   {"TypeScript": 8000})], used=[TS],
       note="sentence-initial capital: no casing signal"),
    E(12, "readme_genuine", alias="react", probe=REACT,
      repos=[repo("# portfolio\n\nMy portfolio site. Stack: react, vite, tailwind.\n", {"JavaScript": 9000})],
      mentioned=[REACT], used=[REACT, JS], note="lowercase genuine list mention"),
    E(13, "readme_genuine", alias="express", probe=EXPRESS,
      repos=[repo("# auth-service\n\nAuthentication microservice (Node.js + Express + Postgres).\n",
                  {"JavaScript": 9000})], mentioned=[EXPRESS, "database.postgresql"],
      used=[EXPRESS, JS, "database.postgresql"]),
    E(14, "readme_genuine", alias="swift", probe=SWIFT,
      repos=[repo("# widget-kit\n\nReusable widgets for macOS apps, implemented in Swift.\n", {"Swift": 9000})],
      mentioned=[SWIFT], used=[SWIFT]),
    E(15, "readme_genuine", alias="rust", probe=RUST,
      repos=[repo("# wasm-game\n\nA browser game compiled from Rust to WebAssembly.\n", {"Rust": 9000})],
      mentioned=[RUST], used=[RUST]),
    E(16, "readme_genuine", alias="ruby", probe=RUBY,
      repos=[repo("# blog\n\nA blog engine built with Ruby on Rails.\n", {"Ruby": 9000})],
      mentioned=[RUBY], used=[RUBY]),
    E(17, "readme_genuine_lowercase", alias="shell", probe=SHELL,
      repos=[repo("# backup\n\nnightly backup via a bash/shell script and cron.\n", {"Shell": 9000})],
      mentioned=[SHELL], used=[SHELL]),
    E(18, "readme_genuine_lowercase", alias="torch", probe=TORCH,
      repos=[repo("# diffusion-toy\n\ntoy diffusion model. needs torch >= 2.0.\n", {"Python": 9000})],
      mentioned=[TORCH], used=[TORCH, PY]),
    E(19, "readme_mention_no_use", alias="swift", probe=SWIFT,
      repos=[repo("# api-spec\n\nOpenAPI spec for our service. Clients can be generated for Swift or Kotlin.\n",
                  {"YAML": 100})], mentioned=[SWIFT, "language.kotlin"], used=[]),
    E(20, "readme_mention_no_use", alias="react", probe=REACT,
      repos=[repo("# state-lib\n\nA framework-agnostic state library; works with React, Vue or Svelte.\n",
                  {"TypeScript": 9000})], mentioned=[REACT], used=[TS]),
    E(21, "job_ordinary", alias="swift", job=REQ + "Swift decision-making under pressure."),
    E(22, "job_ordinary", alias="torch", job=REQ + "Ready to carry the torch for engineering excellence."),
    E(23, "job_genuine", alias="rust", job=REQ + "Strong Rust programming skills.", job_concepts=[RUST]),
    E(24, "job_genuine", alias="shell", job=REQ + "Experience writing shell scripts.", job_concepts=[SHELL]),
    E(25, "paired", cell=1, alias="rust", job=REQ + "Experience with Rust.", job_concepts=[RUST],
      repos=[repo("# kv-store\n\nAn embedded key-value store in Rust.\n", {"Rust": 9000})],
      mentioned=[RUST], used=[RUST]),
    E(26, "paired", cell=2, alias="swift", job=REQ + "Experience with Swift.", job_concepts=[SWIFT],
      repos=[repo("# deploy\n\nA swift way to deploy static sites.\n", {"Go": 9000})], used=[GO]),
    E(27, "paired", cell=3, alias="react", job=REQ + "Ability to react quickly to production incidents.",
      repos=[repo("# web\n\nFrontend built with React.\n", {"JavaScript": 9000}, {"package.json": REACT_PKG})],
      mentioned=[REACT], used=[REACT, JS]),
    E(28, "paired", cell=4, alias="express", job=REQ + "Ability to express ideas clearly.",
      repos=[repo("# journal\n\nA private journal where you can express yourself freely.\n", {"Swift": 9000})],
      used=[SWIFT]),
    E(29, "paired", cell=5, alias="rust", job=REQ + "Must be comfortable working around rust and grease.",
      repos=[repo("# garage\n\nInventory app for a garage full of rust and old tools.\n", {"PHP": 9000})], used=[PHP]),
    E(30, "paired", cell=6, alias="react", job=REQ + "Experience with React.", job_concepts=[REACT],
      repos=[repo("# shop\n\nE-commerce frontend using React.\n", {"TypeScript": 9000}, {"package.json": REACT_PKG})],
      mentioned=[REACT], used=[REACT, TS]),
    E(31, "paired", cell=7, alias="ruby", job=REQ + "Experience with Ruby.", job_concepts=[RUBY],
      repos=[repo("# scraper\n\nA web scraper written in Ruby.\n", {"Ruby": 9000})], mentioned=[RUBY], used=[RUBY]),
    E(32, "paired", cell=8, alias="swift", job=REQ + "Experience with Swift.", job_concepts=[SWIFT],
      repos=[repo("# a\n\nA swift static site generator.\n", {"Go": 9000}, name="a"),
             repo("# b\n\nA swift image resizer.\n", {"Go": 9000}, name="b")], used=[GO]),
    E(33, "paired", cell=9, alias="express", job=REQ + "Experience with Express.", job_concepts=[EXPRESS],
      repos=[repo("# router\n\nA tiny router. Express is not used.\n", {"JavaScript": 9000})],
      mentioned=[EXPRESS], used=[JS]),
    E(34, "paired", cell=10, alias="react", job=REQ + "Experience with React.", job_concepts=[REACT],
      repos=[repo("# design-notes\n\nNotes comparing React and Vue for a talk I gave.\n", {}),
             ], mentioned=[REACT], used=[]),
    E(35, "paired", cell=6, alias="flask", job=REQ + "Experience with Flask.", job_concepts=[FLASK],
      repos=[repo("# shortener\n\nURL shortener service.\n", {"Python": 9000},
                  {"requirements.txt": "flask==3.0.0\n"})], used=[FLASK, PY]),
    E(36, "paired", cell=2, alias="python", job=REQ + "Experience with Python.", job_concepts=[PY],
      repos=[repo("# snake-game\n\nA snake game where the python grows each level.\n", {"Lua": 9000})], used=[]),
]


def _write(controls: list[dict], split: str, label_timing: str) -> None:
    out, freeze = OUT_DIR / f"alias_evidence_controls_{split}.json", OUT_DIR / f"{split}_hash_freeze.json"
    doc = {
        "schema_version": 1, "milestone": "M11-G22-R (ambiguous alias and README evidence audit)", "split": split,
        "provenance": "author-created synthetic job texts and repositories; no real posting, README, employer or "
                      "private material",
        "authorship_disclosure": ("Written by the same researcher who designs the G22-R candidate policies; NOT an "
                                  "independent validation set."),
        "label_timing": label_timing,
        "label_semantics": {"job_concepts": "registry concepts the job text genuinely requires",
                            "mentioned": "registry concepts the README text genuinely refers to as a technology",
                            "used": "registry concepts the candidate's repositories genuinely use (README claim of "
                                    "own use, or a repository artifact)",
                            "probe": "README-only controls are scored against 'Experience with <display>.'"},
        "controls": controls,
    }
    payload = (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if out.exists():
        if gi.canonical_bytes(out.read_bytes()) != payload:
            raise SystemExit(f"{out} is frozen and its content would change; refusing to overwrite")
        print(split, "unchanged", gi.sha256(payload))
        return
    out.write_bytes(payload)
    freeze.write_bytes((json.dumps({
        "frozen_file": out.relative_to(REPO_ROOT).as_posix(), "sha256": gi.sha256(payload),
        "sha256_lf_normalized": gi.sha256(gi.canonical_bytes(payload)), "length_bytes": len(payload),
        "canonical_contract": "crlf-to-lf/v1",
        "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Labels frozen BEFORE any GitScore parser, extractor, matcher or G22-R policy ran on this set. NOT "
                "registered in the canonical manifest (pending authorization).",
    }, indent=2) + "\n").encode("utf-8"))
    print(f"wrote {len(controls)} {split} controls; sha256={gi.sha256(payload)} bytes={len(payload)}")


def main() -> None:
    ids = [c["id"] for c in DEV + EVAL]
    assert len(ids) == len(set(ids))
    for c in DEV + EVAL:
        assert c["job_text"] or c["repos"], c["id"]
        assert c["job_text"] is not None or c["probe"], c["id"]
        assert set(c["mentioned"]) | set(c["used"]) >= set(), c["id"]
    _write(DEV, "dev", "labels frozen before any production run; G22-R policies are designed against this set")
    _write(EVAL, "eval", "authored with DEV but kept unrun until the G22-R policy design freeze; same author, so only "
                         "weakly held out")


if __name__ == "__main__":
    main()
