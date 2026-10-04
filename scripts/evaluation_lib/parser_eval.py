"""Milestone 8C -- Layer A: job-description parser evaluation.

Compares `parse_job_description()`'s REAL output against hand-authored
gold annotations (`evaluation/gold/jobs/<job_id>.json`). Classifies
every gold row (CORRECT/MISSING/WRONG_CONCEPT/WRONG_NECESSITY/
WRONG_OBSERVABILITY/WRONG_ALTERNATIVE_STRUCTURE/PARTIALLY_CORRECT) and
every unmatched actual requirement (SPURIOUS_REQUIREMENT).

Matching unit: gold rows and actual `JobRequirement`s are joined on
`claim_text` == `JobRequirement.original_text` -- the real parser's own
claim-segmentation unit (one bullet/sentence). Within one claim, a gold
row is further keyed by its `facet` (technical/non_technical/
alternative) and the specific concept_id/category/alternative-id-set it
expects. This never requires gold and actual text to match outside that
one join key, and never derives the expected VALUE from the parser's
own output -- only the comparison is automated.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from gitscore.jobs import JobRequirement, parse_job_description

from evaluation_lib import taxonomy as tax


@dataclass
class RequirementVerdict:
    job_id: str
    claim_text: str
    facet: str
    necessity: str
    expected: dict
    status: str
    tags: tuple[str, ...]
    notes: str = ""


@dataclass
class SpuriousFinding:
    job_id: str
    claim_text: str
    concept_id: str | None
    category: str | None
    is_alternative_group: bool


@dataclass
class ParserJobResult:
    job_id: str
    role_family: str
    verdicts: list[RequirementVerdict] = field(default_factory=list)
    spurious: list[SpuriousFinding] = field(default_factory=list)


def _group_actual_by_claim(requirements: tuple[JobRequirement, ...]) -> dict[str, list[JobRequirement]]:
    grouped: dict[str, list[JobRequirement]] = defaultdict(list)
    for req in requirements:
        grouped[req.original_text].append(req)
    return grouped


def _group_gold_by_claim(expected_requirements: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in expected_requirements:
        grouped[row["claim_text"]].append(row)
    return grouped


def _necessity_tag(gold_necessity: str, actual_necessity) -> str | None:
    if gold_necessity != actual_necessity.value:
        return tax.WRONG_NECESSITY
    return None


def _observability_tag(gold_observability: str, actual_observability) -> str | None:
    if gold_observability != actual_observability.name.lower():
        return tax.WRONG_OBSERVABILITY
    return None


def _evaluate_technical_row(gold_row, actual_technical, matched_ids) -> RequirementVerdict:
    expected_concept = gold_row["concept_id"]
    match = next((r for r in actual_technical if r.concept_id == expected_concept), None)
    if match is None:
        return RequirementVerdict(
            job_id="", claim_text=gold_row["claim_text"], facet="technical",
            necessity=gold_row["necessity"], expected=gold_row, status=tax.MISSING, tags=(tax.MISSING,),
            notes=gold_row.get("notes", ""),
        )
    matched_ids.add(id(match))
    tags = tuple(t for t in (_necessity_tag(gold_row["necessity"], match.necessity),
                              _observability_tag(gold_row["github_observability"], match.github_observability)) if t)
    status = tax.CORRECT if not tags else tax.PARTIALLY_CORRECT
    return RequirementVerdict(
        job_id="", claim_text=gold_row["claim_text"], facet="technical",
        necessity=gold_row["necessity"], expected=gold_row, status=status, tags=tags,
        notes=gold_row.get("notes", ""),
    )


def _evaluate_non_technical_row(gold_row, actual_nontech, matched_ids) -> RequirementVerdict:
    expected_category = gold_row["category"]
    match = next((r for r in actual_nontech if r.category == expected_category), None)
    if match is None and expected_category == "other":
        # "other" is this corpus's placeholder for "no non_technical.py
        # category applies" -- never something the real parser can
        # produce (its category table has no "other" entry), so an
        # "other" gold row can ONLY be satisfied by total absence.
        match = None
    if match is None:
        return RequirementVerdict(
            job_id="", claim_text=gold_row["claim_text"], facet="non_technical",
            necessity=gold_row["necessity"], expected=gold_row, status=tax.MISSING, tags=(tax.MISSING,),
            notes=gold_row.get("notes", ""),
        )
    matched_ids.add(id(match))
    tags = tuple(t for t in (_necessity_tag(gold_row["necessity"], match.necessity),
                              _observability_tag(gold_row["github_observability"], match.github_observability)) if t)
    status = tax.CORRECT if not tags else tax.PARTIALLY_CORRECT
    return RequirementVerdict(
        job_id="", claim_text=gold_row["claim_text"], facet="non_technical",
        necessity=gold_row["necessity"], expected=gold_row, status=status, tags=tags,
        notes=gold_row.get("notes", ""),
    )


def _evaluate_alternative_row(gold_row, actual_alternative, actual_nontech, matched_ids) -> RequirementVerdict:
    expected_ids = tuple(gold_row["alternative_concept_ids"])
    exact = next((r for r in actual_alternative if tuple(r.alternative_concept_ids) == expected_ids), None)
    if exact is not None:
        matched_ids.add(id(exact))
        tags = tuple(t for t in (_necessity_tag(gold_row["necessity"], exact.necessity),
                                  _observability_tag(gold_row["github_observability"], exact.github_observability)) if t)
        status = tax.CORRECT if not tags else tax.PARTIALLY_CORRECT
        return RequirementVerdict(
            job_id="", claim_text=gold_row["claim_text"], facet="alternative",
            necessity=gold_row["necessity"], expected=gold_row, status=status, tags=tags,
            notes=gold_row.get("notes", ""),
        )

    # Any OTHER alternative-group requirement under this claim has the
    # WRONG id set -- a real structural error, not a miss.
    if actual_alternative:
        matched_ids.add(id(actual_alternative[0]))
        return RequirementVerdict(
            job_id="", claim_text=gold_row["claim_text"], facet="alternative",
            necessity=gold_row["necessity"], expected=gold_row,
            status=tax.WRONG_ALTERNATIVE_STRUCTURE, tags=(tax.WRONG_ALTERNATIVE_STRUCTURE,),
            notes=gold_row.get("notes", ""),
        )

    # Milestone 6B.1's conservative "unsafe" fallback collapses an
    # unsafe OR-group into a non-technical `category="alternative_requirement"`
    # placeholder -- structurally present, but the alternative semantics
    # were lost. Distinct from a clean MISSING (nothing at all).
    fallback = next((r for r in actual_nontech if r.category == "alternative_requirement"), None)
    if fallback is not None:
        matched_ids.add(id(fallback))
        return RequirementVerdict(
            job_id="", claim_text=gold_row["claim_text"], facet="alternative",
            necessity=gold_row["necessity"], expected=gold_row,
            status=tax.WRONG_ALTERNATIVE_STRUCTURE, tags=(tax.WRONG_ALTERNATIVE_STRUCTURE,),
            notes=(gold_row.get("notes", "") + " [ACTUAL: collapsed to the unsafe non-technical "
                   "alternative_requirement fallback, not a real alternative_concept_ids group]"),
        )

    return RequirementVerdict(
        job_id="", claim_text=gold_row["claim_text"], facet="alternative",
        necessity=gold_row["necessity"], expected=gold_row, status=tax.MISSING, tags=(tax.MISSING,),
        notes=gold_row.get("notes", ""),
    )


def evaluate_job(job: dict, gold: dict) -> ParserJobResult:
    job_id = job["job_id"]
    profile = parse_job_description(job["raw_text"], title=job.get("title"))
    actual_by_claim = _group_actual_by_claim(profile.requirements)
    gold_by_claim = _group_gold_by_claim(gold["expected_requirements"])

    result = ParserJobResult(job_id=job_id, role_family=job.get("role_family", ""))

    for claim_text, gold_rows in gold_by_claim.items():
        actual_reqs = actual_by_claim.get(claim_text, [])
        actual_alternative = [r for r in actual_reqs if r.is_alternative_group]
        actual_technical = [r for r in actual_reqs if r.concept_id is not None and not r.is_alternative_group]
        actual_nontech = [r for r in actual_reqs if r.concept_id is None and not r.is_alternative_group]
        matched_ids: set[int] = set()

        for gold_row in gold_rows:
            facet = gold_row["facet"]
            if facet == "technical":
                verdict = _evaluate_technical_row(gold_row, actual_technical, matched_ids)
            elif facet == "non_technical":
                verdict = _evaluate_non_technical_row(gold_row, actual_nontech, matched_ids)
            elif facet == "alternative":
                verdict = _evaluate_alternative_row(gold_row, actual_alternative, actual_nontech, matched_ids)
            else:
                raise ValueError(f"unknown gold facet {facet!r} in job {job_id}")
            verdict.job_id = job_id
            result.verdicts.append(verdict)

        for req in actual_reqs:
            if id(req) in matched_ids:
                continue
            result.spurious.append(
                SpuriousFinding(
                    job_id=job_id,
                    claim_text=claim_text,
                    concept_id=req.concept_id,
                    category=req.category,
                    is_alternative_group=req.is_alternative_group,
                )
            )

    return result


def evaluate_jobs(jobs_and_gold: list[tuple[dict, dict]]) -> list[ParserJobResult]:
    return [evaluate_job(job, gold) for job, gold in jobs_and_gold]


def aggregate_metrics(results: list[ParserJobResult]) -> dict:
    status_counts = Counter()
    tag_counts = Counter()
    missed_concepts = Counter()
    total_gold = 0

    for result in results:
        for verdict in result.verdicts:
            total_gold += 1
            status_counts[verdict.status] += 1
            for tag in verdict.tags:
                tag_counts[tag] += 1
            if verdict.status in (tax.MISSING, tax.WRONG_ALTERNATIVE_STRUCTURE):
                if verdict.facet == "technical":
                    missed_concepts[verdict.expected["concept_id"]] += 1
                elif verdict.facet == "alternative":
                    for cid in verdict.expected["alternative_concept_ids"]:
                        missed_concepts[cid] += 1

    total_spurious = sum(len(r.spurious) for r in results)
    recovered = status_counts.get(tax.CORRECT, 0) + status_counts.get(tax.PARTIALLY_CORRECT, 0)
    # recall: of every gold-expected row, how many were recovered AT ALL
    # (right concept/category/alt-group id-set), regardless of whether
    # necessity/observability also matched exactly (those nuances stay
    # visible separately via tag_counts -- recall does not hide them,
    # it just answers a narrower question: "was the right THING found").
    recall = round(recovered / total_gold, 3) if total_gold else None
    # precision: of everything the parser actually produced that gold
    # cared to annotate for (recovered rows) plus everything it invented
    # with no gold counterpart at all (spurious), what fraction was real.
    precision = round(recovered / (recovered + total_spurious), 3) if (recovered + total_spurious) else None

    return {
        "total_jobs": len(results),
        "total_expected_requirements": total_gold,
        "status_counts": dict(status_counts),
        "tag_counts": dict(tag_counts),
        "missed_concepts": dict(missed_concepts.most_common()),
        "total_spurious_requirements": total_spurious,
        "recall": recall,
        "precision": precision,
        "metric_definitions": {
            "recall": "(CORRECT + PARTIALLY_CORRECT) / total_expected_requirements -- 'was the right "
                      "concept/category/alternative-set found at all', independent of necessity/"
                      "observability nuance (those are reported separately in tag_counts, never hidden "
                      "inside this one number)",
            "precision": "(CORRECT + PARTIALLY_CORRECT) / (CORRECT + PARTIALLY_CORRECT + spurious) -- "
                         "of everything recovered or invented, what fraction had a real gold counterpart",
        },
    }
