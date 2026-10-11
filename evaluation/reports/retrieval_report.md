# Repository-Retrieval Evaluation Report (Milestone 8D.2)

Corpus version: `8d2:v1`

Relevance ground truth (`genuinely_relevant`) is reported SEPARATELY
from the observed outcome -- a genuinely relevant repository the fixed
budget still excludes is a `RETRIEVAL_MISSED_RELEVANT` miss, never a
negative-control success. See the per-case outcome column below.

Cases evaluated: 7

**Genuinely relevant repositories** (4 cases):
- Recovered by job-aware retrieval: 2
- Already covered by generic ranking: 0
- **Missed despite job-aware retrieval (known limitation): 2**

**Negative controls (genuinely irrelevant repositories)** (3 cases):
- Correctly excluded: 3
- False-positive additions: 0

Regression pin (`expected_analyzed` vs. measured outcome -- NOT a relevance judgment): 7/7 match.

## Per-case verdicts

| candidate | job_id | repo | genuinely_relevant | expected_analyzed | job_aware_analyzed | outcome |
|---|---|---|---|---|---|---|
| jango1324 | ml_engineering_01 | Pneumonia-Detection-Ai | True | True | True | RETRIEVAL_RECOVERED |
| jango1324 | general_swe_01 | Pneumonia-Detection-Ai | True | True | True | RETRIEVAL_RECOVERED |
| karpathy | computer_vision_01 | nn-zero-to-hero | True | False | False | RETRIEVAL_MISSED_RELEVANT |
| karpathy | frontend_01 | nn-zero-to-hero | False | False | False | RETRIEVAL_CORRECTLY_EXCLUDED |
| sindresorhus | fullstack_01 | execa | True | False | False | RETRIEVAL_MISSED_RELEVANT |
| sindresorhus | robotics_controls_01 | execa | False | False | False | RETRIEVAL_CORRECTLY_EXCLUDED |
| sindresorhus | frontend_01 | awesome | False | False | False | RETRIEVAL_CORRECTLY_EXCLUDED |

## Per candidate x job pair: full job-aware addition set

| candidate | job_id | generic_analyzed_count | job_aware_analyzed_count | job_aware_additions |
|---|---|---|---|---|
| jango1324 | ml_engineering_01 | 15 | 16 | Pneumonia-Detection-Ai |
| jango1324 | general_swe_01 | 15 | 16 | Pneumonia-Detection-Ai |
| karpathy | computer_vision_01 | 15 | 22 | arxiv-sanity-lite, arxiv-sanity-preserver, cryptos, examples, neuraltalk2, pytorch-made, pytorch-normalizing-flows |
| karpathy | frontend_01 | 15 | 22 | forestjs, lifejs, notpygamejs, recurrentjs, reinforcejs, svmjs, tsnejs |
| sindresorhus | fullstack_01 | 15 | 25 | acosh, class-names, gulp-react, ink-box, is-docker, is-inside-container, react-dom-pragma, react-extras, sublime-jsrun, unstated-debug |
| sindresorhus | robotics_controls_01 | 15 | 22 | Dagbladet-bildeserier.bundle, editorconfig-sublime, fullname-native, pwuid, sublime-jsrun, weechat-notification-center, whisper.cpp |
| sindresorhus | frontend_01 | 15 | 25 | add-module-exports-webpack-plugin, atom-autoprefixer, atom-perfectionist, broccoli-autoprefixer, broccoli-cssnano, broccoli-csso, broccoli-strip-css-comments, broccoli-stylus, broccoli-uncss, class-names |

## Case rationale

