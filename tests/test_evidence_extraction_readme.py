"""Milestone 5D / 5D.1 -- gitscore.evidence.extraction.readme."""
from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION, evidence_from_readme
from gitscore.evidence.types import ConfidenceLevel, EvidenceType


def test_one_concept_mentioned_produces_one_evidence_item():
    evidence = evidence_from_readme("octocat", "repo", "Built with PostgreSQL.", "README.md")

    assert len(evidence) == 1
    item = evidence[0]
    assert item.concept_id == "database.postgresql"
    assert item.evidence_type == EvidenceType.README
    assert item.confidence == ConfidenceLevel.MODERATE
    assert item.extractor_version == EXTRACTOR_VERSION
    assert item.file_path == "README.md"


def test_multiple_concepts_each_produce_one_evidence_item():
    text = "Built using PostgreSQL and Next.js, deployed with Docker."
    evidence = evidence_from_readme("octocat", "repo", text, "README.md")

    concept_ids = {item.concept_id for item in evidence}
    # Milestone 5D.1: "js" is excluded from README matching (it's marked
    # `readme_unsafe_aliases` on language.javascript), so "Next.js" no
    # longer incidentally produces JavaScript evidence -- only the
    # concepts actually, unambiguously mentioned.
    assert concept_ids == {
        "database.postgresql",
        "framework.nextjs",
        "infra.docker",
    }


def test_case_insensitive_matching():
    evidence = evidence_from_readme("octocat", "repo", "POSTGRESQL powers this app.", "README.md")
    assert [item.concept_id for item in evidence] == ["database.postgresql"]


def test_alias_matching():
    evidence = evidence_from_readme("octocat", "repo", "Uses torch for training.", "README.md")
    assert [item.concept_id for item in evidence] == ["ml.framework.pytorch"]


def test_boundary_aware_matching_does_not_match_inside_another_word():
    # "golang" must not match inside "mangolangley" -- boundary-aware,
    # not substring, matching. ("go"/"c" are readme_unsafe and would
    # produce no evidence here regardless -- see the bare-go/bare-c
    # tests below for that separate guarantee.)
    evidence = evidence_from_readme("octocat", "repo", "A mangolangley vector library.", "README.md")
    assert evidence == []


def test_bare_c_never_matches_in_readme_even_standalone():
    # Documented limitation (registry.py's language.c entry): "c"'s only
    # alias is a single letter, which has no safe deterministic form in
    # prose -- readme_safe_aliases() is empty for this concept, so it
    # never produces README evidence, even for a standalone "C".
    evidence = evidence_from_readme("octocat", "repo", "Written in C for portability.", "README.md")
    assert evidence == []


def test_no_matches_produces_no_evidence():
    evidence = evidence_from_readme("octocat", "repo", "Just a plain description.", "README.md")
    assert evidence == []


def test_readme_absent_produces_no_evidence():
    assert evidence_from_readme("octocat", "repo", None, None) == []


def test_matched_concept_appears_only_once_even_with_repeated_mentions():
    text = "PostgreSQL is great. We really love PostgreSQL. Postgres forever."
    evidence = evidence_from_readme("octocat", "repo", text, "README.md")
    assert len(evidence) == 1


def test_bare_next_no_longer_matches_ordinary_english():
    # Milestone 5D.1 fix (was a documented false positive in Milestone
    # 5D, observed on Jango1324/Arduino-Based-Media-Player): "next" is
    # now `readme_unsafe_aliases` on framework.nextjs, so ordinary
    # English like "Next Track" no longer produces evidence. It remains
    # a valid resolve_concept() alias for structured dependency
    # resolution (package.json) -- see registry.py's framework.nextjs
    # entry.
    evidence = evidence_from_readme("octocat", "repo", "Play / Pause * Next Track", "README.md")
    assert evidence == []


def test_next_steps_does_not_match_nextjs():
    evidence = evidence_from_readme("octocat", "repo", "Next steps: add tests and docs.", "README.md")
    assert evidence == []


def test_uses_nextjs_still_matches_nextjs():
    evidence = evidence_from_readme("octocat", "repo", "Uses Next.js for the frontend.", "README.md")
    assert [item.concept_id for item in evidence] == ["framework.nextjs"]


def test_nextjs_mention_does_not_incidentally_produce_javascript_evidence():
    # The "js" suffix of "Next.js" must not, by itself, count as an
    # independent JavaScript mention (language.javascript's "js" alias is
    # readme_unsafe -- only the full word "javascript" is README-safe).
    evidence = evidence_from_readme("octocat", "repo", "Uses Next.js for the frontend.", "README.md")
    concept_ids = {item.concept_id for item in evidence}
    assert "language.javascript" not in concept_ids


def test_independent_javascript_mention_still_matches():
    evidence = evidence_from_readme("octocat", "repo", "Written in JavaScript.", "README.md")
    assert [item.concept_id for item in evidence] == ["language.javascript"]


def test_bare_go_no_longer_matches_ordinary_english_i_go_for():
    # Milestone 5D.1 fix (was a documented false positive in Milestone
    # 5D, observed on torvalds/1590A and karpathy/autoresearch): "go" is
    # now `readme_unsafe_aliases` on language.go. Bare "Go" in prose is
    # genuinely ambiguous with the ordinary English verb -- this milestone
    # chooses precision over a guess (no fuzzy/NLP inference), so bare
    # "Go" mentions no longer produce evidence at all; "golang" remains a
    # README-safe, unambiguous alternative form.
    evidence = evidence_from_readme(
        "octocat", "repo", "I go for large components when etching boards.", "README.md"
    )
    assert evidence == []


def test_bare_go_no_longer_matches_ordinary_english_let_it_go():
    evidence = evidence_from_readme("octocat", "repo", "Just let it go and ship the release.", "README.md")
    assert evidence == []


def test_written_in_go_bare_form_is_a_documented_limitation_not_detected():
    # See module docstring / docs/ARCHITECTURE.md §15.6: bare "Go" cannot
    # be safely distinguished from the English verb by literal,
    # deterministic matching, so this intentionally produces no evidence
    # -- language-stats extraction (languages.py) is the practical source
    # of Go evidence instead.
    evidence = evidence_from_readme("octocat", "repo", "Written in Go.", "README.md")
    assert evidence == []


def test_golang_unambiguous_form_still_matches():
    evidence = evidence_from_readme("octocat", "repo", "Written in Golang.", "README.md")
    assert [item.concept_id for item in evidence] == ["language.go"]


def test_observation_snippet_is_bounded_not_the_whole_readme():
    huge_text = ("padding " * 500) + "Built with PostgreSQL." + ("padding " * 500)
    evidence = evidence_from_readme("octocat", "repo", huge_text, "README.md")

    assert len(evidence) == 1
    assert len(evidence[0].raw_observation) < len(huge_text)
    assert "postgresql" in evidence[0].raw_observation.lower()
