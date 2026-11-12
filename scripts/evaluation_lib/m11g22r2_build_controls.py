"""Milestone 11-G22-R2 -- README evidence context / confidence research controls (builder).

    python scripts/evaluation_lib/m11g22r2_build_controls.py

Writes two DISTINCT synthetic README control sets and their G14-portable freeze records:

  evaluation/m11g22r2/readme_context_controls_dev.json   (+ dev_hash_freeze.json)
  evaluation/m11g22r2/readme_context_controls_eval.json  (+ eval_hash_freeze.json)

and refuses to overwrite a frozen file whose content would change. Freezes are NOT registered in the
G14 manifest (pending a separate research-commit authorization).

Every label is GROUND TRUTH about the synthetic text, recorded before any GitScore code ran on it:

  concepts   {registry concept id: mention class} for EVERY registry concept the README text mentions in
             any sense. Classes:
               ordinary    the alias is ordinary language, not the technology (false identity)
               reference   genuine technology reference that does not claim this project uses it
               use         explicit or plain-reading claim that this project uses it now
               historical  the project used it in the past
               future      planned, hypothetical, considered, or "can be generated"
               negated     explicitly not used
               ambiguous   intent cannot be determined from the text
  used       concepts the repositories genuinely use NOW (README use claim or a repository artifact):
             the truth for a SUPPORTED requirement
  uncertain  concepts whose SUPPORTED truth is undetermined (historical use, conflicting signals);
             excluded from both true and false SUPPORTED counts and reported separately
  probe      every control is scored against "Requirements:\n- Experience with <display name>."

A manifest or language statistic is repository-artifact evidence of USE in the project. It is never a
claim about the candidate's competence.

Authorship: written by the same researcher who designs the G22-R2 policies -- NOT independent
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

OUT_DIR = REPO_ROOT / "evaluation" / "m11g22r2"
REACT, EXPRESS, SWIFT, RUST, RUBY = "framework.react", "framework.express", "language.swift", "language.rust", "language.ruby"
SHELL, TORCH, FLASK, PANDAS, PY = "language.shell", "ml.framework.pytorch", "framework.flask", "data.library.pandas", \
    "language.python"
JAVA, DOCKER, KOTLIN, FASTAPI = "language.java", "infra.docker", "language.kotlin", "framework.fastapi"
ORD, REF, USE, HIST, FUT, NEG, AMB = "ordinary", "reference", "use", "historical", "future", "negated", "ambiguous"


def repo(readme, languages=None, files=None, name="r1"):
    return {"name": name, "readme": readme, "languages": languages or {}, "files": files or {}}


def X(cid, split, family, probe, readme=None, *, concepts=None, used=(), uncertain=(), repos=None, languages=None,  # noqa: N802
      files=None, pair=None, note=""):
    if repos is None:
        repos = [repo(readme, languages, files)]
    return {"id": f"m11g22r2-{cid}", "split": split, "family": family, "probe": probe, "pair": pair,
            "repos": repos, "concepts": dict(sorted((concepts or {}).items())), "used": sorted(used),
            "uncertain": sorted(uncertain), "note": note}


def D(n, *a, **k):  # noqa: N802
    return X(f"d{n:02d}", "dev", *a, **k)


def E(n, *a, **k):  # noqa: N802
    return X(f"e{n:02d}", "eval", *a, **k)


def md(name, body):
    return f"# {name}\n\n{body}\n"


DEV = [
    # ---- ordinary-language negatives --------------------------------------------------------------
    D(1, "ordinary", REACT, md("oncall-kit", "Checklists that help you react quickly to incidents."), concepts={REACT: ORD}),
    D(2, "ordinary", EXPRESS, md("city-rail", "Timetables for local and express trains in the city."),
      concepts={EXPRESS: ORD}),
    D(3, "ordinary", RUST, md("bike-care", "Keeps bike chains free of rust."), concepts={RUST: ORD}, pair="rust-free-of"),
    D(4, "ordinary_capitalised", RUBY, md("museum", "Shows the Ruby gemstone collection of the city museum."),
      concepts={RUBY: ORD}),
    D(5, "ordinary_capitalised", JAVA, md("travel-notes", "Travel notes: Java is an island in Indonesia."),
      concepts={JAVA: ORD}),
    D(6, "ordinary", FLASK, md("lab-stock", "Inventory of every flask for experiments in our lab."), concepts={FLASK: ORD}),
    D(7, "ordinary_sentence_initial", PANDAS, md("forest-log", "Pandas live in the forest; this app logs sightings."),
      concepts={PANDAS: ORD}),
    D(8, "ordinary", TORCH, md("maintainers", "Maintainers pass the torch each spring."), concepts={TORCH: ORD}),
    D(9, "ordinary_sentence_initial", SWIFT, md("birds", "Swift and swallow migration tracker."), concepts={SWIFT: ORD}),
    D(10, "ordinary", SHELL, md("museum-photos", "Each shell in the museum is photographed twice."),
      concepts={SHELL: ORD}),
    D(11, "ordinary", PY, md("reptiles", "Feeding log for Monty the python."), concepts={PY: ORD}),
    D(12, "ordinary", EXPRESS, md("feedback", "Please express interest by opening an issue."), concepts={EXPRESS: ORD}),
    # ---- genuine technical references (project use) -----------------------------------------------
    D(13, "genuine_use", REACT, md("ui-kit", "A library built on React component architecture."),
      concepts={REACT: USE}, used=[REACT]),
    D(14, "genuine_use", EXPRESS, md("hooks-server", "A small Express.js server for webhooks."),
      concepts={EXPRESS: USE}, used=[EXPRESS]),
    D(15, "genuine_use", RUST, md("renamer", "A Rust command-line tool for renaming files."),
      concepts={RUST: USE}, used=[RUST]),
    D(16, "genuine_use", RUBY, md("digest", "A Ruby application that sends daily digests."),
      concepts={RUBY: USE}, used=[RUBY]),
    D(17, "genuine_use", JAVA, md("resizer", "A Java service that resizes images."), concepts={JAVA: USE}, used=[JAVA]),
    D(18, "genuine_use", FLASK, md("chores", "A Flask web application for tracking chores."),
      concepts={FLASK: USE}, used=[FLASK]),
    D(19, "genuine_use_lowercase", PANDAS, md("sales-batch", "Batch pandas DataFrame processing for sales exports."),
      concepts={PANDAS: USE}, used=[PANDAS]),
    D(20, "genuine_use", TORCH, md("digits", "A PyTorch model for digit recognition."), concepts={TORCH: USE}, used=[TORCH]),
    D(21, "genuine_use_lowercase", TORCH, md("tiny-cnn", "Trains a small CNN with torch and torchvision."),
      concepts={TORCH: USE}, used=[TORCH]),
    # ---- ambiguous but genuine contexts ------------------------------------------------------------
    D(22, "genuine_use_no_cue", PY, md("audio-fx", "Includes a python visualizer for the generated audio."),
      concepts={PY: USE}, used=[PY], note="G22-R real-README case (AudioNoise) paraphrased"),
    D(23, "future_hypothetical", RUST, md("mathlib", "A small math library. Rust bindings can be generated with bindgen."),
      concepts={RUST: FUT}),
    D(24, "reference_only", REACT, md("viewlet", "A tiny view layer inspired by React."), concepts={REACT: REF}),
    D(25, "future", JAVA, md("ledger", "We are migrating this tool to Java."), concepts={JAVA: FUT}),
    D(26, "future", EXPRESS, md("planner", "Considering Express for the backend next quarter."), concepts={EXPRESS: FUT}),
    D(27, "historical", RUBY, md("legacy", "This project previously used Ruby."), concepts={RUBY: HIST}, uncertain=[RUBY]),
    D(28, "negated", REACT, md("plain-ui", "This project does not use React."), concepts={REACT: NEG}),
    D(29, "quoted_ordinary", REACT, md("logs", 'The error message said "react quickly or lose data".'),
      concepts={REACT: ORD}),
    # ---- corroboration -----------------------------------------------------------------------------
    D(30, "corroborated_manifest", FLASK, md("notes-api", "Built with Flask."), files={"requirements.txt": "flask==3.0.0\n"},
      concepts={FLASK: USE}, used=[FLASK]),
    D(31, "corroborated_language", RUST, md("fsearch", "A Rust tool for searching files."), languages={"Rust": 9000},
      concepts={RUST: USE}, used=[RUST]),
    D(32, "corroborated_docker", DOCKER, md("deploy", "Runs in Docker."), files={"Dockerfile": "FROM alpine:3.20\n"},
      concepts={DOCKER: USE}, used=[DOCKER]),
    D(33, "readme_only_use", EXPRESS, md("backend", "Backend written in Express."), concepts={EXPRESS: USE}, used=[EXPRESS]),
    D(34, "multi_repo_use", REACT, None, repos=[repo(md("web-a", "Uses React for the UI."), name="web-a"),
                                                repo(md("web-b", "Uses React for the UI."), name="web-b")],
      concepts={REACT: USE}, used=[REACT]),
    D(35, "conflicting", REACT, md("shop", "Built with React."), files={"package.json": '{"dependencies": {"vue": "^3.4.0"}}'},
      concepts={REACT: AMB}, uncertain=[REACT], note="README claims React; the manifest lists only Vue"),
    D(36, "ordinary_readme_corroborated_use", REACT, md("dash", "Helps operators react quickly to alerts."),
      files={"package.json": '{"dependencies": {"react": "^18.3.0"}}'}, concepts={REACT: ORD}, used=[REACT],
      note="README occurrence is ordinary; React use is established by the manifest"),
    # ---- near-neighbour pairs ----------------------------------------------------------------------
    D(37, "pair_use", RUST, md("safe-io", "Written in Rust, free of unsafe code."), concepts={RUST: USE}, used=[RUST],
      pair="rust-free-of"),
    D(38, "pair_ordinary", EXPRESS, md("rail-b", "Local and express services every hour."), concepts={EXPRESS: ORD},
      pair="express-and"),
    D(39, "pair_use", EXPRESS, md("api-b", "A Node and Express backend."), concepts={EXPRESS: USE}, used=[EXPRESS],
      pair="express-and"),
    D(40, "pair_ordinary_capitalised", JAVA, md("coffee", "Java coffee recipes from our cafe."), concepts={JAVA: ORD},
      pair="java-cap"),
    D(41, "pair_use", JAVA, md("android", "A Java and Kotlin Android app."), concepts={JAVA: USE, KOTLIN: USE},
      used=[JAVA, KOTLIN], pair="java-cap"),
    D(42, "pair_ordinary", RUBY, md("jewels", "A ruby ring photographed in macro."), concepts={RUBY: ORD}, pair="ruby"),
    D(43, "pair_use", RUBY, md("rails-app", "A Ruby on Rails app for book clubs."), concepts={RUBY: USE}, used=[RUBY],
      pair="ruby"),
    D(44, "pair_ordinary", TORCH, md("hike", "Bring a torch and water for the trail."), concepts={TORCH: ORD}, pair="torch"),
]

EVAL = [
    E(1, "ordinary", REACT, md("alerts", "Helps teams react faster to alerts."), concepts={REACT: ORD}),
    E(2, "ordinary_sentence_initial", EXPRESS, md("parcels", "Express delivery tracking for parcels."),
      concepts={EXPRESS: ORD}),
    E(3, "ordinary", RUST, md("photo-fix", "Removes rust from vintage photos."), concepts={RUST: ORD}),
    E(4, "ordinary_capitalised", RUBY, md("named", "Named after Ruby, my grandmother."), concepts={RUBY: ORD}),
    E(5, "ordinary_capitalised", JAVA, md("trip", "Photos from our trip to Java and Bali."), concepts={JAVA: ORD}),
    E(6, "ordinary_sentence_initial", FLASK, md("chem", "Shake the flask before measuring."), concepts={FLASK: ORD}),
    E(7, "ordinary", PANDAS, md("adopt", "Adopt-a-panda donations site; pandas need bamboo."), concepts={PANDAS: ORD}),
    E(8, "ordinary", TORCH, md("night-hike", "Bring a torch for the night hike."), concepts={TORCH: ORD}),
    E(9, "ordinary", SWIFT, md("reply-bot", "A swift reply bot for support tickets."), concepts={SWIFT: ORD}),
    E(10, "ordinary_sentence_initial", SHELL, md("tides", "Shell collection photographed at low tide."),
      concepts={SHELL: ORD}),
    E(11, "ordinary_sentence_initial", PY, md("everglades", "Python sightings in the Everglades, mapped."),
      concepts={PY: ORD}),
    E(12, "ordinary_sentence_initial", EXPRESS, md("stickers", "Express yourself with custom stickers."),
      concepts={EXPRESS: ORD}),
    E(13, "genuine_use", REACT, md("spa", "Single-page app using React hooks."), concepts={REACT: USE}, used=[REACT]),
    E(14, "genuine_use", EXPRESS, md("auth-api", "REST API on Express with JWT auth."), concepts={EXPRESS: USE},
      used=[EXPRESS]),
    E(15, "genuine_use", RUST, md("imgdiff", "Fast image diffing in Rust."), concepts={RUST: USE}, used=[RUST]),
    E(16, "genuine_use", RUBY, md("invoices", "Ruby gem for parsing invoices."), concepts={RUBY: USE}, used=[RUBY]),
    E(17, "genuine_use", JAVA, md("orders", "Spring Boot service in Java."), concepts={JAVA: USE}, used=[JAVA]),
    E(18, "genuine_use", FLASK, md("mini-api", "Minimal Flask API with SQLite."), concepts={FLASK: USE}, used=[FLASK]),
    E(19, "genuine_use_lowercase", PANDAS, md("csv-clean", "Cleans CSV files with pandas."), concepts={PANDAS: USE},
      used=[PANDAS]),
    E(20, "genuine_use_lowercase", TORCH, md("cifar", "Fine-tunes a torch model on CIFAR-10."), concepts={TORCH: USE},
      used=[TORCH]),
    E(21, "genuine_use", SWIFT, md("dates", "Swift package for date formatting."), concepts={SWIFT: USE}, used=[SWIFT]),
    E(22, "genuine_use_lowercase", SHELL, md("provision", "Provisioning shell scripts for Debian."),
      concepts={SHELL: USE}, used=[SHELL]),
    E(23, "genuine_use_no_cue", PY, md("plots", "Ships a small python plotting helper."), concepts={PY: USE}, used=[PY]),
    E(24, "future_hypothetical", RUST, md("codec", "A C codec. Bindings for Rust are planned."), concepts={RUST: FUT}),
    E(25, "reference_only", EXPRESS, md("router", "API design borrowed from Express."), concepts={EXPRESS: REF}),
    E(26, "future", SWIFT, md("notes-app", "Will be ported to Swift later."), concepts={SWIFT: FUT}),
    E(27, "future", FLASK, md("v2-plan", "Evaluating Flask versus FastAPI for v2."), concepts={FLASK: FUT, FASTAPI: FUT}),
    E(28, "historical", JAVA, md("migrated", "Originally written in Java; now pure Kotlin."),
      concepts={JAVA: HIST, KOTLIN: USE}, used=[KOTLIN], uncertain=[JAVA]),
    E(29, "negated", REACT, md("vanilla", "We no longer use React."), concepts={REACT: NEG}),
    E(30, "quoted_ordinary", TORCH, md("motto", 'Our motto: "pass the torch".'), concepts={TORCH: ORD}),
    E(31, "corroborated_language", RUBY, md("rb-tool", "A Ruby script for renaming photos."), languages={"Ruby": 9000},
      concepts={RUBY: USE}, used=[RUBY]),
    E(32, "corroborated_manifest", PANDAS, md("eda", "Analysis with pandas."), files={"requirements.txt": "pandas==2.2.0\n"},
      concepts={PANDAS: USE}, used=[PANDAS]),
    E(33, "corroborated_docker", DOCKER, md("svc", "Containerised with Docker."), files={"Dockerfile": "FROM alpine:3.20\n"},
      concepts={DOCKER: USE}, used=[DOCKER]),
    E(34, "readme_only_use", REACT, md("site", "The frontend uses React."), concepts={REACT: USE}, used=[REACT]),
    E(35, "multi_repo_use", RUST, None, repos=[repo(md("crate-a", "A Rust crate."), name="crate-a"),
                                              repo(md("crate-b", "A Rust crate."), name="crate-b")],
      concepts={RUST: USE}, used=[RUST]),
    E(36, "conflicting", EXPRESS, md("gateway", "Built with Express."),
      files={"package.json": '{"dependencies": {"koa": "^2.15.0"}}'}, concepts={EXPRESS: AMB}, uncertain=[EXPRESS],
      note="README claims Express; the manifest lists only Koa"),
    E(37, "ordinary_readme_corroborated_use", RUST, md("toolbox", "Keeps tools free of rust."), languages={"Rust": 9000},
      concepts={RUST: ORD}, used=[RUST]),
    E(38, "pair_ordinary_sentence_initial", EXPRESS, md("checkout", "Express checkout for the shop."),
      concepts={EXPRESS: ORD}, pair="express-initial"),
    E(39, "pair_use_sentence_initial", EXPRESS, md("logger", "Express middleware for logging."), concepts={EXPRESS: USE},
      used=[EXPRESS], pair="express-initial"),
    E(40, "pair_use", SWIFT, md("knots", "A guide written in Swift for iOS developers."), concepts={SWIFT: USE},
      used=[SWIFT], pair="swift-guide"),
]


def _write(controls: list[dict], split: str, label_timing: str) -> None:
    out, freeze = OUT_DIR / f"readme_context_controls_{split}.json", OUT_DIR / f"{split}_hash_freeze.json"
    doc = {
        "schema_version": 1, "milestone": "M11-G22-R2 (README evidence context and confidence)", "split": split,
        "provenance": "author-created synthetic READMEs and repository artifacts; no real README, posting, employer or "
                      "private material",
        "authorship_disclosure": ("Written by the same researcher who designs the G22-R2 candidate policies; NOT an "
                                  "independent validation set."),
        "label_timing": label_timing,
        "label_classes": ["ordinary", "reference", "use", "historical", "future", "negated", "ambiguous"],
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
        "note": "Labels frozen BEFORE any GitScore parser, extractor, matcher or G22-R2 policy ran on this set. NOT "
                "registered in the canonical manifest (pending authorization).",
    }, indent=2) + "\n").encode("utf-8"))
    print(f"wrote {len(controls)} {split} controls; sha256={gi.sha256(payload)} bytes={len(payload)}")


def main() -> None:
    ids = [c["id"] for c in DEV + EVAL]
    assert len(ids) == len(set(ids))
    classes = {"ordinary", "reference", "use", "historical", "future", "negated", "ambiguous"}
    for c in DEV + EVAL:
        assert set(c["concepts"].values()) <= classes, c["id"]
        assert c["probe"] in c["concepts"] or c["probe"] in c["used"], c["id"]
        assert not set(c["used"]) & set(c["uncertain"]), c["id"]
    _write(DEV, "dev", "labels frozen before any production run; G22-R2 policies are designed against this set")
    _write(EVAL, "eval", "authored with DEV but kept unrun until the G22-R2 policy design freeze; same author, so "
                         "only weakly held out")


if __name__ == "__main__":
    main()
