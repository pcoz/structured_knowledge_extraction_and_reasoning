"""Microtheory worked example #6 — recognisable algorithms with the expanded opcodes.

Examples #3-#5 established that an ordered microtheory is a procedure, a program,
and an exact replica of real code. This one exercises the expanded instruction
set — `CALL` (subroutines / composition / recursion), `DUP`/`SWAP`/`POP`, and
`EMIT` (sequence output) — on familiar algorithms, each proven byte-for-byte
equal to its Python counterpart:

  A. MUTUAL RECURSION   — is_even / is_odd, two microtheories CALLing each other.
  B. RECURSION          — Fibonacci as a self-CALLing microtheory.
  C. COMPOSITION        — a "standard library": lcm CALLs gcd (one mt uses another).
  D. EMIT               — FizzBuzz: emit a code per i, the code computed by a
                          CALLed sub-procedure.
  E. COMPOSITION + EMIT — primes up to N: a CALLed is_prime sieve, EMITting each.

The point: real algorithms — recursion, mutual recursion, library composition,
sequence generation — expressed entirely as inspectable, cited, reason-over-able
SKEAR data, run by ONE ~200-line executor. The logic is knowledge, not code.

Run (from src/):  python -m microtheory.showcase
"""
from __future__ import annotations

import sys

from kb.query import KB, Triple
from kb.execute import run

LINE = "=" * 78


def prog(scope, ops, source="library"):
    """Author a program as an ordered microtheory: each op is a STEP-carrying
    triple (relation=opcode, object=operand, seq=address)."""
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


def call_value(base_triples, scope, args):
    """Run `scope` with `args` pushed on the stack (the calling convention used by
    these stack-based subroutines), returning the executor's ExecResult.

    We synthesise a tiny driver microtheory that PUSHes each argument then CALLs
    the target — exactly how one microtheory invokes another — so the same
    arg-on-stack convention is exercised end to end."""
    driver = prog("_driver", [("PUSH", a) for a in args] + [("CALL", scope), ("RET", None)], "driver")
    kb = KB(triples=list(base_triples) + driver, alias_map={}, n_articles=0)
    return run(kb, "_driver", {})


# ==========================================================================
# A. MUTUAL RECURSION — is_even / is_odd call EACH OTHER
# ==========================================================================
# Python:
#   def is_even(n): return 1 if n == 0 else is_odd(n - 1)
#   def is_odd(n):  return 0 if n == 0 else is_even(n - 1)
IS_EVEN = [
    ("STORE", "n"),                                   # 0  n = arg (off the stack)
    ("LOAD", "n"), ("PUSH", 0), ("EQ", None), ("JZ", 7),   # 1-4 if n != 0 goto 7
    ("PUSH", 1), ("RET", None),                       # 5-6 n == 0 -> return 1 (even)
    ("LOAD", "n"), ("PUSH", 1), ("SUB", None),        # 7-9 push n-1
    ("CALL", "is_odd"), ("RET", None),                # 10-11 return is_odd(n-1)
]
IS_ODD = [
    ("STORE", "n"),                                   # 0  n = arg
    ("LOAD", "n"), ("PUSH", 0), ("EQ", None), ("JZ", 7),   # 1-4 if n != 0 goto 7
    ("PUSH", 0), ("RET", None),                       # 5-6 n == 0 -> return 0 (not odd)
    ("LOAD", "n"), ("PUSH", 1), ("SUB", None),        # 7-9 push n-1
    ("CALL", "is_even"), ("RET", None),               # 10-11 return is_even(n-1)
]


# ==========================================================================
# B. RECURSION — Fibonacci
# ==========================================================================
# Python: def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)
FIB = [
    ("STORE", "n"),                                   # 0  n = arg
    ("LOAD", "n"), ("PUSH", 2), ("LT", None), ("JZ", 7),   # 1-4 if n >= 2 goto 7
    ("LOAD", "n"), ("RET", None),                     # 5-6 n < 2 -> return n
    ("LOAD", "n"), ("PUSH", 1), ("SUB", None), ("CALL", "fib"),   # 7-10  fib(n-1)
    ("LOAD", "n"), ("PUSH", 2), ("SUB", None), ("CALL", "fib"),   # 11-14 fib(n-2)
    ("ADD", None), ("RET", None),                     # 15-16 return their sum
]


