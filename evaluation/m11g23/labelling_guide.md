# M11-G23 labelling guide: candidate-profile heading controls

This guide defines what a **correct** job-description parser should output for each control. It is written
before any G23 candidate policy exists and is shared, unchanged, by the DEV author and the EVAL author. Labels
describe the right answer, never what any parser version currently does. Do not run the job parser, the
assessment pipeline or any evaluation script while labelling.

All text must be **synthetic**: invented wording, no real posting text, no real employer, product or person
names, no URLs. Use placeholder employer names such as "Acme", "Northwind" or "the company" if needed.

## File schema

```json
{
  "schema_version": 1,
  "milestone": "M11-G23",
  "split": "dev | eval",
  "provenance": "...",
  "authorship_disclosure": "...",
  "label_timing": "...",
  "controls": [
    {
      "id": "m11g23-<split>-NNN",
      "family": "<one letter A-T, see below>",
      "pair": null,
      "text": "<the full synthetic job-description text, newlines as \\n>",
      "units": [
        {
          "span": "<exact, UNIQUE substring of text: one sentence or one list item, without its bullet marker>",
          "kind": "qualification | personality | responsibility | company | product | benefits | process | tech_discussion | learning | team_practice | stack | negation",
          "qual": true,
          "nec": "required | preferred | unknown | null",
          "tech": ["<production concept ids>"],
          "nt": ["<acceptable non-technical row categories>"],
          "section": "required | preferred | responsibility | company | benefits | process | learning | stack | none",
          "ambiguous": false,
          "note": "<one short reason>"
        }
      ]
    }
  ]
}
```

Every sentence or list item in `text` that is not a heading line gets exactly one unit. Heading lines
themselves are never units. `pair` may name the id of a near-neighbour control, or be null.

## Field rules

**`span`**: one sentence or one list item, copied exactly (same case, punctuation and inner whitespace) and
appearing exactly once in `text`. Exclude the bullet marker (`- `, `* `, `• `, `1. `). If a sentence would
repeat elsewhere, reword one of them.

**`qual`**: is this unit a CANDIDATE QUALIFICATION, something the applicant is expected (or preferred) to
have: a skill, experience, knowledge, degree, certification, authorisation or ability?

