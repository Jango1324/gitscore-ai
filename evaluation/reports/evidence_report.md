# Candidate Evidence Evaluation Report

Corpus version: `8c:v1`
Candidates evaluated: 4
Ranking checks: 10  |  Prediction errors: 0  |  Repository ranking misses (genuine, relevant repo excluded): 3
Concept checks: 9  |  Found: 9  |  Missing: 0 (BUG=0, KNOWN_SCOPE_LIMITATION=0)
False positives: 1
Total extractor failures across all candidates: 0

## Per-candidate repository coverage

| username | discovered | analyzed | complete |
|---|---|---|---|
| Jango1324 | 20 | 15 | False |
| karpathy | 63 | 15 | False |
| sindresorhus | 1142 | 15 | False |
| torvalds | 12 | 12 | True |

## Ranking verdicts

| username | repo | predicted | actual | RETRIEVAL_MISS? | notes |
|---|---|---|---|---|---|
| Jango1324 | JPod-ESP32 | analyzed | analyzed | no | C++-dominant (93.8% of language bytes per fixture), small ESP32 firmware project |
| Jango1324 | Pneumonia-Detection-Ai | not_analyzed | not_analyzed | YES | Chosen specifically because this exact repo name was used as an ILLUSTRATIVE exa |
| karpathy | micrograd | analyzed | analyzed | no | Jupyter-Notebook-dominant (90.3% of language bytes), README explicitly describes |
| karpathy | llm.c | analyzed | analyzed | no | Cuda-dominant per GitHub language stats (59.4%), with real C/Python also present |
| karpathy | nn-zero-to-hero | not_analyzed | not_analyzed | YES | 24,636-star Jupyter-Notebook ML teaching repository ('Neural Networks: Zero to H |
| sindresorhus | got | analyzed | analyzed | no | TypeScript-only per language stats, with a package.json present. |
| sindresorhus | Gifski | analyzed | analyzed | no | Swift-dominant (85.5% of language bytes). Chosen specifically because Swift is N |
| sindresorhus | awesome | not_analyzed | not_analyzed | no | The single most-starred repository on GitHub (514k+ stars) but a pure curated ma |
| sindresorhus | execa | not_analyzed | not_analyzed | YES | A genuine, well-engineered, actively maintained JavaScript CLI/process-execution |
| torvalds | linux | analyzed | analyzed | no | C-dominant per GitHub language stats (~98.9% of a huge byte count). With only 12 |

## Concept verdicts (only for analyzed repos)

| username | repo | concept_id | found | tag | classification |
|---|---|---|---|---|---|
| Jango1324 | JPod-ESP32 | language.cpp | True |  |  |
| karpathy | micrograd | language.jupyter_notebook | True |  |  |
| karpathy | micrograd | language.python | True |  |  |
| karpathy | llm.c | platform.cuda | True |  |  |
| karpathy | llm.c | language.python | True |  |  |
| karpathy | llm.c | language.c | True |  |  |
| karpathy | llm.c | ml.framework.pytorch | True |  |  |
| sindresorhus | got | language.typescript | True |  |  |
| torvalds | linux | language.c | True |  |  |

## False positives (not-expected concept found)

- `karpathy/llm.c` -> unexpectedly found 'language.cpp': C++ is present in the raw language stats but at ~3.5% of bytes, below the 5% significance floor -- correctly expected to produce NO evidence, not a miss.
