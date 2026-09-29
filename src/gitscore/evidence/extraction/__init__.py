"""Milestone 5D -- bounded technical evidence extraction.

Turns the top-N ranked repositories (gitscore.ranking, Milestone 5B) into
real, provenance-backed Evidence (gitscore.evidence, Milestone 5C) from a
deliberately small set of high-value sources: repository language
statistics, README text, dependency/package manifests, and
Docker-related files. See docs/ARCHITECTURE.md's Milestone 5D section
and docs/CHANGELOG_DEV.md for the full design rationale.

Each submodule is one extractor (or a shared building block used by more
than one extractor):
  languages.py             repository-language-statistics evidence
  readme.py                README concept-mention evidence
  python_deps.py           requirements.txt / pyproject.toml / Pipfile
  js_deps.py                package.json
  dependency_evidence.py    shared declaration -> Evidence conversion
                            (resolve, confidence, unknown-name tracking)
  docker.py                 Dockerfile / docker-compose evidence
  files.py                  root-file discovery (one bounded request)

None of these modules touch V1 (`features/*`, `scoring/readiness.py`,
`pipeline/analyze.py`) or perform any job matching. The orchestrating
entry point is `gitscore.pipeline.evidence.extract_candidate_evidence`.
"""
