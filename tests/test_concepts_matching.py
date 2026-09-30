"""Milestone 6B: gitscore.concepts.matching (shared boundary-aware alias
matching, extracted from evidence/extraction/readme.py so
jobs/parsing/concepts.py can reuse the identical mechanics)."""
from gitscore.concepts.matching import alias_pattern


def test_matches_standalone_token_case_insensitively():
    assert alias_pattern("go").search("Written in GO") is not None


def test_does_not_match_inside_another_word():
    assert alias_pattern("go").search("A mango vector library") is None


def test_matches_alias_with_punctuation():
    assert alias_pattern("next.js").search("Built with Next.js") is not None


def test_pattern_is_cached_and_reused():
    a = alias_pattern("docker")
    b = alias_pattern("docker")
    assert a is b
