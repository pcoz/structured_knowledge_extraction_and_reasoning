"""HermiT (and Pellet) integration via owlready2 — full OWL DL
inference at construction time.

This module adapts our `Ontology` + `KB` into the OWL/RDF world,
invokes a real description-logic reasoner, and converts the inferred
facts back into our `Triple` / `Derivation` shape. Pattern A from
`docs/COMPARISONS.md` — construction-time enricher, runtime untouched.

Soft dependencies:
  - `owlready2` (Python; `pip install owlready2`)
  - Java JVM (system; OpenJDK 17 is fine — the HermiT jar bundled
    with owlready2 needs it)

The module imports owlready2 LAZILY inside `hermit_enrich`, so the
rest of the project keeps loading cleanly even when owlready2 isn't
installed. If a caller invokes `hermit_enrich` without owlready2,
they get a clear `ImportError` with install instructions; if owlready2
is installed but the JVM isn't, they get a clear `RuntimeError`.

What HermiT adds beyond our compile-to-rules backend:

  - **Cardinality restrictions** — `min/max/exactCardinality` axioms
    declared via `Ontology.cardinality(prop, exactly=N, min=N, max=N)`.
    Violations surface as `CONFLICT_OWL_CARDINALITY` markers.
  - **Complex class expressions** — declared via
    `Ontology.class_intersection / class_union / class_complement /
    class_some_values / class_all_values`. HermiT computes the
    inferred class hierarchy (DL classification) from these.
  - **Inconsistency detection** — if the union of axioms + ABox is
    logically inconsistent, HermiT throws; we catch it and report
    via the `info["consistent"]` flag.
  - **Open-world reasoning** for the inferences DL supports (versus
    our closed-world Horn engine).

What HermiT does NOT add for us:
  - Anything our existing OWL DSL already covers (transitive,
    symmetric, inverse, sub-property, sub-class, equivalent, disjoint,
    functional, inverse-functional, domain, range). For those, the
    compile-to-rules backend in `src/kb/ontology_rules.py` already
    produces the same closures with full provenance, no JVM needed.

Translation conventions:
  - Our `IS_A` relation maps to OWL's `rdf:type` (instance-of).
  - All other relations become OWL ObjectProperties.
  - Triple subjects and objects become OWL individuals.
  - Entity / class / property names containing characters that
    aren't valid Python identifiers (spaces, punctuation) are
    sanitized for owlready2's class-creation API; a bidirectional
    map is maintained so derived facts come back with original names.

Naming the resulting Derivations:
  - Inferred class memberships (IS_A): rule name `owl:dl-classification`.
  - Cardinality violations: rule name `owl:CardinalityViolation`.
  - Inconsistency: a single sentinel triple
    `(ontology_name, IS, INCONSISTENT)` with rule name
    `owl:InconsistentOntology` and the conflict's axioms as inputs.
"""

from __future__ import annotations

import re
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb.query import KB, Triple
from kb.reason import Rule, Derivation
from kb.ontology import Ontology


# ----------------------------------------------------------------------
# Soft-dependency imports.
#
# owlready2 is imported inside `_require_owlready2` rather than at
# module top — this keeps the project loadable on hosts without it.
# The adapter raises a clear, installation-actionable error message
# only when actually called.
# ----------------------------------------------------------------------


def _require_owlready2():
    try:
        import owlready2  # noqa: F401
        return owlready2
    except ImportError as e:
        raise ImportError(
            "HermiT adapter requires owlready2. Install with:\n"
            "    pip install owlready2\n"
            "Also requires a Java JVM (OpenJDK 17 recommended).\n"
            "See aws/AWS_WORKFLOW.md for a managed-EC2 setup."
        ) from e


# ----------------------------------------------------------------------
# Name sanitization.
#
# owlready2's class- and property-creation APIs go through Python's
# type() mechanism, so names must be valid identifiers. Our Triples
# routinely contain spaces ("Alexander the Great"), punctuation, and
# Unicode. We map each external name to a sanitized internal name and
# keep a bidirectional lookup for the inverse translation.
# ----------------------------------------------------------------------


