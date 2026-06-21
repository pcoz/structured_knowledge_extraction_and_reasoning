"""Microtheory worked example #19 — interacting decisioning systems that RESOLVE
THEMSELVES (a real-world transaction-approval flow).

This is the capstone for DISPATCH. A real approval decision is not one function —
it is several INDEPENDENT decision systems that interact:

    sanctions screen  (external)        an authority we don't own — consulted, not coded
        -> channel router               picks the risk model for THIS payment rail
            -> risk model (per channel)  card / wire / crypto each score differently
                -> tier classifier       score -> low / medium / high (cited thresholds)
                    -> action policy      tier -> approve / review / decline

The point: the top-level `decide` program contains NO business branches. It never
names "crypto" or "high-risk" or "decline" in its control flow. It consults the
external screen, then lets the cited DATA route itself — `FETCH @txn|CHANNEL`
DISPATCHes to a risk model; the resulting score is classified; the tier DISPATCHes
to an action. Feed a different transaction (different facts) and the correct
decision RESOLVES ITSELF along a different path, carrying the provenance of every
fact each subsystem touched. Add a payment rail or an action: drop in a microtheory
and a table row — the orchestrator is untouched.

The systems genuinely interact: the `review` action RE-READS the transaction's
amount and escalates a medium-risk wire to a decline on its own authority; the
external `sanctions` screen can hard-stop the whole flow before any risk model runs.
Without the screen's verdict the decision CANNOT resolve — `decide` refuses, because
a real approval must consult that external system, not guess it.

Faculties used: OPAQUE (the external screen), parametric FETCH (one risk model per
rail, over any transaction), DISPATCH (channel->model, tier->action), CALL (the tier
classifier), arithmetic + branches. All decidable; all cited.

Run (from src/):  python -m microtheory.decisioning
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.execute import run, ExecError

LINE = "=" * 78


def prog(scope, ops, source="approval_engine"):
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# --- CITED transactions (the data the systems decide over) -------------------
# CHANNEL: 1=card, 2=wire, 3=crypto.  GEO_RISK: a 0/1 flag from a geo system.
def _txn(tid, channel, amount, velocity, geo, src):
    return [
        Triple(tid, "CHANNEL", str(channel), src, 0, None, None, 1.0),
        Triple(tid, "AMOUNT", str(amount), src, 0, None, None, 1.0),
        Triple(tid, "VELOCITY", str(velocity), src, 0, None, None, 1.0),
        Triple(tid, "GEO_RISK", str(geo), src, 0, None, None, 1.0),
    ]


TXNS = (
    _txn("txn1", 1, 500, 1, 0, "card_gateway_2026")        # card, tiny -> approve
    + _txn("txn2", 2, 30000, 0, 1, "wire_rail_2026")       # wire, large, geo -> review->escalate
    + _txn("txn3", 3, 2000, 5, 1, "crypto_desk_2026")      # crypto, medium -> review (stays)
    + _txn("txn4", 3, 9000, 9, 1, "crypto_desk_2026")      # crypto, hot -> decline
)

# --- RISK MODELS (one per payment rail), parametric over @txn ----------------
# Each is entered with the transaction id on the stack; it STОREs it, then FETCHes
# that transaction's OWN cited facts. Different rails weight risk differently.
RISK_CARD = [("STORE", "txn"),
             ("FETCH", "@txn|AMOUNT"), ("PUSH", 100), ("DIV", None),     # amount/100
             ("FETCH", "@txn|VELOCITY"), ("PUSH", 2), ("MUL", None), ("ADD", None),  # + vel*2
             ("FETCH", "@txn|GEO_RISK"), ("PUSH", 5), ("MUL", None), ("ADD", None),  # + geo*5
             ("RET", None)]
RISK_WIRE = [("STORE", "txn"),
             ("FETCH", "@txn|AMOUNT"), ("PUSH", 1000), ("DIV", None),    # amount/1000
             ("FETCH", "@txn|GEO_RISK"), ("PUSH", 8), ("MUL", None), ("ADD", None),  # + geo*8
             ("RET", None)]
RISK_CRYPTO = [("STORE", "txn"),
               ("FETCH", "@txn|AMOUNT"), ("PUSH", 100), ("DIV", None),   # amount/100
               ("FETCH", "@txn|VELOCITY"), ("PUSH", 3), ("MUL", None), ("ADD", None),  # + vel*3
               ("FETCH", "@txn|GEO_RISK"), ("PUSH", 10), ("MUL", None), ("ADD", None), # + geo*10
               ("RET", None)]

# --- TIER CLASSIFIER (a CALL): score -> 1 low (<20) / 2 medium (<50) / 3 high ---
CLASSIFY_TIER = [
    ("STORE", "s"),                                  # 0  s = score
    ("LOAD", "s"), ("PUSH", 20), ("LT", None), ("JZ", 7),   # 1-4 if !(s<20) goto 7
    ("PUSH", 1), ("RET", None),                      # 5-6 low
    ("LOAD", "s"), ("PUSH", 50), ("LT", None), ("JZ", 13),  # 7-10 if !(s<50) goto 13
    ("PUSH", 2), ("RET", None),                      # 11-12 medium
    ("PUSH", 3), ("RET", None),                      # 13-14 high
]

# --- ACTION POLICY (per tier). Each is entered with the txn id on the stack. ---
# approve/decline consume the id and return their code; REVIEW interacts with the
# transaction again — it re-reads the amount and escalates a large one to a decline.
APPROVE = [("STORE", "txn"), ("PUSH", 1), ("RET", None)]      # 1 = approve
DECLINE = [("STORE", "txn"), ("PUSH", 3), ("RET", None)]      # 3 = decline
REVIEW = [
    ("STORE", "txn"),                                # 0
    ("FETCH", "@txn|AMOUNT"), ("PUSH", 25000), ("GT", None), ("JZ", 7),  # 1-4 amount>25000?
    ("PUSH", 3), ("RET", None),                      # 5-6 escalate -> decline
    ("PUSH", 2), ("RET", None),                      # 7-8 stays -> review (2)
]

# --- THE ORCHESTRATOR: consults the external screen, then lets data route itself.
# No business branch lives here — only the consult, the routing, and the wiring.
DECIDE = [
    ("OPAQUE", "sanctions_screen"),   # 0  external system: 0 = clear, 1 = hit (UNVERIFIED)
    ("JZ", 4),                        # 1  if clear, proceed; else hard-stop
    ("PUSH", 3), ("RET", None),       # 2-3 sanctions hit -> decline, before any risk model
    ("LOAD", "txn"),                  # 4  push the id for the risk model
    ("FETCH", "@txn|CHANNEL"),        # 5  the payment rail (a cited fact)
    ("DISPATCH", "1:risk_card,2:risk_wire,3:risk_crypto"),  # 6  rail -> risk model -> score
    ("CALL", "classify_tier"),        # 7  score -> tier
    ("LOAD", "txn"),                  # 8  push id for the action
    ("SWAP", None),                   # 9  -> [id, tier] (tier on top for the dispatch)
    ("DISPATCH", "1:approve,2:review,3:decline"),  # 10 tier -> action -> decision code
    ("RET", None),                    # 11
]

KB_ALL = KB(triples=(
    prog("risk_card", RISK_CARD) + prog("risk_wire", RISK_WIRE) + prog("risk_crypto", RISK_CRYPTO)
    + prog("classify_tier", CLASSIFY_TIER)
    + prog("approve", APPROVE) + prog("review", REVIEW) + prog("decline", DECLINE)
    + prog("decide", DECIDE) + TXNS), alias_map={}, n_articles=0)

ACTION = {1.0: "APPROVE", 2.0: "REVIEW", 3.0: "DECLINE"}


def decide(txn_id, sanctions=0):
    """Run the whole interacting system for one transaction. `sanctions` is the
    external screen's verdict (the oracle that opens that black box)."""
    return run(KB_ALL, "decide", {"txn": txn_id}, trace=True,
               oracles={"sanctions_screen": sanctions})


