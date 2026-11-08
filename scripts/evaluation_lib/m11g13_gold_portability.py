"""Milestone 11-G13 Phase 6 -- gold-freeze portability under different Git
line-ending configurations.

    python scripts/evaluation_lib/m11g13_gold_portability.py [--run-tests]

Read-only with respect to this repository: it clones the CURRENT HEAD
from the local path into temporary directories (no network), once per
`core.autocrlf` value, and re-hashes every committed hash-frozen file.
Nothing in the working tree, `.gitattributes`, frozen gold, or any hash is
modified. `--run-tests` additionally runs the G7 and G12 hash-freeze tests
inside the autocrlf=true clone, using this repository's virtualenv.

Writes `evaluation/m11g13/gold_portability_report.json`.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPO_ROOT / "evaluation" / "m11g13" / "gold_portability_report.json"
CONFIGS = ("true", "input", "false")
HASH_TESTS = (
    "tests/test_m11g7_section_boundary_integrity.py::test_gold_hash_matches_freeze_record",
    "tests/test_m11g12_validator_hardening.py::test_controls_match_hash_freeze",
)


def _git(*args: str, cwd: Path = REPO_ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def frozen_records() -> list[dict]:
    records = []
    for path in _git("ls-files").splitlines():
        if not path.endswith(".json") or "freeze" not in Path(path).name:
            continue
        data = json.loads(_git("show", f"HEAD:{path}"))
        if isinstance(data, dict) and data.get("frozen_file") and data.get("sha256"):
            records.append({"freeze_record": path, "frozen_file": data["frozen_file"], "sha256": data["sha256"]})
    return records


def blob_has_cr(path: str) -> bool:
    blob = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=REPO_ROOT, check=True, capture_output=True).stdout
    return b"\r" in blob


def check(run_tests: bool = False) -> dict:
    records = [r for r in frozen_records() if _git("ls-files", r["frozen_file"]).strip()]
    head = _git("rev-parse", "HEAD").strip()
    report: dict = {
        "head": head,
        "gitattributes_present": (REPO_ROOT / ".gitattributes").exists(),
        "frozen_files_checked": len(records),
        "blobs_with_cr": sum(blob_has_cr(r["frozen_file"]) for r in records),
        "by_autocrlf": {},
    }
    with tempfile.TemporaryDirectory(prefix="m11g13-portability-") as tmp:
        for cfg in CONFIGS:
            dest = Path(tmp) / f"autocrlf-{cfg}"
            subprocess.run(
                ["git", "-c", f"core.autocrlf={cfg}", "clone", "--quiet", "--no-hardlinks",
                 "-c", f"core.autocrlf={cfg}", str(REPO_ROOT), str(dest)],
                check=True, capture_output=True,
            )
            raw_ok = lf_ok = 0
            mismatched = []
            for r in records:
                data = (dest / r["frozen_file"]).read_bytes()
                raw = hashlib.sha256(data).hexdigest() == r["sha256"]
                lf = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() == r["sha256"]
                raw_ok += raw
                lf_ok += lf
                if not raw:
                    mismatched.append(r["frozen_file"])
            entry = {
                "raw_hash_matches": raw_ok,
                "lf_normalized_hash_matches": lf_ok,
                "of": len(records),
                "raw_mismatched_files": mismatched,
            }
            if run_tests and cfg == "true":
                proc = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *HASH_TESTS],
                    cwd=dest, capture_output=True, text=True,
                )
                entry["hash_tests_in_clone"] = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
            report["by_autocrlf"][cfg] = entry
    return report


def main() -> None:
    report = check(run_tests="--run-tests" in sys.argv)
    REPORT_PATH.write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({k: v for k, v in report.items() if k != "by_autocrlf"}))
    for cfg, entry in report["by_autocrlf"].items():
        print(cfg, {k: v for k, v in entry.items() if k != "raw_mismatched_files"},
              "mismatched:", len(entry["raw_mismatched_files"]))


if __name__ == "__main__":
    main()
