"""Transpile an ORDERED microtheory to a Python function — the fast path.

`kb.execute` interprets an ordered-microtheory program instruction by instruction;
that is an interpreter on top of CPython, so ~10^2 x slower than native. This
module compiles a program AHEAD OF TIME into a real Python function, which then
runs at CPython speed.

It is SKEAR's construction/serve split applied to code: the program's triples
stay the canonical, inspectable source; the generated Python is a DERIVED,
throwaway cache (you can read it via `to_python_source`). Behaviour is identical
to the interpreter on the supported subset, and `run_compiled` transparently
FALLS BACK to the interpreter for anything outside it — so correctness never
depends on the optimiser.

How it works (sound, no control-flow guesswork):
  * Split the program into BASIC BLOCKS (a new block begins at index 0, at every
    jump target, and right after every JMP/JZ/RET).
  * A stack-height pass proves the operand stack is empty at every block boundary
    (true for statement-structured programs); if not, we decline (fall back).
  * Each block is compiled to straight-line Python over SSA temporaries `s0, s1,
    …` and the program's variables `v_<name>`, so arithmetic becomes native
    Python on locals with NO per-instruction dispatch.
  * Blocks are wired together by a `pc`-driven `while` loop — sound for any jump
    graph (reducible or not), with the dispatch paid per BLOCK, not per
    instruction.

Supported subset: PUSH, LOAD, STORE, ADD, SUB, MUL, DIV, MOD, LT/LE/GT/GE/EQ/NE,
DUP, POP, SWAP, JMP, JZ, RET. NOT yet: CALL, FETCH, EMIT, and the bitwise ops
AND/OR/XOR/NOT/SHL/SHR (these fall back to the interpreter — the bitwise ops carry
integer-coercion semantics that the float-native transpiled form would not preserve
exactly, so the interpreter, which refuses fractional operands, stays authoritative).
Programs read their inputs as variables (LOAD), matching `run(kb, scope, inputs)`.

Run the self-test:  python -m kb.transpile     (from src/)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kb.query import KB, Triple
from kb.execute import validate, ExecError, run

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class NotTranspilable(Exception):
    """Raised when a program is outside the supported subset; callers fall back
    to the interpreter."""


_UNSUPPORTED = {"CALL", "FETCH", "EMIT", "AND", "OR", "XOR", "NOT", "SHL", "SHR",
                # higher-order ops drive a nested interpreter per element, so they
                # stay on the interpreter rather than being inlined to native code.
                "MAP", "FILTER", "FOLD",
                # OPAQUE is a non-executable black-box marker (run-refused unless an
                # oracle is supplied) — there is nothing to compile to native code.
                "OPAQUE"}
_BINOP = {"ADD": "+", "SUB": "-", "MUL": "*"}
_CMP = {"LT": "<", "LE": "<=", "GT": ">", "GE": ">=", "EQ": "==", "NE": "!="}
# net effect on stack height, used to prove blocks balance at their boundaries
_HEIGHT = {"PUSH": +1, "LOAD": +1, "STORE": -1, "DUP": +1, "POP": -1, "SWAP": 0,
           "ADD": -1, "SUB": -1, "MUL": -1, "DIV": -1, "MOD": -1,
           "LT": -1, "LE": -1, "GT": -1, "GE": -1, "EQ": -1, "NE": -1,
           "JMP": 0, "JZ": -1, "RET": -1}


# helpers injected into the compiled function's namespace so DIV/MOD by zero
# raise the SAME ExecError the interpreter does (not a bare ZeroDivisionError).
def _div(a, b):
    if b == 0:
        raise ExecError("DIV by zero")
    return a / b


def _mod(a, b):
    if b == 0:
        raise ExecError("MOD by zero")
    return a % b


def _decode(kb: KB, scope: str):
    """Ordered program -> (instrs, seq->index). Rejects the unsupported opcodes."""
    prog = validate(kb, scope)                    # closed-set checks + ordering
    instrs = [(t.relation, t.object, t.seq) for t in prog]
    for op, _, seq in instrs:
        if op in _UNSUPPORTED:
            raise NotTranspilable(f"opcode {op!r} (at seq {seq}) is not transpilable yet")
    addr = {t.seq: i for i, t in enumerate(prog)}  # seq (address) -> list index
    return instrs, addr


def _leaders(instrs, addr):
    """Indices that begin a basic block: index 0, every jump target, and the
    instruction following any JMP/JZ/RET."""
    n = len(instrs)
    leaders = {0}
    for i, (op, raw, _seq) in enumerate(instrs):
        if op in ("JMP", "JZ"):
            leaders.add(addr[int(float(raw))])
            if i + 1 < n:
                leaders.add(i + 1)
        elif op == "RET":
            if i + 1 < n:
                leaders.add(i + 1)
    order = sorted(leaders)
    idx_to_block = {}
    for bi, start in enumerate(order):
        end = order[bi + 1] if bi + 1 < len(order) else n
        for j in range(start, end):
            idx_to_block[j] = bi
    return order, idx_to_block


def _check_heights(instrs, order, idx_to_block, addr):
    """Prove each block is entered with an empty operand stack (height 0). This
    is what lets each block compile independently with fresh SSA temps. Returns
    nothing; raises NotTranspilable if the property doesn't hold."""
    n = len(instrs)
    entry = {0: 0}                                 # block 0 entered at height 0
    work = [0]
    while work:
        bi = work.pop()
        h = entry[bi]
        start = order[bi]
        end = order[bi + 1] if bi + 1 < len(order) else n
        succ = []
        terminated = False
        for j in range(start, end):
            op, raw, _seq = instrs[j]
            h += _HEIGHT[op]
            if h < 0:
                raise NotTranspilable(f"stack underflow at index {j} ({op})")
            if op == "JMP":
                succ = [idx_to_block[addr[int(float(raw))]]]
                terminated = True
            elif op == "JZ":
                succ = [idx_to_block[addr[int(float(raw))]], idx_to_block[j + 1]]
                terminated = True
            elif op == "RET":
                succ = []
                terminated = True
            if terminated:
                break
        if not terminated:                         # fell through to the next block
            h_exit = h
            succ = [idx_to_block[end]] if end < n else []
        else:
            h_exit = h                             # height after the terminator's effect
        if h_exit != 0:
            raise NotTranspilable(f"block {bi} leaves the stack at height {h_exit} "
                                  f"(only statement-structured programs are transpiled)")
        for s in succ:
            if s in entry and entry[s] != 0:
                raise NotTranspilable(f"block {s} entered at inconsistent height")
            if s not in entry:
                entry[s] = 0
                work.append(s)


