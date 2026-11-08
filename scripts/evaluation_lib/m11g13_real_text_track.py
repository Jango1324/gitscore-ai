"""Milestone 11-G13 -- real-text generalization track (aggregate-only).

Evaluation-only. Reads the PRIVATE, untracked M11-D / M11-F / M11-G9
holdout annotations and their source postings locally, and emits ONLY
aggregate counts and hashes. No posting text, file name, or
posting-derived id is written to any output or printed. When the private
files are absent (e.g. a fresh clone), every entry point reports
`available=False` and does nothing else.

Gold necessity/qualification labels come from those pre-existing holdouts
(annotated before G12 existed). Extractor proposals are generated
MECHANICALLY by the generator rules frozen in
`evaluation/m11g13/generalization_controls.json` (protocol section) --
never chosen by hand, never tuned.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.qualification import QualificationKind  # noqa: E402

import m11g10_competency_concept_model as g10  # noqa: E402
import m11g11_structured_extraction_feasibility as g11  # noqa: E402
import m11g12_validator_hardening as g12  # noqa: E402

INPUTS_FREEZE_PATH = _REPO_ROOT / "evaluation" / "m11g13" / "real_text_inputs_freeze.json"

DATASETS = {
    "m11d": {
        "annotations": "evaluation/m11d/holdout_annotations.json", "rows_key": "claims",
        "source_dir": "evaluation/m11d/source", "tracked_source_hashes": "evaluation/m11d/source_hashes.json",
        "tracked_gold_freeze": None,
    },
    "m11f": {
        "annotations": "evaluation/m11f/holdout_annotations.json", "rows_key": "controls",
        "source_dir": "evaluation/m11f/source", "tracked_source_hashes": "evaluation/m11f/source_hashes.json",
        "tracked_gold_freeze": "evaluation/m11f/gold_hash_freeze.json",
    },
    "m11g9": {
        "annotations": "evaluation/m11g9/holdout_annotations.json", "rows_key": "controls",
        "source_dir": "evaluation/m11g9/source", "tracked_source_hashes": "evaluation/m11g9/source_hashes.json",
        "tracked_gold_freeze": "evaluation/m11g9/gold_hash_freeze.json",
    },
}

REQ_GEN = re.compile(r"\b(?:required|must|mandatory|essential)\b", re.IGNORECASE)
PREF_GEN = re.compile(r"\b(?:preferred|plus|bonus|nice to have|desirable|ideally)\b", re.IGNORECASE)
_SEGMENT = re.compile(r"[^.!?\n]+[.!?]?")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha_lf(b: bytes) -> str:
    """Line-ending-canonical hash: identical for CRLF and LF copies."""
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


_CANONICAL_FIELDS = ("rows", "source_files", "annotation_sha256_lf_normalized", "sources_combined_sha256_lf_normalized")


def _canonical(fingerprint: dict) -> dict:
    """The subset G13's own integrity check compares: counts and
    LF-normalized hashes only, so the check is platform-independent. Raw
    hashes and tracked-record checks are kept as information (the tracked
    historical records are raw-byte hashes by their own convention)."""
    return {name: {k: v.get(k) for k in _CANONICAL_FIELDS} for name, v in fingerprint.items()}


def missing_inputs() -> list[str]:
    missing = []
    for d in DATASETS.values():
        for rel in (d["annotations"], d["source_dir"]):
            if not (_REPO_ROOT / rel).exists():
                missing.append(rel)
    return missing


def available() -> bool:
    return all((_REPO_ROOT / d["annotations"]).exists() and (_REPO_ROOT / d["source_dir"]).is_dir()
               for d in DATASETS.values())


def _tracked_hash(record: object) -> str | None:
    if isinstance(record, str):
        return record
    if isinstance(record, dict):
        return record.get("sha256")
    return None


def _source_files(cfg) -> list[Path]:
    return sorted(p for p in (_REPO_ROOT / cfg["source_dir"]).rglob("*") if p.is_file())


def _tracked_by_basename(tracked: object) -> dict[str, str]:
    """Normalizes the three tracked record shapes in this repo to
    {basename: sha256}: {path: sha}, {name: {sha256}}, [{id, sha256}]."""
    out: dict[str, str] = {}
    if isinstance(tracked, list):
        for entry in tracked:
            if isinstance(entry, dict) and entry.get("id") and entry.get("sha256"):
                out[entry["id"].replace("\\", "/").rsplit("/", 1)[-1]] = entry["sha256"]
    elif isinstance(tracked, dict):
        for key, rec in tracked.items():
            sha = _tracked_hash(rec)
            if sha:
                out[key.replace("\\", "/").rsplit("/", 1)[-1]] = sha
    return out


def input_fingerprint() -> dict:
    """Hashes and counts only. Verifies each private file against the
    repository's own tracked hash records where such records exist."""
    out: dict = {}
    for name, cfg in DATASETS.items():
        ann_bytes = (_REPO_ROOT / cfg["annotations"]).read_bytes()
        rows = json.loads(ann_bytes.decode("utf-8"))[cfg["rows_key"]]
        sources = _source_files(cfg)
        source_shas = {p.name: _sha(p.read_bytes()) for p in sources}
        tracked = _tracked_by_basename(
            json.loads((_REPO_ROOT / cfg["tracked_source_hashes"]).read_text(encoding="utf-8"))
        )
        checked = matched = 0
        for fname, sha in source_shas.items():
            exp = tracked.get(fname)
            if exp is not None:
                checked += 1
                matched += int(exp == sha)
        gold_match = None
        if cfg["tracked_gold_freeze"]:
            freeze = json.loads((_REPO_ROOT / cfg["tracked_gold_freeze"]).read_text(encoding="utf-8"))
            if freeze.get("frozen_file", "").endswith(Path(cfg["annotations"]).name):
                gold_match = freeze.get("sha256") == _sha(ann_bytes)
        source_shas_lf = sorted(_sha_lf(p.read_bytes()) for p in sources)
        out[name] = {
            "annotation_sha256": _sha(ann_bytes),
            "annotation_sha256_lf_normalized": _sha_lf(ann_bytes),
            "rows": len(rows),
            "source_files": len(sources),
            "sources_combined_sha256": _sha("\n".join(sorted(source_shas.values())).encode()),
            "sources_combined_sha256_lf_normalized": _sha("\n".join(source_shas_lf).encode()),
            "tracked_source_hash_checks": {"matched": matched, "checked": checked},
            "tracked_gold_freeze_match": gold_match,
        }
    return out


