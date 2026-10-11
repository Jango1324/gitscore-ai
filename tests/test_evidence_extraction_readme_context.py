"""Milestone 8D.3 -- gitscore.evidence.extraction.readme_context."""
from gitscore.evidence.extraction.readme_context import (
    NON_IMPLEMENTATION_SECTION_HEADINGS,
    build_context,
    is_non_implementation_mention,
)


def _find(text: str, needle: str) -> tuple[int, int]:
    start = text.index(needle)
    return start, start + len(needle)


# ---------------------------------------------------------------------------
# Section-heading signal
# ---------------------------------------------------------------------------


def test_mention_under_notable_forks_heading_is_excluded():
    text = (
        "# myproject\n\n"
        "Pure C implementation.\n\n"
        "## notable forks\n\n"
        "- [myproject-cpp](https://example.com) by @someone: a C++ port of this project\n"
    )
    start, end = _find(text, "C++")
    context = build_context(text)
    assert is_non_implementation_mention(text, start, end, context) is True


def test_mention_under_related_heading_is_excluded():
    text = (
        "# got\n\nA TypeScript HTTP client.\n\n"
        "## Related\n\n"
        "- [got-fetch](https://example.com) - Got wrapper using Rust internals\n"
    )
    start, end = _find(text, "Rust")
    context = build_context(text)
    assert is_non_implementation_mention(text, start, end, context) is True


def test_mention_before_any_heading_is_not_excluded_by_heading_signal():
    text = "Written in Rust.\n\n## notable forks\n\n- a Go port\n"
    start, end = _find(text, "Rust")
    context = build_context(text)
    assert is_non_implementation_mention(text, start, end, context) is False


def test_mention_under_unrelated_heading_is_not_excluded():
    text = "# myproject\n\n## installation\n\nWritten in Rust for speed.\n"
    start, end = _find(text, "Rust")
    context = build_context(text)
    assert is_non_implementation_mention(text, start, end, context) is False


def test_heading_shaped_line_inside_code_fence_is_not_treated_as_a_heading():
    # A shell comment that happens to start with "#" inside a fenced
    # code block must not be mistaken for a markdown section heading.
    text = (
        "# myproject\n\n"
        "```bash\n"
        "# notable forks\n"
        "echo hi\n"
        "```\n\n"
        "Written in Rust.\n"
    )
    start, end = _find(text, "Rust")
    context = build_context(text)
    # The fake "# notable forks" heading inside the fence must not cause
    # this later, real mention to be excluded.
    assert is_non_implementation_mention(text, start, end, context) is False


def test_heading_normalization_ignores_markdown_emphasis_and_case():
    text = "## **Notable Forks:**\n\n- a C++ port\n"
    start, end = _find(text, "C++")
    context = build_context(text)
    assert is_non_implementation_mention(text, start, end, context) is True
    assert "notable forks" in NON_IMPLEMENTATION_SECTION_HEADINGS


# ---------------------------------------------------------------------------
# Local adjacency cues -- negation / future-intent
# ---------------------------------------------------------------------------


def test_unlike_immediately_before_a_mention_excludes_it():
    text = "Unlike the Python implementation, this is written in C for speed."
    start, end = _find(text, "Python")
    context = build_context(text)
    assert is_non_implementation_mention(text, start, end, context) is True


def test_unlikely_does_not_falsely_trigger_the_unlike_cue():
    # "unlike" must be boundary-matched, not a substring match -- it
    # must not fire merely because "unlikely" contains "unlike".
    text = "In the unlikely event that Rust support ever lands here."
    start, end = _find(text, "Rust")
    context = build_context(text)
    assert is_non_implementation_mention(text, start, end, context) is False


def test_does_not_use_immediately_before_a_mention_excludes_it():
    text = "This project does not use TensorFlow for anything."
    start, end = _find(text, "TensorFlow")
    context = build_context(text)
    assert is_non_implementation_mention(text, start, end, context) is True


def test_is_on_the_roadmap_immediately_after_a_mention_excludes_it():
    text = "A JavaScript SDK is on the roadmap."
    start, end = _find(text, "JavaScript")
    context = build_context(text)
    assert is_non_implementation_mention(text, start, end, context) is True


def test_coming_soon_immediately_after_a_mention_excludes_it():
    text = "Rust bindings (coming soon)."
    start, end = _find(text, "Rust")
    context = build_context(text)
    assert is_non_implementation_mention(text, start, end, context) is True


def test_plain_implementation_statement_is_not_excluded():
    text = "This project is implemented in Python and uses PyTorch for training."
    start, end = _find(text, "Python")
    context = build_context(text)
    assert is_non_implementation_mention(text, start, end, context) is False


def test_instead_of_comparison_is_deliberately_not_an_exclusion_cue():
    # Documented scope boundary (module docstring): generic comparison
    # cues like "instead of" are directionally ambiguous at this bounded
    # scope ("built in Python instead of C" affirms Python), so they are
    # intentionally excluded from the cue list -- this pins that choice.
    text = "Built in Python instead of C for portability."
    start, end = _find(text, "Python")
    context = build_context(text)
    assert is_non_implementation_mention(text, start, end, context) is False


def test_cue_far_outside_the_adjacency_window_does_not_exclude_a_mention():
    padding = "x" * 200
    text = f"does not use{padding}Go for this part of the system."
    start, end = _find(text, "Go")
    context = build_context(text)
    assert is_non_implementation_mention(text, start, end, context) is False
