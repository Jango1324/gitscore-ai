"""Milestone 11-G15 -- regression probe for candidate correction options.

    python scripts/evaluation_lib/m11g15_option_regression_probe.py

NEVER modifies this repository. For each option it clones HEAD into a
temporary directory (local clone, no network), applies a minimal
illustrative patch to THAT throwaway copy only, runs the full existing
test suite there, and records which existing tests fail. The patches
exist only inside the temporary clone and are deleted with it; they are
measurement instruments, not proposed implementations.

Writes `evaluation/m11g15/option_regression_probe.json`.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "evaluation" / "m11g15" / "option_regression_probe.json"

_ASSESS = "src/gitscore/assessment/models.py"
_PARSER = "src/gitscore/jobs/parsing/parser.py"
_FILTER_OLD = "    return tuple(m for m in matches if m.status != MatchStatus.NOT_ASSESSABLE)\n"
_NUMERATOR_OLD = "        return _round_half_up_percentage(self.match_analysis.supported_count, assessable)\n"
_NUMERATOR_NEW = (
    "        supported = sum(1 for m in _assessable_matches(self.match_analysis.requirement_matches)\n"
    "                        if m.status == MatchStatus.SUPPORTED)\n"
    "        return _round_half_up_percentage(supported, assessable)\n"
)
_UNRESOLVED_GROUP = (
    "def _has_unresolved_member(m, groups_only):\n"
    "    r = m.requirement\n"
    "    ids = r.alternative_concept_ids if r.alternative_concept_ids else ((r.concept_id,) if r.concept_id else ())\n"
    "    if groups_only and not r.alternative_concept_ids:\n"
    "        return False\n"
    "    return any(i.startswith('unresolved:') for i in ids)\n\n\n"
)


def _assessor_patch(rule: str, groups_only: bool) -> list[tuple[str, str, str]]:
    return [
        (_ASSESS, "def _assessable_matches(", _UNRESOLVED_GROUP + "def _assessable_matches("),
        (_ASSESS, _FILTER_OLD, f"    return tuple(m for m in matches if {rule.format(g=groups_only)})\n"),
        (_ASSESS, _NUMERATOR_OLD, _NUMERATOR_NEW),
    ]


OPTIONS = {
    "B_exclude_unresolved_or_groups (Option 1, assessor guard)": _assessor_patch(
        "m.status != MatchStatus.NOT_ASSESSABLE and not _has_unresolved_member(m, {g})", True),
    "B_exclude_any_unresolved_requirement (Option 1, wider scope)": _assessor_patch(
        "m.status != MatchStatus.NOT_ASSESSABLE and not _has_unresolved_member(m, {g})", False),
    "C_count_only_when_supported (Option 2 scoring rule)": _assessor_patch(
        "m.status == MatchStatus.SUPPORTED or (m.status == MatchStatus.NOT_OBSERVED "
        "and not _has_unresolved_member(m, {g}))", True),
    "D_parser_unsafe_fallback (Option 3)": [
        (_PARSER, '    if alternative.kind == "technical":\n',
         '    if alternative.kind == "technical" and not any(c.startswith("unresolved:") '
         'for c in alternative.concept_ids):\n'),
        (_PARSER, '    if alternative.kind == "unsafe":\n', '    if alternative.kind in ("unsafe", "technical"):\n'),
    ],
}


def _summary(stdout: str) -> str:
    lines = [ln for ln in stdout.strip().splitlines() if re.search(r"\d+ (passed|failed)", ln)]
    return lines[-1].strip() if lines else ""


def main() -> None:
    python = sys.executable
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()
    report = {"head": head, "note": "patches applied ONLY to throwaway clones; repository untouched", "options": {}}
    with tempfile.TemporaryDirectory(prefix="m11g15-probe-") as tmp:
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
            report["options"][name] = {"files_patched": sorted({e[0] for e in edits}), "suite": _summary(proc.stdout),
                                       "failed_tests": failed, "failed_test_files": sorted({f.split("::")[0]
                                                                                            for f in failed})}
            print(f"{name}: {report['options'][name]['suite']}  files: {report['options'][name]['failed_test_files']}")
    OUT.write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
