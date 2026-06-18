"""Microtheory worked example #7 — NO DISCONNECT: the algorithm lives WITH the data.

In a conventional stack the data
sits in a database and the algorithm sits in application code; bridging them needs
an ORM / serialization / an API, the two drift out of sync, and the provenance of
a computed number is severed from the facts it came from. Other languages struggle
with exactly this seam.

In SKEAR there is no seam. A program is an ORDERED microtheory; a fact is a plain
triple; BOTH are triples in the SAME knowledge base. So a program can read the
KB's own facts directly (the `FETCH` opcode), compute over them, and its result —
with one unbroken provenance trail spanning the program steps AND the source
facts — can be written straight back as a new fact that queries and the reasoner
immediately see. One substrate; three faculties (query / reason / execute) over it.

This file builds a tiny pricing KB that holds DATA and ALGORITHMS together, and
shows:
  1. A program computing an invoice total by FETCHing the KB's own price/qty/tax
     facts — provenance spans program + data.
  2. NO DISCONNECT: edit a *fact* (a quantity), rerun the *same* program, get the
     updated answer — no code change, no data export/import, nothing to keep in sync.
  3. THE LOOP CLOSES: the computed total is asserted back as a fact and is then
     queryable like any other — and a second program FETCHes that derived fact.

Run (from src/):  python -m microtheory.unified
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.execute import run

LINE = "=" * 78


def prog(scope, ops, source="pricing_rules"):
    """Author a program as an ordered microtheory (relation=opcode, object=operand)."""
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# --------------------------------------------------------------------------
# The ALGORITHMS — ordered microtheories. They read the KB's facts via FETCH,
# so they carry NO copy of the data: change the facts and these are unchanged.
# --------------------------------------------------------------------------
# with_tax(subtotal): subtotal on the stack -> subtotal * (1 + store.TAX_RATE)
WITH_TAX = [
    ("STORE", "s"),                       # 0 s = subtotal (off the stack)
    ("LOAD", "s"),                        # 1 push s
    ("PUSH", 1),                          # 2 push 1
    ("FETCH", "store|TAX_RATE"),          # 3 read the tax rate FROM THE KB
    ("ADD", None),                        # 4 1 + tax
    ("MUL", None),                        # 5 s * (1 + tax)
    ("RET", None),                        # 6
]
# invoice_total(): reads every price/qty/tax/shipping fact from the KB and
# composes with_tax. The whole business rule is data, operating on data.
INVOICE_TOTAL = [
    ("FETCH", "widget|PRICE"), ("FETCH", "widget|QTY"), ("MUL", None),   # 0-2 widget line
    ("FETCH", "gizmo|PRICE"), ("FETCH", "gizmo|QTY"), ("MUL", None),     # 3-5 gizmo line
    ("ADD", None),                        # 6 subtotal
    ("CALL", "with_tax"),                 # 7 apply tax (itself FETCHes the rate)
    ("FETCH", "store|SHIPPING"),          # 8 read shipping FROM THE KB
    ("ADD", None),                        # 9 + shipping
    ("RET", None),                        # 10
]


def build_kb(gizmo_qty: int) -> KB:
    """ONE knowledge base holding DATA (plain facts) and ALGORITHMS (ordered
    microtheories) side by side, in the same triple shape, the same store."""
    data = [
        # --- DATA: ordinary facts (global scope, no seq) ---
        Triple("widget", "PRICE", "25", "catalogue_2026", 0, None, None, 1.0),
        Triple("widget", "QTY", "4", "order_4471", 0, None, None, 1.0),
        Triple("gizmo", "PRICE", "9", "catalogue_2026", 0, None, None, 1.0),
        Triple("gizmo", "QTY", str(gizmo_qty), "order_4471", 0, None, None, 1.0),
        Triple("store", "TAX_RATE", "0.10", "tax_policy", 0, None, None, 1.0),
        Triple("store", "SHIPPING", "5", "shipping_policy", 0, None, None, 1.0),
    ]
    # --- ALGORITHMS: programs, in the SAME kb ---
    programs = prog("with_tax", WITH_TAX) + prog("invoice_total", INVOICE_TOTAL)
    return KB(triples=data + programs, alias_map={}, n_articles=0)


def py_invoice(gizmo_qty):
    """The same rule in Python, as an honesty anchor."""
    subtotal = 25 * 4 + 9 * gizmo_qty
    return subtotal * (1 + 0.10) + 5


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #7 — NO DISCONNECT between data and algorithm")
    print(LINE)

    # --- 1. compute over the KB's OWN facts; provenance spans program + data ---
    kb = build_kb(gizmo_qty=10)
    r = run(kb, "invoice_total", {})
    print(f"\n[1] invoice_total() over the facts in the SAME KB = {r.value}")
    print("    the facts the program read (cited, straight from the KB):")
    for cite in r.reads:
        print(f"       {cite}")
    check("program computes the invoice from the KB's own facts", r.value == py_invoice(10))
    check("provenance spans the DATA (every FETCHed fact is cited)", len(r.reads) == 6)
    check("provenance also spans the ALGORITHM (every step traced)",
          len(r.trace) > 0 and all("@" in ln for ln in r.trace))

    # --- 2. NO DISCONNECT: edit a FACT, rerun the SAME program ----------------
    kb2 = build_kb(gizmo_qty=20)          # the ONLY change: a data fact (qty 10 -> 20)
    r2 = run(kb2, "invoice_total", {})
    print(f"\n[2] edit ONE fact (gizmo QTY 10 -> 20), rerun the SAME program:")
    print(f"    invoice_total() = {r2.value}  (was {r.value}) — no code/program change")
    check("changing a fact changes the result; the algorithm was untouched",
          r2.value == py_invoice(20) and r2.value != r.value)
    print("    (a conventional stack would need a DB write + app redeploy + an ORM")
    print("     to bridge the two, and the number's provenance would be lost.)")

    # --- 3. THE LOOP CLOSES: write the result back as a queryable fact --------
    total_fact = Triple("invoice_4471", "TOTAL", str(r.value),
                        "computed:invoice_total", -1)   # a normal fact, made by a program
    kb3 = KB(triples=kb.triples + [total_fact], alias_map={}, n_articles=0)
    queried = kb3.out_facts("invoice_4471", "TOTAL")
    print(f"\n[3] assert the computed total back into the KB; query it like any fact:")
    print(f"    kb.out_facts('invoice_4471','TOTAL') -> "
          f"{[t.object for t in queried]}  (source: {queried[0].source_article})")
    check("a program's output re-enters the KB as a fact, queryable immediately",
          len(queried) == 1 and float(queried[0].object) == r.value)
    # ...and a downstream program can FETCH that derived fact — execute over what
    # execute produced, all in one store.
    apply_discount = prog("after_discount",
                          [("FETCH", "invoice_4471|TOTAL"), ("PUSH", 0.9), ("MUL", None), ("RET", None)])
    kb4 = KB(triples=kb3.triples + apply_discount, alias_map={}, n_articles=0)
    rd = run(kb4, "after_discount", {})
    print(f"    a second program FETCHes that derived fact: 10% off -> {rd.value}")
    check("a program computes over a fact that another program produced",
          abs(rd.value - r.value * 0.9) < 1e-9)

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "Data and algorithm are the same kind of thing — triples — in the same\n"
        "knowledge base, under one provenance model, served by the same three\n"
        "faculties (query / reason / execute). The business rule reads live facts,\n"
        "its result becomes a fact, and the next rule reads that. No ORM, no export,\n"
        "no drift, no severed provenance.")
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
