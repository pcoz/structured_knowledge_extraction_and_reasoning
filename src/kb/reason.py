"""Apply inference rules to derive new facts from the base KB.

The engine supports three classes of rule:

  - Horn clauses (the `Rule` dataclass at stratum 0), run iteratively
    to fixpoint so that a rule whose antecedents include another
    rule's consequent (e.g., transitive closure) converges over
    multiple rounds.
  - Declarative disjunctive rules (`DisjunctiveRule`), capturing the
    "alternative antecedent relations, one consequent" pattern in
    inspectable form.
  - Stratified negation-as-failure (rules at stratum ≥ 1 using the
    `kb_has` helper to test absence). Stratification keeps the result
    deterministic despite negation being non-monotonic.

Each derivation records its rule + input triples + a human-readable
"since ... therefore ..." explanation for provenance ("why?" queries).
A divergence guard raises `RuntimeError` if any stratum fails to
converge within `max_iter`, rather than silently truncating.

The module also ships a `stress_test()` suite of 10 assertion-backed
scenarios (deep chains, cycles, empty KB, alias variants, ordering
invariance, determinism, divergence detection, multi-stratum dispatch)
that runs alongside the main demo to guard against regressions.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

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
# Rule abstractions.
#
# stratum=0 — monotonic Horn rule. Run iteratively to fixpoint.
# stratum=1 — uses negation-as-failure. Run once after stratum-0 has
#             converged. Stratification keeps the result deterministic
#             despite negation being non-monotonic.
# ----------------------------------------------------------------------


@dataclass
class Rule:
    name: str
    fn: Callable[["KB"], list[Derivation]]
    stratum: int = 0


@dataclass
class DisjunctiveRule:
    """Declarative shape: any of `alternatives` (relation names) in
    antecedent position derives one fact of `consequent`. Each
    alternative fires independently. Keeps the rule's structure
    inspectable without reading Python."""
    name: str
    alternatives: list[str]
    consequent: str
    explanation_template: str
    stratum: int = 0

    def to_rule(self) -> "Rule":
        def fn(kb) -> list[Derivation]:
            out: list[Derivation] = []
            for rel in self.alternatives:
                # by_relation gives O(1) access to all triples with a
                # given relation — much faster than scanning kb.triples
                # once per alternative, especially as the KB grows.
                for idx in kb.by_relation.get(rel, []):
                    t = kb.triples[idx]
                    if t.subject == t.object:
                        # Self-relations rarely yield meaningful
                        # consequents and clutter the closure (e.g.
                        # "X INFLUENCED_BY X" from a self-loop).
                        continue
                    derived = Triple(
                        t.subject, self.consequent, t.object,
                        "(derived)", -1,
                    )
                    expl = self.explanation_template.format(
                        subject=t.subject, object=t.object, via=rel,
                    )
                    out.append(Derivation(self.name, derived, [t], expl))
            return out
        return Rule(self.name, fn, self.stratum)


def kb_has(kb, subject: str, relation: str) -> bool:
    """True if the KB has any (subject, relation, *) fact. Used by
    negation-as-failure rules to test absence under the closed-world
    assumption. Subject is canonicalised via the KB's alias map so
    'Einstein' and 'Albert Einstein' resolve to the same entity."""
    canon = kb.alias_map.get(subject, subject)
    for rel, _, _ in kb.out_edges.get(canon, []):
        if rel == relation:
            return True
    return False


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


# ----------------------------------------------------------------------
# Rules that exercise the extended engine.
# ----------------------------------------------------------------------


def r8_transitive_descent(kb: KB) -> list[Derivation]:
    """X INTELLECTUAL_DESCENDANT_OF Y, Y INTELLECTUAL_DESCENDANT_OF Z
       → X INTELLECTUAL_DESCENDANT_OF Z.

    Transitive closure of intellectual descent. The antecedent and
    consequent share a relation, so each round extends chains by one
    hop — needs fixpoint iteration to fully close longer lineages
    (e.g., Socrates → Plato → Aristotle → Theophrastus)."""
    out = []
    for t1 in kb.triples:
        if t1.relation != "INTELLECTUAL_DESCENDANT_OF":
            continue
        # out_facts canonicalises t1.object via the alias map before
        # looking up adjacency, so aliased entities resolve correctly.
        for t2 in kb.out_facts(t1.object, "INTELLECTUAL_DESCENDANT_OF"):
            if t2.object == t1.subject:
                # Block "X descended from X" — would be derived in any
                # cyclic chain (A→B→C→A) and is rarely meaningful.
                continue
            derived = Triple(
                t1.subject, "INTELLECTUAL_DESCENDANT_OF", t2.object,
                "(derived)", -1,
            )
            expl = (
                f"Since {t1.subject} is an intellectual descendant of "
                f"{t1.object}, and {t1.object} is an intellectual "
                f"descendant of {t2.object}, therefore {t1.subject} "
                f"is an intellectual descendant of {t2.object}."
            )
            out.append(Derivation("R8_transitive_descent", derived,
                                   [t1, t2], expl))
    return out


def r11_descent_extension(kb: KB) -> list[Derivation]:
    """X TUTORED_BY Y, Y INTELLECTUAL_DESCENDANT_OF Z → X IDO Z.

    Bridges direct tutoring with existing descent chains. R1 alone
    catches only 2-hop tutoring; R8 closes IDO transitively over its
    own outputs; this rule extends a descent chain by one TUTORED_BY
    hop at the young end. The three rules together produce the full
    transitive closure of intellectual descent at distance ≥ 2.

    This rule was added after stress-test scenario 1 caught the gap:
    a 6-node chain only produced 6/10 expected facts under R1+R8 alone
    because the bridge from "X's direct teacher" to "X's teacher's
    deeper ancestors" was never made."""
    out = []
    for t1 in kb.triples:
        if t1.relation != "TUTORED_BY":
            continue
        for t2 in kb.out_facts(t1.object, "INTELLECTUAL_DESCENDANT_OF"):
            if t2.object == t1.subject:
                continue
            derived = Triple(
                t1.subject, "INTELLECTUAL_DESCENDANT_OF", t2.object,
                "(derived)", -1,
            )
            expl = (
                f"Since {t1.subject} was tutored by {t1.object}, and "
                f"{t1.object} is an intellectual descendant of "
                f"{t2.object}, therefore {t1.subject} is an "
                f"intellectual descendant of {t2.object}."
            )
            out.append(Derivation("R11_descent_extension", derived,
                                   [t1, t2], expl))
    return out