- A unit that mixes a duty with an explicit qualification clause is a qualification.
- **Personality** (`kind: personality`, `qual: false`): temperament, values, enthusiasm or attitude with no
  skill, experience, knowledge or credential ("You are curious and kind.", "You love a good puzzle.",
  "You thrive in a fast-paced environment."). Soft skills phrased as an ability or skill ("Strong written
  communication skills.", "Ability to mentor junior engineers.") ARE qualifications with no technology.
- Negated requirements ("No prior Kotlin experience is required."), historical statements ("We used Perl
  until 2019."), future learning ("You will learn Terraform on the job.") and employer statements ("Our
  team uses Go.") are NOT qualifications.
- Duties ("You will build APIs in Go.", "Design data pipelines.") are NOT qualifications, even when they
  name a technology and even when they appear under a candidate-profile heading.
- Explicitly optional qualifications ("Kotlin experience is a plus but not required.") ARE qualifications,
  with `nec: preferred`.

**`nec`** (qualifications only; `null` when `qual` is false):

1. An explicit marker in the unit wins: "required", "must", "essential", "mandatory" -> `required`;
   "preferred", "a plus", "bonus", "ideally", "would be great", "nice to have", "helpful", "beneficial",
   "an advantage", "appreciated", "optional" -> `preferred`.
2. A negated required marker with an optional or appreciative tail ("not required, but a plus") ->
   `preferred`.
3. Otherwise the governing heading's meaning decides:
   - requirements / qualifications / must-have headings -> `required`;
   - **candidate-profile headings** that describe the person the employer seeks ("About you", "Who you are",
     "What you bring", "What we're looking for", "The ideal candidate", "Your profile", "You might be a fit
     if", "What makes you successful", "You'll thrive here if") -> `required`;
   - headings that explicitly signal something extra or optional ("Nice to have", "Bonus points", "Even
     better if", "What would make you stand out", "It would be great if") -> `preferred`.
4. An unsectioned candidate-attribute sentence ("You have...", "You should have...", "Candidates
   must...") -> `required`.
5. `unknown` only when none of the above decides it.

**`tech`**: technologies GENUINELY named in the unit, as production concept ids. Use a registered id when
the technology is registered (the 39 ids are listed below; their aliases are in
`src/gitscore/concepts/registry.py`). Otherwise use `unresolved:<slug>`, where the slug is exactly what the
production function `gitscore.concepts.registry.unresolved_concept_id("<term>")` returns for the term as
written. Calling that one function is allowed. List technologies for non-qualification units too, since they
are used to detect false admissions. An ordinary English word that only looks like a technology ("react
quickly", "express interest", "a swift learner") is not a technology. A generic category word ("databases",
"cloud", "version control", "machine learning") is not a technology; leave it out.

Registered ids: cloud.aws, data.library.pandas, database.postgresql, database.redis,
embedded.rtos.freertos, framework.express, framework.fastapi, framework.flask, framework.nestjs,
framework.nextjs, framework.react, framework.react_native, hdl.verilog, infra.docker, infra.kubernetes,
language.c, language.cpp, language.csharp, language.css, language.go, language.html, language.java,
language.javascript, language.jupyter_notebook, language.kotlin, language.php, language.python,
language.ruby, language.rust, language.shell, language.sql, language.swift, language.typescript,
ml.framework.pytorch, ml.framework.tensorflow, orm.prisma, platform.cuda, robotics.ros2, toolchain.llvm.

**`nt`**: acceptable non-technical row categories for a qualification unit, any of `education`,
`experience`, `legal`, `leadership`, `soft_skill`. Empty for non-qualifications.

**`section`**: the TRUE governing context of the unit:
- `required`: requirements, qualifications or must-have headings, **and candidate-profile headings**;
- `preferred`: nice-to-have or optional headings;
- `responsibility`, `company` (about us / employer description), `benefits`, `process` (hiring process),
  `learning`, `stack` (a "Tech stack" description of the employer's tools);
- `none`: no heading governs the unit.

A sub-heading nested under a candidate-profile heading ("Technical skills", "Tools") keeps the
candidate-profile meaning. A later heading of a different kind ends it.

**`ambiguous`**: true only for genuinely ambiguous qualification language, where reasonable readers would
disagree about whether the unit is a qualification. Ambiguous units are excluded from precision and recall
denominators and reported separately. Use it sparingly.

## Families (each control has exactly one primary family)

- **A**: genuine technical qualifications beneath candidate-profile headings.
- **B**: genuine qualifications beneath conventional Requirements / Qualifications headings.
- **C**: responsibilities beneath "What you'll do" (or similar) headings.
- **D**: employer descriptions beneath "About us" (or similar).
- **E**: benefits beneath "What we offer" (or similar).
- **F**: candidate-profile sections mixing personality statements and technical qualifications.
- **G**: REQUIRED versus PREFERRED qualifications (both in one posting).
- **H**: explicitly optional qualifications.
- **I**: negated, historical and future-learning statements (including under candidate-profile headings).
- **J**: nested headings and sub-section inheritance.
- **K**: multiple qualification sections in one posting.
- **L**: headings with apostrophes, curly punctuation (’ “ ” –) and headings broken across two lines.
- **M**: long or visually ambiguous headings.
- **N**: bullet lists and free-form prose under candidate-profile headings.
- **O**: technical concepts inside duties that must not become qualifications.
- **P**: qualifications phrased with a candidate subject ("You have...", "You're familiar with...").
- **Q**: compound AND/OR requirements ("Python or Go", "Docker and Kubernetes").
- **R**: alias equivalence: alternate spellings of one registered technology ("Golang", "Postgres",
  "k8s", "JS", "TS").
- **S**: qualifications with no GitHub-observable evidence pathway (degrees, clearances, spoken languages,
  certifications, years of experience with no technology).
- **T**: postings that mention READMEs, repositories or GitHub (the job-side admission decision must not
  depend on any candidate's repositories).

## Heading variety

Use varied heading styles across controls: with and without a colon, Markdown (`## About you`,
`**What you bring**`), ALL CAPS, sentence case and title case, straight and curly apostrophes. Include
headings of all kinds (not only candidate-profile ones) so that non-qualification content is also tested.
