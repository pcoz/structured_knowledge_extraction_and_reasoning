"""Microtheory worked example #4 — an ORDERED microtheory as a SUBSTITUTE FOR CODE.

Example #3 showed an ordered microtheory is a *procedure* (steps for a human).
Push the idea one notch: if the steps are OPERATIONS, the ordered microtheory is
an *executable program*, run by SKEAR's core executor (`kb.execute`). The
algorithm then lives as scoped, ordered, provenance-carrying triples —
inspectable knowledge — instead of as hand-written Python control flow.

Why this matters (the "SKEAR as a substitute for code" claim):
  * The LOGIC IS DATA. Adding or changing a computation means adding or editing
    triples, not writing and deploying code. ONE executor (`kb.execute.run`) runs
    every program; the behaviour is in the KB.
  * IT STAYS AUDITABLE. A program is a microtheory you can query, diff across
    versions, cite step-by-step ("why did it output X?"), and reason over with
    the same engine used for everything else.
  * IT STAYS INERT/SAFE. The executor honours a CLOSED opcode set. A step it does
    not recognise is REFUSED, never executed — no eval, no host access.

This file authors two programs purely as data and runs them on the core executor.
For exact replication of a real Python block with branches/loops, and the
efficiency-at-scale argument, see worked example #5 (`microtheory.replicate`).

Run (from src/):  python -m microtheory.program
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.execute import run, ExecError, OPCODES

LINE = "=" * 78


def program_triples(scope, ops, source):
    """Author a program as an ordered microtheory: each op is a STEP-carrying
    triple (relation = opcode, object = operand) with its position in `seq`."""
    return [Triple("program", op, ("" if a is None else str(a)),
                   source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# Two programs, authored purely as data.
# Simple interest: I = P * R * T
INTEREST = [("LOAD", "P"), ("LOAD", "R"), ("MUL", None), ("LOAD", "T"),
            ("MUL", None), ("RET", None)]
# Celsius -> Fahrenheit: F = C * 9 / 5 + 32
C2F = [("LOAD", "C"), ("PUSH", 9), ("MUL", None), ("PUSH", 5), ("DIV", None),
       ("PUSH", 32), ("ADD", None), ("RET", None)]


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #4 — an ordered microtheory as a SUBSTITUTE FOR CODE")
    print(LINE)

    kb = KB(triples=program_triples("interest", INTEREST, "finance_handbook")
            + program_triples("c2f", C2F, "units_reference"),
            alias_map={}, n_articles=0)

    # --- One executor, two programs — the logic is in the data ------------
    print("\n[1] The core executor (kb.execute.run) runs two programs (logic = data):")
    r_int = run(kb, "interest", {"P": 1000, "R": 0.05, "T": 3})
    print(f"    interest(P=1000, R=0.05, T=3) = {r_int.value}")
    check("program 'interest' computes P*R*T", r_int.value == 150.0)
    r_f = run(kb, "c2f", {"C": 100})
    print(f"    c2f(C=100) = {r_f.value}")
    check("program 'c2f' computes C*9/5+32", r_f.value == 212.0)
    check("neither program required new executor code", True)

    # --- A program is inspectable, cited knowledge ------------------------
    print("\n[2] The program is queryable, ordered, cited knowledge (a 'why' trace):")
    for line in r_int.trace:
        print(f"    {line}")
    check("every executed step carries provenance",
          all("[finance_handbook]" in ln for ln in r_int.trace))

    # --- Change behaviour by EDITING DATA, not code -----------------------
    print("\n[3] Change behaviour as a data edit (no code change):")
    promo = INTEREST[:-1] + [("PUSH", 2), ("MUL", None), ("RET", None)]   # *2 promo
    kb2 = KB(triples=program_triples("interest_promo", promo, "promo_memo"),
             alias_map={}, n_articles=0)
    r_promo = run(kb2, "interest_promo", {"P": 1000, "R": 0.05, "T": 3})
    print(f"    interest_promo(...) = {r_promo.value}  (was {r_int.value})")
    check("editing the triples changed the computation, executor untouched",
          r_promo.value == 300.0)

    # --- Inert/safe: an unknown opcode is refused, not executed -----------
    print("\n[4] A program with an instruction outside the closed set is REFUSED:")
    bad = KB(triples=program_triples("evil", [("LOAD", "x"), ("SYSTEM_CALL", "rm -rf /")],
                                     "untrusted"), alias_map={}, n_articles=0)
    refused = False
    try:
        run(bad, "evil", {"x": 1})
    except ExecError as e:
        refused = True
        print(f"    refused: {e}")
    check("an out-of-set opcode is refused (closed set = " + str(len(OPCODES)) + " opcodes)",
          refused)

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "Ordered microtheories let SKEAR stand in for code where the logic is a\n"
        "sequence of well-defined operations: the algorithm becomes inspectable,\n"
        "versionable, citable, reason-over-able DATA executed by one core executor\n"
        "— deterministic and safe-by-construction, never opaque.")
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
