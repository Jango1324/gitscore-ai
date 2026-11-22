"""Milestone 11-G22-S1 -- setext heading section boundaries (structural Markdown fix).

Written BEFORE the production change and run red against readme:v4 first (see
docs/evaluation/MILESTONE_11_G22S1_SETEXT_HEADING_BOUNDARIES.md for the red/green record).

Expected outcomes follow CommonMark heading semantics, not any particular implementation:
  * a setext heading is a paragraph (one or more non-blank text lines) immediately followed by an underline of '='
    (level 1) or '-' (level 2) characters, indented at most three spaces, with only trailing whitespace;
  * a '---' line after a blank line, after a list item or after a blockquote is a thematic break / not an underline;
  * lines inside fenced code blocks are never headings;
  * a section runs from its heading to the next heading of any level (the existing 8D.3 "nearest preceding heading"
    rule, unchanged) -- so a setext heading ENDS a preceding denylisted section, and a setext denylisted heading
    STARTS one.
The 8D.3 heading denylist itself, the adjacency cues and every alias are unchanged.
"""
from __future__ import annotations

import pytest

from gitscore.evidence.extraction import readme_context as rc
from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION, evidence_from_readme


def _concepts(text: str) -> set[str]:
    return {e.concept_id for e in evidence_from_readme("o", "r", text, "README.md")}


def _heading_at(text: str, needle: str, nth: int = 0) -> str | None:
    pos = -1
    for _ in range(nth + 1):
        pos = text.index(needle, pos + 1)
    return rc.build_context(text).enclosing_heading(pos)


def _crlf(text: str) -> str:
    return text.replace("\n", "\r\n")


ATX_RELATED_THEN_SETEXT_DEV = ("# grepx\n\n## Related projects\n\nOther projects mentioned here: ripgrep (Rust).\n\n"
                               "Development\n-----------\n\nOur implementation uses Python.\n")
SETEXT_RELATED_THEN_ATX_DEV = ("# grepx\n\nRelated projects\n----------------\n\n- ripgrep (Rust)\n\n## Development\n\n"
                               "Our implementation uses Python.\n")


# ---- 1, 2: setext H1 and H2 are headings ---------------------------------------------------------------------
@pytest.mark.parametrize("underline", ["================", "----------------", "===", "-", "  ---  "])
def test_setext_related_heading_starts_an_excluded_section(underline):
    text = f"# tool\n\nA grep in Go.\n\nRelated projects\n{underline}\n\n- ripgrep (Rust)\n"
    assert _heading_at(text, "ripgrep") == "related projects"
    assert "language.rust" not in _concepts(text)


# ---- 3, 6: ATX excluded section followed by a setext section ----------------------------------------------------
def test_atx_related_followed_by_setext_development_recovers_development_evidence():
    assert _heading_at(ATX_RELATED_THEN_SETEXT_DEV, "ripgrep") == "related projects"
    assert _heading_at(ATX_RELATED_THEN_SETEXT_DEV, "Our implementation") == "development"
    got = _concepts(ATX_RELATED_THEN_SETEXT_DEV)
    assert "language.python" in got          # recovered: Development is a new section
    assert "language.rust" not in got        # Related projects stays excluded


# ---- 4: setext excluded section followed by ATX ------------------------------------------------------------------
def test_setext_related_followed_by_atx_development():
    assert _heading_at(SETEXT_RELATED_THEN_ATX_DEV, "ripgrep") == "related projects"
    assert _heading_at(SETEXT_RELATED_THEN_ATX_DEV, "Our implementation") == "development"
    got = _concepts(SETEXT_RELATED_THEN_ATX_DEV)
    assert "language.python" in got and "language.rust" not in got


# ---- 5: section policy unchanged: genuine-sounding text inside an excluded section stays excluded -------------------
@pytest.mark.parametrize("heading", ["## Related projects\n", "Related projects\n================\n",
                                     "Related projects\n----------------\n"])
