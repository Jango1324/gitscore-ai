# Milestone 11-G23: candidate-profile heading recovery (research)

**Status:** research only. Production is unchanged: parser `job_description_parser:v15`, scoring
`github_evidence_alignment:v2`, matcher `requirement_matcher:v1`, README `readme:v6`, registry 4. At the research
commit the two G23 **control sets** (DEV, EVAL) were registered in the G14 manifest (27 → 29); the policy design
freeze is not a control set and is not registered (§10.1).

**Outcome:** the selected policy (P4) **failed the frozen EVAL acceptance gate G1 (recall)** and passed every
safety gate. The result is preserved as measured. No policy, gate or label was changed after EVAL, and EVAL is
now an exposed holdout. **No production implementation is recommended from this milestone.**

## 1. Baseline

At HEAD `1a6e8bf` (equal to origin/main):

- versions: v15 / v2 / v1 / `readme:v6` / 4;
- tests: backend 2598 passed, 13 skipped, 18 xfailed; frontend 53;
- G14: 27 freezes;
- 18 private untracked M11 entries;
- no prior G23 work.

## 2. How v15 loses candidate-profile requirements (Phase 1)

Live path: `segmentation.segment_description()` → `parser._requirements_from_claim()` (G21 intent, then 10E
necessity, then 6B/G21 necessity, then G17 alternatives, then G22-Q concepts) → dedup.

| # | Mechanism | Where | Example | Effect |
|---|---|---|---|---|
| 1 | Heading not recognised: no family root | `_matched_heading_families` | "What you bring:", "Who you are", "The ideal candidate:" | The line becomes `UNKNOWN`. Content is admitted only through `_looks_like_requirement`, gets no necessity hint, and `resolve_necessity_hint` returns `None` unless a local marker exists. The result is an **UnparsedClaim** (visible, never scored). |
| 2 | Heading recognised as the wrong kind | `_NON_QUALIFICATION_ROOT` `^about\b` | "About you:", "ABOUT YOU" | The line becomes **SKIP**. Every line is dropped, with no claim and no diagnostic. This is the worst outcome. G6's candidate-profile exclusion covers "looking for", "we need", "you bring" and "ideal candidate", but not "about you". |
| 3 | Not a heading at all | shape gate (bare lines need Title Case plus a family root) | bare "About you", "What you bring", "Required qualifications" | The line is ordinary content, so its list stays under whatever section came before (or none). |
| 3b | Heading split over two lines / long headings | shape gate, 14-word cap | "Who we're looking" / "for:" | Neither line is a candidate-profile heading. |
| 3c | Family-less sub-heading inside a qualification section | `_classify_heading_line`, then `UNKNOWN` | "About you:" then "Technical skills:" | The nested list loses its parent section. This also happens under ordinary "Requirements:". |
| 4 | Admission logic | G21 `decide_qualification_intent` | — | Not a cause. G21 runs in every section and declines duties, employer text, benefits, learning and negation by frame. Under a recognised candidate-profile heading it already does the right thing. |
| 5 | Concepts lost after admission | G22 concept recognition and registry | bare "Go", "JS"/"TS", unregistered Kafka/Terraform/dbt, non-technical phrasing | Independent of headings; fails under "Requirements:" too. |
| 6 | Necessity | `infer_necessity` / `refine_necessity` | "is optional", "some exposure to" | Independent of headings. |

**G17** (compound containment) and **G22-Q** (alias equivalence) run downstream of segmentation and are unaffected
by any heading change. Measured in §7.

## 3. Historical failure inventory (Phase 2)

**Public, traced through the real v15 parser:**

