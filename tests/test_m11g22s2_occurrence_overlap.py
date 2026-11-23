"""Milestone 11-G22-S2 -- concept occurrence overlap correction (README extractor).

Written BEFORE the production change and run red against readme:v5 first (see
docs/evaluation/MILESTONE_11_G22S2_OCCURRENCE_OVERLAP.md for the red/green record).

Expected outcomes follow the registry's actual identities (checked, not assumed):
  * `framework.react` aliases: react, react.js, reactjs; `framework.react_native`: react native, react-native,
    reactnative. "react" textually matches inside "React Native" / "React-Native" -- the ONLY cross-concept alias
    containment in the registry. Same-concept containments: shell / shell script, psycopg2 / psycopg2-binary,
    react / react.js, express / express.js, nestjs / @nestjs, prisma / @prisma.
  * "javascript" does not contain the word "java"; "pytorch" does not contain the word "torch"; there is no Docker
    Compose concept (the word "Docker" in "Docker Compose" is `infra.docker`).
Semantics under test:
  * SAME-position overlap: the strictly longer alias of another concept wins (the shared 8D.1 rule) -- "React" inside
    "React Native" is never React evidence;
  * an overlap at position A never suppresses a separate occurrence at position B;
  * existing section / negation exclusions, fall-through, one item per concept and alias precedence are unchanged.
"""
from __future__ import annotations

import pytest

from gitscore.concepts.registry import default_registry
from gitscore.evidence.extraction import readme_context as rc
from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION, evidence_from_readme

RE, RN = "framework.react", "framework.react_native"


def _ev(text: str, path: str = "README.md") -> dict:
    return {e.concept_id: e for e in evidence_from_readme("o", "r", text, path)}


def _concepts(text: str) -> set[str]:
    return set(_ev(text))


PRIMARY = "A React Native app. The web dashboard uses React."


# ---- 1-6: React Native / React ordering and placement ---------------------------------------------------------------
def test_react_native_then_independent_react_recovers_react():
    ev = _ev(PRIMARY)
    assert set(ev) == {RN, RE}
    assert "uses React" in ev[RE].raw_observation


def test_independent_react_then_react_native():
    assert _concepts("The web dashboard uses React. A React Native app too.") == {RE, RN}


def test_react_native_alone_is_not_react():
    assert _concepts("A React Native app.") == {RN}


def test_react_alone():
    assert _concepts("Built with React.") == {RE}


def test_two_separate_react_mentions_give_one_item_from_the_first():
    ev = _ev("Built with React. More React later.")
    assert set(ev) == {RE} and "Built with React" in ev[RE].raw_observation


def test_react_native_and_react_in_distinct_paragraphs():
    assert _concepts("# app\n\nA React Native app.\n\nThe web dashboard uses React.\n") == {RN, RE}


# ---- 7-8: sections ---------------------------------------------------------------------------------------------------
def test_mentions_in_separate_atx_sections():
    assert _concepts("# app\n\n## Mobile\n\nReact Native client.\n\n## Web\n\nReact dashboard.\n") == {RN, RE}


def test_mentions_surrounding_a_setext_heading():
    assert _concepts("Mobile\n------\n\nReact Native client.\n\nWeb\n---\n\nReact dashboard.\n") == {RN, RE}


# ---- 9-12: overlapping aliases ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text", ["Uses React Native.", "Uses react-native.", "Uses ReactNative."])
def test_same_position_overlap_resolves_to_the_longer_alias(text):
    assert _concepts(text) == {RN}


def test_hyphenated_react_native_then_independent_react():
    assert _concepts("A React-Native app; the admin panel uses React.") == {RN, RE}


def test_longer_alias_wins_only_at_its_own_position():
    ev = _ev("Web: React. Mobile: React Native.")
    assert set(ev) == {RE, RN}
    assert "Web: React" in ev[RE].raw_observation


@pytest.mark.parametrize("text,concept,alias", [
    ("A React.js front end; see the ReactJS docs.", RE, "react"),       # alias precedence: 'react' first
    ("Helper shell script for deploys.", "language.shell", "shell"),
    ("An Express.js server.", "framework.express", "express"),
    ("Depends on psycopg2-binary.", "database.postgresql", "psycopg2"),
])
def test_two_aliases_of_one_concept_give_one_item_with_existing_precedence(text, concept, alias):
    ev = evidence_from_readme("o", "r", text, "README.md")
    assert [e.concept_id for e in ev] == [concept]
    assert ev[0].raw_observation.startswith(f"README mentions '{alias}':")


def test_two_aliases_of_different_concepts():
    assert _concepts("An Express.js server backed by Redis.") == {"framework.express", "database.redis"}


# ---- 13-16: registry identities -------------------------------------------------------------------------------------
def test_java_versus_javascript():
    assert _concepts("Written in JavaScript.") == {"language.javascript"}
    assert _concepts("Java service with a JavaScript UI.") == {"language.java", "language.javascript"}


def test_docker_versus_docker_compose():
    assert _concepts("Run it with Docker Compose.") == {"infra.docker"}


