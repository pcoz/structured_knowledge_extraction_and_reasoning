"""Microtheory worked example #3 — an ORDERED microtheory is a PROCEDURE.

The flat microtheory (examples #1, #2) is a *set* of co-scoped facts. Adding
the optional `Triple.seq` ordinal makes a microtheory a *sequence*: the same
scope, but its member facts now carry an intrinsic order. That single change
turns a microtheory into a first-class **procedure** — a recipe, a runbook, a
clinical protocol, an algorithm — and, because it is still just scoped triples,
*every existing SKEAR faculty composes with it unchanged*. This file shows three
of those compositions, each assertion-backed.

  A. READ IN ORDER. `KB.ordered_scope(scope)` reads a procedure microtheory out
     as steps 1..N (by `seq`), independent of source/ingest order.

  B. PROCEDURES AS FRAMINGS. Two *variants* of the same task are two ordered
     microtheories. The multi-framing machinery from example #1 now works on
     PROCESSES: the variants' differences are queryable (a step-level diff), and
     scope-aware conflict detection treats "variant A does it differently from
     variant B" as data, NOT contradiction — while a genuine contradiction
     *within one variant* is still caught.

  C. ORDER IS JUST MORE TRIPLES, SO IT REASONS. Emit PRECEDES(step_i, step_i+1)
     from the sequence and hand it to the SAME fixpoint reasoner used for
     intellectual-descent closure. It computes the full precedence closure, and
     a non-linearizable (cyclic) procedure surfaces as derived self-precedence —
     a structural bug caught by reasoning, not by a bespoke checker.

Run (from src/):  python -m microtheory.procedure
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.ontology import Ontology
from kb.conflict import (apply_with_conflict_resolution, ChainPolicy,
                         AuthorityWinsPolicy, HighestConfidencePolicy)
from kb.reason import Rule, Derivation, apply_all_rules_to_fixpoint

LINE = "=" * 78


# --------------------------------------------------------------------------
# Two ordered microtheories: the same task, two variants. Steps are listed
# here OUT of seq order on purpose, to prove `seq` (not list position) is the
# source of truth.
# --------------------------------------------------------------------------
SRC = "bp_monitor_manual"

# The correct procedure (steps deliberately scrambled in this literal).
_CANONICAL = [
    ("apply_cuff_at_heart_level", 3),
    ("rest_quietly_for_5_minutes", 0),
    ("press_start_and_stay_still", 4),
    ("sit_with_back_supported", 1),
    ("record_the_reading", 5),
    ("bare_the_upper_arm", 2),
]
# A "rushed" variant that drops the rest step and the back-support step.
_RUSHED = [
    ("bare_the_upper_arm", 0),
    ("apply_cuff_at_heart_level", 1),
    ("press_start_and_stay_still", 2),
    ("record_the_reading", 3),
]

CANON = "measure_bp__canonical"
RUSHED = "measure_bp__rushed"


def _procedure_triples(scope, steps, recommended_by):
    """Build one procedure microtheory: STEP facts carrying `seq`, plus a
    functional applicability fact (RECOMMENDED_BY) used for the framing demo."""
    tris = [Triple("measure_bp", "STEP", obj, SRC, seq, None, None, 1.0, scope, seq)
            for (obj, seq) in steps]
    # A functional property that legitimately DIFFERS across variants.
    tris.append(Triple("measure_bp", "RECOMMENDED_BY", recommended_by,
                       SRC, 99, None, None, 1.0, scope))   # seq=None: not a step
    return tris


def _precedence_rule(scope=None):
    """A real Horn rule for the fixpoint engine: PRECEDES is transitive.
    PRECEDES(a,b) & PRECEDES(b,c) -> PRECEDES(a,c). NOT self-blocked, so a
    cyclic procedure derives PRECEDES(x,x) — that is the cycle detector."""
    def fn(kb: KB) -> list[Derivation]:
        out = []
        pre = [kb.triples[i] for i in kb.by_relation.get("PRECEDES", [])]
        by_subj = {}
        for t in pre:
            by_subj.setdefault(t.subject, []).append(t.object)
        for t1 in pre:
            for c in by_subj.get(t1.object, []):
                out.append(Derivation(
                    "precedes_transitive",
                    Triple(t1.subject, "PRECEDES", c, "(derived)", -1),
                    [t1],
                    f"{t1.subject} precedes {t1.object} precedes {c}"))
        return out
    return Rule("precedes_transitive", fn)


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #3 — an ORDERED microtheory is a PROCEDURE")
    print(LINE)

    kb = KB(triples=_procedure_triples(CANON, _CANONICAL, "clinical_guideline_2024")
            + _procedure_triples(RUSHED, _RUSHED, "office_shortcut_memo"),
            alias_map={}, n_articles=0,
            source_authority={"clinical_guideline_2024": 0.95,
                              "office_shortcut_memo": 0.4})

    # --- A. READ IN ORDER --------------------------------------------------
    print("\n[A] Read the canonical procedure out IN ORDER (seq, not list order):")
    steps = [t.object for t in kb.ordered_scope(CANON) if t.relation == "STEP"]
    for i, s in enumerate(steps, 1):
        print(f"    {i}. {s}")
    check("ordered_scope yields the true step sequence",
          steps == ["rest_quietly_for_5_minutes", "sit_with_back_supported",
                    "bare_the_upper_arm", "apply_cuff_at_heart_level",
                    "press_start_and_stay_still", "record_the_reading"])
    check("procedures present as microtheories", kb.scopes() == {CANON, RUSHED})

    # --- B. PROCEDURES AS FRAMINGS: diff + scope-aware conflict ------------
    print("\n[B] Two variants are two framings of one task — diff them:")
    canon = [t.object for t in kb.ordered_scope(CANON) if t.relation == "STEP"]
    rushed = [t.object for t in kb.ordered_scope(RUSHED) if t.relation == "STEP"]
    missing = [s for s in canon if s not in rushed]
    print(f"    canonical has {len(canon)} steps; rushed has {len(rushed)}.")
    print(f"    steps the rushed variant DROPS: {missing}")
    check("diff finds the dropped safety steps",
          set(missing) == {"rest_quietly_for_5_minutes", "sit_with_back_supported"})

    onto = Ontology(functional_properties={"RECOMMENDED_BY"})
    policy = ChainPolicy([AuthorityWinsPolicy(), HighestConfidencePolicy()])
    _, _, conflicts, _ = apply_with_conflict_resolution(kb, ontology=onto, policy=policy)
    print(f"\n    RECOMMENDED_BY differs across variants; conflicts flagged: {len(conflicts)}")
    check("variant differences are NOT contradictions (different microtheories)",
          len(conflicts) == 0)

    # a genuine contradiction WITHIN one variant must still fire
    kb2 = KB(triples=kb.triples + [Triple("measure_bp", "RECOMMENDED_BY",
             "a_contradicting_source", SRC, 98, None, None, 0.9, CANON)],
             alias_map={}, n_articles=0, source_authority=kb.source_authority)
    _, _, conflicts2, _ = apply_with_conflict_resolution(kb2, ontology=onto, policy=policy)
    within = [c for c in conflicts2 if "RECOMMENDED_BY" in c.detail]
    print(f"    add a 2nd RECOMMENDED_BY *within* canonical: conflicts flagged: {len(within)}")
    check("within-variant contradiction is still caught", len(within) == 1)

    # --- C. ORDER REASONS: precedence closure + cycle detection -----------
    print("\n[C] Hand step-order to the REAL fixpoint reasoner as PRECEDES facts:")
    # consecutive steps -> PRECEDES (the seq made explicit as relations)
    seqd = sorted([t for t in kb.ordered_scope(CANON) if t.relation == "STEP"],
                  key=lambda t: t.seq)
    pre = [Triple(seqd[i].object, "PRECEDES", seqd[i + 1].object, "(seq)", -1)
           for i in range(len(seqd) - 1)]
    pkb = KB(triples=pre, alias_map={}, n_articles=0)
    ext, derivs, _ = apply_all_rules_to_fixpoint(
        pkb, rules=[_precedence_rule()], propagate_confidence=False,
        propagate_temporal=False)
    pairs = {(t.subject, t.object) for t in ext.triples if t.relation == "PRECEDES"}
    n = len(seqd)
    print(f"    {n} steps -> {len(pre)} adjacent PRECEDES -> closure {len(pairs)} pairs")
    check("transitive closure of a total order = n*(n-1)/2 pairs",
          len(pairs) == n * (n - 1) // 2)
    check("a correct procedure is linearizable (no self-precedence)",
          not any(a == b for a, b in pairs))

    # a deliberately cyclic procedure: A->B->C->A. The SAME reasoner surfaces
    # the cycle as derived self-precedence — no bespoke cycle checker needed.
    cyc = [Triple("A", "PRECEDES", "B", "x", -1),
           Triple("B", "PRECEDES", "C", "x", -1),
           Triple("C", "PRECEDES", "A", "x", -1)]
    cext, _, _ = apply_all_rules_to_fixpoint(
        KB(triples=cyc, alias_map={}, n_articles=0), rules=[_precedence_rule()],
        propagate_confidence=False, propagate_temporal=False)
    self_pre = {t.subject for t in cext.triples
                if t.relation == "PRECEDES" and t.subject == t.object}
    print(f"    cyclic procedure A->B->C->A: steps with derived self-precedence: "
          f"{sorted(self_pre)}")
    check("a non-linearizable (cyclic) procedure is caught by reasoning",
          self_pre == {"A", "B", "C"})

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "An ordered microtheory needs no new engine: a procedure is just scoped\n"
        "triples that happen to carry `seq`. Reading, framing-comparison,\n"
        "conflict detection, and the fixpoint reasoner all compose with it for\n"
        "free — so SKEAR now represents recipes, runbooks, protocols and\n"
        "algorithms as first-class, queryable, reasoned-over knowledge.")
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