# Disjunctive rule: INFLUENCED_BY fires from either a direct tutoring
# relation or a transitive intellectual-descent relation. Demonstrates
# the engine's disjunction support — one declarative consequent, two
# alternative antecedent patterns.
R9_INFLUENCED_BY = DisjunctiveRule(
    name="R9_influenced_by",
    alternatives=["TUTORED_BY", "INTELLECTUAL_DESCENDANT_OF"],
    consequent="INFLUENCED_BY",
    explanation_template=(
        "Since {subject} stands in relation {via} to {object}, "
        "therefore {subject} was influenced by {object}."
    ),
)


def r10_progenitor(kb: KB) -> list[Derivation]:
    """X CHILD_OF Y, NOT (Y CHILD_OF *) → Y IS_A FAMILY_PROGENITOR.

    Negation-as-failure (stratum 1): Y is recorded as somebody's
    parent but the KB records no parent for Y. Sound only under the
    closed-world assumption — if the KB is incomplete, this rule
    over-fires. Stratified semantics guarantees this rule runs once,
    on the converged positive closure."""
    out = []
    seen = set()
    for t in kb.triples:
        if t.relation != "CHILD_OF":
            continue
        # Canonicalise via alias map so "Einstein" and "Albert Einstein"
        # collapse to one progenitor rather than two — without this, a
        # stress-test caught duplicate emissions across surface forms.
        parent = kb.alias_map.get(t.object, t.object)
        if parent in seen:
            continue
        if kb_has(kb, parent, "CHILD_OF"):
            continue
        seen.add(parent)
        derived = Triple(
            parent, "IS_A", "FAMILY_PROGENITOR", "(derived)", -1,
        )
        expl = (
            f"Since at least one entity is recorded as a child of "
            f"{parent}, and the KB records no parent for {parent}, "
            f"therefore {parent} is a family progenitor "
            f"(closed-world)."
        )
        out.append(Derivation("R10_progenitor", derived, [t], expl))
    return out


