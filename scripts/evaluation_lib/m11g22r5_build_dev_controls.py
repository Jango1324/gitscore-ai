"""Milestone 11-G22-R5 -- synthetic DEVELOPMENT controls for attribution-aware README evidence (POLICY-AUTHOR written).

    python scripts/evaluation_lib/m11g22r5_build_dev_controls.py

DEV material only: written by the same author who composes the R5 research candidates, so it can never count as
validation. Written and hash-frozen BEFORE any R5 candidate ran on it (the freeze record is written once and never
overwritten). Focus: project ATTRIBUTION (third-party projects / documentation, references and comparisons,
historical use, future / hypothetical use, quotations), Markdown structure (setext headings, sections, nested lists,
blockquotes, fenced code, link references) and MULTI-OCCURRENCE behaviour (invalid then valid, valid then invalid,
several invalid, mixed history and current use, README plus artifacts) -- deliberately across NON-ambiguous aliases
too (FastAPI, Docker, PostgreSQL, Kubernetes, TensorFlow, Redis, TypeScript, Next.js, CUDA, ...).

Schema: the G22-R2 harness control schema (`m11g22r2_harness.run_control`), plus `scenario` (the Phase-4 pattern).
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
OUT = REPO_ROOT / "evaluation" / "m11g22r5"
CLASSES = {"use", "ordinary", "reference", "historical", "future", "negated", "ambiguous"}

PY, RS, RB, JV, TS, JS = ("language.python", "language.rust", "language.ruby", "language.java", "language.typescript",
                          "language.javascript")
RE, RN, EX, FL, FA = "framework.react", "framework.react_native", "framework.express", "framework.flask", "framework.fastapi"
NX, PT, TF, PD = "framework.nextjs", "ml.framework.pytorch", "ml.framework.tensorflow", "data.library.pandas"
DK, K8, PG, RD, CU, AW = ("infra.docker", "infra.kubernetes", "database.postgresql", "database.redis", "platform.cuda",
                          "cloud.aws")
GO, SW, CPP, SH = "language.go", "language.swift", "language.cpp", "language.shell"

# (family, scenario, probe, readme, concepts, used, uncertain, languages, files, note)
_CASES = [
    # ---- 1. third-party projects / documentation ----
    ("third_party", "invalid_only", FA, "# minirest\n\nA tiny REST router for Go, inspired by FastAPI.\n",
     {FA: "reference"}, [], [], {}, {}, ""),
    ("third_party", "invalid_only", PT, "# tensor-cheatsheet\n\nPrintable cheat sheet of common PyTorch tensor "
     "operations, typeset in LaTeX.\n", {PT: "reference"}, [], [], {}, {}, "notes about someone else's software"),
    ("third_party", "invalid_only", K8, "# k8s-notes\n\nMy study notes on how the Kubernetes scheduler places pods.\n",
     {K8: "reference"}, [], [], {}, {}, ""),
    ("third_party", "invalid_only", PG, "# pg-docs-es\n\nSpanish translation of the official PostgreSQL documentation.\n",
     {PG: "reference"}, [], [], {}, {}, ""),
    ("third_party", "invalid_only", RD, "# keyval\n\nAn embedded key-value store for Go; a drop-in replacement for "
     "Redis in tests.\n", {RD: "reference"}, [], [], {}, {}, ""),
    ("third_party", "invalid_only", TF, "# vision-zoo\n\nA C++ inference runtime. Models trained elsewhere are converted "
     "with a TensorFlow tool maintained by another team.\n", {TF: "reference", CPP: "use"}, [CPP], [], {}, {}, ""),
    ("third_party", "bindings_by_others", PY, "# libfoo\n\nA C library for parsing foo files.\n\n## Language bindings\n\n"
     "- [pyfoo](https://example.invalid/pyfoo) - Python\n- [rbfoo](https://example.invalid/rbfoo) - Ruby\n",
     {PY: "reference", RB: "reference"}, [], [], {"C": 9000}, {}, "other people's bindings"),
    ("third_party", "bindings_by_others_linkref", RB, "# libbar\n\nA C library. Bindings like [rugged-bar][1] (Ruby) are "
     "maintained by the community.\n\n[1]: https://example.invalid/rugged-bar\n", {RB: "reference"}, [], [],
     {"C": 9000}, {}, "link-reference style"),
    ("third_party", "bindings_in_repo", PY, "# libbaz\n\nA C library for parsing baz files.\n\n## Bindings\n\nThe Python "
     "bindings in `bindings/python` are part of this repository and tested in CI.\n", {PY: "use"}, [PY], [],
     {"C": 9000, "Python": 2000}, {}, "bindings maintained here"),
    # ---- 2. references and comparisons ----
    ("comparison", "invalid_only", EX, "# tinyroute\n\nA router for Deno; roughly twice as fast as Express in our "
     "benchmarks.\n", {EX: "reference"}, [], [], {}, {}, ""),
    ("comparison", "invalid_only", NX, "# pagekit\n\nA static site generator written in Go. Think of it as Next.js "
     "without the JavaScript runtime.\n", {NX: "reference", JS: "reference"}, [], [], {}, {}, ""),
    ("comparison", "invalid_only", FL, "# webby\n\nA web framework for Nim, similar to Flask.\n", {FL: "reference"}, [],
     [], {}, {}, ""),
    ("comparison", "like_with_use_verb", RE, "# board\n\nBuilt with modern tools like React and Vite.\n", {RE: "use"},
     [RE], [], {}, {}, "use verb opens the clause"),
    # ---- 3. historical ----
    ("historical", "invalid_only", FL, "# booking\n\nOriginally a Flask app; it now runs on FastAPI.\n",
     {FL: "historical", FA: "use"}, [FA], [], {}, {}, "migration: old historical, new current"),
    ("historical", "current_after_migration", FA, "# booking\n\nOriginally a Flask app; it now runs on FastAPI.\n",
     {FL: "historical", FA: "use"}, [FA], [], {}, {}, "same README, current target"),
    ("historical", "invalid_only", RD, "# sessions\n\nWe moved off Redis in 2024; sessions now live in the database.\n",
     {RD: "historical"}, [], [], {}, {}, ""),
    ("historical", "invalid_only", TF, "# counter\n\nUntil v2.0 this package depended on TensorFlow for its tiny "
     "classifier; the model is now plain NumPy.\n", {TF: "historical"}, [], [], {}, {}, ""),
    ("historical", "mixed_hist_current", PG, "# ledger\n\nThe first prototype used SQLite. Production data now lives in "
     "PostgreSQL, and the old PostgreSQL 12 cluster was upgraded in place.\n", {PG: "use"}, [PG], [], {}, {},
     "current use first; a later 'old PostgreSQL' mention"),
    # ---- 4. future / hypothetical ----
    ("future", "invalid_only", K8, "# deployer\n\nRuns as a single binary. We plan to add Kubernetes manifests once the "
     "API settles.\n", {K8: "future"}, [], [], {}, {}, ""),
    ("future", "invalid_only", CU, "# raytrace\n\nA CPU ray tracer. CUDA support is on the roadmap.\n",
     {CU: "future"}, [], [], {}, {}, ""),
    ("future", "task_list", TS, "# toolkit\n\n## TODO\n\n- [x] CLI\n- [ ] TypeScript type definitions\n",
     {TS: "future"}, [], [], {}, {}, ""),
    ("future", "hypothetical", GO, "# api-spec\n\nOpenAPI spec for our service. Clients can be generated for Golang "
     "or Kotlin.\n", {GO: "future", "language.kotlin": "future"}, [], [], {}, {}, ""),
    ("future", "task_done", TS, "# toolkit\n\n## Roadmap\n\n- [x] TypeScript type definitions\n- [ ] Web UI\n",
     {TS: "use"}, [TS], [], {}, {}, "completed roadmap item is current"),
    # ---- 5. quotations ----
    ("quotation", "invalid_only", RD, "# notices\n\nThird-party notices.\n\nFrom the cachelib README:\n\n> cachelib "
     "stores entries in Redis and is MIT licensed.\n", {RD: "reference"}, [], [], {}, {}, ""),
    ("quotation", "project_quote", PY, "# fastcsv\n\nStreaming CSV tools.\n\n> **Note:** this project requires Python "
     "3.11 or newer.\n", {PY: "use"}, [PY], [], {}, {}, "a project note in a blockquote is valid"),
    ("quotation", "testimonial", DK, "# shipit\n\nOne-command deploys.\n\n## What users say\n\n> 'Replaced our pile of "
     "Docker scripts in an afternoon.'\n", {DK: "reference"}, [], [], {}, {}, "the user's Docker scripts"),
    # ---- 6. multi-occurrence patterns ----
    ("multi_mention", "invalid_then_valid", RS, "# grepx\n\nA faster grep, inspired by ripgrep's Rust implementation. "
     "This tool is also written in Rust.\n", {RS: "use"}, [RS], [], {}, {}, ""),
    ("multi_mention", "valid_then_invalid", DK, "# webapp\n\nShips as a Docker image. Unlike the old Docker Compose v1 "
     "setup, deploys are one command.\n", {DK: "use"}, [DK], [], {}, {}, ""),
    ("multi_mention", "several_invalid", FA, "# minirest\n\nInspired by FastAPI. Benchmarks against FastAPI are in "
     "`bench/`. A FastAPI-style decorator API is planned.\n", {FA: "reference"}, [], [], {}, {}, ""),
    ("multi_mention", "several_valid", PG, "# shop\n\nUses PostgreSQL for orders. Migrations target PostgreSQL 16.\n",
     {PG: "use"}, [PG], [], {}, {}, ""),
    ("multi_mention", "invalid_other_section", RS, "# grepx\n\nA faster grep.\n\n## Related projects\n\n- ripgrep "
     "(Rust)\n\n## Development\n\nThis tool is written in Rust; run `cargo build`.\n", {RS: "use"}, [RS], [], {}, {}, ""),
    ("multi_mention", "valid_in_project_quote", RD, "# queue\n\nA job queue.\n\n> **Requirement:** this service needs "
     "a running Redis 7 instance.\n\nInspired by Sidekiq.\n", {RD: "use"}, [RD], [], {}, {}, ""),
    ("multi_mention", "mixed_hist_current", PY, "# crawler\n\nPreviously a Python script; ported to Golang in 2024. "
     "The Python test harness in `tests/` is still used in CI.\n", {PY: "use", GO: "use"}, [PY, GO], [], {}, {}, ""),
    ("multi_mention", "readme_invalid_plus_artifact", FL, "# api\n\nOriginally a Flask app.\n", {FL: "historical"},
     [FL], [], {}, {"requirements.txt": "flask==3.0.0\n"}, "README history, but the manifest still lists flask"),
    ("multi_mention", "overlap_then_valid", RE, "# app\n\nA React Native mobile app. The web dashboard uses React.\n",
     {RN: "use", RE: "use"}, [RN, RE], [], {}, {}, "production loses React through overlap resolution (8D.1)"),
    # ---- 7. Markdown structure ----
    ("markdown", "setext_after_related", RS, "# grepx\n\nRelated projects\n----------------\n\n- ripgrep (Rust)\n\n"
     "Development\n-----------\n\nThis tool is written in Rust.\n", {RS: "use"}, [RS], [], {}, {}, "setext headings"),
    ("markdown", "atx_related_then_setext_dev", RS, "# grepx\n\n## Related projects\n\n- ripgrep (Rust)\n\n"
     "Development\n-----------\n\nThis tool is written in Rust.\n", {RS: "use"}, [RS], [], {}, {},
     "production keeps the 'related projects' section open across the setext heading"),
    ("markdown", "setext_related_only", RS, "# grepx\n\nA faster grep in Go.\n\nRelated projects\n================\n\n"
     "- ripgrep (Rust)\n", {RS: "reference"}, [], [], {}, {}, "setext related section"),
    ("markdown", "nested_list_bindings", JV, "# libgit-lite\n\nLanguage Bindings\n=================\n\n* Java\n    * "
     "jgit-lite <https://example.invalid/jgit-lite>\n* Rust\n    * git-lite-rs <https://example.invalid/glrs>\n",
     {JV: "reference", RS: "reference"}, [], [], {"C": 9000}, {}, "libgit2-style list"),
    ("markdown", "fence_other_project", PD, "# report-tool\n\nA report generator written in Go.\n\nUpstream example "
     "(from the polars docs):\n\n```python\nimport pandas as pd\n```\n", {PD: "reference", PY: "reference"}, [], [],
     {}, {}, "code copied from another project's docs"),
    ("markdown", "fence_install_own", FA, "# notes-api\n\n## Install\n\n```bash\npip install fastapi uvicorn\n```\n",
     {FA: "use", SH: "ambiguous"}, [FA], [SH], {}, {}, "install command for this project"),
    ("markdown", "copied_upstream_readme", NX, "# my-blog\n\nPersonal blog, built with Hugo.\n\n---\n\n*The section "
     "below is copied from the upstream theme's README.*\n\n> This theme also ships a Next.js starter.\n",
     {NX: "reference"}, [], [], {}, {}, "copied upstream documentation"),
    ("markdown", "subsection_of_alternatives", FA, "# minirest\n\n## Alternatives\n\n### FastAPI\n\nMore mature, but "
     "Python-only.\n", {FA: "reference", PY: "reference"}, [], [], {}, {}, "subsection of an alternatives section"),
    # ---- 8. plain genuine use (recall guards) ----
    ("use", "valid_only", DK, "# hello\n\nRun it with `docker compose up`.\n", {DK: "use"}, [DK], [], {}, {}, ""),
    ("use", "valid_only", K8, "# chart\n\nHelm chart that deploys the app to Kubernetes.\n", {K8: "use"}, [K8], [], {},
     {}, ""),
    ("use", "valid_only", AW, "# infra\n\nTerraform modules for our AWS accounts.\n", {AW: "use"}, [AW], [], {}, {}, ""),
    ("use", "valid_only", CU, "# kernels\n\nHand-written CUDA kernels for sparse attention.\n", {CU: "use"}, [CU], [],
     {}, {}, ""),
    ("use", "valid_only", TF, "# tfserve\n\nServes TensorFlow models over gRPC.\n", {TF: "use"}, [TF], [], {}, {}, ""),
    ("use", "valid_only", SW, "# keychainify\n\nOne-line Swift API for the keychain.\n", {SW: "use"}, [SW], [], {}, {},
     ""),
    ("use", "valid_than_trap", PY, "# fastjson\n\nA JSON parser written in Python, faster than the standard library "
     "on large files.\n", {PY: "use"}, [PY], [], {}, {}, "'than' after the alias must not matter"),
    ("use", "valid_old_trap", PG, "# migrator\n\nUpgrades databases from the previous PostgreSQL major version to the "
     "next one; requires PostgreSQL 15+.\n", {PG: "use"}, [PG], [], {}, {}, "'previous PostgreSQL' then a requirement"),
]


def build() -> dict:
    known = {c.concept_id for c in default_registry().all_concepts()}
    controls = []
    for i, (family, scenario, probe, readme, concepts, used, uncertain, langs, files, note) in enumerate(_CASES, 1):
        assert probe in known and set(concepts) <= known and set(concepts.values()) <= CLASSES, i
        assert set(used) <= known and set(uncertain) <= known, i
        controls.append({"id": f"m11g22r5-dev-{i:03d}", "split": "dev", "family": family, "scenario": scenario,
                         "probe": probe, "pair": None,
                         "repos": [{"name": "r1", "readme": readme, "languages": langs, "files": files}],
                         "concepts": concepts, "used": used, "uncertain": uncertain, "note": note})
    return {"schema_version": 1, "milestone": "M11-G22-R5 (attribution-aware README evidence research)",
            "split": "dev", "authorship": "written by the R5 policy author; DEVELOPMENT data only, never validation",
            "label_timing": "labels hash-frozen BEFORE any R5 candidate was run on this set",
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
        "frozen_file": "evaluation/m11g22r5/dev_controls.json", "sha256": sha, "sha256_lf_normalized": sha,
        "length_bytes": len(data), "canonical_contract": gi.CONTRACT,
        "frozen_at_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Policy-author DEV controls, frozen BEFORE any R5 candidate ran on them. DEV only. NOT registered in "
                "the canonical manifest (pending authorization).",
    }, indent=2) + "\n").encode("utf-8"))
    print("dev", len(_CASES), sha)


if __name__ == "__main__":
    main()