def to_python_source(kb: KB, scope: str, func_name: str = "_compiled") -> str:
    """Generate the Python source for `scope` (raises NotTranspilable if out of
    subset). Exposed so the derived code is itself inspectable."""
    instrs, addr = _decode(kb, scope)
    order, idx_to_block = _leaders(instrs, addr)
    _check_heights(instrs, order, idx_to_block, addr)

    variables = sorted({raw for op, raw, _ in instrs if op in ("LOAD", "STORE")})
    n = len(instrs)
    tmp = [0]

    def new_tmp():
        tmp[0] += 1
        return f"s{tmp[0]}"

    body = []
    for bi, start in enumerate(order):
        end = order[bi + 1] if bi + 1 < len(order) else n
        body.append(f"        if pc == {bi}:" if bi == 0 else f"        elif pc == {bi}:")
        sym = []                                   # symbolic stack of temp names
        terminated = False
        for j in range(start, end):
            op, raw, _seq = instrs[j]
            if op == "PUSH":
                t = new_tmp(); body.append(f"            {t} = {float(raw)!r}"); sym.append(t)
            elif op == "LOAD":
                t = new_tmp(); body.append(f"            {t} = v_{raw}"); sym.append(t)
            elif op == "STORE":
                body.append(f"            v_{raw} = {sym.pop()}")
            elif op in _BINOP:
                b, a = sym.pop(), sym.pop(); t = new_tmp()
                body.append(f"            {t} = ({a} {_BINOP[op]} {b})"); sym.append(t)
            elif op == "DIV":
                b, a = sym.pop(), sym.pop(); t = new_tmp()
                body.append(f"            {t} = _div({a}, {b})"); sym.append(t)
            elif op == "MOD":
                b, a = sym.pop(), sym.pop(); t = new_tmp()
                body.append(f"            {t} = _mod({a}, {b})"); sym.append(t)
            elif op in _CMP:
                b, a = sym.pop(), sym.pop(); t = new_tmp()
                body.append(f"            {t} = (1.0 if ({a} {_CMP[op]} {b}) else 0.0)"); sym.append(t)
            elif op == "DUP":
                sym.append(sym[-1])
            elif op == "POP":
                sym.pop()
            elif op == "SWAP":
                sym[-1], sym[-2] = sym[-2], sym[-1]
            elif op == "JMP":
                body.append(f"            pc = {idx_to_block[addr[int(float(raw))]]}; continue")
                terminated = True; break
            elif op == "JZ":
                cond = sym.pop()
                ktrue = idx_to_block[addr[int(float(raw))]]      # jump taken when cond == 0
                kfalse = idx_to_block[j + 1]
                body.append(f"            pc = {ktrue} if ({cond} == 0.0) else {kfalse}; continue")
                terminated = True; break
            elif op == "RET":
                body.append(f"            return {sym.pop() if sym else 'None'}")
                terminated = True; break
        if not terminated:                         # fall through to the next block
            body.append(f"            pc = {idx_to_block[end]}; continue")

    init = [f"    v_{v} = float(inputs['{v}']) if '{v}' in inputs else 0.0" for v in variables]
    src = (f"def {func_name}(inputs):\n"
           + ("\n".join(init) + "\n" if init else "")
           + "    pc = 0\n"
           + "    while True:\n"
           + "\n".join(body) + "\n")
    return src


