# Milestone 9B Phase 2 -- Retrieval-Sensitive End-to-End Evaluation (Synthetic Fixtures)

Corpus version: `9b:v1`

Four events measured independently per case: (A) retrieval success, (B) new evidence discovery, (C) new requirement support, (D) alignment-score impact. See module docstring for why these must never be conflated.

| job_id | A: retrieved? | B: new concepts | C: newly SUPPORTED | D: score before->after | justified? |
|---|---|---|---|---|---|
| m9b_rust_or_go_backend_01 | True | language.rust | Proficiency in Rust or Go | 67 -> 100 | True |
| m9b_kotlin_preferred_01 | False | (none) | (none) | 67 -> 67 | True |
| m9b_redundant_rust_01 | True | (none) | (none) | 100 -> 100 | True |

## Common-language repository dominance check

`viral-js-framework` (80000 stars) relevance score: 1.0  |  `js-service-01` (50 stars) relevance score: 1.0  |  equal despite the star gap: True

## Per-case detail

### m9b_rust_or_go_backend_01 (candidate: crowded_polyglot_dev)
- Test intent: A REQUIRED alternative-group requirement (Rust or Go) satisfiable only by a repository (aaa-rust-microtool) that the generic ranker excludes on crowded_polyglot_dev, but that job-aware retrieval recovers via the structured primary_language signal. Demonstrates genuinely NEW evidence causing a real NOT_OBSERVED -> SUPPORTED flip and a real alignment_score change.
- Generic selection: 15 repos
- Job-aware selection: 16 repos; additions: ['aaa-rust-microtool']
- (A) Retrieval success: True
- (B) New evidence concepts gained: ['language.rust']
- (C) Requirements newly SUPPORTED: ['Proficiency in Rust or Go']
- Requirements still NOT_OBSERVED after retrieval: []
- NOT_ASSESSABLE requirement count: 1
- (D) alignment_score: 67 -> 100
       required: (2, 3) -> (3, 3)
       preferred: None -> None
- Score change justified: True (score change fully explained by newly-SUPPORTED requirement(s): ('Proficiency in Rust or Go',))

### m9b_kotlin_preferred_01 (candidate: crowded_polyglot_dev)
- Test intent: A PREFERRED, single-concept requirement (Kotlin) satisfiable only by a repository (kotlin-microtool) the generic ranker excludes on the SAME crowded_polyglot_dev candidate -- but this time job-aware retrieval ALSO fails to recover it, because 21 other repositories on the account each score a full REQUIRED-weight 1.0 for this job's javascript/python terms while kotlin-microtool scores only the PREFERRED weight 0.5, so the fixed relevance_top_k=10 budget fills entirely with 1.0-scorers before kotlin-microtool is ever considered. Demonstrates a genuinely relevant repository still crowded out under the bounded top-K budget, with no alignment_score change as a result.
- Generic selection: 15 repos
- Job-aware selection: 15 repos; additions: []
- (A) Retrieval success: False
- (B) New evidence concepts gained: []
- (C) Requirements newly SUPPORTED: []
- Requirements still NOT_OBSERVED after retrieval: ['Familiarity with Kotlin is a plus']
- NOT_ASSESSABLE requirement count: 1
- (D) alignment_score: 67 -> 67
       required: (2, 2) -> (2, 2)
       preferred: (0, 1) -> (0, 1)
- Score change justified: True (no score change and no new support -- consistent (redundant recovery or no recovery))

### m9b_redundant_rust_01 (candidate: redundant_recovery_dev)
- Test intent: A REQUIRED single-concept requirement (Rust) that is ALREADY supported generically on redundant_recovery_dev via polyglot-service's 20% Rust byte-share (above the 5% significance floor), while a second, Rust-only repository (aaa-rust-only-mini) sits outside the generic top-15 and IS recovered by job-aware retrieval. Demonstrates retrieval succeeding (a new repository is genuinely analyzed) while contributing only redundant evidence -- no requirement flips, no alignment_score change.
- Generic selection: 15 repos
- Job-aware selection: 16 repos; additions: ['aaa-rust-only-mini']
- (A) Retrieval success: True
- (B) New evidence concepts gained: []
- (C) Requirements newly SUPPORTED: []
- Requirements still NOT_OBSERVED after retrieval: []
- NOT_ASSESSABLE requirement count: 1
- (D) alignment_score: 100 -> 100
       required: (2, 2) -> (2, 2)
       preferred: None -> None
- Score change justified: True (no score change and no new support -- consistent (redundant recovery or no recovery))

