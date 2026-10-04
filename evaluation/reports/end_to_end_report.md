# End-to-End Evaluation Matrix Report

Corpus version: `8c:v1`
Pairs evaluated: 12
Assessment aggregation errors: 0
Matcher integrity errors: 0

## Matrix

| candidate | job_id | expected_direction | alignment | required | preferred | supported | not_observed | not_assessable | agg_ok | matcher_ok |
|---|---|---|---|---|---|---|---|---|---|---|
| karpathy | ml_engineering_01 | positive | 75 | (2, 3) | (1, 1) | 3 | 1 | 2 | True | True |
| karpathy | computer_vision_01 | partial | 100 | (3, 3) | (1, 1) | 4 | 0 | 1 | True | True |
| karpathy | frontend_01 | negative | 80 | (4, 4) | (0, 1) | 4 | 1 | 1 | True | True |
| torvalds | systems_cpp_01 | positive | 67 | (1, 1) | (1, 2) | 2 | 1 | 0 | True | True |
| torvalds | embedded_firmware_01 | partial | 0 | None | (0, 1) | 0 | 1 | 1 | True | True |
| torvalds | data_science_01 | negative | 25 | (1, 3) | (0, 1) | 1 | 3 | 0 | True | True |
| sindresorhus | frontend_01 | positive | 80 | (4, 4) | (0, 1) | 4 | 1 | 1 | True | True |
| sindresorhus | fullstack_01 | partial | 57 | (3, 5) | (1, 2) | 4 | 3 | 1 | True | True |
| sindresorhus | robotics_controls_01 | negative | 33 | (1, 3) | None | 1 | 2 | 0 | True | True |
| Jango1324 | embedded_firmware_01 | partial | 0 | None | (0, 1) | 0 | 1 | 1 | True | True |
| Jango1324 | ml_engineering_01 | partial | 50 | (2, 3) | (0, 1) | 2 | 2 | 2 | True | True |
| Jango1324 | general_swe_01 | partial | 100 | (1, 1) | None | 1 | 0 | 1 | True | True |

## Rationale per pair

- `karpathy` x `ml_engineering_01` (positive): ML-heavy account against an ML Engineer posting.
- `karpathy` x `computer_vision_01` (partial): Shares Python/PyTorch/CUDA with CV, but OpenCV itself is unresolvable (registry gap) and no repo is vision-specific.
- `karpathy` x `frontend_01` (negative): ML account against a frontend posting -- cross-domain, little overlap expected.
- `torvalds` x `systems_cpp_01` (positive): C-heavy systems account against a Systems Software Engineer posting.
- `torvalds` x `embedded_firmware_01` (partial): Shares the C language, but no FreeRTOS/peripheral evidence exists on this account.
- `torvalds` x `data_science_01` (negative): Kernel-engineering account against a Data Scientist posting -- cross-domain.
- `sindresorhus` x `frontend_01` (positive): Prolific JS/TS account against a Frontend Engineer posting.
- `sindresorhus` x `fullstack_01` (partial): Strong JS/TS/React evidence, but no Python/PostgreSQL evidence on this account.
- `sindresorhus` x `robotics_controls_01` (negative): Frontend/web account against a Robotics/Controls posting -- cross-domain.
- `Jango1324` x `embedded_firmware_01` (partial): Has one C++-dominant ESP32 firmware repo, but no FreeRTOS/peripheral-specific evidence.
- `Jango1324` x `ml_engineering_01` (partial): Has a Pneumonia-Detection-Ai repo by name, but it falls outside the top-15 ranking cutoff -- tests whether a retrieval miss suppresses otherwise-plausible alignment.
- `Jango1324` x `general_swe_01` (partial): Multi-domain student account against a broad general-SWE posting.
