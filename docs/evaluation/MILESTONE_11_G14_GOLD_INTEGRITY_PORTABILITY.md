# Milestone 11-G14 — Cross-Platform Gold Integrity

Status: **test-infrastructure correction implemented, validated and
committed** under explicit user authorization as
`fix: make evaluation gold integrity checks portable`. No production parser, matcher, scoring, extraction,
API or frontend code changed. No frozen control, annotation, gold label
or historical raw hash changed (all 8 frozen files and every freeze record
are byte-identical to HEAD). No `.gitattributes` was added.

| Artifact | Path |
|---|---|
| Shared verifier (contract `crlf-to-lf/v1`) | `scripts/evaluation_lib/gold_integrity.py` |
| Attested canonical manifest (additive, versioned) | `evaluation/integrity/canonical_hash_manifest.json` |
| Manifest builder (attests; refuses to change entries) | `scripts/evaluation_lib/m11g14_build_canonical_manifest.py` |
| Clean-checkout matrix tool | `scripts/evaluation_lib/m11g14_portability_matrix.py` |
| Before / after matrices | `evaluation/integrity/m11g14_portability_matrix_before.json`, `…_after.json` |
| Focused tests (111) | `tests/test_m11g14_gold_integrity.py` |

## Baseline (verified)

- HEAD `80bb294b477ffbae936e376351c0433e47ab2713`, `main`, no tracked
  diffs, parser v12.
- Original environment: 1858 passed, 13 skipped, 18 xfailed.
- The 18 private / untracked M11 entries are preserved.

## Phase 1 — Inventory and reproduction

### Freeze records

| Freeze record | Frozen file | Tracked? | Raw hash taken over | Verified by |
|---|---|---|---|---|
| `m11g1/controls_hash_freeze.json` | `alternative_requirement_controls.json` | yes | **LF** | script `evaluate_m11g1_…` |
| `m11g2/controls_hash_freeze.json` | `section_context_controls.json` | yes | **CRLF** | scripts `evaluate_m11g2_section_context`, `…_strategy_comparison` |
| `m11g3/controls_hash_freeze.json` | `full_posting_controls.json` | yes | **CRLF** | script `evaluate_m11g3_end_to_end` |
| `m11g4/controls_hash_freeze.json` | `admission_recovery_controls.json` | yes | **CRLF** | script `evaluate_m11g4_admission_recovery` |
| `m11g6/gold_hash_freeze.json` | `heading_controls.json` | yes | **CRLF** | test G6 + scripts `m11g6_phase1/phase3` |
| `m11g7/gold_hash_freeze.json` | `boundary_controls.json` | yes | **CRLF** | test G7 + scripts `m11g7_phase1/phase3` |
| `m11g12/controls_hash_freeze.json` | `validator_controls.json` | yes | **LF** | test G12 + script `evaluate_m11g12_…` |
| `m11g13/controls_hash_freeze.json` | `generalization_controls.json` | yes | **LF** (+ freeze-time LF-normalized hash) | already canonical (G13) |
| `m11f/gold_hash_freeze.json` | `m11f/holdout_annotations.json` | **no (private)** | raw | script `evaluate_m11f_…` |
| `m11g9/gold_hash_freeze.json` | `m11g9/holdout_annotations.json` | **no (private)** | raw | test G9 (skips if absent) + script |
| (untracked) `m11g5/…` | `m11g5/holdout_annotations.json` | **no (private)** | raw | tests G5, G8 (skip if absent) |

**Other hash records** (`m11d/provenance.json`,
`m11d|m11f|m11g9/source_hashes.json`, `holdout_annotations_metadata.json`,
`m11g13/real_text_inputs_freeze.json`) all cover private, untracked files.
G13's input freeze is already LF-normalized.

**Out of scope.** Git never checks out untracked private files, so
`core.autocrlf` cannot change their bytes.

**In scope.** 8 tracked freezes and 13 verification call sites:

- 3 tests: G6, G7, G12.
- 10 scripts: G1, G2 ×2, G3, G4, G6 phase-1/3, G7 phase-1/3, G12.
- G13's verifier was already portable.

### Root cause

- Two incompatible freeze conventions coexist.
- G2, G3, G4, G6 and G7 were hashed over **CRLF** working-tree bytes.
  Their builders wrote text on Windows, so Git stored the content as LF.