- [RETRIEVAL_RECOVERED] `jango1324` x `ml_engineering_01` / `Pneumonia-Detection-Ai`: 8C's own documented genuine ranking miss (retrieval_miss_relevant=true, gold/candidates/jango1324.json). This repo's GitHub-reported primary_language is Python; ml_engineering_01 requires language.python (REQUIRED) -- recoverable via the cheap structured language-field signal alone, no description/topics needed. Genuinely relevant AND successfully recovered by job-aware retrieval.
- [RETRIEVAL_RECOVERED] `jango1324` x `general_swe_01` / `Pneumonia-Detection-Ai`: general_swe_01's sole technical requirement is an alternative group ['language.cpp','language.java','language.python'] (Proficiency in at least one of Python, Java, or C++) -- demonstrates ANY-side alternative-group relevance end-to-end (Part 4), not just in isolated unit tests. Genuinely relevant AND recovered via the same language.python match as the ml_engineering_01 case.
- [RETRIEVAL_MISSED_RELEVANT] `karpathy` x `computer_vision_01` / `nn-zero-to-hero`: GENUINELY RELEVANT -- this is a real ML-education repository and this repo's primary_language is 'Jupyter Notebook', which DOES earn real, correct relevance (score 0.5, the PREFERRED weight for computer_vision_01's language.jupyter_notebook term -- confirmed via score_repository_relevance() directly). It is still NOT ANALYZED (expected_analyzed=false) because karpathy's account has 39 total repositories scoring >0 for this job (mostly 1.0-2.0, matching the REQUIRED language.python/ml.framework.pytorch/platform.cuda terms), and this repo ranks 38th of 39 by score -- far outside the default relevance_top_k=10. This MUST be reported as a missed relevant repository (classify_retrieval_outcome -> RETRIEVAL_MISSED_RELEVANT), never as a correctly-excluded negative control -- the relevance signal correctly identifies it as relevant; the fixed top-10 budget still excludes it because so many OTHER repos score higher. Increasing relevance_top_k specifically to recover this one case would be tuning the budget to this evaluation rather than choosing it on its own merits (Milestone brief: 'conservative defaults based on the existing top_n=15 behavior') -- documented as a known limitation instead (docs/evaluation/MILESTONE_8D2_JOB_AWARE_RETRIEVAL.md).
- [RETRIEVAL_CORRECTLY_EXCLUDED] `karpathy` x `frontend_01` / `nn-zero-to-hero`: GENUINE NEGATIVE CONTROL for the same repository as the case above: frontend_01's required concepts are language.javascript/language.typescript/framework.react/language.css -- none of which this Jupyter-Notebook ML repo's language field or free text plausibly satisfies. Demonstrates recovery is JOB-SPECIFIC, never a blanket 'always retrieve this repo' rule (Milestone brief's explicit warning), and that the SAME repository can be genuinely relevant to one job (the case above) and genuinely irrelevant to another.
- [RETRIEVAL_MISSED_RELEVANT] `sindresorhus` x `fullstack_01` / `execa`: GENUINELY RELEVANT -- a well-engineered, widely-used JavaScript process-execution library, and this repo's primary_language is JavaScript, which DOES earn real, correct relevance (score 1.0, matching fullstack_01's REQUIRED language.javascript term -- confirmed via score_repository_relevance() directly). It is still NOT ANALYZED (expected_analyzed=false) because sindresorhus has 1,142 repositories and 992 of them score >0 for this job (the account is overwhelmingly JavaScript/TypeScript, so a single language-field match is a very weak discriminator here) -- execa ties at score 1.0 with hundreds of others and ranks 231st of 992 by the deterministic name-ascending tie-break, far outside relevance_top_k=10. This MUST be reported as a missed relevant repository (RETRIEVAL_MISSED_RELEVANT), never as a correctly-excluded negative control. This is the SAME underlying problem 8C's own evaluation named for this exact account/repository (an extremely prolific account defeats any small fixed cutoff) -- Stage-2 retrieval narrows but does not eliminate it for a single-weak-signal match on a 1000+-repository account; a stronger/more specific job requirement (matching execa's own topics -- 'exec', 'spawn', 'child-process' -- none of which any job in this corpus names) or a larger budget would be needed, and is documented as a known limitation rather than forced via a larger default (docs/evaluation/MILESTONE_8D2_JOB_AWARE_RETRIEVAL.md).
- [RETRIEVAL_CORRECTLY_EXCLUDED] `sindresorhus` x `robotics_controls_01` / `execa`: GENUINE NEGATIVE CONTROL for the same repository: robotics_controls_01 requires robotics.ros2/language.python/language.cpp -- none of which a JavaScript process-execution library's language field or free text (topics: binary, child-process, exec, nodejs, shell, spawn...) plausibly satisfies.
- [RETRIEVAL_CORRECTLY_EXCLUDED] `sindresorhus` x `frontend_01` / `awesome`: GENUINE NEGATIVE CONTROL against a hugely-starred but genuinely low-substance repository (a curated markdown link-list, no real 'language', gold/candidates/sindresorhus.json's own documented DELIBERATE deprioritization -- not a retrieval miss). Must not be pulled in by job relevance either: its description/topics (awesome, awesome-list, lists, resources, unicorns) share no concept with frontend_01's JS/TS/React/CSS requirements. Confirms job-aware retrieval does not simply chase star count or any common word.
