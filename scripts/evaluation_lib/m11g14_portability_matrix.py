"""Milestone 11-G14 -- cross-platform freeze-verification matrix.

    python scripts/evaluation_lib/m11g14_portability_matrix.py [--overlay PATH ...] [--out FILE] [--skip-full-suite]

Builds throwaway clean checkouts (local clones, no network) of HEAD --
optionally plus an explicit overlay of working-tree files committed in a
throwaway staging repository -- under `core.autocrlf=true` and
`core.autocrlf=false`, and in each one measures:

1. every tracked freeze record whose frozen file is tracked: raw-hash
   match, and whether any mismatch is a newline-only conversion (the
   checked-out bytes are identical to the committed blob once CRLF is
   mapped to LF) or a genuine content difference;
2. every historical evaluation-script freeze verifier, executed in the
   clone;
3. the hash-verifying test nodes;
4. the full backend suite (unless `--skip-full-suite`).

Private, untracked corpora are never copied into a clone. Nothing in this
repository is modified. Output is a JSON report.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ("true", "false")

# (label, module directory relative to repo, module name, callable)
SCRIPT_VERIFIERS = (
    ("G1", "scripts", "evaluate_m11g1_alternative_requirements", "_verify_hash_freeze"),
    ("G2", "scripts", "evaluate_m11g2_section_context", "_verify_hash_freeze"),
    ("G2-strategy", "scripts", "evaluate_m11g2_strategy_comparison", "_verify_hash_freeze"),
    ("G3", "scripts", "evaluate_m11g3_end_to_end", "_verify_hash_freeze"),
    ("G4", "scripts", "evaluate_m11g4_admission_recovery", "_verify_hash_freeze"),
    ("G6-phase1", "scripts/evaluation_lib", "m11g6_phase1_current_behavior", "main"),
    ("G6-phase3", "scripts/evaluation_lib", "m11g6_phase3_candidate_fix_simulation", "main"),
    ("G7-phase1", "scripts/evaluation_lib", "m11g7_phase1_current_behavior", "main"),
    ("G7-phase3", "scripts/evaluation_lib", "m11g7_phase3_candidate_fix_simulation", "main"),
    ("G12", "scripts", "evaluate_m11g12_validator_hardening", "load_frozen_controls"),
    ("G13", "scripts", "evaluate_m11g13_generalization", "load_frozen_controls"),
)

HASH_TEST_FILES = (
    "tests/test_m11g6_heading_classification.py",
    "tests/test_m11g7_section_boundary_integrity.py",
    "tests/test_m11g12_validator_hardening.py",
    "tests/test_m11g13_generalization_and_or_contract.py",
)


def _run(args, cwd, check=True):
    return subprocess.run(args, cwd=cwd, check=check, capture_output=True, text=True)


def tracked_freezes(root: Path) -> list[dict]:
    out = []
    for path in _run(["git", "ls-files", "evaluation"], root).stdout.split():
        if not (path.endswith(".json") and "freeze" in Path(path).name):
            continue
        data = json.loads((root / path).read_text(encoding="utf-8"))
        target = data.get("frozen_file") if isinstance(data, dict) else None
        if target and data.get("sha256") and _run(["git", "ls-files", target], root).stdout.strip():
            out.append({"record": path, "file": target, "sha256": data["sha256"]})
    return out


def _summary(stdout: str) -> str:
    lines = [ln for ln in stdout.strip().splitlines() if re.search(r"\d+ (passed|failed|error)", ln)]
    return lines[-1].strip() if lines else stdout.strip().splitlines()[-1] if stdout.strip() else ""


def build_stage(tmp: Path, overlay: list[str]) -> Path:
    stage = tmp / "stage"
    _run(["git", "clone", "--quiet", "--no-hardlinks", str(REPO_ROOT), str(stage)], tmp)
    if overlay:
        for rel in overlay:
            src = REPO_ROOT / rel
            dst = stage / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        _run(["git", "add", "--", *overlay], stage)
        _run(["git", "-c", "user.name=m11g14", "-c", "user.email=m11g14@localhost", "commit", "--quiet",
              "-m", "throwaway overlay for the M11-G14 portability matrix"], stage)
    return stage


def measure(clone: Path, python: str, full_suite: bool) -> dict:
    result: dict = {"freezes": [], "script_verifiers": {}, "hash_tests": "", "full_suite": None}
    for f in tracked_freezes(clone):
        data = (clone / f["file"]).read_bytes()
        blob = subprocess.run(["git", "show", f"HEAD:{f['file']}"], cwd=clone, check=True, capture_output=True).stdout
        import hashlib
        raw_ok = hashlib.sha256(data).hexdigest() == f["sha256"]
        newline_only = data.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n")
        result["freezes"].append({
            "file": f["file"],
            "raw_hash_matches_freeze": raw_ok,
            "checked_out_has_crlf": b"\r\n" in data,
            "content_identical_to_blob_modulo_crlf": newline_only,
            "classification": "match" if raw_ok else ("newline_conversion_only" if newline_only else "CONTENT_DIFFERS"),
        })
    for label, mod_dir, module, func in SCRIPT_VERIFIERS:
        code = (
            "import sys, io, contextlib; "
            f"sys.path[:0] = ['src', 'scripts/evaluation_lib', 'scripts', {mod_dir!r}]; "
            f"import {module} as m; "
            "buf = io.StringIO(); "
            f"ctx = contextlib.redirect_stdout(buf); ctx.__enter__(); m.{func}(); ctx.__exit__(None, None, None); "
            "print('VERIFIED')"
        )
        proc = _run([python, "-c", code], clone, check=False)
        ok = proc.returncode == 0 and proc.stdout.strip().endswith("VERIFIED")
        tail = (proc.stderr.strip().splitlines() or [""])[-1][:160]
        result["script_verifiers"][label] = "verified" if ok else f"FAILED: {tail}"
    proc = _run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *HASH_TEST_FILES], clone, check=False)
    result["hash_test_files"] = _summary(proc.stdout)
    if full_suite:
        proc = _run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider"], clone, check=False)
        result["full_suite"] = _summary(proc.stdout)
        result["full_suite_failures"] = [ln.split(" ")[1] for ln in proc.stdout.splitlines()
                                         if ln.startswith(("FAILED ", "ERROR "))][:60]
        if not result["full_suite_failures"]:
            proc2 = _run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfE"], clone, check=False) \
                if "failed" in result["full_suite"] or "error" in result["full_suite"] else None
            if proc2 is not None:
                result["full_suite_failures"] = [ln.split(" ")[1] for ln in proc2.stdout.splitlines()
                                                 if ln.startswith(("FAILED ", "ERROR "))][:60]
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--overlay", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-full-suite", action="store_true")
    args = ap.parse_args()
    python = sys.executable
    report = {"head": _run(["git", "rev-parse", "HEAD"], REPO_ROOT).stdout.strip(), "overlay": args.overlay,
              "private_corpora_copied": False, "by_autocrlf": {}}
    with tempfile.TemporaryDirectory(prefix="m11g14-matrix-") as tmp:
        tmp_path = Path(tmp)
        stage = build_stage(tmp_path, args.overlay)
        for cfg in CONFIGS:
            clone = tmp_path / f"autocrlf-{cfg}"
            _run(["git", "-c", f"core.autocrlf={cfg}", "clone", "--quiet", "--no-hardlinks",
                  "-c", f"core.autocrlf={cfg}", str(stage), str(clone)], tmp_path)
            report["by_autocrlf"][cfg] = measure(clone, python, not args.skip_full_suite)
    Path(args.out).write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    for cfg, r in report["by_autocrlf"].items():
        bad = [f"{x['file'].split('/')[1]}:{x['classification']}" for x in r["freezes"] if x["classification"] != "match"]
        failed_scripts = [k for k, v in r["script_verifiers"].items() if v != "verified"]
        print(f"== autocrlf={cfg}")
        print("  freeze mismatches:", bad or "none")
        print("  script verifiers failing:", failed_scripts or "none")
        print("  hash test files:", r["hash_test_files"])
        print("  full suite:", r["full_suite"])
        if r.get("full_suite_failures"):
            print("  failing nodes:", r["full_suite_failures"])


if __name__ == "__main__":
    main()