- G1, G12 and G13 were hashed over **LF** bytes.
- No committed blob contains a CR, and there is no `.gitattributes`.
- Every verifier hashed the raw working-tree bytes. A checkout whose
  `core.autocrlf` differed from the freeze-time convention therefore
  failed, even though the content was identical.

### Baseline matrix

Clean local clones of HEAD, no private files, measured by
`m11g14_portability_matrix.py`.

| | `core.autocrlf=true` (Windows default) | `core.autocrlf=false` (Linux/macOS-like layout) |
|---|---|---|
| Raw-hash mismatches | G1, G12, G13 | G2, G3, G4, G6, G7 |
| Mismatch classification | **all newline-conversion-only** | **all newline-conversion-only** |
| Script verifiers failing | G1, G12 (2/11) | G2, G2-strategy, G3, G4, G6 ×2, G7 ×2 (8/11) |
| Hash-test files (G6, G7, G12, G13) | 2 failed, 6 errors | 2 failed |
| Full suite | **2 failed, 6 errors**, 1826 passed, 37 skipped, 18 xfailed | **2 failed**, 1832 passed, 37 skipped, 18 xfailed |

- **Corruption vs conversion.** Every mismatch was checked byte for byte.
  Mapping CRLF to LF in the checked-out file yields exactly the committed
  blob, so there is **no actual corruption** anywhere.
- **Skips.** The 37 skips (13 in the original environment) are tests that
  need the private corpora, which a clean clone does not contain. They are
  environmental and unrelated to line endings.

## Phase 2 — Canonical integrity contract

**Contract `crlf-to-lf/v1`.** Canonical bytes are the raw bytes with every
two-byte CRLF sequence (`0x0D 0x0A`) replaced by LF (`0x0A`). Nothing else
changes:

- no lone-CR handling
- no BOM removal
- no whitespace trimming
- no Unicode normalization
- no decoding or re-encoding
- no JSON parsing or reordering

This is exactly the transformation `core.autocrlf` applies, and nothing
more.

**Raw hashes are preserved.** Historical freeze records are not touched.
The new manifest (`evaluation/integrity/canonical_hash_manifest.json`) is
additive, and each entry records:

- the freeze record path
- the historical raw sha256, copied, never replaced
- the historical newline form (`lf` or `crlf`)
- the canonical sha256 and length
- the commit it was attested from

**Baselines are established independently.** The builder reads each
frozen file's committed blob (`git show HEAD:…`, never the working tree)
and accepts an entry only if re-encoding the canonical bytes in some
permitted newline form reproduces the historical raw sha256, and length
where one was recorded, **exactly**.

- All 8 tracked freezes were attested: G1, G12 and G13 as `lf`; G2, G3,
  G4, G6 and G7 as `crlf`.
- G13's freeze-time LF-normalized hash equals its attested canonical hash.
- A canonical hash is therefore never "whatever is on disk now". It is
  anchored to the original raw hash.

**Verification** (`verify_frozen_file`) never writes anything:

1. The record must name this file.
2. If the raw sha256 and length match: pass (`raw`).
3. Otherwise, all of the following must hold:
   - the manifest entry exists, uses contract `crlf-to-lf/v1`, and belongs
     to this freeze record;
   - the manifest's historical raw hash equals the freeze record's hash
     (the manifest cannot drift);
   - the canonical hash and length match;
   - re-encoding in the attested form reproduces the historical raw hash
     and length exactly. This is a direct proof against the original
     freeze.

   Then: pass (`canonical`).
4. Anything else raises `FreezeIntegrityError`. Its message names the
   failed check and says "Do not regenerate hashes: restore the frozen
   content". It subclasses `AssertionError`, so test semantics are
   unchanged.

**No silent regeneration.** The builder aborts if any attestation fails,
and refuses to change an existing manifest entry (test-enforced). The
verifier contains no write path (test-enforced).

### Helper vs `.gitattributes`

A narrow rule such as `evaluation/**/*.json text eol=lf` was considered
and **rejected as unnecessary and insufficient**:

- It would make the LF-hashed freezes (G1, G12, G13) pass everywhere, but
  the CRLF-hashed ones (G2, G3, G4, G6, G7) would then fail *everywhere*,
  including the Windows checkouts that pass today. So the helper is
  required anyway.
- It changes how every existing working tree is materialized on its next
  checkout.

The helper alone fixes both conventions with no working-tree change.

## Phase 3 — Adversarial verification

