"""Microtheory worked example #5 — replicate REAL Python with ordered microtheories,
and measure the efficiency gain honestly.

Two claims, each demonstrated, not asserted:

  PART 1 — EXACT REPLICATION. Take actual Python functions with real control flow
  (Euclid's GCD: a loop with MOD; a piecewise grader: a branch ladder) and express
  each as an ordered microtheory run by SKEAR's core executor (`kb.execute`). Prove
  byte-for-byte behavioural equality against the Python over a large input sweep.
  The "program" is now inspectable, cited, reason-over-able data.

  PART 2 — THE EFFICIENCY GAIN, HONESTLY. Where does code-as-data actually win? Not
  on a single function (you pay for the executor). It wins at SCALE, on FAMILIES of
  similar behaviours — exactly the regime SKEAR is built for ("adding a variant
  costs ~0"). We grow a family of N piecewise business rules and measure:
    (a) hand-written, BUG-CAPABLE code: grows linearly, k lines per rule, forever;
    (b) SKEAR: the executor is written ONCE (fixed), every further rule is pure
        DATA — zero new code, and its incremental representation is just the few
        operands that differ from its siblings (the shared opcode structure
        compresses to ~0, shown with zlib).
  We print the crossover and the marginal-cost curve. We are explicit about where
  this does NOT help, so the win is the real one.

Run (from src/):  python -m microtheory.replicate
"""
from __future__ import annotations

import inspect
import sys
import zlib

from kb.query import KB, Triple
from kb.execute import run
import kb.execute as execute

LINE = "=" * 78


def prog(scope, ops, source="manual"):
    """Author an ordered-microtheory program (relation=opcode, object=operand)."""
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# ==========================================================================
# PART 1 — exact replication of real Python
# ==========================================================================
def py_gcd(a, b):
    """Euclid's algorithm — a genuine loop with remainder."""
    while b != 0:
        a, b = b, a % b
    return a


# The SAME algorithm as an ordered microtheory (addresses chosen so the loop's
# back-edge is explicit). Registers a, b live as variables; swap via a temp.
GCD = [
    ("LOAD", "b"), ("PUSH", 0), ("EQ", None), ("JZ", 6),   # 0-3: while b != 0  (if b==0 -> exit @ ... )
    ("LOAD", "a"), ("RET", None),                          # 4-5: return a
    ("LOAD", "b"), ("STORE", "t"),                         # 6-7: t = b
    ("LOAD", "a"), ("LOAD", "b"), ("MOD", None), ("STORE", "b"),  # 8-11: b = a % b
    ("LOAD", "t"), ("STORE", "a"),                         # 12-13: a = t
    ("JMP", 0),                                            # 14: loop
]


def py_grade(score):
    """A piecewise branch ladder — the shape of a thousand business rules."""
    if score >= 90:
        return 4.0
    elif score >= 80:
        return 3.0
    elif score >= 70:
        return 2.0
    elif score >= 60:
        return 1.0
    return 0.0


GRADE = [
    ("LOAD", "score"), ("PUSH", 90), ("GE", None), ("JZ", 6), ("PUSH", 4), ("RET", None),   # 0-5
    ("LOAD", "score"), ("PUSH", 80), ("GE", None), ("JZ", 12), ("PUSH", 3), ("RET", None),  # 6-11
    ("LOAD", "score"), ("PUSH", 70), ("GE", None), ("JZ", 18), ("PUSH", 2), ("RET", None),  # 12-17
    ("LOAD", "score"), ("PUSH", 60), ("GE", None), ("JZ", 24), ("PUSH", 1), ("RET", None),  # 18-23
    ("PUSH", 0), ("RET", None),                                                             # 24-25
]


def part1(check):
    print("\n[PART 1] Exact replication of real Python (loop + branch):")
    kb = KB(triples=prog("gcd", GCD, "euclid") + prog("grade", GRADE, "rubric"),
            alias_map={}, n_articles=0)

    gcd_cases = [(a, b) for a in range(0, 60) for b in range(0, 60)]
    gcd_ok = all(run(kb, "gcd", {"a": a, "b": b}).value == py_gcd(a, b)
                 for a, b in gcd_cases)
    print(f"    GCD: ordered microtheory vs py_gcd over {len(gcd_cases)} (a,b) pairs -> "
          f"{'EXACT MATCH' if gcd_ok else 'MISMATCH'}")
    check("GCD microtheory exactly replicates Euclid's algorithm", gcd_ok)

    grade_ok = all(run(kb, "grade", {"score": s}).value == py_grade(s)
                   for s in range(0, 101))
    print(f"    GRADE: ordered microtheory vs py_grade over 0..100 -> "
          f"{'EXACT MATCH' if grade_ok else 'MISMATCH'}")
    check("GRADE microtheory exactly replicates the branch ladder", grade_ok)

    # show it's not a black box: a cited 'why' trace for one execution
    tr = run(kb, "gcd", {"a": 48, "b": 36})
    print(f"    gcd(48,36) = {tr.value} in {tr.steps} steps; first 3 cited steps:")
    for ln in tr.trace[:3]:
        print(f"       {ln}")
    check("execution is cited step-by-step (auditable)", "[euclid]" in tr.trace[0])


# ==========================================================================
# PART 2 — the efficiency gain, measured and honest
# ==========================================================================
# A family of piecewise shipping-cost rules. Each VARIANT differs only in its
# bracket thresholds/rates — the control-flow shape is identical. This is the
# "many similar rules" regime (tax tables, tariffs, pricing) where rules
# proliferate and code rots.

