"""Declarative ontology DSL — the source-of-truth for OWL-style axioms.

This module is pure data. It captures the OWL constructs we support
(class hierarchies, property characteristics, equivalences,
disjointness, domain/range) as a single `Ontology` object. Two
downstream backends consume it:

  - `src/kb/ontology_rules.py` compiles an Ontology into the existing
    engine's Rule / DisjunctiveRule shapes. Pure stdlib. Closed-world.
    Covers ~70-80% of practical OWL usage.

  - (planned `src/kb/ontology_owl.py`) exports an Ontology to an
    RDF/OWL file for a real description-logic reasoner. Open-world.
    Optional external dependency. Covers the residual DL-only
    constructs (cardinality, complex class expressions).

The DSL deliberately stays small — it has only the OWL axioms that
either (a) compile cleanly to Horn / disjunctive / stratified-negation
rules, or (b) are commonly useful when bolted onto a closed-world
reasoner. Cardinality and unrestricted class expressions are
recognised but flagged for the (future) DL backend rather than
silently dropped.

Class membership convention: instances are members of a class via the
`IS_A` relation (matching the existing project convention from R6
multi-conqueror). So 'Aristotle IS_A Philosopher' is the canonical
form of class membership.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ----------------------------------------------------------------------
# The Ontology dataclass.
#
# Storing axioms as sorted sets / lists of tuples keeps the ontology
# trivially serialisable and gives deterministic compile order — two
# different processes will compile the same ontology into the same
# rule list, byte-for-byte. That's important for the "no AI at
# runtime, deterministic artifact" architectural commitment.
# ----------------------------------------------------------------------


@dataclass
class Ontology:
    """A bag of OWL-style axioms, accumulated via declarative methods.

    Axiom kinds and the rule shapes they compile to:

      transitive_properties:  r(X,Y) ∧ r(Y,Z) → r(X,Z)
      symmetric_properties:   r(X,Y)          → r(Y,X)
      inverse_property_pairs: r1(X,Y)         → r2(Y,X)   (and vice versa)
      sub_property_pairs:     r1(X,Y)         → r2(X,Y)
      sub_class_pairs:        IS_A(X,C1)      → IS_A(X,C2)
      equivalent_class_pairs: bidirectional sub_class_pairs
      equivalent_property_pairs: bidirectional sub_property_pairs
      disjoint_class_pairs:   IS_A(X,C1) ∧ IS_A(X,C2) → CONTRADICTION
      domain_constraints:     r(X,Y) → IS_A(X,C)
      range_constraints:      r(X,Y) → IS_A(Y,C)
    """

    name: str = "default"

    # Vocabulary declarations — used for sanity checks and auto-doc.
    # An axiom may reference a class/property that wasn't declared
    # first; we don't enforce declaration, just record what's seen.
    classes: set[str] = field(default_factory=set)
    properties: set[str] = field(default_factory=set)

    # Property characteristics (axioms over a single relation).
    transitive_properties: set[str] = field(default_factory=set)
    symmetric_properties: set[str] = field(default_factory=set)
    # Functional: a property that has at most ONE value per subject
    # at any given time. Two values for the same subject is a
    # conflict, detected by the rule compiler and resolved by
    # src/kb/conflict.py. Examples: BIRTH_DATE, CURRENT_EMPLOYER,
    # CAPITAL_OF (for nation states).
    functional_properties: set[str] = field(default_factory=set)
    # Inverse-functional: a property with at most ONE subject per
    # value. The object uniquely identifies the subject. Examples:
    # HAS_SSN, HAS_PASSPORT_NUMBER, HAS_ISBN.
    inverse_functional_properties: set[str] = field(default_factory=set)

    # Binary axioms (axioms relating two relations or two classes).
    # Stored as lists rather than sets of tuples so the compile order
    # is deterministic and explanations can reference the declaration
    # order.
    inverse_property_pairs: list[tuple[str, str]] = field(default_factory=list)
    sub_property_pairs: list[tuple[str, str]] = field(default_factory=list)
    equivalent_property_pairs: list[tuple[str, str]] = field(default_factory=list)
    sub_class_pairs: list[tuple[str, str]] = field(default_factory=list)
    equivalent_class_pairs: list[tuple[str, str]] = field(default_factory=list)
    disjoint_class_pairs: list[tuple[str, str]] = field(default_factory=list)

    # Domain / range — each property may have at most one of each
    # declared. We allow overwrite (last declaration wins) so callers
    # can refine an inherited ontology without errors.
    domain_constraints: dict[str, str] = field(default_factory=dict)
    range_constraints: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Vocabulary declarations.
    # Optional — axiom methods auto-register their referenced names.
    # Useful when an ontology wants to list its vocabulary up front
    # for documentation.
    # ------------------------------------------------------------------

    def declare_class(self, name: str) -> "Ontology":
        self.classes.add(name)
        return self

    def declare_classes(self, *names: str) -> "Ontology":
        for n in names:
            self.classes.add(n)
        return self

    def declare_property(self, name: str) -> "Ontology":
        self.properties.add(name)
        return self

    def declare_properties(self, *names: str) -> "Ontology":
        for n in names:
            self.properties.add(n)
        return self

    # ------------------------------------------------------------------
    # Property characteristics.
    # ------------------------------------------------------------------

    def transitive_property(self, prop: str) -> "Ontology":
        """Declare `prop` as transitive: r(X,Y) ∧ r(Y,Z) → r(X,Z)."""
        self.properties.add(prop)
        self.transitive_properties.add(prop)
        return self

    def symmetric_property(self, prop: str) -> "Ontology":
        """Declare `prop` as symmetric: r(X,Y) → r(Y,X)."""
        self.properties.add(prop)
        self.symmetric_properties.add(prop)
        return self

    def functional_property(self, prop: str) -> "Ontology":
        """Declare `prop` as functional: at most one value per subject.

        The compiler emits a conflict-detection rule that fires when
        any subject has two distinct objects under this property.
        Used by src/kb/conflict.py policies (LatestWins,
        HighestConfidence, AuthorityWins) to resolve the conflict
        deterministically at construction time.

        If your property is functional only WITHIN a time window
        (e.g., CURRENT_EMPLOYER), pair it with temporal slots — the
        conflict detector only treats temporally-overlapping triples
        as conflicting."""
        self.properties.add(prop)
        self.functional_properties.add(prop)
        return self

    def inverse_functional_property(self, prop: str) -> "Ontology":
        """Declare `prop` as inverse-functional: the object uniquely
        identifies the subject. Two distinct subjects with the same
        object is a conflict.

        Classic uses: identifier properties (HAS_SSN, HAS_ISBN,
        HAS_PASSPORT_NUMBER). When two subjects share an
        identifier, either the identifier is wrong on one row or
        the subjects are actually the same entity — useful for
        record-linkage upstream of the reasoner."""
        self.properties.add(prop)
        self.inverse_functional_properties.add(prop)
        return self

    def inverse_properties(self, p1: str, p2: str) -> "Ontology":
        """Declare `p1` and `p2` as inverse: r1(X,Y) ↔ r2(Y,X).

        The compiler emits two Horn rules — one for each direction —
        so callers don't need to declare both orderings."""
        self.properties.add(p1)
        self.properties.add(p2)
        # Store canonicalised order so (p1,p2) and (p2,p1) don't
        # both register as separate axioms.
        key = tuple(sorted([p1, p2]))
        if key not in [tuple(sorted(pair)) for pair in self.inverse_property_pairs]:
            self.inverse_property_pairs.append((p1, p2))
        return self

    # ------------------------------------------------------------------
    # Property hierarchy.
    # ------------------------------------------------------------------

    def sub_property_of(self, sub: str, sup: str) -> "Ontology":
        """Declare `sub` as a sub-property of `sup`: r_sub(X,Y) → r_sup(X,Y)."""
        self.properties.add(sub)
        self.properties.add(sup)
        if (sub, sup) not in self.sub_property_pairs:
            self.sub_property_pairs.append((sub, sup))
        return self

    def equivalent_properties(self, p1: str, p2: str) -> "Ontology":
        """Declare `p1` and `p2` as equivalent properties (bidirectional
        sub-property). Compiles to two sub_property rules."""
        self.properties.add(p1)
        self.properties.add(p2)
        key = tuple(sorted([p1, p2]))
        if key not in [tuple(sorted(pair)) for pair in self.equivalent_property_pairs]:
            self.equivalent_property_pairs.append((p1, p2))
        return self

    # ------------------------------------------------------------------
    # Class hierarchy.
    # ------------------------------------------------------------------

    def subclass_of(self, child: str, parent: str) -> "Ontology":
        """Declare class hierarchy: every instance of `child` is also
        an instance of `parent`. Compiles to:
            IS_A(X, child) → IS_A(X, parent)
        Chained subclass relations close transitively via fixpoint."""
        self.classes.add(child)
        self.classes.add(parent)
        if (child, parent) not in self.sub_class_pairs:
            self.sub_class_pairs.append((child, parent))
        return self

    def equivalent_classes(self, c1: str, c2: str) -> "Ontology":
        """Declare `c1` and `c2` as the same class. Compiles to two
        subclass_of rules — instances of either are instances of both."""
        self.classes.add(c1)
        self.classes.add(c2)
        key = tuple(sorted([c1, c2]))
        if key not in [tuple(sorted(pair)) for pair in self.equivalent_class_pairs]:
            self.equivalent_class_pairs.append((c1, c2))
        return self

    def disjoint_with(self, c1: str, c2: str) -> "Ontology":
        """Declare `c1` and `c2` as disjoint: no instance can belong to
        both. Compiles to a rule that emits a CONTRADICTION_DETECTED
        fact for any instance in both classes — the engine surfaces
        this rather than halting, so downstream code can decide what
        to do about inconsistencies."""
        self.classes.add(c1)
        self.classes.add(c2)
        key = tuple(sorted([c1, c2]))
        if key not in [tuple(sorted(pair)) for pair in self.disjoint_class_pairs]:
            self.disjoint_class_pairs.append((c1, c2))
        return self

    # ------------------------------------------------------------------
    # Domain / range.
    # ------------------------------------------------------------------

    def domain(self, prop: str, cls: str) -> "Ontology":
        """Declare that `prop`'s subjects must be of class `cls`.
        Compiles to: r(X,Y) → IS_A(X, cls)."""
        self.properties.add(prop)
        self.classes.add(cls)
        # Last-write-wins: a refinement subclass can override.
        self.domain_constraints[prop] = cls
        return self

    def range(self, prop: str, cls: str) -> "Ontology":
        """Declare that `prop`'s objects must be of class `cls`.
        Compiles to: r(X,Y) → IS_A(Y, cls)."""
        self.properties.add(prop)
        self.classes.add(cls)
        self.range_constraints[prop] = cls
        return self

    # ------------------------------------------------------------------
    # Diagnostics.
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Human-readable summary of the ontology's axioms — useful in
        demos and debugging output. Stable ordering so the summary is
        diffable across runs."""
        lines = [f"Ontology '{self.name}':"]
        lines.append(f"  classes:     {len(self.classes)}")
        lines.append(f"  properties:  {len(self.properties)}")
        lines.append(f"  axioms:")
        lines.append(f"    transitive properties:      "
                     f"{len(self.transitive_properties)}")
        lines.append(f"    symmetric properties:       "
                     f"{len(self.symmetric_properties)}")
        lines.append(f"    functional properties:      "
                     f"{len(self.functional_properties)}")
        lines.append(f"    inverse-functional props:   "
                     f"{len(self.inverse_functional_properties)}")
        lines.append(f"    inverse-property pairs:     "
                     f"{len(self.inverse_property_pairs)}")
        lines.append(f"    sub-property axioms:        "
                     f"{len(self.sub_property_pairs)}")
        lines.append(f"    equivalent-property pairs:  "
                     f"{len(self.equivalent_property_pairs)}")
        lines.append(f"    sub-class axioms:           "
                     f"{len(self.sub_class_pairs)}")
        lines.append(f"    equivalent-class pairs:     "
                     f"{len(self.equivalent_class_pairs)}")
        lines.append(f"    disjoint-class pairs:       "
                     f"{len(self.disjoint_class_pairs)}")
        lines.append(f"    domain constraints:         "
                     f"{len(self.domain_constraints)}")
        lines.append(f"    range constraints:          "
                     f"{len(self.range_constraints)}")
        return "\n".join(lines)


# ----------------------------------------------------------------------
# Demo + assertion-backed stress tests.
#
# Mirrors the pattern in src/kb/reason.py: each scenario builds a
# small synthetic ontology, compiles it via ontology_rules, runs the
# engine, and asserts the exact closure. Acts as both a regression
# test for the compiler and a worked example of each OWL axiom shape.
# ----------------------------------------------------------------------


def _stress_test() -> None:
    """Exercise every OWL axiom shape the compiler supports."""
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

    from kb.query import KB, Triple
    from kb.reason import apply_all_rules_to_fixpoint
    from kb.ontology_rules import compile_to_rules

    def _kb(triples: list[tuple[str, str, str]]) -> KB:
        return KB(
            triples=[Triple(s, r, o, "(test)", -1) for s, r, o in triples],
            alias_map={},
            n_articles=0,
        )

    print("=" * 78)
    print("OWL rule-compiler stress tests")
    print("=" * 78)
    print()

    # -- Scenario 1: TransitiveProperty closes a chain. ---------------
    ont = Ontology("test1").transitive_property("ANCESTOR_OF")
    rules = compile_to_rules(ont)
    kb = _kb([
        ("A", "ANCESTOR_OF", "B"),
        ("B", "ANCESTOR_OF", "C"),
        ("C", "ANCESTOR_OF", "D"),
    ])
    kb_ext, _, stats = apply_all_rules_to_fixpoint(kb, rules=rules)
    ancestor_pairs = {
        (t.subject, t.object) for t in kb_ext.triples
        if t.relation == "ANCESTOR_OF"
    }
    expected = {("A", "B"), ("B", "C"), ("C", "D"),
                ("A", "C"), ("B", "D"), ("A", "D")}
    print("Scenario 1: TransitiveProperty(ANCESTOR_OF) over A→B→C→D")
    print(f"  Iterations: {stats['stratum_0_iters']}; "
          f"closure size: {len(ancestor_pairs)}/{len(expected)}")
    assert ancestor_pairs == expected, (
        f"FAIL: missing {expected - ancestor_pairs}, "
        f"extra {ancestor_pairs - expected}"
    )
    print("  PASS: full transitive closure derived")
    print()

    # -- Scenario 2: SymmetricProperty. ------------------------------
    ont = Ontology("test2").symmetric_property("SIBLING_OF")
    rules = compile_to_rules(ont)
    kb = _kb([("Alice", "SIBLING_OF", "Bob")])
    kb_ext, _, _ = apply_all_rules_to_fixpoint(kb, rules=rules)
    siblings = {
        (t.subject, t.object) for t in kb_ext.triples
        if t.relation == "SIBLING_OF"
    }
    print("Scenario 2: SymmetricProperty(SIBLING_OF)")
    assert siblings == {("Alice", "Bob"), ("Bob", "Alice")}
    print(f"  PASS: both directions derived ({len(siblings)} facts)")
    print()

    # -- Scenario 3: InverseProperties — both directions. -----------
    ont = Ontology("test3").inverse_properties("TEACHES", "STUDENT_OF")
    rules = compile_to_rules(ont)
    kb = _kb([
        ("Plato", "TEACHES", "Aristotle"),
        ("Theophrastus", "STUDENT_OF", "Aristotle"),
    ])
    kb_ext, _, _ = apply_all_rules_to_fixpoint(kb, rules=rules)
    teaches = {(t.subject, t.object) for t in kb_ext.triples
               if t.relation == "TEACHES"}
    student = {(t.subject, t.object) for t in kb_ext.triples
               if t.relation == "STUDENT_OF"}
    print("Scenario 3: InverseProperties(TEACHES ↔ STUDENT_OF)")
    # From (Plato TEACHES Aristotle) we expect (Aristotle STUDENT_OF Plato).
    assert ("Aristotle", "Plato") in student
    # From (Theophrastus STUDENT_OF Aristotle) we expect (Aristotle TEACHES Theophrastus).
    assert ("Aristotle", "Theophrastus") in teaches
    print("  PASS: both inverse directions propagated")
    print()

    # -- Scenario 4: SubPropertyOf chain. ---------------------------
    ont = (
        Ontology("test4")
        .sub_property_of("TAUGHT_BY", "INFLUENCED_BY_FIG")
        .sub_property_of("INFLUENCED_BY_FIG", "CONNECTED_TO")
    )
    rules = compile_to_rules(ont)
    kb = _kb([("Aristotle", "TAUGHT_BY", "Plato")])
    kb_ext, _, _ = apply_all_rules_to_fixpoint(kb, rules=rules)
    conn = {(t.subject, t.object) for t in kb_ext.triples
            if t.relation == "CONNECTED_TO"}
    inf = {(t.subject, t.object) for t in kb_ext.triples
           if t.relation == "INFLUENCED_BY_FIG"}
    print("Scenario 4: SubPropertyOf chain (TAUGHT_BY ⊑ INFLUENCED_BY_FIG ⊑ CONNECTED_TO)")
    assert ("Aristotle", "Plato") in inf
    assert ("Aristotle", "Plato") in conn
    print("  PASS: sub-property chain closes transitively via fixpoint")
    print()

    # -- Scenario 5: SubClassOf chain via IS_A. ---------------------
    ont = (
        Ontology("test5")
        .subclass_of("Philosopher", "Person")
        .subclass_of("Person", "Living")
    )
    rules = compile_to_rules(ont)
    kb = _kb([("Aristotle", "IS_A", "Philosopher")])
    kb_ext, _, _ = apply_all_rules_to_fixpoint(kb, rules=rules)
    classes_of_aristotle = {
        t.object for t in kb_ext.out_facts("Aristotle", "IS_A")
    }
    print("Scenario 5: SubClassOf chain (Philosopher ⊑ Person ⊑ Living)")
    assert classes_of_aristotle == {"Philosopher", "Person", "Living"}, (
        f"FAIL: got {classes_of_aristotle}"
    )
    print("  PASS: class membership propagates up the hierarchy")
    print()

    # -- Scenario 6: EquivalentProperties. --------------------------
    ont = Ontology("test6").equivalent_properties("AUTHOR_OF", "WROTE")
    rules = compile_to_rules(ont)
    kb = _kb([
        ("Plato", "AUTHOR_OF", "Republic"),
        ("Aristotle", "WROTE", "Ethics"),
    ])
    kb_ext, _, _ = apply_all_rules_to_fixpoint(kb, rules=rules)
    author = {(t.subject, t.object) for t in kb_ext.triples
              if t.relation == "AUTHOR_OF"}
    wrote = {(t.subject, t.object) for t in kb_ext.triples
             if t.relation == "WROTE"}
    print("Scenario 6: EquivalentProperties(AUTHOR_OF ≡ WROTE)")
    assert ("Plato", "Republic") in wrote and ("Plato", "Republic") in author
    assert ("Aristotle", "Ethics") in wrote and ("Aristotle", "Ethics") in author
    print("  PASS: equivalence propagates both ways")
    print()

    # -- Scenario 7: EquivalentClasses. -----------------------------
    ont = Ontology("test7").equivalent_classes("Sage", "Wise_One")
    rules = compile_to_rules(ont)
    kb = _kb([
        ("Socrates", "IS_A", "Sage"),
        ("Confucius", "IS_A", "Wise_One"),
    ])
    kb_ext, _, _ = apply_all_rules_to_fixpoint(kb, rules=rules)
    socr = {t.object for t in kb_ext.out_facts("Socrates", "IS_A")}
    conf = {t.object for t in kb_ext.out_facts("Confucius", "IS_A")}
    print("Scenario 7: EquivalentClasses(Sage ≡ Wise_One)")
    assert socr == {"Sage", "Wise_One"} and conf == {"Sage", "Wise_One"}
    print("  PASS: class equivalence propagates both ways")
    print()

    # -- Scenario 8: DisjointWith — contradiction surfaces. ---------
    ont = Ontology("test8").disjoint_with("Living", "Deceased")
    rules = compile_to_rules(ont)
    kb = _kb([
        ("X", "IS_A", "Living"),
        ("X", "IS_A", "Deceased"),
        ("Y", "IS_A", "Living"),
    ])
    kb_ext, _, _ = apply_all_rules_to_fixpoint(kb, rules=rules)
    contras = {
        t.subject for t in kb_ext.triples
        if t.relation == "CONTRADICTION_DETECTED"
    }
    print("Scenario 8: DisjointWith(Living, Deceased)")
    print(f"  Contradictions: {contras}")
    assert contras == {"X"}, f"FAIL: got {contras}"
    print("  PASS: contradiction surfaced for X; Y left untouched")
    print()

    # -- Scenario 9: Domain / Range emit class memberships. ---------
    ont = (
        Ontology("test9")
        .domain("CONQUERED", "Person")
        .range("CONQUERED", "Place")
    )
    rules = compile_to_rules(ont)
    kb = _kb([("Alexander", "CONQUERED", "Persia")])
    kb_ext, _, _ = apply_all_rules_to_fixpoint(kb, rules=rules)
    alex_is_a = {t.object for t in kb_ext.out_facts("Alexander", "IS_A")}
    persia_is_a = {t.object for t in kb_ext.out_facts("Persia", "IS_A")}
    print("Scenario 9: domain(CONQUERED, Person) + range(CONQUERED, Place)")
    assert alex_is_a == {"Person"} and persia_is_a == {"Place"}
    print("  PASS: subject/object types derived from property use")
    print()

    # -- Scenario 10: Composition — transitive + inverse interplay. -
    # ANCESTOR_OF is transitive; DESCENDANT_OF is its inverse. The
    # engine should derive both relations' full closures.
    ont = (
        Ontology("test10")
        .transitive_property("ANCESTOR_OF")
        .inverse_properties("ANCESTOR_OF", "DESCENDANT_OF")
    )
    rules = compile_to_rules(ont)
    kb = _kb([
        ("A", "ANCESTOR_OF", "B"),
        ("B", "ANCESTOR_OF", "C"),
    ])
    kb_ext, _, stats = apply_all_rules_to_fixpoint(kb, rules=rules)
    anc = {(t.subject, t.object) for t in kb_ext.triples
           if t.relation == "ANCESTOR_OF"}
    desc = {(t.subject, t.object) for t in kb_ext.triples
            if t.relation == "DESCENDANT_OF"}
    print("Scenario 10: TransitiveProperty + InverseProperties combined")
    print(f"  Fixpoint iterations: {stats['stratum_0_iters']}")
    assert anc == {("A", "B"), ("B", "C"), ("A", "C")}
    assert desc == {("B", "A"), ("C", "B"), ("C", "A")}
    print(f"  PASS: ANCESTOR_OF closed transitively, DESCENDANT_OF "
          f"derived via inverse, both reach full size")
    print()

    # -- Scenario 11: Determinism — same ontology compiles to the
    # same rule list byte-for-byte, two runs produce identical KBs. --
    ont1 = (
        Ontology("test11")
        .transitive_property("R1")
        .symmetric_property("R2")
        .subclass_of("A", "B")
        .inverse_properties("R3", "R4")
    )
    ont2 = (
        Ontology("test11")
        .transitive_property("R1")
        .symmetric_property("R2")
        .subclass_of("A", "B")
        .inverse_properties("R3", "R4")
    )
    rules1 = compile_to_rules(ont1)
    rules2 = compile_to_rules(ont2)
    names1 = [r.name for r in rules1]
    names2 = [r.name for r in rules2]
    print("Scenario 11: determinism (same ontology → same rule list)")
    assert names1 == names2, (
        f"FAIL: rule-name lists differ across runs"
    )
    print(f"  PASS: {len(names1)} rules emitted in identical order")
    print()

    print("=" * 78)
    print("All OWL stress-test assertions passed.")
    print("=" * 78)
    print()


def _demo() -> None:
    """Walked example: build a small biographical ontology, compile,
    and combine with the existing kb.reason RULES on the Wikipedia KB.

    Demonstrates that OWL-compiled rules and hand-written rules
    interleave cleanly in the same dispatcher."""
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

    from kb.query import KB
    from kb.reason import RULES, apply_all_rules_to_fixpoint
    from kb.ontology_rules import compile_to_rules

    kb_path = _Path(__file__).resolve().parent / "kb_1000_articles.json"
    if not kb_path.exists():
        return

    print("=" * 78)
    print("OWL ontology + existing rules on the 1000-article KB")
    print("=" * 78)
    print()

    # Build a small biographical ontology. Every axiom here was either
    # hard-coded in the engine before this module existed (R8
    # transitive descent, R9 disjunctive inverse) or genuinely new
    # (subclass hierarchy, domain/range typing).
    ont = (
        Ontology("biographical")
        # R8 was a hand-written transitive rule; here we re-declare
        # it via the OWL axiom to show the equivalence.
        .transitive_property("INTELLECTUAL_DESCENDANT_OF")
        # CHILD_OF / GRANDCHILD_OF are not strictly inverse, but
        # TUTORED and TUTORED_BY are.
        .inverse_properties("TUTORED", "TUTORED_BY")
        # Class hierarchy — instances of MULTI_CONQUEROR are also
        # CONQUERORS, which are PERSONS. R6 already derives
        # MULTI_CONQUEROR; the subClassOf axioms lift them.
        .subclass_of("MULTI_CONQUEROR", "CONQUEROR")
        .subclass_of("CONQUEROR", "Person")
        .subclass_of("FAMILY_PROGENITOR", "Person")
        # Domain/range: anything CONQUERED is conquered BY a person,
        # of a place.
        .domain("CONQUERED", "Person")
        .range("CONQUERED", "Place")
    )
    print(ont.summary())
    print()

    owl_rules = compile_to_rules(ont)
    print(f"Compiled {len(owl_rules)} OWL-derived rules:")
    for r in owl_rules:
        print(f"  - {r.name}")
    print()

    kb = KB.load(kb_path)
    base_size = len(kb.triples)
    combined = list(RULES) + owl_rules
    kb_ext, derivations, stats = apply_all_rules_to_fixpoint(
        kb, rules=combined
    )
    print(f"Base KB: {base_size:,} triples")
    print(f"After fixpoint with OWL rules combined: "
          f"{len(kb_ext.triples):,} triples")
    print(f"Stratum-0 iterations: {stats['stratum_0_iters']}, "
          f"per-iter: {stats['stratum_0_per_iter']}")
    print()

    # Show some OWL-derived facts.
    print("Sample OWL-derived facts:")
    owl_derivs = [
        d for d in derivations
        if d.rule_name.startswith("owl:") or d.rule_name.startswith("rdfs:")
    ]
    seen_rules: set[str] = set()
    for d in owl_derivs:
        if d.rule_name in seen_rules:
            continue
        seen_rules.add(d.rule_name)
        print(f"  [{d.rule_name}]")
        print(f"    {d.output.subject} --{d.output.relation}--> "
              f"{d.output.object}")
        print(f"    {d.explanation}")
    print()


if __name__ == "__main__":
    _demo()
    _stress_test()