def test_pytorch_versus_torch():
    ev = evidence_from_readme("o", "r", "A PyTorch model; it calls torch.compile.", "README.md")
    assert [e.concept_id for e in ev] == ["ml.framework.pytorch"]
    assert ev[0].raw_observation.startswith("README mentions 'pytorch':")


def test_express_versus_express_js():
    assert _concepts("Express.js routes, plus an Express error handler.") == {"framework.express"}


# ---- 17-21: exclusions, negation, repetition, deduplication -----------------------------------------------------------
def test_earlier_excluded_mention_then_valid_mention():
    text = "# app\n\n## Related\n\n- React Native Paper\n\n## Usage\n\nThe dashboard uses React.\n"
    assert _concepts(text) == {RE}


def test_earlier_valid_mention_then_excluded_mention():
    assert _concepts("# app\n\nBuilt with React.\n\n## Related\n\n- React Native Paper\n") == {RE}


@pytest.mark.parametrize("text", [
    "We do not use React Native.\n\nThe mobile client is a plain native build; the separate web dashboard uses React.",
    "React Native is not supported. The web app uses React."])
def test_negated_mention_then_explicit_use(text):
    assert _concepts(text) == {RE}


def test_existing_negation_window_is_unchanged():
    # The 8D.3 adjacency cue looks 60 characters back, across sentences: here "do not use" still precedes the later
    # "React" inside that window, so that occurrence stays excluded. S2 does not change negation handling (pinned).
    assert _concepts("We do not use React Native. The web app uses React.") == set()


# ---- G22-S2 Gate 1 decision: a negated React Native mention never yields React (accepted v6 behaviour) -------------
# The 8D.3 FOLLOWING-cue window starts at a match's END, so "React" (5 chars) and "React Native" (12 chars) at the same
# position look at windows offset by 7 characters. With the cue in that 7-character tail, the React Native mention is
# excluded but the "React" inside it is not: readme:v5 then emitted React evidence whose only source was the words
# "React Native". readme:v6 applies same-position precedence first, so that occurrence is never React evidence.
NEGATED_RN_PLAIN = "React Native is not supported."
NEGATED_RN_TAIL = "A React Native client. " + "y" * 21 + " and it is not supported."


def test_negated_react_native_cue_sits_in_the_seven_character_tail():
    start = NEGATED_RN_TAIL.index("React")
    react_following = NEGATED_RN_TAIL[start + 5: start + 5 + 60]
    rn_following = NEGATED_RN_TAIL[start + 12: start + 12 + 60]
    assert "is not supported" not in react_following and "is not supported" in rn_following
    assert rc._ADJACENCY_RADIUS == 60                       # the preserved 8D.3 window


@pytest.mark.parametrize("text", [NEGATED_RN_PLAIN, NEGATED_RN_TAIL])
def test_negated_react_native_gives_neither_react_nor_react_native(text):
    for t in (text, text.replace("\n", "\r\n")):
        assert _concepts(t) == set()


@pytest.mark.parametrize("text", [NEGATED_RN_PLAIN, NEGATED_RN_TAIL])
def test_negated_react_native_then_independent_react_still_recovers_react(text):
    ev = _ev(text + " The web dashboard uses React.")
    assert set(ev) == {RE}
    assert "dashboard uses React" in ev[RE].raw_observation


def test_readme_v5_pin_reproduces_the_historical_negated_react_native_leak():
    _scripts_on_path()
    import readme_v5_pin
    with readme_v5_pin.pinned():
        ev = _ev(NEGATED_RN_TAIL)
        assert set(ev) == {RE} and "React Native client" in ev[RE].raw_observation   # v5's incorrect React item
        assert _concepts(NEGATED_RN_PLAIN) == set()
    assert _concepts(NEGATED_RN_TAIL) == set()


def test_repeated_react_native_mentions_never_invent_react():
    assert _concepts("A React Native app. Another React Native screen. React Native everywhere.") == {RN}


def test_multiple_valid_mentions_give_one_item_per_concept():
    ev = evidence_from_readme("o", "r", "A React Native app. The dashboard uses React. React 18 everywhere.",
                              "README.md")
    assert sorted(e.concept_id for e in ev) == [RE, RN]


# ---- 22-24: provenance, line endings, section exclusions -----------------------------------------------------------------
def test_recovered_item_keeps_original_snippet_alias_and_path():
    (item,) = [e for e in evidence_from_readme("o", "r", PRIMARY, "docs/README.md") if e.concept_id == RE]
    assert item.file_path == "docs/README.md"
    assert item.raw_observation.startswith("README mentions 'react': ...")
    assert "dashboard uses React" in item.raw_observation
    assert item.extractor_version == EXTRACTOR_VERSION


@pytest.mark.parametrize("text", [PRIMARY, "# app\n\nA React Native app.\n\nThe web dashboard uses React.\n",
                                  "Mobile\n------\n\nReact Native client.\n\nWeb\n---\n\nReact dashboard.\n"])