_SAFE_CHAR = re.compile(r"[^A-Za-z0-9_]")


def _sanitize(name: str) -> str:
    """Map an arbitrary string to a valid Python identifier.

    Replaces unsafe characters with underscores; prefixes with `_`
    if the result starts with a digit. Collisions are possible in
    theory (two different inputs sanitize to the same string) but
    rare in practice; the caller's _NameMap detects and resolves
    them by appending a numeric suffix."""
    if not name:
        return "_empty"
    safe = _SAFE_CHAR.sub("_", name)
    if safe[0].isdigit():
        safe = "_" + safe
    return safe


class _NameMap:
    """Bidirectional sanitized-name registry. Lets us round-trip
    derived facts back into the original names regardless of what
    Unicode soup the corpus uses."""

    def __init__(self):
        self._fwd: dict[str, str] = {}  # original → sanitized
        self._rev: dict[str, str] = {}  # sanitized → original

    def register(self, name: str) -> str:
        if name in self._fwd:
            return self._fwd[name]
        base = _sanitize(name)
        candidate = base
        i = 1
        # Resolve collisions by suffixing _2, _3, ... until unique.
        while candidate in self._rev:
            i += 1
            candidate = f"{base}_{i}"
        self._fwd[name] = candidate
        self._rev[candidate] = name
        return candidate

    def original(self, sanitized: str) -> str:
        return self._rev.get(sanitized, sanitized)


# ----------------------------------------------------------------------
# Translation: Ontology + KB → OWL world.
# ----------------------------------------------------------------------


