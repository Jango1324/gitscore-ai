"""Milestone 6B Part 3/11 -- gitscore.jobs.parsing.segmentation."""
from gitscore.jobs.parsing.segmentation import segment_description
from gitscore.jobs.types import Necessity


def _texts(description):
    return [c.text for c in segment_description(description)]


# ---------------------------------------------------------------------------
# Span correctness (Part 11) -- the load-bearing invariant every claim must satisfy
# ---------------------------------------------------------------------------

def test_every_claim_span_is_an_exact_substring_of_the_description():
    description = (
        "Backend Software Engineer\n\n"
        "Requirements:\n"
        "- Strong Python skills\n"
        "- Experience with PostgreSQL\n\n"
        "Preferred Qualifications:\n"
        "- Experience with AWS\n"
    )
    for claim in segment_description(description):
        assert description[claim.start:claim.end] == claim.text
        assert claim.text == claim.text.strip()  # never includes leading/trailing whitespace


def test_span_correctness_with_multi_paragraph_prose():
    description = "About us: we build things.\n\nRequirements:\nMust have Python. Experience with Docker is required."
    for claim in segment_description(description):
        assert description[claim.start:claim.end] == claim.text


# ---------------------------------------------------------------------------
# Bullet lists
# ---------------------------------------------------------------------------

def test_bullet_list_dash_markers():
    description = "Requirements:\n- Python\n- PostgreSQL\n- Docker\n"
    assert _texts(description) == ["Python", "PostgreSQL", "Docker"]


def test_bullet_list_asterisk_and_numbered_markers():
    description = "Requirements:\n* Python\n1. PostgreSQL\n2) Docker\n"
    assert _texts(description) == ["Python", "PostgreSQL", "Docker"]


# ---------------------------------------------------------------------------
# Newline-separated (no bullet markers)
# ---------------------------------------------------------------------------

def test_newline_separated_requirements_without_bullets():
    description = "Requirements:\nPython\nPostgreSQL\nDocker\n"
    assert _texts(description) == ["Python", "PostgreSQL", "Docker"]


# ---------------------------------------------------------------------------
# Sentences
# ---------------------------------------------------------------------------

def test_sentence_splitting_within_one_line():
    description = "Requirements:\nMust have Python. Experience with PostgreSQL is required."
    claims = _texts(description)
    assert "Must have Python." in claims
    assert "Experience with PostgreSQL is required." in claims


# ---------------------------------------------------------------------------
# Section headings and necessity inheritance
# ---------------------------------------------------------------------------

def test_requirements_section_yields_required_hint():
    description = "Requirements:\n- Python\n"
    claim = segment_description(description)[0]
    assert claim.necessity_hint == Necessity.REQUIRED


def test_preferred_qualifications_section_yields_preferred_hint():
    description = "Preferred Qualifications:\n- Kubernetes experience\n"
    claim = segment_description(description)[0]
    assert claim.necessity_hint == Necessity.PREFERRED


def test_nice_to_have_heading_yields_preferred_hint():
    description = "Nice to Have:\n- AWS experience\n"
    claim = segment_description(description)[0]
    assert claim.necessity_hint == Necessity.PREFERRED


def test_responsibilities_section_still_yields_a_hint_and_is_segmented():
    description = "Responsibilities:\n- Build Python backend services\n"
    claims = segment_description(description)
    assert len(claims) == 1
    assert claims[0].necessity_hint == Necessity.REQUIRED


def test_heading_line_itself_never_becomes_a_claim():
    description = "Requirements:\n- Python\n"
    for claim in segment_description(description):
        assert claim.text.lower() != "requirements"


# ---------------------------------------------------------------------------
# Skip sections (Part 3: avoid obvious marketing/benefits prose)
# ---------------------------------------------------------------------------

def test_benefits_section_produces_no_claims():
    description = (
        "Requirements:\n- Python\n\n"
        "Benefits:\n- Free React JS meetups every Friday\n- Unlimited PTO\n"
    )
    claims = _texts(description)
    assert claims == ["Python"]
    assert not any("meetup" in c.lower() or "PTO" in c for c in claims)


def test_about_us_section_produces_no_claims():
    description = (
        "About Us:\nWe are revolutionizing the industry with cutting-edge technology.\n\n"
        "Requirements:\n- PostgreSQL\n"
    )
    assert _texts(description) == ["PostgreSQL"]


def test_skip_section_ends_at_the_next_heading():
    description = (
        "Benefits:\n- Unlimited snacks\n\n"
        "Requirements:\n- Docker\n"
    )
    assert _texts(description) == ["Docker"]


# ---------------------------------------------------------------------------
# Headerless text: gated by the conservative requirement-signal heuristic
# ---------------------------------------------------------------------------

def test_headerless_marketing_prose_is_not_treated_as_a_requirement():
    description = "We are a fast-growing startup changing the world one line of code at a time."
    assert _texts(description) == []


def test_headerless_sentence_with_a_known_concept_is_treated_as_a_requirement():
    description = "You should have solid experience with Python and PostgreSQL."
    claims = _texts(description)
    assert len(claims) == 1
    assert "Python" in claims[0]


def test_headerless_sentence_with_requirement_vocabulary_is_treated_as_a_requirement():
    description = "3+ years of professional experience is required for this role."
    claims = _texts(description)
    assert len(claims) == 1
