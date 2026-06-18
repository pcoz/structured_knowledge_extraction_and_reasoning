"""Microtheory worked example #8 — a POLYNOMIAL speedup from the integrated substrate.

The earlier examples showed code-as-data with a constant-factor interpreter cost.
This one shows where the integrated data+algorithm approach is *asymptotically*
faster than the natural Python solution — not a constant factor, a better
complexity class.

The lever: storing facts as a knowledge base builds adjacency / by-relation
INDEXES at construction time (`KB.__post_init__`). An algorithm that runs against
the KB therefore does indexed lookups, whereas the natural Python baseline — data
held in a flat list of tuples (as you'd have it straight from a CSV) with a
straightforward loop — must SCAN. On a multi-hop relational JOIN that is the
classic gap:

    grandparent(x, z)  :-  parent(x, y), parent(y, z)      (a 2-hop self-join)

  * naive Python over a flat edge list: for each edge (x, y), scan every edge for
    one of the form (y, z).  -> O(M^2)
  * the KB: for each middle node y, take its parents (in-index) x its children
    (out-index) directly.  -> O(M) for bounded degree

We prove the gap with deterministic OPERATION COUNTS (so it doesn't depend on the
machine or timer), confirm both methods return the identical set, and print wall-
clock times for flavour.

Honest note: a Python developer can match the KB by building a dict index by hand
— but that is precisely adopting this paradigm's representation, maintained
separately from the data and without its provenance. Here the index is intrinsic
to representing data as a knowledge base, the join stays a query over cited facts,
and each derived pair can carry the two source facts it came from.

Run (from src/):  python -m microtheory.complexity
"""
from __future__ import annotations

import sys
import time

from kb.query import KB, Triple

LINE = "=" * 78


def build(n: int, branching: int = 2):
    """A `branching`-ary tree of `n` nodes as PARENT facts. Returns (triples for
    the KB, flat edge list for the Python baseline) — the SAME data, two shapes."""
    triples, edges = [], []
    for i in range(1, n):
        parent = f"n{(i - 1) // branching}"
        child = f"n{i}"
        triples.append(Triple(parent, "PARENT", child, "genealogy", i))
        edges.append((parent, child))
    return triples, edges


def naive_python(edges):
    """The natural standalone-Python solution: data is a flat list, scan it.
    Returns (result_set, op_count) where op_count is inner-loop comparisons."""
    result = set()
    ops = 0
    for (x, y) in edges:
        for (y2, z) in edges:        # scan for an edge starting where this one ends
            ops += 1
            if y2 == y:
                result.add((x, z))
    return result, ops


def indexed_kb(kb):
    """The integrated solution: run the join against the KB's intrinsic indexes.
    Returns (result_set, op_count) where op_count is index lookups + emissions."""
    result = set()
    ops = 0
    for mid in kb.entities():
        parents = kb.in_facts(mid, "PARENT")     # O(1) index lookup: x with x PARENT mid
        children = kb.out_facts(mid, "PARENT")   # O(1) index lookup: z with mid PARENT z
        ops += 2
        for p in parents:
            for c in children:
                ops += 1
                result.add((p.subject, c.object))
    return result, ops


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #8 — a polynomial speedup from the integrated index")
    print(LINE)
    print("\n  grandparent(x,z) :- parent(x,y), parent(y,z)   (a 2-hop relational join)\n")
    print(f"  {'nodes N':>8} {'edges M':>8} | {'naive ops':>12} {'indexed ops':>12} "
          f"{'ops ratio':>10} | {'naive ms':>9} {'kb ms':>8}")
    print("  " + "-" * 78)

    ratios = []
    for n in (64, 128, 256, 512, 1024):
        triples, edges = build(n)
        kb = KB(triples=triples, alias_map={}, n_articles=0)

        t = time.perf_counter(); r_py, ops_py = naive_python(edges); ms_py = (time.perf_counter() - t) * 1000
        t = time.perf_counter(); r_kb, ops_kb = indexed_kb(kb); ms_kb = (time.perf_counter() - t) * 1000

        ratio = ops_py / ops_kb
        ratios.append(ratio)
        print(f"  {n:>8} {len(edges):>8} | {ops_py:>12,} {ops_kb:>12,} {ratio:>10.1f} "
              f"| {ms_py:>9.2f} {ms_kb:>8.2f}")
        check(f"N={n}: both methods return the identical grandparent set", r_py == r_kb)

    print("\n  Reading the table:")
    print("  * naive ops grow ~M^2 (each edge scans every edge); indexed ops grow ~M.")
    print("  * so the ops RATIO roughly DOUBLES each time N doubles — a polynomial,")
    print("    not constant, separation: O(M^2) vs O(M).")
    # The asymptotic claim, asserted deterministically: each doubling of N at least
    # ~1.7x's the advantage (would be ~constant if it were only a constant factor).
    growth = ratios[-1] / ratios[0]
    print(f"  * advantage at N=1024 is {growth:.1f}x what it was at N=64 "
          f"(N grew 16x) -> the gap scales with the data.")
    check("the advantage grows with N (super-constant -> polynomial speedup)",
          all(ratios[i + 1] > ratios[i] * 1.7 for i in range(len(ratios) - 1)))

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "Because data stored as a knowledge base is indexed by construction, an\n"
        "algorithm run against it does indexed lookups where the natural flat-list\n"
        "Python does linear scans. On a multi-hop join that is an O(M^2) -> O(M)\n"
        "improvement — a polynomial speedup — and the result stays a query over\n"
        "cited facts rather than an opaque loop over an array.")
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
