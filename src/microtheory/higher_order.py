"""Microtheory worked example #14 — MAP / FILTER / FOLD over a cited series.

The executor gains the functional/collection sibling of its imperative loops:
higher-order opcodes that apply a microtheory across a bounded range [0, n).

  FOLD scope   — reduce/aggregate: acc = seed; for i in [0,n): acc = scope(acc, i).
  MAP scope    — apply scope(i) across the range, EMITting a sequence.
  FILTER scope — keep the i where predicate scope(i) holds, EMITting them.

`scope` is an ordinary ordered microtheory (the per-element function), so this is
composition — the same engine, applied element-wise. Bounded by n, so termination
and the closed-set guarantees hold. These are the SKEAR equivalents of LINQ's
`Aggregate` / `Select` / `Where` (or Python's `reduce` / `map` / `filter`).

Demonstrated over a small CITED loan KB — the kind of series arithmetic real
financial knowledge needs:

  FOLD   — compound balance after N periods: balance = principal·(1+rate)^N,
           as a reduce that multiplies the running balance by (1+rate) each period.
  MAP    — an accrual schedule: the interest accrued by the end of each period.
  FILTER — screening: from which periods does accrued interest cross a threshold?

Every per-element step FETCHes the loan's own cited facts, so the aggregate result
carries the provenance of the data it reduced.

Run (from src/):  python -m microtheory.higher_order
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.execute import run

LINE = "=" * 78


def prog(scope, ops, source="lending_model"):
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# --- CITED loan facts --------------------------------------------------------
FACTS = [
    Triple("loan", "PRINCIPAL", "1000", "loan_agreement_2026", 0, None, None, 1.0),
    Triple("loan", "RATE", "0.1", "rate_schedule_2026", 0, None, None, 1.0),
    Triple("loan", "PERIODS", "3", "loan_agreement_2026", 0, None, None, 1.0),
    Triple("loan", "THRESHOLD", "250", "review_policy_2026", 0, None, None, 1.0),
]

# --- PER-ELEMENT microtheories (the "lambdas") -------------------------------
# compound_step(acc, i): acc * (1 + rate)  — one period of compounding (ignores i).
COMPOUND_STEP = [("LOAD", "acc"), ("FETCH", "loan|RATE"), ("PUSH", 1), ("ADD", None),
                 ("MUL", None), ("RET", None)]
# accrued(i): principal * rate * (i + 1)  — interest accrued by the end of period i.
ACCRUED = [("FETCH", "loan|PRINCIPAL"), ("FETCH", "loan|RATE"), ("MUL", None),
           ("LOAD", "i"), ("PUSH", 1), ("ADD", None), ("MUL", None), ("RET", None)]
# over_threshold(i): accrued(i) >= threshold  — the screening predicate.
OVER_THRESHOLD = [("FETCH", "loan|PRINCIPAL"), ("FETCH", "loan|RATE"), ("MUL", None),
                  ("LOAD", "i"), ("PUSH", 1), ("ADD", None), ("MUL", None),
                  ("FETCH", "loan|THRESHOLD"), ("GE", None), ("RET", None)]

# --- DRIVERS that invoke the higher-order ops --------------------------------
# balance = FOLD(compound_step, seed=PRINCIPAL, n=PERIODS)  (stack: seed, then n)
BALANCE = [("FETCH", "loan|PRINCIPAL"), ("FETCH", "loan|PERIODS"),
           ("FOLD", "compound_step"), ("RET", None)]
# schedule: MAP(accrued) over PERIODS -> EMITs the accrual sequence
SCHEDULE = [("FETCH", "loan|PERIODS"), ("MAP", "accrued"), ("RET", None)]
# review: FILTER(over_threshold) over PERIODS -> EMITs the periods that cross it
REVIEW = [("FETCH", "loan|PERIODS"), ("FILTER", "over_threshold"), ("RET", None)]


def py_balance(p, r, n):
    for _ in range(n):
        p = p * (1 + r)
    return p


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    kb = KB(triples=FACTS
            + prog("compound_step", COMPOUND_STEP) + prog("accrued", ACCRUED)
            + prog("over_threshold", OVER_THRESHOLD)
            + prog("balance", BALANCE) + prog("schedule", SCHEDULE) + prog("review", REVIEW),
            alias_map={}, n_articles=0)

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #14 — MAP / FILTER / FOLD over a cited series")
    print(LINE)

    # FOLD — compound balance (reduce/aggregate), like LINQ .Aggregate -----------
    r = run(kb, "balance", {})
    print(f"\n[FOLD]   compound balance after 3 periods = {r.value}")
    print(f"         cited series inputs: {sorted(set(r.reads))}")
    check("FOLD reduces the series to the compound balance (1000·1.1^3 = 1331)",
          abs(r.value - py_balance(1000.0, 0.1, 3)) < 1e-9)
    check("the aggregate carries the provenance of the facts it reduced",
          any("rate_schedule_2026" in c for c in r.reads))

    # MAP — accrual schedule (a produced sequence), like LINQ .Select -----------
    s = run(kb, "schedule", {})
    print(f"\n[MAP]    accrual schedule (interest by end of each period) = {s.outputs}")
    check("MAP produces the per-period accrual sequence [100, 200, 300]",
          s.outputs == [100.0, 200.0, 300.0])

    # FILTER — threshold screening, like LINQ .Where ----------------------------
    f = run(kb, "review", {})
    print(f"\n[FILTER] periods whose accrued interest >= 250 (0-based) = {f.outputs}")
    check("FILTER keeps only period index 2 (accrued 300 >= 250)", f.outputs == [2.0])

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "Reduce, map, and filter over a bounded range are now ordered microtheories:\n"
        "the per-element function is itself a cited microtheory, composed element-wise\n"
        "by FOLD / MAP / FILTER. Functional/collection computation joins the imperative\n"
        "loops as deterministic, terminating, provenance-native knowledge.")
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