# ==========================================================================
# C. COMPOSITION — a standard library: lcm CALLs gcd
# ==========================================================================
# gcd(a, b) by Euclid (args pushed a then b, so top of stack is b).
GCD = [
    ("STORE", "b"), ("STORE", "a"),                   # 0-1 b = top, a = next
    ("LOAD", "b"), ("PUSH", 0), ("EQ", None), ("JZ", 8),   # 2-5 while b != 0 (b==0 -> done)
    ("LOAD", "a"), ("RET", None),                     # 6-7 return a
    ("LOAD", "b"), ("STORE", "t"),                    # 8-9 t = b
    ("LOAD", "a"), ("LOAD", "b"), ("MOD", None), ("STORE", "b"),   # 10-13 b = a % b
    ("LOAD", "t"), ("STORE", "a"),                    # 14-15 a = t
    ("JMP", 2),                                        # 16 loop
]
# lcm(a, b) = a * b / gcd(a, b)  — composes gcd.
LCM = [
    ("STORE", "b"), ("STORE", "a"),                   # 0-1
    ("LOAD", "a"), ("LOAD", "b"), ("MUL", None),      # 2-4 a*b
    ("LOAD", "a"), ("LOAD", "b"), ("CALL", "gcd"),    # 5-7 push gcd(a,b)
    ("DIV", None), ("RET", None),                     # 8-9 (a*b)/gcd
]


# ==========================================================================
# D. EMIT — FizzBuzz (code per i, computed by a CALLed sub-procedure)
#    code: 3=fizzbuzz, 1=fizz, 2=buzz, 0=plain number
# ==========================================================================
FBCODE = [
    ("STORE", "i"),                                                   # 0
    ("LOAD", "i"), ("PUSH", 15), ("MOD", None), ("PUSH", 0), ("EQ", None), ("JZ", 9),  # 1-6 i%15==0?
    ("PUSH", 3), ("RET", None),                                       # 7-8 fizzbuzz
    ("LOAD", "i"), ("PUSH", 3), ("MOD", None), ("PUSH", 0), ("EQ", None), ("JZ", 17),  # 9-14 i%3==0?
    ("PUSH", 1), ("RET", None),                                       # 15-16 fizz
    ("LOAD", "i"), ("PUSH", 5), ("MOD", None), ("PUSH", 0), ("EQ", None), ("JZ", 25),  # 17-22 i%5==0?
    ("PUSH", 2), ("RET", None),                                       # 23-24 buzz
    ("PUSH", 0), ("RET", None),                                       # 25-26 plain number
]
FIZZBUZZ = [
    ("STORE", "n"),                                                   # 0  n = arg (off stack)
    ("PUSH", 1), ("STORE", "i"),                                      # 1-2 i=1
    ("LOAD", "i"), ("LOAD", "n"), ("LE", None), ("JZ", 16),           # 3-6 while i<=n
    ("LOAD", "i"), ("CALL", "fbcode"), ("EMIT", None), ("POP", None), # 7-10 emit fbcode(i)
    ("LOAD", "i"), ("PUSH", 1), ("ADD", None), ("STORE", "i"),        # 11-14 i+=1
    ("JMP", 3),                                                       # 15 loop
    ("PUSH", 0), ("RET", None),                                       # 16-17 done
]


# ==========================================================================
# E. COMPOSITION + EMIT — primes up to N (CALLed is_prime, EMIT each prime)
# ==========================================================================
IS_PRIME = [
    ("STORE", "n"),                                   # 0
    ("LOAD", "n"), ("PUSH", 2), ("LT", None), ("JZ", 7),   # 1-4 if n>=2 goto 7
    ("PUSH", 0), ("RET", None),                       # 5-6 n<2 -> not prime
    ("PUSH", 2), ("STORE", "d"),                      # 7-8 d=2
    ("LOAD", "d"), ("LOAD", "n"), ("LT", None), ("JZ", 26),    # 9-12 while d<n else prime
    ("LOAD", "n"), ("LOAD", "d"), ("MOD", None), ("PUSH", 0), ("EQ", None), ("JZ", 21),  # 13-18 n%d==0?
    ("PUSH", 0), ("RET", None),                       # 19-20 divisor found -> not prime
    ("LOAD", "d"), ("PUSH", 1), ("ADD", None), ("STORE", "d"),     # 21-24 d+=1
    ("JMP", 9),                                        # 25 loop
    ("PUSH", 1), ("RET", None),                       # 26-27 no divisor -> prime
]
PRIMES = [
    ("STORE", "n"),                                   # 0  n = arg (off stack)
    ("PUSH", 2), ("STORE", "i"),                      # 1-2 i=2
    ("LOAD", "i"), ("LOAD", "n"), ("LE", None), ("JZ", 18),    # 3-6 while i<=n
    ("LOAD", "i"), ("CALL", "is_prime"), ("JZ", 13),  # 7-9 if !is_prime(i) skip
    ("LOAD", "i"), ("EMIT", None), ("POP", None),     # 10-12 emit i
    ("LOAD", "i"), ("PUSH", 1), ("ADD", None), ("STORE", "i"),     # 13-16 i+=1
    ("JMP", 3),                                        # 17 loop
    ("PUSH", 0), ("RET", None),                       # 18-19 done
]


