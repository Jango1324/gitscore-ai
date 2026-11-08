"""Milestone 11-G14 -- builds the versioned canonical-hash manifest.

    python scripts/evaluation_lib/m11g14_build_canonical_manifest.py

For every TRACKED freeze record whose frozen file is also tracked, reads
the frozen file's COMMITTED blob at HEAD (`git show HEAD:<path>`, never
the working tree) and attests it with `gold_integrity.attest()`: an entry
is created only if a permitted newline form of the committed content
reproduces the freeze record's historical raw sha256 exactly.

Safety rules:
* Any attestation failure aborts without writing anything.
* An existing manifest entry is never changed; a recomputed entry that
  differs aborts the build. Historical freeze records, frozen files and
  their raw hashes are never written.
* Freeze records whose frozen file is untracked (private corpora) are not
  covered: Git never converts their line endings.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import gold_integrity as gi  # noqa: E402

REPO_ROOT = gi.REPO_ROOT
MANIFEST = gi.DEFAULT_MANIFEST


def _git(*args: str, text: bool = True):
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=text).stdout


def build() -> dict:
    head = _git("rev-parse", "HEAD").strip()
    entries: dict = {}
    for path in _git("ls-files", "evaluation").split():
        if not (path.endswith(".json") and "freeze" in Path(path).name):
            continue
        record = json.loads(_git("show", f"HEAD:{path}"))
        target = record.get("frozen_file") if isinstance(record, dict) else None
        if not target or not record.get("sha256") or not _git("ls-files", target).strip():
            continue
        blob = _git("show", f"HEAD:{target}", text=False)
        entry = gi.attest(blob, record["sha256"], record.get("length_bytes"))
        lf_field = record.get("sha256_lf_normalized")
        if lf_field is not None and lf_field != entry["canonical_sha256"]:
            raise gi.FreezeIntegrityError(f"{target}: freeze-time sha256_lf_normalized disagrees with attestation")
        entries[target] = {"freeze_record": path, **entry, "attested_from_commit": head}
    return {
        "schema_version": 1,
        "contract": gi.CONTRACT,
        "contract_definition": "canonical bytes = raw bytes with every CRLF (0x0D0A) replaced by LF (0x0A); "
                               "no other transformation of any kind",
        "note": "Additive to, never a replacement for, each historical freeze record's raw sha256. Each entry was "
                "accepted only because re-encoding its committed content in historical_newline_form reproduces the "
                "historical raw sha256 exactly.",
        "entries": dict(sorted(entries.items())),
    }


def main() -> None:
    new = build()
    if MANIFEST.exists():
        old = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for key, old_entry in old.get("entries", {}).items():
            new_entry = new["entries"].get(key)
            comparable = {k: v for k, v in old_entry.items() if k != "attested_from_commit"}
            if new_entry is None or {k: v for k, v in new_entry.items() if k != "attested_from_commit"} != comparable:
                raise SystemExit(f"REFUSING to change existing manifest entry for {key}")
            new_entry["attested_from_commit"] = old_entry["attested_from_commit"]
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_bytes((json.dumps(new, indent=2) + "\n").encode("utf-8"))
    for key, e in new["entries"].items():
        print(f"{e['historical_newline_form']:4} {key}")
    print(f"wrote {MANIFEST.relative_to(REPO_ROOT)} ({len(new['entries'])} entries)")


if __name__ == "__main__":
    main()
