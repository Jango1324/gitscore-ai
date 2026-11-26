"""Milestone 11-G23 -- schema validator for the candidate-profile heading control sets (research only).

    python scripts/evaluation_lib/m11g23_validate_controls.py <controls.json>

Checks structure only: every unit span is an exact, unique substring of its control text; field values come
from the closed vocabularies in `evaluation/m11g23/labelling_guide.md`; every `tech` id is either a registered
concept id or exactly `unresolved_concept_id(...)`-shaped; families are A-T. It never runs the job parser,
matcher or scoring, so a control author can use it without seeing any parser outcome.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.concepts.registry import default_registry  # noqa: E402

KINDS = {"qualification", "personality", "responsibility", "company", "product", "benefits", "process",
         "tech_discussion", "learning", "team_practice", "stack", "negation"}
NECS = {"required", "preferred", "unknown"}
SECTIONS = {"required", "preferred", "responsibility", "company", "benefits", "process", "learning", "stack", "none"}
NT = {"education", "experience", "legal", "leadership", "soft_skill"}
FAMILIES = set("ABCDEFGHIJKLMNOPQRST")
_UNRESOLVED = re.compile(r"^unresolved:[a-z0-9][a-z0-9_.+#-]*$")


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    registered = {c.concept_id for c in default_registry().all_concepts()}
    for key in ("schema_version", "milestone", "split", "provenance", "authorship_disclosure", "label_timing",
                "controls"):
        if key not in data:
            errors.append(f"missing top-level key {key!r}")
    ids = set()
    for c in data.get("controls", []):
        cid = c.get("id", "?")
        if cid in ids:
            errors.append(f"{cid}: duplicate id")
        ids.add(cid)
        if c.get("family") not in FAMILIES:
            errors.append(f"{cid}: family {c.get('family')!r} not in A-T")
        text = c.get("text", "")
        if not text.strip():
            errors.append(f"{cid}: empty text")
        if not c.get("units"):
            errors.append(f"{cid}: no units")
        for k, u in enumerate(c.get("units", [])):
            where = f"{cid} unit {k}"
            span = u.get("span", "")
            n = text.count(span) if span else 0
            if n != 1:
                errors.append(f"{where}: span occurs {n} times in text: {span[:60]!r}")
            if u.get("kind") not in KINDS:
                errors.append(f"{where}: kind {u.get('kind')!r}")
            if not isinstance(u.get("qual"), bool):
                errors.append(f"{where}: qual must be a boolean")
            nec = u.get("nec")
            if u.get("qual") and nec not in NECS:
                errors.append(f"{where}: qualification nec {nec!r}")
            if not u.get("qual") and nec is not None:
                errors.append(f"{where}: non-qualification nec must be null")
            if u.get("section") not in SECTIONS:
                errors.append(f"{where}: section {u.get('section')!r}")
            if not isinstance(u.get("ambiguous"), bool):
                errors.append(f"{where}: ambiguous must be a boolean")
            for t in u.get("tech", []):
                if t not in registered and not _UNRESOLVED.match(t):
                    errors.append(f"{where}: tech {t!r} is neither registered nor unresolved:<slug>")
            for t in u.get("nt", []):
                if t not in NT:
                    errors.append(f"{where}: nt {t!r}")
            if not u.get("qual") and u.get("nt"):
                errors.append(f"{where}: nt must be empty for non-qualifications")
    return errors


def main() -> None:
    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(data)
    controls = data.get("controls", [])
    fam: dict[str, int] = {}
    for c in controls:
        fam[c.get("family")] = fam.get(c.get("family"), 0) + 1
    units = [u for c in controls for u in c.get("units", [])]
    print(f"controls {len(controls)} | units {len(units)} | qualification units "
          f"{sum(1 for u in units if u.get('qual'))} | families {dict(sorted(fam.items()))}")
    if errors:
        print(f"{len(errors)} error(s):")
        for e in errors:
            print("  " + e)
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
