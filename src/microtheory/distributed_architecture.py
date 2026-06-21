"""Microtheory worked example #17 — a distributed system's architecture as knowledge.

On a real platform — dozens of services, third-party APIs, ML models, a legacy
mainframe, queues — the questions that keep an architect up at night are not about
any one component but about the WHOLE GRAPH:

  * What is our full trust boundary — every black box we depend on, transitively?
  * If the legacy mainframe changes, what is the blast radius?
  * Where does customer PII flow into an unaudited third-party black box? (compliance)
  * Which entry points can cause a write or emit an event (side effects)?

By hand, on a large system, these are error-prone and never quite current. Here the
architecture IS knowledge: each service is an ordered microtheory whose `CALL` and
`OPAQUE` steps ARE its connectors and trust boundaries; the architecture graph is
EXTRACTED from the programs-as-data, then QUERIED and REASONED over, every finding
cited. Composition (`CALL`) + black boxes (`OPAQUE`) + effects + reasoning.

A small but realistic payments platform stands in for the large one.

Run (from src/):  python -m microtheory.distributed_architecture
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.reason import Rule, Derivation, apply_all_rules_to_fixpoint
from kb.execute import run, ExecError

LINE = "=" * 78


def prog(scope, ops, source="platform"):
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# --- the services, as ordered microtheories ---------------------------------
# Their CALL / OPAQUE steps are the architecture: who calls whom, and which
# components are black boxes (external services, ML models, the legacy mainframe).
SERVICES = {
    "api_gateway":          [("CALL", "order_service"), ("RET", None)],
    "order_service":        [("CALL", "fraud_service"), ("CALL", "fx_service"),
                             ("CALL", "kyc_service"), ("CALL", "ledger_service"),
                             ("CALL", "notification_service"), ("RET", None)],
    "fraud_service":        [("OPAQUE", "fraud_ml_model"), ("RET", None)],
    "fx_service":           [("FETCH", "order|AMOUNT"), ("OPAQUE", "fx_rate_oracle"),
                             ("MUL", None), ("RET", None)],     # executable: amount * fx_rate
    "kyc_service":          [("OPAQUE", "kyc_provider"), ("RET", None)],
    "ledger_service":       [("OPAQUE", "legacy_mainframe"), ("CALL", "reconciliation_service"),
                             ("RET", None)],
    "reconciliation_service": [("RET", None)],
    "notification_service": [("RET", None)],
}

# --- declared facts the program text doesn't carry (effects, data sensitivity) ---
DECLARED = [
    Triple("order", "AMOUNT", "100", "order_event", 0, None, None, 1.0),
    # which services touch regulated personal data
    Triple("order_service", "HANDLES_PII", "customer_record", "data_map", 0, None, None, 1.0),
    Triple("fraud_service", "HANDLES_PII", "customer_record", "data_map", 0, None, None, 1.0),
    Triple("kyc_service", "HANDLES_PII", "customer_record", "data_map", 0, None, None, 1.0),
    # external side effects
    Triple("ledger_service", "WRITES_TO", "ledger_db", "data_map", 0, None, None, 1.0),
    Triple("reconciliation_service", "WRITES_TO", "recon_db", "data_map", 0, None, None, 1.0),
    Triple("notification_service", "EMITS_EVENT", "notification_queue", "data_map", 0, None, None, 1.0),
]


def extract_architecture(kb: KB):
    """Programs-as-data -> architecture-as-data: read each service's CALL and OPAQUE
    steps off its own microtheory, as CALLS / OPAQUE_DEP facts. (Same move as
    deriving a program's FETCH dependencies in example #9 — structure from the
    program itself, no source parsing.)"""
    facts = []
    for scope in SERVICES:
        for t in kb.ordered_scope(scope):
            if t.relation == "CALL" and t.object:
                facts.append(Triple(scope, "CALLS", t.object, f"arch:{scope}", 0, None, None, 1.0))
            elif t.relation == "OPAQUE" and t.object:
                facts.append(Triple(scope, "OPAQUE_DEP", t.object, f"arch:{scope}", 0, None, None, 1.0))
    return facts


def _reach(edges: dict, start: str) -> set:
    """Forward transitive reachability over an adjacency map (BFS)."""
    seen, stack = set(), [start]
    while stack:
        n = stack.pop()
        for m in edges.get(n, ()):
            if m not in seen:
                seen.add(m); stack.append(m)
    return seen


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    # one KB: the service programs + declared facts + the extracted architecture graph
    prog_triples = [t for s, ops in SERVICES.items() for t in prog(s, ops)]
    code_kb = KB(triples=prog_triples, alias_map={}, n_articles=0)
    kb = KB(triples=prog_triples + DECLARED + extract_architecture(code_kb),
            alias_map={}, n_articles=0)

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #17 — a payments platform's architecture as knowledge")
    print(LINE)

    calls = {}
    for i in kb.by_relation.get("CALLS", []):
        t = kb.triples[i]
        calls.setdefault(t.subject, []).append(t.object)

    # [1] the FULL TRUST BOUNDARY — every black box reachable from the gateway -----
    reachable = {"api_gateway"} | _reach(calls, "api_gateway")
    opaque_dep = {}
    for i in kb.by_relation.get("OPAQUE_DEP", []):
        t = kb.triples[i]
        opaque_dep.setdefault(t.subject, []).append(t.object)
    boundary = {b for s in reachable for b in opaque_dep.get(s, [])}
    print(f"\n[1] full trust boundary (black boxes reachable from api_gateway):\n    {sorted(boundary)}")
    check("trust boundary = the four external black boxes",
          boundary == {"fraud_ml_model", "fx_rate_oracle", "kyc_provider", "legacy_mainframe"})

    # [2] COMPLIANCE RISK — PII flowing into a black box (derived by the reasoner) --
    def pii_to_blackbox(kbx):
        out = []
        pii = {kbx.triples[i].subject for i in kbx.by_relation.get("HANDLES_PII", [])}
        for i in kbx.by_relation.get("OPAQUE_DEP", []):
            t = kbx.triples[i]
            if t.subject in pii:
                out.append(Derivation("compliance_risk",
                                      Triple(t.subject, "COMPLIANCE_RISK", t.object, "(derived)", -1),
                                      [t], f"{t.subject} handles PII and calls black box {t.object}"))
        return out

    ext, _d, _s = apply_all_rules_to_fixpoint(
        kb, rules=[Rule("pii_to_blackbox", pii_to_blackbox)],
        propagate_confidence=False, propagate_temporal=False)
    risks = {(t.subject, t.object) for t in ext.triples if t.relation == "COMPLIANCE_RISK"}
    print(f"\n[2] compliance risk (PII -> black box), derived & cited:\n    {sorted(risks)}")
    check("fraud_service sends PII to the fraud ML model", ("fraud_service", "fraud_ml_model") in risks)
    check("kyc_service sends PII to the third-party KYC provider", ("kyc_service", "kyc_provider") in risks)
    check("order_service handles PII but has no DIRECT black box -> not flagged",
          not any(s == "order_service" for s, _b in risks))

    # [3] BLAST RADIUS — what depends on the legacy mainframe? ---------------------
    holder = next(s for s, boxes in opaque_dep.items() if "legacy_mainframe" in boxes)  # ledger_service
    blast = {s for s in SERVICES if holder in ({s} | _reach(calls, s))}
    print(f"\n[3] blast radius of 'legacy_mainframe' (depends on {holder}):\n    {sorted(blast)}")
    check("blast radius includes the gateway and the orchestrator",
          {"api_gateway", "order_service", "ledger_service"} <= blast
          and "notification_service" not in blast)

    # [4] SIDE-EFFECT REACHABILITY — can the gateway cause a write/emit? -----------
    effectful = {kb.triples[i].subject for i in kb.by_relation.get("WRITES_TO", [])} \
        | {kb.triples[i].subject for i in kb.by_relation.get("EMITS_EVENT", [])}
    gw_effects = ({"api_gateway"} | _reach(calls, "api_gateway")) & effectful
    print(f"\n[4] services with external effects reachable from api_gateway:\n    {sorted(gw_effects)}")
    check("the gateway transitively causes writes and emits", len(gw_effects) >= 2)

    # [5] OPAQUE in EXECUTION — fx_service won't run without its black box ----------
    print("\n[5] executing fx_service (amount * fx_rate, the rate a black box):")
    check("fx_service refuses to run without the fx_rate oracle",
          _refuses(lambda: run(kb, "fx_service", {})))
    fx = run(kb, "fx_service", {}, oracles={"fx_rate_oracle": 1.1})
    print(f"    with oracle fx_rate=1.1 -> {fx.value}  (unverified: {fx.opaque})")
    check("fx_service runs with the oracle (100 * 1.1 = 110), value flagged unverified",
          abs(fx.value - 110.0) < 1e-9 and fx.opaque)

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "The architecture is cited knowledge: services are microtheories, their CALL\n"
        "and OPAQUE steps are the connectors and trust boundaries, effects and data\n"
        "sensitivity are declared facts. The graph-spanning questions an architect\n"
        "dreads — full trust boundary, blast radius, PII-into-a-black-box, side-effect\n"
        "reach — are then queries and derivations over one cited KB, not whiteboard\n"
        "archaeology. And the verifiable parts still execute; the black boxes don't.")
    print(LINE)
    if failures:
        sys.exit(1)


def _refuses(fn) -> bool:
    try:
        fn(); return False
    except ExecError:
        return True


if __name__ == "__main__":
    main()
