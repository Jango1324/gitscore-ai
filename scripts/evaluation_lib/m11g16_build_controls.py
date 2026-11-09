"""Milestone 11-G16 Phase 2 -- frozen controls for compound (AND/OR)
requirement logic.

Writes `evaluation/m11g16/compound_logic_controls.json` and its freeze
record. All text is ORIGINAL synthetic material. Each control carries a
hand-annotated Boolean tree (the annotator's reading of the sentence) plus
flags (qualification / ambiguous / conditional). Everything else is DERIVED
from those annotations by the written rules below -- never from
production output, which has not been run on these controls when this
file is frozen:

* representable(): current public models can express only an AND of
  conjuncts, each a single concept or one OR-group of concepts
  (`JobRequirement.alternative_concept_ids`); a k-of-n with 1<k<n, an
  OR containing an AND, an ambiguous or conditional expression are not.
* faithful_rows(): the CNF clauses of a representable tree, duplicates
  removed, redundant clauses absorbed ((D or K) and D == D).
* kleene(): three-valued truth of the tree under a candidate's evidence --
  an evidenceable concept is True/False by evidence; a concept GitHub can
  never evidence ("none"/"non_technical") is UNKNOWN, never False.

Freeze convention (M11-G14): raw `sha256` + freeze-time
`sha256_lf_normalized` (contract crlf-to-lf/v1).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gold_integrity as gi  # noqa: E402

OUT_DIR = REPO_ROOT / "evaluation" / "m11g16"
OUT_PATH = OUT_DIR / "compound_logic_controls.json"
FREEZE_PATH = OUT_DIR / "controls_hash_freeze.json"

LEAVES = {
    "Python": ("language.python", "registry"), "Go": ("language.go", "registry"),
    "Rust": ("language.rust", "registry"), "Java": ("language.java", "registry"),
    "TypeScript": ("language.typescript", "registry"), "SQL": ("language.sql", "registry"),
    "Docker": ("infra.docker", "registry"), "Kubernetes": ("infra.kubernetes", "registry"),
    "AWS": ("cloud.aws", "registry"), "PostgreSQL": ("database.postgresql", "registry"),
    "Redis": ("database.redis", "registry"),
    "Terraform": ("unresolved:terraform", "none"), "Ansible": ("unresolved:ansible", "none"),
    "Azure": ("unresolved:azure", "none"), "Kafka": ("unresolved:kafka", "none"),
    "Spark": ("unresolved:spark", "none"), "Flink": ("unresolved:flink", "none"),
    "Elixir": ("unresolved:elixir", "language_stats"),
    "a security clearance": ("non_technical:security_clearance", "non_technical"),
}
EVIDENCEABLE = ("registry", "language_stats")
IRRELEVANT = ("framework.react", "language.typescript")


def L(surface, necessity=None):  # noqa: N802
    cid, ev = LEAVES[surface]
    node = {"leaf": cid, "surface": surface, "evidenceability": ev}
    if necessity:
        node["necessity"] = necessity
    return node


def OR(*args, necessity=None):  # noqa: N802
    node = {"op": "or", "args": list(args)}
    if necessity:
        node["necessity"] = necessity
    return node


def AND(*args):  # noqa: N802
    return {"op": "and", "args": list(args)}


def KOF(k, *args):  # noqa: N802
    return {"op": "kof", "k": k, "args": list(args)}


def leaves(node) -> list[dict]:
    if node is None:
        return []
    if "leaf" in node:
        return [node]
    return [x for a in node["args"] for x in leaves(a)]


def kleene(node, evidence: set[str]) -> str:
    if "leaf" in node:
        if node["evidenceability"] not in EVIDENCEABLE:
            return "U"
        return "T" if node["leaf"] in evidence else "F"
    vals = [kleene(a, evidence) for a in node["args"]]
    if node["op"] == "or":
        return "T" if "T" in vals else ("F" if all(v == "F" for v in vals) else "U")
    if node["op"] == "and":
        return "F" if "F" in vals else ("T" if all(v == "T" for v in vals) else "U")
    t, u = vals.count("T"), vals.count("U")
    return "T" if t >= node["k"] else ("F" if t + u < node["k"] else "U")


def _normalize(node):
    if node["op"] == "kof" and node["k"] == 1:
        return {**node, "op": "or"}
    if node["op"] == "kof" and node["k"] == len(node["args"]):
        return {**node, "op": "and"}
    return node


def representable(node) -> bool:
    if node is None:
        return False
    if "leaf" in node:
        return True
    node = _normalize(node)
    if node["op"] == "kof":
        return False
    if node["op"] == "or":
        return all("leaf" in a for a in node["args"])
    return all("leaf" in a or (_normalize(a)["op"] == "or" and all("leaf" in x for x in a["args"]))
               for a in node["args"])


def faithful_rows(node, claim_necessity: str) -> list[dict]:
    node = _normalize(node) if "op" in node else node
    if "leaf" in node or node["op"] == "or":
        conjuncts = [node]
    else:
        conjuncts = node["args"]
    rows = []
    for c in conjuncts:
        members = sorted({x["leaf"] for x in leaves(c)})
        rows.append({"members": members, "necessity": c.get("necessity", claim_necessity)})
    unique = []
    for r in rows:
        if r not in unique:
            unique.append(r)
    absorbed = [r for r in unique if not any(set(o["members"]) < set(r["members"]) for o in unique)]
    return absorbed


def fixtures(tree) -> dict[str, list[str]]:
    ev = []
    for lf in leaves(tree):
        if lf["evidenceability"] in EVIDENCEABLE and lf["leaf"] not in ev:
            ev.append(lf["leaf"])
    out = {}
    for i, name in enumerate("ABCD"[:len(ev)]):
        out[f"only_{name}"] = [ev[i]]
    if len(ev) >= 3:
        out["A_and_C"] = [ev[0], ev[2]]
        out["B_and_C"] = [ev[1], ev[2]]
    out["all_members"] = list(ev)
    out["none"] = []
    out["irrelevant"] = [next(i for i in IRRELEVANT if i not in ev)]
    if any(lf["evidenceability"] not in EVIDENCEABLE for lf in leaves(tree)):
        out["mixed_observability_all_evidenceable"] = list(ev)
    return out


def expected_for(control: dict) -> dict:
    tree = control["tree"]
    if not control["is_qualification"]:
        return {"behavior": "not_qualification", "representable": False, "rows": [], "per_fixture": {}}
    rep = representable(tree) and not control["ambiguous"] and not control["conditional"]
    behavior = "represent" if rep else "decline"
    rows = faithful_rows(tree, control["necessity"]) if rep else []
    per = {}
    for name, ev in fixtures(tree).items():
        evs = set(ev)
        supported = sum(1 for r in rows if evs & {m for m in r["members"]
                                                 if LEAVES_BY_ID[m][1] in EVIDENCEABLE})
        per[name] = {
            "evidence": ev,
            "gold_truth": kleene(tree, evs),
            "expected_scored_rows": len(rows),
            "expected_supported_rows": supported,
            "expected_claim_satisfied": kleene(tree, evs) == "T",
        }
    return {
        "behavior": behavior,
        "representable": representable(tree),
        "rows": rows,
        "rows_with_unevidenceable_member": sum(
            1 for r in rows if any(LEAVES_BY_ID[m][1] not in EVIDENCEABLE for m in r["members"])),
        "per_fixture": per,
    }


LEAVES_BY_ID = {cid: (s, ev) for s, (cid, ev) in LEAVES.items()}


def Q(id_, family, text, tree, *, necessity="required", ambiguous=False, conditional=False,  # noqa: N802
      qualification=True, note=""):
    return {"id": f"m11g16-{id_}", "family": family, "text": text,
            "source_span": {"start": 0, "end": len(text)},
            "is_qualification": qualification, "necessity": necessity if qualification else "unknown",
            "tree": tree, "ambiguous": ambiguous, "conditional": conditional, "note": note}


P, G, R, J, T, S = (L(x) for x in ("Python", "Go", "Rust", "Java", "TypeScript", "SQL"))
D, K, A, PG, RD = (L(x) for x in ("Docker", "Kubernetes", "AWS", "PostgreSQL", "Redis"))

CONTROLS = [
    # simple OR
    Q("001", "simple_or", "Experience with Docker or Kubernetes is required.", OR(D, K)),
    Q("002", "simple_or", "Python or Rust experience is preferred.", OR(P, R), necessity="preferred"),
    Q("003", "simple_or", "Either Java or TypeScript is required.", OR(J, T)),
    # simple AND
    Q("004", "simple_and", "Experience with Python and Docker is required.", AND(P, D)),
    Q("005", "simple_and", "Both Kubernetes and AWS experience are required.", AND(K, A)),
    Q("006", "simple_and", "All of the following are required: Python, PostgreSQL, Docker.", AND(P, PG, D)),
    # (A OR B) AND C
    Q("007", "or_then_and", "Experience with Docker or Kubernetes, and Python, is required.", AND(OR(D, K), P)),
    Q("008", "or_then_and", "Docker or Kubernetes experience as well as Python is required.", AND(OR(D, K), P)),
    Q("009", "or_then_and", "You need Docker or Kubernetes plus AWS.", AND(OR(D, K), A)),
    Q("010", "or_then_and", "Required: Docker or Kubernetes; Python.", AND(OR(D, K), P)),
    Q("011", "or_then_and", "Experience with (Docker or Kubernetes) and Python is required.", AND(OR(D, K), P)),
    # A AND (B OR C)
    Q("012", "and_then_or", "Experience with Python and either Docker or Kubernetes is required.", AND(P, OR(D, K))),
    Q("013", "and_then_or", "Python and Docker or Kubernetes experience required.", AND(P, OR(D, K)),
      ambiguous=True, note="precedence undetermined: Python AND (Docker OR K8s) vs (Python AND Docker) OR K8s"),
    Q("014", "and_then_or", "Experience with Python and one of Docker or Kubernetes is required.", AND(P, OR(D, K))),
    Q("015", "and_then_or", "Python, plus either AWS or Docker, is required.", AND(P, OR(A, D))),
    # (A OR B) AND (C OR D)
    Q("016", "or_and_or", "Experience with Python or Go, and Docker or Kubernetes, is required.",
      AND(OR(P, G), OR(D, K))),
    Q("017", "or_and_or", "Python or Java; PostgreSQL or Redis (required).", AND(OR(P, J), OR(PG, RD))),
    Q("018", "or_and_or", "Either Python or Go and either Docker or Kubernetes is required.",
      AND(OR(P, G), OR(D, K))),
    # A OR (B AND C) -- not representable
    Q("019", "or_of_and", "Experience with Rust, or both Docker and Kubernetes, is required.", OR(R, AND(D, K))),
    Q("020", "or_of_and", "Either Python, or Java and SQL, is required.", OR(P, AND(J, S))),
    Q("021", "or_of_and", "Experience with AWS or with both Docker and Kubernetes is required.", OR(A, AND(D, K))),
    # three or more
    Q("022", "three_plus", "Experience with Python, Java, or Rust is required.", OR(P, J, R)),
    Q("023", "three_plus", "Experience with Python, Java, and Rust is required.", AND(P, J, R)),
    Q("024", "three_plus", "Experience with Python or Java or Rust, and Docker is required.", AND(OR(P, J, R), D)),
    # nested alternatives
    Q("025", "nested", "Experience with Python and either Docker, Kubernetes or AWS is required.",
      AND(P, OR(D, K, A))),
    Q("026", "nested", "Either Python and Docker, or Java and Kubernetes, is required.", OR(AND(P, D), AND(J, K))),
    # bullets and nested sublists
    Q("027", "bullets", "Required:\n- Python\n- Docker or Kubernetes\n- PostgreSQL", AND(P, OR(D, K), PG)),
    Q("028", "bullets", "Required:\n- One of:\n  - Docker\n  - Kubernetes\n- Python", AND(OR(D, K), P)),
    Q("029", "bullets", "Requirements:\n- Python or Java, and SQL", AND(OR(P, J), S)),
    # natural-language conjunctions
    Q("030", "natural_language", "You should know Python, and also Docker or Kubernetes.", AND(P, OR(D, K))),
    Q("031", "natural_language", "We need someone with Java experience along with either AWS or Docker.",
      AND(J, OR(A, D))),
    # either / both / one of / all of
    Q("032", "either_both", "One of the following is required: Python, Java, Rust.", OR(P, J, R)),
    Q("033", "either_both", "All of Python, Docker and PostgreSQL are required.", AND(P, D, PG)),
    Q("034", "either_both", "Both Python and Go are required, or equivalent Rust experience.", OR(AND(P, G), R)),
    # at least k of
    Q("035", "k_of_n", "Experience with at least one of Python, Go, or Rust is required.", KOF(1, P, G, R)),
    Q("036", "k_of_n", "Experience with at least two of Python, Java, or Rust is required.", KOF(2, P, J, R)),
    Q("037", "k_of_n", "Strong skills in at least two of: Docker, Kubernetes, AWS.", KOF(2, D, K, A)),
    # conditional
    Q("038", "conditional", "For backend roles, Python or Java is required, and Docker.", AND(OR(P, J), D),
      conditional=True),
    Q("039", "conditional", "Go or Rust is required if you join the platform team, and Docker always.",
      AND(OR(G, R), D), conditional=True),
    # required vs preferred
    Q("040", "necessity_mix", "Python is required; Docker or Kubernetes is preferred.",
      AND(P, OR(D, K, necessity="preferred"))),
    Q("041", "necessity_mix", "Required: Python or Java. Nice to have: Docker and Kubernetes.",
      AND(OR(P, J), L("Docker", "preferred"), L("Kubernetes", "preferred"))),
    Q("042", "necessity_mix", "Python or Go is required, and Docker is a plus.",
      AND(OR(P, G), L("Docker", "preferred"))),
    # ambiguous "A, B or C"
    Q("043", "ambiguous_list", "Experience with Python, Docker or Kubernetes is required.", AND(P, OR(D, K)),
      ambiguous=True, note="mixed-kind list: one OR of three vs Python AND (Docker OR Kubernetes)"),
    Q("044", "ambiguous_list", "Java, Python or Rust experience is required.", OR(J, P, R),
      note="same-kind language list read as one OR of three (annotation convention)"),
    Q("045", "ambiguous_list", "Docker, Kubernetes or Terraform experience is required.",
      OR(D, K, L("Terraform")), note="same-kind infrastructure list read as one OR of three"),
    # unregistered technologies
    Q("046", "unregistered", "Experience with Terraform or Ansible, and Python, is required.",
      AND(OR(L("Terraform"), L("Ansible")), P)),
    Q("047", "unregistered", "Experience with Kafka and either Spark or Flink is required.",
      AND(L("Kafka"), OR(L("Spark"), L("Flink")))),
    Q("048", "unregistered", "Elixir or Go, and PostgreSQL, is required.", AND(OR(L("Elixir"), G), PG)),
    # mixed observability
    Q("049", "mixed_observability", "Experience with AWS or Azure, and Docker, is required.",
      AND(OR(A, L("Azure")), D)),
    Q("050", "mixed_observability", "Experience with Docker or a security clearance, and Python, is required.",
      AND(OR(D, L("a security clearance")), P)),
    # duplicates
    Q("051", "duplicates", "Experience with Docker or Kubernetes, and Docker, is required.", AND(OR(D, K), D),
      note="absorption: equivalent to Docker alone"),
    Q("052", "duplicates", "Experience with Kubernetes (k8s) or Docker, and Python, is required.",
      AND(OR(K, D), P), note="alias inside an OR member"),
    # narrative / responsibilities
    Q("053", "narrative", "You will maintain services written in Python or Go, and deploy them with Docker.", None,
      qualification=False),
    Q("054", "narrative", "Our platform uses Docker or Kubernetes and Python.", None, qualification=False),
    Q("055", "narrative", "Our team builds with Java or Rust, and you will learn Docker.", None, qualification=False),
    # cross-sentence
    Q("056", "cross_sentence", "Experience with Docker or Kubernetes is required. Python is also required.",
      AND(OR(D, K), P)),
    Q("057", "cross_sentence", "Experience with Python or Go is required. You must also know Docker.",
      AND(OR(P, G), D)),
    Q("058", "cross_sentence", "Experience with AWS is required. Alternatively, Docker experience is acceptable.",
      OR(A, D), ambiguous=True, note="cross-sentence alternative: not safely linkable by a sentence-level parser"),
]


def main() -> None:
    ids = [c["id"] for c in CONTROLS]
    assert len(ids) == len(set(ids))
    controls = [{**c, "expected": expected_for(c)} for c in CONTROLS]
    out = {
        "schema_version": 1,
        "milestone": "M11-G16",
        "provenance": "original synthetic text authored for M11-G16; no real or private posting",
        "authorship_disclosure": "same author as G10-G15; not independently annotated",
        "derivation_rules": "representable(), faithful_rows(), fixtures(), kleene() in m11g16_build_controls.py",
        "controls": controls,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(out, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    OUT_PATH.write_bytes(payload)
    freeze = {
        "frozen_file": "evaluation/m11g16/compound_logic_controls.json",
        "sha256": gi.sha256(payload),
        "sha256_lf_normalized": gi.sha256(gi.canonical_bytes(payload)),
        "length_bytes": len(payload),
        "canonical_contract": gi.CONTRACT,
        "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Frozen BEFORE any production run or candidate fix strategy on these controls.",
    }
    FREEZE_PATH.write_bytes((json.dumps(freeze, indent=2) + "\n").encode("utf-8"))
    from collections import Counter
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)}: {len(controls)} controls; "
          f"behaviors={dict(Counter(c['expected']['behavior'] for c in controls))}; "
          f"fixtures={sum(len(c['expected']['per_fixture']) for c in controls)}; sha256={freeze['sha256']}")


if __name__ == "__main__":
    main()
