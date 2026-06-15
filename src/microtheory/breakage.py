"""Microtheory worked example #2 — how OVERLAPPING microtheories break knowledge.

Two microtheories about light are each internally coherent — classical
(ether, observer-dependent speed) and relativistic (no ether, invariant
speed). They hold genuinely incompatible facts about the SAME subject, and
that is fine **as long as they stay separate**.

This example shows the pathology: when microtheories OVERLAP — either by
mis-scoping a framing-specific fact to GLOBAL (so it leaks into every
context), or by MERGING two distinct contexts into one scope — the body of
knowledge breaks. The functional-property contradictions that scoping kept
apart all fire at once; a deterministic resolver is then forced to pick one
value and silently discard the other across the whole KB, destroying every
framing's careful internal coherence.

The takeaway: a knowledge base that ingests incompatible framings into one
undifferentiated context cannot keep them straight — scope is what prevents
that, and what makes the breakage visible and repairable when it happens.

Run (from src/):  python -m microtheory.breakage
"""
from __future__ import annotations

import sys
from dataclasses import replace

from kb.ontology import Ontology
from kb.conflict import (apply_with_conflict_resolution, ChainPolicy,
                         AuthorityWinsPolicy, HighestConfidencePolicy)
from kb.query import KB, Triple

LINE = "=" * 78
SUBJECT = "light"
CLASSICAL = "classical_ether_mt"
RELATIVISTIC = "relativistic_mt"
FUNCTIONAL = {"IS_A", "PROPAGATES_THROUGH", "SPEED_DEPENDS_ON_OBSERVER"}

# Each microtheory, internally coherent. (rel, obj, scope)
_CLASSICAL = [
    ("IS_A", "mechanical_wave", CLASSICAL),
    ("PROPAGATES_THROUGH", "luminiferous_ether", CLASSICAL),
    ("SPEED_DEPENDS_ON_OBSERVER", "true", CLASSICAL),
]
_RELATIVISTIC = [
    ("IS_A", "wave_particle", RELATIVISTIC),
    ("PROPAGATES_THROUGH", "vacuum_no_medium", RELATIVISTIC),
    ("SPEED_DEPENDS_ON_OBSERVER", "false", RELATIVISTIC),
]


def _kb(rows):
    return KB(triples=[Triple(SUBJECT, r, o, scope, 0, None, None, 1.0, scope)
                       for (r, o, scope) in rows],
              alias_map={}, n_articles=0,
              source_authority={CLASSICAL: 0.5, RELATIVISTIC: 0.9})


def _conflicts(kb, onto, policy):
    _, _, c, _ = apply_with_conflict_resolution(kb, ontology=onto, policy=policy)
    return c


def main() -> None:
    onto = Ontology(functional_properties=set(FUNCTIONAL))
    policy = ChainPolicy([AuthorityWinsPolicy(), HighestConfidencePolicy()])
    failures = 0

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #2 — overlapping microtheories break knowledge")
    print(LINE)

    # --- 1. Properly scoped: coherent ----------------------------------
    healthy = _kb(_CLASSICAL + _RELATIVISTIC)
    c0 = _conflicts(healthy, onto, policy)
    print("\n[1] Properly scoped (classical_ether_mt | relativistic_mt):")
    print(f"    conflicts: {len(c0)}")
    print(f"    classical view  -> SPEED_DEPENDS_ON_OBSERVER = "
          f"{[t.object for t in healthy.in_scope(CLASSICAL) if t.relation=='SPEED_DEPENDS_ON_OBSERVER' and t.scope==CLASSICAL][0]}")
    print(f"    relativistic view -> SPEED_DEPENDS_ON_OBSERVER = "
          f"{[t.object for t in healthy.in_scope(RELATIVISTIC) if t.relation=='SPEED_DEPENDS_ON_OBSERVER' and t.scope==RELATIVISTIC][0]}")
    assert len(c0) == 0, "properly scoped microtheories must be conflict-free"
    failures += (len(c0) != 0)
    print("    -> coherent: each paradigm is internally consistent; no contradiction.")

    # --- 2. Breakage mode A: mis-scope to GLOBAL (a fact leaks everywhere) ---
    leaked_rows = [(r, o, None) for (r, o, _) in _CLASSICAL] + _RELATIVISTIC
    leaked = _kb(leaked_rows)
    cA = _conflicts(leaked, onto, policy)
    print("\n[2] BREAKAGE A — classical facts mis-scoped to GLOBAL (leak into every context):")
    print(f"    conflicts: {len(cA)}  (global facts now collide with the relativistic ones)")
    assert len(cA) >= 3, "globalised classical facts should collide on all 3 functional relations"
    failures += (len(cA) < 3)
    for c in cA:
        print(f"       contradiction: {c.detail}")
    print("    -> the relativistic microtheory can no longer be read cleanly:")
    glob_q = sorted({t.object for t in leaked.in_scope(RELATIVISTIC)
                     if t.relation == "SPEED_DEPENDS_ON_OBSERVER"})
    print(f"       in_scope(relativistic) SPEED_DEPENDS_ON_OBSERVER now returns {glob_q} (both!) — incoherent.")
    assert glob_q == ["false", "true"], "the leaked global fact contaminates the relativistic view"
    failures += (glob_q != ["false", "true"])

    # --- 3. Breakage mode B: MERGE two microtheories into one scope -----
    merged_rows = ([(r, o, "physics_mt") for (r, o, _) in _CLASSICAL]
                   + [(r, o, "physics_mt") for (r, o, _) in _RELATIVISTIC])
    merged = _kb(merged_rows)
    cB = _conflicts(merged, onto, policy)
    print("\n[3] BREAKAGE B — both paradigms MERGED into one scope 'physics_mt' (overlap):")
    print(f"    conflicts: {len(cB)}  (one context now asserts both paradigms at once)")
    assert len(cB) >= 3, "merging the two contexts should surface 3 functional contradictions"
    failures += (len(cB) < 3)
    print("    -> a deterministic resolver is now forced to pick ONE value per relation and")
    print("       discard the other ACROSS THE WHOLE KB — every paradigm-specific distinction")
    print("       is overwritten by whichever source has higher authority. The careful")
    print("       separation that made each paradigm usable is destroyed.")

    # --- 4. Repair: re-separate the scopes ------------------------------
    repaired = _kb(_CLASSICAL + _RELATIVISTIC)
    cR = _conflicts(repaired, onto, policy)
    print("\n[4] REPAIR — restore the two distinct scopes:")
    print(f"    conflicts: {len(cR)}  -> coherence restored; both paradigms readable again.")
    assert len(cR) == 0
    failures += (len(cR) != 0)

    print("\n" + LINE)
    if failures == 0:
        print("ALL ASSERTIONS PASSED.")
    else:
        print(f"{failures} ASSERTION(S) FAILED.")
    print(
        "Lesson: flat microtheories must stay disjoint where they genuinely disagree.\n"
        "Overlapping them — by globalising a context-specific fact, or by merging two\n"
        "contexts — collapses a coherent body of knowledge into contradiction, and any\n"
        "resolver then flattens every framing into one arbitrary winner. Any store that\n"
        "ingests incompatible framings into one undifferentiated context inherits this\n"
        "breakage. SKEAR's scope tag is what keeps the knowledge separated — and makes\n"
        "the breakage visible and repairable when scopes are mis-applied."
    )
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
