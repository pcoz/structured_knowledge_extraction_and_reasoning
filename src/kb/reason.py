"""Apply inference rules to derive new facts from the base KB.

Rules are Horn clauses: `IF antecedents THEN consequent`.
Each derivation records its rule + input triples + a human-readable
"since ... therefore ..." explanation for provenance ("why?" queries).
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kb.query import KB, Triple, KB_PATH, fmt_path


@dataclass
class Derivation:
    rule_name: str
    output: Triple
    inputs: list[Triple] = field(default_factory=list)
    explanation: str = ""


# ----------------------------------------------------------------------
# Date / era helpers.
# ----------------------------------------------------------------------


def parse_year(date_str: str) -> tuple[int, str] | None:
    """Return (year, era) where era is 'BC' or 'AD', or None."""
    if not date_str:
        return None
    m = re.match(r"(\d+)\s*BC", date_str, re.IGNORECASE)
    if m:
        return (int(m.group(1)), "BC")
    m = re.match(r"(\d+)\s*AD", date_str, re.IGNORECASE)
    if m:
        return (int(m.group(1)), "AD")
    m = re.match(r"(\d{3,4})", date_str)
    if m:
        return (int(m.group(1)), "AD")
    return None


def classify_era(date_str: str) -> str | None:
    yr = parse_year(date_str)
    if yr is None:
        return None
    year, era = yr
    if era == "BC":
        if year >= 800: return "ancient_archaic_era"
        if year >= 400: return "ancient_classical_era"
        return "ancient_hellenistic_era"
    if year < 500:  return "late_antiquity"
    if year < 1500: return "medieval"
    if year < 1800: return "early_modern"
    if year < 1900: return "nineteenth_century"
    if year < 2000: return "twentieth_century"
    return "twenty_first_century"


def years_lived(born: str, died: str) -> int | None:
    b = parse_year(born)
    d = parse_year(died)
    if not (b and d):
        return None
    b_yr, b_era = b
    d_yr, d_era = d
    b_signed = -b_yr if b_era == "BC" else b_yr
    d_signed = -d_yr if d_era == "BC" else d_yr
    diff = d_signed - b_signed
    if 1 <= diff <= 120:
        return diff
    return None


# ----------------------------------------------------------------------
# Rules — each returns a list of Derivation objects.
# ----------------------------------------------------------------------


def r1_intellectual_descent(kb: KB) -> list[Derivation]:
    """X TUTORED_BY Y, Y TUTORED_BY Z → X INTELLECTUAL_DESCENDANT_OF Z"""
    out = []
    for t1 in kb.triples:
        if t1.relation != "TUTORED_BY":
            continue
        for t2 in kb.out_facts(t1.object, "TUTORED_BY"):
            if t2.object == t1.subject:
                continue
            derived = Triple(
                t1.subject, "INTELLECTUAL_DESCENDANT_OF", t2.object,
                "(derived)", -1,
            )
            expl = (
                f"Since {t1.subject} was tutored by {t1.object}, and "
                f"{t1.object} was tutored by {t2.object}, therefore "
                f"{t1.subject} is an intellectual descendant of "
                f"{t2.object}."
            )
            out.append(Derivation("R1_intellectual_descent", derived,
                                   [t1, t2], expl))
    return out


def r2_mentor_reach(kb: KB) -> list[Derivation]:
    """X TUTORED Y, Y CONQUERED Z → X TAUGHT_CONQUEROR_OF Z"""
    out = []
    for t1 in kb.triples:
        if t1.relation != "TUTORED":
            continue
        for t2 in kb.out_facts(t1.object, "CONQUERED"):
            derived = Triple(
                t1.subject, "TAUGHT_CONQUEROR_OF", t2.object,
                "(derived)", -1,
            )
            expl = (
                f"Since {t1.subject} tutored {t1.object}, and "
                f"{t1.object} conquered {t2.object}, therefore "
                f"{t1.subject}'s teaching reached the conquest of "
                f"{t2.object}."
            )
            out.append(Derivation("R2_mentor_reach", derived,
                                   [t1, t2], expl))
    return out


def r3_grandchild(kb: KB) -> list[Derivation]:
    """X CHILD_OF Y, Y CHILD_OF Z → X GRANDCHILD_OF Z"""
    out = []
    for t1 in kb.triples:
        if t1.relation != "CHILD_OF":
            continue
        for t2 in kb.out_facts(t1.object, "CHILD_OF"):
            if t2.object == t1.subject:
                continue
            derived = Triple(
                t1.subject, "GRANDCHILD_OF", t2.object,
                "(derived)", -1,
            )
            expl = (
                f"Since {t1.subject} is a child of {t1.object}, and "
                f"{t1.object} is a child of {t2.object}, therefore "
                f"{t1.subject} is a grandchild of {t2.object}."
            )
            out.append(Derivation("R3_grandchild", derived,
                                   [t1, t2], expl))
    return out


def r4_era(kb: KB) -> list[Derivation]:
    """X BORN_DATE D → X LIVED_IN era_tag"""
    out = []
    seen = set()
    for t in kb.triples:
        if t.relation != "BORN_DATE":
            continue
        era = classify_era(t.object)
        if era is None or (t.subject, era) in seen:
            continue
        seen.add((t.subject, era))
        derived = Triple(t.subject, "LIVED_IN", era, "(derived)", -1)
        expl = (
            f"Since {t.subject} was born in {t.object}, therefore "
            f"{t.subject} lived in the {era.replace('_', ' ')}."
        )
        out.append(Derivation("R4_era", derived, [t], expl))
    return out


def r5_lifespan(kb: KB) -> list[Derivation]:
    """X BORN_DATE B, X DIED_DATE D → X LIVED_FOR years"""
    out = []
    born = {t.subject: t for t in kb.triples if t.relation == "BORN_DATE"}
    died = {t.subject: t for t in kb.triples if t.relation == "DIED_DATE"}
    for subj in born:
        if subj not in died:
            continue
        years = years_lived(born[subj].object, died[subj].object)
        if years is None:
            continue
        derived = Triple(
            subj, "LIVED_FOR", f"{years} years", "(derived)", -1,
        )
        expl = (
            f"Since {subj} was born in {born[subj].object} and died "
            f"in {died[subj].object}, therefore {subj} lived for "
            f"{years} years."
        )
        out.append(Derivation("R5_lifespan", derived,
                               [born[subj], died[subj]], expl))
    return out


def r6_multi_conqueror(kb: KB) -> list[Derivation]:
    """X CONQUERED Y, X CONQUERED Z, Y ≠ Z → X IS_A MULTI_CONQUEROR"""
    out = []
    by_subj: dict[str, set[str]] = defaultdict(set)
    triples_by_subj: dict[str, list[Triple]] = defaultdict(list)
    for t in kb.triples:
        if t.relation == "CONQUERED":
            by_subj[t.subject].add(t.object)
            triples_by_subj[t.subject].append(t)
    for subj, places in by_subj.items():
        if len(places) < 2:
            continue
        derived = Triple(subj, "IS_A", "MULTI_CONQUEROR", "(derived)", -1)
        expl = (
            f"Since {subj} conquered {', '.join(sorted(places))}, "
            f"therefore {subj} is a multi-conqueror."
        )
        out.append(Derivation("R6_multi_conqueror", derived,
                               triples_by_subj[subj], expl))
    return out


def r7_contemporary(kb: KB, window: int = 50) -> list[Derivation]:
    """X BORN_DATE D1, Y BORN_DATE D2, |D1-D2| ≤ window → X CONTEMPORARY_OF Y"""
    out = []
    parsed = []
    for t in kb.triples:
        if t.relation != "BORN_DATE":
            continue
        p = parse_year(t.object)
        if p is None:
            continue
        year, era = p
        signed = -year if era == "BC" else year
        parsed.append((signed, t))
    parsed.sort(key=lambda x: x[0])
    for i, (y1, t1) in enumerate(parsed):
        for y2, t2 in parsed[i + 1:]:
            if y2 - y1 > window:
                break
            if t1.subject == t2.subject:
                continue
            derived = Triple(
                t1.subject, "CONTEMPORARY_OF", t2.subject,
                "(derived)", -1,
            )
            expl = (
                f"Since {t1.subject} was born in {t1.object} and "
                f"{t2.subject} was born in {t2.object}, therefore "
                f"they were contemporaries (within {window} years)."
            )
            out.append(Derivation("R7_contemporary", derived,
                                   [t1, t2], expl))
    return out


RULES = [
    ("R1_intellectual_descent", r1_intellectual_descent),
    ("R2_mentor_reach",         r2_mentor_reach),
    ("R3_grandchild",           r3_grandchild),
    ("R4_era",                  r4_era),
    ("R5_lifespan",             r5_lifespan),
    ("R6_multi_conqueror",      r6_multi_conqueror),
    ("R7_contemporary",         r7_contemporary),
]


def apply_all_rules(kb: KB) -> tuple[KB, list[Derivation]]:
    """One pass through all rules. Returns extended KB + all derivations."""
    derivations: list[Derivation] = []
    for _, rule_fn in RULES:
        derivations.extend(rule_fn(kb))
    seen = {(t.subject, t.relation, t.object) for t in kb.triples}
    new_triples = []
    for d in derivations:
        key = (d.output.subject, d.output.relation, d.output.object)
        if key not in seen:
            seen.add(key)
            new_triples.append(d.output)
    extended = KB(
        triples=kb.triples + new_triples,
        alias_map=kb.alias_map,
        n_articles=kb.n_articles,
    )
    return extended, derivations


def main() -> None:
    print("=" * 78)
    print("KB reasoning — apply inference rules")
    print("=" * 78)
    print()
    if not KB_PATH.exists():
        print(f"  KB not found: {KB_PATH}")
        return

    kb = KB.load(KB_PATH)
    print(f"  Base: {len(kb.triples):,} triples, {len(kb.entities()):,} entities")
    print()

    kb_ext, derivations = apply_all_rules(kb)

    print("DERIVATIONS BY RULE")
    print("-" * 78)
    by_rule: dict[str, list[Derivation]] = defaultdict(list)
    for d in derivations:
        by_rule[d.rule_name].append(d)
    for rule_name, derivs in by_rule.items():
        print(f"  {rule_name:<32s} {len(derivs):>5d} derivations")
    print(f"  Extended KB: {len(kb_ext.triples):,} triples")
    print()

    # Sample derivations
    print("EXAMPLE DERIVATIONS")
    print("-" * 78)
    for rule_name, derivs in by_rule.items():
        if not derivs:
            continue
        print(f"\n  {rule_name} (showing 2 of {len(derivs)})")
        for d in derivs[:2]:
            print(f"    {d.explanation}")
    print()

    # Compound reasoning queries
    print("COMPOUND REASONING QUERIES")
    print("-" * 78)

    print(f"\n  Q: Who is an intellectual descendant of Socrates?")
    for t in kb_ext.in_facts("Socrates", "INTELLECTUAL_DESCENDANT_OF"):
        print(f"    → {t.subject}")

    print(f"\n  Q: Whose teaching influenced the conquest of Persia?")
    for t in kb_ext.in_facts("Persia", "TAUGHT_CONQUEROR_OF"):
        print(f"    → {t.subject}")

    print(f"\n  Q: Lifespans of selected figures")
    for ent in ["Aristotle", "Plato", "Socrates", "Albert Einstein",
                "Charles Darwin"]:
        for t in kb_ext.out_facts(ent, "LIVED_FOR"):
            print(f"    → {ent} lived for {t.object}")

    print(f"\n  Q: Eras of selected figures")
    for ent in ["Aristotle", "Plato", "Socrates", "Albert Einstein",
                "Alexander the Great"]:
        for t in kb_ext.out_facts(ent, "LIVED_IN"):
            print(f"    → {ent} lived in: {t.object}")

    print(f"\n  Q: Multi-conquerors (showing 5)")
    seen = set()
    for t in kb_ext.triples:
        if t.relation == "IS_A" and t.object == "MULTI_CONQUEROR":
            if t.subject in seen:
                continue
            seen.add(t.subject)
            places = sorted({tc.object for tc in kb_ext.out_facts(t.subject, "CONQUERED")})
            print(f"    → {t.subject}: {places}")
            if len(seen) >= 5:
                break

    print(f"\n  Q: Aristotle's contemporaries (born within 50 years)")
    contemps = set()
    for t in kb_ext.out_facts("Aristotle", "CONTEMPORARY_OF"):
        contemps.add(t.object)
    for t in kb_ext.in_facts("Aristotle", "CONTEMPORARY_OF"):
        contemps.add(t.subject)
    for c in sorted(contemps)[:8]:
        print(f"    → {c}")

    # "Why?" query
    print(f"\n  Q (why?): Why is Aristotle an intellectual descendant of Socrates?")
    relevant = [
        d for d in derivations
        if (d.output.subject == "Aristotle"
            and d.output.relation == "INTELLECTUAL_DESCENDANT_OF"
            and d.output.object == "Socrates")
    ]
    if relevant:
        d = relevant[0]
        print(f"    Rule:   {d.rule_name}")
        print(f"    Inputs:")
        for inp in d.inputs:
            print(f"      - {inp.subject} --{inp.relation}--> {inp.object} "
                  f"(from '{inp.source_article}')")
        print(f"    {d.explanation}")

    # Save extended KB
    out_path = KB_PATH.parent / "kb_1000_articles_extended.json"
    payload = {
        "n_articles": kb_ext.n_articles,
        "alias_map": kb_ext.alias_map,
        "triples": [
            {
                "subject": t.subject,
                "relation": t.relation,
                "object": t.object,
                "source_article": t.source_article,
                "source_sentence_idx": t.source_sentence_idx,
            }
            for t in kb_ext.triples
        ],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n  Extended KB saved to: {out_path.name}")
    print()


if __name__ == "__main__":
    main()
