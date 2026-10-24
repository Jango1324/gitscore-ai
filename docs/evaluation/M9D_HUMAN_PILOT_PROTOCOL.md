# Milestone 9D — Human-Review Pilot Protocol

**Status: protocol only — not yet run.** This document is a ready-to-use
study design for the project owner to run with 3-5 volunteer
participants. No participants have been recruited, contacted, or
simulated, and no responses or usability metrics exist yet anywhere in
this repository. Every number in the "example materials" section below
comes from `evaluation/reports/m9d_pilot_cohort_report.json`
(`scripts/evaluate_m9d_pilot_cohort.py`, Milestone 9D's own offline
pilot cohort — see `MILESTONE_9D_PRODUCT_VALIDATION.md` §2/§4) and is
real GitScore output against public, offline GitHub fixtures and
synthetic job postings — never a live or fabricated result.

---

## A. Standardized introduction (read aloud or handed to each participant)

> GitScore AI analyzes a GitHub profile against a job description and
> shows what *GitHub evidence* supports, doesn't show, or simply can't
> speak to. It produces a number called **"GitHub Evidence Alignment"**.
>
> Three things to know before you start:
>
> 1. This number is **not** a hiring recommendation, a measure of overall
>    engineering skill, or a prediction that someone will get the job.
>    It measures what fraction of the job's *GitHub-observable*
>    requirements have evidence in the candidate's analyzed repositories.
> 2. If a requirement shows as "not observed," that means GitScore found
>    no evidence for it in the repositories it looked at — **it does
>    not mean the candidate lacks that skill.** They may have it and
>    simply not have demonstrated it on GitHub.
> 3. Some requirements (a college degree, years of professional
>    experience, soft skills) are not things GitHub can speak to at
>    all. GitScore labels these separately and never counts them as a
>    failure.
>
> You'll be shown one or two real GitScore results (built from public
> GitHub profiles and realistic, hand-written sample job postings — not
> live job listings) and asked to complete five short tasks. There are
> no wrong answers — we're testing whether the product communicates
> clearly, not testing you.

---

## B. Five tasks

Each task should take 3-7 minutes. Give the participant the relevant
result screen (or printed/screenshotted result) and ask them to think
aloud while completing it.

### Task 1 — Interpret a high alignment score

**Material:** the `karpathy × computer_vision_01` result
(`alignment_score = 100`, `required = 3/3`, `preferred = 1/1`).

**Prompt:** "This candidate's GitHub Evidence Alignment for this job is
100. What does that number tell you, and what doesn't it tell you? Would
you feel confident recommending this candidate for the role based on
this number alone?"

**What we're checking:** does the participant correctly avoid treating
100 as "will definitely get the job" / "is the best candidate" /
"has no weaknesses"? Do they notice the required/preferred breakdown
underneath the headline? (Internal note for the observer, not shown to
the participant: this specific pairing's 100 is partly inflated by a
silently-dropped OpenCV requirement — see
`MILESTONE_9D_PRODUCT_VALIDATION.md` §4.2/§6.2 — so a participant who
asks "is this really measuring everything the posting asked for?" is
giving exactly the kind of skeptical reaction this task is designed to
surface, not a wrong answer.)

### Task 2 — Explain a `NOT_OBSERVED` requirement

**Material:** the `torvalds × data_science_01` result — specifically the
"Not observed in analyzed GitHub evidence" section, which includes
`data.library.pandas`, `unresolved:numpy`, `language.sql`, and
`language.jupyter_notebook`.

**Prompt:** "This candidate's result shows four requirements as 'not
observed.' In your own words, what does 'not observed' mean here? Does
it mean the candidate can't do these things?"

**What we're checking:** does the participant correctly distinguish
"no evidence found" from "proven absent"?

(Internal note for the observer, not shown to the participant: this
result's "Supported" section one scroll up also shows "Experience with
Python, pandas, and numpy" — the identical sentence behind two of this
task's four "not observed" rows. See
`MILESTONE_9D_PRODUCT_VALIDATION.md` §6.5. Do not point this out
unprompted, but if a participant notices the repeated text and asks
about it, that reaction is itself a valid, recordable data point for
the observation sheet, not a distraction from the task.)

### Task 3 — Explain a `NOT_ASSESSABLE` requirement

**Material:** the `Jango1324 × general_swe_01` result — specifically the
"Not assessable from GitHub" section's two subsections: "Genuinely
non-technical requirements" (a Bachelor's degree) and "Could not be
confidently interpreted" (the computer-science-fundamentals and
distributed-systems claims).

**Prompt:** "This section has two sub-groups. What's the difference
between them? Why do you think a degree requirement and a
'distributed systems' requirement ended up in different groups, even
though both say 'not assessable'?"

