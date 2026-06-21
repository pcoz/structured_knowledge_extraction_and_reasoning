"""Microtheory worked example #12 — bit masks and flag-sets as auditable knowledge.

SKEAR's executor gained a bitwise opcode family — `AND`, `OR`, `XOR`, `NOT`,
`SHL`, `SHR` — the integer-logic sibling of the arithmetic ops.

Why this is broadly useful (not just here): a *bit mask* lets you store a whole
SET in a single number, and then membership, union, intersection, difference, and
counting each become ONE cheap, exact, deterministic operation. Many people don't
reach for this naturally — they model "which permissions does this role have?" or
"which days is the clinic open?" as lists or booleans — but the bitmask form is
compact, fast, and (the part SKEAR cares about) trivially auditable: a permission
check is `role.PERMISSIONS AND action.REQUIRES`, traceable to the policy document
the masks came from. This file shows the general techniques, each exercising one
of the new opcodes over the organisation's own CITED facts:

  AND  — does a role HAVE a capability? (set membership)            [1]
  OR   — combine two roles' capabilities                            (set union)        [2]
  NOT  — suspend one capability, keep the rest                      (clear a bit)      [3]
  XOR  — what CHANGED between two states?  (symmetric difference)   + popcount         [4]
  ==   — does an applicant have ALL required documents?  (superset) [5]
  SHL  — is the clinic open on weekday d?  (build a one-bit mask)   [6]
  SHR  — unpack a field packed into a larger number                (bit-field decode) [7]

Each rule is parametric (`FETCH @who|...`), so one rule serves every entity, and
each answer is provenance-bearing.

Run (from src/):  python -m microtheory.bitwise
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.execute import run

LINE = "=" * 78

# Vocabularies — each value is a documented single bit.
VIEW, EDIT, PRESCRIBE, ADMIN = 1, 2, 4, 8           # RBAC capabilities
DOC_ID, DOC_INCOME, DOC_RESIDENCY = 1, 2, 4         # required documents


def prog(scope, ops, source="rules"):
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# A reusable popcount tail (count the 1-bits left in variable `n`), starting at the
# given program address `at`; returns the count. Used to turn a mask into a count.
def popcount_from(at):
    return [
        ("PUSH", 0), ("STORE", "c"),                                   # at+0 .. at+1
        ("LOAD", "n"), ("PUSH", 0), ("NE", None), ("JZ", at + 17),     # at+2 .. at+5 while n!=0
        ("LOAD", "c"), ("PUSH", 1), ("ADD", None), ("STORE", "c"),     # at+6 .. at+9 c+=1
        ("LOAD", "n"), ("LOAD", "n"), ("PUSH", 1), ("SUB", None),
        ("AND", None), ("STORE", "n"),                                 # at+10 .. at+15 n &= n-1
        ("JMP", at + 2),                                               # at+16
        ("LOAD", "c"), ("RET", None),                                  # at+17 .. at+18
    ]


# --- CITED domain facts ------------------------------------------------------
FACTS = [
    Triple("role_nurse",  "PERMISSIONS", str(VIEW | EDIT),             "rbac_policy_2026", 0, None, None, 1.0),
    Triple("role_doctor", "PERMISSIONS", str(VIEW | EDIT | PRESCRIBE), "rbac_policy_2026", 0, None, None, 1.0),
    Triple("role_admin",  "PERMISSIONS", str(VIEW | ADMIN),            "rbac_policy_2026", 0, None, None, 1.0),
    Triple("act_prescribe", "REQUIRES",  str(PRESCRIBE),               "rbac_policy_2026", 0, None, None, 1.0),
    Triple("benefit_housing", "REQUIRED_DOCS", str(DOC_ID | DOC_INCOME | DOC_RESIDENCY), "reg_housing", 0, None, None, 1.0),
    Triple("applicant_42", "SUBMITTED", str(DOC_ID | DOC_INCOME),                 "intake_2026", 0, None, None, 1.0),
    Triple("applicant_99", "SUBMITTED", str(DOC_ID | DOC_INCOME | DOC_RESIDENCY), "intake_2026", 0, None, None, 1.0),
    Triple("clinic_north", "OPEN_DAYS", str(0b0011111), "opening_hours_2026", 0, None, None, 1.0),  # Mon-Fri
    # A packed staff card: low nibble = department code, high nibble = clearance level.
    Triple("card_7", "PACKED", str((3 << 4) | 5), "credential_format_2026", 0, None, None, 1.0),  # level 3, dept 5
]

# --- RULES -------------------------------------------------------------------
# [1] AND — membership: does the role hold the capability the action requires?
MAY_PERFORM = [("FETCH", "@role|PERMISSIONS"), ("FETCH", "@action|REQUIRES"),
               ("AND", None), ("PUSH", 0), ("NE", None), ("RET", None)]
# [2] OR — union: combine two roles, then test a capability.
MERGED_MAY = [("FETCH", "@r1|PERMISSIONS"), ("FETCH", "@r2|PERMISSIONS"), ("OR", None),
              ("FETCH", "@action|REQUIRES"), ("AND", None), ("PUSH", 0), ("NE", None), ("RET", None)]
# [3] NOT + AND — suspend one capability, keep the rest.
SUSPEND = [("FETCH", "@role|PERMISSIONS"), ("FETCH", "@action|REQUIRES"),
           ("NOT", None), ("AND", None), ("RET", None)]
# [4] XOR + popcount — how many capabilities DIFFER between two roles?
N_DIFFERENCES = ([("FETCH", "@r1|PERMISSIONS"), ("FETCH", "@r2|PERMISSIONS"),
                  ("XOR", None), ("STORE", "n")] + popcount_from(4))
# [5] AND + EQ — superset: are ALL required documents present?
ELIGIBLE = [("FETCH", "@benefit|REQUIRED_DOCS"), ("DUP", None),
            ("FETCH", "@applicant|SUBMITTED"), ("AND", None), ("EQ", None), ("RET", None)]
# [6] SHL + AND — is bit `day` set in the open-days mask?
OPEN_ON = [("FETCH", "@clinic|OPEN_DAYS"), ("PUSH", 1), ("LOAD", "day"), ("SHL", None),
           ("AND", None), ("PUSH", 0), ("NE", None), ("RET", None)]
# [7] SHR + AND — unpack the high-nibble clearance level from a packed card.
CLEARANCE = [("FETCH", "@card|PACKED"), ("PUSH", 4), ("SHR", None),
             ("PUSH", 15), ("AND", None), ("RET", None)]


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    kb = KB(triples=FACTS
            + prog("may_perform", MAY_PERFORM) + prog("merged_may", MERGED_MAY)
            + prog("suspend", SUSPEND) + prog("n_diff", N_DIFFERENCES)
            + prog("eligible", ELIGIBLE) + prog("open_on", OPEN_ON)
            + prog("clearance", CLEARANCE),
            alias_map={}, n_articles=0)

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #12 — bit masks / flag-sets as cited knowledge")
    print(LINE)

    # [1] AND — set membership
    print("\n[1] AND  — does a role HAVE the capability an action requires?")
    r = run(kb, "may_perform", {"role": "role_doctor", "action": "act_prescribe"})
    print(f"    doctor may prescribe? {bool(r.value)}   cited: {r.reads}")
    check("doctor may prescribe (has the bit)", r.value == 1.0)
    check("nurse may not prescribe (lacks the bit)",
          run(kb, "may_perform", {"role": "role_nurse", "action": "act_prescribe"}).value == 0.0)

    # [2] OR — set union (a user holding two roles)
    print("\n[2] OR   — combine two roles' capabilities, then test (set union)")
    check("nurse+admin together still cannot prescribe",
          run(kb, "merged_may", {"r1": "role_nurse", "r2": "role_admin", "action": "act_prescribe"}).value == 0.0)
    check("nurse+doctor together can prescribe",
          run(kb, "merged_may", {"r1": "role_nurse", "r2": "role_doctor", "action": "act_prescribe"}).value == 1.0)

    # [3] NOT + AND — clear one bit, keep the rest
    print("\n[3] NOT  — suspend ONE capability, leave the others intact")
    suspended = run(kb, "suspend", {"role": "role_doctor", "action": "act_prescribe"}).value
    print(f"    doctor with prescribing suspended -> permission mask {int(suspended)}")
    check("suspending prescribe leaves VIEW|EDIT (7 AND NOT 4 == 3)", suspended == 3.0)

    # [4] XOR + popcount — symmetric difference / change detection
    print("\n[4] XOR  — how many capabilities DIFFER between two roles? (a clean diff)")
    diff = run(kb, "n_diff", {"r1": "role_nurse", "r2": "role_doctor"}).value
    print(f"    nurse vs doctor differ in {int(diff)} capability(ies)")
    check("nurse vs doctor differ by exactly 1 (PRESCRIBE)", diff == 1.0)
    check("a role differs from itself by 0", run(kb, "n_diff", {"r1": "role_doctor", "r2": "role_doctor"}).value == 0.0)

    # [5] AND + EQ — superset test (all required present)
    print("\n[5] AND+EQ — has the applicant submitted EVERY required document?")
    check("applicant_42 (missing residency) is not eligible",
          run(kb, "eligible", {"applicant": "applicant_42", "benefit": "benefit_housing"}).value == 0.0)
    check("applicant_99 (all docs) is eligible",
          run(kb, "eligible", {"applicant": "applicant_99", "benefit": "benefit_housing"}).value == 1.0)

    # [6] SHL + AND — test one bit built on the fly
    print("\n[6] SHL  — is the clinic open on weekday d?  (1 SHL d builds the day's bit)")
    check("clinic open on Wednesday (day 2)", run(kb, "open_on", {"clinic": "clinic_north", "day": 2}).value == 1.0)
    check("clinic closed on Sunday (day 6)", run(kb, "open_on", {"clinic": "clinic_north", "day": 6}).value == 0.0)

    # [7] SHR + AND — unpack a field packed into a larger number
    print("\n[7] SHR  — unpack the clearance level packed into the high nibble of a card")
    level = run(kb, "clearance", {"card": "card_7"}).value
    print(f"    card_7 packed value decodes to clearance level {int(level)}")
    check("clearance level unpacks to 3 ((53 SHR 4) AND 0xF)", level == 3.0)

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "A bit mask stores a whole set in one number; AND/OR/XOR/NOT/SHL/SHR then do\n"
        "membership, union, difference, complement, mask-building, and field-unpacking\n"
        "as single exact operations. It's a compact, fast, broadly-applicable modelling\n"
        "technique — and as SKEAR microtheories it stays deterministic, cited to the\n"
        "source policy, and auditable. Useful well beyond any one application.")
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
