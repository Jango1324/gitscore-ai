"""Milestone 10A -- evaluation-integrity guards for `evaluation/m10/corpus.json`
and `scripts/evaluate_m10a_realworld.py`.

**What these tests do NOT claim.** Unlike `evaluation/m9b/corpus.json`
(whose annotations were written and committed to a separate file BEFORE
the real parser was ever run against them, per that corpus's own
process and `tests/test_m9b_preservation_eval.py::test_every_entry_declares_its_annotation_independently_of_the_parser`),
`evaluation/m10/corpus.json`'s labels were FORMALIZED into this file
AFTER diagnostic parser runs against the real SOTI/Manulife postings
had already been observed in the same working session. No test here
asserts, implies, or could truthfully assert "written before the
parser ran" -- that would misrepresent the actual process. These are
RETROSPECTIVE evaluation judgments: a human/model reading of what each
claim means, recorded alongside (not derived FROM) the parser's
observed behavior. See `evaluation/m10/corpus.json`'s own `source_note`
and `docs/evaluation/MILESTONE_10A_REALWORLD_PARSING_FAILURES.md` §0/§2
for the full, honest account of this limitation relative to M9B's
stronger procedural guarantee.

What IS tested: internal consistency and groundedness -- every
annotation is structurally complete, every category label is one of
the seven the milestone brief named, every claim's text is a real,
exact substring of its source posting (never paraphrased), every
concept id an `ideal_outcome` names is traceable to a real alias
actually present in that claim's own text (never copied wholesale from
an unrelated parser trace), and a claim already flagged as a confirmed
defect never has its `ideal_outcome` silently set equal to the
defective result itself (which would quietly launder a known bug into
"the expected answer").
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from gitscore.concepts.registry import default_registry, is_unresolved_concept_id  # noqa: E402
from gitscore.jobs.parsing.segmentation import segment_description  # noqa: E402

CORPUS_PATH = REPO_ROOT / "evaluation" / "m10" / "corpus.json"
SCRIPT_PATH = SCRIPTS_DIR / "evaluate_m10a_realworld.py"

VALID_CATEGORIES = {
    "required_qualifications",
    "preferred_qualifications",
    "responsibilities",
    "learning_opportunities",
    "company_information",
    "legal_administrative",
    "ambiguous",
}

REQUIRED_CLAIM_FIELDS = {"id", "section", "text", "is_requirement", "category_annotation"}


def _load_corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _posting_source_text(posting: dict) -> str:
    path = REPO_ROOT / posting["source_file"]
    return path.read_text(encoding="utf-8-sig")


def _real_segmentation_claims(posting: dict) -> set[str]:
    return {c.text for c in segment_description(_posting_source_text(posting))}


# ---------------------------------------------------------------------------
# Annotation completeness
# ---------------------------------------------------------------------------


def test_every_real_segmentation_claim_has_a_corpus_entry():
    """Every `Claim` the real, unmodified segmenter actually produces for
    each posting must be covered by a corpus entry -- this corpus must
    never silently omit something the parser DID see, even if that
    entry's own annotation records a defect.
    """
    corpus = _load_corpus()
    for posting in corpus["postings"]:
        real_claims = _real_segmentation_claims(posting)
        annotated_texts = {c["text"] for c in posting["claims"]}
        missing = real_claims - annotated_texts
        assert not missing, f"{posting['id']}: segmentation claims with no corpus annotation: {missing}"


def test_entries_annotated_as_never_becoming_a_claim_are_confirmed_absent_from_segmentation():
    """The corpus's own most severe findings (zero-trace claims) assert
    that a specific sentence never becomes a `Claim` at all. Confirm
    this against the real segmenter for every entry whose own `notes`
    field makes that specific claim, rather than trusting the prose.
    """
    corpus = _load_corpus()
    for posting in corpus["postings"]:
        real_claims = _real_segmentation_claims(posting)
        for entry in posting["claims"]:
            notes = entry.get("notes", "")
            if "never becomes a" in notes.lower() or "never even becomes a" in notes.lower():
                assert entry["text"] not in real_claims, (
                    f"{entry['id']}: notes claim this text never becomes a segmentation Claim, "
                    "but it does"
                )


# ---------------------------------------------------------------------------
# Independent semantic labels: schema validity
# ---------------------------------------------------------------------------


def test_every_claim_has_the_required_fields():
    corpus = _load_corpus()
    for posting in corpus["postings"]:
        for entry in posting["claims"]:
            missing = REQUIRED_CLAIM_FIELDS - set(entry)
            assert not missing, f"{entry.get('id', '?')}: missing fields {missing}"


def test_every_claim_uses_one_of_the_seven_named_categories():
    corpus = _load_corpus()
    for posting in corpus["postings"]:
        for entry in posting["claims"]:
            assert entry["category_annotation"] in VALID_CATEGORIES, (
                entry["id"],
                entry["category_annotation"],
            )


def test_is_requirement_is_a_real_boolean_not_a_truthy_string():
    corpus = _load_corpus()
    for posting in corpus["postings"]:
        for entry in posting["claims"]:
            assert isinstance(entry["is_requirement"], bool), entry["id"]


def test_responsibility_category_claims_are_never_marked_is_requirement_true():
    """The explicit Milestone 10A verification-pass correction: a job
    DUTY must never be labeled as an applicant qualification -- checked
    structurally here, not just in prose, so a future edit cannot
    silently reintroduce the metric-inflation risk that correction
    fixed.
    """
    corpus = _load_corpus()
    for posting in corpus["postings"]:
        for entry in posting["claims"]:
            if entry["category_annotation"] == "responsibilities":
                assert entry["is_requirement"] is False, (
                    f"{entry['id']}: a 'responsibilities' claim must never be is_requirement=True"
                )


def test_claim_ids_are_unique_within_each_posting():
    corpus = _load_corpus()
    for posting in corpus["postings"]:
        ids = [c["id"] for c in posting["claims"]]
        assert len(ids) == len(set(ids)), f"{posting['id']}: duplicate claim ids"


# ---------------------------------------------------------------------------
# Source-span fidelity
# ---------------------------------------------------------------------------


def test_every_claim_text_is_an_exact_substring_of_its_posting_source_file():
    """No claim's recorded `text` may be paraphrased, truncated, or
    reconstructed -- it must appear character-for-character in the
    actual source transcription this corpus cites.
    """
    corpus = _load_corpus()
    for posting in corpus["postings"]:
        source_text = _posting_source_text(posting)
        for entry in posting["claims"]:
            assert entry["text"] in source_text, (
                f"{entry['id']}: claim text not found verbatim in {posting['source_file']}"
            )


# ---------------------------------------------------------------------------
# Groundedness of ideal_outcome concept ids -- a concrete, checkable
# stand-in for "not copied wholesale from an unrelated parser trace."
# ---------------------------------------------------------------------------


def _term_from_unresolved_id(concept_id: str) -> str:
    return concept_id.split(":", 1)[1].replace("_", " ")


def test_ideal_outcome_concept_ids_are_traceable_to_the_claims_own_text():
    """Every concept id an `ideal_outcome` names must be groundable in
    THAT claim's own text: either a real registry concept whose
    display name (or an alias) appears in the text, or an
    `unresolved:<term>` placeholder whose encoded term appears in the
    text. This is a concrete, checkable stand-in for "this annotation
    reflects a reading of the posting, not a value pasted in from some
    other claim or from the parser's own (possibly wrong) output" --
    it does not, and cannot, prove the annotation predates any parser
    run (see this module's own docstring).
    """
    registry = default_registry()
    corpus = _load_corpus()
    for posting in corpus["postings"]:
        for entry in posting["claims"]:
            ideal = entry.get("ideal_outcome")
            if not ideal or "alternative_concept_ids" not in ideal:
                continue
            claim_text_lower = entry["text"].lower()
            for concept_id in ideal["alternative_concept_ids"]:
                if is_unresolved_concept_id(concept_id):
                    term = _term_from_unresolved_id(concept_id)
                    assert term in claim_text_lower, (
                        f"{entry['id']}: ideal_outcome names {concept_id!r} but {term!r} "
                        f"does not appear in the claim's own text"
                    )
                else:
                    concept = registry.get(concept_id)
                    assert concept is not None, f"{entry['id']}: {concept_id!r} is not a registered concept"
                    candidate_names = [concept.display_name, *concept.aliases]
                    assert any(re.search(re.escape(name), claim_text_lower, re.IGNORECASE) for name in candidate_names), (
                        f"{entry['id']}: ideal_outcome names {concept_id!r} ({concept.display_name}) "
                        f"but no alias of it appears in the claim's own text"
                    )


# ---------------------------------------------------------------------------
# A confirmed defect must never have its ideal_outcome silently equal
# the defective actual result -- guards against laundering a known bug
# into "the expected answer."
# ---------------------------------------------------------------------------


def test_confirmed_false_positive_entries_never_specify_a_requirement_as_ideal():
    """Every entry whose notes say CONFIRMED LIVE FALSE POSITIVE describes
    `is_requirement: false` text that the real parser turns into a
    scored row. Its ideal_outcome must say no row should exist -- never
    silently match whatever the parser actually produced.
    """
    corpus = _load_corpus()
    for posting in corpus["postings"]:
        for entry in posting["claims"]:
            if "CONFIRMED LIVE FALSE POSITIVE" in entry.get("notes", ""):
                assert entry["is_requirement"] is False
                ideal = entry.get("ideal_outcome") or {}
                assert ideal.get("type") in (
                    "no_requirement_row",
                    "no_scored_requirement",
                    "heading_recognized_not_a_claim",
                ), (
                    f"{entry['id']}: a confirmed false positive's ideal_outcome must assert "
                    f"no requirement row, got {ideal.get('type')!r}"
                )


def test_confirmed_invisible_entries_specify_some_trace_as_ideal_or_fallback():
    """Every entry whose notes say 'zero trace anywhere' must specify, in
    its ideal_outcome or acceptable_fallback, an outcome that is NOT
    itself 'nothing' -- the whole point of flagging it is that
    something should have been visible.
    """
    corpus = _load_corpus()
    for posting in corpus["postings"]:
        for entry in posting["claims"]:
            if "zero trace anywhere" in entry.get("notes", "").lower():
                ideal = entry.get("ideal_outcome")
                fallback = entry.get("acceptable_fallback")
                assert ideal is not None or fallback is not None, (
                    f"{entry['id']}: flagged as a zero-trace defect but specifies no "
                    "ideal_outcome or acceptable_fallback at all"
                )


# ---------------------------------------------------------------------------
# Read-only / structural safeguards, mirroring M9B's own precedent
# ---------------------------------------------------------------------------


def test_evaluate_m10a_realworld_never_writes_to_the_corpus_or_source_files():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import evaluate_m10a_realworld as m10a

    before = {
        CORPUS_PATH: CORPUS_PATH.read_bytes(),
    }
    for posting in _load_corpus()["postings"]:
        path = REPO_ROOT / posting["source_file"]
        before[path] = path.read_bytes()

    m10a.main()

    for path, content in before.items():
        assert path.read_bytes() == content, f"{path} was modified by evaluate_m10a_realworld.main()"


def test_frozen_gold_directories_are_not_imported_by_any_m10a_module():
    """Mirrors `test_m9b_evaluation_integrity.py`'s own equivalent guard:
    this milestone's tooling must never reach into
    `evaluation/gold/`/`evaluation/gold_v1_1/`/`evaluation/m9b/`.
    """
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    forbidden = ("GOLD_JOBS_DIR", "GOLD_CANDIDATES_DIR", "evaluation/gold", "evaluation/m9b")
    for identifier in forbidden:
        assert identifier not in text, (SCRIPT_PATH, identifier)
