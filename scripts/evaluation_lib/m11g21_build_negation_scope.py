"""Milestone 11-G21 (Option B) -- pre-labelled negation-scope / optionality examples (builder).

    python scripts/evaluation_lib/m11g21_build_negation_scope.py

Writes `evaluation/m11g21/negation_scope_controls.json` and its G14-portable freeze
record `evaluation/m11g21/negation_scope_hash_freeze.json`; refuses to overwrite a
frozen file whose content would change.

Provenance: AUTHOR-CREATED synthetic validation for the G21 negation-scope
correction, written and frozen BEFORE the revised implementation existed. Same
author as the implementation: this is NOT an independent holdout. Every
expectation records the TRUE reading, including cases the author expects the
narrow correction NOT to handle (marked `expected_limitation`), so failures are
reported rather than hidden.

`expected_rows` is the exact multiset of rows a correct parser emits:
`[label, necessity]`, where `label` is a registry concept id, `unresolved:<slug>`,
or a non-technical category (`education`, `experience`, `legal`, ...). An empty
list means the claim must not become any JobRequirement.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import gold_integrity as gi  # noqa: E402

OUT_DIR = REPO_ROOT / "evaluation" / "m11g21"
OUT = OUT_DIR / "negation_scope_controls.json"
FREEZE = OUT_DIR / "negation_scope_hash_freeze.json"

R, P = "required", "preferred"


def X(cid, family, text, rows, note="", limitation=False):  # noqa: N802
    return {"id": cid, "family": family, "text": text, "expected_rows": [list(r) for r in rows],
            "expected_limitation": limitation, "note": note}


CONTROLS = [
    # clause-local requirement negation + contrastive ellipsis
    X("m11g21-n01", "elliptical_contrast", "A Master's degree is not required, but strong SQL skills are.",
      [("language.sql", R)], "comma-but contrast; ellipsis resolves to 'required'"),
    X("m11g21-n02", "elliptical_contrast", "Kubernetes certification is not mandatory; hands-on Kubernetes experience is.",
      [("infra.kubernetes", R)], "ellipsis resolves to 'mandatory'"),
    X("m11g21-n03", "elliptical_contrast", "Java is not required; Kotlin is.",
      [("language.kotlin", R)], "ellipsis without a candidate-attribute noun"),
    X("m11g21-n04", "clause_local_negation", "Golang experience is not required; Rust experience is preferred.",
      [("language.rust", P)], "negated clause + explicit preference clause"),
    X("m11g21-n05", "clause_local_negation", "A PhD is not required; a Master's degree is preferred.",
      [("education", P)], "education only from the preferred clause"),
    X("m11g21-n06", "clause_local_negation", "Experience with Kafka is not needed; we will train you.",
      [], "negation + employer narrative: nothing to admit"),
    X("m11g21-n07", "clause_local_negation", "No prior Rust experience is necessary, but strong C++ skills are.",
      [("language.cpp", R)], "'No <tech> experience is necessary' is outside the negation vocabulary",
      limitation=True),
    # optionality (explicit preference + 'not required/essential')
    X("m11g21-n08", "optionality", "Docker is nice to have but not required.", [("infra.docker", P)]),
    X("m11g21-n09", "optionality", "Experience with Redis is a plus, though not mandatory.", [("database.redis", P)]),
    X("m11g21-n10", "optionality", "React knowledge is welcome though not essential.", [("framework.react", P)],
      "'welcome' is not in the existing preference vocabulary", limitation=True),
    X("m11g21-n11", "optionality", "PyTorch is preferred, although not essential.", [("ml.framework.pytorch", P)],
      "concession after the preference"),
    # pure negation / rejection
    X("m11g21-n12", "requirement_negation", "Prior AWS experience is not essential.", []),
    X("m11g21-n13", "requirement_negation", "Knowledge of Terraform is not needed for this role.", []),
    # narrative with preference / negation vocabulary
    X("m11g21-n14", "narrative_preference", "Our engineers prefer Rust for systems work.", []),
    X("m11g21-n15", "narrative_preference", "Our team does not require Python; we use Golang.", []),
    # mixed necessity in one sentence (positive preference in another clause)
    X("m11g21-n16", "mixed_necessity", "Strong SQL skills are required; Docker knowledge is preferred.",
      [("language.sql", R), ("infra.docker", P)], "per-clause necessity needs per-conjunct rows (out of scope)",
      limitation=True),
]


def main() -> None:
    doc = {
        "schema_version": 1, "milestone": "M11-G21 (Option B negation-scope correction)",
        "split": "author_created_validation",
        "provenance": "author-created synthetic examples; no real posting text or employer",
        "authorship_disclosure": ("Written by the implementation's author BEFORE the revised implementation existed; "
                                  "NOT an independent holdout."),
        "label_timing": "expectations written and frozen BEFORE the revised v14 implementation ran",
        "controls": CONTROLS,
    }
    payload = (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        if OUT.read_bytes() != payload:
            raise SystemExit(f"{OUT} is frozen and its content would change; refusing to overwrite")
        print("unchanged")
        return
    OUT.write_bytes(payload)
    FREEZE.write_bytes((json.dumps({
        "frozen_file": OUT.relative_to(REPO_ROOT).as_posix(), "sha256": gi.sha256(payload),
        "sha256_lf_normalized": gi.sha256(gi.canonical_bytes(payload)), "length_bytes": len(payload),
        "canonical_contract": "crlf-to-lf/v1",
        "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Frozen BEFORE the revised (negation-scope) v14 implementation existed. NOT registered in the "
                "canonical manifest (pending authorization).",
    }, indent=2) + "\n").encode("utf-8"))
    print(f"wrote {len(CONTROLS)} controls; sha256={gi.sha256(payload)}")


if __name__ == "__main__":
    main()