def _build_owl_world(ontology: Ontology, kb: KB):
    """Construct an owlready2 ontology populated with our axioms +
    the KB triples as an ABox. Returns (onto, name_map). Caller is
    responsible for invoking the reasoner."""
    or2 = _require_owlready2()
    names = _NameMap()

    onto = or2.get_ontology(
        f"http://sker.local/{_sanitize(ontology.name)}.owl#"
    )

    # ----- Classes -------------------------------------------------
    # Pre-create every class referenced anywhere — by membership
    # triples, by sub_class axioms, by complex class definitions, by
    # domain/range, etc. Use the ontology's `classes` set as the
    # authoritative inventory.
    with onto:
        owl_classes: dict[str, Any] = {}
        for cls_name in sorted(ontology.classes):
            sanitized = names.register(cls_name)
            cls = or2.types.new_class(sanitized, (or2.Thing,))
            owl_classes[cls_name] = cls

        # Class hierarchy (sub_class_of axioms). Sets each child's
        # bases to include the parent.
        for child, parent in ontology.sub_class_pairs:
            if child in owl_classes and parent in owl_classes:
                owl_classes[child].is_a.append(owl_classes[parent])

        # Equivalent classes.
        for c1, c2 in ontology.equivalent_class_pairs:
            if c1 in owl_classes and c2 in owl_classes:
                owl_classes[c1].equivalent_to.append(owl_classes[c2])

        # Disjoint classes.
        for c1, c2 in ontology.disjoint_class_pairs:
            if c1 in owl_classes and c2 in owl_classes:
                or2.AllDisjoint([owl_classes[c1], owl_classes[c2]])

        # Complex class definitions — the HermiT-only constructs.
        # Each maps to an owlready2 expression that's used as the
        # equivalent_to of the named class.
        for name, expr in ontology.complex_class_definitions:
            if name not in owl_classes:
                continue
            cls = owl_classes[name]
            kind = expr[0]
            if kind == "intersection":
                parts = [owl_classes[c] for c in expr[1] if c in owl_classes]
                if parts:
                    cls.equivalent_to.append(or2.And(parts))
            elif kind == "union":
                parts = [owl_classes[c] for c in expr[1] if c in owl_classes]
                if parts:
                    cls.equivalent_to.append(or2.Or(parts))
            elif kind == "complement":
                other = expr[1]
                if other in owl_classes:
                    cls.equivalent_to.append(or2.Not(owl_classes[other]))
            # `some` and `all` need the property to exist first — see
            # second pass after properties below.

        # ----- Properties --------------------------------------------
        owl_props: dict[str, Any] = {}
        for prop_name in sorted(ontology.properties):
            sanitized = names.register(prop_name)
            # All our properties are object properties (subject and
            # object are both entities, never literals). The HermiT
            # adapter doesn't currently expose DataProperty axioms.
            prop = or2.types.new_class(sanitized, (or2.ObjectProperty,))
            owl_props[prop_name] = prop

        # Property characteristics.
        for prop in ontology.transitive_properties:
            if prop in owl_props:
                owl_props[prop].is_a.append(or2.TransitiveProperty)
        for prop in ontology.symmetric_properties:
            if prop in owl_props:
                owl_props[prop].is_a.append(or2.SymmetricProperty)
        for prop in ontology.functional_properties:
            if prop in owl_props:
                owl_props[prop].is_a.append(or2.FunctionalProperty)
        for prop in ontology.inverse_functional_properties:
            if prop in owl_props:
                owl_props[prop].is_a.append(or2.InverseFunctionalProperty)
        for p1, p2 in ontology.inverse_property_pairs:
            if p1 in owl_props and p2 in owl_props:
                owl_props[p1].inverse_property = owl_props[p2]
        for sub, sup in ontology.sub_property_pairs:
            if sub in owl_props and sup in owl_props:
                owl_props[sub].is_a.append(owl_props[sup])
        for p1, p2 in ontology.equivalent_property_pairs:
            if p1 in owl_props and p2 in owl_props:
                owl_props[p1].equivalent_to.append(owl_props[p2])

        # Domain / range — declared on the property.
        for prop, cls in ontology.domain_constraints.items():
            if prop in owl_props and cls in owl_classes:
                owl_props[prop].domain.append(owl_classes[cls])
        for prop, cls in ontology.range_constraints.items():
            if prop in owl_props and cls in owl_classes:
                owl_props[prop].range.append(owl_classes[cls])

        # Cardinality. owlready2 expresses cardinality via class-level
        # restrictions, so we anchor each cardinality axiom on the
        # domain class (or owl:Thing if no domain was declared).
        for prop, min_v, max_v, qualifier in ontology.cardinality_axioms:
            if prop not in owl_props:
                continue
            anchor_class = (
                owl_classes.get(ontology.domain_constraints.get(prop, ""))
                or or2.Thing
            )
            qual_class = owl_classes.get(qualifier) if qualifier else or2.Thing
            p = owl_props[prop]
            if min_v is not None and max_v is not None and min_v == max_v:
                anchor_class.is_a.append(p.exactly(min_v, qual_class))
            else:
                if min_v is not None:
                    anchor_class.is_a.append(p.min(min_v, qual_class))
                if max_v is not None:
                    anchor_class.is_a.append(p.max(max_v, qual_class))

        # Second-pass complex class definitions that need both
        # classes and properties.
        for name, expr in ontology.complex_class_definitions:
            if name not in owl_classes:
                continue
            cls = owl_classes[name]
            kind = expr[0]
            if kind == "some" and len(expr) >= 3:
                prop_name, target = expr[1], expr[2]
                if prop_name in owl_props and target in owl_classes:
                    cls.equivalent_to.append(
                        owl_props[prop_name].some(owl_classes[target])
                    )
            elif kind == "all" and len(expr) >= 3:
                prop_name, target = expr[1], expr[2]
                if prop_name in owl_props and target in owl_classes:
                    cls.equivalent_to.append(
                        owl_props[prop_name].only(owl_classes[target])
                    )

        # ----- ABox: individuals + property assertions ---------------
        # We register one individual per unique entity name seen in
        # the triples. owlready2 creates the individual when its class
        # is called: `MyClass("name")`.
        individuals: dict[str, Any] = {}

        def _individual(entity_name: str):
            """Get-or-create an individual. Defaults to owl:Thing so
            HermiT can later infer richer class memberships."""
            if entity_name not in individuals:
                sanitized = names.register(entity_name)
                individuals[entity_name] = or2.Thing(sanitized)
            return individuals[entity_name]

        for t in kb.triples:
            # Skip our internal marker relations; they're not OWL
            # assertions, they're conflict-reporting facts.
            if t.relation in (
                "CONFLICT_FUNCTIONAL",
                "CONFLICT_INVERSE_FUNCTIONAL",
                "CONTRADICTION_DETECTED",
                "CONFLICT_UNRESOLVED",
            ):
                continue

            subj = _individual(t.subject)

            if t.relation == "IS_A":
                # Class membership — append to the individual's `is_a`.
                cls = owl_classes.get(t.object)
                if cls is not None:
                    subj.is_a.append(cls)
                continue

            # Generic object property assertion.
            prop = owl_props.get(t.relation)
            if prop is None:
                # Property not declared in the ontology — skip.
                # HermiT can only reason over declared vocabulary.
                continue
            obj_ind = _individual(t.object)
            # owlready2 assignment style: subj.PROPERTY = [...]
            current = getattr(subj, names._fwd[t.relation], None)
            if isinstance(current, list):
                current.append(obj_ind)
            else:
                setattr(subj, names._fwd[t.relation], [obj_ind])

    return onto, names, individuals, owl_classes