def test_mentions_inside_an_excluded_section_remain_excluded(heading):
    text = f"# x\n\n{heading}\nThis project is written in Rust.\n"
    assert "language.rust" not in _concepts(text)


# ---- 7: consecutive setext headings ----------------------------------------------------------------------------
def test_consecutive_setext_headings():
    text = "Related projects\n================\nDevelopment\n-----------\n\nThis tool is written in Rust.\n"
    assert _heading_at(text, "Development") == "development"
    assert _heading_at(text, "This tool") == "development"
    assert "language.rust" in _concepts(text)


# ---- 8: thematic breaks are not headings ---------------------------------------------------------------------------
@pytest.mark.parametrize("brk", ["\n---\n", "\n***\n", "\n___\n", "\n- - -\n", "\n----------\n"])
def test_horizontal_rule_after_a_blank_line_is_not_a_heading(brk):
    text = f"# x\n\n## Related projects\n\n- ripgrep (Rust)\n{brk}\nThis tool is written in Rust.\n"
    assert _heading_at(text, "This tool") == "related projects"
    assert "language.rust" not in _concepts(text)


@pytest.mark.parametrize("block", ["- ripgrep (Rust)\n---\n", "> ripgrep (Rust)\n---\n", "* ripgrep (Rust)\n===\n"])
def test_dash_or_equals_line_after_a_list_item_or_blockquote_is_not_an_underline(block):
    text = f"# x\n\n## Related projects\n\n{block}\nThis tool is written in Rust.\n"
    assert _heading_at(text, "This tool") == "related projects"
    assert "language.rust" not in _concepts(text)


def test_blank_line_between_text_and_dashes_is_not_an_underline():
    text = "# x\n\n## Related projects\n\n- ripgrep (Rust)\n\nDevelopment\n\n-----------\n\nWritten in Rust.\n"
    assert _heading_at(text, "Written in") == "related projects"
    assert "language.rust" not in _concepts(text)


def test_underline_indented_four_spaces_is_not_an_underline():
    text = "# x\n\n## Related projects\n\n- ripgrep (Rust)\n\nDevelopment\n    -----------\n\nWritten in Rust.\n"
    assert _heading_at(text, "Written in") == "related projects"


# ---- 9, 10: fenced code -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("fenced", ["Development\n-----------", "Development\n===========", "# Development",
                                    "## Development"])
def test_heading_shaped_lines_inside_fenced_code_are_ignored(fenced):
    text = f"# x\n\n## Related projects\n\n```\n{fenced}\n```\n\nThis tool is written in Rust.\n"
    assert _heading_at(text, "This tool") == "related projects"
    assert "language.rust" not in _concepts(text)


def test_setext_heading_after_a_closed_fence_is_recognised():
    text = ("# x\n\n## Related projects\n\n```\nripgrep --version\n```\n\nDevelopment\n-----------\n\n"
            "This tool is written in Rust.\n")
    assert _heading_at(text, "This tool") == "development"
    assert "language.rust" in _concepts(text)


# ---- 11: blank lines around sections ---------------------------------------------------------------------------
def test_boundaries_hold_across_extra_blank_lines():
    text = ("# x\n\n\n## Related projects\n\n\n- ripgrep (Rust)\n\n\n\nDevelopment\n-----------\n\n\n\n"
            "This tool is written in Rust.\n\n\n")
    assert _heading_at(text, "ripgrep") == "related projects"
    assert _heading_at(text, "This tool") == "development"
    assert "language.rust" in _concepts(text)


# ---- 12: mixed ATX / setext levels, multi-line setext text, emphasis and trailing colon -----------------------------
def test_mixed_atx_and_setext_levels():
    text = ("grepx\n=====\n\n## Related projects\n\n- ripgrep (Rust)\n\nUsage\n-----\n\nRun it.\n\n### Internals\n\n"
            "Credits\n=======\n\n- Thanks to the Kubernetes community.\n\nBuilding\n--------\n\nRequires Python 3.11.\n")
    assert _heading_at(text, "grepx") == "grepx"
    assert _heading_at(text, "ripgrep") == "related projects"
    assert _heading_at(text, "Run it") == "usage"
    assert _heading_at(text, "Thanks to") == "credits"
    assert _heading_at(text, "Requires") == "building"
    got = _concepts(text)
    assert "language.python" in got
    assert "language.rust" not in got and "infra.kubernetes" not in got