| Case | v15 | Under P4 |
|---|---|---|
| G20 d028 "About you:" | SKIP; 2 qualifications missed entirely | 2 represented |
| G20 d029 "What you bring:" | UNKNOWN; 2 qualifications UnparsedClaim | 2 represented |
| G20 h008 "What we need from you:" | UNKNOWN; 2 UnparsedClaim | 2 represented; its non-qualification still declined |
| G20 h009 "About You" | SKIP; 2 missed | 2 represented |
| G20 h010 "Your profile:" | UNKNOWN; 1 of 2 represented | 2 represented |
| G6 candidate-profile controls (003–010, 027, 028, 033–040, 043, 044) | gold `UNKNOWN` heading, body necessity `UNKNOWN` | REQUIRED; see §7 for the frozen-label divergence |
| G7-018, G7-024 "Who We Are Looking For…" | `UNKNOWN` | REQUIRED |
| m11g3 "What You'll Bring:", m11g12 "What you'll bring:", m11g13 "### What we need" | `UNKNOWN` | changed (universal diff, §7) |

**Previously inspected private postings** (aggregate only; not evaluation data):

- **Vocabulary coverage:** the closed vocabulary matches 4 heading lines in 4 of 62 postings. v15 kinds: 2 UNKNOWN, 1
  not-a-heading, 1 already REQUIRED.
- **Proxy count (heuristic, counts only):** 8 more short candidate-facing heading-like lines are UNKNOWN,
  not-a-heading or REQUIRED with wording outside the vocabulary.

## 4. Controls, freezes and provenance (Phases 3–4)

| Set | Controls | Units | Qualification units | Families | SHA-256 (canonical, CRLF→LF) |
|---|---|---|---|---|---|
| DEV | 61 | 123 | 81 | A–T (≥3 each) | `2419157032ee343890b8403fcf90df6c595cf8acac66e2985833e29448791173` |
| EVAL | 62 | 219 | 146 (145 non-ambiguous) | A–T (≥3 each; L, R ×4) | `705276be60d64eecde9229565b8404691303075c3df04355a05170f8c76f3092` |

- **Labelling guide:** `evaluation/m11g23/labelling_guide.md`, SHA-256 `069f6b12…`. It was written before any
  policy existed and is shared by both authors. It keeps admission (`qual`), concepts (`tech`) and necessity (`nec`)
  as separate labels.
- **DEV author:** Claude (this session), who had read the v15 source. It is a design set, never validation.
- **EVAL author:** an **AI subagent**: a fresh general-purpose Claude agent instructed only with the guide.
  - It could read the registry and call `unresolved_concept_id`.
  - It had no access to `src/gitscore/jobs`, the policies, DEV or any results, and ran no parser.
  - It marked 3 units ambiguous.
  - Its file uses CRLF line endings. The raw freeze hash `38c5c38e…` is preserved, and the canonical hash above is
    the portable identity.
- **Chronology** (all on 2026-11-22 local; UTC timestamps are in the freeze records):
  1. guide written;
  2. DEV labels written and frozen;
  3. EVAL authoring started in parallel;
  4. harness and P0–P3 drafted, with a P0 fidelity sweep;
  5. EVAL frozen on receipt;
  6. DEV and historical comparison, plus ablation, then P4 defined;
  7. gates fixed and dry-run on DEV;
  8. **policy design freeze**;
  9. **one EVAL run**.
- **Disclosure:** the step-4 fidelity sweep walked every `evaluation/**` string and may have included EVAL while it was
  being written. It ran only a P0-replica-vs-production equality check, ran no policy, inspected no labels and
  printed one integer (0).

## 5. Policies and the DEV comparison (Phase 5)

**Harness.** `m11g23_harness.segment()` is a replica of production `segment_description()` with hooks.
`active(policy)` installs it where the parser, G20 replica and G22-Q dump look segmentation up, and always restores
the originals. Fidelity checks:

- P0 equals production on 31,863 strings and on DEV and EVAL;
- the P0 historical dump is byte-identical to the unpatched production dump.

