"""Milestone 5D -- gitscore.evidence.extraction.python_deps (requirements.txt)."""
from gitscore.evidence.extraction.python_deps import parse_requirements_txt


def test_known_dependency():
    declarations = parse_requirements_txt("torch\n")
    assert [d.package_name for d in declarations] == ["torch"]


def test_version_specifier_is_stripped_from_package_name():
    declarations = parse_requirements_txt("torch==2.5\npandas>=2\nfastapi~=0.1\n")
    assert [d.package_name for d in declarations] == ["torch", "pandas", "fastapi"]
    assert declarations[0].raw_text == "torch==2.5"


def test_comments_are_ignored():
    text = "# a full-line comment\ntorch  # inline comment\n"
    declarations = parse_requirements_txt(text)
    assert [d.package_name for d in declarations] == ["torch"]
    assert declarations[0].raw_text == "torch"


def test_blank_lines_are_ignored():
    declarations = parse_requirements_txt("torch\n\n\npandas\n")
    assert [d.package_name for d in declarations] == ["torch", "pandas"]


def test_unknown_dependency_is_still_parsed_as_a_declaration():
    # Resolving names to concepts is dependency_evidence's job, not the
    # parser's -- the parser must not pre-judge which names are "known".
    declarations = parse_requirements_txt("some-totally-made-up-package==1.0\n")
    assert [d.package_name for d in declarations] == ["some-totally-made-up-package"]


def test_pip_directives_are_safely_ignored():
    text = "-r other-requirements.txt\n--index-url https://example.com\n-e .\ntorch\n"
    declarations = parse_requirements_txt(text)
    assert [d.package_name for d in declarations] == ["torch"]


def test_vcs_url_requirement_is_safely_skipped():
    text = "git+https://github.com/example/example.git\ntorch\n"
    declarations = parse_requirements_txt(text)
    assert [d.package_name for d in declarations] == ["torch"]


def test_extras_are_stripped_from_package_name():
    declarations = parse_requirements_txt("fastapi[all]>=0.1\n")
    assert declarations[0].package_name == "fastapi"


def test_duplicate_dependency_lines_are_both_parsed():
    # De-duplication is Evidence's job (structural equality via set()),
    # not the parser's -- two identical lines produce two declarations.
    declarations = parse_requirements_txt("torch\ntorch\n")
    assert [d.package_name for d in declarations] == ["torch", "torch"]


def test_empty_file_produces_no_declarations():
    assert parse_requirements_txt("") == []
