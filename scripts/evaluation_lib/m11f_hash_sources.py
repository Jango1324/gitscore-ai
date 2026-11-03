"""Milestone 11-F -- compute SHA-256 hashes of the raw, local-only
source postings BEFORE annotation begins (hash-freeze protocol,
established in M11-D and reused verbatim here).

Writes evaluation/m11f/source_hashes.json (safe to publish -- hashes
only, no source text).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = REPO_ROOT / "evaluation" / "m11f" / "source"
OUT_PATH = REPO_ROOT / "evaluation" / "m11f" / "source_hashes.json"


def main() -> None:
    hashes = {}
    for path in sorted(SOURCE_DIR.glob("*.txt")):
        content = path.read_bytes()
        hashes[path.name] = {
            "sha256": hashlib.sha256(content).hexdigest(),
            "length_bytes": len(content),
        }
    OUT_PATH.write_text(json.dumps(hashes, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Hashed {len(hashes)} source files -> {OUT_PATH}")


if __name__ == "__main__":
    main()