| Policy | What it does |
|---|---|
| P0 | production v15 |
| P1 | A closed vocabulary of candidate-profile heading frames ("about you", "what you bring", "the ideal candidate", …), matched on curly-normalised text. It rescues only a heading production gives **no family**, or the `^about` SKIP on "About you". Maps to REQUIRED, or PREFERRED for optional-signal headings ("what would make you stand out"). |
| P2 | P1 plus: curly normalisation for every family, bare sentence-case candidate-profile lines, two-line candidate-profile headings, attribute sub-heading inheritance in REQUIRED/PREFERRED sections, and list-section paragraph reset. |
| P3 | P1 headings, but the section default applies only to a sentence the existing clause-local G21 decision reads as a qualification; otherwise it is handled like UNKNOWN. |
| **P4 (selected)** | P2 restricted to components with a measured benefit: P1, bare lines, two-line headings and inheritance. |

**DEV results (81 qualification units, 42 non-qualification units):**

| Policy | Strict recall | False-admitted units | Necessity | Fabricated concepts | Spans within unit | Controls with a newly defined score |
|---|---|---|---|---|---|---|
| P0 | 21 | 1 (duty) | 22/23 | 0 | 25/25 | — |
| P1 | 62 | 2 | 64/66 | 0 | 73/73 | 27 |
| P2 | 67 | 1 | 69/71 | 0 | 77/77 | 30 |
| P3 | 55 | 2 | 57/59 | 0 | 66/66 | 25 |
| P4 | 67 | 1 | 69/71 | 0 | 77/77 | 30 |

**Strict recall:** every expected concept is present, no unexpected concept is emitted, and necessity is right.

**Ablation of P2's components on top of P1** (recovered / false-admitted):

| Component | Result | Change vs P1 |
|---|---|---|
| inheritance | 66/2 | +4 recovered |
| two-line headings | 63/2 | +1 recovered |
| bare lines | 62/1 | −1 false admission, plus 2 genuine private qualifications |
| curly-all | 62/2 | no effect |
| paragraph reset | 62/2 | no effect |

**Remaining DEV failures:**

- **P4's one false admission:** dev-026 "No prior Rust experience is required." becomes a REQUIRED row. This is the
  documented **G21 negation-vocabulary gap** ("No prior <tech> experience…" is outside `NEGATION`). v15 hid it only
  because "About you" was SKIP. The same sentence shape is already falsely admitted by v15 on EVAL (eval-025), so
  the gap is independent of headings.
- **Other P4 DEV misses:** concept recognition (bare Go, JS/TS, unregistered technologies), non-technical vocabulary
  and necessity vocabulary ("optional").
- **P3:** loses 7 genuine qualifications that carry no G21 frame ("Java, Kotlin, or Scala.", "Has written…",
  "Comfortable writing SQL…", clearance and legal items). It prevents no false admission on DEV, G20 or the private
  aggregates, so it was not combined into P4.

**Selection.** P4 is the smallest policy whose every component showed a measured benefit. It was not chosen for
aggressiveness: P2 gives identical DEV results with a larger change surface.

## 6. Acceptance gates and the single EVAL run (Phase 6)

The gates were fixed from DEV and dry-run on DEV, where all pass. They are recorded in
`evaluation/m11g23/policy_design_freeze.json` with their justification.

