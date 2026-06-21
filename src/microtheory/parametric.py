"""Microtheory worked example #11 — ONE rule, EVERY entity: parametric FETCH.

The earlier FETCH examples (#7 `unified`) read a fact whose subject is baked into
the operand: `FETCH widget|PRICE`. That ties a program to one specific entity. A
real business rule is generic — "a customer's loan offer is three times their
monthly income plus their balance" — and must run against *any* customer without
being rewritten per customer.

Parametric FETCH (`FETCH @var|relation`) supplies exactly that. The subject is
read from a local variable (an entity id passed in as an input), so a SINGLE
ordered microtheory serves an entire population. The literal form is still there
for genuinely-fixed subjects (a global policy), so one rule mixes both: per-entity
facts (`@who|...`) and shared facts (`bank|INCOME_MULTIPLE`).

This file shows:
  1. ONE generic program, run against three different customers — no per-entity
     rewrite, each result cited to the RESOLVED subject and its source.
  2. NO DISCONNECT (the #7 property, now parametric): edit a customer's fact,
     rerun the SAME program for that customer, get the updated answer.
  3. SELF-DESCRIBING DEPENDENCIES: a parametric operand is inspectable DATA, so
     the system can DECLARE — before running — exactly which facts the rule will
     read for a given entity, and that declared surface matches what execution
     actually FETCHes. The rule's data dependencies are themselves knowledge.

Run (from src/):  python -m microtheory.parametric
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.execute import run

LINE = "=" * 78


def prog(scope, ops, source="lending_policy_2026"):
    """Author a program as an ordered microtheory (relation=opcode, object=operand)."""
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# --------------------------------------------------------------------------
# THE RULE — written ONCE, over a generic subject `@who`.
# loan_offer(who) = who.MONTHLY_INCOME * bank.INCOME_MULTIPLE + who.BALANCE
# Two parametric FETCHes (per-customer) and one literal FETCH (shared policy)
# live side by side in the same program.
# --------------------------------------------------------------------------
LOAN_OFFER = [
    ("FETCH", "@who|MONTHLY_INCOME"),     # 0 read THIS customer's income
    ("FETCH", "bank|INCOME_MULTIPLE"),    # 1 read the shared policy multiple
    ("MUL", None),                        # 2 income * multiple
    ("FETCH", "@who|BALANCE"),            # 3 read THIS customer's balance
    ("ADD", None),                        # 4 + balance
    ("RET", None),                        # 5
]

INCOME_MULTIPLE = 3.0


def build_kb(alice_balance: float = 1500.0) -> KB:
    """ONE knowledge base: per-customer facts, a shared policy fact, and the rule
    — all triples, all in the same store. `alice_balance` is a knob so we can edit
    a single fact later and rerun the unchanged program (demonstration 2)."""
    data = [
        # --- per-customer facts (the @who|... operands resolve to these) ---
        Triple("c_alice", "MONTHLY_INCOME", "4000", "kyc_intake", 0, None, None, 1.0),
        Triple("c_alice", "BALANCE", str(alice_balance), "ledger_2026q2", 0, None, None, 1.0),
        Triple("c_bob", "MONTHLY_INCOME", "2500", "kyc_intake", 0, None, None, 1.0),
        Triple("c_bob", "BALANCE", "300", "ledger_2026q2", 0, None, None, 1.0),
        Triple("c_carol", "MONTHLY_INCOME", "6000", "kyc_intake", 0, None, None, 1.0),
        Triple("c_carol", "BALANCE", "9000", "ledger_2026q2", 0, None, None, 1.0),
        # --- shared policy fact (the literal FETCH resolves to this) ---
        Triple("bank", "INCOME_MULTIPLE", str(INCOME_MULTIPLE), "lending_policy_2026", 0, None, None, 1.0),
    ]
    return KB(triples=data + prog("loan_offer", LOAN_OFFER), alias_map={}, n_articles=0)


def py_loan_offer(income, balance):
    """The same rule in Python, as an honesty anchor."""
    return income * INCOME_MULTIPLE + balance


# Known customer facts, for asserting against the anchor.
CUSTOMERS = {
    "c_alice": (4000.0, 1500.0),
    "c_bob":   (2500.0,  300.0),
    "c_carol": (6000.0, 9000.0),
}


def declared_fetch_surface(kb: KB, scope: str, who: str) -> list[tuple[str, str]]:
    """Read the rule's data-dependency surface straight out of its OWN triples,
    resolving the parametric subject `@who` to a concrete entity. No execution —
    this is the program describing, in advance, which facts it will read for
    `who`. The result is an ordered list of (subject, relation) pairs."""
    surface = []
    for t in kb.ordered_scope(scope):
        if t.relation != "FETCH":
            continue
        subj, _, rel = str(t.object).partition("|")
        if subj.startswith("@"):
            subj = who if subj[1:] == "who" else subj            # resolve @who
        surface.append((subj, rel))
    return surface


def read_surface(result) -> list[tuple[str, str]]:
    """The (subject, relation) pairs a run ACTUALLY read, parsed from its cited
    `reads` log (format: 'subject relation object [source]')."""
    pairs = []
    for cite in result.reads:
        parts = cite.split()
        pairs.append((parts[0], parts[1]))
    return pairs


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #11 — ONE rule, EVERY entity (parametric FETCH)")
    print(LINE)

    kb = build_kb()

    # --- 1. ONE program, MANY entities — no per-customer rewrite --------------
    print("\n[1] the SAME ordered microtheory 'loan_offer', run for each customer:")
    for who, (income, balance) in CUSTOMERS.items():
        r = run(kb, "loan_offer", {"who": who})
        print(f"    loan_offer({who}) = {r.value}   "
              f"(reads: {', '.join(c.split(' [')[0] for c in r.reads)})")
        check(f"one generic rule serves {who} ({income}*{INCOME_MULTIPLE}+{balance})",
              r.value == py_loan_offer(income, balance))
        check(f"the offer for {who} is cited to the RESOLVED subject, not '@who'",
              any(c.startswith(who + " ") for c in r.reads)
              and not any("@who" in c for c in r.reads))
    # The program scope is literally ONE microtheory — the same six triples drive
    # every customer; only the input differs.
    check("there is exactly ONE program (six steps), reused for all customers",
          len([t for t in kb.ordered_scope("loan_offer")]) == 6)

    # --- 2. NO DISCONNECT, parametrically: edit a FACT, rerun the SAME rule ----
    before = run(kb, "loan_offer", {"who": "c_alice"}).value
    kb2 = build_kb(alice_balance=8000.0)   # the ONLY change: one data fact
    after = run(kb2, "loan_offer", {"who": "c_alice"}).value
    print(f"\n[2] edit ONE fact (c_alice BALANCE 1500 -> 8000), rerun the SAME rule:")
    print(f"    loan_offer(c_alice) = {after}  (was {before}) — no program change")
    check("editing a customer's fact changes only that customer's offer",
          after == py_loan_offer(4000.0, 8000.0) and after != before
          and run(kb2, "loan_offer", {"who": "c_bob"}).value == before_unchanged_for_bob(kb))

    # --- 3. SELF-DESCRIBING DEPENDENCIES: declared surface == read surface -----
    print("\n[3] the rule DECLARES its data dependencies (parametric operands are")
    print("    inspectable data); resolve @who and it matches what the run reads:")
    for who in CUSTOMERS:
        declared = declared_fetch_surface(kb, "loan_offer", who)
        actual = read_surface(run(kb, "loan_offer", {"who": who}))
        if who == "c_alice":
            print(f"    declared for {who}: {declared}")
            print(f"    actually read  : {actual}")
        check(f"declared FETCH surface for {who} equals the executed read surface",
              declared == actual)
    # And the surface is genuinely parametric: alice's and bob's differ only in
    # the resolved subject, never in the rule.
    sa = declared_fetch_surface(kb, "loan_offer", "c_alice")
    sb = declared_fetch_surface(kb, "loan_offer", "c_bob")
    check("the declared surface is parametric (differs only by subject, same shape)",
          [rel for _, rel in sa] == [rel for _, rel in sb] and sa != sb)

    # --- unset variable is a controlled refusal, not a wrong answer -----------
    check("running the rule with no subject is a controlled refusal", _refuses(kb))

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "A business rule is written ONCE over a generic subject and serves the whole\n"
        "population — each answer cited to the concrete entity and its source. The\n"
        "rule's per-entity data dependencies are themselves inspectable knowledge,\n"
        "declarable in advance and provably equal to what execution reads.")
    print(LINE)
    if failures:
        sys.exit(1)


def before_unchanged_for_bob(kb: KB) -> float:
    """Bob's offer in the ORIGINAL kb — used to assert that editing alice's fact
    left every other customer's offer untouched."""
    return run(kb, "loan_offer", {"who": "c_bob"}).value


def _refuses(kb: KB) -> bool:
    from kb.execute import ExecError
    try:
        run(kb, "loan_offer", {})        # no 'who' -> parametric FETCH cannot resolve
        return False
    except ExecError:
        return True


if __name__ == "__main__":
    main()
