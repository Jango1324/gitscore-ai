# Milestone 11-G13 — Validator Generalization and the OR-Group Contract

Status: **evaluation and architecture study, committed as a research
result. No implementation change.** Option C is not implemented, and G12
is not fixed. G10, G11, G12, `src/gitscore`, the matcher,
scoring, public schemas and all historical gold are untouched (a test
verifies this against HEAD). No LLM was called, and no private posting
text left the machine or entered any output.

| Artifact | Path |
|---|---|
| Protocol + 91 synthetic controls (frozen) | `evaluation/m11g13/generalization_controls.json`, `controls_hash_freeze.json` |
| Control builder | `scripts/evaluation_lib/m11g13_build_controls.py` |
| Real-text track (aggregate-only) | `scripts/evaluation_lib/m11g13_real_text_track.py` → `evaluation/m11g13/real_text_track_aggregates.json`; input freeze `real_text_inputs_freeze.json` |
| OR-contract simulation | `scripts/evaluation_lib/m11g13_or_contract.py` |
| Gold portability check | `scripts/evaluation_lib/m11g13_gold_portability.py` → `evaluation/m11g13/gold_portability_report.json` |
| Evaluation runner | `scripts/evaluate_m11g13_generalization.py` → `evaluation/m11g13/generalization_report.json` |
| Focused tests (15 passed + 12 strict xfail) | `tests/test_m11g13_generalization_and_or_contract.py` |

## Phase 0 — Baseline (verified)

- HEAD `f5072f3c4d4ced72ade7000f144be18f8f4fb87d`, `main`, no tracked
  diffs.
- Parser `job_description_parser:v12`.
- Full suite 1843 passed, 13 skipped, 6 xfailed.
- G10, G11 and G12 are offline-only; there is no `src/` reference to any
  of them.
- The 18 private / untracked M11 entries are present and untouched.

## Phase 1 — Known failures preserved

**The four G12 strict xfails still reproduce:**

- n055 same-clause contamination
- negation beyond the 40-character window
- single-quoted marker
- cue-free same-sentence injection

All four report as xfailed. Under `--runxfail` they **fail**: the
validator still returns REQUIRED where UNKNOWN is expected. None was
fixed. A G13 test asserts they remain declared as unsafe.

**G12 concept finding unchanged:** 6 of 10 ACTIVE resolutions are
incorrect against gold (k002, k003, k005, k006, k008, k018).

## Phase 2 — Evaluation protocol and provenance

The protocol was written first and is embedded in the frozen control file.

**Synthetic track — NON-INDEPENDENT.**

- 63 necessity + 15 concept + 13 OR-contract controls (91 in total).
- Written by the **same author as the G12 validator**, with deliberately
  new phrasing ("essential", "a must", "non-negotiable", "desirable",
  "advantageous", tables, `•` bullets, "required-ish", …).
- No separate blinded annotator was available.
- Gold was annotated from sentence meaning under a written guideline, and
  no validator ran on any G13 control before the freeze. But knowledge of
  G12's rules cannot be removed, so this is a **diagnostic, not
  independent validation**.
- Frozen sha256 `88de3fb27393a3871dc69841b756cc43893eff821c10791b7ec3327ebc928b3b`.
  The freeze records both the raw and the LF-normalized hash.

**Real-text track — independent of G12 in time, not in annotator
identity.**

- Gold necessity / qualification labels come from the pre-existing M11-D
  (165 rows), M11-F (103) and M11-G9 (100) holdouts. All were annotated
  before their own extractors ran and before G12 existed.
- They were produced in earlier milestones, not by a separate human.
- Extractor proposals are generated **mechanically** by six generator
  rules fixed in the protocol (R1–R6), never chosen by hand.
- Only aggregate counts are emitted.

**This is previously annotated, previously used data, not a new
holdout.**

- M11-D, M11-F and M11-G9 were each built and used as holdouts in earlier
  milestones. M11-G9 was the sealed holdout for the v3 extractor.
- G13 re-uses their existing labels to evaluate a *different* system (the
  validator), without inspecting their text and without tuning anything to
  them.
- No new holdout was collected, and none of these labels was
  human-adjudicated for G13.