| Gate | Threshold (justification) | EVAL result | Pass |
|---|---|---|---|
| G1 recall | ≥ +0.20 absolute and ≥ +15 units; DEV gain was 0.568, so the gate is about 35% of it | 53 → 62 of 145 (**+0.062, +9 units**) | **no** |
| G2a severe false admissions | new duty/employer/benefit/process unit with a registry row = 0 (the brief's minimum) | 0 | yes |
| G2b false admissions | ≤ 0.10 new per recovered unit (DEV 0.022) | 0 new | yes |
| G3 necessity | ≥ 0.90 (DEV 0.972) | 68/72 = 0.944 | yes |
| G4 no regression | 0 units lost versus P0, covering conventional headings, G17 compounds and G22-Q aliases | 0 | yes |
| G5 G19 capability | 0 counted non-technical rows | 0 | yes |
| G6 historical | every non-candidate-profile section of the G22-Q dump unchanged | unchanged | yes |
| G7 G20 false admissions | not increased | 0→0 dev; 1→1 holdout | yes |

**Verdict: FAIL (G1).** Per the protocol, the milestone stops here.

**The frozen alternatives on EVAL** (information only; they cannot change the selection):

| Policy | Strict recall | False-admitted units |
|---|---|---|
| P1 | 60 | 3 |
| P2 | 62 | 1 |
| P3 | 58 | 3 |

**What P4 changed on EVAL:**

- **Recovered:** 9 units, all with correct concepts and necessity.
- **Removed:** two v15 false duty admissions (eval-044).
- **Fabricated concept:** 1 new, `unresolved:too` from "…SQL, too." This is a G22 fragment-gate defect newly exposed
  by admission. The row is unresolved, so v2 never counts it.
- **Score effects (full evidence):** 7 controls go from an undefined score to a defined one, the denominator and
  numerator each rise by +11, 2 rows are removed and 0 MatchStatus values change on existing rows. With no evidence,
  the same 7 become defined at 0.

### 6.1 Post-hoc diagnostics (non-confirmatory)

Source: `evaluation/m11g23/eval_posthoc_diagnostics.json`, from `scripts/evaluation_lib/m11g23_posthoc.py`, written
after the failure. Only the frozen P0 and P4 were run.

**Why the gain was small.** Of the 83 qualification units P4 still misses:

| Mechanism | Units | Note |
|---|---|---|
| Concept / vocabulary | 45 | Fails under conventional headings too; out of G23's scope. |
| Heading / section | 29 | |
| Necessity | 6 | |
| Unsectioned, not admitted | 3 | |

v15 already recovers 37% of EVAL qualifications, against 26% on DEV, because the blind author used many
conventional headings.

**Heading misses** are phrasings outside the closed vocabulary:

- "THE PERSON WE'RE LOOKING FOR", "What makes you a great fit:", "Skills we need:" / "Skills we'd love:";
- "More about you:", "**What we expect**", "You'll also need", "**Optional extras**";
- "Who we’re hoping / to meet", "YOU’LL BE A GREAT FIT / IF YOU HAVE";
- 20-word headings;
- bare sentence-case conventional headings ("Required qualifications", "Preferred qualifications"), which v15 does not
  recognise at all.

**The closed-vocabulary approach does not generalise to independently written phrasing.**

**Erratum (selected-policy defect, recorded and not fixed).** P4 never rescues a **bare** sentence-case
"About you" line: production's `^about` root gives it the SKIP family, and the bare-line path then rejects it. DEV
never exercised this. Its impact is small: of the 20 qualification units under bare "About you" lines in EVAL, v15
already represents most through the existing paths, and the rest fail on non-technical or unregistered vocabulary.
Fixing it and re-running EVAL would be tuning against an exposed holdout.

## 7. Historical compatibility (Phase 7)

Each policy was measured through the G22-Q dump.

**Unchanged under every policy (P1–P4):**

- G15, G16, G18, M10D, M10E and G7 rows;
- 8c jobs, the **frozen 8c v1 / v1.1 matrices** and M10 scoring (torvalds/systems_cpp_01 = 67, libgit2 and Gifski
  unchanged);
- G13 OR-contract;
- G21 adversarial and negation-scope sets;
- G22 controls and scoring;
- **M10E-g3** (still `language.sql` REQUIRED from "You will learn SQL, but prior knowledge of databases is
  required.", 1 row, row-existence test unchanged) and M10E row existence.

**Universal diff.** Over every tracked job-like string (1,052 texts in 54 files), P4 changes rows only in the 10
texts that contain candidate-profile headings (G20 d028/d029/h008–h010 and the G20 report copies, m11g3, m11g12,
m11g13).

**G20.** The same under P1–P4:

| Split | Unit recall | Concept recall | Unit admission precision | Necessity correct | False admissions |
|---|---|---|---|---|---|
| dev | 0.836 → 0.909 | 0.889 → 0.963 | 1.0 → 1.0 | 46 → 50 | 0 → 0 |
| holdout | 0.704 → 0.889 | 0.774 → 0.968 | 0.955 → 0.963 | 19 → 24 | 1 → 1 |

**G6 / G7 frozen labels: intended, documented divergence. Gold is not rewritten.**

| Set | Heading-kind labels changed (frozen → P4) | Body necessity labels |
|---|---|---|
| G6 | **19 newly diverge.** 18 go `UNKNOWN` → `REQUIRED` (003, 004, 005, 007, 008, 009, 010, 027, 028, 033, 035, 036, 037, 038, 039, 040, 043, 044); 006 goes `NOT_A_HEADING` → `REQUIRED`. G6-034 (em-dash) diverges already under v15. | 11 move from frozen `UNKNOWN` (reported, not scored) to scored `REQUIRED`: 005, 007, 008, 009, 010, 027, 028, 033, 037, 039, 040. The 3 pre-existing body mismatches (020, 022, 043) are unchanged. |
| G7 | 2: 018 and 024, `UNKNOWN` → `REQUIRED` | the 5 pre-existing body mismatches are unchanged |

These follow directly from reversing G6's explicit "candidate-profile headings stay UNKNOWN, never default
REQUIRED" decision, as G20 forecast (16 + 2 with its smaller vocabulary).

**G17, G22-Q, G21, G19:**

- EVAL families Q (compound) and R (aliases): 0 regressions (gate G4).
- G21 controls are unchanged, and a G21 gap is newly exposed under recovered headings (§5).
- G19: 0 counted non-technical rows anywhere (G5).

**Private** (counts only, `private_candidate_profile_aggregates.json`):

- **P4, labelled postings:** qualifications admitted m11d 57→59, m11f 41→42, m11g5 81→85, every one with correct
  necessity. Admission precision is unchanged or higher.
- **P4, unlabelled postings:** +9 rows in one posting, from inheritance under a conventional **Requirements** section
  with a "…skills" sub-heading. All 9 sentences are qualification-framed by G21, but they are unverified.

## 8. Implementation feasibility (Phase 8)

**No production change is recommended now.** If a later milestone revisits this, the smallest safe shape the
evidence supports is:

- **Where:** `segmentation.py` only:
  - a candidate-profile rescue inside `_classify_heading_line` / `_matched_heading_families`, reachable only when no
    family fires or only `^about` fires on "about you";
  - bare-line and two-line recognition;
  - sub-heading inheritance in `segment_description`.
- **What stays unchanged:** clause-level admission. G21 already declines duties, employer text and benefits under a
  recognised section, and P3 shows a stricter gate only loses recall. The necessity, alternatives, concepts,
  registry, matcher, scoring, API and README extractor are unchanged too.
- **Inheritance:** needed for nested lists (family J). It also changes conventional Requirements sections, which is
  outside candidate-profile scope; see the private +9 rows.
- **Version:** parser v15 → v16, with version-pinned historical tests in the style of the README pins. G6 and G7
  label tests would need a v15 pin; their frozen gold stays as is.
- **Provenance:** spans and provenance are unchanged. Every recovered row keeps its exact source span (P4: all rows
  within their unit on DEV; 83/85 on EVAL, the same 2 multi-unit claims as v15).
- **Scoring v2:** formula unchanged and compatible. Effects come only through more counted rows: denominators rise
  and undefined scores become defined.

**What blocks it.** A closed vocabulary missed most independently written phrasings (§6.1). A future attempt needs
a **fresh** blind set and a different recognition approach, for example a structural candidate-facing-heading signal
rather than a phrase list. It also needs the decisions in §11. The G21 "No prior <tech> experience" negation gap
should be closed first, because recovering headings increases its exposure.

## 9. Verification (Phase 10)

- **G23 research tests:** 19/19. They check frozen hashes, design-freeze integrity, schema validity, P0 fidelity on
  DEV and EVAL, pin restoration, no `src/` import, versions, v15 mechanism traces, recorded DEV/EVAL metrics
  reproduced for every policy, the preserved G1 failure, unchanged historical sections, and a counts-only private
  file.
- **Full backend suite:** 2617 passed, 13 skipped (the same 10 M10E + 3 M11-A2), 18 xfailed, 0 failed. That is the
  2598 baseline plus 19.
- **Frontend:** 53/53.
- **G14:** 27/27 freezes verified at research time; 29/29 after the registration in §10.1.
- **Scope:** versions v15 / v2 / v1 / `readme:v6` / 4. No `src/`, `frontend/` or tracked `evaluation/` change. The
  18 private entries are untouched.
- **Fidelity sweep:** the 31,863-string P0 fidelity sweep was a one-off scratch check; the committed runner and tests
  re-check DEV, EVAL and the full historical dump.

## 10. Files

All research-only and uncommitted.

| Kind | Path |
|---|---|
| Controls and guide | `evaluation/m11g23/labelling_guide.md`, `controls_dev.json`, `controls_eval.json` |
| Freezes | `controls_dev_hash_freeze.json`, `controls_eval_hash_freeze.json`, `policy_design_freeze.json` |
| Outputs | `candidate_profile_report.json`, `private_candidate_profile_aggregates.json`, `eval_posthoc_diagnostics.json` |
| Harness | `scripts/evaluation_lib/m11g23_{harness,policies,eval,historical,dump_under_policy,validate_controls,build_dev_controls,posthoc}.py` |
| Runner | `scripts/evaluate_m11g23_candidate_profile_headings.py` |
| Tests | `tests/test_m11g23_candidate_profile_headings.py` |

### 10.1 G14 registration (research commit, 2026-11-25)

The DEV and EVAL control sets are registered in `evaluation/integrity/canonical_hash_manifest.json` (27 → 29). The 27
existing entries are unchanged field for field.

| Control set | Freeze-time raw SHA-256 | Historical form | Canonical SHA-256 |
|---|---|---|---|
| DEV | `2419157032ee343890b8403fcf90df6c595cf8acac66e2985833e29448791173` | lf | same |
| EVAL | `38c5c38ea1a788a8a9ff7267043a349f8e140fe4ca6892ba03dbe8ae3b84c67f` | crlf | `705276be60d64eecde9229565b8404691303075c3df04355a05170f8c76f3092` |

**EVAL provenance.** The raw hash is the one recorded at freeze time (2026-11-23 04:58:13 UTC), and the working-tree
file was last modified before it (04:57:11 UTC). All 3,406 line endings are CRLF, with no lone CR or LF. So CRLF→LF
normalisation is lossless, and re-encoding the canonical bytes with CRLF reproduces the raw hash exactly; G14's
`attest()` / `verify_frozen_file()` re-check this reconstruction. The parsed content, labels and ordering are
identical. The canonical hash was **not** recorded at freeze time: it was first computed after the EVAL run and
re-verified at registration. The freeze record states this, and its freeze-time fields are unchanged. The G14 field
names (`frozen_file`, `length_bytes`, `sha256_lf_normalized`, `canonical_contract`) were added to both control
freeze records at registration, each with a note.

**Post-EVAL amendment.** The runner's `_sha()` now hashes CRLF→LF-normalised bytes, because the EVAL file arrived
with CRLF. Only `report.frozen_inputs` changed; every measured section equals the single EVAL run. The original and
amended hashes are recorded in the design freeze.

## 11. Decisions needed

1. **G6/G7 reversal:** accept reversing G6's "candidate-profile headings stay UNKNOWN / never default REQUIRED"
   decision? That means 19 G6 + 2 G7 heading labels and 11 G6 body necessity labels diverge from frozen gold under a
   future parser version.
2. **After the G1 failure:** retire the closed-vocabulary approach, or fund a different recognition design with a
   **new** blind EVAL set? The current EVAL is exposed.
3. **G21 negation gap:** close "No prior <tech> experience is required" first?
4. **Inheritance scope:** should sub-heading inheritance apply to conventional Requirements sections, which affects
   unlabelled private postings, or only to candidate-profile sections?
5. **Separate milestone?** Bare sentence-case conventional headings ("Required qualifications") are not recognised
   by v15 at all.
6. *(Resolved: the research commit and the registration of the two G23 control sets, 27 → 29, were authorized; the
   policy design freeze stays unregistered.)*
