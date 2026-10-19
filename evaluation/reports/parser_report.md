# Parser Evaluation Report

Corpus version: `8c:v1`
Jobs evaluated: 15
Expected requirements: 103
Recall: 0.621  |  Precision: 0.771

## Status counts

| status | count |
|---|---|
| CORRECT | 64 |
| MISSING | 38 |
| WRONG_ALTERNATIVE_STRUCTURE | 1 |

## Error tag counts (a verdict may carry more than one)

| tag | count |
|---|---|
| MISSING | 38 |
| WRONG_ALTERNATIVE_STRUCTURE | 1 |

## Most-missed concepts/terms

| concept_id / term | miss count |
|---|---|
| unresolved:kubernetes | 2 |
| unresolved:flutter | 1 |
| unresolved:react_native | 1 |

## Spurious requirements: 19

- `backend_01` / 'Familiarity with Docker and Kubernetes' -> concept_id='infra.kubernetes' category='infrastructure'
- `data_engineering_01` / 'Strong SQL skills across relational databases' -> concept_id='language.sql' category='language'
- `data_engineering_01` / 'Experience with dbt' -> concept_id=None category='unresolved_requirement'
- `data_science_01` / 'Proficiency in SQL for data analysis' -> concept_id='language.sql' category='language'
- `data_science_01` / 'Experience with scikit-learn' -> concept_id=None category='unresolved_requirement'
- `devops_cloud_01` / 'Strong experience with Docker and Kubernetes' -> concept_id='infra.kubernetes' category='infrastructure'
- `embedded_firmware_01` / 'Experience with CMake-based build systems' -> concept_id=None category='unresolved_requirement'
- `general_swe_01` / 'Strong computer science fundamentals, including data structures and algorithms' -> concept_id=None category='unresolved_requirement'
- `general_swe_01` / 'Experience with distributed systems' -> concept_id=None category='unresolved_requirement'
- `mobile_01` / 'Strong experience with Swift for iOS development' -> concept_id='language.swift' category='language'
- `mobile_01` / 'Experience with Kotlin for Android development' -> concept_id='language.kotlin' category='language'
- `mobile_01` / 'Familiarity with REST API integration' -> concept_id=None category='unresolved_requirement'
- `robotics_controls_01` / 'Experience with control systems or state estimation' -> concept_id=None category='unresolved_requirement'
- `robotics_controls_01` / 'Familiarity with PLC programming' -> concept_id=None category='unresolved_requirement'
- `security_01` / 'Experience with penetration testing or vulnerability assessment' -> concept_id=None category='unresolved_requirement'
- `security_01` / 'Security certification such as OSCP or CISSP' -> concept_id=None category='unresolved_requirement'
- `sre_platform_01` / 'Experience with Kubernetes for container orchestration' -> concept_id='infra.kubernetes' category='infrastructure'
- `sre_platform_01` / 'Experience with Terraform' -> concept_id=None category='unresolved_requirement'
- `systems_cpp_01` / 'Experience with Linux systems programming' -> concept_id=None category='unresolved_requirement'
