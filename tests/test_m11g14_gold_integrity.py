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


# The eight freezes registered by M11-G14, pinned record-by-record. These
# values must never change; a later milestone may only ADD registrations.
HISTORICAL_REGISTRATIONS = {
    "evaluation/m11g1/alternative_requirement_controls.json": (
        "evaluation/m11g1/controls_hash_freeze.json",
        "6f77cf62c9df0643ca6607c57f2f69eaf61f3499e173df4cf1a312278a0f5a03", "lf",
        "6f77cf62c9df0643ca6607c57f2f69eaf61f3499e173df4cf1a312278a0f5a03", 8874),
    "evaluation/m11g12/validator_controls.json": (
        "evaluation/m11g12/controls_hash_freeze.json",
        "abfd3a37295098d41ce3350ef3e48b1821c12fcbcb02ea91ae8314f1f0dca49a", "lf",
        "abfd3a37295098d41ce3350ef3e48b1821c12fcbcb02ea91ae8314f1f0dca49a", 106741),
    "evaluation/m11g13/generalization_controls.json": (
        "evaluation/m11g13/controls_hash_freeze.json",
        "88de3fb27393a3871dc69841b756cc43893eff821c10791b7ec3327ebc928b3b", "lf",
        "88de3fb27393a3871dc69841b756cc43893eff821c10791b7ec3327ebc928b3b", 102616),
    "evaluation/m11g2/section_context_controls.json": (
        "evaluation/m11g2/controls_hash_freeze.json",
        "7b21d2e0b1cbfd2be007e95996543fb6bd506bce52f318262acf5e6e2afad6e0", "crlf",
        "55c07b70b7e4150d86c96f04f7e4362b66fa90928750f8a950a179a2675dc36f", 19470),
    "evaluation/m11g3/full_posting_controls.json": (
        "evaluation/m11g3/controls_hash_freeze.json",
        "2ecec618a87642266e2b798b1226d1fc8febb2b8cb835b1b2becd2b9e8cc9692", "crlf",
        "90352867a467456994d438e43a5019e524f203005ebd3db651d35c2c654162ee", 55223),
    "evaluation/m11g4/admission_recovery_controls.json": (
        "evaluation/m11g4/controls_hash_freeze.json",
        "694b98929bbe65b16da8ea965f2811a41c649b29f792a004167549c965dab168", "crlf",
        "fd47ed9b08672985fd9bcc09c8a633608be23deb01df5ade7f9539b2c6e6ea32", 33226),
    "evaluation/m11g6/heading_controls.json": (
        "evaluation/m11g6/gold_hash_freeze.json",
        "56e92f18eeb040ae1ea522d398b0a735e23a45ac5602136cc18af844bc6140c5", "crlf",
        "bfdeef7593a71b9b7d359ba6b0b1ee19d5039ceebdb102ce570468c520321704", 46686),
    "evaluation/m11g7/boundary_controls.json": (
        "evaluation/m11g7/gold_hash_freeze.json",
        "563e9b9ad353c42d428bf19d999674ac4a2fb72244c9672549a3118eb8c6ef00", "crlf",
        "6f0fdcae1c1ecfd80213b4f6daf8b07139619ca640deb96a3296dba21c847fef", 52830),
}
_ENTRY_FIELDS = ("freeze_record", "historical_raw_sha256", "historical_newline_form",
                 "canonical_sha256", "canonical_length_bytes")


def _strict_json(text: str) -> dict:
    """json.loads that REJECTS duplicate keys instead of silently keeping the last one."""
    def hook(pairs):
        keys = [k for k, _ in pairs]
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            raise ValueError(f"duplicate JSON keys: {sorted(dupes)}")
        return dict(pairs)
    return json.loads(text, object_pairs_hook=hook)


