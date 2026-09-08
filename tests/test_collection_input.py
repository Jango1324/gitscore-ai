"""Tests for gitscore.dataset.collection_input (Milestone 4).

Username-file parsing for scripts/collect_dataset.py. No GitHub calls.
"""
import pytest

from gitscore.dataset.collection_input import (
    UsernameFileError,
    load_username_file,
    parse_usernames,
)


def test_parses_one_username_per_line():
    assert parse_usernames("torvalds\nkarpathy\ngvanrossum\n") == [
        "torvalds",
        "karpathy",
        "gvanrossum",
    ]


def test_ignores_blank_and_whitespace_only_lines():
    text = "torvalds\n\n   \n\tkarpathy\n\n"
    assert parse_usernames(text) == ["torvalds", "karpathy"]


def test_ignores_full_line_comments():
    text = "# collection list\ntorvalds\n#karpathy is skipped\ngvanrossum\n"
    assert parse_usernames(text) == ["torvalds", "gvanrossum"]


def test_strips_inline_comments():
    text = "torvalds   # linux\nkarpathy\t#nn\n"
    assert parse_usernames(text) == ["torvalds", "karpathy"]


def test_line_that_is_only_an_inline_comment_after_text_is_dropped():
    assert parse_usernames("   # just a comment\n") == []


def test_deduplicates_case_insensitively_keeping_first_spelling():
    text = "Torvalds\ntorvalds\nTORVALDS\nkarpathy\nKarpathy\n"
    assert parse_usernames(text) == ["Torvalds", "karpathy"]


def test_preserves_order_of_first_occurrence():
    text = "c\na\nb\na\nc\n"
    assert parse_usernames(text) == ["c", "a", "b"]


def test_takes_first_token_when_a_line_has_trailing_junk():
    assert parse_usernames("torvalds extra stuff\n") == ["torvalds"]


def test_empty_text_yields_empty_list():
    assert parse_usernames("") == []
    assert parse_usernames("\n\n# only comments\n") == []


def test_load_username_file_reads_and_parses(tmp_path):
    p = tmp_path / "usernames.txt"
    p.write_text("# list\ntorvalds\ntorvalds\nkarpathy\n", encoding="utf-8")
    assert load_username_file(p) == ["torvalds", "karpathy"]


def test_load_username_file_raises_clearly_when_missing(tmp_path):
    missing = tmp_path / "nope.txt"
    with pytest.raises(UsernameFileError) as excinfo:
        load_username_file(missing)
    assert "not found" in str(excinfo.value)
    assert "usernames.example.txt" in str(excinfo.value)


def test_example_template_file_parses_to_no_usernames():
    """The committed template must contain only comments (no real list)."""
    from pathlib import Path

    example = (
        Path(__file__).resolve().parents[1]
        / "data" / "collection" / "usernames.example.txt"
    )
    assert example.exists()
    assert load_username_file(example) == []
