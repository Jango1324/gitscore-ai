# Milestone 11-D — Independent Generalization Validation

**Status: evaluation execution only. No algorithm modified, no production
code touched, no commit made.** `git diff --name-only -- src/gitscore`
is empty throughout this milestone — every file this document discusses
is new, additive, and read-only against `competency_extraction.py` as
committed in M11-C.

## 1. Verified baseline

| Check | Expected | Actual |
|---|---|---|
| HEAD | `b3cc7b1e8a3c6f70d9c195f9f14d8ec635961a6c` | confirmed |
| Branch | `main` | confirmed |
| Parser version | `job_description_parser:v10` | confirmed, unchanged |
| Tests | 1372 passed, 13 skipped | confirmed, unchanged after this milestone's own work |
| Offline competency extractor | committed, unmodified | confirmed — `git diff --name-only -- src/gitscore` empty |
| M11-C development evaluation | unchanged | confirmed — `evaluate_m11c_offline_extractor_safety.py` re-run, byte-identical (26/28 recall, 26/26 precision, 20/20 necessity, 27/28 logical grouping, 28/28 span exactness) |
| Frozen historical gold | unchanged | confirmed, `git diff --stat` empty |
| Five M11 generalization files | untracked, preserved | confirmed present |

---

## 2. Authentic corpus inventory and provenance

**12 authentic, independently-sourced job postings** were acquired via
`WebSearch` (queries scoped to `boards.greenhouse.io`/
`job-boards.greenhouse.io`/`jobs.lever.co`) and retrieved via `WebFetch`
with an explicit instruction to return complete, verbatim text. Full
provenance — employer, role, source URL, domain, seniority — is
recorded in `evaluation/m11d/provenance.json`; raw text is saved
verbatim in `evaluation/m11d/source/*.txt`.

### Target vs. actual — reported explicitly, not minimized

| | Target | Actual |
|---|---|---|
| Postings | 20–30 | **12** |
| Annotated qualification spans | ≥100 | **165** |

**Why the posting-count shortfall:** the large majority of specific
job-posting URLs returned by `WebSearch` (e.g. `boards.greenhouse.io/<company>/jobs/<id>`)
had already migrated to `job-boards.greenhouse.io` and/or expired by
fetch time — confirmed directly, not assumed: repeated `WebFetch` calls
against these specific IDs returned the company's general job-INDEX
page (hundreds of unrelated open roles) rather than the posting itself,
or a plain 404. This reflects how quickly real postings churn (filled
or closed roles), not a tooling malfunction. Acquisition continued
until 12 postings were successfully, verifiably fetched across every
one of the 10 requested domains, then stopped — padding the corpus
with synthetic or non-independently-sourced material to reach 20–30
was explicitly rejected, per this milestone's own instruction.

The annotation-span target (≥100) was still exceeded (165), by
annotating densely within each of the 12 postings' own Requirements/
Preferred-Qualifications/Responsibilities/About sections rather than
one span per posting.

### Domain and seniority coverage

| Domain | Postings | Employer(s) | Seniority represented |
|---|---|---|---|
| software_engineering_general | 2 | Scale AI, SpaceX | junior/new-grad |
| backend_distributed_systems | 1 | Figma | senior |
| ai_ml | 1 | May Mobility | mid |
| robotics_autonomy | 2 | Field AI (×2) | mid, senior |
| embedded_systems | 1 | Anduril Industries | senior |
| electrical_engineering | 1 | Voyager Technologies | senior |
| systems_performance_engineering | 1 | Real-Time Innovations | senior |
| cybersecurity | 1 | Anthropic | mid |
| infrastructure_cloud | 1 | Together AI | staff/senior |
| data_engineering | 1 | Anthropic | mid |

All 10 requested domains have at least one posting. 8 of the 10 have
exactly one — **a thin sample, disclosed explicitly in §8 below, never
treated as statistically representative of that domain.**

