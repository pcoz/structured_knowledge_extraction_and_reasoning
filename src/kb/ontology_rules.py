"""Compile an Ontology into Rule objects that the existing engine runs.

Translates each OWL-style axiom in `src/kb/ontology.py:Ontology` into
one or more rules in the shape that `apply_all_rules_to_fixpoint`
already consumes. The result: an ontology declared once becomes a
list of `Rule`s plugged into the same dispatcher as the hand-written
R1..R11.

What this gives us in practice: a declarative OWL surface for the
~70-80% of OWL constructs that fit a Horn / disjunctive /
stratified-negation engine. Class hierarchies close transitively
via fixpoint, inverse properties auto-propagate, disjointness
surfaces contradictions, domain/range emit class memberships.

What this does NOT give us: full description-logic subsumption,
cardinality restrictions, open-world semantics. Those need an
external DL reasoner — planned `src/kb/ontology_owl.py`.

Every generated rule:
  - Has a name prefixed `owl:` so it's distinguishable from hand-
    written rules in derivation logs.
  - Emits Derivations with a "since X therefore Y" explanation that
    names the OWL axiom that produced it.
  - Runs at stratum 0 (monotonic Horn) unless otherwise noted. The
    only stratum-1 rule is the disjointness contradiction check —
    not because it's negation-as-failure, but for symmetry with the
    rest of the negation-shaped tooling.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Engine types come from kb.query (KB, Triple) and kb.reason
# (Rule, Derivation). The ontology DSL is purely declarative data.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb.query import KB, Triple
from kb.reason import Rule, Derivation
from kb.ontology import Ontology


# ----------------------------------------------------------------------
# Public entry point.
# ----------------------------------------------------------------------


def compile_to_rules(ontology: Ontology) -> list[Rule]:
    """Translate an Ontology into a list of Rule objects.

    Order of generation is deterministic — same ontology produces the
    same rule list byte-for-byte across runs. Important for the
    project's "deterministic artifact" guarantee.

    Generated rules are independent: each can be added to or removed
    from the engine's RULES list without affecting any other.
    """
    rules: list[Rule] = []

    # Property characteristics — single-relation axioms.
    for prop in sorted(ontology.transitive_properties):
        rules.append(_compile_transitive(prop))
    for prop in sorted(ontology.symmetric_properties):
        rules.append(_compile_symmetric(prop))

    # Functional / inverse-functional emit CONFLICT_* facts rather
    # than positive new inferences. Stratum 0 because the consequent
    # is monotonic — they just mark violations for the conflict
    # resolution pass to consume.
    for prop in sorted(ontology.functional_properties):
        rules.append(_compile_functional(prop))
    for prop in sorted(ontology.inverse_functional_properties):
        rules.append(_compile_inverse_functional(prop))

    # Inverse properties — emit one rule per direction so callers
    # don't need to think about which way the existing facts go.
    for (p1, p2) in ontology.inverse_property_pairs:
        rules.append(_compile_inverse(p1, p2))
        rules.append(_compile_inverse(p2, p1))

    # Sub-property: r_sub(X,Y) → r_sup(X,Y).
    for (sub, sup) in ontology.sub_property_pairs:
        rules.append(_compile_sub_property(sub, sup))

    # Equivalent properties: bidirectional sub-property. Emitted as
    # two sub_property rules so transitive chains of equivalence
    # close naturally via fixpoint.
    for (p1, p2) in ontology.equivalent_property_pairs:
        rules.append(_compile_sub_property(p1, p2))
        rules.append(_compile_sub_property(p2, p1))

    # Class hierarchy: IS_A(X, child) → IS_A(X, parent).
    for (child, parent) in ontology.sub_class_pairs:
        rules.append(_compile_sub_class(child, parent))

    # Equivalent classes: bidirectional sub_class.
    for (c1, c2) in ontology.equivalent_class_pairs:
        rules.append(_compile_sub_class(c1, c2))
        rules.append(_compile_sub_class(c2, c1))

    # Disjoint classes: emit CONTRADICTION_DETECTED for any instance
    # in both classes. Stratum 0 — pure positive Horn rule, but the
    # consequent is a meta-fact that downstream code can inspect.
    for (c1, c2) in ontology.disjoint_class_pairs:
        rules.append(_compile_disjoint(c1, c2))

    # Domain / range — typed inference on subjects/objects of a
    # property. Reflects that any use of the property implies the
    # subject/object inhabits the domain/range class.
    for prop, cls in sorted(ontology.domain_constraints.items()):
        rules.append(_compile_domain(prop, cls))
    for prop, cls in sorted(ontology.range_constraints.items()):
        rules.append(_compile_range(prop, cls))

    return rules


# ----------------------------------------------------------------------
# Individual axiom compilers.
#
# Each takes the axiom's parameters and returns a single Rule whose
# `fn` closes over those parameters. Closure-based generation lets us
# emit cleanly-named, individually-removable rules without any
# stringified-code or eval shenanigans.
# ----------------------------------------------------------------------


def _compile_transitive(prop: str) -> Rule:
    """owl:TransitiveProperty(prop): r(X,Y) ∧ r(Y,Z) → r(X,Z).

    Same shape as the hand-written R8/R11 — closes the relation
    transitively. Fixpoint over multiple iterations handles deep
    chains."""
    rule_name = f"owl:TransitiveProperty({prop})"

    def fn(kb: KB) -> list[Derivation]:
        out: list[Derivation] = []
        # Iterate only the triples carrying this relation, via the
        # by_relation index, to avoid O(N) scans over the whole KB.
        for idx in kb.by_relation.get(prop, []):
            t1 = kb.triples[idx]
            for t2 in kb.out_facts(t1.object, prop):
                if t2.object == t1.subject:
                    # Self-loops in transitive closure are blocked
                    # for the same reason as R8: rarely meaningful,
                    # always introduce cycles in derived graphs.
                    continue
                derived = Triple(
                    t1.subject, prop, t2.object, "(derived)", -1,
                )
                expl = (
                    f"Since ({t1.subject}, {prop}, {t1.object}) and "
                    f"({t1.object}, {prop}, {t2.object}), therefore "
                    f"({t1.subject}, {prop}, {t2.object}) "
                    f"[by owl:TransitiveProperty({prop})]."
                )
                out.append(Derivation(rule_name, derived, [t1, t2], expl))
        return out

    return Rule(rule_name, fn, stratum=0)


def _compile_symmetric(prop: str) -> Rule:
    """owl:SymmetricProperty(prop): r(X,Y) → r(Y,X).

    Every directed edge implies the reverse edge. Fixpoint guards
    via the engine's seen-set ensure a single pass is enough — the
    second iteration finds no new facts."""
    rule_name = f"owl:SymmetricProperty({prop})"

    def fn(kb: KB) -> list[Derivation]:
        out: list[Derivation] = []
        for idx in kb.by_relation.get(prop, []):
            t = kb.triples[idx]
            if t.subject == t.object:
                # An A → A edge is trivially symmetric — skip to
                # avoid an extra dedup hit.
                continue
            derived = Triple(t.object, prop, t.subject, "(derived)", -1)
            expl = (
                f"Since ({t.subject}, {prop}, {t.object}), therefore "
                f"({t.object}, {prop}, {t.subject}) "
                f"[by owl:SymmetricProperty({prop})]."
            )
            out.append(Derivation(rule_name, derived, [t], expl))
        return out

    return Rule(rule_name, fn, stratum=0)


def _compile_inverse(p_from: str, p_to: str) -> Rule:
    """owl:inverseOf(p_from, p_to): r_from(X,Y) → r_to(Y,X).

    Emitted once per direction by compile_to_rules — calling code
    declares the pair once, and gets two rules implementing both
    directions of inference."""
    rule_name = f"owl:inverseOf({p_from},{p_to})"

    def fn(kb: KB) -> list[Derivation]:
        out: list[Derivation] = []
        for idx in kb.by_relation.get(p_from, []):
            t = kb.triples[idx]
            derived = Triple(t.object, p_to, t.subject, "(derived)", -1)
            expl = (
                f"Since ({t.subject}, {p_from}, {t.object}), therefore "
                f"({t.object}, {p_to}, {t.subject}) "
                f"[by owl:inverseOf({p_from},{p_to})]."
            )
            out.append(Derivation(rule_name, derived, [t], expl))
        return out

    return Rule(rule_name, fn, stratum=0)


def _compile_sub_property(sub: str, sup: str) -> Rule:
    """rdfs:subPropertyOf(sub, sup): r_sub(X,Y) → r_sup(X,Y).

    Any assertion of the more-specific property implies the more-
    general. Transitive chains of subPropertyOf close naturally via
    fixpoint — declare A subPropertyOf B subPropertyOf C and the
    engine derives A → C in a second iteration."""
    rule_name = f"rdfs:subPropertyOf({sub},{sup})"

    def fn(kb: KB) -> list[Derivation]:
        out: list[Derivation] = []
        for idx in kb.by_relation.get(sub, []):
            t = kb.triples[idx]
            derived = Triple(t.subject, sup, t.object, "(derived)", -1)
            expl = (
                f"Since ({t.subject}, {sub}, {t.object}) and {sub} is "
                f"a sub-property of {sup}, therefore "
                f"({t.subject}, {sup}, {t.object}) "
                f"[by rdfs:subPropertyOf({sub},{sup})]."
            )
            out.append(Derivation(rule_name, derived, [t], expl))
        return out

    return Rule(rule_name, fn, stratum=0)


def _compile_sub_class(child: str, parent: str) -> Rule:
    """rdfs:subClassOf(child, parent): IS_A(X, child) → IS_A(X, parent).

    Class membership is represented by the IS_A relation (matching
    the project's existing R6 convention). Chained subClassOf axioms
    (Philosopher ⊑ Person ⊑ Living) close transitively via fixpoint —
    each iteration walks one step up the hierarchy."""
    rule_name = f"rdfs:subClassOf({child},{parent})"

    def fn(kb: KB) -> list[Derivation]:
        out: list[Derivation] = []
        # Scan all IS_A triples for ones with `child` as the object —
        # those are instances of the child class.
        for idx in kb.by_relation.get("IS_A", []):
            t = kb.triples[idx]
            if t.object != child:
                continue
            derived = Triple(t.subject, "IS_A", parent, "(derived)", -1)
            expl = (
                f"Since {t.subject} IS_A {child}, and {child} is a "
                f"subclass of {parent}, therefore {t.subject} IS_A "
                f"{parent} [by rdfs:subClassOf({child},{parent})]."
            )
            out.append(Derivation(rule_name, derived, [t], expl))
        return out

    return Rule(rule_name, fn, stratum=0)


def _compile_disjoint(c1: str, c2: str) -> Rule:
    """owl:disjointWith(c1, c2): IS_A(X, c1) ∧ IS_A(X, c2) → CONTRADICTION.

    Emits a fact `(X, CONTRADICTION_DETECTED, "c1|c2")` for every
    instance found in both classes. Stratum 0 — pure positive Horn —
    even though the spirit is a constraint violation. The engine
    surfaces these for inspection rather than halting, which lets
    downstream code decide whether to reject, log, or repair."""
    rule_name = f"owl:disjointWith({c1},{c2})"
    flag = f"{c1}|{c2}"

    def fn(kb: KB) -> list[Derivation]:
        out: list[Derivation] = []
        # Build the set of instances of c1 once, then scan c2's
        # instances for overlap. Cheaper than a nested triple scan
        # when the classes are large.
        in_c1 = {
            kb.triples[idx].subject
            for idx in kb.by_relation.get("IS_A", [])
            if kb.triples[idx].object == c1
        }
        for idx in kb.by_relation.get("IS_A", []):
            t = kb.triples[idx]
            if t.object != c2 or t.subject not in in_c1:
                continue
            derived = Triple(
                t.subject, "CONTRADICTION_DETECTED", flag,
                "(derived)", -1,
            )
            expl = (
                f"{t.subject} is declared a member of both {c1} and "
                f"{c2}, which are disjoint "
                f"[by owl:disjointWith({c1},{c2})]."
            )
            # Include the matching c1-membership triple as an input
            # for full provenance — anyone reading the contradiction
            # can find both offending facts via the why-trace.
            c1_triples = [
                kb.triples[i]
                for i in kb.by_relation.get("IS_A", [])
                if kb.triples[i].subject == t.subject
                and kb.triples[i].object == c1
            ]
            inputs = c1_triples[:1] + [t]
            out.append(Derivation(rule_name, derived, inputs, expl))
        return out

    return Rule(rule_name, fn, stratum=0)


def _compile_domain(prop: str, cls: str) -> Rule:
    """rdfs:domain(prop, cls): r(X,Y) → IS_A(X, cls).

    Any use of `prop` implies its subject belongs to the domain
    class. Useful for typing entities that the extractor saw in
    relation position but never explicitly classified."""
    rule_name = f"rdfs:domain({prop},{cls})"

    def fn(kb: KB) -> list[Derivation]:
        out: list[Derivation] = []
        for idx in kb.by_relation.get(prop, []):
            t = kb.triples[idx]
            derived = Triple(t.subject, "IS_A", cls, "(derived)", -1)
            expl = (
                f"Since ({t.subject}, {prop}, {t.object}) and {prop} "
                f"has domain {cls}, therefore {t.subject} IS_A {cls} "
                f"[by rdfs:domain({prop},{cls})]."
            )
            out.append(Derivation(rule_name, derived, [t], expl))
        return out

    return Rule(rule_name, fn, stratum=0)


def _compile_range(prop: str, cls: str) -> Rule:
    """rdfs:range(prop, cls): r(X,Y) → IS_A(Y, cls)."""
    rule_name = f"rdfs:range({prop},{cls})"

    def fn(kb: KB) -> list[Derivation]:
        out: list[Derivation] = []
        for idx in kb.by_relation.get(prop, []):
            t = kb.triples[idx]
            derived = Triple(t.object, "IS_A", cls, "(derived)", -1)
            expl = (
                f"Since ({t.subject}, {prop}, {t.object}) and {prop} "
                f"has range {cls}, therefore {t.object} IS_A {cls} "
                f"[by rdfs:range({prop},{cls})]."
            )
            out.append(Derivation(rule_name, derived, [t], expl))
        return out

    return Rule(rule_name, fn, stratum=0)


def _compile_functional(prop: str) -> Rule:
    """owl:FunctionalProperty(prop): at most one value per subject.

    Emits `(X, CONFLICT_FUNCTIONAL, "prop:Y1|Y2")` for every pair
    (X, Y1), (X, Y2) where the same subject has two distinct values
    under the functional property. Triples whose validity intervals
    don't overlap are NOT flagged — a person can be CURRENT_EMPLOYER
    of two companies at different times without contradiction.

    Overlap is tested with `temporal.strictly_overlaps` (positive-duration
    overlap), so a clean value succession — one value ending exactly where
    the next begins (touching boundaries, Allen "meets") — is NOT flagged.
    Only genuinely co-valid pairs conflict. See
    `Ontology.functional_property` for the convention and rationale.

    src/kb/conflict.py consumes these markers and applies a
    resolution policy (LatestWins, HighestConfidence, etc.)."""
    rule_name = f"owl:FunctionalProperty({prop})"

    # Lazy import to avoid making temporal a hard dependency of
    # ontology_rules when the caller doesn't use functional props.
    from kb.temporal import interval_of, strictly_overlaps

    def fn(kb: KB) -> list[Derivation]:
        out: list[Derivation] = []
        emitted: set[tuple[str, str, str]] = set()
        # Group all triples of this property by subject. Cheaper than
        # double-scanning when the property has many triples.
        by_subject: dict[str, list[Triple]] = {}
        for idx in kb.by_relation.get(prop, []):
            t = kb.triples[idx]
            by_subject.setdefault(t.subject, []).append(t)
        for subj, ts in by_subject.items():
            if len(ts) < 2:
                continue
            for i, t1 in enumerate(ts):
                for t2 in ts[i + 1:]:
                    if t1.object == t2.object:
                        # Same value duplicated — not a conflict.
                        continue
                    # Temporal scope: only flag pairs that genuinely
                    # co-exist for a positive duration. Touching/"meets"
                    # boundaries (clean succession) are NOT a conflict;
                    # atemporal triples (both unbounded) overlap trivially.
                    if not strictly_overlaps(interval_of(t1), interval_of(t2)):
                        continue
                    pair = tuple(sorted([t1.object, t2.object]))
                    flag = f"{prop}:{pair[0]}|{pair[1]}"
                    key = (subj, "CONFLICT_FUNCTIONAL", flag)
                    if key in emitted:
                        continue
                    emitted.add(key)
                    derived = Triple(
                        subj, "CONFLICT_FUNCTIONAL", flag,
                        "(derived)", -1,
                    )
                    expl = (
                        f"{subj} has two distinct {prop} values "
                        f"({pair[0]} and {pair[1]}) with overlapping "
                        f"validity, violating "
                        f"owl:FunctionalProperty({prop})."
                    )
                    out.append(Derivation(rule_name, derived,
                                           [t1, t2], expl))
        return out

    return Rule(rule_name, fn, stratum=0)


def _compile_inverse_functional(prop: str) -> Rule:
    """owl:InverseFunctionalProperty(prop): at most one subject per value.

    Emits `(Y, CONFLICT_INVERSE_FUNCTIONAL, "prop:X1|X2")` for every
    pair of subjects sharing the same value. Same temporal-overlap
    scoping as the functional case."""
    rule_name = f"owl:InverseFunctionalProperty({prop})"

    from kb.temporal import interval_of, strictly_overlaps

    def fn(kb: KB) -> list[Derivation]:
        out: list[Derivation] = []
        emitted: set[tuple[str, str, str]] = set()
        # Group by object — same dedup pattern, inverted axis.
        by_object: dict[str, list[Triple]] = {}
        for idx in kb.by_relation.get(prop, []):
            t = kb.triples[idx]
            by_object.setdefault(t.object, []).append(t)
        for obj, ts in by_object.items():
            if len(ts) < 2:
                continue
            for i, t1 in enumerate(ts):
                for t2 in ts[i + 1:]:
                    if t1.subject == t2.subject:
                        continue
                    if not intersects(interval_of(t1), interval_of(t2)):
                        continue
                    pair = tuple(sorted([t1.subject, t2.subject]))
                    flag = f"{prop}:{pair[0]}|{pair[1]}"
                    key = (obj, "CONFLICT_INVERSE_FUNCTIONAL", flag)
                    if key in emitted:
                        continue
                    emitted.add(key)
                    derived = Triple(
                        obj, "CONFLICT_INVERSE_FUNCTIONAL", flag,
                        "(derived)", -1,
                    )
                    expl = (
                        f"{obj} is shared by two distinct subjects "
                        f"({pair[0]} and {pair[1]}) under {prop} with "
                        f"overlapping validity, violating "
                        f"owl:InverseFunctionalProperty({prop})."
                    )
                    out.append(Derivation(rule_name, derived,
                                           [t1, t2], expl))
        return out

    return Rule(rule_name, fn, stratum=0)