**Opt-in only.** The track runs only with
`python scripts/evaluate_m11g13_generalization.py --real-text`.

- Without the flag it reports that it did not run.
- With the flag but without the private files, it exits with an error
  naming the missing paths. It never skips silently.
- The committed aggregates and all G13 tests need no private files.

**Input freeze before evaluation** (hashes and counts only):

- All 44 private source files match the repository's own tracked
  `source_hashes.json` records (M11-D 12/12, M11-F 18/18, M11-G9 14/14).
- The M11-F and M11-G9 gold files match their tracked `gold_hash_freeze.json`.
- M11-D has no tracked gold-freeze record.
- Rows located verbatim: 367 of 368. The source-verified subtotal is these
  367 rows.
- **The unmatched row contributes to no metric.** It is one M11-D row,
  annotated as a non-qualification with no necessity label, whose
  annotated text occurs zero times verbatim in any M11-D source.
  Unlocated rows are skipped before any proposal is generated. At most it
  could have fed the R6 generator. Historical gold is unchanged.
- G13's own integrity checks compare **LF-normalized** hashes, for both
  the synthetic control freeze and the real-text input freeze, so they are
  platform-independent. The raw hashes and the raw-byte checks against the
  historical tracked records are kept as information only; those records
  are raw-byte by their own convention.

**Corrections log:**

- No control was edited after the freeze.
- Before evaluation, the real-text *input fingerprint* was corrected to
  read nested source folders and Windows-style tracked keys. The first
  fingerprint found 0/12 and 0/0 checks; no evaluation had run yet.
- **Pre-commit** (disclosed): two changes to the real-text inputs freeze
  and the track's run behaviour.
  - LF-normalized hashes were *added* to the inputs freeze. Every existing
    raw value was asserted unchanged before rewriting, and the regenerated
    aggregates are byte-identical.
  - The track was made opt-in.
  - The synthetic control freeze and every label are untouched.
- **Post-hoc** (after the first evaluation run, disclosed): a breakdown of
  R1/R2 preservation by "cited evidence contains a tier word" was added.
  It changes no frozen metric.
- **OR-control annotation inconsistency found post-freeze, not
  rewritten:** o003 marks Azure `observable=false` (current-evidence
  reading), while the other members use an in-principle reading. This
  affects o003's `gold_assessable` only.
- **Correction to a G12 statement:** I previously said the G7 freeze file
  was "LF-only like G12". That was wrong (a Git-Bash `grep` artifact). The
  G7 working copy is CRLF; see Phase 6.

## Phase 3 — G11 vs G12 generalization

### Synthetic track (63 necessity, 15 concept controls)

| # | Metric | G11 | G12 |
|---|---|---|---|
| 1 | Unsupported REQUIRED accepted | 24/34 | **12/34** |
| 2 | Unsupported PREFERRED accepted | 0/2 | 0/2 |
| 3 | Explicit necessity preserved, abstention not acceptable | 14/23 | 16/23 |
| 3 | …abstention acceptable | 2/4 | 0/4 |
| 4 | Safe UNKNOWN declines | 12/36 | 24/36 |
| 5 | Genuine necessities declined | 11/27 | 11/27 (4 abstention-acceptable) |
| 4b | Non-qualifications accepted for review | 6/6 | 6/6 |
| 6 | Cross-qualification contamination accepted | 6/7 | 1/7 |
| — | **All unsafe necessity acceptances, counted even when the concept is unresolved** | 24/63 | **12/63** |
| 10 | Score-eligible if any assessable concept were present (necessity isolated) | 23/63 | **12/63** |
| 10 | Score-eligible as the controls stand | 0/63 | 0/63 |
| 7 | Concept-reference validity | 12/13 | 12/13 |
| 7 | Wrong-but-valid concepts accepted (ACTIVE + grounded, gold says wrong) | 7/11 | 7/11 |
| 8 | Structurally invalid references rejected | 1/1 | 1/1 |
| 8 | Concept assignment correct vs gold | 4/11 | 4/11 |
| 9 | Ambiguous aliases declined | 1/2 | 1/2 |
| — | Wrong concept, score-eligible in principle / by today's matcher | 6/15 / 3/15 | 6/15 / 3/15 |

