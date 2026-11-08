"""Milestone 11-G14 -- line-ending-portable freeze verification.

Adversarial tests use ORIGINAL synthetic fixtures written into a temporary
directory; real-repository tests check the attested canonical manifest
against every tracked historical freeze. No frozen gold is modified.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation_lib"))

import gold_integrity as gi  # noqa: E402
import m11g14_build_canonical_manifest as builder  # noqa: E402

# Original synthetic fixture (never a real posting). Composed "é" (U+00E9).
SYNTHETIC = (
    "{\n"
    '  "schema_version": 1,\n'
    '  "controls": [\n'
    "    {\n"
    '      "id": "synthetic-001",\n'
    '      "text": "Experience with Rust is required.",\n'
    '      "span": {"start": 16, "end": 20},\n'
    '      "expected_necessity": "required",\n'
    '      "note": "café résumé example"\n'
    "    },\n"
    "    {\n"
    '      "id": "synthetic-002",\n'
    '      "text": "Go would be nice.",\n'
    '      "span": {"start": 0, "end": 2},\n'
    '      "expected_necessity": "preferred",\n'
    '      "note": "plain"\n'
    "    }\n"
    "  ]\n"
    "}\n"
)
FROZEN_REL = "evaluation/synthetic/controls.json"
RECORD_REL = "evaluation/synthetic/controls_hash_freeze.json"
MANIFEST_REL = "evaluation/integrity/canonical_hash_manifest.json"


def _setup(tmp_path: Path, historical_form: str) -> dict:
    canonical = SYNTHETIC.encode("utf-8")
    historical = gi.encode_form(canonical, historical_form)
    (tmp_path / "evaluation" / "synthetic").mkdir(parents=True)
    (tmp_path / "evaluation" / "integrity").mkdir(parents=True)
    record = {"frozen_file": FROZEN_REL, "sha256": gi.sha256(historical), "length_bytes": len(historical)}
    (tmp_path / RECORD_REL).write_text(json.dumps(record), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "contract": gi.CONTRACT,
        "entries": {FROZEN_REL: {"freeze_record": RECORD_REL,
                                 **gi.attest(canonical, record["sha256"], record["length_bytes"])}},
    }
    (tmp_path / MANIFEST_REL).write_text(json.dumps(manifest), encoding="utf-8")
    return {"canonical": canonical, "record": record, "manifest": manifest}


def _write_checkout(tmp_path: Path, text_lf: str, form: str) -> None:
    (tmp_path / FROZEN_REL).write_bytes(gi.encode_form(text_lf.encode("utf-8"), form))


def _verify(tmp_path: Path):
    return gi.verify_frozen_file(FROZEN_REL, RECORD_REL, repo_root=tmp_path, manifest_path=tmp_path / MANIFEST_REL)


FORMS = ("lf", "crlf")


# ---------------------------------------------------------------------------
# LF / CRLF equivalence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("historical", FORMS)
@pytest.mark.parametrize("checkout", FORMS)
def test_lf_crlf_checkouts_are_equivalent(tmp_path, historical, checkout):
    _setup(tmp_path, historical)
    _write_checkout(tmp_path, SYNTHETIC, checkout)
    result = _verify(tmp_path)
    assert result.method == ("raw" if historical == checkout else "canonical")


# ---------------------------------------------------------------------------
# Genuine content changes are rejected, in every historical/checkout form
# ---------------------------------------------------------------------------

MUTATIONS = {
    "control_value": lambda t: t.replace("Experience with Rust is required.", "Experience with Rust is preferred."),
    "gold_label": lambda t: t.replace('"expected_necessity": "preferred"', '"expected_necessity": "required"'),
    "source_span": lambda t: t.replace('"start": 16', '"start": 17'),
    "metadata": lambda t: t.replace('"schema_version": 1', '"schema_version": 2'),
    "added_content": lambda t: t.replace('"note": "plain"', '"note": "plain",\n      "extra": true'),
    "deleted_content": lambda t: t.replace('      "note": "plain"\n', ""),
    "reordered_keys": lambda t: t.replace(
        '      "id": "synthetic-002",\n      "text": "Go would be nice.",\n',
        '      "text": "Go would be nice.",\n      "id": "synthetic-002",\n'),
    "trailing_space": lambda t: t.replace('"plain"\n', '"plain" \n'),
    "tab_indentation": lambda t: t.replace('    {\n      "id": "synthetic-001"', '\t{\n      "id": "synthetic-001"'),
    "extra_blank_line": lambda t: t.replace("  ]\n", "  ]\n\n"),
    "missing_final_newline": lambda t: t[:-1],
    "unicode_nfd": lambda t: unicodedata.normalize("NFD", t),
    "unicode_replaced": lambda t: t.replace("café", "cafe"),
    "byte_order_mark": lambda t: "﻿" + t,
    "truncated": lambda t: t[: len(t) // 2],
}


@pytest.mark.parametrize("historical", FORMS)
@pytest.mark.parametrize("checkout", FORMS)
@pytest.mark.parametrize("mutation", sorted(MUTATIONS))
def test_genuine_content_changes_are_rejected(tmp_path, historical, checkout, mutation):
    _setup(tmp_path, historical)
    mutated = MUTATIONS[mutation](SYNTHETIC)
    assert mutated != SYNTHETIC
    _write_checkout(tmp_path, mutated, checkout)
    with pytest.raises(gi.FreezeIntegrityError):
        _verify(tmp_path)


@pytest.mark.parametrize("historical", FORMS)
def test_lone_cr_line_endings_are_not_a_permitted_conversion(tmp_path, historical):
    _setup(tmp_path, historical)
    (tmp_path / FROZEN_REL).write_bytes(SYNTHETIC.encode("utf-8").replace(b"\n", b"\r"))
    with pytest.raises(gi.FreezeIntegrityError):
        _verify(tmp_path)


# ---------------------------------------------------------------------------
# Incorrect metadata and corrupted hashes are rejected
# ---------------------------------------------------------------------------


def _edit_json(path: Path, fn) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def _flip(h: str) -> str:
    return ("0" if h[0] != "0" else "1") + h[1:]


METADATA_CORRUPTIONS = {
    "record_names_other_file": (RECORD_REL, lambda d: d.update(frozen_file="evaluation/synthetic/other.json")),
    "record_length_wrong": (RECORD_REL, lambda d: d.update(length_bytes=d["length_bytes"] + 1)),
    "record_sha_corrupted": (RECORD_REL, lambda d: d.update(sha256=_flip(d["sha256"]))),
    "manifest_canonical_sha_corrupted": (
        MANIFEST_REL, lambda d: d["entries"][FROZEN_REL].update(canonical_sha256=_flip(d["entries"][FROZEN_REL]["canonical_sha256"]))),
    "manifest_historical_raw_corrupted": (
        MANIFEST_REL, lambda d: d["entries"][FROZEN_REL].update(
            historical_raw_sha256=_flip(d["entries"][FROZEN_REL]["historical_raw_sha256"]))),
    "manifest_canonical_length_wrong": (
        MANIFEST_REL, lambda d: d["entries"][FROZEN_REL].update(
            canonical_length_bytes=d["entries"][FROZEN_REL]["canonical_length_bytes"] - 1)),
    "manifest_form_swapped": (
        MANIFEST_REL, lambda d: d["entries"][FROZEN_REL].update(
            historical_newline_form="crlf" if d["entries"][FROZEN_REL]["historical_newline_form"] == "lf" else "lf")),
    "manifest_wrong_freeze_record": (MANIFEST_REL, lambda d: d["entries"][FROZEN_REL].update(freeze_record="x.json")),
    "manifest_wrong_contract": (MANIFEST_REL, lambda d: d.update(contract="strip-all-whitespace/v1")),
    "manifest_entry_missing": (MANIFEST_REL, lambda d: d["entries"].clear()),
}


@pytest.mark.parametrize("historical", FORMS)
@pytest.mark.parametrize("corruption", sorted(METADATA_CORRUPTIONS))
def test_corrupted_metadata_or_hashes_are_rejected(tmp_path, historical, corruption):
    """The checkout is a legitimate opposite-newline copy, so verification
    MUST go through the canonical path -- and must fail on the corruption."""
    _setup(tmp_path, historical)
    _write_checkout(tmp_path, SYNTHETIC, "crlf" if historical == "lf" else "lf")
    rel, fn = METADATA_CORRUPTIONS[corruption]
    _edit_json(tmp_path / rel, fn)
    with pytest.raises(gi.FreezeIntegrityError):
        _verify(tmp_path)


def test_missing_manifest_is_rejected_for_a_converted_checkout(tmp_path):
    _setup(tmp_path, "lf")
    _write_checkout(tmp_path, SYNTHETIC, "crlf")
    (tmp_path / MANIFEST_REL).unlink()
    with pytest.raises(gi.FreezeIntegrityError):
        _verify(tmp_path)


# ---------------------------------------------------------------------------
# Never silently regenerate
# ---------------------------------------------------------------------------


def test_failed_verification_writes_nothing(tmp_path):
    _setup(tmp_path, "crlf")
    _write_checkout(tmp_path, MUTATIONS["gold_label"](SYNTHETIC), "lf")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(gi.FreezeIntegrityError):
        _verify(tmp_path)
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_verifier_module_has_no_write_path():
    src = (REPO_ROOT / "scripts" / "evaluation_lib" / "gold_integrity.py").read_text(encoding="utf-8")
    for forbidden in ("write_bytes", "write_text", "open(", ".unlink(", "json.dump("):
        assert forbidden not in src, forbidden


def test_attestation_rejects_content_change_and_lone_cr():
    canonical = SYNTHETIC.encode("utf-8")
    historical = gi.sha256(gi.encode_form(canonical, "crlf"))
    with pytest.raises(gi.FreezeIntegrityError):
        gi.attest(MUTATIONS["control_value"](SYNTHETIC).encode("utf-8"), historical)
    with pytest.raises(gi.FreezeIntegrityError):
        gi.attest(canonical.replace(b"\n", b"\r", 1), historical)


def test_builder_refuses_to_change_an_existing_entry(tmp_path, monkeypatch):
    manifest = json.loads((REPO_ROOT / MANIFEST_REL).read_text(encoding="utf-8"))
    key = next(iter(manifest["entries"]))
    manifest["entries"][key]["canonical_sha256"] = _flip(manifest["entries"][key]["canonical_sha256"])
    altered = tmp_path / "manifest.json"
    altered.write_text(json.dumps(manifest), encoding="utf-8")
    before = altered.read_bytes()
    monkeypatch.setattr(builder, "MANIFEST", altered)
    with pytest.raises(SystemExit, match="REFUSING"):
        builder.main()
    assert altered.read_bytes() == before


# ---------------------------------------------------------------------------
# Real repository: the committed manifest and every tracked freeze
# ---------------------------------------------------------------------------


def _tracked_freezes() -> dict[str, dict]:
    out = {}
    for path in subprocess.run(["git", "ls-files", "evaluation"], cwd=REPO_ROOT, capture_output=True,
                               text=True, check=True).stdout.split():
        if path.endswith(".json") and "freeze" in Path(path).name:
            record = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
            target = record.get("frozen_file") if isinstance(record, dict) else None
            if target:
                out[target] = {"record": path, **record}
    return out


def test_manifest_covers_exactly_the_tracked_frozen_files():
    manifest = json.loads((REPO_ROOT / MANIFEST_REL).read_text(encoding="utf-8"))
    tracked = {t for t in _tracked_freezes()
               if subprocess.run(["git", "ls-files", t], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()}
    assert set(manifest["entries"]) == tracked
    assert len(tracked) == 8
    # Private, untracked frozen files are never converted by Git and are not covered.
    assert "evaluation/m11f/holdout_annotations.json" not in manifest["entries"]
    assert "evaluation/m11g9/holdout_annotations.json" not in manifest["entries"]


def test_manifest_never_replaces_historical_raw_hashes():
    manifest = json.loads((REPO_ROOT / MANIFEST_REL).read_text(encoding="utf-8"))
    freezes = _tracked_freezes()
    for target, entry in manifest["entries"].items():
        assert entry["historical_raw_sha256"] == freezes[target]["sha256"], target
        assert entry["freeze_record"] == freezes[target]["record"], target
        lf = freezes[target].get("sha256_lf_normalized")
        if lf is not None:
            assert lf == entry["canonical_sha256"], target


def test_manifest_is_reproducible_from_committed_history():
    committed = json.loads((REPO_ROOT / MANIFEST_REL).read_text(encoding="utf-8"))
    rebuilt = builder.build()
    strip = lambda es: {k: {f: v for f, v in e.items() if f != "attested_from_commit"} for k, e in es.items()}  # noqa: E731
    assert strip(rebuilt["entries"]) == strip(committed["entries"])


@pytest.mark.parametrize("target", sorted(json.loads(
    (REPO_ROOT / MANIFEST_REL).read_text(encoding="utf-8"))["entries"]))
def test_every_tracked_frozen_file_verifies(target):
    entry = json.loads((REPO_ROOT / MANIFEST_REL).read_text(encoding="utf-8"))["entries"][target]
    result = gi.verify_frozen_file(target, entry["freeze_record"])
    assert result.historical_raw_sha256 == entry["historical_raw_sha256"]


@pytest.mark.parametrize("target", sorted(json.loads(
    (REPO_ROOT / MANIFEST_REL).read_text(encoding="utf-8"))["entries"]))
def test_real_historical_gold_copies_tamper_check(tmp_path, target):
    """Copies (never edits) one real frozen file, its freeze record and the
    manifest into a temporary root: LF and CRLF copies verify; a single
    changed content byte in either form is rejected."""
    entry = json.loads((REPO_ROOT / MANIFEST_REL).read_text(encoding="utf-8"))["entries"][target]
    canonical = gi.canonical_bytes((REPO_ROOT / target).read_bytes())
    for rel in (entry["freeze_record"], MANIFEST_REL):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes((REPO_ROOT / rel).read_bytes())
    (tmp_path / target).parent.mkdir(parents=True, exist_ok=True)
    middle = len(canonical) // 2
    while canonical[middle:middle + 1] in (b"\n", b"\r"):
        middle += 1
    tampered = canonical[:middle] + (b"X" if canonical[middle:middle + 1] != b"X" else b"Y") + canonical[middle + 1:]
    for form in FORMS:
        (tmp_path / target).write_bytes(gi.encode_form(canonical, form))
        gi.verify_frozen_file(target, entry["freeze_record"], repo_root=tmp_path,
                              manifest_path=tmp_path / MANIFEST_REL)
        (tmp_path / target).write_bytes(gi.encode_form(tampered, form))
        with pytest.raises(gi.FreezeIntegrityError):
            gi.verify_frozen_file(target, entry["freeze_record"], repo_root=tmp_path,
                                  manifest_path=tmp_path / MANIFEST_REL)


def test_not_imported_by_production():
    offenders = [str(p) for p in (REPO_ROOT / "src" / "gitscore").rglob("*.py")
                 if "gold_integrity" in p.read_text(encoding="utf-8")]
    assert offenders == []