def test_multi_line_setext_heading_text_is_one_heading():
    text = "# x\n\n## Related projects\n\n- ripgrep (Rust)\n\nDevelopment\nnotes\n-----\n\nWritten in Rust.\n"
    assert _heading_at(text, "Written in") == "development notes"
    assert "language.rust" in _concepts(text)


@pytest.mark.parametrize("label", ["**Related projects**", "Related projects:", "_Acknowledgements_", "  Credits  "])
def test_setext_heading_text_is_normalised_like_atx(label):
    text = f"# x\n\nA tool.\n\n{label}\n----------------\n\n- Thanks to the Kubernetes community.\n"
    assert "infra.kubernetes" not in _concepts(text)


# ---- 13: source positions and snippets preserved -------------------------------------------------------------------
def test_recovered_evidence_keeps_original_source_snippet_and_path():
    ev = [e for e in evidence_from_readme("o", "r", ATX_RELATED_THEN_SETEXT_DEV, "docs/README.md")
          if e.concept_id == "language.python"]
    assert len(ev) == 1
    assert ev[0].file_path == "docs/README.md"
    assert "Our implementation uses Python" in ev[0].raw_observation
    assert ev[0].raw_observation.startswith("README mentions 'python': ...")


# ---- 14: existing ATX exclusions unchanged -------------------------------------------------------------------------
@pytest.mark.parametrize("heading", sorted(rc.NON_IMPLEMENTATION_SECTION_HEADINGS))
def test_existing_atx_section_exclusions_are_unchanged(heading):
    text = f"# x\n\n## {heading}\n\n- Some project built with Rust.\n"
    assert "language.rust" not in _concepts(text)


def test_atx_only_documents_have_the_same_heading_index_as_before():
    text = "# a\n\n## Related\n\nRust.\n\n### Usage\n\n```\n# not a heading\n```\n\n#### Credits\n\nPython.\n"
    ctx = rc.build_context(text)
    for needle, expected in (("Rust.", "related"), ("not a heading", "usage"), ("Python.", "credits")):
        assert ctx.enclosing_heading(text.index(needle)) == expected


# ---- 15: occurrences evaluated independently --------------------------------------------------------------------
def test_invalid_then_valid_occurrence_selects_the_valid_one():
    text = "# x\n\nRelated projects\n----------------\n\n- ripgrep (Rust)\n\nDevelopment\n-----------\n\nRust everywhere.\n"
    (ev,) = [e for e in evidence_from_readme("o", "r", text, "README.md") if e.concept_id == "language.rust"]
    assert "Rust everywhere" in ev.raw_observation and _heading_at(text, "Rust everywhere") == "development"


def test_valid_then_invalid_occurrence_keeps_the_valid_one():
    text = "# x\n\nWritten in Rust.\n\nRelated projects\n----------------\n\n- ripgrep (Rust)\n"
    (ev,) = [e for e in evidence_from_readme("o", "r", text, "README.md") if e.concept_id == "language.rust"]
    assert "Written in Rust" in ev.raw_observation


# ---- 16: CRLF and LF are equivalent --------------------------------------------------------------------------------
@pytest.mark.parametrize("text", [ATX_RELATED_THEN_SETEXT_DEV, SETEXT_RELATED_THEN_ATX_DEV,
                                  "Related projects\n================\nDevelopment\n-----------\n\nWritten in Rust.\n"])
def test_crlf_and_lf_give_the_same_sections_and_evidence(text):
    crlf = _crlf(text)
    assert _concepts(crlf) == _concepts(text)
    lf_heads = [rc.build_context(text).enclosing_heading(i) for i in range(len(text))]
    crlf_ctx = rc.build_context(crlf)
    crlf_heads = [crlf_ctx.enclosing_heading(i) for i, ch in enumerate(crlf) if ch != "\r"]
    assert crlf_heads == lf_heads


