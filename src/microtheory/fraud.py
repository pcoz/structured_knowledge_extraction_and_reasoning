"""Microtheory worked example #10 — fraud detection on one provenance-native KB.

An applied capstone. A single knowledge base holds the transactions (facts), the
fraud policy (facts you can tune), the risk-scoring rule (an ordered-microtheory
program), and the account-link graph — and all three faculties run over it:

  * QUERY    — read each transaction's fields from the KB.
  * EXECUTE  — a data-defined scoring program reads the policy weights/thresholds
               straight from the KB (`FETCH`) and returns a flag; change the
               policy facts and the behaviour changes with no code edit.
  * REASON   — the fixpoint reasoner derives a fraud RING by transitively closing
               SHARED_DEVICE links, catching accounts a per-transaction score
               misses.

Every decision is cited: a scored flag to the policy facts it read, a ring flag to
the link facts the reasoner chained. The fraud rule is inspectable, tunable,
versionable knowledge — not opaque code buried away from the data it judges.

Run (from src/):  python -m microtheory.fraud
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.reason import Rule, Derivation, apply_all_rules_to_fixpoint
from kb.execute import run

LINE = "=" * 78


def prog(scope, ops, source="fraud_policy"):
    """Author a program as an ordered microtheory (relation=opcode, object=operand)."""
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# --- DATA: transactions, as facts -----------------------------------------
# Each transaction has an account, an amount, a foreign flag (1/0), and the gap
# in hours since the previous transaction on that account (small = rapid-fire).
TXNS = {
    "txn1": {"account": "acctA", "amount": 4200, "foreign": 1, "gap": 1},   # big + foreign + rapid
    "txn2": {"account": "acctB", "amount": 120,  "foreign": 0, "gap": 50},  # nothing
    "txn3": {"account": "acctC", "amount": 5000, "foreign": 0, "gap": 100}, # big only (but ring)
    "txn4": {"account": "acctA", "amount": 90,   "foreign": 0, "gap": 0.5}, # rapid only
    "txn5": {"account": "acctD", "amount": 800,  "foreign": 1, "gap": 30},  # foreign only (but ring)
}


def transaction_facts():
    facts = []
    for tid, f in TXNS.items():
        facts.append(Triple(tid, "ACCOUNT", f["account"], "ledger", 0))
        facts.append(Triple(tid, "AMOUNT", str(f["amount"]), "ledger", 0))
        facts.append(Triple(tid, "FOREIGN", str(f["foreign"]), "ledger", 0))
        facts.append(Triple(tid, "GAP_HOURS", str(f["gap"]), "ledger", 0))
    return facts


# --- DATA: the fraud POLICY, as tunable facts (the "knobs") ----------------
def policy_facts(cutoff="0.6"):
    return [
        Triple("policy", "W_AMOUNT", "0.5", "risk_policy_v3", 0),
        Triple("policy", "W_FOREIGN", "0.3", "risk_policy_v3", 0),
        Triple("policy", "W_VELOCITY", "0.4", "risk_policy_v3", 0),
        Triple("policy", "AMOUNT_LIMIT", "3000", "risk_policy_v3", 0),
        Triple("policy", "RAPID_HOURS", "2", "risk_policy_v3", 0),
        Triple("policy", "CUTOFF", cutoff, "risk_policy_v3", 0),
    ]


# --- ALGORITHM: the risk score, as an ordered microtheory ------------------
# Inputs (per transaction): amount, foreign, gap. Weights/limits/cutoff are read
# from the KB's policy facts via FETCH, so the rule and its knobs live together.
#   over_limit = amount > AMOUNT_LIMIT ; rapid = gap < RAPID_HOURS
#   score = W_AMOUNT*over_limit + W_FOREIGN*foreign + W_VELOCITY*rapid
#   flag  = score >= CUTOFF
SCORE = [
    ("LOAD", "amount"), ("FETCH", "policy|AMOUNT_LIMIT"), ("GT", None),      # 0-2 over_limit
    ("FETCH", "policy|W_AMOUNT"), ("MUL", None),                            # 3-4 * weight
    ("LOAD", "foreign"), ("FETCH", "policy|W_FOREIGN"), ("MUL", None),      # 5-7 foreign term
    ("ADD", None),                                                          # 8 sum
    ("LOAD", "gap"), ("FETCH", "policy|RAPID_HOURS"), ("LT", None),         # 9-11 rapid
    ("FETCH", "policy|W_VELOCITY"), ("MUL", None),                          # 12-13 * weight
    ("ADD", None),                                                          # 14 score
    ("FETCH", "policy|CUTOFF"), ("GE", None), ("RET", None),                # 15-17 flag
]


def shared_device_transitive(kb: KB):
    """Horn rule: SHARED_DEVICE is transitive (accounts on a common device chain
    form one ring). Runs on the same KB as the transactions and the scorer."""
    out = []
    edges = [kb.triples[i] for i in kb.by_relation.get("SHARED_DEVICE", [])]
    by_subj = {}
    for t in edges:
        by_subj.setdefault(t.subject, []).append(t.object)
    for t in edges:
        for z in by_subj.get(t.object, []):
            if t.subject != z:
                out.append(Derivation(
                    "shared_device_transitive",
                    Triple(t.subject, "SHARED_DEVICE", z, "(derived)", -1),
                    [t], f"{t.subject} shares a device with {t.object} shares with {z}"))
    return out


def score_flags(kb, txn_ids):
    """QUERY each transaction's fields from the KB, then EXECUTE the scoring
    program over them. Returns (flagged set, citations for one flag)."""
    flagged, sample_cites = set(), []
    for tid in txn_ids:
        amount = float(kb.out_facts(tid, "AMOUNT")[0].object)
        foreign = float(kb.out_facts(tid, "FOREIGN")[0].object)
        gap = float(kb.out_facts(tid, "GAP_HOURS")[0].object)
        r = run(kb, "score", {"amount": amount, "foreign": foreign, "gap": gap})
        if r.value == 1.0:
            flagged.add(tid)
            if not sample_cites:
                sample_cites = r.reads          # the policy facts this score read
    return flagged, sample_cites


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #10 — fraud detection on one provenance-native KB")
    print(LINE)

    # link graph: acctC -- acctD -- acctE share devices (one ring); acctA/B don't
    links = [Triple("acctC", "SHARED_DEVICE", "acctD", "device_log", 0),
             Triple("acctD", "SHARED_DEVICE", "acctE", "device_log", 0)]
    kb = KB(triples=transaction_facts() + policy_facts() + prog("score", SCORE) + links,
            alias_map={}, n_articles=0)
    txn_ids = sorted(TXNS)

    # --- 1. EXECUTE the data-defined scoring rule (reads policy from the KB) --
    flagged, cites = score_flags(kb, txn_ids)
    print(f"\n[1] Risk score (rule + knobs are KB data). Flagged by score: {sorted(flagged)}")
    print("    one flag's cited policy inputs (provenance):")
    for c in cites:
        print(f"       {c}")
    check("the scoring program flags exactly the high-risk transaction (txn1)",
          flagged == {"txn1"})

    # --- 2. TUNE BY DATA: lower the cutoff fact, rerun the SAME program --------
    kb_loose = KB(triples=transaction_facts() + policy_facts(cutoff="0.3")
                  + prog("score", SCORE) + links, alias_map={}, n_articles=0)
    flagged_loose, _ = score_flags(kb_loose, txn_ids)
    print(f"\n[2] Lower CUTOFF 0.6 -> 0.3 (edit ONE fact). Flagged now: {sorted(flagged_loose)}")
    check("editing a policy fact widens the net, with no change to the program",
          flagged == {"txn1"} and flagged_loose == {"txn1", "txn3", "txn4", "txn5"})

    # --- 3. REASON: derive the fraud ring (transitive shared device) ----------
    ext, derivs, _ = apply_all_rules_to_fixpoint(
        kb, rules=[Rule("shared_device_transitive", shared_device_transitive)],
        propagate_confidence=False, propagate_temporal=False)
    ring_accounts = {t.subject for t in ext.triples if t.relation == "SHARED_DEVICE"} \
        | {t.object for t in ext.triples if t.relation == "SHARED_DEVICE"}
    print(f"\n[3] Reasoner closes SHARED_DEVICE transitively -> ring accounts: "
          f"{sorted(ring_accounts)}")
    check("the reasoner derives the transitive ring link acctC -> acctE",
          any(t.subject == "acctC" and t.object == "acctE"
              for t in ext.triples if t.relation == "SHARED_DEVICE"))
    ring_txns = {tid for tid in txn_ids
                 if kb.out_facts(tid, "ACCOUNT")[0].object in ring_accounts}
    print(f"    transactions on ring accounts (a score alone would miss): {sorted(ring_txns)}")
    check("ring membership flags the low-score transactions txn3 and txn5",
          ring_txns == {"txn3", "txn5"})

    # --- 4. COMBINE: fraud = high score OR ring member ------------------------
    fraud = flagged | ring_txns
    print(f"\n[4] Final fraud set (score OR ring): {sorted(fraud)}")
    check("the combined verdict catches all three, each cited to its cause",
          fraud == {"txn1", "txn3", "txn5"})

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "Transactions, the fraud policy, the scoring rule, and the account graph all\n"
        "live in one knowledge base. Query reads the transactions, execute runs the\n"
        "data-defined rule against the data-defined policy, and reason finds the ring\n"
        "— every flag traceable to the facts and steps that produced it, and the whole\n"
        "policy tunable and auditable as data rather than buried in code.")
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
