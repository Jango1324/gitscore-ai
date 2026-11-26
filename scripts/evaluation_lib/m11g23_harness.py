"""Milestone 11-G23 -- candidate-profile heading research harness (OFFLINE, research only).

Nothing here is imported by `src/gitscore`. Production code is never modified.

`segment(description, policy)` is a replica of production `segmentation.segment_description()` (parser v15)
with policy hooks for heading classification, sub-heading inheritance, list-section paragraph reset,
two-line headings and per-claim qualification-intent gating. With `P0` (no hooks) it must equal production
byte for byte -- `fidelity_mismatches()` checks that on every corpus the report measures.

`active(policy)` installs the replica for the duration of a `with` block in every place the v15 pipeline and
the G20/G21/G22 research harnesses look segmentation up at call time:
`gitscore.jobs.parsing.parser.segment_description` / `.document_has_any_recognized_heading`,
`gitscore.jobs.parsing.segmentation.segment_description` / `.document_has_any_recognized_heading`, and the
G20 replica's `m11g20_admission.segment` / `.doc_has_heading`. Everything downstream -- G21 qualification
intent, necessity, alternatives (G17), concepts (G22-Q), dedup, matcher v1, scoring v2 -- is the real
production code. The previous objects are always restored, including on exceptions.
"""
from __future__ import annotations

import re
import sys
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import m11g20_admission as adm  # noqa: E402

from gitscore.jobs.parsing import parser as parser_mod  # noqa: E402
from gitscore.jobs.parsing import segmentation as seg  # noqa: E402
from gitscore.jobs.parsing.qualification_intent import claim_role  # noqa: E402
from gitscore.jobs.types import Necessity  # noqa: E402

K = seg._SectionKind
_QUALIFYING = (K.REQUIRED, K.PREFERRED)


def _heading(policy, lines, i, description):
    """(kind, lines_consumed, is_candidate_profile) for the line at `i`, or None when it is content."""
    m = lines[i]
    line = m.group()
    span = seg._line_content_span(line, m.start())
    if span is None:
        return None
    content = description[span[0]:span[1]]
    kind, cp = policy.classify(line, content)
    if kind is not None:
        return kind, 1, cp
    if policy.wrapped_headings and i + 1 < len(lines):
        nxt = lines[i + 1]
        nspan = seg._line_content_span(nxt.group(), nxt.start())
        if nspan is not None and "\n\n" not in description[m.end():nxt.start()].replace("\r", ""):
            combined = f"{content} {description[nspan[0]:nspan[1]]}"
            kind2, cp2 = policy.classify_wrapped(line, content, nxt.group(), combined)
            if kind2 is not None:
                return kind2, 2, cp2
    return None


def segment(description: str, policy) -> tuple:
    """Replica of production `segment_description()` with G23 hooks (identical when the hooks are off)."""
    claims: list = []
    current_kind = None
    cp_section = False          # current section was opened by a candidate-profile heading (G23 hooks only)
    last_bulleted = False
    last_block_end = None
    lines = list(re.finditer(r"[^\r\n]+", description))
    i = 0
    while i < len(lines):
        line_match = lines[i]
        line = line_match.group()
        content_span = seg._line_content_span(line, line_match.start())
        if content_span is None:
            i += 1
            continue
        content_start, content_end = content_span
        content = description[content_start:content_end]

        head = _heading(policy, lines, i, description)
        if head is not None:
            kind, consumed, cp = head
            if (policy.inherit_subheadings and kind is K.UNKNOWN and current_kind in _QUALIFYING
                    and policy.is_inheritable_subheading(content)):
                kind, cp = current_kind, cp_section   # a family-less attribute sub-heading keeps its parent
            current_kind, cp_section = kind, cp
            last_bulleted, last_block_end = False, None
            i += consumed
            continue

        if current_kind is K.SKIP:
            i += 1
            continue

        is_bulleted = seg._BULLET_PREFIX.match(line) is not None
        if (policy.paragraph_reset and current_kind in _QUALIFYING and not is_bulleted and last_bulleted
                and last_block_end is not None and seg._is_paragraph_gap(description, last_block_end, content_start)):
            current_kind, cp_section = K.UNKNOWN, False

        block_end = content_end
        j = i + 1
        while j < len(lines) and seg._ends_incomplete(description[content_start:block_end]):
            next_match = lines[j]
            next_line = next_match.group()
            next_span = seg._line_content_span(next_line, next_match.start())
            if next_span is None:
                break
            next_content_start, next_content_end = next_span
            if seg._BULLET_PREFIX.match(next_line) is not None:
                break
            if _heading(policy, lines, j, description) is not None:
                break
            if seg._is_paragraph_gap(description, block_end, next_content_start):
                break
            block_end = next_content_end
            j += 1
        content = description[content_start:block_end]

        if current_kind in (K.UNKNOWN, K.LEARNING):
            hint = None
        else:
            hint = seg._SECTION_NECESSITY_HINT.get(current_kind, Necessity.REQUIRED)
        in_recognized = current_kind in (K.REQUIRED, K.PREFERRED, K.RESPONSIBILITY)
        kind_name = current_kind.name if current_kind is not None else None

        for s, e in seg._split_sentences(content, description, content_start):
            sentence = description[s:e]
            c_hint, c_kind, c_recognized = hint, kind_name, in_recognized
            if cp_section and policy.intent_gate is not None:
                c_hint, c_kind, c_recognized = policy.intent_gate(sentence, hint, kind_name)
            if not c_recognized and not seg._looks_like_requirement(sentence):
                continue
            claims.append(seg.Claim(text=sentence, start=s, end=e, necessity_hint=c_hint, section_kind=c_kind))
        last_bulleted = is_bulleted
        last_block_end = block_end
        i = j
    return tuple(claims)


def doc_has_heading(description: str, policy) -> bool:
    lines = list(re.finditer(r"[^\r\n]+", description))
    return any(_heading(policy, lines, i, description) is not None for i in range(len(lines)))


# ---- installation --------------------------------------------------------------------------------------------
_TARGETS = ((parser_mod, "segment_description"), (parser_mod, "document_has_any_recognized_heading"),
            (seg, "segment_description"), (seg, "document_has_any_recognized_heading"),
            (adm, "segment"), (adm, "doc_has_heading"))


@contextmanager
def active(policy):
    """Install `policy` everywhere segmentation is looked up; always restores the originals."""
    saved = [(mod, name, getattr(mod, name)) for mod, name in _TARGETS]
    try:
        parser_mod.segment_description = seg.segment_description = lambda d: segment(d, policy)
        parser_mod.document_has_any_recognized_heading = seg.document_has_any_recognized_heading = \
            lambda d: doc_has_heading(d, policy)
        adm.segment = lambda d, _p: tuple(
            adm.RClaim(c.text, c.start, c.end, c.necessity_hint, c.section_kind) for c in segment(d, policy))
        adm.doc_has_heading = lambda d, _p: doc_has_heading(d, policy)
        yield policy
    finally:
        for mod, name, obj in saved:
            setattr(mod, name, obj)


def fidelity_mismatches(texts, p0) -> list[int]:
    """Indices where the P0 replica differs from production segmentation (must be [])."""
    bad = []
    for k, t in enumerate(texts):
        if segment(t, p0) != seg.segment_description(t) or \
                doc_has_heading(t, p0) != seg.document_has_any_recognized_heading(t):
            bad.append(k)
    return bad


def intent_role(sentence: str) -> str:
    return claim_role(sentence)[0]