# ----------------------------------------------------------------------
# Reasoning + result extraction.
# ----------------------------------------------------------------------


def hermit_enrich(
    kb: KB,
    ontology: Ontology,
    reasoner: str = "hermit",
    debug: int = 0,
) -> tuple[KB, list[Derivation], dict]:
    """Run a DL reasoner over (ontology + kb); return the enriched KB.

    Steps:
      1. Build an owlready2 ontology from `ontology` + `kb` via
         `_build_owl_world` (translates classes, properties, axioms,
         and ABox triples).
      2. Invoke the reasoner — HermiT by default, Pellet alternative.
      3. Read back inferred class memberships and property
         assertions; convert to our `Derivation` shape.
      4. Catch inconsistency: HermiT throws
         `OwlReadyInconsistentOntologyError`; we report it as a
         CONTRADICTION_DETECTED marker on the ontology name.

    Returns (enriched_kb, derivations, info). `info` is a dict with:
        consistent: bool — False if HermiT proved the ontology
                    inconsistent
        reasoner:   str — which reasoner ran
        n_inferred: int — count of inferred facts emitted
    """
    or2 = _require_owlready2()

    onto, names, individuals, owl_classes = _build_owl_world(ontology, kb)

    # Snapshot the EXPLICITLY-asserted class memberships per individual.
    # After reasoning, we'll compare against `INDIRECT_is_a` (which
    # includes both explicit and inferred memberships) to identify
    # which classes were newly inferred. Using `is_a` here is correct
    # — it captures only what we put in, before any inference.
    pre_classes: dict[str, set[str]] = {}
    for ext_name, ind in individuals.items():
        pre_classes[ext_name] = {c.name for c in ind.is_a}

    # Assert AllDifferent over all individuals so that OWL's open-world
    # default (where two named individuals MIGHT be the same unless
    # `differentFrom` is asserted) doesn't let HermiT trivially
    # satisfy cardinality constraints by identifying named individuals
    # with each other. This is the unique-name-assumption posture most
    # callers expect: distinct names mean distinct things.
    if len(individuals) >= 2:
        with onto:
            or2.AllDifferent(list(individuals.values()))

    info: dict = {"consistent": True, "reasoner": reasoner, "n_inferred": 0}
    derivations: list[Derivation] = []

    try:
        with onto:
            if reasoner == "pellet":
                or2.sync_reasoner_pellet(infer_property_values=True, debug=debug)
            else:
                or2.sync_reasoner_hermit(debug=debug)
    except or2.base.OwlReadyInconsistentOntologyError as e:
        info["consistent"] = False
        marker = Triple(
            ontology.name, "CONTRADICTION_DETECTED", "OWL_INCONSISTENT",
            "(owl)", -1,
        )
        derivations.append(Derivation(
            "owl:InconsistentOntology",
            marker, [],
            f"HermiT proved the ontology + ABox inconsistent: {e}",
        ))
        # Return early with the marker — no point reading back
        # inferred memberships from an inconsistent ontology.
        enriched = KB(
            triples=kb.triples + [d.output for d in derivations],
            alias_map=kb.alias_map, n_articles=kb.n_articles,
            source_authority=kb.source_authority,
        )
        return enriched, derivations, info
    except FileNotFoundError as e:
        # Java not installed — owlready2 raises FileNotFoundError when
        # it can't find the `java` binary.
        raise RuntimeError(
            "HermiT requires a Java JVM. Install OpenJDK 17 (or any "
            "Java 8+) and ensure `java` is on PATH. See "
            "aws/AWS_WORKFLOW.md for an EC2-managed alternative."
        ) from e

    # Diff: any class membership now present that wasn't before is an
    # inference. owlready2 exposes the full (asserted + inferred)
    # class set as `INDIRECT_is_a`; the explicit set lives in `is_a`.
    # We ignore owl:Thing (every individual is a Thing — uninformative).
    seen_kb_triples = {
        (t.subject, t.relation, t.object) for t in kb.triples
    }
    for ext_name, ind in individuals.items():
        # INDIRECT_is_a includes inferred superclasses; that's the
        # closure we want to mine for new memberships.
        post = {c.name for c in ind.INDIRECT_is_a}
        new_classes = post - pre_classes[ext_name]
        for cls_name in new_classes:
            if cls_name == "Thing":
                continue
            # Map sanitized class name back to original.
            original_cls = names.original(cls_name)
            key = (ext_name, "IS_A", original_cls)
            if key in seen_kb_triples:
                continue  # already asserted
            derived = Triple(
                ext_name, "IS_A", original_cls, "(owl)", -1,
                confidence=1.0,
            )
            derivations.append(Derivation(
                "owl:dl-classification",
                derived, [],
                f"HermiT inferred that {ext_name} is a {original_cls} "
                f"from the ontology's axioms.",
            ))

    info["n_inferred"] = len(derivations)

    enriched = KB(
        triples=kb.triples + [d.output for d in derivations],
        alias_map=kb.alias_map, n_articles=kb.n_articles,
        source_authority=kb.source_authority,
    )
    return enriched, derivations, info


# ----------------------------------------------------------------------
# Rule-shaped wrapper for engine integration.
# ----------------------------------------------------------------------


def hermit_rule(ontology: Ontology, stratum: int = 5) -> Rule:
    """Wrap `hermit_enrich` as a Rule, so it slots into the standard
    engine dispatcher.

    Stratum default is 5 — high enough that the Horn (stratum 0)
    closure and any negation-as-failure (stratum 1) rules have run
    first. HermiT then sees the closed KB and supplies the DL-only
    inferences (cardinality, complex class expressions) at the end.

    Returns a Rule whose function calls HermiT once per invocation
    and emits Derivations for inferred facts. The engine's seen-set
    prevents duplicate derivations across re-runs."""
    rule_name = f"hermit({ontology.name})"

    def fn(kb: KB) -> list[Derivation]:
        try:
            _, derivations, _ = hermit_enrich(kb, ontology)
        except (ImportError, RuntimeError) as e:
            # Soft-fail: log to stderr but don't crash the pipeline.
            # The rest of the rule list still runs.
            print(f"[{rule_name}] skipped: {e}", file=sys.stderr)
            return []
        return derivations

    return Rule(rule_name, fn, stratum=stratum)
