"""Milestone 5D -- gitscore.evidence.extraction.python_deps (pyproject.toml)."""
import tomllib

import pytest

from gitscore.evidence.extraction.python_deps import parse_pyproject_toml


def test_supported_project_dependencies_array():
    text = """
    [project]
    name = "example"
    dependencies = ["torch==2.5.0", "fastapi"]
    """
    declarations = parse_pyproject_toml(text)
    assert [d.package_name for d in declarations] == ["torch", "fastapi"]


def test_known_dependency():
    text = '[project]\ndependencies = ["psycopg2-binary"]\n'
    declarations = parse_pyproject_toml(text)
    assert declarations[0].package_name == "psycopg2-binary"


def test_unknown_dependency_is_still_parsed():
    text = '[project]\ndependencies = ["some-made-up-thing>=1"]\n'
    declarations = parse_pyproject_toml(text)
    assert declarations[0].package_name == "some-made-up-thing"


def test_malformed_toml_raises_tomldecodeerror_not_a_generic_crash():
    with pytest.raises(tomllib.TOMLDecodeError):
        parse_pyproject_toml("this is not [valid toml")


def test_missing_project_table_produces_no_declarations():
    assert parse_pyproject_toml("[tool.other]\nfoo = 1\n") == []


def test_poetry_style_dependencies_table_is_not_supported():
    # [tool.poetry.dependencies] is a name-keyed table, not the PEP 621
    # array of strings this parser supports -- explicitly out of scope.
    text = """
    [tool.poetry.dependencies]
    torch = "^2.5"
    """
    assert parse_pyproject_toml(text) == []


def test_empty_text_produces_no_declarations():
    assert parse_pyproject_toml("") == []