def freeze_inputs() -> dict:
    fp = input_fingerprint()
    INPUTS_FREEZE_PATH.write_bytes((json.dumps(fp, indent=2) + "\n").encode("utf-8"))
    return fp


def _load_sources(cfg) -> dict[str, str]:
    return {p.name: p.read_bytes().decode("utf-8") for p in _source_files(cfg)}


def _locate(name: str, row: dict, sources: dict[str, str]) -> tuple[str, int, int] | None:
    text = (row.get("text") or "").strip()
    if not text:
        return None
    if name == "m11g9" and row.get("source_span"):
        s, e = row["source_span"]["start"], row["source_span"]["end"]
        for key in (row.get("posting"), f"{row.get('posting')}.txt"):
            if key in sources and sources[key][s:e] == row["text"]:
                return sources[key], s, e
    if name == "m11d" and row.get("posting_id"):
        for key in (row["posting_id"], f"{row['posting_id']}.txt"):
            if key in sources and sources[key].count(text) == 1:
                i = sources[key].index(text)
                return sources[key], i, i + len(text)
    hits = [(src, src.index(text)) for src in sources.values() if src.count(text) == 1]
    if len(hits) == 1 and sum(src.count(text) for src in sources.values()) == 1:
        src, i = hits[0]
        return src, i, i + len(text)
    return None


def _segments(job_text: str) -> list[tuple[int, int]]:
    segs = []
    for m in _SEGMENT.finditer(job_text):
        raw = m.group()
        lead = len(raw) - len(raw.lstrip())
        stripped = raw.strip()
        if stripped:
            segs.append((m.start() + lead, m.start() + lead + len(stripped)))
    return segs


def _borrowed(job_text: str, s: int, e: int, pattern: re.Pattern[str]) -> str | None:
    best = None
    for a, b in _segments(job_text):
        if a < e and s < b:
            continue
        if not pattern.search(job_text, a, b):
            continue
        dist = abs(a - s)
        if best is None or dist < best[0]:
            best = (dist, a, b)
    return job_text[best[1]:best[2]] if best else None


def _heading(job_text: str, s: int) -> str | None:
    line_start = job_text.rfind("\n", 0, s) + 1
    above = job_text[:line_start].split("\n")
    for line in reversed(above):
        st = line.strip()
        if not st or len(st) > 80:
            continue
        letters = [c for c in st if c.isalpha()]
        if st.endswith(":") or st.startswith("#") or (st.startswith("**") and st.endswith("**")) or (
            letters and st == st.upper()
        ):
            return st
    return None


def _candidate(row: dict, s: int, e: int, job_text: str, proposed: str, evidence: str | None):
    try:
        kind = QualificationKind((row.get("qualification_kind") or "").lower())
    except ValueError:
        kind = QualificationKind.OTHER_LEGITIMATE
    text = job_text[s:e]
    return g11.CandidateQualification(
        source_text=text,
        source_span=SourceSpan(start=s, end=e),
        applicant_classification=g11.ApplicantClassification.QUALIFICATION,
        classification_evidence=text,
        proposed_necessity=g11.ExtractedNecessity(proposed),
        necessity_evidence=evidence,
        qualification_kind=kind,
        proposed_concept=g11.ProposedConceptReference(unresolved_term="real-text-track"),
    )


