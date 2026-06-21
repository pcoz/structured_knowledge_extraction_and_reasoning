"""Microtheory worked example #13 — a whole decision engine, all faculties at once.

The grand capstone: ONE small, self-contained knowledge base that exercises EVERY
SKEAR faculty to make a real, auditable decision — "may this clinician prescribe
this drug to this patient, and at what safe dose?" — with nothing but cited facts
and ordered microtheories.

What it uses (all of it):
  * QUERY      — look a cited fact straight out of the KB.
  * REASON     — derive new facts to fixpoint: transitive supervision + colleagues.
  * EXECUTE    — ordered-microtheory programs combining:
       - FETCH (literal `drug|REQUIRES` and parametric `@clinician|PERMISSIONS`),
       - BITWISE  AND / OR / XOR / NOT / SHL / SHR  (entitlements, capability gaps,
         granting, dose halving),
       - arithmetic + compare, control flow (JZ/JMP), CALL (composition + recursion),
       - EMIT (an audit trail of the decision).
  * CONFLICT   — contradictory data (two clearance levels) is flagged, not used.
  * PERFORMANCE — a pure sub-program runs identically via interpreter and transpiler.
  * PROVENANCE — every answer cites the facts it read.

Each numeric result is checked against a plain-Python anchor.

Run (from src/):  python -m microtheory.decision_engine
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

# Capability bits.
VIEW, DIAGNOSE, PRESCRIBE, CONTROLLED = 1, 2, 4, 8


def prog(scope, ops, source="clinical_policy"):
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# --- CITED domain facts ------------------------------------------------------
FACTS = [
    # clinicians: effective permission masks (cited to the access-control policy)
    Triple("dr_jones", "PERMISSIONS", str(VIEW | DIAGNOSE | PRESCRIBE | CONTROLLED), "rbac_2026", 0, None, None, 1.0),
    Triple("dr_smith", "PERMISSIONS", str(VIEW | DIAGNOSE | PRESCRIBE),              "rbac_2026", 0, None, None, 1.0),
    Triple("nurse_amy", "PERMISSIONS", str(VIEW | DIAGNOSE),                         "rbac_2026", 0, None, None, 1.0),
    # supervision chain + shared department (for the reasoner)
    Triple("dr_jones", "SUPERVISES", "dr_smith",  "org_chart", 0, None, None, 1.0),
    Triple("dr_smith", "SUPERVISES", "nurse_amy", "org_chart", 0, None, None, 1.0),
    Triple("dr_jones", "DEPARTMENT", "cardiology", "hr", 0, None, None, 1.0),
    Triple("dr_smith", "DEPARTMENT", "cardiology", "hr", 0, None, None, 1.0),
    # formulary: what each drug requires (a privilege mask) and its base dose
    Triple("drug_morphine", "REQUIRES", str(PRESCRIBE | CONTROLLED), "formulary_2026", 0, None, None, 1.0),
    Triple("drug_morphine", "BASE_DOSE", "100", "formulary_2026", 0, None, None, 1.0),
    Triple("drug_aspirin", "REQUIRES", str(PRESCRIBE), "formulary_2026", 0, None, None, 1.0),
    Triple("drug_aspirin", "BASE_DOSE", "500", "formulary_2026", 0, None, None, 1.0),
    # patient
    Triple("patient_7", "WEIGHT_FACTOR", "3", "ehr", 0, None, None, 1.0),
]

DOSE_CEILING = 200

# --- PROGRAMS ----------------------------------------------------------------
# safe_dose(d): recursively halve (SHR) until <= ceiling. CALL recursion + SHR.
SAFE_DOSE = [
    ("STORE", "d"),                                          # 0
    ("LOAD", "d"), ("PUSH", DOSE_CEILING), ("LE", None), ("JZ", 7),  # 1-4 if d<=ceil fall thru
    ("LOAD", "d"), ("RET", None),                            # 5-6 base case
    ("LOAD", "d"), ("PUSH", 1), ("SHR", None),               # 7-9 d >> 1
    ("CALL", "safe_dose"), ("RET", None),                    # 10-11 recurse
]
# popcount(n): count set bits via n & (n-1). CALL-able (arg on stack).
POPCOUNT = [
    ("STORE", "n"), ("PUSH", 0), ("STORE", "c"),                       # 0-2
    ("LOAD", "n"), ("PUSH", 0), ("NE", None), ("JZ", 18),              # 3-6 while n!=0
    ("LOAD", "c"), ("PUSH", 1), ("ADD", None), ("STORE", "c"),         # 7-10 c+=1
    ("LOAD", "n"), ("LOAD", "n"), ("PUSH", 1), ("SUB", None),
    ("AND", None), ("STORE", "n"),                                     # 11-16 n &= n-1
    ("JMP", 3),                                                        # 17
    ("LOAD", "c"), ("RET", None),                                      # 18-19
]
# decide(@clinician,@drug,@patient): entitlement (AND + superset ==), then dose
# (MUL + CALL safe_dose), EMIT the audit value; refuse (-1) otherwise.
DECIDE = [
    ("FETCH", "@drug|REQUIRES"), ("DUP", None),              # 0-1 req req
    ("FETCH", "@clinician|PERMISSIONS"), ("AND", None),      # 2-3 req (req & perms)
    ("EQ", None), ("JZ", 12),                                # 4-5 entitled? else -> 12
    ("FETCH", "@drug|BASE_DOSE"), ("FETCH", "@patient|WEIGHT_FACTOR"),  # 6-7
    ("MUL", None), ("CALL", "safe_dose"),                    # 8-9 dose0 -> safe dose
    ("EMIT", None), ("RET", None),                           # 10-11 audit + return dose
    ("PUSH", -1), ("EMIT", None), ("RET", None),             # 12-14 refusal
]
# gap(@senior,@junior): capability analysis with OR / XOR / NOT, returns popcount
# of the symmetric difference. EMITs differ, extra-held-by-senior, and union.
GAP = [
    ("FETCH", "@senior|PERMISSIONS"), ("STORE", "s"),        # 0-1
    ("FETCH", "@junior|PERMISSIONS"), ("STORE", "j"),        # 2-3
    ("LOAD", "s"), ("LOAD", "j"), ("XOR", None), ("EMIT", None), ("POP", None),   # 4-8 differ
    ("LOAD", "s"), ("LOAD", "j"), ("NOT", None), ("AND", None), ("EMIT", None), ("POP", None),  # 9-14 extra = s & ~j
    ("LOAD", "s"), ("LOAD", "j"), ("OR", None), ("EMIT", None), ("POP", None),    # 15-19 union
    ("LOAD", "s"), ("LOAD", "j"), ("XOR", None), ("CALL", "popcount"), ("RET", None),  # 20-24 count(differ)
]
# grant(@clinician): add the CONTROLLED capability via SHL + OR (1 SHL 3 == 8).
GRANT = [
    ("FETCH", "@clinician|PERMISSIONS"), ("PUSH", 1), ("PUSH", 3), ("SHL", None),  # 0-3
    ("OR", None), ("RET", None),                             # 4-5
]
# pure arithmetic (no FETCH/CALL/bitwise) — for the interpreter-vs-transpiler check
LINEAR = [("LOAD", "base"), ("LOAD", "factor"), ("MUL", None), ("RET", None)]


# --- reasoning rules ---------------------------------------------------------
def transitive_supervises(kb: KB):
    out, edges = [], [kb.triples[i] for i in kb.by_relation.get("SUPERVISES", [])]
    by_subj = {}
    for t in edges:
        by_subj.setdefault(t.subject, []).append(t.object)
    for t in edges:
        for z in by_subj.get(t.object, []):
            if t.subject != z:
                out.append(Derivation("transitive_supervises",
                                      Triple(t.subject, "SUPERVISES", z, "(derived)", -1),
                                      [t], f"{t.subject} supervises {t.object} supervises {z}"))
    return out


def colleagues(kb: KB):
    out, by_dept = [], {}
    for i in kb.by_relation.get("DEPARTMENT", []):
        t = kb.triples[i]
        by_dept.setdefault(t.object, []).append(t.subject)
    for subs in by_dept.values():
        for a in subs:
            for b in subs:
                if a != b:
                    out.append(Derivation("colleagues",
                                          Triple(a, "COLLEAGUE", b, "(derived)", -1),
                                          [], f"{a} and {b} share a department"))
    return out


# --- plain-Python anchors ----------------------------------------------------
def py_safe(d):
    while d > DOSE_CEILING:
        d >>= 1
    return d


def py_decide(perms, req, base, wf):
    return float(py_safe(base * wf)) if (req & perms) == req else -1.0


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    kb = KB(triples=FACTS + prog("safe_dose", SAFE_DOSE) + prog("popcount", POPCOUNT)
            + prog("decide", DECIDE) + prog("gap", GAP) + prog("grant", GRANT)
            + prog("linear", LINEAR),
            alias_map={}, n_articles=0)

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #13 — a decision engine using ALL of SKEAR")
    print(LINE)

    # [1] QUERY ----------------------------------------------------------------
    base = kb.out_facts("drug_morphine", "BASE_DOSE")
    print(f"\n[1] QUERY: morphine base dose = {base[0].object}  (cited: {base[0].source_article})")
    check("query returns the cited base-dose fact", base and base[0].object == "100")

    # [2] REASON ---------------------------------------------------------------
    ext, derivs, _ = apply_all_rules_to_fixpoint(
        kb, rules=[Rule("supervises", transitive_supervises), Rule("colleagues", colleagues)],
        propagate_confidence=False, propagate_temporal=False)
    sup = {(t.subject, t.object) for t in ext.triples if t.relation == "SUPERVISES"}
    col = {(t.subject, t.object) for t in ext.triples if t.relation == "COLLEAGUE"}
    print(f"\n[2] REASON to fixpoint: dr_jones transitively supervises nurse_amy? "
          f"{('dr_jones','nurse_amy') in sup}; jones-smith colleagues? {('dr_jones','dr_smith') in col}")
    check("transitive supervision derived", ("dr_jones", "nurse_amy") in sup)
    check("colleague relation derived", ("dr_jones", "dr_smith") in col)

    # [3] EXECUTE — the decision (entitlement + dose + audit), parametric -------
    print("\n[3] EXECUTE the decision engine (FETCH + bitwise + arithmetic + CALL + EMIT):")
    cases = [
        ("dr_jones", "drug_morphine", "patient_7", 15, 12, 100),   # entitled -> 150
        ("dr_smith", "drug_morphine", "patient_7", 7, 12, 100),    # lacks CONTROLLED -> refuse
        ("dr_smith", "drug_aspirin", "patient_7", 7, 4, 500),      # entitled -> 187
        ("nurse_amy", "drug_aspirin", "patient_7", 3, 4, 500),     # lacks PRESCRIBE -> refuse
    ]
    for clin, drug, pat, perms, req, bdose in cases:
        r = run(kb, "decide", {"clinician": clin, "drug": drug, "patient": pat})
        want = py_decide(perms, req, bdose, 3)
        verdict = "REFUSED" if r.value == -1.0 else f"dose {int(r.value)}"
        print(f"    {clin:9s} + {drug:13s} -> {verdict:11s}  (audit EMIT={r.outputs})")
        check(f"decide({clin},{drug}) == anchor {want}", r.value == want)
    rj = run(kb, "decide", {"clinician": "dr_jones", "drug": "drug_morphine", "patient": "patient_7"})
    check("decision is cited to the facts it read", any("formulary_2026" in c for c in rj.reads))

    # [4] EXECUTE — capability gap (OR / XOR / NOT) and grant (SHL) -------------
    g = run(kb, "gap", {"senior": "dr_jones", "junior": "dr_smith"})
    print(f"\n[4] EXECUTE capability analysis (XOR/NOT/AND/OR): "
          f"differ/extra/union EMIT={[int(x) for x in g.outputs]}, #differences={int(g.value)}")
    check("gap: jones has exactly 1 capability beyond smith (CONTROLLED)", g.value == 1.0)
    check("gap: EMITs symmetric-difference, extra, and union masks", g.outputs == [8.0, 8.0, 15.0])
    granted = run(kb, "grant", {"clinician": "dr_smith"}).value
    check("grant via SHL+OR adds CONTROLLED to dr_smith (7 -> 15)", granted == 15.0)

    # [5] CONFLICT -------------------------------------------------------------
    contradictory = kb.triples + [
        Triple("dr_jones", "CLEARANCE", "3", "badge_system", 0, None, None, 1.0),
        Triple("dr_jones", "CLEARANCE", "5", "legacy_import", 0, None, None, 1.0)]
    kb_c = KB(triples=contradictory, alias_map={}, n_articles=0)
    onto = Ontology(functional_properties={"CLEARANCE"})
    policy = ChainPolicy([AuthorityWinsPolicy(), LatestWinsPolicy(), HighestConfidencePolicy()])
    _, _, conflicts, _ = apply_with_conflict_resolution(kb_c, ontology=onto, policy=policy)
    print(f"\n[5] CONFLICT: two clearance levels for dr_jones -> {len(conflicts)} conflict(s) flagged")
    check("contradictory functional fact is flagged, not silently used", len(conflicts) >= 1)

    # [6] PERFORMANCE: interpreter vs transpiler agree on a pure sub-program ----
    args = {"base": 100, "factor": 3}
    interp = run(kb, "linear", args).value
    comp = run_compiled(kb, "linear", args)
    print(f"\n[6] PERFORMANCE: linear dose interpreter={interp} transpiled={comp}")
    check("interpreter and transpiler agree", interp == comp == 300.0)

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "One self-contained KB makes a complete, auditable clinical decision: it is\n"
        "QUERIED, REASONED over to fixpoint, and EXECUTED — entitlements by bitwise\n"
        "masks, dosing by recursive arithmetic, an EMITted audit trail — with bad data\n"
        "caught by CONFLICT detection and the hot path optionally TRANSPILED, every\n"
        "answer cited. Facts, rules, and programs, one medium: the KB is the computer.")
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