_CACHE: dict = {}


def compile_program(kb: KB, scope: str):
    """Compile `scope` to a Python callable `f(inputs) -> float` (cached per
    (id(kb), scope)). Raises NotTranspilable if out of subset."""
    key = (id(kb), scope)
    if key in _CACHE:
        return _CACHE[key]
    src = to_python_source(kb, scope)
    ns = {"_div": _div, "_mod": _mod, "ExecError": ExecError}
    exec(compile(src, f"<transpiled:{scope}>", "exec"), ns)
    fn = ns["_compiled"]
    _CACHE[key] = fn
    return fn


def run_compiled(kb: KB, scope: str, inputs: dict | None = None):
    """Run `scope` via the transpiled function for speed, falling back to the
    interpreter for any program outside the supported subset. Returns the value
    (equivalent to `execute.run(...).value`)."""
    try:
        return compile_program(kb, scope)(inputs or {})
    except NotTranspilable:
        return run(kb, scope, inputs, trace=False).value


# --------------------------------------------------------------------------
# Self-test: transpiled output must equal the interpreter, over input sweeps.
# --------------------------------------------------------------------------
def _prog(scope, ops):
    return [Triple("p", op, ("" if a is None else str(a)), "t", i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


# sum 1..n (variable-convention: n comes from inputs)
SUM = [
    ("PUSH", 0), ("STORE", "t"), ("PUSH", 1), ("STORE", "i"),
    ("LOAD", "i"), ("LOAD", "n"), ("LE", None), ("JZ", 17),
    ("LOAD", "t"), ("LOAD", "i"), ("ADD", None), ("STORE", "t"),
    ("LOAD", "i"), ("PUSH", 1), ("ADD", None), ("STORE", "i"),
    ("JMP", 4),
    ("LOAD", "t"), ("RET", None),
]
# piecewise grade ladder
GRADE = [
    ("LOAD", "x"), ("PUSH", 90), ("GE", None), ("JZ", 6), ("PUSH", 4), ("RET", None),
    ("LOAD", "x"), ("PUSH", 80), ("GE", None), ("JZ", 12), ("PUSH", 3), ("RET", None),
    ("LOAD", "x"), ("PUSH", 70), ("GE", None), ("JZ", 18), ("PUSH", 2), ("RET", None),
    ("LOAD", "x"), ("PUSH", 60), ("GE", None), ("JZ", 24), ("PUSH", 1), ("RET", None),
    ("PUSH", 0), ("RET", None),
]
# gcd(a,b) Euclid, variable-convention (a,b from inputs)
GCD = [
    ("LOAD", "b"), ("PUSH", 0), ("EQ", None), ("JZ", 6),
    ("LOAD", "a"), ("RET", None),
    ("LOAD", "b"), ("STORE", "t"),
    ("LOAD", "a"), ("LOAD", "b"), ("MOD", None), ("STORE", "b"),
    ("LOAD", "t"), ("STORE", "a"),
    ("JMP", 0),
]
# uses DUP and SWAP: (x*x) - (a - b)
EXPR = [
    ("LOAD", "x"), ("DUP", None), ("MUL", None),
    ("LOAD", "a"), ("LOAD", "b"), ("SWAP", None), ("SUB", None),   # b - a
    ("SUB", None), ("RET", None),                                  # x*x - (b-a)
]


def _run() -> int:
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            fails += 1

    sum_kb = KB(triples=_prog("sum", SUM), alias_map={}, n_articles=0)
    check("transpiled sum == interpreter over n=0..50",
          all(compile_program(sum_kb, "sum")({"n": n}) == run(sum_kb, "sum", {"n": n}).value
              for n in range(0, 51)))

    grade_kb = KB(triples=_prog("grade", GRADE), alias_map={}, n_articles=0)
    check("transpiled grade == interpreter over x=0..100",
          all(compile_program(grade_kb, "grade")({"x": x}) == run(grade_kb, "grade", {"x": x}).value
              for x in range(0, 101)))

    gcd_kb = KB(triples=_prog("gcd", GCD), alias_map={}, n_articles=0)
    check("transpiled gcd == interpreter over a,b in 0..30",
          all(compile_program(gcd_kb, "gcd")({"a": a, "b": b}) == run(gcd_kb, "gcd", {"a": a, "b": b}).value
              for a in range(0, 31) for b in range(0, 31)))

    expr_kb = KB(triples=_prog("expr", EXPR), alias_map={}, n_articles=0)
    check("transpiled DUP/SWAP expr == interpreter",
          all(compile_program(expr_kb, "expr")({"x": x, "a": a, "b": b})
              == run(expr_kb, "expr", {"x": x, "a": a, "b": b}).value
              for x in (-3, 0, 4) for a in (1, 7) for b in (2, 9)))

    # the generated code is itself inspectable
    src = to_python_source(sum_kb, "sum")
    check("generates readable Python source (def + while loop)",
          src.startswith("def _compiled(inputs):") and "while True:" in src)

    # DIV by zero preserves the ExecError contract
    dz = KB(triples=_prog("dz", [("LOAD", "x"), ("PUSH", 0), ("DIV", None), ("RET", None)]),
            alias_map={}, n_articles=0)
    raised = False
    try:
        compile_program(dz, "dz")({"x": 1})
    except ExecError:
        raised = True
    check("transpiled DIV by zero raises ExecError (not ZeroDivisionError)", raised)

    # a CALL program is declined and falls back to the interpreter, same answer
    call_kb = KB(triples=_prog("inc", [("STORE", "a"), ("LOAD", "a"), ("PUSH", 1), ("ADD", None), ("RET", None)])
                 + _prog("usesinc", [("PUSH", 5), ("CALL", "inc"), ("RET", None)]),
                 alias_map={}, n_articles=0)
    declined = False
    try:
        compile_program(call_kb, "usesinc")
    except NotTranspilable:
        declined = True
    check("a CALL program is declined (NotTranspilable)", declined)
    check("run_compiled falls back to the interpreter for CALL programs",
          run_compiled(call_kb, "usesinc", {}) == run(call_kb, "usesinc", {}).value == 6.0)

    print("ALL PASS" if fails == 0 else f"{fails} FAILED")
    return fails


if __name__ == "__main__":
    sys.exit(1 if _run() else 0)