# ---- 17, 18: deduplication and no unrelated concepts ------------------------------------------------------------------
def test_one_item_per_concept_and_no_unrelated_concepts():
    text = ("# x\n\n## Related projects\n\n- ripgrep (Rust)\n- fd (Rust)\n\nDevelopment\n-----------\n\n"
            "Written in Rust. The Rust code lives in `src/`. Rust 1.80 is required.\n")
    ev = evidence_from_readme("o", "r", text, "README.md")
    assert [e.concept_id for e in ev] == ["language.rust"]


def test_setext_heading_text_itself_is_not_new_evidence():
    # The heading words are ordinary text; only registry aliases ever become evidence.
    text = "# x\n\nOverview\n========\n\nA small tool.\n"
    assert _concepts(text) == set()


# ---- version ----------------------------------------------------------------------------------------------------------
def test_extractor_version_marks_the_setext_boundary_change():
    assert EXTRACTOR_VERSION == "readme:v5"


# ---- historical reproduction pin and the recorded real-pipeline comparison ----------------------------------------
def test_readme_v4_pin_restores_exact_v4_behaviour_and_unwinds():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "evaluation_lib"))
    import readme_v4_pin
    from gitscore.evidence.extraction import readme as readme_mod
    assert readme_v4_pin.reproduces_v4()
    with readme_v4_pin.pinned():
        assert readme_mod.EXTRACTOR_VERSION == "readme:v4"
        # readme:v4 behaviour: the setext Development section stays inside 'related projects'
        assert "language.python" not in _concepts(ATX_RELATED_THEN_SETEXT_DEV)
        assert {e.extractor_version for e in evidence_from_readme("o", "r", "Built with Rust.", "README.md")} == \
            {"readme:v4"}
    assert readme_mod.EXTRACTOR_VERSION == "readme:v5" and rc.build_context("x").__class__ is rc.ReadmeContext
    assert "language.python" in _concepts(ATX_RELATED_THEN_SETEXT_DEV)


def test_recorded_real_pipeline_comparison():
    import json
    from pathlib import Path
    report = json.loads((Path(__file__).resolve().parents[1] / "evaluation" / "m11g22s1" /
                         "setext_boundary_comparison.json").read_text(encoding="utf-8"))
    assert report["versions"] == {"before": "readme:v4", "after": "readme:v5"}
    # frozen 8c: no evidence, provenance, status, score or undefined-score change; G19 capability identical
    assert all(not (v["added"] or v["removed"] or v["provenance_moved"]) for v in report["fixtures_8c"].values())
    assert report["matrix_8c_changes"] == {} and report["undefined_score_changes"] == []
    assert report["capability_identical"] is True and report["g22r_controls"]["changed_controls"] == []
    dev = report["labelled_sets"]["g22r5_dev"]
    assert dev["outcome_changes"] == [
        ["m11g22r5-dev-037", "language.rust", "use", "missed", "true_supported"],
        ["m11g22r5-dev-038", "language.rust", "reference", "false_supported", "true_not_supported"]]
    for name, s in report["labelled_sets"].items():
        if name not in ("g22r5_dev", "g22r5_fresh"):
            assert not (s["readme_items_recovered"] or s["readme_items_newly_excluded"] or s["provenance_moved"]
                        or s["match_status_changes"]), name


def test_real_pipeline_comparison_reproduces():
    import json
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for p in (root / "scripts", root / "scripts" / "evaluation_lib"):
        sys.path.insert(0, str(p))
    import evaluate_m11g22s1_setext_boundaries as s1
    import readme_v4_pin
    v5 = s1.measure()
    with readme_v4_pin.pinned():
        v4 = s1.measure()
    live = json.loads(json.dumps(s1.compare(v4, v5)))
    assert live == json.loads((root / "evaluation" / "m11g22s1" / "setext_boundary_comparison.json")
                              .read_text(encoding="utf-8"))