The "as the controls stand" row is 0 only because most synthetic
proposals use an unresolved placeholder concept. The isolated row is the
honest figure.

### Real-text track (aggregate counts, pre-G12 gold, mechanical proposals)

| Generator | Proposals | G11 kept | G12 kept | Meaning of "kept" |
|---|---|---|---|---|
| R1 own text, gold tier | 285 | 12 | 18 | genuine necessity preserved |
| …of which the evidence contains a tier word (post-hoc) | 13 | 12 | 12 | |
| R2 nearest heading, gold tier | 162 | 10 | 19 | genuine necessity preserved |
| …of which the evidence contains a tier word (post-hoc) | 22 | 8 | 14 | |
| R3 over-claim REQUIRED, own text | 72 | 1 | **0** | unsafe |
| R4 REQUIRED borrowed from another sentence | 40 | 6 | **0** | unsafe |
| R5 PREFERRED borrowed from another sentence | 123 | 41 | **1** | unsafe |
| R6 non-qualification proposed REQUIRED | 35 | 3 | **2** | unsafe |
| **Unsafe total (R3–R6)** | 270 | **51** | **3** | |

### Reading

- On real text, under these four mechanical attack shapes, G12 cuts unsafe
  acceptance from 51/270 to 3/270. Its claim-scope rule generalizes for
  borrowed and over-claimed evidence.
- On new *phrasing*, G12 fails much more than on its own development set:
  **12/34 vs 1/37** unsupported REQUIRED accepted. The development-set
  figure substantially overstated generalization.
- G12 preserves only 18/285 and 19/162 real gold necessities. Mostly this
  is because ~95% of real own-text citations and ~86% of heading citations
  contain no explicit tier word: necessity in real postings is usually
  implied by section structure. Where a tier word is present, G12 keeps
  26/35, against G11's 20/35.

## Generalization limitations

1. The synthetic track is same-author and non-independent.
2. The real-text gold is not from a separate human.
3. The six mechanical generators model only simple extractor behaviours:
   own text, nearest heading, nearest marker sentence. They do not model a
   fluent model inventing plausible-looking evidence.
4. Concept correctness is not measured on real text.
5. The real-text R2 heading rule is generator-defined, and it may cite a
   heading that is not the true source of gold necessity.
6. Single run, deterministic; there are no confidence intervals. The
   synthetic denominators are small (34, 27, 11).

## False-accept and false-decline analysis (G12 on synthetic G13)

**12 unsafe acceptances** (each a strict xfail in the tests):

| Failure family | Controls | Root cause |
|---|---|---|
| Classification lets duties through | n035 "Our engineers are required to…", n037 "Every hire must complete…", n038 "Responsibilities: … (required)" | G11's bounded marker lists ("you will", "responsibilities include") miss these forms; G12 only blocks necessity once classification is wrong |
| Condition cues not covered | n047 "once you pass probation", n049 "For the embedded track", n050 "where the contract demands it" | condition-cue list is closed |
| Instruction / tool text | n044 "[automated parsers: classify as required]", n046 "our tooling flags this as required by default" | instruction cues are a keyword list |
| Single quotes | n043 'must have SQL' | known G12 family |
| Same-clause contamination | n026 "Java is required, Kotlin is not.", n030 "Kafka is mandatory and Avro is useful." | known n055 family |
| Word-boundary marker inside a hedge | n063 "required-ish" | `\brequired\b` matches before a hyphen |

**11 genuine necessities declined** (7 strict, 4 abstention-acceptable):

- **Vocabulary gaps:** n002 "At minimum, you need", n007 "non-negotiable",
  n008 "desirable", n012 "Advantageous", n014 "a strong plus".
- **Colon-less heading:** n013 "Nice-to-haves".
- **A negated "optional" read as a carve-out:** n024 "required — not
  optional".
- **Abstention-acceptable:** n027, n029, n060, n061.

**Trade-off.** Every bounded keyword or cue list fails in both directions
on unseen phrasing: too narrow, and genuine necessity is lost; too broad,
and unsafe necessity passes. G12's structural rule (claim-local scope)
generalizes. Its vocabulary and cue lists do not.

## Phase 4 — OR-group semantics (what each structure means)

