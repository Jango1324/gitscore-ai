# Parser Evaluation Report

Corpus version: `8c:v1`
Jobs evaluated: 15
Expected requirements: 103
Recall: 0.563  |  Precision: 0.892

## Status counts

| status | count |
|---|---|
| CORRECT | 58 |
| MISSING | 44 |
| WRONG_ALTERNATIVE_STRUCTURE | 1 |

## Error tag counts (a verdict may carry more than one)

| tag | count |
|---|---|
| MISSING | 44 |
| WRONG_ALTERNATIVE_STRUCTURE | 1 |

## Most-missed concepts/terms

| concept_id / term | miss count |
|---|---|
| unresolved:kubernetes | 2 |
| unresolved:bigquery | 1 |
| unresolved:snowflake | 1 |
| unresolved:spi | 1 |
| unresolved:i2c | 1 |
| unresolved:uart | 1 |
| unresolved:angular | 1 |
| unresolved:vue | 1 |
| unresolved:flutter | 1 |
| unresolved:react_native | 1 |
| unresolved:matlab | 1 |
| unresolved:simulink | 1 |

## Spurious requirements: 7

- `backend_01` / 'Familiarity with Docker and Kubernetes' -> concept_id='infra.kubernetes' category='infrastructure'
- `data_engineering_01` / 'Strong SQL skills across relational databases' -> concept_id='language.sql' category='language'
- `data_science_01` / 'Proficiency in SQL for data analysis' -> concept_id='language.sql' category='language'
- `devops_cloud_01` / 'Strong experience with Docker and Kubernetes' -> concept_id='infra.kubernetes' category='infrastructure'
- `mobile_01` / 'Strong experience with Swift for iOS development' -> concept_id='language.swift' category='language'
- `mobile_01` / 'Experience with Kotlin for Android development' -> concept_id='language.kotlin' category='language'
- `sre_platform_01` / 'Experience with Kubernetes for container orchestration' -> concept_id='infra.kubernetes' category='infrastructure'
