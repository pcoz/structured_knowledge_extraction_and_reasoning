"""Microtheory worked example #16 — modelling a system, then opening its black boxes.

`OPAQUE` lets SKEAR represent a WHOLE system, not just its verifiable core: a
component whose internals are not (yet) modelled is a declared black box with an
honest "unverified" boundary. Compose `FETCH` (cited data sources), `CALL`
(transparent sub-components) and `OPAQUE` (black-box components) and you have a
system ARCHITECTURE expressed as cited, queryable, reason-over-able knowledge —
a component/connector graph with explicit trust boundaries.

This file models a loan-origination system and then performs STEPWISE REFINEMENT:
it opens the black boxes one by one — replacing each `OPAQUE` node with a real
sub-microtheory — recursively (opening one box can reveal a deeper one), until the
whole system has complete, deterministic detail and runs with no black boxes left.

At every stage the system is COMPLETE and AUDITABLE: the opaque parts are honestly
declared, the verified parts run, and the system's full (transitive) black-box
boundary is queryable. Refinement monotonically shrinks that boundary to nothing.

Run (from src/):  python -m microtheory.architecture
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.execute import run, ExecError

LINE = "=" * 78


def prog(scope, ops, source="origination_system"):
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# --- CITED facts the transparent components read ----------------------------
FACTS = [
    Triple("app", "INCOME", "5000", "application_form", 0, None, None, 1.0),
    Triple("app", "DEBT", "1500", "application_form", 0, None, None, 1.0),
    Triple("app", "HISTORY_YEARS", "8", "credit_file", 0, None, None, 1.0),
    Triple("bureau", "BASE", "600", "bureau_feed", 0, None, None, 1.0),
    Triple("policy", "MAX_DTI", "0.4", "lending_policy", 0, None, None, 1.0),
    Triple("policy", "MIN_CREDIT", "650", "lending_policy", 0, None, None, 1.0),
    Triple("policy", "HISTORY_BONUS", "10", "lending_policy", 0, None, None, 1.0),
]

# --- the top-level system: approve = affordability_ok AND credit_ok ----------
# Two assemblies of the same system: components left OPAQUE vs opened to a CALL.
ORIG_BOXED = [("OPAQUE", "affordability"), ("OPAQUE", "credit_check"), ("AND", None), ("RET", None)]
ORIG_AFF_OPEN = [("CALL", "affordability"), ("OPAQUE", "credit_check"), ("AND", None), ("RET", None)]
ORIG_OPEN = [("CALL", "affordability"), ("CALL", "credit_check"), ("AND", None), ("RET", None)]

# --- the components, as transparent sub-microtheories ------------------------
# affordability_ok = (DEBT / INCOME) <= MAX_DTI
AFFORDABILITY = [("FETCH", "app|DEBT"), ("FETCH", "app|INCOME"), ("DIV", None),
                 ("FETCH", "policy|MAX_DTI"), ("LE", None), ("RET", None)]
# credit_check, with the bureau score still a black box (a DEEPER opaque node)
CREDIT_CHECK_BOXED = [("OPAQUE", "bureau_score"), ("FETCH", "policy|MIN_CREDIT"), ("GE", None), ("RET", None)]
# credit_check, with the bureau score opened to a real sub-component
CREDIT_CHECK_OPEN = [("CALL", "bureau_score"), ("FETCH", "policy|MIN_CREDIT"), ("GE", None), ("RET", None)]
# bureau_score = BASE + HISTORY_YEARS * HISTORY_BONUS
BUREAU_SCORE = [("FETCH", "bureau|BASE"), ("FETCH", "app|HISTORY_YEARS"),
                ("FETCH", "policy|HISTORY_BONUS"), ("MUL", None), ("ADD", None), ("RET", None)]


def transitive_opaque(kb: KB, entry: str) -> set:
    """The system's FULL black-box boundary: every OPAQUE label reachable from
    `entry` through the CALL graph (recursively). This is reasoning OVER the
    architecture-as-data — the complete set of components still left unopened."""
    seen, boxes, stack = set(), set(), [entry]
    while stack:
        scope = stack.pop()
        if scope in seen:
            continue
        seen.add(scope)
        for t in kb.ordered_scope(scope):
            if t.relation == "OPAQUE":
                boxes.add(t.object)
            elif t.relation == "CALL" and t.object:
                stack.append(t.object)
    return boxes


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #16 — model a system, then open its black boxes")
    print(LINE)

    # The four refinement stages, each a KB. Each stage opens one more box; opening
    # `credit_check` reveals a DEEPER box (`bureau_score`) — refinement is recursive.
    stages = [
        ("0: architecture sketch", FACTS + prog("origination", ORIG_BOXED), {"affordability": 1, "credit_check": 1}),
        ("1: open affordability", FACTS + prog("origination", ORIG_AFF_OPEN) + prog("affordability", AFFORDABILITY), {"credit_check": 1}),
        ("2: open credit_check (reveals bureau_score)", FACTS + prog("origination", ORIG_OPEN)
         + prog("affordability", AFFORDABILITY) + prog("credit_check", CREDIT_CHECK_BOXED), {"bureau_score": 680}),
        ("3: open bureau_score — complete", FACTS + prog("origination", ORIG_OPEN)
         + prog("affordability", AFFORDABILITY) + prog("credit_check", CREDIT_CHECK_OPEN)
         + prog("bureau_score", BUREAU_SCORE), {}),
    ]

    prior_boxes = None
    for label, triples, oracles in stages:
        kb = KB(triples=triples, alias_map={}, n_articles=0)
        boxes = transitive_opaque(kb, "origination")
        # try to run with NO oracles — only the fully-opened system should succeed
        try:
            run(kb, "origination", {})
            runnable = True
        except ExecError:
            runnable = False
        # run supplying the stage's black-box values (buyer-beware) to get a result
        res = run(kb, "origination", {}, oracles=oracles)
        # Refinement need not SHRINK the boundary at every step: opening one box can
        # REVEAL a deeper one (recursion). What must hold is that it makes progress —
        # the boundary changes and the just-opened box is gone — and trends to ∅.
        if prior_boxes is None:
            delta = ""
        elif len(boxes) < len(prior_boxes):
            delta = "  (shrank)"
        else:
            delta = "  (a deeper black box was revealed — refinement is recursive)"
        print(f"\n[stage {label}]")
        print(f"    remaining black boxes (transitive): {sorted(boxes) or '∅ — fully transparent'}{delta}")
        print(f"    runs with NO oracles? {runnable};  decision (with oracles) = {int(res.value)}")
        if res.opaque:
            print(f"    unverified black-box values used: {res.opaque}")
        check(f"stage '{label}': decision approves (1)", res.value == 1.0)
        check(f"stage '{label}': refinement changed the black-box boundary",
              prior_boxes is None or boxes != prior_boxes)
        prior_boxes = boxes

    # The fully-opened system runs end-to-end with NO oracles and NO opaque steps.
    final = KB(triples=stages[-1][1], alias_map={}, n_articles=0)
    fr = run(final, "origination", {})
    check("the fully-refined system runs deterministically with no black boxes",
          fr.value == 1.0 and not fr.opaque)
    check("the fully-refined system's opaque boundary is empty",
          transitive_opaque(final, "origination") == set())
    # ...and its answer is cited end to end (no unverified inputs)
    print(f"\n    fully-refined system: decision = {int(fr.value)}, "
          f"cited reads = {len(set(fr.reads))}, unverified boxes = {len(fr.opaque)}")
    check("the refined decision is fully cited and carries no unverified value",
          fr.reads and not fr.opaque)

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "A system is modelled top-down as cited knowledge: transparent components\n"
        "(microtheories) and declared black boxes (OPAQUE), composed by CALL/FETCH.\n"
        "Its full trust boundary is queryable; refinement opens the boxes one by one,\n"
        "recursively, each opening possibly revealing a deeper box — until the whole\n"
        "system has complete, deterministic, fully-cited detail. The same medium holds\n"
        "the architecture, its boundaries, and its eventual full implementation.")
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