def test_lf_and_crlf_are_equivalent(text):
    crlf = text.replace("\n", "\r\n")
    assert _concepts(crlf) == _concepts(text) == {RN, RE}


@pytest.mark.parametrize("related", ["## Related projects\n", "Related projects\n----------------\n"])
def test_atx_and_setext_section_exclusions_still_apply(related):
    text = f"# app\n\n{related}\n- React Native Paper\n\nDevelopment\n-----------\n\nThe dashboard uses React.\n"
    assert _concepts(text) == {RE}
    assert rc.build_context(text).enclosing_heading(text.index("Paper")) == "related projects"


# ---- 25: every README-safe alias still extractable, also after an overlapping mention ---------------------------------
@pytest.mark.parametrize("prefix", ["", "A React Native app. "])
def test_every_readme_safe_alias_remains_extractable(prefix):
    reg = default_registry()
    for c in reg.all_concepts():
        for alias in c.readme_safe_aliases():
            got = _concepts(f"# demo\n\n{prefix}This project is built with {alias}.\n")
            assert c.concept_id in got, (prefix, c.concept_id, alias)


# ---- version ----------------------------------------------------------------------------------------------------------
def test_extractor_version_marks_the_overlap_correction():
    assert EXTRACTOR_VERSION == "readme:v6"


# ---- historical v5 pin and the recorded real-pipeline comparison ----------------------------------------------------
def _scripts_on_path():
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for p in (root / "scripts", root / "scripts" / "evaluation_lib"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    return root


def test_readme_v5_pin_restores_exact_v5_selection_and_unwinds():
    _scripts_on_path()
    import readme_v5_pin
    from gitscore.evidence.extraction import readme as readme_mod
    production = readme_mod._inside_longer_other_concept_match
    with readme_v5_pin.pinned():
        assert readme_mod.EXTRACTOR_VERSION == "readme:v5"
        assert _concepts(PRIMARY) == {RN}                       # the v5 loss, reproduced exactly
    try:
        with readme_v5_pin.pinned():
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert readme_mod.EXTRACTOR_VERSION == "readme:v6" and readme_mod._inside_longer_other_concept_match is production
    assert _concepts(PRIMARY) == {RN, RE}


def test_readme_v4_pin_still_reproduces_v4_from_v6():
    _scripts_on_path()
    import readme_v4_pin
    from gitscore.evidence.extraction import readme as readme_mod
    setext = "# x\n\n## Related projects\n\n- ripgrep (Rust)\n\nDevelopment\n-----------\n\nWritten in Rust.\n"
    with readme_v4_pin.pinned():
        assert readme_mod.EXTRACTOR_VERSION == "readme:v4"
        assert _concepts(PRIMARY) == {RN} and "language.rust" not in _concepts(setext)
    assert readme_mod.EXTRACTOR_VERSION == "readme:v6" and "language.rust" in _concepts(setext)


def _report():
    import json
    root = _scripts_on_path()
    return json.loads((root / "evaluation" / "m11g22s2" / "occurrence_overlap_comparison.json").read_text(encoding="utf-8"))


def test_recorded_real_pipeline_comparison():
    report = _report()
    assert report["versions"] == {"before": "readme:v5", "after": "readme:v6"}
    assert all(not (v["added"] or v["removed"] or v["provenance_moved"]) for v in report["fixtures_8c"].values())
    assert report["matrix_8c_changes"] == {} and report["undefined_score_changes"] == []
    assert report["capability_identical"] is True and report["g22r_controls"]["changed_controls"] == []
    dev = report["labelled_sets"]["g22r5_dev"]
    assert dev["outcome_changes"] == [["m11g22r5-dev-035", "framework.react", "use", "missed", "true_supported"]]
    for name, s in report["labelled_sets"].items():
        assert s["false_supported"][1] <= s["false_supported"][0], name          # no new false SUPPORTED
        assert s["true_supported"][1] >= s["true_supported"][0], name            # no genuine evidence lost
        assert not s["readme_items_newly_excluded"] and not s["provenance_moved"], name
        if name != "g22r5_dev":
            assert not (s["readme_items_recovered"] or s["match_status_changes"]), name


def test_real_pipeline_comparison_reproduces():
    import json
    _scripts_on_path()
    import evaluate_m11g22s2_occurrence_overlap as s2
    import readme_v5_pin
    v6, inv6 = s2.s1.measure(), s2.react_inventory()
    with readme_v5_pin.pinned():
        v5, inv5 = s2.s1.measure(), s2.react_inventory()
    live = s2.s1.compare(v5, v6)
    recorded = _report()
    assert json.loads(json.dumps(live)) == {k: v for k, v in recorded.items() if k not in ("note", "react_occurrences_8c")} \
        | {"note": live["note"]}
    assert {k: [v["readme_items"] for v in (inv5[k], inv6[k])] for k in inv6} == \
        {k: [v["readme_items_v5"], v["readme_items_v6"]] for k, v in recorded["react_occurrences_8c"].items()}
