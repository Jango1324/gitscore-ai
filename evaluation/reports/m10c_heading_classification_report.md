# Milestone 10C Heading Classification Report

Corpus: `evaluation\m10c\heading_controls.json` -- 78 entries.

## Summary

| Strategy | Heading-detection accuracy | exact_match | safe_disagreement | unsafe_mismatch | Real-posting headings correct (of 11) |
|---|---|---|---|---|---|
| A_expanded_exact_match | 0.872 | 68 | 6 | 4 | 10 |
| B_anchored_patterns_precedence | 0.923 | 71 | 5 | 2 | 10 |
| C_structured_detection_plus_purpose | 0.923 | 72 | 5 | 1 | 10 |

## A_expanded_exact_match

### Strict per-family precision/recall (non-ambiguous, is_heading=true entries only)

| Family | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|
| REQUIRED | 17 | 0 | 0 | 1.000 | 1.000 |
| PREFERRED | 9 | 0 | 0 | 1.000 | 1.000 |
| RESPONSIBILITY | 7 | 0 | 0 | 1.000 | 1.000 |
| LEARNING | 6 | 0 | 0 | 1.000 | 1.000 |
| NON_QUALIFICATION | 16 | 0 | 3 | 1.000 | 0.842 |
| UNKNOWN | 0 | 0 | 1 | n/a | 0.000 |

### Unsafe mismatches (confidently wrong, scoring-relevant)

| id | text | truth | predicted | severity |
|---|---|---|---|---|
| m10c-045-about-lumenbridge-fictional | About Lumenbridge | NON_QUALIFICATION | NOT_HEADING | low |
| m10c-046-about-coriander-labs-fictional | About Coriander Labs | NON_QUALIFICATION | NOT_HEADING | low |
| m10c-047-about-vertrix-systems-fictional | About Vertrix Systems | NON_QUALIFICATION | NOT_HEADING | low |
| m10c-069-additional-information | Additional Information | UNKNOWN | NOT_HEADING | low |

### Real-posting heading trace

| posting | text | truth | today recognized? | predicted | matches truth? |
|---|---|---|---|---|---|
| soti | Opportunity | UNKNOWN | False | NOT_HEADING | False |
| soti | What you will learn: | LEARNING | False | LEARNING | True |
| soti | Required skills: | REQUIRED | False | REQUIRED | True |
| soti | About SOTI | NON_QUALIFICATION | False | NON_QUALIFICATION | True |
| manulife | Position Responsibilities: | RESPONSIBILITY | False | RESPONSIBILITY | True |
| manulife | Required Qualifications: | REQUIRED | True | REQUIRED | True |
| manulife | Preferred Qualifications: | PREFERRED | True | PREFERRED | True |
| manulife | When you join our team: | NON_QUALIFICATION | False | NON_QUALIFICATION | True |
| manulife | Application instructions: | NON_QUALIFICATION | False | NON_QUALIFICATION | True |
| manulife | About Manulife and John Hancock | NON_QUALIFICATION | False | NON_QUALIFICATION | True |
| manulife | Working Arrangement | NON_QUALIFICATION | False | NON_QUALIFICATION | True |

## B_anchored_patterns_precedence

### Strict per-family precision/recall (non-ambiguous, is_heading=true entries only)

| Family | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|
| REQUIRED | 17 | 0 | 0 | 1.000 | 1.000 |
| PREFERRED | 9 | 0 | 0 | 1.000 | 1.000 |
| RESPONSIBILITY | 7 | 0 | 0 | 1.000 | 1.000 |
| LEARNING | 6 | 0 | 0 | 1.000 | 1.000 |
| NON_QUALIFICATION | 19 | 0 | 0 | 1.000 | 1.000 |
| UNKNOWN | 0 | 0 | 1 | n/a | 0.000 |

### Unsafe mismatches (confidently wrong, scoring-relevant)

| id | text | truth | predicted | severity |
|---|---|---|---|---|
| m10c-017-required-responsibilities | Required Responsibilities | RESPONSIBILITY | REQUIRED | high |
| m10c-069-additional-information | Additional Information | UNKNOWN | NOT_HEADING | low |

### Real-posting heading trace

| posting | text | truth | today recognized? | predicted | matches truth? |
|---|---|---|---|---|---|
| soti | Opportunity | UNKNOWN | False | NOT_HEADING | False |
| soti | What you will learn: | LEARNING | False | LEARNING | True |
| soti | Required skills: | REQUIRED | False | REQUIRED | True |
| soti | About SOTI | NON_QUALIFICATION | False | NON_QUALIFICATION | True |
| manulife | Position Responsibilities: | RESPONSIBILITY | False | RESPONSIBILITY | True |
| manulife | Required Qualifications: | REQUIRED | True | REQUIRED | True |
| manulife | Preferred Qualifications: | PREFERRED | True | PREFERRED | True |
| manulife | When you join our team: | NON_QUALIFICATION | False | NON_QUALIFICATION | True |
| manulife | Application instructions: | NON_QUALIFICATION | False | NON_QUALIFICATION | True |
| manulife | About Manulife and John Hancock | NON_QUALIFICATION | False | NON_QUALIFICATION | True |
| manulife | Working Arrangement | NON_QUALIFICATION | False | NON_QUALIFICATION | True |

## C_structured_detection_plus_purpose

### Strict per-family precision/recall (non-ambiguous, is_heading=true entries only)

| Family | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|
| REQUIRED | 17 | 0 | 0 | 1.000 | 1.000 |
| PREFERRED | 9 | 0 | 0 | 1.000 | 1.000 |
| RESPONSIBILITY | 7 | 0 | 0 | 1.000 | 1.000 |
| LEARNING | 6 | 0 | 0 | 1.000 | 1.000 |
| NON_QUALIFICATION | 19 | 0 | 0 | 1.000 | 1.000 |
| UNKNOWN | 0 | 0 | 1 | n/a | 0.000 |

### Unsafe mismatches (confidently wrong, scoring-relevant)

| id | text | truth | predicted | severity |
|---|---|---|---|---|
| m10c-069-additional-information | Additional Information | UNKNOWN | NOT_HEADING | low |

### Real-posting heading trace

| posting | text | truth | today recognized? | predicted | matches truth? |
|---|---|---|---|---|---|
| soti | Opportunity | UNKNOWN | False | NOT_HEADING | False |
| soti | What you will learn: | LEARNING | False | LEARNING | True |
| soti | Required skills: | REQUIRED | False | REQUIRED | True |
| soti | About SOTI | NON_QUALIFICATION | False | NON_QUALIFICATION | True |
| manulife | Position Responsibilities: | RESPONSIBILITY | False | RESPONSIBILITY | True |
| manulife | Required Qualifications: | REQUIRED | True | REQUIRED | True |
| manulife | Preferred Qualifications: | PREFERRED | True | PREFERRED | True |
| manulife | When you join our team: | NON_QUALIFICATION | False | NON_QUALIFICATION | True |
| manulife | Application instructions: | NON_QUALIFICATION | False | NON_QUALIFICATION | True |
| manulife | About Manulife and John Hancock | NON_QUALIFICATION | False | NON_QUALIFICATION | True |
| manulife | Working Arrangement | NON_QUALIFICATION | False | NON_QUALIFICATION | True |