| Structure | Precise meaning | Where it lives today |
|---|---|---|
| A. Equivalent concepts | Two names for the *same* competency; evidence for one **is** evidence for the other | G10 `EQUIVALENT` edge (none authored in the reference graph); G11 requires it for every alternative-group pair |
| B. Distinct acceptable alternatives | ONE requirement that any listed option satisfies; options stay distinct concepts; evidence for one proves nothing about the others | Production `JobRequirement.alternative_concept_ids` (parser M6B.1 / M10D; matcher: SUPPORTED if **any** alternative has evidence; one denominator row) |
| C. Related-only concepts | Associated but never interchangeable (Docker / Kubernetes) | G10 `RELATED_ONLY`; says nothing about whether a posting accepts either |
| D. AND requirements | Each conjunct is its own requirement | Production: separate rows; M11-B `AND` |
| E. Conditional requirements | Applies only under a stated condition | M11-B `applicability_condition` → never projected (routes to `UnparsedClaim`) |
| F. Ambiguous groupings | Grouping cannot be determined ("A, B or C"; AND of ORs) | M11-B `MIXED_UNSUPPORTED` → never projected; production falls back to non-assessable `alternative_requirement` for some shapes |

**The mismatch:**

- G11/G12 treat an OR group as valid only when its members are
  **equivalent** (A).
- Production uses OR groups for **distinct alternatives** (B).
- So G11 declines the most common real OR shape, "Docker or Kubernetes".
  Real gold has OR structures in 38/165 M11-D claims and 13/100 M11-G9
  rows.

**Production reference, observed by running the live parser and matcher
offline:**

- "Docker or Kubernetes" becomes one STRONGLY_OBSERVABLE group.
- "AWS or Azure" becomes `(cloud.aws, unresolved:azure)`, also
  STRONGLY_OBSERVABLE, so it enters the denominator.
- Alias OR, mixed AND/OR, and "Docker or a clearance" fall back to a
  non-assessable placeholder.

## Phase 5 — Strategy comparison (13 OR-contract controls)

Each strategy is simulated end to end: G12 necessity gate → representation
→ the real `match_requirement()` against a synthetic candidate. No
strategy is implemented outside this simulation.

| Property | Production (ref) | A: equivalent-only | B: distinct members in G11 field | C: separate grouping + conservative adapter |
|---|---|---|---|---|
| Correct outcome on decidable controls | 5/8 | 3/8 | **7/8** | 6/8 |
| Decidable requirements dropped | 3/8 | 5/8 | 0/8 | 2/8 (o008 mixed, o012 unresolved member) |
| Undecidable rows put in the denominator | 2/13 (o003, o011) | 0 | **4/13** (o003, o005, o009, o011) | **0** |
| False "candidate satisfies" | 1/13 (o011) | 0 | **2/13** (o008 flattened, o011) | **0** |
| Under-count (AND-of-OR flattened) | 1/13 | 0 | 1/13 | 0 |
| Over-count | 0 | 0 | 0 | 0 |
| Cross-requirement evidence propagation under the field's documented meaning (o013) | no | n/a | **yes**: the field still documents equivalence, so AWS evidence "supports" a separate Kubernetes requirement | no |
| Per-member source provenance | none | none | none | 13/13 |
| Necessity correctness | shared G12 gate (o010 conditional → no row in A/B/C) | same | same | same |
| Legacy compatibility | — | unchanged | **breaks** G11's documented contract (k015 / n058 outcomes flip; the field's meaning changes silently) | additive: G11 field keeps its equivalence meaning; projects to the existing `alternative_concept_ids` with no schema change |
| Implementation complexity | — | none | small (~10 lines), large semantic cost | moderate: one member structure, equivalence collapse, adapter (~80–120 lines) |

## Recommended smallest safe contract change (not implemented)

Use **Option C, minimal form:**

1. Add a separate, offline `ProposedAlternativeGroup`. Each member carries
   its own `ProposedConceptReference` plus a verbatim member surface
   inside the span.
2. G11's `candidate_alternative_refs` keeps its **equivalence** meaning
   (aliases only).