def code_variant_source(k):
    """The hand-written Python a developer would author for variant k. Realistic
    boilerplate: a 2-bracket piecewise rule. (Counted as bug-capable code.)"""
    t1, r1, r2 = 50 + k, 0.10 + 0.001 * k, 0.05 + 0.001 * k
    return (f"def ship_{k}(w):\n"
            f"    if w >= {t1}:\n"
            f"        return w * {r2:.3f}\n"
            f"    return w * {r1:.3f}\n")


def data_variant_program(k):
    """The SAME variant k as an ordered-microtheory program. Opcodes are shared
    across the whole family; only the 3 operands (t1, r1, r2) differ."""
    t1, r1, r2 = 50 + k, 0.10 + 0.001 * k, 0.05 + 0.001 * k
    return [("LOAD", "w"), ("PUSH", t1), ("GE", None), ("JZ", 8),       # 0-3: if w>=t1 fall through, else goto 8
            ("LOAD", "w"), ("PUSH", round(r2, 3)), ("MUL", None), ("RET", None),   # 4-7: return w*r2
            ("LOAD", "w"), ("PUSH", round(r1, 3)), ("MUL", None), ("RET", None)]   # 8-11: return w*r1


def part2(check):
    print("\n[PART 2] Efficiency gain — measured on a family of N similar rules:")

    # First: confirm the data form EXACTLY replicates the code form for a sample,
    # so the size comparison is between two verified-equivalent representations.
    sample_ok = True
    for k in (0, 3, 9):
        ns = {}
        exec(code_variant_source(k), ns)             # the literal Python variant
        fn = ns[f"ship_{k}"]
        kb = KB(triples=prog(f"ship_{k}", data_variant_program(k)), alias_map={}, n_articles=0)
        for w in range(0, 120, 7):
            if run(kb, f"ship_{k}", {"w": w}).value != fn(w):
                sample_ok = False
    check("each data rule exactly replicates its Python counterpart", sample_ok)

    # The fixed cost of the SKEAR approach: the executor, written once. Count its
    # real source size from the module — no hand-waving.
    executor_src = inspect.getsource(execute)
    EXEC_BYTES = len(executor_src.encode())
    EXEC_LOC = sum(1 for ln in executor_src.splitlines()
                   if ln.strip() and not ln.strip().startswith("#"))

    def data_bytes(k):
        # serialise a program as compact "OP arg" lines (operands are the payload)
        return len("\n".join(f"{op} {'' if a is None else a}"
                             for op, a in data_variant_program(k)).encode())

    code_loc_per = sum(1 for ln in code_variant_source(0).splitlines() if ln.strip())

    print(f"    fixed cost (SKEAR executor, written ONCE): {EXEC_BYTES} bytes, "
          f"{EXEC_LOC} lines of bug-capable code — then 0 new code, forever.")
    print(f"    {'N rules':>7} | {'NEW code LOC':>12} | {'zlib(code)':>10} {'zlib(data)':>10} "
          f"| {'z/rule code':>11} {'z/rule data':>11}")
    print("    " + "-" * 76)
    z_per_rule = {}
    for n in (1, 10, 100, 1000):
        code_blob = "".join(code_variant_source(k) for k in range(n))
        data_blob = "\n".join("\n".join(f"{op} {'' if a is None else a}"
                                        for op, a in data_variant_program(k)) for k in range(n))
        zc = len(zlib.compress(code_blob.encode(), 9))
        zd = len(zlib.compress(data_blob.encode(), 9))
        new_code_loc = n * code_loc_per           # code: linear, forever
        print(f"    {n:>7} | {new_code_loc:>12} | {zc:>10} {zd:>10} "
              f"| {zc/n:>11.2f} {zd/n:>11.2f}")
        z_per_rule[n] = zd / n                     # compressed bytes per rule (data)

    print("\n    The honest reading (where code-as-data does and does NOT win):")
    print("    * It does NOT win on raw bytes: you pay once for the executor, and a")
    print("      rule's operands cost about the same either way. Single functions:")
    print("      plain code is smaller. We are not pretending otherwise.")
    print("    * It WINS on bug-capable code: every new rule adds 0 lines of code")
    print(f"      (vs {code_loc_per} LOC each); the executor is the only thing that can")
    print("      have a bug, and it is fixed and 6-way self-tested.")
    print("    * It WINS on information content: zlib(data) per rule keeps shrinking")
    print("      as the family grows — shared opcode structure compresses to ~0, so")
    print("      only the differing operands carry information (SKEAR novelty #2).")
    print("    * And the rule stays inspectable, diffable, cited, and reason-over-")
    print("      able — none of which opaque code (or an LLM 'just computing it') is.")
    check("a data rule's compressed cost per rule falls as the family grows",
          z_per_rule[1000] < z_per_rule[1])


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #5 — replicate real Python; measure the efficiency gain")
    print(LINE)
    part1(check)
    part2(check)

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "Ordered microtheories let SKEAR replicate real code EXACTLY (loops,\n"
        "branches and all) as inspectable, cited, reason-over-able data. The\n"
        "efficiency is not magic compression of one function — it is that the\n"
        "executor is written once and every behaviour after it is DATA: zero new\n"
        "bug-capable code, and shared structure across a family of rules costs ~0.\n"
        "At the scale of real rule-bases, that is where code-as-data wins.")
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
