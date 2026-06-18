"""Microtheory worked example #9 — provenance-native knowledge computing.

The capstone. Everything else built a piece; this shows the whole shape in ONE
knowledge base: facts, a relational rule, and procedures/programs are all the same
substance — scoped, ordered, cited triples — and the SAME engine can QUERY them,
REASON over them, and EXECUTE them, with provenance unbroken from input data ->
computation -> derived data. The knowledge base is the computer.

It demonstrates, against one small lending KB, the five defining properties:

  1. CODE = DATA = RULES, ONE MEDIUM. A program is not text operating on a
     database; it is knowledge sitting beside the facts, in the same triple shape.
  2. THE SYSTEM REASONS ABOUT ITS OWN ALGORITHMS. Because a procedure is data, we
     can compute a property of it — here, its data dependencies — by querying the
     program itself.
  3. EVERY RESULT IS AUDITABLE TO ITS CAUSES. A computed number cites the facts it
     read and re-enters the KB as a fact the next step can use.
  4. MULTI-FRAMED / VERSIONED BY CONSTRUCTION. Two versions of the pricing
     algorithm are two microtheories that coexist; we diff them.
  5. MEANING / PERFORMANCE SEPARATED. The canonical form is inspectable data;
     speed is a derived cache — interpret and transpile give the identical answer.

And it runs all three faculties on the one KB: query (`out_facts`), reason
(`apply_all_rules_to_fixpoint`), execute (`run` / `run_compiled`).

Run (from src/):  python -m microtheory.paradigm
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.reason import Rule, Derivation, apply_all_rules_to_fixpoint
from kb.execute import run
from kb.transpile import run_compiled

LINE = "=" * 78


def prog(scope, ops, source="pricing_policy"):
    """Author a program as an ordered microtheory (relation=opcode, object=operand)."""
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# --- DATA: ordinary facts (global scope) ----------------------------------
FACTS = [
    Triple("alice", "LOAN_AMOUNT", "12000", "application_8841", 0),
    Triple("policy", "RATE", "0.07", "rate_card_2024", 0),
    Triple("policy", "TERM_MONTHS", "24", "rate_card_2024", 0),
    # a referral chain — for the relational reasoner to extend
    Triple("alice", "REFERRED_BY", "bob", "crm", 0),
    Triple("bob", "REFERRED_BY", "carol", "crm", 0),
]

# --- ALGORITHM v1: simple-interest monthly payment, reading the KB's facts --
#   interest = amount * rate * (term_months / 12); monthly = (amount + interest) / term_months
PAYMENT = [
    ("FETCH", "alice|LOAN_AMOUNT"), ("FETCH", "policy|RATE"), ("MUL", None),  # amount*rate
    ("FETCH", "policy|TERM_MONTHS"), ("PUSH", 12), ("DIV", None), ("MUL", None),  # *years -> interest
    ("FETCH", "alice|LOAN_AMOUNT"), ("ADD", None),                            # + amount -> total
    ("FETCH", "policy|TERM_MONTHS"), ("DIV", None), ("RET", None),            # / term -> monthly
]
# --- ALGORITHM v2: a promotional half-rate variant (a SECOND microtheory) ---
PAYMENT_PROMO = [
    ("FETCH", "alice|LOAN_AMOUNT"), ("FETCH", "policy|RATE"), ("PUSH", 0.5), ("MUL", None),  # half rate
    ("MUL", None),
    ("FETCH", "policy|TERM_MONTHS"), ("PUSH", 12), ("DIV", None), ("MUL", None),
    ("FETCH", "alice|LOAN_AMOUNT"), ("ADD", None),
    ("FETCH", "policy|TERM_MONTHS"), ("DIV", None), ("RET", None),
]
# --- A pure-arithmetic variant (no FETCH) for the meaning/performance split -
AMORTIZE = [
    ("LOAD", "amount"), ("LOAD", "rate"), ("MUL", None), ("LOAD", "years"), ("MUL", None),
    ("LOAD", "amount"), ("ADD", None), ("LOAD", "termm"), ("DIV", None), ("RET", None),
]


def transitive_referred(kb: KB):
    """A real Horn rule: REFERRED_BY is transitive. Runs on the SAME KB that holds
    the facts and the programs."""
    out = []
    edges = [kb.triples[i] for i in kb.by_relation.get("REFERRED_BY", [])]
    by_subj = {}
    for t in edges:
        by_subj.setdefault(t.subject, []).append(t.object)
    for t in edges:
        for z in by_subj.get(t.object, []):
            if t.subject != z:
                out.append(Derivation(
                    "transitive_referred",
                    Triple(t.subject, "REFERRED_BY", z, "(derived)", -1),
                    [t], f"{t.subject} referred by {t.object} referred by {z}"))
    return out


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #9 — provenance-native knowledge computing")
    print(LINE)

    kb = KB(triples=FACTS + prog("payment", PAYMENT) + prog("payment_promo", PAYMENT_PROMO)
            + prog("amortize", AMORTIZE),
            alias_map={}, n_articles=0)

    # 1. CODE = DATA = RULES, ONE MEDIUM --------------------------------------
    n_data = sum(1 for t in kb.triples if t.scope is None)
    n_prog = sum(1 for t in kb.triples if t.scope is not None)
    print(f"\n[1] One medium: {len(kb.triples)} triples = {n_data} data facts + "
          f"{n_prog} program steps.")
    print(f"    programs present as microtheories: {sorted(kb.scopes())}")
    check("the program is just triples, retrievable as data",
          len(kb.ordered_scope("payment")) == len(PAYMENT)
          and all(isinstance(t, Triple) for t in kb.ordered_scope("payment")))

    # 2. THE SYSTEM REASONS ABOUT ITS OWN ALGORITHM ---------------------------
    # Compute the data dependencies of `payment` BY QUERYING THE PROGRAM ITSELF:
    # which facts does it FETCH? No source parsing — it's just data.
    deps = sorted({t.object for t in kb.ordered_scope("payment") if t.relation == "FETCH"})
    print(f"\n[2] Reason about the algorithm — `payment`'s data dependencies, derived")
    print(f"    by querying the program-as-data: {deps}")
    check("dependencies of the algorithm computed from the algorithm-as-data",
          deps == ["alice|LOAN_AMOUNT", "policy|RATE", "policy|TERM_MONTHS"])

    # 3. EXECUTE over the facts; result is auditable and re-enters as a fact ---
    r = run(kb, "payment", {})
    print(f"\n[3] Execute over the KB's own facts: monthly payment = {r.value}")
    print("    cited inputs (provenance spans the data):")
    for c in r.reads:
        print(f"       {c}")
    check("payment computed from the facts (amount 12000, 7%, 24mo -> 570)", r.value == 570.0)
    # the result re-enters the KB as an ordinary fact, queryable like any other
    kb2 = KB(triples=kb.triples + [Triple("alice", "MONTHLY_PAYMENT", str(r.value),
             "computed:payment", -1)], alias_map={}, n_articles=0)
    check("the computed result re-enters as a queryable fact",
          [t.object for t in kb2.out_facts("alice", "MONTHLY_PAYMENT")] == ["570.0"])

    # ...and the relational REASONER runs on the same KB and derives a new fact
    ext, derivs, _ = apply_all_rules_to_fixpoint(
        kb2, rules=[Rule("transitive_referred", transitive_referred)],
        propagate_confidence=False, propagate_temporal=False)
    derived = {(t.subject, t.object) for t in ext.triples if t.relation == "REFERRED_BY"}
    print(f"\n    the reasoner (same KB) derives the transitive referral: "
          f"{'alice<-carol' if ('alice','carol') in derived else 'MISSING'}")
    check("query, execute, and reason all run on the one KB",
          ("alice", "carol") in derived)

    # 4. MULTI-FRAMED / VERSIONED ALGORITHM -----------------------------------
    v1 = [f"{t.relation} {t.object}".strip() for t in kb.ordered_scope("payment")]
    v2 = [f"{t.relation} {t.object}".strip() for t in kb.ordered_scope("payment_promo")]
    extra = [step for step in v2 if step not in v1]
    r_promo = run(kb, "payment_promo", {})
    print(f"\n[4] Two versions coexist as microtheories. promo adds steps {extra};")
    print(f"    standard payment = {r.value}, promo (half-rate) = {r_promo.value}")
    check("both algorithm versions coexist and give different, cited results",
          r_promo.value == 535.0 and r_promo.value != r.value)

    # 5. MEANING / PERFORMANCE SEPARATED --------------------------------------
    args = {"amount": 12000, "rate": 0.07, "years": 2, "termm": 24}
    interpreted = run(kb, "amortize", args).value
    compiled = run_compiled(kb, "amortize", args)       # transpiled to Python, a derived cache
    print(f"\n[5] Same algorithm, two execution strategies (canonical data vs cache):")
    print(f"    interpreter -> {interpreted} ; transpiled -> {compiled}")
    check("interpreter and transpiler give the identical answer", interpreted == compiled == 570.0)

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "One knowledge base; one provenance model; three faculties (query, reason,\n"
        "execute) over the same scoped, ordered, cited triples. Facts, rules, and\n"
        "programs are the same substance — so computation is queryable, auditable,\n"
        "versionable knowledge, and the boundary between the database, the rules,\n"
        "and the code is gone. The knowledge base is the computer.")
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