**A disclosed corpus-integrity limitation:** `WebFetch` processes
fetched HTML through its own extraction model before returning text —
this is NOT a byte-for-byte scrape of the live page's raw HTML/DOM.
The saved source text is the best-effort verbatim capture this tool
provides, not a guaranteed exact copy; `provenance.json`'s own
`methodology` field states this explicitly. One concrete, observed
consequence: `WebFetch`'s own extraction imposes a fairly uniform
Markdown heading structure on every posting regardless of the original
page's own formatting, which flattens some of the "posting structure"
variation (§7's own writing-style axis) this milestone set out to
measure — also disclosed, not hidden.

None of these 12 postings is SOTI, Manulife, NVIDIA, or any posting
previously inspected in M11/M11-B/M11-C's own development material —
confirmed by direct comparison of employer and role title.

---

## 3. Hash-frozen annotation integrity

- Every one of the 12 raw source files was hashed with SHA-256
  **before** any annotation was written (`evaluation/m11d/provenance.json`'s
  own `sha256` field per posting).
- The completed 165-claim annotation file,
  `evaluation/m11d/holdout_annotations.json`, was itself hashed
  immediately upon completion, **before**
  `extract_competency_qualifications()` was ever run against it:
  `sha256(holdout_annotations.json) = 51ed1c8756c5fe1e88b277fea25d74a6018dede0fee4a1385e05ca09f37af3c6`.
- Annotation did not inspect, anticipate, or back-fill from any
  extractor output — each claim's `qualification_kind`/`necessity`/
  `logical_composition`/`github_observability` was decided from the
  sentence's own meaning alone, exactly as M11-B/M11-C's own prior
  corpora were authored.
- **The gold was not rewritten after evaluating the extractor.** One
  specific tension surfaced during review (§6's own discussion of
  `m11d-anduril-firmware-01-05`'s `or_any` vs. `single` annotation) is
  reported as a measured mismatch and a methodological note, not
  corrected retroactively — unlike M11-C's own pre-evaluation corpus
  fix (which was made BEFORE any strategy was run), this is a
  POST-evaluation finding and is therefore left exactly as originally
  annotated, per this milestone's own explicit instruction.
- Unresolved annotation disagreements/ambiguity were preserved
  explicitly rather than resolved for convenience — e.g.
  `m11d-anthropic-secengr-01-01` ("3+ years... with security experience
  a plus and/or 5+ years...") has a REQUIRED outer claim with an
  embedded PREFERRED sub-clause, annotated as REQUIRED/OR_ANY with a
  note rather than silently simplified.

---

## 3a. Publication-safety disposition

This repository is public. Neither a Greenhouse/Lever job-board posting
nor the employer that wrote it has confirmed republication rights for
its text, and public availability of a page does not itself grant
those rights. Two local artifacts fall on the unsafe side of that line
and are **not committed**:

- `evaluation/m11d/source/*.txt` — the 12 raw postings, retained
  verbatim locally only.
- `evaluation/m11d/holdout_annotations.json` — the full, hash-frozen
  annotation file; its 165 `text` fields collectively reproduce most of
  each posting's own Requirements/Preferred-Qualifications content,
  not a brief excerpt. Retained locally only, at the SAME frozen hash
  recorded in §3 above.

**What IS committed instead:**

- `evaluation/m11d/provenance.json` — pure factual metadata (employer,
  role title, source URL, domain, seniority, per-file SHA-256). No
  employer's own expression is reproduced here.
- `evaluation/m11d/holdout_annotations_metadata.json` — every one of
  the 165 claims, with every structural/analytical field intact
  (`qualification_kind`, `necessity`, `logical_composition`,
  `github_observability`, `new_vocabulary_gap`, domain/posting
  linkage, this project's own `notes`) and `text` set to `null`,
  replaced by `text_length_chars` + `text_sha256` of the original
  string. This is this project's own original analytical work product,
  not the employer's expression, and reproduces none of the latter.
- `scripts/evaluate_m11d_generalization_validation.py` — fingerprints
  (`text_length_chars`/`text_sha256`) rather than embeds verbatim text
  in its own `mismatches` output, so a future re-run against the local
  annotation file stays publication-safe automatically, without a
  manual redaction step.
- `evaluation/reports/m11d_generalization_validation_report.json` —
  the script's own output; contains zero verbatim posting text.
- This design document — quotes short (typically <20-word) fragments
  of posting text in §6's own root-cause analysis, for the same reason
  a book review may quote a sentence to support its argument (comment/
  criticism on a specific, narrow point) rather than to republish the
  work; every quoted fragment is far shorter than the claim-level
  excerpts the redacted artifacts above deliberately withhold.

**Disclosed reproducibility limitation:** a reader with only the
published artifacts can verify every AGGREGATE number in §4/§5/§7 of
this document (they are computed directly from `holdout_annotations_metadata.json`'s
own non-text fields, identical to the source data) and can verify,
via `text_sha256`, that any locally-held copy of
`holdout_annotations.json` is byte-identical to the one actually
evaluated — but cannot independently re-derive the ANNOTATIONS
themselves (i.e. cannot check "was this specific sentence correctly
labeled REQUIRED") without separately obtaining the same 12 postings
from their own original, public source URLs (listed in full in
`provenance.json`) and re-reading them. This is the direct and
intended consequence of not republishing the underlying text, not an
oversight.

---

## 4. Independent benchmark performance (the real module, holdout corpus)

`scripts/evaluate_m11d_generalization_validation.py` ran the REAL,
UNMODIFIED `extract_competency_qualifications()` against all 165
holdout claims. No algorithm change of any kind was made before or
during this run.

| Metric | Result |
|---|---|
| `TECHNICAL_COMPETENCY` recall | **3 / 59** |
| `TECHNICAL_COMPETENCY` precision | **3 / 6** |
| False positives from responsibility bullets | 0 |
| False positives from company-narrative sentences | 1 |
| False positives from other non-qualification / different-kind text | 2 |
| Necessity classification (among recognized claims) | 0 / 0 (none of the 3 recognized claims had a comparable non-null ground-truth/predicted necessity pair — see §6) |
| Logical grouping (among recognized claims) | 5 / 6 |
| Missing-contract declines | 0 (see §6 — the one authentic missing-contract SHAPE in this corpus was not reached, for a different, also-disclosed reason) |
| Vocabulary-coverage gap claims correctly declined as `no_competency_language` | 32 / 32 |
| Source-span exactness | 6 / 6 |
| Scoring safety: never `SUPPORTED` with empty evidence | **True** |
| Scoring safety: never falsely assessable without a concept mapping | **True** |

---

## 5. Comparison against M11-C development results

| Metric | M11-C development corpus (45 examples, single-session, synthetic) | M11-D independent holdout (165 claims, 12 authentic postings) |
|---|---|---|
| `TECHNICAL_COMPETENCY` recall | 26/28 (93%) | **3/59 (5%)** |
| `TECHNICAL_COMPETENCY` precision | 26/26 (100%) | 3/6 (50%) |
| False positives (any kind) | 0 | 3 |
| Necessity classification | 20/20 (100%, nulls excluded) | 0/0 (no comparable pairs reached) |
| Logical grouping | 27/28 (96%) | 5/6 (83%) |
| Source-span exactness | 28/28 (100%) | 6/6 (100%) |
| Scoring safety | Both safety invariants `True` | Both safety invariants `True` |

**The headline finding: recall collapses from 93% to 5% on independent,
authentic text, while precision also drops materially (100%→50%), and
the one property that held perfectly in BOTH settings is scoring
safety.** This is not a marginal generalization gap — it is a
near-total failure to recognize genuine technical-competency language
once it is phrased the way real employers actually phrase it, while
the extractor's own safety invariants (never fabricate, never
falsely-assessable) continue to hold exactly as designed. See §6 for
why, with exact evidence from this run, not speculation.

---

## 6. Detailed false-positive / false-negative analysis

### False negatives (56 of 59 genuine competency claims missed) — root cause confirmed directly, not inferred

Querying which of the 59 ground-truth `technical_competency` claims the
extractor actually recognized returns exactly three:

1. *"Deep understanding of **distributed systems** concepts such as
   sharding, replication..."* — matches because it contains the literal
   phrase `distributed systems`.
2. *"Strong **system design** skills and a track record..."* — matches
   because it contains the literal phrase `system design`.
3. *"Bare-metal or RTOS **firmware** development experience"* — matches
   because it contains the bare word `firmware`.

**Every one of the other 56 claims is conceptually within the 17-tag
vocabulary's own named domains (or a disclosed `new_vocabulary_gap`
outside them) but is phrased differently from the single canonical
trigger phrase each vocabulary pattern expects.** Concrete examples,
each independently verified against the actual regex:

- *"Understanding of robot interfaces across sensing, state
  estimation, actuation, and control"* — conceptually
  `robotics-systems-integration` (a `new_vocabulary_gap` tag), but even
  if that tag existed, no fixed phrase here would be guessable in
  advance.
- *"Familiarity with control tuning and performance profiling on
  physical robots"* — conceptually `control-systems` (an EXISTING M11-C
  tag!), but the vocabulary pattern requires the literal phrase
  `control systems theory` / `PID` / `state-space methods` — none of
  which appear; "control tuning" is a real, common synonym the pattern
  never anticipated.
- *"Working knowledge of service and edge networking (DNS, TLS, CDNs,
  load balancing)"* — conceptually `os-networking` (an EXISTING tag),
  missed because the pattern requires `operating systems internals` /
  `TCP/IP networking` / `process scheduling` / `networking fundamentals`
  / bare `operating systems` — "service and edge networking" matches
  none of them.

**This demonstrates the dominant failure mode is Category A
(competency-vocabulary coverage), and specifically its WORST form: not
merely missing DOMAINS, but missing PARAPHRASES even of domains the
vocabulary nominally covers.** The 17-tag vocabulary was effectively
tuned to near-verbatim match its own 45 single-session development
sentences; real employer phrasing varies far more than that.

### False positives (3 total) — each with a specific, confirmed mechanism

1. **`m11d-anduril-firmware-01-02`**, *"5+ years firmware/embedded
   software development experience"* (ground truth: bare `EXPERIENCE`,
   not a competency claim) — misclassified because the bare word
   `firmware` appears in it. The vocabulary has no way to tell "this
   sentence is fundamentally a years-of-experience claim that happens
   to use the word firmware" from "this sentence asserts the firmware/
   embedded-systems competency itself."
