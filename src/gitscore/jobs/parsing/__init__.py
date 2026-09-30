"""Milestone 6B -- deterministic, rule-based job-description parsing.

Raw Job Description -> JobRequirementProfile (Milestone 6A's existing
domain model, unchanged). No LLM, no external API, no candidate/job
matching, no scoring. See `jobs/parsing/parser.py`'s module docstring for
the full pipeline diagram and `docs/ARCHITECTURE.md`'s Milestone 6B
section for the complete design write-up.
"""
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION, parse_job_description

__all__ = [
    "JOB_DESCRIPTION_PARSER_VERSION",
    "parse_job_description",
]
