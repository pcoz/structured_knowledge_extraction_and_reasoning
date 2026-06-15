"""Microtheory worked example #1 — four schools of thought, one recession.

The SAME subject is carried under four incompatible economic framings at once.
Each is internally coherent and sourced; the disagreement between them is
preserved as queryable data rather than averaged into one synthetic "the
economists say" answer that no individual school would endorse.

Demonstrates:
  * KB.in_scope(school)  — read one microtheory (its facts + the global ones)
  * KB.scopes()          — enumerate the microtheories present
  * scope-aware conflict detection — incompatible classifications across
    schools are NOT contradictions (different microtheories), but a genuine
    within-school contradiction IS still flagged.

Run (from src/):  python -m microtheory.analyse
"""
from __future__ import annotations

import sys

from kb.ontology import Ontology
from kb.conflict import (apply_with_conflict_resolution, ChainPolicy,
                         AuthorityWinsPolicy, LatestWinsPolicy,
                         HighestConfidencePolicy)
from kb.query import Triple
from microtheory.corpus import (build_recession_kb, SUBJECT, SCHOOLS,
                               FUNCTIONAL_RELATIONS)

LINE = "=" * 78


def _val(kb, school, relation):
    """The value(s) a school holds for a relation (scoped, excluding globals)."""
    return [t for t in kb.in_scope(school)
            if t.relation == relation and t.scope == school]


def main() -> None:
    kb = build_recession_kb()
    failures = 0

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #1 — four schools of thought, one recession")
    print(LINE)

    # --- The agreed, global record -------------------------------------
    print("\nGlobal facts (scope=None — agreed by every school):")
    for t in kb.in_scope(None):
        print(f"   {t.relation:16s} {t.object:28s} (src '{t.source_article}')")

    print(f"\nMicrotheories present: {sorted(kb.scopes())}")

    # --- Read each microtheory on its own terms ------------------------
    print("\n--- What each school holds (read via KB.in_scope, sourced) ---")
    for school in SCHOOLS:
        isa = _val(kb, school, "IS_A")[0]
        cause = _val(kb, school, "PRIMARY_CAUSE")[0]
        rx = _val(kb, school, "PRESCRIBES")[0]
        print(f"\n  [{school}]")
        print(f"     IS_A          : {isa.object}   (src '{isa.source_article}')")
        print(f"     PRIMARY_CAUSE : {cause.object}")
        print(f"     PRESCRIBES    : {rx.object}")
        # each school's in_scope view = its own facts + the global ones
        view = kb.in_scope(school)
        n_global = sum(1 for t in view if t.scope is None)
        n_own = sum(1 for t in view if t.scope == school)
        assert n_global == 3, "every school should see the 3 global facts"
        if n_global != 3:
            failures += 1

    # --- The structural disagreement, made explicit --------------------
    print("\n--- Structural disagreement across schools (preserved, not blended) ---")
    for rel in ("IS_A", "PRIMARY_CAUSE", "PRESCRIBES", "UNIT_OF_ANALYSIS"):
        vals = {school: _val(kb, school, rel)[0].object for school in SCHOOLS}
        distinct = len(set(vals.values()))
        print(f"   {rel}: {distinct} distinct positions")
        for school, v in vals.items():
            print(f"       {school:18s} -> {v}")
        assert distinct == len(SCHOOLS), f"{rel}: schools should each differ"
        if distinct != len(SCHOOLS):
            failures += 1

    # --- Scope-aware conflict detection --------------------------------
    # IS_A etc. are functional, yet the four schools' incompatible values must
    # NOT be flagged as conflicts — they hold in different microtheories.
    onto = Ontology(functional_properties=set(FUNCTIONAL_RELATIONS))
    policy = ChainPolicy([AuthorityWinsPolicy(), LatestWinsPolicy(),
                          HighestConfidencePolicy()])
    _, _, conflicts, _ = apply_with_conflict_resolution(kb, ontology=onto, policy=policy)
    print(f"\nScope-aware conflict detection across the four schools: "
          f"{len(conflicts)} conflicts")
    assert len(conflicts) == 0, "cross-school differences must not be conflicts"
    if conflicts:
        failures += 1
    print("   -> 0: incompatible framings coexist; the disagreement is data, not error.")

    # --- But a genuine WITHIN-school contradiction is still caught ------
    kb2 = build_recession_kb()
    # A second Keynesian source asserts a *different* primary cause — a real
    # contradiction inside one microtheory.
    kb2.triples.append(Triple(SUBJECT, "PRIMARY_CAUSE", "animal_spirits_collapse",
                              "rival_keynesian_paper", 9, None, None, 0.8, "keynesian_school"))
    kb2 = type(kb2)(triples=kb2.triples, alias_map={}, n_articles=0)
    _, _, conflicts2, _ = apply_with_conflict_resolution(kb2, ontology=onto, policy=policy)
    within = [c for c in conflicts2 if "PRIMARY_CAUSE" in c.detail]
    print(f"\nAdd a contradictory PRIMARY_CAUSE *within* the Keynesian school: "
          f"{len(within)} conflict flagged")
    assert len(within) == 1, "a within-school contradiction must be flagged"
    if len(within) != 1:
        failures += 1
    print("   -> 1: within a single microtheory, contradiction is still caught and resolved.")

    print("\n" + LINE)
    if failures == 0:
        print("ALL ASSERTIONS PASSED.")
    else:
        print(f"{failures} ASSERTION(S) FAILED.")
    print(
        "Why scope matters: collapsing the four schools into one context would force\n"
        "a single 'mainstream' answer that no individual school endorses, and lose the\n"
        "ability to restrict to one school's internally-coherent position or to cite\n"
        "which school holds what. Scoped microtheories keep each framing separate,\n"
        "sourced, and queryable — while still catching contradiction *inside* a framing."
    )
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