RULES: list[Rule] = [
    Rule("R1_intellectual_descent", r1_intellectual_descent),
    Rule("R2_mentor_reach",         r2_mentor_reach),
    Rule("R3_grandchild",           r3_grandchild),
    Rule("R4_era",                  r4_era),
    Rule("R5_lifespan",             r5_lifespan),
    Rule("R6_multi_conqueror",      r6_multi_conqueror),
    Rule("R7_contemporary",         r7_contemporary),
    Rule("R8_transitive_descent",   r8_transitive_descent),
    R9_INFLUENCED_BY.to_rule(),
    Rule("R10_progenitor",          r10_progenitor,          stratum=1),
    Rule("R11_descent_extension",   r11_descent_extension),
]


def apply_all_rules(kb: KB) -> tuple[KB, list[Derivation]]:
    """Run all rules to fixpoint with stratified negation-as-failure.

    Backward-compatible wrapper around apply_all_rules_to_fixpoint
    that discards per-iteration diagnostics."""
    kb_ext, derivations, _ = apply_all_rules_to_fixpoint(kb)
    return kb_ext, derivations


def apply_all_rules_to_fixpoint(
    kb: KB, rules: list[Rule] | None = None, max_iter: int = 20,
) -> tuple[KB, list[Derivation], dict]:
    """Iterate rules to fixpoint, stratum by stratum, in ascending order.

    Stratified-Datalog semantics: strata run in order; within each
    stratum, rules iterate until no new facts are derived. Negation-
    as-failure rules belong in a stratum ≥ 1 and should only check
    `kb_has` for facts whose producing rules live in lower strata —
    this is what makes the engine deterministic despite negation
    being non-monotonic.

    By convention: stratum 0 holds monotonic Horn rules; stratum 1
    holds negation-as-failure rules using `kb_has` against stratum-0
    facts. Higher strata are supported (rules at stratum N may use
    negation against any stratum < N), and are dispatched in order.

    Raises `RuntimeError` if a stratum hits `max_iter` without
    converging — this almost always means a rule produces unbounded
    new facts (a likely bug, not a slow convergence).

    Returns (extended_kb, all_derivations, stats), where stats has:
        per_stratum:        dict[int, list[int]] — new-fact counts per
                            iteration, keyed by stratum
        total_iters:        int — total iterations across all strata
        stratum_0_per_iter: list[int] — back-compat shortcut
        stratum_0_iters:    int       — back-compat shortcut
        stratum_1_count:    int       — back-compat shortcut
    """
    if rules is None:
        rules = RULES
    # Group rules by stratum: stratum 0 (Horn) is safe to iterate;
    # stratum ≥ 1 (negation-as-failure) must wait until lower strata
    # converge so the absence check it performs is well-defined.
    by_stratum: dict[int, list[Rule]] = defaultdict(list)
    for r in rules:
        by_stratum[r.stratum].append(r)

    # `seen` is the dedup set: every fact already in the KB plus every
    # fact derived so far. Lets us cheaply check "is this triple new?"
    # without scanning kb.triples on every derivation.
    seen = {(t.subject, t.relation, t.object) for t in kb.triples}
    all_derivations: list[Derivation] = []
    per_stratum: dict[int, list[int]] = defaultdict(list)
    current = kb

    for stratum in sorted(by_stratum.keys()):
        stratum_rules = by_stratum[stratum]
        for iteration in range(max_iter):
            # Semi-naive discipline: rules see `current` (last round's
            # snapshot). Facts derived in this round only become
            # visible in the next round. Without this, two rules in
            # the same round could see each other's partial outputs
            # and produce non-deterministic results.
            round_new: list[Triple] = []
            round_derivs: list[Derivation] = []
            for r in stratum_rules:
                for d in r.fn(current):
                    key = (d.output.subject, d.output.relation, d.output.object)
                    if key not in seen:
                        seen.add(key)
                        round_new.append(d.output)
                        round_derivs.append(d)
            if not round_new:
                break
            per_stratum[stratum].append(len(round_new))
            all_derivations.extend(round_derivs)
            # Rebuild the KB so __post_init__ re-indexes the adjacency
            # structures with the new triples included. Cost is linear
            # in total triples per round — fine for our scale.
            current = KB(
                triples=current.triples + round_new,
                alias_map=current.alias_map,
                n_articles=current.n_articles,
            )
        else:
            # `for…else` runs when the for-loop completes without
            # hitting `break`. Here that means we exhausted max_iter
            # without converging — almost always a buggy rule that
            # produces unbounded new facts. Better to raise than to
            # silently return a truncated artifact.
            raise RuntimeError(
                f"Stratum {stratum} did not converge in {max_iter} "
                f"iterations — likely a rule producing unbounded new "
                f"facts (check for missing self-loop / duplicate guards)."
            )

    stats = {
        "per_stratum": dict(per_stratum),
        "total_iters": sum(len(v) for v in per_stratum.values()),
        # Back-compat shortcuts for callers that read the old keys.
        "stratum_0_per_iter": per_stratum.get(0, []),
        "stratum_0_iters": len(per_stratum.get(0, [])),
        "stratum_1_count": sum(per_stratum.get(1, [])),
    }
    return current, all_derivations, stats


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

    kb_ext, derivations, stats = apply_all_rules_to_fixpoint(kb)

    print("FIXPOINT CONVERGENCE")
    print("-" * 78)
    print(f"  Stratum 0 (monotonic Horn): {stats['stratum_0_iters']} "
          f"iterations, new facts per round: {stats['stratum_0_per_iter']}")
    print(f"  Stratum 1 (negation-as-failure): "
          f"{stats['stratum_1_count']} derivations on closure")
    print()

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

    # --- Fixpoint: R8 transitive intellectual descent. ---
    print(f"\n  Q (fixpoint): Aristotle's full intellectual lineage "
          f"(transitive closure)")
    ancestors = sorted({
        t.object for t in kb_ext.out_facts(
            "Aristotle", "INTELLECTUAL_DESCENDANT_OF")
    })
    for a in ancestors:
        print(f"    → {a}")

    # --- Disjunction: R9 INFLUENCED_BY via either TUTORED_BY or descent. ---
    print(f"\n  Q (disjunction): Who influenced Aristotle?")
    influences = sorted({
        t.object for t in kb_ext.out_facts("Aristotle", "INFLUENCED_BY")
    })
    for inf in influences:
        print(f"    → {inf}")

    # --- Negation-as-failure: R10 FAMILY_PROGENITOR. ---
    print(f"\n  Q (negation-as-failure): Family progenitors in the KB "
          f"(parents with no recorded parent of their own)")
    progenitors = sorted({
        t.subject for t in kb_ext.triples
        if t.relation == "IS_A" and t.object == "FAMILY_PROGENITOR"
    })
    for p in progenitors[:10]:
        children = [tc.subject for tc in kb_ext.in_facts(p, "CHILD_OF")]
        print(f"    → {p}  (parent of: {', '.join(children[:3])}"
              f"{'...' if len(children) > 3 else ''})")

    # --- Compound query: chains fixpoint + disjunction + classification.
    # For each derived MULTI_CONQUEROR with a known teacher, show the
    # teacher's INFLUENCED_BY set (which itself comes from R1+R11
    # tutoring chains via the R9 disjunctive rule). Touches three of
    # the new capabilities in one query. ---
    print(f"\n  Q (compound): For each MULTI_CONQUEROR in the KB with a "
          f"known teacher, trace who influenced that teacher")
    conquerors = sorted({
        t.subject for t in kb_ext.triples
        if t.relation == "IS_A" and t.object == "MULTI_CONQUEROR"
    })
    found_any = False
    for c in conquerors:
        teachers = sorted({t.subject for t in kb_ext.in_facts(c, "TUTORED")})
        for teacher in teachers:
            ancestors = sorted({
                t.object for t in kb_ext.out_facts(teacher, "INFLUENCED_BY")
            })
            if ancestors:
                found_any = True
                print(f"    → {c} was taught by {teacher}; "
                      f"{teacher} was influenced by: {', '.join(ancestors)}")
    if not found_any:
        print(f"    (no chains found in this corpus)")

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


