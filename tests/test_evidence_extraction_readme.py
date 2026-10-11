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


# ---------------------------------------------------------------------------
# Milestone 8D.3 -- evidence attribution (section-heading + adjacency-cue
# context filtering, gitscore.evidence.extraction.readme_context)
# ---------------------------------------------------------------------------


def test_known_false_positive_regression_karpathy_llm_c_notable_forks():
    # The milestone's driving real-world case: a trimmed, faithful
    # reproduction of karpathy/llm.c's actual "## notable forks" section
    # (evaluation/fixtures/candidates/karpathy.json), which lists OTHER
    # people's separate, externally-linked ports -- including three C++
    # mentions -- none of which are evidence that llm.c itself uses C++
    # (GitHub's own language stats put C++ at ~3.5% of llm.c's bytes,
    # below languages.py's 5% significance floor).
    text = (
        "# llm.c\n\n"
        "LLMs in simple, pure C/CUDA with no need for 245MB of PyTorch. "
        "I'd like this repo to only maintain C and CUDA code. Ports to "
        "other languages or repos are very welcome, but should be done "
        "in separate repos.\n\n"
        "## notable forks\n\n"
        "- CUDA C++\n"
        "  - [llm.cpp](https://example.com) by @someone: a port of this "
        "project using the CUDA C++ Core Libraries\n\n"
        "- C++/CUDA\n"
        "  - [llm.cpp](https://example.com) by @someone: a port of this "
        "project using Eigen, supporting CPU/CUDA.\n\n"
        "- WebGPU C++\n"
        "  - [gpu.cpp](https://example.com) by @someone: a library for "
        "portable GPU compute in C++ using native WebGPU.\n"
    )
    evidence = evidence_from_readme("karpathy", "llm.c", text, "README.md")
    concept_ids = {item.concept_id for item in evidence}
    assert "language.cpp" not in concept_ids
    # The genuine, non-forks-section mentions survive.
    assert "platform.cuda" in concept_ids
    assert "ml.framework.pytorch" in concept_ids


def test_cpp_mentioned_outside_any_excluded_section_still_matches():
    # Positive control: the same alias, the same concept, but as a
    # genuine top-level implementation statement -- must still produce
    # evidence. Proves the fix is about WHERE a mention sits, not a
    # blacklist on "C++" itself.
    evidence = evidence_from_readme("octocat", "repo", "Written in C++ for performance.", "README.md")
    assert [item.concept_id for item in evidence] == ["language.cpp"]


def test_genuine_mention_elsewhere_survives_even_when_forks_section_also_matches():
    # If the SAME alias also appears legitimately outside the excluded
    # section, that occurrence must still produce evidence -- excluding
    # one occurrence must not discard the whole concept.
    text = (
        "Written in C++ for the core engine.\n\n"
        "## notable forks\n\n"
        "- a C++ port by someone else\n"
    )
    evidence = evidence_from_readme("octocat", "repo", text, "README.md")
    assert [item.concept_id for item in evidence] == ["language.cpp"]


def test_dependency_style_statement_still_matches_outside_excluded_context():
    # Positive control: genuine dependency-flavored README statement.
    evidence = evidence_from_readme("octocat", "repo", "Requires PyTorch 2.0 or later.", "README.md")
    assert [item.concept_id for item in evidence] == ["ml.framework.pytorch"]


def test_comparison_only_mention_is_excluded():
    # Negative control: mentioned only in a direct, directional
    # comparison ("unlike X") -- not evidence this repo uses X.
    evidence = evidence_from_readme(
        "octocat", "repo", "Unlike TensorFlow, this project has no GPU dependency.", "README.md"
    )
    assert "ml.framework.tensorflow" not in {item.concept_id for item in evidence}


def test_external_reference_section_mention_is_excluded():
    # Negative control: external project/reference section.
    text = "# myproject\n\n## References\n\n- Built on ideas from the Rust compiler.\n"
    evidence = evidence_from_readme("octocat", "repo", text, "README.md")
    assert "language.rust" not in {item.concept_id for item in evidence}


def test_explicit_non_use_statement_is_excluded():
    # Negative control: explicit statement the technology is NOT used.
    evidence = evidence_from_readme(
        "octocat", "repo", "This project does not use TensorFlow anywhere.", "README.md"
    )
    assert "ml.framework.tensorflow" not in {item.concept_id for item in evidence}


def test_future_intention_without_implementation_is_excluded():
    # Negative control: planned, not implemented.
    evidence = evidence_from_readme(
        "octocat", "repo", "A Rust rewrite is on the roadmap.", "README.md"
    )
    assert "language.rust" not in {item.concept_id for item in evidence}


def test_extractor_version_bumped_for_8d3():
    assert EXTRACTOR_VERSION == "readme:v4"
