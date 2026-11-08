"""Milestone 11-G14 -- shared, line-ending-portable freeze verification.

Evaluation infrastructure only; nothing in `src/gitscore` imports it.

CANONICALIZATION CONTRACT ("crlf-to-lf/v1")
-------------------------------------------
canonical_bytes(raw) = raw with every two-byte CRLF sequence (0x0D 0x0A)
replaced by a single LF (0x0A). NOTHING else changes: no lone-CR
handling, no BOM removal, no whitespace stripping, no Unicode
normalization, no decoding/re-encoding, no JSON parsing or reordering.
That is exactly the transformation Git's `core.autocrlf` applies between
the repository and a working tree, and nothing more.

VERIFICATION (never writes anything; never regenerates an expected hash)
------------------------------------------------------------------------
`verify_frozen_file(frozen_file, freeze_record)`:

1. The freeze record must name `frozen_file` as its `frozen_file`.
2. If the file's RAW bytes hash to the record's historical `sha256` (and
   match `length_bytes` when recorded): verified, method "raw".
3. Otherwise the file must be covered by the versioned canonical manifest
   (`evaluation/integrity/canonical_hash_manifest.json`), and ALL of:
   a. the manifest's `historical_raw_sha256` equals the freeze record's
      `sha256` (the manifest can never drift from the historical record);
   b. sha256(canonical bytes) equals the manifest's `canonical_sha256`
      and their length equals `canonical_length_bytes`;
   c. re-encoding the canonical bytes into the frozen file's attested
      historical form (`lf` or `crlf`) reproduces the historical raw
      `sha256` (and `length_bytes`) EXACTLY -- a direct proof against the
      original freeze, independent of the manifest's own canonical hash.
   Verified, method "canonical".
4. Anything else raises `FreezeIntegrityError` naming the failed check.

Manifest entries are created only by
`m11g14_build_canonical_manifest.py`, which attests each entry against the
committed blob and refuses to change an existing entry.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "evaluation" / "integrity" / "canonical_hash_manifest.json"
CONTRACT = "crlf-to-lf/v1"

CRLF, LF = b"\r\n", b"\n"


class FreezeIntegrityError(AssertionError):
    """A frozen file does not match its historical freeze. Subclasses
    AssertionError so a failing check fails a test exactly like the raw
    `assert` it replaces."""


@dataclass(frozen=True)
class VerificationResult:
    frozen_file: str
    method: str  # "raw" | "canonical"
    historical_raw_sha256: str
    canonical_sha256: str


def canonical_bytes(raw: bytes) -> bytes:
    return raw.replace(CRLF, LF)


def encode_form(canonical: bytes, form: str) -> bytes:
    """Inverse of canonicalization for an attested historical form."""
    if form == "lf":
        return canonical
    if form == "crlf":
        return canonical.replace(LF, CRLF)
    raise FreezeIntegrityError(f"unknown historical newline form {form!r}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def attest(committed_blob: bytes, historical_sha256: str, historical_length: int | None = None) -> dict:
    """Builds ONE manifest entry from the committed blob, or raises. The
    entry is accepted only if some permitted newline form of the blob's
    canonical bytes reproduces the historical raw hash exactly."""
    if b"\r" in canonical_bytes(committed_blob):
        raise FreezeIntegrityError("committed blob contains a lone CR; it cannot be attested under crlf-to-lf/v1")
    canonical = canonical_bytes(committed_blob)
    for form in ("lf", "crlf"):
        encoded = encode_form(canonical, form)
        if sha256(encoded) == historical_sha256 and (historical_length is None or len(encoded) == historical_length):
            return {
                "historical_raw_sha256": historical_sha256,
                "historical_newline_form": form,
                "canonical_sha256": sha256(canonical),
                "canonical_length_bytes": len(canonical),
            }
    raise FreezeIntegrityError(
        "no permitted newline form of the committed content reproduces the historical raw sha256 "
        f"{historical_sha256}: the content differs from what was frozen, not just its line endings"
    )


def _rel(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def verify_frozen_file(
    frozen_file: Path | str,
    freeze_record: Path | str,
    *,
    repo_root: Path = REPO_ROOT,
    manifest_path: Path | None = None,
) -> VerificationResult:
    repo_root = Path(repo_root)
    frozen_path = Path(frozen_file) if Path(frozen_file).is_absolute() else repo_root / frozen_file
    record_path = Path(freeze_record) if Path(freeze_record).is_absolute() else repo_root / freeze_record
    rel = _rel(frozen_path, repo_root)

    record = json.loads(record_path.read_text(encoding="utf-8"))
    named = str(record.get("frozen_file", "")).replace("\\", "/")
    if named != rel:
        raise FreezeIntegrityError(f"{_rel(record_path, repo_root)} freezes {named!r}, not {rel!r}")
    historical = record.get("sha256")
    if not isinstance(historical, str) or len(historical) != 64:
        raise FreezeIntegrityError(f"{_rel(record_path, repo_root)} has no valid historical sha256")
    historical_length = record.get("length_bytes")

    raw = frozen_path.read_bytes()
    canonical = canonical_bytes(raw)
    if sha256(raw) == historical and (historical_length is None or len(raw) == historical_length):
        return VerificationResult(rel, "raw", historical, sha256(canonical))

    manifest_file = manifest_path or (repo_root / DEFAULT_MANIFEST.relative_to(REPO_ROOT))
    if not manifest_file.exists():
        raise FreezeIntegrityError(
            f"{rel}: raw sha256 {sha256(raw)} != frozen {historical}, and no canonical manifest exists at "
            f"{manifest_file} -- cannot distinguish a line-ending conversion from a content change"
        )
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("contract") != CONTRACT:
        raise FreezeIntegrityError(f"canonical manifest contract {manifest.get('contract')!r} != {CONTRACT!r}")
    entry = manifest.get("entries", {}).get(rel)
    if entry is None:
        raise FreezeIntegrityError(
            f"{rel}: raw sha256 {sha256(raw)} != frozen {historical}, and the file has no canonical-manifest entry"
        )
    if entry.get("freeze_record") != _rel(record_path, repo_root):
        raise FreezeIntegrityError(f"{rel}: manifest entry belongs to {entry.get('freeze_record')!r}")
    if entry.get("historical_raw_sha256") != historical:
        raise FreezeIntegrityError(
            f"{rel}: manifest historical_raw_sha256 {entry.get('historical_raw_sha256')} does not equal the freeze "
            f"record's sha256 {historical} -- the manifest has drifted from the historical record"
        )
    if sha256(canonical) != entry.get("canonical_sha256") or len(canonical) != entry.get("canonical_length_bytes"):
        raise FreezeIntegrityError(
            f"{rel}: CONTENT CHANGED. canonical sha256 {sha256(canonical)} ({len(canonical)} bytes) != frozen "
            f"canonical {entry.get('canonical_sha256')} ({entry.get('canonical_length_bytes')} bytes). The difference "
            "is not a CRLF/LF conversion. Do not regenerate hashes: restore the frozen content."
        )
    reencoded = encode_form(canonical, entry.get("historical_newline_form", ""))
    if sha256(reencoded) != historical or (historical_length is not None and len(reencoded) != historical_length):
        raise FreezeIntegrityError(
            f"{rel}: re-encoding to the attested {entry.get('historical_newline_form')!r} form does not reproduce the "
            f"historical sha256 {historical}"
        )
    return VerificationResult(rel, "canonical", historical, sha256(canonical))