**111 tests** in `tests/test_m11g14_gold_integrity.py`.

**Synthetic fixture (original text), every historical form × checkout
form:**

- **LF ↔ CRLF equivalence:** 4/4 pass. The same form verifies via `raw`;
  the opposite form via `canonical`.
- **15 genuine content changes**, each **rejected in all 4 form
  combinations** (60/60):
  - control value
  - gold label
  - source span
  - metadata value
  - added field
  - deleted field
  - reordered keys
  - trailing space
  - tab indentation
  - extra blank line
  - missing final newline
  - Unicode NFC→NFD
  - Unicode character replaced
  - BOM added
  - truncation
- **Lone-CR line endings** (not a Git conversion): rejected (2/2).
- **10 metadata / hash corruptions**, each **rejected for both historical
  forms** on a legitimately converted checkout (20/20), so the canonical
  path itself is attacked:
  - record names another file
  - wrong `length_bytes`
  - corrupted record sha256
  - corrupted manifest canonical hash
  - corrupted manifest historical raw hash
  - wrong canonical length
  - swapped newline form
  - wrong freeze-record link
  - wrong contract
  - missing entry
- **Missing manifest:** rejected.
- **No regeneration:**
  - A failed verification leaves every file byte-identical.
  - The verifier has no write calls.
  - The builder refuses to change an altered entry and leaves it unwritten.
  - Attestation rejects a content change and a lone CR.

**Real repository:**

- The manifest covers exactly the 8 tracked frozen files, and not the
  private M11-F / M11-G9 files.
- Every manifest raw hash equals its freeze record.
- The manifest is reproducible from committed history.
- All 8 frozen files verify.
- **Real-gold tamper check:** each of the 8 real frozen files is *copied*
  to a temporary directory. LF and CRLF copies verify; a single changed
  content byte in either form is rejected (8/8).

**Conclusion:** canonicalization accepts only CRLF↔LF substitution. Every
tested change to content, whitespace, Unicode, structure, metadata or
hashes still fails.

## Phase 4 — Implementation scope

The only behavioural change in each modified file is that its freeze check
calls `verify_frozen_file` instead of comparing raw bytes:

- **Tests:** `test_m11g6_heading_classification.py`,
  `test_m11g7_section_boundary_integrity.py`, `test_m11g12_validator_hardening.py`
  (one hash test each).
- **Scripts:** `evaluate_m11g1_alternative_requirements.py`,
  `evaluate_m11g2_section_context.py`, `evaluate_m11g2_strategy_comparison.py`,
  `evaluate_m11g3_end_to_end.py`, `evaluate_m11g4_admission_recovery.py`,
  `evaluate_m11g12_validator_hardening.py`, and
  `m11g6_phase1|phase3_…`, `m11g7_phase1|phase3_…` in `scripts/evaluation_lib/`.

Notes:

- The phase-1 scripts' `"gold_hash_verified"` report field is now set to
  `True` after a verification that raises otherwise, so its value is
  unchanged.
- Now-unused `hashlib` imports and `freeze` loads were removed.
- No evaluation decision, metric, control or label logic changed.
- G13 is untouched; it was already canonical.

## Phase 5 — Cross-platform validation

### After the change

Clean local clones of HEAD plus the G14 overlay; no private files.

| | `core.autocrlf=true` | `core.autocrlf=false` |
|---|---|---|
| Raw-byte differences (still present; expected) | G1, G12, G13: newline-only | G2, G3, G4, G6, G7: newline-only |
| Script verifiers | **11/11 verified** (was 9/11) | **11/11 verified** (was 3/11) |
| Hash-test files (G6, G7, G12, G13) | **291 passed, 18 xfailed** (was 2 failed, 6 errors) | **291 passed, 18 xfailed** (was 2 failed) |
| Full suite | **1945 passed, 37 skipped, 18 xfailed, 0 failed, 0 errors** (was 2 failed, 6 errors) | **1945 passed, 37 skipped, 18 xfailed, 0 failed** (was 2 failed) |
| Files whose content differs beyond newlines | none | none |

In each clone, 1945 = the 1834 tests that previously passed or failed,
plus 111 G14 tests.

### Original environment

