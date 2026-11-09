"""Milestone 11-G16 -- regression probe for compound-logic fix options.

    python scripts/evaluation_lib/m11g16_option_regression_probe.py

NEVER modifies this repository. For each option it clones HEAD into a
temporary directory (local clone, no network), copies in the G16
simulation module, and adds a ROOT-level `conftest.py` -- in that
throwaway clone only -- that calls `m11g16_compound_logic.install(mode)`
before any test runs (an in-memory rebinding of the parser's own helpers;
no source file of the clone is edited either). It then runs the full
existing suite and records which existing tests fail.

Writes `evaluation/m11g16/option_regression_probe.json`.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "evaluation" / "m11g16" / "option_regression_probe.json"
MODES = ("A_lexical_guard", "D_structural_guard", "C_decompose")
CONFTEST = '''import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
for p in (ROOT / "src", ROOT / "scripts" / "evaluation_lib"):
    sys.path.insert(0, str(p))


def pytest_configure(config):
    import m11g16_compound_logic as sim
    sim.install(os.environ["M11G16_MODE"])
'''


def _summary(stdout: str) -> str:
    lines = [ln for ln in stdout.strip().splitlines() if re.search(r"\d+ (passed|failed)", ln)]
    return lines[-1].strip() if lines else ""


def main() -> None:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()
    report = {"head": head, "note": "options installed in memory inside throwaway clones only; repository untouched",
              "options": {}}
    with tempfile.TemporaryDirectory(prefix="m11g16-probe-") as tmp:
        for mode in MODES:
            clone = Path(tmp) / mode
            subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(REPO_ROOT), str(clone)], check=True,
                           capture_output=True)
            for rel in ("scripts/evaluation_lib/m11g16_compound_logic.py",):
                shutil.copyfile(REPO_ROOT / rel, clone / rel)
            (clone / "conftest.py").write_text(CONFTEST, encoding="utf-8")
            env = {**__import__("os").environ, "M11G16_MODE": mode}
            proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf"],
                                  cwd=clone, capture_output=True, text=True, env=env)
            failed = sorted({ln.split(" ")[1] for ln in proc.stdout.splitlines() if ln.startswith("FAILED ")})
            report["options"][mode] = {"suite": _summary(proc.stdout), "failed_tests": failed,
                                       "failed_test_files": sorted({f.split("::")[0] for f in failed})}
            print(f"{mode}: {report['options'][mode]['suite']}  files: {report['options'][mode]['failed_test_files']}")
    OUT.write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