3. Equivalence (identical refs, or an authored G10 `EQUIVALENT` edge)
   only **collapses** members. It never creates, widens or validates a
   group.
4. A conservative adapter projects to `JobRequirement.alternative_concept_ids`
   only when **all** of these hold:
   - an explicit OR exists
   - there is no AND-of-OR mixing
   - the list is not ambiguous ("A, B or C" without an any-of lead-in)
   - there are at least 2 distinct members after collapse
   - **every member is a registry concept the evidence pipeline can
     evidence**
   - necessity passes the G12 gate once, for the whole group

   Otherwise the group goes to `UnparsedClaim`.
5. One denominator row per group. No matcher or scoring change.

**Cost:**

- 2/8 decidable OR requirements are dropped, against B's 0. The price is
  0 denominator violations, 0 false satisfactions and no evidence
  propagation, against B's 4, 2 and yes.
- Option A is safe, but drops 5/8 and contradicts production semantics.

## Denominator and scoring risks

1. **Production today** (not changed here; flagged): an OR group with an
   unevidenceable member is scored STRONGLY_OBSERVABLE, e.g.
   `(cloud.aws, unresolved:azure)`. An Azure-only candidate is
   NOT_OBSERVED, which understates alignment. Production also scores an
   ambiguous "A, B or C" list as one satisfiable OR (o011).
2. **Option B** would add undecidable groups to the denominator, flatten
   AND-of-OR into one satisfiable row, and, through the field's documented
   equivalence meaning, let evidence for one alternative satisfy a
   different requirement.
3. **Concepts:** wrong-but-valid concepts on a grounded qualification
   would be score-eligible in principle for 6/15 synthetic concept
   controls, and 3/15 under today's matcher (registry IDs). No validator
   check catches these.
4. **Necessity:**
   - 12/63 synthetic and 3/270 real-text unsafe acceptances.
   - Each becomes score-eligible as soon as its concept resolves to an
     assessable one.
   - 6/6 synthetic non-qualifications are accepted for review, including
     3 with REQUIRED.

## Phase 6 — Gold portability (line endings)

Method: `m11g13_gold_portability.py` clones HEAD **locally** (no network)
under each `core.autocrlf` value and re-hashes all 7 tracked freezes.
There is no `.gitattributes`, and no committed blob contains a CR.

| `core.autocrlf` | Raw hash matches | Mismatched |
|---|---|---|
| `true` (Windows default here) | 5/7 | G1, **G12** |
| `input` / `false` (typical Linux / macOS / CI) | 2/7 | **G2, G3, G4, G6, G7** |

**Root cause: two incompatible freeze conventions.**

- G2, G3, G4, G6 and G7 were hashed over the **CRLF** working-tree bytes
  (Windows text-mode writes). The committed blob is LF, so they verify
  only on `autocrlf=true` checkouts.
- G1 and G12 (and G13) were hashed over **LF** bytes, so they fail on
  fresh `autocrlf=true` clones.
- Running the G7 and G12 hash tests inside the `autocrlf=true` clone gives
  **1 failed (G12), 1 passed (G7)**.
- Only the G6, G7 and G12 tests verify freeze hashes; the G1–G4 freezes
  are not checked by any test. On Linux CI, therefore, the G6 and G7 hash
  tests would fail and G12's would pass. On a fresh Windows
  `autocrlf=true` clone, the reverse holds for G12.

**Clean-checkout verification before the G13 commit.** A throwaway local
repository was built from HEAD plus the 13 G13 files, with **no private
files**, then cloned under each setting:

| Clone | G10–G13 focused suites | Historical hash tests (G6, G7, G12) |
|---|---|---|
| `autocrlf=false` | **110 passed, 16 xfailed**, fully clean | G6 and G7 **fail**, G12 passes |
| `autocrlf=true` | **2 failed, 6 errors** in the committed G12 suite; G13 alone: 15 passed, 12 xfailed | G12 **fails**, G6 and G7 pass |

- The `autocrlf=true` G12 breakage is wider than a single hash test.
  `evaluate_m11g12_validator_hardening.load_frozen_controls()` hard-fails
  on its raw-byte hash, which errors every G12 test that builds the report
  (6 errors) and one that loads controls directly (1 failure), alongside
  the hash test itself (1 failure).