**What we're checking:** does the participant notice there are two
distinct reasons bundled under one outer heading, and can they
articulate the difference (a fact about the job vs. a fact about
GitScore's own parsing) without being told?

### Task 4 — Identify parser uncertainty

**Material:** the `torvalds × sre_platform_01` result — the headline's
"1 requirement could not be confidently interpreted" caveat, and
separately, the "Statements GitScore could not parse as requirements"
section listing "Experience with monitoring and observability tooling"
and "On-call experience and incident response."

**Prompt:** "The top of the page mentions 1 requirement GitScore
couldn't confidently interpret. Scroll through the rest of the page —
does that number match everything you can find that GitScore seems
unsure about?"

**What we're checking:** this task directly probes
`MILESTONE_9D_PRODUCT_VALIDATION.md` §6.1's finding — the headline count
structurally excludes the separate "statements GitScore could not parse"
section. **Do not correct the participant if they miss the discrepancy**
— that itself is the data point (a participant who confidently answers
"yes, 1 matches" without noticing the other section is direct evidence
for how easily the headline number is taken as the complete picture).

### Task 5 — Verify whether repository evidence supports a claim

**Material:** the `sindresorhus × devops_cloud_01` result — the
"Supported by GitHub evidence" section's "Experience with AWS or Azure"
item, whose evidence is a README mention in the `file-type` repository
("...rmine the file type of a file stored on [Ama...]").

**Prompt:** "This requirement is marked 'supported.' Look at the
evidence shown for it. Based on what's shown, how confident are you that
this candidate has real AWS experience? What would you want to see
instead?"

**What we're checking:** this directly probes
`MILESTONE_9D_PRODUCT_VALIDATION.md` §6.3's finding. A participant who
reads the raw evidence snippet and expresses skepticism ("that's just a
mention, not proof they used AWS") demonstrates the evidence *is*
traceable enough to catch a weak citation when actually read — valuable
signal either way about whether real users read evidence detail at all
versus only the headline status.

---

## C. Feedback questionnaire

Ask after all five tasks, either verbally or via a short written form.
Use a 1-5 scale ("strongly disagree" to "strongly agree") for the rated
items, plus the open-ended questions at the end.

**Understanding**
1. I understood what "GitHub Evidence Alignment" measures.
2. I understood the difference between "not observed" and "not
   assessable."
3. I understood why some requirements had no status at all (the
   "statements GitScore could not parse" section).

**Perceived clarity**
4. The result page was easy to read and navigate.
5. The language used avoided making me think this was a hiring
   recommendation.

**Evidence traceability**
6. When a requirement was marked "supported," I could tell what
   specific evidence justified that.
7. I felt I could verify the evidence myself if I wanted to (even though
   it required manually looking up the repository, rather than clicking
   a link).

**Trust calibration**
8. After seeing the evidence behind a "supported" requirement, my
   confidence in that specific verdict went up, down, or stayed the
   same? (open-ended, not a 1-5 scale)
9. Did any score or section make you more confident in the candidate
   than the underlying evidence actually justified? If so, which one?

**Usability**
10. I found it easy to locate the specific section I was asked about in
    each task.
11. The page's structure (order of sections) made sense to me.

**Open-ended**
12. What was the single most confusing part of this experience?
13. What, if anything, would make you trust this tool's output more?
14. Is there anything you expected to see that wasn't there?

---

## D. Structured observation sheet

One copy per participant, filled in by the observer during the session
(not shown to the participant).

| Task | Time to complete | Did they scroll past the headline before answering? | Correct interpretation (observer judgment) | Notable quote | Confusion points observed |
|---|---|---|---|---|---|
| 1 — High score | | | | | |
| 2 — NOT_OBSERVED | | | | | |
| 3 — NOT_ASSESSABLE | | | | | |
| 4 — Parser uncertainty | | | | | |
| 5 — Evidence verification | | | | | |

Additional fields to record per participant:
- Role/background (student / developer / hiring manager/recruiter / other)
- Prior familiarity with GitHub profile-analysis tools (none / some / extensive)
- Total session duration
- Any moment the participant expressed surprise, confusion, or distrust
  unprompted (verbatim if possible)
- Any moment the participant over-trusted a number (e.g. treated 100 as
  "hire this person") — flag explicitly, this is the specific failure
  mode §6.3 of the main report is most concerned about

---

## E. Success criteria (defined before running the study)

Define these thresholds now, before any session, so results are not
rationalized after the fact. Suggested starting thresholds (the project
owner should adjust before running, not after seeing results):

| Criterion | Threshold | Rationale |
|---|---|---|
| Task 2/3 correct interpretation | ≥ 4 of 5 participants correctly distinguish "not observed" from "proven absent," and correctly distinguish the two `not_assessable` subsections | These are the product's core trust-calibration claims; if most participants get these wrong, the copy needs rework before anything else matters |
| Task 1/5 over-trust check | 0 of 5 participants treat a single number (the 100, or the "supported" AWS claim) as proof of hiring suitability or genuine proficiency without any hedge | Directly tests whether the careful copy throughout the product actually prevents the over-trust failure mode §6.3/§6.4 of the main report identifies as the highest-stakes risk |
| Task 4 headline-completeness check | If ≥ 3 of 5 participants fail to notice the headline caveat undercounts the full unparsed-claims list, treat `MILESTONE_9D_PRODUCT_VALIDATION.md` risk #1 as validated by real users, not just by code reading, and prioritize it accordingly | Converts a code-level finding into a user-confirmed one |
| Questionnaire Q5 (hiring-recommendation framing) average | ≥ 4/5 average | A score below this would indicate the product's careful "alignment, not hiring probability" framing is not landing even with deliberately careful copy |
| Questionnaire Q7 (traceability without links) average | No fixed threshold — record the distribution; use it to decide whether risk #4 (clickable evidence links) should be re-prioritized above risk #2/#3 | This criterion is exploratory, not pass/fail |

If a criterion is missed, the recommended response is a scoped product
change (see `MILESTONE_9D_PRODUCT_VALIDATION.md` §9's prioritized list),
not a larger redesign — consistent with this project's own engineering
principle of preferring small, understandable fixes.

---

## Running the study

1. Recruit 3-5 participants matching the suggested mix (engineering
   students, software developers, and — if available — a technical
   hiring manager or recruiter).
2. For each session: read §A aloud, run Tasks 1-5 in order using the
   materials specified, fill in §D live, administer §C immediately
   afterward.
3. Do not show participants this protocol document, the main
   `MILESTONE_9D_PRODUCT_VALIDATION.md` report, or any "expected answer"
   before or during their session.
4. After all sessions, compare results against §E's pre-registered
   criteria and write up findings as a new, dated entry — do not edit
   this protocol document's criteria retroactively to match whatever
   result came in.