| | Before | After |
|---|---|---|
| Full suite | 1858 passed, 13 skipped, 18 xfailed | **1969 passed, 13 skipped, 18 xfailed** (+111 G14 tests) |
| G14 focused | — | 111 passed |
| G13 focused | 15 passed, 12 xfailed | 15 passed, 12 xfailed |
| G12 focused | 37 passed, 4 xfailed | 37 passed, 4 xfailed |
| G11 / G10 focused | 23 / 35 passed | 23 / 35 passed |
| G6 / G7 parser regression suites | 102 passed + 2 xfailed / 137 passed | unchanged |

Acceptance:

- The same historical fixtures validate under both checkout
  configurations.
- Genuine content changes still fail.
- No historical gold or raw hash was modified.
- No new skips: 13 in the original environment, 37 in clean clones,
  before and after.
- All 18 xfails are unchanged, with the same strict definitions.
- No production behaviour changed.

### Honesty about coverage

Both configurations were exercised **on this Windows machine**.
`core.autocrlf=false` reproduces the byte layout a Linux or macOS checkout
produces for these files, but **no actual Linux or macOS run was
performed**. OS-level differences (filesystem, paths, Python build) are
untested.

## Security and integrity implications

- **Accepted equivalence.** Only CRLF↔LF substitution is accepted. All 8
  covered files are JSON, where a raw CR or LF can occur only as
  inter-token whitespace (string values must escape them), so the accepted
  equivalence has no semantic effect on any parsed control or label.
- **Not for raw text fixtures.** The contract is deliberately **not**
  applied to raw `.txt` sources. For those, line endings can be
  meaningful test input (e.g. M11-A2 line-wrap handling), and extending
  coverage would need its own review.
- **Tamper-resistance.** It is no weaker than before: someone able to
  edit the frozen file *and* both the historical record and the manifest
  consistently could always defeat a hash check. Review and Git history
  remain the backstop. The manifest adds a cross-check: it must agree with
  the historical raw hash, so manifest-only tampering fails.

## Remaining portability limitations

1. Private, untracked corpora (M11-D/F/G5/G9) still verify by raw bytes.
   Git never converts them, but a tool that rewrites their line endings
   would cause a (correct, explicit) failure.
2. Without `.gitattributes`, working trees still differ by platform. Only
   the verification method differs (`raw` vs `canonical`); results do not.
3. Some scripts *record* a raw hash in regenerated reports (e.g. the G12
   report's `controls_sha256`). Regenerating such a report on a differently
   configured checkout changes that informational field. It is not a
   verification.
4. Any new freeze must either be created with `sha256_lf_normalized` (as
   G13 does) or be attested into the manifest by the builder.
5. No real Linux or macOS execution (see above).

## Changed-file inventory (committed together as one commit)

**New:**

- `docs/evaluation/MILESTONE_11_G14_GOLD_INTEGRITY_PORTABILITY.md`
- `scripts/evaluation_lib/gold_integrity.py`
- `scripts/evaluation_lib/m11g14_build_canonical_manifest.py`
- `scripts/evaluation_lib/m11g14_portability_matrix.py`
- `evaluation/integrity/canonical_hash_manifest.json`
- `evaluation/integrity/m11g14_portability_matrix_before.json`
- `evaluation/integrity/m11g14_portability_matrix_after.json`
- `tests/test_m11g14_gold_integrity.py`

**Modified** (verification call sites only):

- `scripts/evaluate_m11g1_alternative_requirements.py`
- `scripts/evaluate_m11g2_section_context.py`
- `scripts/evaluate_m11g2_strategy_comparison.py`
- `scripts/evaluate_m11g3_end_to_end.py`
- `scripts/evaluate_m11g4_admission_recovery.py`
- `scripts/evaluate_m11g12_validator_hardening.py`
- `scripts/evaluation_lib/m11g6_phase1_current_behavior.py`
- `scripts/evaluation_lib/m11g6_phase3_candidate_fix_simulation.py`
- `scripts/evaluation_lib/m11g7_phase1_current_behavior.py`
- `scripts/evaluation_lib/m11g7_phase3_candidate_fix_simulation.py`
- `tests/test_m11g6_heading_classification.py`
- `tests/test_m11g7_section_boundary_integrity.py`
- `tests/test_m11g12_validator_hardening.py`

**Unchanged:** every frozen control and gold file, every freeze record,
`src/`, G10, G11, the G12 validator, G13, the private corpora and
`.gitattributes`.

## Commit-readiness verdict

Committed after 15 final verification gates passed (including a repeat of the clean-checkout matrix with identical
results). Native Linux/macOS execution remains untested. G15 has not started.