# --------------------------------------------------------------------------
# Python references — the executor's outputs are checked against these.
# --------------------------------------------------------------------------
def py_fib(n):
    return n if n < 2 else py_fib(n - 1) + py_fib(n - 2)


def py_gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def py_fizzbuzz_code(i):
    return 3 if i % 15 == 0 else 1 if i % 3 == 0 else 2 if i % 5 == 0 else 0


def py_primes(n):
    return [x for x in range(2, n + 1)
            if x >= 2 and all(x % d for d in range(2, x))]


def main() -> None:
    failures = 0

    def check(name, cond):
        nonlocal failures
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            failures += 1

    print(LINE)
    print("MICROTHEORY WORKED EXAMPLE #6 — recognisable algorithms, expanded opcodes")
    print(LINE)

    # A. mutual recursion ---------------------------------------------------
    even_odd = prog("is_even", IS_EVEN) + prog("is_odd", IS_ODD)
    a_ok = all(call_value(even_odd, "is_even", [n]).value == (1.0 if n % 2 == 0 else 0.0)
               for n in range(0, 21))
    print(f"\n[A] MUTUAL RECURSION  is_even/is_odd over 0..20 -> "
          f"{'EXACT MATCH' if a_ok else 'MISMATCH'}")
    check("is_even/is_odd (two microtheories calling each other) match Python", a_ok)

    # B. recursion ----------------------------------------------------------
    fib = prog("fib", FIB)
    b_ok = all(call_value(fib, "fib", [n]).value == py_fib(n) for n in range(0, 16))
    print(f"[B] RECURSION         fib over 0..15 -> {'EXACT MATCH' if b_ok else 'MISMATCH'}  "
          f"(fib(15)={int(call_value(fib, 'fib', [15]).value)})")
    check("recursive Fibonacci matches Python", b_ok)

    # C. composition --------------------------------------------------------
    lib = prog("gcd", GCD) + prog("lcm", LCM)
    pairs = [(12, 18), (21, 6), (100, 80), (17, 5), (48, 36)]
    c_ok = all(call_value(lib, "lcm", [a, b]).value == a * b // py_gcd(a, b) for a, b in pairs)
    print(f"[C] COMPOSITION       lcm (which CALLs gcd) over {len(pairs)} pairs -> "
          f"{'EXACT MATCH' if c_ok else 'MISMATCH'}")
    check("lcm composing gcd matches Python", c_ok)

    # D. EMIT (FizzBuzz) ----------------------------------------------------
    fb = prog("fbcode", FBCODE) + prog("fizzbuzz", FIZZBUZZ)
    fb_out = call_value(fb, "fizzbuzz", [100]).outputs
    fb_expect = [float(py_fizzbuzz_code(i)) for i in range(1, 101)]
    print(f"[D] EMIT              FizzBuzz codes for 1..100 -> "
          f"{'EXACT MATCH' if fb_out == fb_expect else 'MISMATCH'}  "
          f"(emitted {len(fb_out)} codes; e.g. 15 -> {int(fb_out[14])} = fizzbuzz)")
    check("FizzBuzz via EMIT matches Python over 1..100", fb_out == fb_expect)

    # E. composition + EMIT (primes) ----------------------------------------
    pr = prog("is_prime", IS_PRIME) + prog("primes", PRIMES)
    pr_out = [int(x) for x in call_value(pr, "primes", [50]).outputs]
    print(f"[E] COMPOSITION+EMIT  primes up to 50 -> {pr_out}")
    check("primes (CALLed is_prime + EMIT) match Python up to 50",
          pr_out == py_primes(50))

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "Mutual recursion, recursion, library composition, and sequence generation\n"
        "— all expressed as ordered microtheories (scoped, ordered, cited triples)\n"
        "and run by one small executor. The algorithms are knowledge you can read,\n"
        "diff, cite, and reason over — not opaque code.")
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
