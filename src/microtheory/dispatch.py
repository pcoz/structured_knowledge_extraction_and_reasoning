"""Microtheory worked example #18 — DISPATCH: choosing the computation from DATA.

The executor gains a computed CALL: an integer selector popped from the stack
chooses which microtheory to run next, from a jump table written on the opcode:

    ("DISPATCH", "1:combine_sum,2:combine_max,3:combine_avg")

This is the data-driven sibling of CALL. CALL names its target in the program;
DISPATCH reads its target from a VALUE — so the candidate set lives in a table
(data), not in a chain of hand-written `if`s (code). It is the building block of
interpreters (opcode -> handler), virtual dispatch (type -> method), state
machines (state -> transition) and rule engines (case -> action).

Why it matters in practice — the part people miss:

  The CHOICE of computation can itself be a cited fact. Here a risk engine combines
  two sub-scores, but HOW it combines them is set by policy: `policy|COMBINE` is a
  fact in the KB (1=sum, 2=max, 3=average). The engine FETCHes that policy and
  DISPATCHes on it. Changing the policy — a single fact, with provenance — changes
  the computation, with NO change to the program. And the engine is open/closed:
  add `combine_min` by adding one microtheory and one table row; the caller is
  untouched. Branch chains have neither property.

The dispatch is decidable: a table lookup over an integer selector. So choosing
behaviour from data is HARD (cited), not soft — the selector's provenance flows
straight into the result's provenance.

Run (from src/):  python -m microtheory.dispatch
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.execute import run, ExecError

LINE = "=" * 78


def prog(scope, ops, source="risk_policy_2026"):
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# --- CITED facts: two sub-scores, and the POLICY that says how to combine them ---
# The operator is knowledge, not code: it carries a source like any other fact.
def facts(combine_code):
    return [
        Triple("riskA", "SCORE", "30", "model_a_2026", 0, None, None, 1.0),
        Triple("riskB", "SCORE", "50", "model_b_2026", 0, None, None, 1.0),
        Triple("policy", "COMBINE", str(combine_code), "risk_policy_2026", 0, None, None, 1.0),
    ]


# --- HANDLER microtheories (the "methods" in the vtable) ----------------------
# Each is entered with the two operands on the stack: A (deeper), B (top).
COMBINE_SUM = [("ADD", None), ("RET", None)]                       # A + B
COMBINE_AVG = [("ADD", None), ("PUSH", 2), ("DIV", None), ("RET", None)]  # (A + B) / 2
# max(A, B): store both, compare, return the larger (a real branch, addressed by seq).
COMBINE_MAX = [
    ("STORE", "b"), ("STORE", "a"),                # b = B (top), a = A
    ("LOAD", "a"), ("LOAD", "b"), ("GE", None),    # a >= b ?
    ("JZ", 8),                                     # if not, go return b
    ("LOAD", "a"), ("RET", None),                  # 6-7  return a
    ("LOAD", "b"), ("RET", None),                  # 8-9  return b
]
# An ADDED operation, to show open/closed extension: min(A, B). The caller below
# never changes — only this microtheory and one table row are added.
COMBINE_MIN = [
    ("STORE", "b"), ("STORE", "a"),
    ("LOAD", "a"), ("LOAD", "b"), ("LE", None),    # a <= b ?
    ("JZ", 8),
    ("LOAD", "a"), ("RET", None),
    ("LOAD", "b"), ("RET", None),
]

# --- The ENGINE: fetch the two scores and the policy, then DISPATCH on it ------
# Note the program never mentions sum/max/avg/min by name in its control flow —
# the policy fact selects the handler. The table maps the cited code -> handler.
TABLE = "1:combine_sum,2:combine_max,3:combine_avg,4:combine_min"
ENGINE = [
    ("FETCH", "riskA|SCORE"),       # A
    ("FETCH", "riskB|SCORE"),       # B
    ("FETCH", "policy|COMBINE"),    # the operator code — a cited fact
    ("DISPATCH", TABLE),            # run the handler the policy chose
    ("RET", None),
]

HANDLERS = (prog("combine_sum", COMBINE_SUM) + prog("combine_avg", COMBINE_AVG)
            + prog("combine_max", COMBINE_MAX) + prog("combine_min", COMBINE_MIN))


def combine_under(policy_code):
    kb = KB(triples=HANDLERS + prog("engine", ENGINE) + facts(policy_code),
            alias_map={}, n_articles=0)
    return run(kb, "engine", {}, trace=True)


def main():
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            fails += 1

    print(LINE)
    print("DISPATCH — the COMPUTATION is chosen by a cited policy fact (A=30, B=50)")
    print(LINE)
    labels = {1: "sum", 2: "max", 3: "average", 4: "min"}
    for code in (1, 2, 3, 4):
        res = combine_under(code)
        cite = next((r for r in res.reads if "COMBINE" in r), None)
        print(f"  policy COMBINE={code} ({labels[code]:7s}) -> {res.value:>5}   "
              f"[operator cited: {cite}]")

    # The four policies select genuinely different computations over the same data.
    check("COMBINE=1 dispatches to sum (30+50=80)", combine_under(1).value == 80.0)
    check("COMBINE=2 dispatches to max (max(30,50)=50)", combine_under(2).value == 50.0)
    check("COMBINE=3 dispatches to average ((30+50)/2=40)", combine_under(3).value == 40.0)
    check("COMBINE=4 dispatches to the ADDED min (min(30,50)=30) — caller untouched",
          combine_under(4).value == 30.0)

    # The operator's provenance rides into the result: choosing behaviour from data
    # is a cited, decidable (HARD) act, not a soft guess.
    reads = combine_under(2).reads
    check("the chosen operator is cited (policy COMBINE from risk_policy_2026)",
          any("COMBINE" in r and "risk_policy_2026" in r for r in reads))

    # An unmapped policy is an honest refusal — no silent default.
    refused = False
    try:
        combine_under(9)
    except ExecError:
        refused = True
    check("an unmapped policy code is REFUSED (no case 9), not defaulted", refused)

    print("\n" + LINE)
    print("ALL PASS" if fails == 0 else f"{fails} FAILED")
    print("One engine, one program. The policy fact — with provenance — picks the")
    print("computation; new operations drop in as a microtheory + a table row. This")
    print("is dispatch as DATA: the basis of interpreters, virtual dispatch, and")
    print("(see CodeGuard) resolving which method a call actually targets.")
    print(LINE)
    return fails


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
