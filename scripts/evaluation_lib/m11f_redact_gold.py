"""Milestone 11-F -- produce a publication-safe, text-redacted
derivative of the frozen gold annotations (same pattern established
in M11-D): every `text` field is replaced with null + a length/hash
fingerprint, so structural metadata (categories, tags, relations,
necessity, etc.) can be safely published while the verbatim posting
text never leaves the local machine.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "evaluation" / "m11f" / "holdout_annotations.json"
OUT_PATH = REPO_ROOT / "evaluation" / "m11f" / "holdout_annotations_metadata.json"


def main() -> None:
    data = json.loads(SRC_PATH.read_text(encoding="utf-8"))
    redacted_controls = []
    for control in data["controls"]:
        redacted = dict(control)
        text = redacted.pop("text")
        redacted["text_length_chars"] = len(text)
        redacted["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        redacted_controls.append(redacted)

    payload = {
        "corpus_version": data["corpus_version"],
        "annotation_provenance": data["annotation_provenance"],
        "schema_notes": data["schema_notes"],
        "redaction_note": (
            "Verbatim posting text has been removed from this published derivative. "
            "Each control retains only its structural annotation fields plus a "
            "text_length_chars/text_sha256 fingerprint of the original text, following "
            "the same publication-safety pattern established in M11-D."
        ),
        "controls": redacted_controls,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    print(f"Wrote redacted metadata for {len(redacted_controls)} controls -> {OUT_PATH}")


if __name__ == "__main__":
    main()