2. **`m11d-anduril-firmware-01-03`**, *"Strong C coding ability for
   embedded systems"* (ground truth: `SPECIFIC_TECHNOLOGY`, the C
   language) — misclassified because the literal phrase `embedded
   systems` appears as a qualifying context phrase, not the sentence's
   own main claim. **This is Category H/B: the extractor has zero
   coordination with the existing technology-mention detector**, so it
   cannot recognize "embedded systems" here is modifying a TECHNOLOGY
   claim rather than asserting a COMPETENCY claim — exactly the
   structural limitation M11-C's own Phase 1 (`decisions A/B/C kept
   separate`) anticipated in principle; this is the first CONCRETE,
   authentic instance of it actually occurring.
3. **`m11d-anduril-firmware-01-14`**, *"Anduril seeks a Senior
   Firmware Engineer for their Costa Mesa team."* (ground truth:
   `COMPANY_NARRATIVE`) — misclassified because the bare word
   `firmware` appears (inside the quoted job TITLE, "Firmware
   Engineer"), and this sentence escapes ALL THREE rejection filters:
   `contains_narrative_cue()` (tuned to M10E's "our team has
   built...", "you'll learn..." shapes — this sentence matches
   neither), the new `_BROADER_NARRATIVE_SUBJECT` pattern (tuned to
   "our team"/"we're a"/"the team" — "Anduril seeks..." matches none
   of these), and `_RESPONSIBILITY_LEAD` (requires a LEADING imperative
   verb — this sentence opens with the company's own name, not a verb).
   **A "`[Company] seeks a [Role] for their [Team]`" opening is an
   extremely common real "About the Role" sentence shape this
   milestone's synthetic development corpus never exercised at all.**

### The one authentic missing-contract SHAPE that did not trigger the decline — for a documented, distinct reason

`m11d-spacex-newgrad-01-04`, *"Experience with real-time embedded or
distributed computing systems"*, was independently annotated as a REAL
occurrence of M11-C's own disclosed `missing_contract` shape (an
`OR_ANY` of two EXISTING competency tags, `embedded-systems-design` OR
`distributed-systems`). Verified directly: neither tag's pattern
actually fires on this exact wording — `embedded-systems-design`
requires `embedded systems` as a contiguous phrase, but the real
sentence has an elliptical coordination, "**embedded** or distributed
computing **systems**" (= "embedded computing systems" OR "distributed
computing systems," with "computing systems" shared across both
branches) — neither canonical phrase appears contiguously. **This is a
SECOND, independent vocabulary-brittleness finding, distinct from
missing recall on an uncovered paraphrase**: here the SHAPE the
extractor was explicitly designed to handle safely (declining an
OR_ANY-of-tags case) was never reached, because elliptical/shared-noun
coordination — a common English construction — defeats the phrase
matcher before the logical-structure analysis ever runs.

### One self-identified annotation-methodology tension (reported, not corrected)

`m11d-anduril-firmware-01-05`, *"Bare-metal or RTOS firmware
development experience"*, was annotated `logical_composition: or_any`
(two alternative framings of one competency) but the extractor
produced `single` (one competency tag found, since only `firmware`
matched). Reviewing this AFTER the run surfaces a genuine ambiguity in
this milestone's OWN annotation convention (also present, less
visibly, in M11-C's own corpus): should "X or Y" naming two
DESCRIPTIONS of the same underlying competency area be `OR_ANY` or
`SINGLE`? M11-C's own corpus leaned `SINGLE` for "and"-joined
descriptive sub-terms (after its own mid-Phase-3 self-correction) but
this holdout corpus's one `or_any`-annotated analogous case was never
revisited the same way. **Left exactly as originally annotated** —
correcting it now, after seeing the extractor's own output, would
violate this milestone's explicit instruction not to rewrite gold
post-evaluation. Reported here as a measured mismatch AND a
methodological note for whoever authors the NEXT corpus.

---

## 7. Performance breakdown by domain and writing style

### By domain

| Domain | TP | FN | FP | Technical-competency claims |
|---|---|---|---|---|
| robotics_autonomy | 0 | 16 | 0 | 16 |
| cybersecurity | 0 | 6 | 0 | 6 |
| electrical_engineering | 0 | 6 | 0 | 6 |
| embedded_systems | 1 | 5 | 1 | 6 |
| infrastructure_cloud | 0 | 5 | 0 | 5 |
| software_engineering_general | 0 | 5 | 0 | 5 |
| systems_performance_engineering | 0 | 5 | 0 | 5 |
| ai_ml | 0 | 4 | 0 | 4 |
| backend_distributed_systems | 2 | 2 | 0 | 4 |
| data_engineering | 0 | 2 | 0 | 2 |

**Recall is not uniformly near-zero — it is ZERO in 8 of the 10
domains**, and the only two domains with ANY recall
(`backend_distributed_systems` 2/4, `embedded_systems` 1/6) succeeded
specifically because their postings happened to use the exact
canonical phrases (`distributed systems`, `system design`, `firmware`)
the vocabulary was built around. This is consistent with — and further
confirms — §6's finding that the failure is paraphrase coverage, not a
domain-specific weakness: `robotics_autonomy` (the domain with the
MOST claims, 16) scored zero recall despite the vocabulary nominally
including `embedded-systems-design` and `control-systems`, which
appear conceptually relevant to several of its missed claims.

### By writing style — a disclosed measurement gap, not a finding

This corpus does NOT cleanly separate "writing style" as its own axis,
for the reason stated in §2: `WebFetch`'s own extraction step imposes
a fairly uniform Markdown-heading structure on every posting, which
flattens the real page's own original formatting (bulleted vs. prose,
sectioned vs. not) before this milestone ever sees it. One partial
exception survives: `evaluation/m11d/source/voyager_senior_electrical_hardware_engineer.txt`'s
"Minimum Qualifications"/"Preferred Qualifications" sections are
PROSE paragraphs, not bullets, in the saved source — and that
posting's own recall was still zero (0/6), suggesting prose-vs-bullet
formatting is not, by itself, the dominant factor (vocabulary
paraphrase coverage already explains the miss) — but this is a single
data point, not a controlled comparison, and is reported as exactly
that.

---

## 8. Major architectural limitations (not fixed in this milestone)

Mapped directly to the eight candidate root causes named in the
milestone's own Phase 4 instruction, each confirmed or ruled out by
the evidence in §6 above — not asserted without it:

- **(A) Competency vocabulary coverage — CONFIRMED as the dominant
  failure mode**, and specifically in its most severe form: paraphrase
  intolerance even within covered domains, not merely absent domains.
  56 of 59 missed claims are explained by this alone.
- **(B) Qualification-vs-responsibility classification — CONFIRMED,
  one concrete instance**: the "`[Company] seeks a [Role] for their
  [Team]`" company-narrative opening defeats every existing rejection
  heuristic.
- **(C) Section-level necessity inference — NOT DIRECTLY TESTABLE by
  this run**: `extract_competency_qualifications()` never threads
  section context through at all (confirmed in M11-C's own design
  doc as a disclosed limitation); this holdout corpus's necessity
  comparison produced 0 comparable pairs because so few claims were
  recognized at all for necessity to be checked against. This root
  cause remains measured as "present and unaddressed," not newly
  discovered.
- **(D) Compound competency representation — CONFIRMED, one concrete
  instance**: the elliptical-coordination case (§6, SpaceX new-grad)
  shows compound/shared-noun phrasing defeats even the ALREADY-covered
  tags before the missing-contract logic ever has a chance to run.
- **(E) Source segmentation — NOT EXERCISED by this run**: every
  holdout claim was fed to the extractor as an already-isolated
  sentence (mirroring M11-C's own methodology); this milestone did not
  test the EXISTING `segment_description()` against these full raw
  postings, so segmentation-induced errors are explicitly out of
  scope here and not claimed to be absent.
- **(F) Logical grouping — a SECONDARY issue (5/6 among the few
  recognized claims), not the primary driver of the recall collapse.**
- **(G) Observability policy — CONFIRMED SAFE, no issue found**: both
  Phase 5 safety invariants held perfectly (`True`/`True`) across every
  recognized claim.
- **(H) Other structural limitations — CONFIRMED, one concrete
  instance**: zero coordination between the competency extractor and
  the existing technology-mention detector (§6, "C coding... for
  embedded systems") lets a technology-context phrase masquerade as a
  competency claim.

**No claim of universal generalization is made anywhere in this
document.** 165 claims from 12 postings, acquired in one session, is
not a statistically representative sample of real-world job postings
in general, and this document does not treat it as one — it is a
single, honest measurement, reported with its own exact scope.

---

## 9. Production-readiness verdict

**Verdict: Option 1 — continued offline development only.**

Measured against the milestone's own four options:

1. **Continued offline development only** — supported directly by the
   evidence: 5% recall on independent text is not a basis for ANY
   production-facing use, shadow or otherwise.
2. **Shadow comparison alongside the live parser** — NOT supported yet.
   A shadow comparison's entire value is measuring a candidate's
   real-world behavior difference from production; at 5% recall, the
   candidate would show almost no behavior to compare, and the
   comparison's own signal-to-noise would be dominated by near-total
   misses rather than informative near-misses.
3. **A narrowly scoped non-scoreable qualification enhancement** — NOT
   supported yet, for the same reason: at 5% recall there is
   essentially nothing to enhance with.
4. **Full production integration** — explicitly and obviously not
   supported; not seriously considered.

**What IS confirmed safe, and should be weighed separately from the
readiness verdict above:** the Phase 5 scoring-safety invariants held
perfectly on independent data, exactly as they did on development
data. Whatever this extractor's recall/precision limitations, it has
not been shown to fabricate, to falsely score, or to corrupt the
EXISTING, unmodified live-parser behavior in any way — the failure
mode measured here is "does too little," never "does something unsafe."

---

## 10. Recommended next implementation milestone

**Not a fix to this extractor directly.** Per this milestone's own
explicit restriction ("Do not fix errors in this milestone"), and
given the measured root cause (§8, dominantly Category A — vocabulary
paraphrase intolerance), the smallest NEXT milestone this evidence
actually supports is:

> **An evaluation-first investigation into paraphrase-tolerant
> competency-phrase matching** — NOT a larger fixed vocabulary (more
> phrases would still be brittle to the NEXT paraphrase), but a
> design review of whether a bounded, deterministic technique exists
> that tolerates real synonymy ("control tuning" ≈ "control systems",
> "service and edge networking" ≈ "operating systems internals") while
> still respecting this project's own "no LLM extraction" restriction
> — e.g. a curated synonym/stemming table per competency tag (an
> explicit, auditable expansion of today's exact-phrase table, still
> fully deterministic), measured against BOTH this holdout corpus
> (reused, since it is now itself prior development material once
> inspected) AND a NEW, second independent holdout, before any
> conclusion is drawn.

Explicitly NOT recommended as the next step: wiring anything into the
live parser, a shadow comparison, or acquiring a larger postings corpus
at the same acquisition difficulty — the dominant, confirmed problem
(§6/§8) is phrase-matching brittleness, not corpus size, and a bigger
corpus of postings using the SAME kind of real phrasing would very
likely reproduce the same ~5% recall, not usefully extend the finding.

---

**STOP — evaluation execution and generalization measurement only. No
algorithm was modified (`git diff --name-only -- src/gitscore` empty).
No commit was made. Returning results for review before any further
authorization.**
