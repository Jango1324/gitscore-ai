"""Milestone 11-G22-R4 -- synthetic DEVELOPMENT near-neighbour controls (written by the POLICY AUTHOR).

    python scripts/evaluation_lib/m11g22r4_build_dev_controls.py

These controls are DEV material only: they were written by the same author who designs the R4 research policies, so
they can never count as validation. They were written and hash-frozen BEFORE any R4 candidate policy was run on them
(the freeze record is written once and never overwritten), and every later policy iteration that used them is
disclosed in `evaluation/m11g22r4/policy_design_freeze.json`.

Schema: the G22-R2 harness control schema (`m11g22r2_harness.run_control`): `probe` is scored against
"Experience with <display>."; `concepts` labels every registry concept mentioned in the README text with one class of
use / ordinary / reference / historical / future / negated / ambiguous; `used` is README use claims plus artifact
rules (manifest entries, language bytes >= 5%, Docker file presence); `uncertain` is excluded from truth.
Several controls share one README with different probes (marked by `pair`), so both senses of a near-neighbour are
measured on identical text.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parents[1] / "src"))

import gold_integrity as gi  # noqa: E402
from gitscore.concepts.registry import default_registry  # noqa: E402

REPO_ROOT = _HERE.parents[1]
OUT = REPO_ROOT / "evaluation" / "m11g22r4"
CLASSES = {"use", "ordinary", "reference", "historical", "future", "negated", "ambiguous"}

PY, RS, RB, JV, SW, SH = ("language.python", "language.rust", "language.ruby", "language.java", "language.swift",
                          "language.shell")
RE, EX, FL, TO, PD = ("framework.react", "framework.express", "framework.flask", "ml.framework.pytorch",
                      "data.library.pandas")
FA, DK, GO = "framework.fastapi", "infra.docker", "language.go"

# (family, probe, pair, readme, concepts, used, uncertain, languages, files, note)
_CASES = [
    # ---- named near-neighbour pairs (Phase 4 list) ----
    ("near_pair", RS, "express-train", "# railsim\n\nExpress train simulator built in Rust. Models a single line with "
     "stopping and fast services.\n", {EX: "ordinary", RS: "use"}, [RS], [], {}, {}, "Rust is the implementation"),
    ("near_pair", EX, "express-train", "# railsim\n\nExpress train simulator built in Rust. Models a single line with "
     "stopping and fast services.\n", {EX: "ordinary", RS: "use"}, [RS], [], {}, {}, "'Express train' is transit"),
    ("near_pair", EX, "express-train-2", "# platform-board\n\nDeparture board for local and express trains at one "
     "station.\n", {EX: "ordinary"}, [], [], {}, {}, ""),
    ("near_pair", PY, "rust-removal", "# derust\n\nRust removal tool written in Python: photograph a part and it "
     "estimates how much sanding is needed.\n", {RS: "ordinary", PY: "use"}, [PY], [], {}, {}, ""),
    ("near_pair", RS, "rust-removal", "# derust\n\nRust removal tool written in Python: photograph a part and it "
     "estimates how much sanding is needed.\n", {RS: "ordinary", PY: "use"}, [PY], [], {}, {}, "rust = corrosion"),
    ("near_pair", RS, "rust-free", "# gate-log\n\nMaintenance log that keeps the farm gates painted and free of "
     "rust.\n", {RS: "ordinary"}, [], [], {}, {}, ""),
    ("near_pair", JV, "java-coffee", "# brewdesk\n\nCoffee ordering application written in Java for small cafes.\n",
     {JV: "use"}, [JV], [], {}, {}, ""),
    ("near_pair", JV, "java-coffee-amb", "# brewdesk\n\nJava coffee ordering application for small cafes.\n",
     {JV: "ambiguous"}, [], [JV], {}, {}, "'Java coffee' could be the bean origin or the language"),
    ("near_pair", JV, "java-island", "# ferry-notes\n\nJava is an island; these notes list the ferries that reach "
     "it.\n", {JV: "ordinary"}, [], [], {}, {}, ""),
    ("near_pair", RB, "ruby-gem", "# gemcat\n\nA Ruby gemstone catalog built in Ruby, with a small Sinatra front "
     "end.\n", {RB: "use"}, [RB], [], {}, {}, "second Ruby is the language"),
    ("near_pair", RB, "ruby-gem-2", "# gemcat\n\nA ruby gemstone photographed under four kinds of light.\n",
     {RB: "ordinary"}, [], [], {}, {}, ""),
    ("near_pair", PY, "pure-python", "# tomlette\n\nPure Python TOML parser with no dependencies.\n", {PY: "use"},
     [PY], [], {}, {}, ""),
    ("near_pair", PY, "python-snake", "# vivarium\n\nThe keeper feeds the python every ten days and logs its "
     "weight.\n", {PY: "ordinary"}, [], [], {}, {}, ""),
    ("near_pair", SW, "swift-api", "# keychainify\n\nOne-line Swift API for storing secrets in the keychain.\n",
     {SW: "use"}, [SW], [], {}, {}, ""),
    ("near_pair", SW, "swift-response", "# triage\n\nA swift response to every bug report, routed to the right "
     "person.\n", {SW: "ordinary"}, [], [], {}, {}, ""),
    ("near_pair", RE, "react-ui", "# fleetboard\n\nReact-based UI for monitoring delivery vans.\n", {RE: "use"}, [RE],
     [], {}, {}, ""),
    ("near_pair", RE, "react-quick", "# fleetboard\n\nLets dispatchers react quickly when a delivery van breaks "
     "down.\n", {RE: "ordinary"}, [], [], {}, {}, ""),
    ("near_pair", FL, "flask-app", "# glassware\n\nFlask application that tracks which lab glassware is on loan.\n",
     {FL: "use"}, [FL], [], {}, {}, ""),
    ("near_pair", FL, "flask-glass", "# glassware\n\nRecords which lab flask is on which bench, and when it was last "
     "washed.\n", {FL: "ordinary"}, [], [], {}, {}, ""),
    ("near_pair", TO, "torch-train", "# tinyvision\n\nTorch training framework for small vision models.\n",
     {TO: "use"}, [TO], [], {}, {}, ""),
    ("near_pair", TO, "torch-carry", "# nightshift\n\nRota app for night shifts; remember to carry a torch on the "
     "loading dock.\n", {TO: "ordinary"}, [], [], {}, {}, ""),
    ("near_pair", RS, "rust-bindings-gen", "# ccodec\n\nA C audio codec. Bindings for Rust can be generated with "
     "bindgen.\n", {RS: "future"}, [], [], {"C": 9000}, {}, "hypothetical bindings"),
    ("near_pair", RS, "rust-bindings-real", "# ccodec\n\nA C audio codec. The Rust bindings in `bindings/rust` are "
     "maintained here and published to crates.io.\n", {RS: "use"}, [RS], [], {"C": 9000}, {}, "bindings in repo"),
    # ---- seen named phrases (kept as DEV) ----
    ("named_phrase", RS, None, "# pixdiff\n\nFast image diffing in Rust.\n", {RS: "use"}, [RS], [], {}, {}, ""),
    ("named_phrase", PY, None, "# audiokit\n\nShips a small python plotting helper for the waveforms.\n",
     {PY: "use"}, [PY], [], {}, {}, ""),
    ("named_phrase", TO, None, "# catdog\n\nImage classifier trained with torch.\n", {TO: "use"}, [TO], [], {}, {}, ""),
    ("named_phrase", RS, None, "# kvlite\n\nA tiny key-value store in Rust.\n", {RS: "use"}, [RS], [], {}, {}, ""),
    ("named_phrase", PD, None, "# salesviz\n\nAnalysis with pandas and a few matplotlib charts.\n", {PD: "use"}, [PD],
     [], {}, {}, ""),
    # ---- verb / adjective / name senses ----
    ("ordinary", EX, None, "# feedback-wall\n\nA place where students can express what they found hardest.\n",
     {EX: "ordinary"}, [], [], {}, {}, ""),
    ("ordinary", RE, None, "# titration\n\nSimulates how bases react with acids, one drop at a time.\n",
     {RE: "ordinary"}, [], [], {}, {}, ""),
    ("ordinary", RB, None, "# pets\n\nPhotos of my dog, Ruby, and her favourite walks.\n", {RB: "ordinary"}, [], [],
     {}, {}, ""),
    ("ordinary", SH, None, "# tidepool\n\nIdentify a crab, a starfish or a shell from one photo.\n",
     {SH: "ordinary"}, [], [], {}, {}, ""),
    ("ordinary", PD, None, "# zoo-feed\n\nFeeding rota for the giant pandas and the otters.\n", {PD: "ordinary"},
     [], [], {}, {}, ""),
    ("ordinary", SH, None, "# budget\n\nNo need to shell out for an expensive licence.\n", {SH: "ordinary"}, [], [],
     {}, {}, ""),
    # ---- technical uses that a positive-cue guard tends to drop ----
    ("use_terse", JV, None, "# ledgerline\n\nDouble-entry bookkeeping for Java 21.\n", {JV: "use"}, [JV], [], {}, {},
     ""),
    ("use_terse", RE, None, "# statusboard\n\nReact 18 dashboard for build health.\n", {RE: "use"}, [RE], [], {}, {},
     ""),
    ("use_terse", SW, None, "# csvkit-swift\n\nStreaming CSV reader (Swift) for large exports.\n", {SW: "use"}, [SW],
     [], {}, {}, ""),
    ("use_terse", RB, None, "# slugs\n\nTiny Ruby gem that turns titles into URL slugs.\n", {RB: "use"}, [RB], [],
     {}, {}, ""),
    ("use_terse", EX, None, "# authkit\n\nSession middleware for Express.\n", {EX: "use"}, [EX], [], {}, {}, ""),
    ("use_terse", SH, None, "# dotfiles\n\nMy shell setup: aliases, prompt and a few helper functions.\n",
     {SH: "use"}, [SH], [], {}, {}, ""),
    # ---- non-use frames ----
    ("negated", RE, None, "# onefile\n\nA to-do list in one HTML file, deliberately without React.\n",
     {RE: "negated", "language.html": "use"}, ["language.html"], [], {}, {}, ""),
    ("negated", PY, None, "# shipit\n\nSingle static binary; Python is not required on the target machine.\n",
     {PY: "negated"}, [], [], {}, {}, ""),
    ("historical", FL, None, "# booking\n\nOriginally a Flask app; it now runs on FastAPI.\n",
     {FL: "historical", FA: "use"}, [FA], [], {}, {}, ""),
    ("historical", RB, None, "# crawler\n\nPorted from Ruby to Go in 2024; the old Ruby code was removed.\n",
     {RB: "historical"}, [], [], {}, {}, "Go itself is not a README alias"),
    ("future", SW, None, "# notes\n\nAn Android notes app. A Swift port is planned for next year.\n",
     {SW: "future"}, [], [], {}, {}, ""),
    ("future", RS, None, "# imgtool\n\n## Roadmap\n\n- [x] PNG support\n- [ ] Rust rewrite of the decoder\n",
     {RS: "future"}, [], [], {}, {}, ""),
    ("comparison", EX, None, "# tinyroute\n\nA router for Deno; roughly twice as fast as Express in our "
     "benchmarks.\n", {EX: "reference"}, [], [], {}, {}, ""),
    ("comparison", PD, None, "# logframe\n\nThink of it as pandas for log files, but streaming.\n",
     {PD: "reference"}, [], [], {}, {}, ""),
    ("third_party", PY, None, "# libfoo\n\nA C library for parsing foo files.\n\n## Bindings by the community\n\n"
     "- [pyfoo](https://example.invalid/pyfoo) - Python bindings\n- [rbfoo](https://example.invalid/rbfoo) - Ruby "
     "bindings\n", {PY: "reference", RB: "reference"}, [], [], {"C": 9000}, {}, "other people's bindings"),
    ("quotation", RS, None, "# notices\n\nThird-party licence notices.\n\nFrom the fastzip README:\n\n> fastzip is "
     "written in Rust and is MIT licensed.\n", {RS: "reference"}, [], [], {}, {}, ""),
    # ---- sections and multiple mentions ----
    ("multi_mention", RS, None, "# grepx\n\nA faster grep.\n\n## Related projects\n\n- ripgrep (Rust)\n\n"
     "## Development\n\nThis tool is written in Rust; run `cargo build`.\n", {RS: "use"}, [RS], [], {}, {}, ""),
    ("multi_mention", RE, None, "# pager\n\nHelps on-call teams react to alerts before customers notice. The "
     "dashboard is a React app.\n", {RE: "use"}, [RE], [], {}, {}, "first mention verb, second use"),
    ("multi_mention", EX, None, "# parcels-api\n\nTracks express and standard parcels. The API is an Express server "
     "on Node 20.\n", {EX: "use"}, [EX], [], {}, {}, ""),
    # ---- artifacts ----
    ("artifacts", FL, None, "# labtimer\n\nShake the flask, start the timer, log the colour change.\n",
     {FL: "ordinary"}, [FL], [], {}, {"requirements.txt": "flask==3.0.0\n"}, "used via manifest only"),
    ("artifacts", RS, None, "# chainlube\n\nReminds you to keep the chain free of rust.\n", {RS: "ordinary"}, [RS],
     [], {"Rust": 9000}, {}, "used via language stats only"),
    ("artifacts", FL, None, "# hello-flask\n\nRuns as a Flask app inside Docker: `docker compose up`.\n",
     {FL: "use", DK: "use"}, [FL, DK], [], {}, {"docker-compose.yml": "services: {}\n"}, ""),
    ("artifacts", PD, None, "# csvtidy\n\nThis project does not use pandas.\n", {PD: "negated"}, [PD], [], {},
     {"requirements.txt": "pandas==2.2.0\n"}, "conflict: manifest proves use"),
    ("artifacts", SW, None, "# skyline\n\nA weather widget written in Swift.\n", {SW: "use"}, [SW], [],
     {"Python": 9000}, {}, "README claim counts as use even though stats disagree"),
    # ---- non-ambiguous aliases (must never change) ----
    ("non_ambiguous", FA, None, "# minirest\n\nInspired by FastAPI, but for Go.\n", {FA: "reference"}, [], [], {},
     {}, "readme:v4 extracts it; the R4 guard must not change non-ambiguous evidence"),
    ("non_ambiguous", DK, None, "# runner\n\nNo Docker needed.\n", {DK: "negated"}, [], [], {}, {},
     "readme:v4 extracts it; non-ambiguous evidence must be unchanged"),
]


def build() -> dict:
    known = {c.concept_id for c in default_registry().all_concepts()}
    controls = []
    for i, (family, probe, pair, readme, concepts, used, uncertain, langs, files, note) in enumerate(_CASES, 1):
        assert probe in known and set(concepts) <= known and set(concepts.values()) <= CLASSES, i
        assert set(used) <= known and set(uncertain) <= known, i
        controls.append({"id": f"m11g22r4-dev-{i:03d}", "split": "dev", "family": family, "probe": probe,
                         "pair": pair, "repos": [{"name": "r1", "readme": readme, "languages": langs, "files": files}],
                         "concepts": concepts, "used": used, "uncertain": uncertain, "note": note})
    return {"schema_version": 1, "milestone": "M11-G22-R4 (high-recall README evidence guard research)",
            "split": "dev",
            "authorship": "written by the R4 policy author; DEVELOPMENT data only, never validation",
            "label_timing": "labels hash-frozen BEFORE any R4 candidate policy was run on this set",
            "label_classes": sorted(CLASSES), "controls": controls}


def main() -> None:
    target, record = OUT / "dev_controls.json", OUT / "dev_hash_freeze.json"
    if target.exists() or record.exists():
        raise SystemExit("REFUSING to overwrite an existing freeze")
    data = (json.dumps(build(), indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    sha = gi.sha256(gi.canonical_bytes(data))
    record.write_bytes((json.dumps({
        "frozen_file": "evaluation/m11g22r4/dev_controls.json", "sha256": sha, "sha256_lf_normalized": sha,
        "length_bytes": len(data), "canonical_contract": gi.CONTRACT,
        "frozen_at_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Policy-author DEV controls, frozen BEFORE any R4 candidate ran on them. DEV only. NOT registered in "
                "the canonical manifest (pending authorization).",
    }, indent=2) + "\n").encode("utf-8"))
    print("dev", len(_CASES), sha)


if __name__ == "__main__":
    main()