def _proposals(row: dict, s: int, e: int, job_text: str):
    gold = (row.get("necessity") or "unknown").lower()
    text = job_text[s:e]
    if row.get("is_applicant_qualification"):
        if gold in ("required", "preferred"):
            yield "R1_own_text_gold", gold, text, gold
            h = _heading(job_text, s)
            if h:
                yield "R2_heading_gold", gold, h, gold
        if gold in ("preferred", "unknown"):
            yield "R3_overclaim_own_text", "required", text, gold
            b = _borrowed(job_text, s, e, REQ_GEN)
            if b:
                yield "R4_borrowed_required", "required", b, gold
        if gold in ("required", "unknown"):
            b = _borrowed(job_text, s, e, PREF_GEN)
            if b:
                yield "R5_borrowed_preferred", "preferred", b, gold
    else:
        ev = text if REQ_GEN.search(text) else _borrowed(job_text, s, e, REQ_GEN)
        if ev:
            yield "R6_nonqualification_required", "required", ev, "unknown"


PRESERVATION_GENERATORS = ("R1_own_text_gold", "R2_heading_gold")


def run_real_text_track() -> dict:
    """OPT-IN only (see `scripts/evaluate_m11g13_generalization.py --real-text`).
    Fails loudly -- never silently skips -- when the private inputs are
    missing or differ from their G13 freeze."""
    missing = missing_inputs()
    if missing:
        raise SystemExit(
            "M11-G13 real-text track requested, but private holdout material is missing: "
            + ", ".join(missing) + ". This track needs the local, untracked M11-D/F/G9 files; "
            "the committed aggregates in evaluation/m11g13/real_text_track_aggregates.json stand on their own."
        )
    frozen = json.loads(INPUTS_FREEZE_PATH.read_text(encoding="utf-8"))
    if _canonical(input_fingerprint()) != _canonical(frozen):
        raise SystemExit("REAL-TEXT INPUTS CHANGED since their G13 freeze (LF-normalized comparison)")
    graph = g10.build_reference_graph()
    located = Counter()
    rows_total = Counter()
    tallies: dict = {}
    for name, cfg in DATASETS.items():
        sources = _load_sources(cfg)
        rows = json.loads((_REPO_ROOT / cfg["annotations"]).read_text(encoding="utf-8"))[cfg["rows_key"]]
        for row in rows:
            rows_total[name] += 1
            loc = _locate(name, row, sources)
            if loc is None:
                continue
            job_text, s, e = loc
            located[name] += 1
            for gen, proposed, evidence, gold in _proposals(row, s, e, job_text):
                cand = _candidate(row, s, e, job_text, proposed, evidence)
                key = (name, gen)
                t = tallies.setdefault(key, Counter())
                t["proposals"] += 1
                for label, validator in (("g11", g11.validate_candidate), ("g12", g12.validate_candidate_hardened)):
                    r = validator(cand, job_text, graph)
                    kept = r.necessity.value == proposed and r.accepted_for_review
                    t[f"{label}_kept"] += int(kept)
                if gen in PRESERVATION_GENERATORS:
                    # POST-HOC breakdown (added after the first run, disclosed in the doc):
                    # does the cited evidence contain the generator's own tier marker at all?
                    tier_marker = REQ_GEN if proposed == "required" else PREF_GEN
                    if tier_marker.search(evidence):
                        t["posthoc_evidence_has_tier_marker"] += 1
                        r12 = g12.validate_candidate_hardened(cand, job_text, graph)
                        r11 = g11.validate_candidate(cand, job_text, graph)
                        t["posthoc_g12_kept_given_marker"] += int(
                            r12.necessity.value == proposed and r12.accepted_for_review)
                        t["posthoc_g11_kept_given_marker"] += int(
                            r11.necessity.value == proposed and r11.accepted_for_review)
                if gen == "R3_overclaim_own_text":
                    t["row_text_contains_required_language"] += int(bool(REQ_GEN.search(job_text[s:e])))
                    r12 = g12.validate_candidate_hardened(cand, job_text, graph)
                    if r12.necessity.value == "required" and r12.accepted_for_review:
                        t["g12_kept_and_row_text_contains_required_language"] += int(
                            bool(REQ_GEN.search(job_text[s:e]))
                        )
    per_dataset: dict = {}
    for (name, gen), t in sorted(tallies.items()):
        per_dataset.setdefault(name, {})[gen] = dict(t)
    totals: dict = {}
    for gen in sorted({g for (_, g) in tallies}):
        agg = Counter()
        for (_, g), t in tallies.items():
            if g == gen:
                agg.update(t)
        totals[gen] = dict(agg)
    return {
        "available": True,
        "rows": dict(rows_total),
        "rows_located_verbatim": dict(located),
        "per_dataset": per_dataset,
        "totals": totals,
        "interpretation": {
            "preservation_generators": list(PRESERVATION_GENERATORS),
            "note": "For R1/R2 'kept' counts genuine gold necessities the validator preserved. For R3-R6 'kept' "
                    "counts UNSAFE acceptances: the proposal disagrees with gold yet was returned unchanged with "
                    "accepted_for_review=True. Counts include candidates whose concept is unresolved; with any "
                    "resolved assessable concept each unsafe acceptance would be score-eligible.",
        },
    }
