"""Microtheory worked example #15 — a lending engine using every faculty, incl. higher-order.

A second whole-engine capstone (the first, `decision_engine.py`, predates the
higher-order opcodes). One self-contained, cited knowledge base makes a complete
lending decision and amortization plan, exercising EVERY SKEAR faculty:

  * QUERY      — read a cited loan fact.
  * REASON     — derive new facts to fixpoint (transitive referral chain).
  * EXECUTE    — one ordered-microtheory decision program that combines:
       - bitwise entitlement (`AND`/`==`): may this officer approve this tier?
       - HIGHER-ORDER `FOLD`: compound the balance over the loan term (reduce);
       - control flow (`JZ`) branching to a cited refusal otherwise;
       - composition: `FOLD` runs a per-period microtheory; `MAP`/`FILTER` build the
         amortization schedule and the review-period screen;
       - `EMIT`: the decision's audit value.
  * CONFLICT   — a contradictory interest rate is flagged, not used.
  * PERFORMANCE — a pure sub-program is interpreted and TRANSPILED to identical results.
  * PROVENANCE — every answer cites the facts it read.

Each numeric result is checked against a plain-Python anchor.

Run (from src/):  python -m microtheory.lending_engine
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.reason import Rule, Derivation, apply_all_rules_to_fixpoint
from kb.execute import run
from kb.transpile import run_compiled
from kb.conflict import (apply_with_conflict_resolution, ChainPolicy,
                         AuthorityWinsPolicy, LatestWinsPolicy, HighestConfidencePolicy)
from kb.ontology import Ontology

LINE = "=" * 78

# Approval-authority bits.
APPROVE, APPROVE_LARGE, OVERRIDE = 1, 2, 4


def prog(scope, ops, source="lending_policy"):
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# --- CITED facts -------------------------------------------------------------
FACTS = [
    # officers' approval authority (a permission bitmask)
    Triple("officer_jones", "PERMISSIONS", str(APPROVE | APPROVE_LARGE), "delegated_authority_2026", 0, None, None, 1.0),
    Triple("officer_amy", "PERMISSIONS", str(APPROVE), "delegated_authority_2026", 0, None, None, 1.0),
    Triple("tier_large", "REQUIRES", str(APPROVE_LARGE), "lending_policy_2026", 0, None, None, 1.0),
    # the loan itself
    Triple("loan", "PRINCIPAL", "1000", "loan_agreement_2026", 0, None, None, 1.0),
    Triple("loan", "RATE", "0.1", "rate_schedule_2026", 0, None, None, 1.0),
    Triple("loan", "PERIODS", "3", "loan_agreement_2026", 0, None, None, 1.0),
    Triple("loan", "THRESHOLD", "250", "review_policy_2026", 0, None, None, 1.0),
    # a referral chain for the reasoner to extend
    Triple("applicant_smith", "REFERRED_BY", "broker_a", "crm", 0, None, None, 1.0),
    Triple("broker_a", "REFERRED_BY", "partner_x", "crm", 0, None, None, 1.0),
]

# --- per-element microtheories (composed by the higher-order ops) ------------
COMPOUND_STEP = [("LOAD", "acc"), ("FETCH", "loan|RATE"), ("PUSH", 1), ("ADD", None), ("MUL", None), ("RET", None)]
ACCRUED = [("FETCH", "loan|PRINCIPAL"), ("FETCH", "loan|RATE"), ("MUL", None),
           ("LOAD", "i"), ("PUSH", 1), ("ADD", None), ("MUL", None), ("RET", None)]
OVER_THRESHOLD = [("FETCH", "loan|PRINCIPAL"), ("FETCH", "loan|RATE"), ("MUL", None),
                  ("LOAD", "i"), ("PUSH", 1), ("ADD", None), ("MUL", None),
                  ("FETCH", "loan|THRESHOLD"), ("GE", None), ("RET", None)]

# --- the decision program: bitwise entitlement + FOLD + control + EMIT -------
# decide(@officer): if (tier.REQUIRES AND officer.PERMISSIONS) == tier.REQUIRES,
# approve and return the compounded balance (a FOLD); else EMIT a refusal code.
DECIDE = [
    ("FETCH", "tier_large|REQUIRES"), ("DUP", None),            # 0-1
    ("FETCH", "@officer|PERMISSIONS"), ("AND", None), ("EQ", None),  # 2-4 entitled?
    ("JZ", 11),                                                 # 5 not entitled -> refuse
    ("FETCH", "loan|PRINCIPAL"), ("FETCH", "loan|PERIODS"),     # 6-7 seed, n
    ("FOLD", "compound_step"), ("EMIT", None), ("RET", None),   # 8-10 balance, audit, return
    ("PUSH", -1), ("EMIT", None), ("RET", None),                # 11-13 refusal
]
SCHEDULE = [("FETCH", "loan|PERIODS"), ("MAP", "accrued"), ("RET", None)]
REVIEW = [("FETCH", "loan|PERIODS"), ("FILTER", "over_threshold"), ("RET", None)]
# pure arithmetic (no FETCH/CALL/higher-order) for the transpiler check
SIMPLE_INTEREST = [("LOAD", "p"), ("LOAD", "r"), ("MUL", None), ("LOAD", "n"), ("MUL", None), ("RET", None)]


def transitive_referred(kb: KB):
    out, edges = [], [kb.triples[i] for i in kb.by_relation.get("REFERRED_BY", [])]
    by_subj = {}
    for t in edges:
        by_subj.setdefault(t.subject, []).append(t.object)
    for t in edges:
        for z in by_subj.get(t.object, []):
            if t.subject != z:
                out.append(Derivation("transitive_referred",
                                      Triple(t.subject, "REFERRED_BY", z, "(derived)", -1),
                                      [t], f"{t.subject} <- {t.object} <- {z}"))
    return out


def py_balance(p, r, n):
    for _ in range(n):
        p *= (1 + r)
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
            + prog("over_threshold", OVER_THRESHOLD) + prog("decide", DECIDE)
            + prog("schedule", SCHEDULE) + prog("review", REVIEW)
            + prog("simple_interest", SIMPLE_INTEREST),
            alias_map={}, n_articles=0)

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #15 — a lending engine using every faculty")
    print(LINE)

    # [1] QUERY ----------------------------------------------------------------
    p = kb.out_facts("loan", "PRINCIPAL")
    print(f"\n[1] QUERY: loan principal = {p[0].object}  (cited: {p[0].source_article})")
    check("query returns the cited principal", p and p[0].object == "1000")

    # [2] REASON ---------------------------------------------------------------
    ext, _d, _s = apply_all_rules_to_fixpoint(
        kb, rules=[Rule("transitive_referred", transitive_referred)],
        propagate_confidence=False, propagate_temporal=False)
    referred = {(t.subject, t.object) for t in ext.triples if t.relation == "REFERRED_BY"}
    print(f"\n[2] REASON to fixpoint: applicant_smith transitively referred by partner_x? "
          f"{('applicant_smith', 'partner_x') in referred}")
    check("transitive referral derived", ("applicant_smith", "partner_x") in referred)

    # [3] EXECUTE: entitlement (bitwise) + FOLD + control + EMIT ----------------
    rj = run(kb, "decide", {"officer": "officer_jones"})
    ra = run(kb, "decide", {"officer": "officer_amy"})
    print(f"\n[3] EXECUTE decision: officer_jones -> {rj.value} (audit {rj.outputs}); "
          f"officer_amy -> {ra.value} (audit {ra.outputs})")
    check("entitled officer's loan compounds to the balance (1000·1.1^3 = 1331)",
          abs(rj.value - py_balance(1000.0, 0.1, 3)) < 1e-9)
    check("un-entitled officer is refused (-1)", ra.value == -1.0)
    check("the decision cites the facts it read", any("rate_schedule_2026" in c for c in rj.reads))

    # higher-order schedule + screening
    sched = run(kb, "schedule", {}).outputs
    rev = run(kb, "review", {}).outputs
    print(f"    MAP amortization schedule = {sched};  FILTER review periods = {rev}")
    check("MAP builds the accrual schedule", sched == [100.0, 200.0, 300.0])
    check("FILTER screens the review periods", rev == [2.0])

    # [4] CONFLICT -------------------------------------------------------------
    kb_c = KB(triples=kb.triples + [Triple("loan", "RATE", "0.2", "stale_import", 0, None, None, 1.0)],
              alias_map={}, n_articles=0)
    onto = Ontology(functional_properties={"RATE"})
    policy = ChainPolicy([AuthorityWinsPolicy(), LatestWinsPolicy(), HighestConfidencePolicy()])
    _, _, conflicts, _ = apply_with_conflict_resolution(kb_c, ontology=onto, policy=policy)
    print(f"\n[4] CONFLICT: two interest rates for the loan -> {len(conflicts)} flagged")
    check("contradictory rate is flagged, not silently used", len(conflicts) >= 1)

    # [5] PERFORMANCE ----------------------------------------------------------
    args = {"p": 1000, "r": 0.1, "n": 3}
    interp = run(kb, "simple_interest", args).value
    comp = run_compiled(kb, "simple_interest", args)
    print(f"\n[5] PERFORMANCE: simple interest interpreted={interp} transpiled={comp}")
    check("interpreter and transpiler agree", interp == comp == 300.0)

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "One cited KB makes a full lending decision: QUERIED, REASONED to fixpoint,\n"
        "and EXECUTED — entitlement by bitwise masks, the balance by a higher-order\n"
        "FOLD over the term, the schedule by MAP and the review screen by FILTER, an\n"
        "EMITted audit trail — with bad data caught by CONFLICT and the pure path\n"
        "TRANSPILED, every answer cited. Query, reason, execute: one medium.")
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