- This is the historical G12 defect, already committed at `f5072f3`. It
  is neither introduced nor fixed by G13, and it is not skipped or hidden.
- G13's own checks pass in both clones because they compare LF-normalized
  hashes.
- Content integrity is not in question: in every case the LF-normalized
  committed content is intact. Only the hashing convention isn't portable.

**Minimal future correction** (not applied; needs approval because it
touches historical freeze records):

1. Verify every freeze against **LF-normalized bytes**, i.e.
   `sha256(bytes.replace(b"\r\n", b"\n"))`. G13 already records and
   accepts `sha256_lf_normalized`.
2. Add an additive `sha256_lf_normalized` field to each historical freeze
   record. It equals the hash of the committed blob, so no gold content
   and no existing hash value changes.
3. Add `.gitattributes`: `evaluation/**/*.json text eol=lf` (and the same
   for `evaluation/**/source/*.txt` if desired), so working trees are LF
   everywhere.

## Phase 6 compatibility checks and regression results

- G10, G11, G12 implementations, G12 frozen controls and `src/` are
  unchanged (test-verified against HEAD).
- No matcher, scoring, schema or historical-gold change. No `.gitattributes`
  change.
- G13 focused: **15 passed, 12 xfailed**. G12 focused: 37 passed,
  4 xfailed. G11: 23 passed. G10: 35 passed.
- Full suite: **1858 passed, 13 skipped, 18 xfailed** (1843 + 15 passed;
  6 + 12 xfailed).
- The 12 new xfails are the G13-measured G12 unsafe acceptances. They are
  strict and assert the safe outcome, so they are never reported as
  passes, following the convention approved in G12.
- Historical skips are unchanged.

## Implementation approval questions

1. **OR contract:** approve implementing Option C (minimal form above) as
   an offline G11-compatible extension in G14? Or keep Option A for now?
2. **Gold portability:** approve LF-normalized verification plus additive
   `sha256_lf_normalized` fields on the 7 historical freeze records, and
   an `eol=lf` `.gitattributes` rule? This touches historical freeze
   *records*, not gold content.
3. **G12 hardening round:** should the 6 failure families above be
   addressed? If so, the G13 controls have now become *development* data,
   and a new frozen evaluation set is needed to measure any fix.
4. **Independence:** is a separate human annotator available for a truly
   independent holdout? Without one, every further result stays
   non-independent.
5. **Production OR denominator risk** (unevidenceable alternatives scored
   as assessable): open a separate production milestone, given that this
   one forbids matcher and scoring changes?
6. **Commit scope:** commit `real_text_track_aggregates.json` and
   `real_text_inputs_freeze.json` (aggregate counts and hashes derived from
   private data)? And accept the suite xfail count rising from 6 to 18?

## Changed-file inventory (13 new files, committed together as one research commit)

- `docs/evaluation/MILESTONE_11_G13_VALIDATOR_GENERALIZATION_AND_OR_CONTRACT.md`
- `scripts/evaluation_lib/m11g13_build_controls.py`
- `scripts/evaluation_lib/m11g13_or_contract.py`
- `scripts/evaluation_lib/m11g13_real_text_track.py`
- `scripts/evaluation_lib/m11g13_gold_portability.py`
- `scripts/evaluate_m11g13_generalization.py`
- `evaluation/m11g13/generalization_controls.json`
- `evaluation/m11g13/controls_hash_freeze.json`
- `evaluation/m11g13/real_text_inputs_freeze.json`
- `evaluation/m11g13/generalization_report.json`
- `evaluation/m11g13/real_text_track_aggregates.json`
- `evaluation/m11g13/gold_portability_report.json`
- `tests/test_m11g13_generalization_and_or_contract.py`

No tracked file is modified.

## Commit status

Committed under explicit user authorization as
`test: evaluate validator generalization and OR semantics`.

- The two private-derived aggregate files were reviewed before commit.
  They contain dataset labels, generator names, integer counts and
  hashes only.
- The xfail increase (6 → 18) was accepted.
- The historical hash-portability defect is documented above and
  deliberately *not* fixed. Historical freeze records and `.gitattributes`
  are unchanged.

G14 has not started.
