# Milestone 9B Phase 1 -- Requirement Preservation Benchmark

Corpus version: `9b:v1`  |  Parser version under test: `job_description_parser:v5`

Total entries: 30 (26 requirement claims, 4 non-requirement prose/headings)

## Verdict distribution

| Verdict | Count |
|---|---|
| IDEAL_MATCH | 13 |
| FALLBACK_MATCH | 7 |
| SILENT_DROP_GAP | 6 |
| CORRECTLY_EXCLUDED | 4 |

## Metrics (kept separate by design -- see each definition)

### 1_genuine_requirement_preservation_recall
- Definition: fraction of real requirements that produced >=1 JobRequirement row, of any honest shape
- Value: 0.615 (16/26)

### 2_correctly_structured_technical_requirements
- Definition: fraction of technical requirements matching their ideal_outcome exactly (full structural credit)
- Value: 0.5 (9/18)

### 3_unknown_concept_preservation
- Definition: fraction of entries whose ideal outcome names a specific unresolved:<term> id that actually produced that exact id
- Value: 0.5 (5/10)

### 4_unknown_or_and_structural_correctness
- Definition: of metric 3's entries that are OR- or AND-structured, fraction with the fully correct group/list structure
- Value: 0.833 (5/6)

### 5_correct_unparsed_placeholder_preservation
- Definition: of entries whose ideal or accepted-fallback outcome is a non-fabricating placeholder, fraction that landed on exactly that placeholder
- Value: 0.643 (9/14)

### 6_spurious_requirement_creation
- Definition: raw count of JobRequirement rows produced for an is_requirement=false entry (should always be 0)
- Value: 0

### 7_incorrect_technology_fabrication
- Definition: raw count of entries where a REAL, wrong concept id was attached -- kept separate from metric 6 and from any placeholder metric by design
- Value: 0

### 8_exact_source_span_correctness
- Definition: of entries producing >=1 row, fraction whose source_span exactly matches the claim's true position in the wrapped text
- Value: 1.0 (16/16)

### 9_silent_drop_count
- Definition: raw counts of real requirements producing zero rows, split by whether this corpus's own annotation accepts that as non-failure
- Value: {'accepted_by_corpus': 0, 'flagged_as_gap': 6}

### 10_correctly_excluded_non_requirement_prose
- Definition: fraction of is_requirement=false entries (headings/prose) that correctly produced zero rows for that exact text
- Value: 1.0 (4/4)

## Per-entry verdicts

| ID | Category | Verdict | Rows produced | Actual |
|---|---|---|---|---|
| m9b-001 | registered_technical_concept | IDEAL_MATCH | 2 | language.python; database.postgresql |
| m9b-002 | registered_technical_concept | IDEAL_MATCH | 2 | infra.docker; infra.kubernetes |
| m9b-003 | unregistered_named_technology | FALLBACK_MATCH | 1 | category='unresolved_requirement' |
| m9b-004 | unregistered_named_technology | FALLBACK_MATCH | 1 | category='unresolved_requirement' |
| m9b-005 | unknown_single_term | SILENT_DROP_GAP | 0 | (none) |
| m9b-006 | unknown_single_term | SILENT_DROP_GAP | 0 | (none) |
| m9b-007 | unknown_and_list | IDEAL_MATCH | 3 | unresolved:spi; unresolved:i2c; unresolved:uart |
| m9b-008 | unknown_and_list | SILENT_DROP_GAP | 0 | (none) |
| m9b-009 | unknown_or_group | IDEAL_MATCH | 1 | ALT['unresolved:angular', 'unresolved:vue'] |
| m9b-010 | unknown_or_group | IDEAL_MATCH | 1 | ALT['unresolved:matlab', 'unresolved:simulink'] |
| m9b-011 | unknown_or_group | IDEAL_MATCH | 1 | ALT['unresolved:bigquery', 'unresolved:snowflake'] |
| m9b-012 | mixed_known_and_unknown | IDEAL_MATCH | 3 | framework.react; unresolved:vue; unresolved:graphql |
| m9b-013 | mixed_known_and_unknown | IDEAL_MATCH | 1 | category='alternative_requirement' |
| m9b-014 | technical_competency_no_named_product | SILENT_DROP_GAP | 0 | (none) |
| m9b-015 | technical_competency_no_named_product | SILENT_DROP_GAP | 0 | (none) |
| m9b-016 | technical_competency_no_named_product | SILENT_DROP_GAP | 0 | (none) |
| m9b-017 | professional_experience | IDEAL_MATCH | 1 | category='experience' |
| m9b-018 | education | IDEAL_MATCH | 1 | category='education' |
| m9b-019 | certification | FALLBACK_MATCH | 1 | category='unresolved_requirement' |
| m9b-020 | certification | FALLBACK_MATCH | 0 | (none) |
| m9b-021 | soft_skill | IDEAL_MATCH | 1 | category='soft_skill' |
| m9b-022 | soft_skill | FALLBACK_MATCH | 0 | (none) |
| m9b-023 | soft_skill | IDEAL_MATCH | 1 | category='soft_skill' |
| m9b-024 | non_requirement_prose | CORRECTLY_EXCLUDED | 0 | (none) |
| m9b-025 | non_requirement_prose | CORRECTLY_EXCLUDED | 0 | (none) |
| m9b-026 | heading_or_section_intro | CORRECTLY_EXCLUDED | 0 | (none) |
| m9b-027 | heading_or_section_intro | CORRECTLY_EXCLUDED | 0 | (none) |
| m9b-028 | ambiguous_language | IDEAL_MATCH | 1 | category='unresolved_requirement' |
| m9b-029 | ambiguous_language | FALLBACK_MATCH | 0 | (none) |
| m9b-030 | registered_technical_concept | FALLBACK_MATCH | 0 | (none) |