def main():
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            fails += 1

    print(LINE)
    print("INTERACTING DECISIONING SYSTEMS — the decision resolves itself from data")
    print(LINE)
    print("\n  Each transaction enters the SAME orchestrator; the cited facts route it:\n")
    for tid in ("txn1", "txn2", "txn3", "txn4"):
        res = decide(tid, sanctions=0)
        rails = {1: "card", 2: "wire", 3: "crypto"}
        ch = next((r for r in res.reads if tid in r and "CHANNEL" in r), "")
        print(f"  {tid}: -> {ACTION[res.value]:8s}  ({len(res.reads)} cited facts read along the way)")

    # The correct decision resolves itself for each — verified against the hand path.
    check("txn1 (card, tiny) resolves to APPROVE", decide('txn1', 0).value == 1.0)
    check("txn2 (wire, large) resolves to DECLINE — review escalated it",
          decide('txn2', 0).value == 3.0)
    check("txn3 (crypto, medium) resolves to REVIEW", decide('txn3', 0).value == 2.0)
    check("txn4 (crypto, hot) resolves to DECLINE", decide('txn4', 0).value == 3.0)

    # The external screen interacts FIRST: a sanctions hit hard-stops any transaction
    # before its risk model runs — even txn1, which would otherwise approve.
    check("a sanctions hit overrides everything (txn1 -> DECLINE)",
          decide('txn1', sanctions=1).value == 3.0)

    # Provenance resolves itself too: the decision cites the facts the subsystems read.
    r2 = decide('txn2', 0)
    check("the decision cites the transaction's own facts (txn2 AMOUNT)",
          any("txn2" in c and "AMOUNT" in c for c in r2.reads))
    check("the external screen is recorded as an UNVERIFIED black box",
          any("sanctions_screen" in o for o in r2.opaque))

    # Without consulting the external system, the decision CANNOT resolve — refused.
    refused = False
    try:
        run(KB_ALL, "decide", {"txn": "txn1"}, trace=False)   # no sanctions oracle
    except ExecError:
        refused = True
    check("with no sanctions verdict, the decision REFUSES to resolve (no guess)", refused)

    print("\n" + LINE)
    print("ALL PASS" if fails == 0 else f"{fails} FAILED")
    print("Five independent systems — one external — and not one business branch in")
    print("the orchestrator. The cited data routes itself through them via DISPATCH,")
    print("and the correct, fully-cited decision falls out the end. New rails and")
    print("actions are added as data, not as edits to the decision flow.")
    print(LINE)
    return fails


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
