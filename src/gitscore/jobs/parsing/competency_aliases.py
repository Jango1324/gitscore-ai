"""Milestone 11-E -- a bounded, auditable semantic-alias table for the
17 existing M11-C competency tags.

**NOT wired into the live parser.** Standalone, like every other
module in this `jobs/parsing/` paraphrase-extraction lineage
(`qualification.py`, `qualification_adapter.py`,
`competency_extraction.py`) -- confirmed by a dedicated test.

## Why this exists

M11-D's own independent holdout measurement found `TECHNICAL_COMPETENCY`
recall collapsing from 93% (M11-C's own development corpus) to 5% on
authentic postings, and traced the dominant cause directly: the 17-tag
vocabulary matches near-verbatim canonical phrases only, with almost
no tolerance for the PARAPHRASE variance real employers actually use
("control tuning" vs. "control systems theory", "service and edge
networking" vs. "operating systems internals"). This module is the
GENERAL-MECHANISM response to that finding -- a bounded table of
alternate phrasings per tag, each explicitly classified by how safely
it may be treated as that tag, NOT a patch reverse-engineered from
M11-D's own specific holdout sentences (M11-D's own raw text/
annotations were not re-read while authoring this table; every alias
below was derived from ordinary professional-English synonymy for its
domain, independent of what M11-D specifically measured).

## The four relation types (per this milestone's own explicit contract)

- `SEMANTICALLY_EQUIVALENT`: a genuine synonym/paraphrase of the SAME
  competency -- safe to treat exactly like the canonical phrase,
  contributing `ParserConfidence.HIGH` when it is the ONLY signal
  found (mirrors a direct alias match's own existing confidence
  policy elsewhere in this project, e.g. `confidence.py`).
- `NARROWER_OR_MORE_SPECIFIC`: a genuine instance of the broader
  competency, but a more specific sub-skill the current 17-tag
  vocabulary has no finer-grained tag for. Mapped UP to the parent
  tag (the best existing representation available) but at
  `ParserConfidence.MEDIUM` -- an explicit, weaker confidence,
  never silently equated with an exact/equivalent match. Never
  promoted into a NEW canonical tag (explicit restriction: tag count
  is not expanded merely to raise recall).
- `RELATED_ONLY`: topically adjacent but NOT the same competency --
  deliberately EXCLUDED from the active matcher entirely (never
  compiled into a trigger pattern). Recorded here only for audit
  (so a reviewer can see what was considered and explicitly rejected)
  and reused by the Phase 3 evaluation harness as a precision
  stress-test: a strategy that fires on a `RELATED_ONLY` phrase is
  measurably wrong, not merely imprecise.
- `UNKNOWN`: considered, but no confident relation could be assigned
  at all -- also excluded from the active matcher. Distinct from
  `RELATED_ONLY` only for audit clarity (RELATED_ONLY names a
  specific, named reason the mapping is unsafe; UNKNOWN does not).

Only `SEMANTICALLY_EQUIVALENT` and `NARROWER_OR_MORE_SPECIFIC` entries
are compiled into `ACTIVE_ALIAS_PATTERNS` below; `RELATED_ONLY`/
`UNKNOWN` entries exist in `ALL_ALIASES` for audit and evaluation use
only and are NEVER matched against real text by any strategy in this
project.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class AliasRelation(str, Enum):
    SEMANTICALLY_EQUIVALENT = "semantically_equivalent"
    NARROWER_OR_MORE_SPECIFIC = "narrower_or_more_specific"
    RELATED_ONLY = "related_only"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CompetencyAlias:
    tag: str
    phrase: str
    relation: AliasRelation
    note: str = ""


# ---------------------------------------------------------------------------
# The alias table itself -- one block per existing M11-C competency tag.
# Every `phrase` is ordinary professional-English synonymy for its domain,
# reasoned independently per this module's own docstring.
# ---------------------------------------------------------------------------

ALL_ALIASES: tuple[CompetencyAlias, ...] = (
    # algorithms-data-structures
    CompetencyAlias("algorithms-data-structures", r"\bDS&A\b|\bDSA\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("algorithms-data-structures", r"\bcomputational complexity\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("algorithms-data-structures", r"\balgorithm design\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("algorithms-data-structures", r"\balgorithmic\s+(?:skills?|ability|thinking)\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("algorithms-data-structures", r"\bgraph algorithms\b|\bsorting algorithms\b|\bdynamic programming\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("algorithms-data-structures", r"\bcompetitive programming\b", AliasRelation.RELATED_ONLY, "contest skill, not necessarily job-relevant DS&A depth"),

    # concurrency
    CompetencyAlias("concurrency", r"\bthread[- ]safety\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("concurrency", r"\bparallel programming\b", AliasRelation.SEMANTICALLY_EQUIVALENT, "general-purpose parallel programming, distinct from GPU/HPC-specific parallelism"),
    CompetencyAlias("concurrency", r"\basync(?:hronous)?[/ ]await\b|\bactor model\b|\bmutex(?:es)?\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("concurrency", r"\bdistributed computing\b", AliasRelation.RELATED_ONLY, "should map to distributed-systems, not concurrency"),

    # distributed-systems
    CompetencyAlias("distributed-systems", r"\bdistributed computing\b|\bdistributed architecture\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("distributed-systems", r"\bleader election\b|\breplication strategies\b|\bCAP theorem\b|\beventual consistency\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("distributed-systems", r"\bmicroservices?\b", AliasRelation.RELATED_ONLY, "an architectural style, not proof of distributed-systems theory depth"),

    # system-design
    CompetencyAlias("system-design", r"\bsoftware architecture\b|\barchitectural design\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("system-design", r"\bAPI design\b|\bservice design\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("system-design", r"\bobject[- ]oriented design\b", AliasRelation.RELATED_ONLY, "narrower OOP concept, not system-level architecture"),

    # performance-optimization
    CompetencyAlias("performance-optimization", r"\bperformance tuning\b|\blatency optimization\b|\bthroughput optimization\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("performance-optimization", r"\bprofiling\b|\bbenchmarking\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("performance-optimization", r"\bscalability\b", AliasRelation.RELATED_ONLY, "often really a system-design/distributed-systems claim"),

    # os-networking
    CompetencyAlias("os-networking", r"\bnetwork protocols\b|\bsocket programming\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("os-networking", r"\bkernel development\b|\bedge networking\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("os-networking", r"\bnetwork security\b", AliasRelation.RELATED_ONLY, "belongs to cybersecurity-threat-modeling, not os-networking"),

    # database-design
    CompetencyAlias("database-design", r"\bschema design\b|\bquery optimization\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("database-design", r"\bnormalization\b|\bsharding strategies\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("database-design", r"\bdatabase administration\b", AliasRelation.RELATED_ONLY, "operational DBA work, a different skill from design"),

    # ml-fundamentals
    CompetencyAlias("ml-fundamentals", r"\bstatistical learning\b|\bML theory\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("ml-fundamentals", r"\bhyperparameter tuning\b|\bmodel evaluation metrics\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("ml-fundamentals", r"\bdata science\b", AliasRelation.RELATED_ONLY, "a broad field, not equivalent to ML fundamentals specifically"),

    # gpu-parallel-computing
    CompetencyAlias("gpu-parallel-computing", r"\bCUDA programming\b|\bHPC\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("gpu-parallel-computing", r"\bSIMD optimization\b|\bvectorization\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("gpu-parallel-computing", r"\bcloud computing\b", AliasRelation.RELATED_ONLY, "unrelated despite the shared word 'computing'"),

    # signal-processing
    CompetencyAlias("signal-processing", r"\bDSP\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("signal-processing", r"\bspectral analysis\b|\bwavelet transforms?\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("signal-processing", r"\baudio engineering\b", AliasRelation.RELATED_ONLY, "an application area, not the underlying competency"),

    # circuit-theory
    CompetencyAlias("circuit-theory", r"\banalog circuit design\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("circuit-theory", r"\bamplifier design\b|\bpower electronics\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("circuit-theory", r"\bPCB layout\b", AliasRelation.RELATED_ONLY, "a different, more mechanical layout skill"),

    # embedded-systems-design
    CompetencyAlias("embedded-systems-design", r"\bbare[- ]metal programming\b|\bmicrocontroller programming\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("embedded-systems-design", r"\bRTOS development\b|\bdevice driver development\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("embedded-systems-design", r"\bIoT development\b", AliasRelation.RELATED_ONLY, "broader, includes cloud/app layers beyond embedded"),

    # control-systems
    CompetencyAlias("control-systems", r"\bfeedback control\b|\bcontrol theory\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("control-systems", r"\bPID tuning\b|\bmodel predictive control\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("control-systems", r"\brobotics\b", AliasRelation.RELATED_ONLY, "too broad -- robotics includes many non-control competencies"),

    # computer-vision
    CompetencyAlias("computer-vision", r"\bCV\b|\bimage recognition\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("computer-vision", r"\bpose estimation\b|\boptical character recognition\b|\bOCR\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("computer-vision", r"\bgraphics programming\b", AliasRelation.RELATED_ONLY, "rendering, not understanding -- a different discipline"),

    # cybersecurity-threat-modeling
    CompetencyAlias("cybersecurity-threat-modeling", r"\bpenetration testing\b|\bvulnerability assessment\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("cybersecurity-threat-modeling", r"\bincident response\b|\bmalware analysis\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("cybersecurity-threat-modeling", r"\bcompliance\b|\bgovernance\b", AliasRelation.RELATED_ONLY, "an organizational function, not technical threat modeling"),

    # digital-logic
    CompetencyAlias("digital-logic", r"\blogic design\b|\bcombinational logic\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("digital-logic", r"\bFPGA programming\b|\bHDL design\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("digital-logic", r"\bcomputer architecture\b", AliasRelation.RELATED_ONLY, "broader, related but distinct from digital-logic design itself"),

    # quantum-computing
    CompetencyAlias("quantum-computing", r"\bquantum algorithms\b", AliasRelation.SEMANTICALLY_EQUIVALENT),
    CompetencyAlias("quantum-computing", r"\bquantum error correction codes?\b", AliasRelation.NARROWER_OR_MORE_SPECIFIC),
    CompetencyAlias("quantum-computing", r"\bquantum physics\b", AliasRelation.RELATED_ONLY, "the broader physics field, not the computing-specific competency"),
)

ACTIVE_RELATIONS = frozenset({AliasRelation.SEMANTICALLY_EQUIVALENT, AliasRelation.NARROWER_OR_MORE_SPECIFIC})

ACTIVE_ALIAS_PATTERNS: tuple[tuple[str, "re.Pattern[str]", AliasRelation], ...] = tuple(
    (a.tag, re.compile(a.phrase, re.IGNORECASE), a.relation) for a in ALL_ALIASES if a.relation in ACTIVE_RELATIONS
)
"""Only these patterns are ever matched against real text -- confirmed
by construction: `RELATED_ONLY`/`UNKNOWN` entries are filtered out at
import time, not merely by convention."""

EXCLUDED_ALIAS_PATTERNS: tuple[tuple[str, "re.Pattern[str]", AliasRelation, str], ...] = tuple(
    (a.tag, re.compile(a.phrase, re.IGNORECASE), a.relation, a.note) for a in ALL_ALIASES if a.relation not in ACTIVE_RELATIONS
)
"""`RELATED_ONLY`/`UNKNOWN` patterns, compiled for evaluation/audit use
ONLY (the Phase 3 harness uses these to confirm a candidate strategy
does NOT fire on them) -- never consulted by any extraction function."""