def inventory_problems(entries: dict, freeze_records: list[tuple[str, dict]], tracked: set[str]) -> list[str]:
    """The registration/coverage rule for committed evaluation freezes.
    `freeze_records` = every TRACKED freeze record as (record path, record);
    `tracked` = tracked file paths. Returns every violation found."""
    problems: list[str] = []
    named: dict[str, list[str]] = {}
    for path, record in freeze_records:
        target = record.get("frozen_file")
        if target:
            named.setdefault(target, []).append(path)
    for target, paths in named.items():
        if len(paths) > 1:
            problems.append(f"duplicate freeze records for {target}: {paths}")
    required = {t for t in named if t in tracked}
    for target in sorted(required - set(entries)):
        problems.append(f"UNREGISTERED tracked freeze: {target}")
    for target in sorted(set(entries) - required):
        problems.append(f"registered freeze is missing or untracked: {target}")
    records_by_path = dict(freeze_records)
    for target, entry in entries.items():
        record = records_by_path.get(entry.get("freeze_record"))
        if record is None or record.get("frozen_file") != target:
            problems.append(f"{target}: manifest freeze_record does not name this file")
            continue
        if entry.get("historical_raw_sha256") != record.get("sha256"):
            problems.append(f"{target}: historical raw hash differs from its freeze record")
        if target in HISTORICAL_REGISTRATIONS:
            if tuple(entry.get(f) for f in _ENTRY_FIELDS) != HISTORICAL_REGISTRATIONS[target]:
                problems.append(f"{target}: pinned historical registration was ALTERED")
        elif record.get("sha256_lf_normalized") != entry.get("canonical_sha256"):
            problems.append(f"{target}: new registration not reconciled with its freeze-time LF-normalized hash")
    for target in sorted(set(HISTORICAL_REGISTRATIONS) - set(entries)):
        problems.append(f"pinned historical registration REMOVED: {target}")
    return problems


def _repo_inventory():
    manifest = _strict_json((REPO_ROOT / MANIFEST_REL).read_text(encoding="utf-8"))
    tracked = set(subprocess.run(["git", "ls-files", "evaluation"], cwd=REPO_ROOT, capture_output=True,
                                 text=True, check=True).stdout.split())
    records = [(p, json.loads((REPO_ROOT / p).read_text(encoding="utf-8"))) for p in sorted(tracked)
               if p.endswith(".json") and "freeze" in Path(p).name]
    records = [(p, r) for p, r in records if isinstance(r, dict) and r.get("frozen_file")]
    return manifest, records, tracked


def test_manifest_covers_exactly_the_tracked_frozen_files():
    """Registered set == tracked-freeze set (both directions), no duplicate
    registrations, the eight M11-G14 registrations unaltered, and every
    later registration reconciled with its freeze-time anchor."""
    manifest, records, tracked = _repo_inventory()
    assert inventory_problems(manifest["entries"], records, tracked) == []
    # Private, untracked frozen files are never converted by Git and are not covered.
    assert "evaluation/m11f/holdout_annotations.json" not in manifest["entries"]
    assert "evaluation/m11g9/holdout_annotations.json" not in manifest["entries"]


def _inventory_case(mutate):
    manifest, records, tracked = _repo_inventory()
    entries = json.loads(json.dumps(manifest["entries"]))
    records = json.loads(json.dumps(records))
    tracked = set(tracked)
    mutate(entries, records, tracked)
    return inventory_problems(entries, [tuple(r) for r in records], tracked)


def _alter_pinned(e, r, t):
    e["evaluation/m11g7/boundary_controls.json"]["canonical_sha256"] = "0" * 64


def _drop_g15_anchor(e, r, t):
    for rec in r:
        if rec[1].get("frozen_file") == "evaluation/m11g15/or_scoring_controls.json":
            rec[1]["sha256_lf_normalized"] = "0" * 64


INVENTORY_VIOLATIONS = {
    "unregistered_tracked_freeze": lambda e, r, t: (
        r.append(["evaluation/new/controls_hash_freeze.json",
                  {"frozen_file": "evaluation/new/controls.json", "sha256": "1" * 64}]),
        t.add("evaluation/new/controls.json")),
    "registered_file_missing": lambda e, r, t: t.discard("evaluation/m11g12/validator_controls.json"),
    "duplicate_freeze_record": lambda e, r, t: r.append(
        ["evaluation/m11g7/second_freeze.json", {"frozen_file": "evaluation/m11g7/boundary_controls.json",
                                                 "sha256": "2" * 64}]),
    "pinned_registration_altered": _alter_pinned,
    "pinned_registration_removed": lambda e, r, t: e.pop("evaluation/m11g2/section_context_controls.json"),
    "raw_hash_diverges_from_record": lambda e, r, t: e["evaluation/m11g1/alternative_requirement_controls.json"]
    .update(historical_raw_sha256="3" * 64),
    "new_registration_unreconciled": _drop_g15_anchor,
    "wrong_freeze_record_link": lambda e, r, t: e["evaluation/m11g13/generalization_controls.json"]
    .update(freeze_record="evaluation/m11g12/controls_hash_freeze.json"),
}


@pytest.mark.parametrize("violation", sorted(INVENTORY_VIOLATIONS))
def test_inventory_rule_detects_violations(violation):
    assert _inventory_case(INVENTORY_VIOLATIONS[violation]) != []


def test_duplicate_manifest_keys_are_rejected():
    with pytest.raises(ValueError, match="duplicate JSON keys"):
        _strict_json('{"entries": {"a": {}, "a": {}}}')


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
