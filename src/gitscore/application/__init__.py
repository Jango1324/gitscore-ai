"""Milestone 7C -- the application/orchestration layer.

The only package in this codebase allowed to depend on `gitscore.pipeline`,
`gitscore.jobs`, `gitscore.matching`, and `gitscore.assessment` together.
Those packages are domain/component layers and must never import from
here -- see `gitscore.application.job_fit`'s module docstring for the
full pipeline diagram and the rest of this package's design rationale.
"""
from gitscore.application.job_fit import JobAnalysisResult, analyze_job_fit

__all__ = [
    "JobAnalysisResult",
    "analyze_job_fit",
]
