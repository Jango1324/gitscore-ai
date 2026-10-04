"""Milestone 8C -- evaluation-only helper package.

NOT part of `gitscore` (`src/gitscore/` is untouched by this milestone,
per its own "production code freeze" instruction). Everything here is
evaluation tooling: fixture loaders, gold-vs-actual classification, and
deterministic report writers consumed by `scripts/evaluate_*.py`. It
imports FROM `gitscore` (read-only use of the real, unmodified pipeline
functions) but nothing in `gitscore` imports from here.
"""