def _make_kb(
    triples: list[tuple[str, str, str]],
    alias_map: dict[str, str] | None = None,
) -> KB:
    """Build a small in-memory KB from (subject, relation, object) tuples."""
    return KB(
        triples=[
            Triple(s, r, o, "(test)", -1) for s, r, o in triples
        ],
        alias_map=alias_map or {},
        n_articles=0,
    )


def stress_test() -> None:
    """Exercise fixpoint, disjunction, and stratified negation on
    synthetic KBs whose expected closures can be computed by hand.

    Each scenario asserts an exact match against the expected output.
    The 1000-article KB used by main() is too thin in places (only one
    INTELLECTUAL_DESCENDANT_OF chain, no cycles) to actually stress the
    engine — these scenarios do."""
    print("=" * 78)
    print("Reasoning-engine stress tests")
    print("=" * 78)
    print()

    # -- Scenario 1: deep tutoring chain. ------------------------------
    # F TUTORED E, E TUTORED D, ..., B TUTORED A.
    # With R1 producing IDO from 2-link tutoring chains and R8 closing
    # IDO transitively, the expected set is every (descendant, ancestor)
    # pair at distance ≥ 2 in the chain.
    chain = ["F", "E", "D", "C", "B", "A"]    # F is the elder, A the youngest
    triples_1 = [(chain[i + 1], "TUTORED_BY", chain[i])
                 for i in range(len(chain) - 1)]
    kb1 = _make_kb(triples_1)
    kb1_ext, _, stats1 = apply_all_rules_to_fixpoint(kb1)
    descents = {
        (t.subject, t.object) for t in kb1_ext.triples
        if t.relation == "INTELLECTUAL_DESCENDANT_OF"
    }
    expected = {
        (chain[i], chain[j])
        for i in range(len(chain))
        for j in range(i)
        if i - j >= 2
    }
    print("Scenario 1: deep tutoring chain (6 nodes, 5 links)")
    print(f"  Fixpoint iterations:   {stats1['stratum_0_iters']}")
    print(f"  Per-iter new facts:    {stats1['stratum_0_per_iter']}")
    print(f"  IDO derived:           {len(descents)} (expected {len(expected)})")
    assert descents == expected, (
        f"FAIL: missing={expected - descents}, extra={descents - expected}"
    )
    # Fixpoint must actually iterate — a chain this long can't close in 1 pass.
    assert stats1["stratum_0_iters"] >= 3, (
        f"FAIL: fixpoint converged in {stats1['stratum_0_iters']} "
        f"iterations; deep chain should need ≥3"
    )
    print("  PASS: transitive closure complete; fixpoint iterated as expected")
    print()

    # -- Scenario 2: disjunctive rule fires from both alternatives. ----
    # R9 INFLUENCED_BY := TUTORED_BY ∪ INTELLECTUAL_DESCENDANT_OF.
    # Both should produce facts on the same KB after fixpoint.
    influenced = {
        (t.subject, t.object) for t in kb1_ext.triples
        if t.relation == "INFLUENCED_BY"
    }
    expected_inf = set()
    for t in kb1_ext.triples:
        if t.relation in ("TUTORED_BY", "INTELLECTUAL_DESCENDANT_OF"):
            expected_inf.add((t.subject, t.object))
    print("Scenario 2: disjunctive rule (TUTORED_BY ∪ DESCENDANT_OF)")
    print(f"  INFLUENCED_BY derived: {len(influenced)} (expected {len(expected_inf)})")
    assert influenced == expected_inf, (
        f"FAIL: diff = {influenced ^ expected_inf}"
    )
    print("  PASS: both alternatives fire; consequent reached from each")
    print()

    # -- Scenario 3: stratification — R10 must not run before R1. ------
    # If R10 ran during stratum 0 it could fire on an intermediate state
    # where R3_grandchild hasn't yet derived facts. Build a CHILD_OF
    # chain and check both: R3 derives correctly, and R10 only flags the
    # true root.
    kb3 = _make_kb([
        ("Child", "CHILD_OF", "Parent"),
        ("Parent", "CHILD_OF", "Grandparent"),
    ])
    kb3_ext, _, _ = apply_all_rules_to_fixpoint(kb3)
    progenitors = {
        t.subject for t in kb3_ext.triples
        if t.relation == "IS_A" and t.object == "FAMILY_PROGENITOR"
    }
    grandchildren = {
        (t.subject, t.object) for t in kb3_ext.triples
        if t.relation == "GRANDCHILD_OF"
    }
    print("Scenario 3: stratified negation on a CHILD_OF chain")
    print(f"  Progenitors:           {progenitors}")
    print(f"  GRANDCHILD_OF derived: {grandchildren}")
    assert progenitors == {"Grandparent"}, (
        f"FAIL: expected {{'Grandparent'}}, got {progenitors}"
    )
    assert ("Child", "Grandparent") in grandchildren
    # Parent is NOT a progenitor because Parent has CHILD_OF Grandparent.
    assert "Parent" not in progenitors
    print("  PASS: only the true root emits; positive R3 also fires")
    print()

    # -- Scenario 4: cycle protection. ---------------------------------
    # A 3-cycle in TUTORED_BY should yield IDO between every distinct pair
    # but no self-loops, and fixpoint must terminate well before max_iter.
    kb4 = _make_kb([
        ("A", "TUTORED_BY", "B"),
        ("B", "TUTORED_BY", "C"),
        ("C", "TUTORED_BY", "A"),
    ])
    kb4_ext, _, stats4 = apply_all_rules_to_fixpoint(kb4, max_iter=20)
    descents4 = {
        (t.subject, t.object) for t in kb4_ext.triples
        if t.relation == "INTELLECTUAL_DESCENDANT_OF"
    }
    expected_desc4 = {
        (a, b) for a in "ABC" for b in "ABC" if a != b
    }
    self_loops = [
        t for t in kb4_ext.triples
        if t.relation == "INTELLECTUAL_DESCENDANT_OF" and t.subject == t.object
    ]
    print("Scenario 4: cycle protection (3-node TUTORED_BY cycle)")
    print(f"  Fixpoint iterations:   {stats4['stratum_0_iters']}")
    print(f"  IDO derived:           {len(descents4)} (expected {len(expected_desc4)})")
    assert descents4 == expected_desc4, (
        f"FAIL: got {descents4}, expected {expected_desc4}"
    )
    assert not self_loops, f"FAIL: self-loops found: {self_loops}"
    assert stats4["stratum_0_iters"] < 20, "FAIL: fixpoint did not terminate"
    print("  PASS: no self-loops; fixpoint terminates")
    print()

    # -- Scenario 5: empty KB. -----------------------------------------
    kb5 = _make_kb([])
    kb5_ext, derivs5, stats5 = apply_all_rules_to_fixpoint(kb5)
    print("Scenario 5: empty KB")
    assert kb5_ext.triples == []
    assert derivs5 == []
    assert stats5["stratum_0_iters"] == 0
    assert stats5["stratum_1_count"] == 0
    print("  PASS: no crash; no derivations")
    print()

    # -- Scenario 6: alias canonicalisation in negation. ---------------
    # Two CHILD_OF facts using different surface forms for the same
    # parent must produce ONE progenitor, not two.
    kb6 = _make_kb(
        [
            ("Junior", "CHILD_OF", "Einstein"),
            ("Senior", "CHILD_OF", "Albert Einstein"),
        ],
        alias_map={"Einstein": "Albert Einstein"},
    )
    kb6_ext, _, _ = apply_all_rules_to_fixpoint(kb6)
    progenitors6 = {
        t.subject for t in kb6_ext.triples
        if t.relation == "IS_A" and t.object == "FAMILY_PROGENITOR"
    }
    print("Scenario 6: alias canonicalisation in r10_progenitor")
    print(f"  Progenitors:           {progenitors6}")
    assert progenitors6 == {"Albert Einstein"}, (
        f"FAIL: expected one canonical progenitor, got {progenitors6}"
    )
    print("  PASS: aliases collapsed to one canonical progenitor")
    print()

    # -- Scenario 7: stratified negation, ordering invariance. ---------
    # Reverse triple order — result must be identical. Stratification
    # makes the engine order-insensitive at the rule level.
    kb7 = _make_kb([
        ("Parent", "CHILD_OF", "Grandparent"),    # parent triple first
        ("Child", "CHILD_OF", "Parent"),
    ])
    kb7_ext, _, _ = apply_all_rules_to_fixpoint(kb7)
    progenitors7 = {
        t.subject for t in kb7_ext.triples
        if t.relation == "IS_A" and t.object == "FAMILY_PROGENITOR"
    }
    print("Scenario 7: ordering invariance (CHILD_OF triples reversed)")
    print(f"  Progenitors:           {progenitors7}")
    assert progenitors7 == {"Grandparent"}, (
        f"FAIL: stratified result depended on triple order: {progenitors7}"
    )
    print("  PASS: result is order-invariant")
    print()

    # -- Scenario 8: determinism — two runs produce identical artifacts. -
    kb8a = _make_kb([
        ("Aristotle", "TUTORED_BY", "Plato"),
        ("Plato", "TUTORED_BY", "Socrates"),
        ("Alexander", "CHILD_OF", "Philip"),
    ])
    kb8b = _make_kb([
        ("Aristotle", "TUTORED_BY", "Plato"),
        ("Plato", "TUTORED_BY", "Socrates"),
        ("Alexander", "CHILD_OF", "Philip"),
    ])
    out_a = sorted(
        (t.subject, t.relation, t.object)
        for t in apply_all_rules_to_fixpoint(kb8a)[0].triples
    )
    out_b = sorted(
        (t.subject, t.relation, t.object)
        for t in apply_all_rules_to_fixpoint(kb8b)[0].triples
    )
    print("Scenario 8: determinism across runs")
    assert out_a == out_b, "FAIL: same input, different output"
    print(f"  PASS: identical artifacts across two independent runs "
          f"({len(out_a)} triples each)")
    print()

    # -- Scenario 9: divergence guard. ----------------------------------
    # A pathological rule that emits unbounded new facts must trigger
    # the RuntimeError, not loop until max_iter and silently truncate.
    def runaway_rule(kb_: KB) -> list[Derivation]:
        out = []
        for t in kb_.triples:
            if t.relation == "BOGUS":
                # Each iteration generates a new object suffixed with
                # the current size — unbounded by design.
                new_obj = f"{t.object}_{len(kb_.triples)}"
                out.append(Derivation(
                    "runaway",
                    Triple(t.subject, "BOGUS", new_obj, "(derived)", -1),
                    [t], "runaway",
                ))
        return out

    kb9 = _make_kb([("X", "BOGUS", "Y")])
    runaway_rules = [Rule("runaway", runaway_rule)]
    print("Scenario 9: divergence guard (unbounded-output rule)")
    try:
        apply_all_rules_to_fixpoint(kb9, rules=runaway_rules, max_iter=5)
        assert False, "FAIL: divergent rule did not raise"
    except RuntimeError as e:
        assert "did not converge" in str(e)
        print(f"  PASS: RuntimeError raised as expected")
    print()

    # -- Scenario 10: arbitrary higher strata are dispatched in order. -
    # A stratum-2 rule must see stratum-1 facts. Build a chain where:
    #   stratum 0: TUTORED_BY → IDO  (existing R1)
    #   stratum 1: IDO present, no DIED_DATE → IS_A LIVING_INFLUENCE
    #   stratum 2: IS_A LIVING_INFLUENCE → IS_A NOTABLE_FIGURE
    # If the engine ignored stratum 2 (the old hardcoded 0/1 behaviour),
    # NOTABLE_FIGURE would not be derived.
    def r_living_influence(kb_: KB) -> list[Derivation]:
        out = []
        for t in kb_.triples:
            if t.relation != "INTELLECTUAL_DESCENDANT_OF":
                continue
            if kb_has(kb_, t.object, "DIED_DATE"):
                continue
            out.append(Derivation(
                "r_living_influence",
                Triple(t.object, "IS_A", "LIVING_INFLUENCE", "(derived)", -1),
                [t], f"{t.object} has descendants but no death date",
            ))
        return out

    def r_notable(kb_: KB) -> list[Derivation]:
        out = []
        for t in kb_.triples:
            if t.relation == "IS_A" and t.object == "LIVING_INFLUENCE":
                out.append(Derivation(
                    "r_notable",
                    Triple(t.subject, "IS_A", "NOTABLE_FIGURE", "(derived)", -1),
                    [t], f"{t.subject} is a living influence",
                ))
        return out

    kb10 = _make_kb([
        ("Student", "TUTORED_BY", "Mentor"),
        ("Mentor",  "TUTORED_BY", "Sage"),
        # Sage has no DIED_DATE → presumed living influence
    ])
    custom_rules = [
        Rule("R1", r1_intellectual_descent, stratum=0),
        Rule("r_living_influence", r_living_influence, stratum=1),
        Rule("r_notable", r_notable, stratum=2),
    ]
    kb10_ext, _, stats10 = apply_all_rules_to_fixpoint(kb10, rules=custom_rules)
    notable = {
        t.subject for t in kb10_ext.triples
        if t.relation == "IS_A" and t.object == "NOTABLE_FIGURE"
    }
    print("Scenario 10: arbitrary higher strata (stratum-2 rule)")
    print(f"  Per-stratum iters:     {stats10['per_stratum']}")
    print(f"  NOTABLE_FIGURE:        {notable}")
    assert notable == {"Sage"}, f"FAIL: stratum-2 not dispatched: {notable}"
    assert 2 in stats10["per_stratum"], "FAIL: stratum 2 not recorded"
    print("  PASS: strata dispatched in ascending order")
    print()

    print("=" * 78)
    print("All stress-test assertions passed.")
    print("=" * 78)
    print()


if __name__ == "__main__":
    main()
    stress_test()
