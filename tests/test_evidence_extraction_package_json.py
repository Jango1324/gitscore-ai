"""Milestone 5D -- gitscore.evidence.extraction.js_deps (package.json)."""
import json

import pytest

from gitscore.evidence.extraction.js_deps import parse_package_json


def test_dependencies_section():
    text = json.dumps({"dependencies": {"react": "^18.0.0"}})
    declarations = parse_package_json(text)
    assert declarations[0].package_name == "react"
    assert "(dependencies)" in declarations[0].raw_text


def test_dev_dependencies_section():
    text = json.dumps({"devDependencies": {"typescript": "^5.0.0"}})
    declarations = parse_package_json(text)
    assert declarations[0].package_name == "typescript"
    assert "(devDependencies)" in declarations[0].raw_text


def test_known_packages():
    text = json.dumps({"dependencies": {"next": "^14.0.0", "express": "^4.0.0"}})
    declarations = parse_package_json(text)
    assert {d.package_name for d in declarations} == {"next", "express"}


def test_unknown_package_is_still_parsed():
    text = json.dumps({"dependencies": {"some-made-up-thing": "1.0.0"}})
    declarations = parse_package_json(text)
    assert declarations[0].package_name == "some-made-up-thing"


def test_duplicate_dependency_in_both_sections_prefers_dependencies():
    text = json.dumps(
        {
            "dependencies": {"react": "18.0.0"},
            "devDependencies": {"react": "17.0.0"},
        }
    )
    declarations = parse_package_json(text)
    assert len(declarations) == 1
    assert declarations[0].raw_text == "react@18.0.0 (dependencies)"


def test_malformed_json_raises_jsondecodeerror_not_a_generic_crash():
    with pytest.raises(json.JSONDecodeError):
        parse_package_json("{not valid json")


def test_missing_dependency_sections_produce_no_declarations():
    assert parse_package_json(json.dumps({"name": "example"})) == []


def test_empty_text_produces_no_declarations():
    assert parse_package_json("") == []
