"""Milestone 11-G18 -- regression probe for the score-eligibility options.

    python scripts/evaluation_lib/m11g18_option_regression_probe.py

NEVER modifies this repository. For each option it clones HEAD into a
temporary directory (local clone, no network), applies a minimal
ILLUSTRATIVE patch to that throwaway copy only, runs the full existing
test suite there and records which existing tests fail. Patches are
measurement instruments, not proposed implementations; they are deleted
with the clone. A clean clone lacks the private, untracked datasets, so
its skip count is higher than the working repository's.

On the current registry the capability contract (C_declared) selects
exactly the same rows as the `unresolved:` prefix rule (tested by
`b_equals_c_declared`), so one assessor patch measures both B and C.

Writes `evaluation/m11g18/option_regression_probe.json`.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "evaluation" / "m11g18" / "option_regression_probe.json"
_ASSESS = "src/gitscore/assessment/models.py"
_FILTER_OLD = "    return tuple(m for m in matches if m.status != MatchStatus.NOT_ASSESSABLE)\n"
_NUMERATOR_OLD = "        return _round_half_up_percentage(self.match_analysis.supported_count, assessable)\n"
_NUMERATOR_NEW = (
    "        supported = sum(1 for m in _assessable_matches(self.match_analysis.requirement_matches)\n"
    "                        if m.status == MatchStatus.SUPPORTED)\n"
    "        return _round_half_up_percentage(supported, assessable)\n"
)
_HELPER = (
    "def _has_unresolved_member(m, groups_only):\n"
    "    r = m.requirement\n"
    "    ids = r.alternative_concept_ids if r.alternative_concept_ids else ((r.concept_id,) if r.concept_id else ())\n"
    "    if groups_only and not r.alternative_concept_ids:\n"
    "        return False\n"
    "    return any(i.startswith('unresolved:') for i in ids)\n\n\n"
)


def _assessor_patch(groups_only: bool) -> list[tuple[str, str, str]]:
    rule = f"m.status != MatchStatus.NOT_ASSESSABLE and not _has_unresolved_member(m, {groups_only})"
    return [
        (_ASSESS, "def _assessable_matches(", _HELPER + "def _assessable_matches("),
        (_ASSESS, _FILTER_OLD, f"    return tuple(m for m in matches if {rule})\n"),
        (_ASSESS, _NUMERATOR_OLD, _NUMERATOR_NEW),
    ]


OPTIONS = {
    "baseline_unpatched_clone": [],
    "B_or_groups_only (G15 scope)": _assessor_patch(True),
    "B_equals_C_declared (OR groups + standalone)": _assessor_patch(False),
}
HEAD_GUARDS = ("test_g10_g11_g12_and_production_unchanged", "test_no_production_change_and_no_production_import")


def _summary(stdout: str) -> str:
    lines = [ln for ln in stdout.strip().splitlines() if re.search(r"\d+ (passed|failed)", ln)]
    return lines[-1].strip() if lines else ""


def main() -> None:
    python = sys.executable
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()
    report = {"head": head, "note": "patches applied ONLY to throwaway clones; repository untouched",
              "head_identity_guards": list(HEAD_GUARDS), "options": {}}
    with tempfile.TemporaryDirectory(prefix="m11g18-probe-") as tmp:
        for name, edits in OPTIONS.items():
            clone = Path(tmp) / re.sub(r"\W+", "_", name)[:40]
            subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(REPO_ROOT), str(clone)], check=True,
                           capture_output=True)
            for rel, old, new in edits:
                path = clone / rel
                text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
                assert text.count(old) == 1, (name, rel, old[:60])
                path.write_bytes(text.replace(old, new).encode("utf-8"))
            proc = subprocess.run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf"], cwd=clone,
                                  capture_output=True, text=True)
            failed = sorted({ln.split(" ")[1] for ln in proc.stdout.splitlines() if ln.startswith("FAILED ")})
            behavioural = [f for f in failed if not f.endswith(HEAD_GUARDS)]
            report["options"][name] = {
                "files_patched": sorted({e[0] for e in edits}), "suite": _summary(proc.stdout),
                "failed_tests": failed, "head_identity_guard_failures": len(failed) - len(behavioural),
                "behavioural_failures": behavioural,
                "behavioural_failure_files": sorted({f.split("::")[0] for f in behavioural}),
            }
            print(f"{name}: {report['options'][name]['suite']}  behavioural: {len(behavioural)}")
    OUT.write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
