"""Execute an ORDERED microtheory as a program — SKEAR's third operational faculty.

SKEAR already has faculties that act on triples: `query.py` (lookup / traversal)
and `reason.py` (deductive inference — derive new facts). This module adds the
third: an **executor** that runs an ordered microtheory as a program, turning
*structure → computation* (the counterpart to the deterministic *structure →
text* rendering elsewhere in the system).

The premise: once a microtheory is a SEQUENCE (`Triple.seq`), a microtheory whose
member relations are OPCODES and whose objects are OPERANDS is a program, and the
sequence is its instruction stream. A small, fixed stack machine interprets it —
so an algorithm can live as inspectable, scoped, provenance-carrying DATA rather
than as opaque code. One executor runs every program; behaviour is in the KB.

Design commitments (the same ones that make the rest of SKEAR trustworthy):
  * CLOSED instruction set. Only the opcodes in `OPCODES` execute; anything else
    is REFUSED before any step runs. There is no `eval`, no host/IO access, no
    dynamic dispatch into Python — execution cannot do what the opcode set can't.
  * DETERMINISTIC + AUDITABLE. Same program + same inputs → same result, and a
    per-step trace cites the source of every instruction (a "why" for the output).
  * GUARANTEED TERMINATION. A step budget bounds execution; a program that would
    loop forever raises `ExecError` instead of hanging — the executor's analogue
    of the reasoner's fixpoint divergence guard. A call-depth bound does the same
    for runaway recursion.

Instruction set. A program is authored as STEP triples — relation=opcode,
object=operand, seq=address:

  data / arithmetic / compare
    PUSH c        push numeric constant c
    LOAD v        push the value of input/variable v (variables are per-call: local)
    STORE v       pop and store into variable v
    ADD SUB MUL   pop b, pop a, push (a OP b)
    DIV MOD
    LT LE GT      pop b, pop a, push 1.0 if (a CMP b) else 0.0
    GE EQ NE
  bitwise (INTEGER ops — operands must be whole numbers, else REFUSED)
    AND OR XOR    pop b, pop a, push (int(a) OP int(b)) as a number — bit masks,
                  flags, set membership: the things real code expresses with & | ^
    SHL SHR       pop b, pop a, push int(a) shifted by int(b) bits (b >= 0)
    NOT           pop a, push ~int(a). Two's-complement, width-free: NOT n == -(n+1),
                  so `x AND (NOT mask)` clears mask's bits exactly, as in C.
  stack shuffling (ergonomics — author without a temp variable for everything)
    DUP           push a copy of the top
    POP           discard the top
    SWAP          exchange the top two
  control flow
    JMP a         set the program counter to address (seq) a
    JZ  a         pop c; if c == 0 (false) jump to address a, else fall through
    CALL scope    invoke another ordered microtheory `scope` as a SUBROUTINE:
                  it shares the operand stack (args in, result out) but gets a
                  fresh local-variable frame; execution resumes after the CALL
                  when the callee hits RET. Enables composition + recursion —
                  i.e. procedures (microtheories) calling sub-procedures.
    RET           return to the caller (or stop, if top-level). Result = top of stack.
  output
    EMIT          append the top of stack to the result's `outputs` list (for
                  programs that produce a SEQUENCE of outputs, not one value)
  data access (NO disconnect between the algorithm and the data)
    FETCH s|r     read the fact (subject=s, relation=r) from THIS SAME KB and push
                  its object as a number. The program operates directly on the
                  knowledge base's own facts — no ORM, no serialization, no
                  separate data layer. The fact's source is recorded in the trace,
                  so the result's provenance spans both the program and the data.
    FETCH @v|r    PARAMETRIC subject: read the subject from the local variable `v`
                  (an entity id supplied as an input or STOREd earlier), then fetch
                  (that subject, relation=r). This lets one program be written once
                  over a GENERIC entity and run against any concrete one — e.g. a
                  per-customer rule whose `customer_id` is an input — instead of
                  baking a specific subject into the operand. The resolved subject
                  is recorded in the trace exactly like a literal FETCH.

`seq` is the address: JMP/JZ targets name the `seq` of the instruction to run
next. CALL targets name another scope. Authoring programs with contiguous seq
0..N-1 makes addresses obvious.

Run the self-test:  python -m kb.execute     (from src/)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kb.query import KB, Triple

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# The closed instruction set. A relation outside this set is not executable.
_NULLARY = {"ADD", "SUB", "MUL", "DIV", "MOD",
            "LT", "LE", "GT", "GE", "EQ", "NE",
            "AND", "OR", "XOR", "NOT", "SHL", "SHR",
            "DUP", "POP", "SWAP", "EMIT", "RET"}
_UNARY = {"PUSH", "LOAD", "STORE", "JMP", "JZ", "CALL", "FETCH"}
OPCODES = _NULLARY | _UNARY


class ExecError(Exception):
    """A controlled execution failure: an unknown opcode (refusal), a malformed
    program, division by zero, an empty-stack pop, a bad jump/call target, or a
    budget (steps / call depth) exceeded. Raised instead of letting the host
    crash or loop forever."""


@dataclass
class ExecResult:
    value: float | None                 # top of stack when the top-level returns
    trace: list[str] = field(default_factory=list)   # per-step provenance log
    steps: int = 0                      # instructions executed (for cost/limits)
    outputs: list = field(default_factory=list)       # values produced by EMIT
    reads: list = field(default_factory=list)         # facts read via FETCH (cited)


@dataclass
class _Frame:
    """One activation record: a program (ordered scope), its address map, the
    program counter, and a private variable namespace (so recursion works)."""
    scope: str
    prog: list
    addr: dict
    pc: int = 0
    variables: dict = field(default_factory=dict)


def validate(kb: KB, scope: str) -> list[Triple]:
    """Check a program is executable BEFORE running a single step: it must be a
    non-empty ordered scope using only known opcodes, with unary ops carrying an
    operand. Returns the instruction list (ordered by seq). Refuses otherwise —
    this is what makes execution safe-by-construction rather than safe-by-luck."""
    prog = [t for t in kb.ordered_scope(scope) if t.seq is not None]
    if not prog:
        raise ExecError(f"scope {scope!r} is not an ordered program (no seq'd steps)")
    for t in prog:
        if t.relation not in OPCODES:
            raise ExecError(f"opcode {t.relation!r} not in the closed set {sorted(OPCODES)}")
        if t.relation in _UNARY and (t.object is None or t.object == ""):
            raise ExecError(f"opcode {t.relation!r} at seq {t.seq} needs an operand")
    return prog


def _compile(kb: KB, scope: str, cache: dict) -> tuple:
    """Compile an ordered microtheory ONCE into a fast, pre-decoded instruction
    list, and memoise it in `cache`. This is SKEAR's construction/serve split
    applied to execution: the data (scoped triples) stays canonical and
    inspectable; the compiled form is a derived, throwaway cache. Decoding once
    here is what makes recursion cheap — a self-CALL re-uses the cached program
    instead of re-validating and re-sorting the scope on every call.

    Each compiled step is `(op, arg, triple)` with the operand PRE-PARSED:
      * PUSH      -> float constant
      * JMP / JZ  -> the *list index* of the target (resolved from seq now, so the
                     hot loop never does a dict lookup or string->int parse)
      * FETCH     -> a (subject, relation) pair
      * others    -> the raw operand (variable name / scope name / None)
    The original triple is kept for the cited trace."""
    if scope in cache:
        return cache[scope]
    prog = validate(kb, scope)                    # closed-set + operand checks (refusal)
    addr = {t.seq: i for i, t in enumerate(prog)}  # seq (address) -> list index
    decoded = []
    for t in prog:
        op, raw = t.relation, t.object
        if op == "PUSH":
            arg = float(raw)
        elif op in ("JMP", "JZ"):
            try:
                target = int(float(raw))
            except (TypeError, ValueError):
                raise ExecError(f"jump target {raw!r} is not an address")
            if target not in addr:
                raise ExecError(f"jump to undefined address {target} in {scope!r}")
            arg = addr[target]                    # resolve to a list index up front
        elif op == "FETCH":
            # subject may be a literal ("widget") or parametric ("@customer_id");
            # the leading '@' is resolved against frame locals at run time.
            subj, sep, rel = str(raw).partition("|")
            if not sep:
                raise ExecError(f"FETCH operand {raw!r} must be 'subject|relation'")
            arg = (subj, rel)
        else:
            arg = raw
        decoded.append((op, arg, t))
    cache[scope] = (decoded, addr)
    return cache[scope]


def _as_int(x, op, t):
    """Coerce a stack value to an int for a bitwise op. Bitwise logic is integer
    logic, so a fractional operand is a REFUSAL (an honest error), not a silent
    floor — same safe-by-construction stance as DIV-by-zero or an unknown opcode."""
    if isinstance(x, float) and not x.is_integer():
        raise ExecError(f"{op} requires integer operands, got {x} at seq {t.seq}")
    return int(x)


def _norm_input(v):
    """Normalise one run() input. Numbers (and numeric strings) become floats so
    the executor's arithmetic stays float-only and LOAD stays a bare dict read.
    A non-numeric string is kept verbatim — it is an entity id for parametric
    `FETCH @var|relation`, a subject rather than a quantity."""
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return v                                  # entity id (subject), not a number
    return float(v)


def run(kb: KB, scope: str, inputs: dict[str, float] | None = None,
        max_steps: int = 100_000, max_depth: int = 256, trace: bool = True) -> ExecResult:
    """Execute the program in microtheory `scope` against `inputs`. Returns an
    ExecResult (value + provenance trace + step count + EMITted outputs + FETCHed
    facts). Raises ExecError on any refusal/fault. `max_steps` bounds total work
    and `max_depth` bounds the CALL stack, so a non-terminating or infinitely-
    recursive program fails loudly instead of hanging.

    `trace=True` (the default) records a cited line per executed step. Building
    those strings dominates runtime, so pass `trace=False` for hot/measured
    execution where only the result and EMIT/FETCH outputs are needed."""
    stack: list = []
    outputs: list = []
    fetched: list = []                            # facts read via FETCH (cited)
    tlog: list = []                               # per-step trace (only if `trace`)
    cache: dict = {}                              # compiled programs, by scope
    decoded, addr = _compile(kb, scope, cache)
    # Normalise inputs ONCE here. Numeric inputs become floats so the hot loop's
    # LOAD stays a bare dict read (every value the arithmetic ops touch is already
    # a float: PUSH is pre-parsed, arithmetic yields floats, STORE only ever
    # stores stack values). NON-numeric strings are kept verbatim — these are the
    # entity ids consumed by parametric `FETCH @var|relation`, which reads a
    # subject (e.g. "customer_7741"), not a number. They never enter arithmetic in
    # a well-formed program; LOAD of one simply pushes the id back unchanged.
    init_vars = {k: _norm_input(v) for k, v in (inputs or {}).items()}
    frames: list[_Frame] = [_Frame(scope, decoded, addr, 0, init_vars)]
    steps = 0

    def pop(op):
        if not stack:
            raise ExecError(f"stack underflow on {op}")
        return stack.pop()

    while frames:
        fr = frames[-1]
        prog = fr.prog
        if fr.pc >= len(prog):                    # ran off the end => implicit return
            frames.pop()
            continue
        if steps >= max_steps:
            raise ExecError(f"step budget {max_steps} exceeded (non-terminating program?)")
        steps += 1
        op, arg, t = prog[fr.pc]                   # pre-decoded: no parsing here
        nxt = fr.pc + 1                            # default: fall through

        if op == "PUSH":
            stack.append(arg)                     # already a float
        elif op == "LOAD":
            v = fr.variables
            if arg not in v:
                raise ExecError(f"LOAD of undefined variable {arg!r} in {fr.scope!r}")
            stack.append(v[arg])                  # already float (normalised on entry / STORE)
        elif op == "STORE":
            fr.variables[arg] = pop(op)
        elif op == "ADD":
            b, a = pop(op), pop(op); stack.append(a + b)
        elif op == "SUB":
            b, a = pop(op), pop(op); stack.append(a - b)
        elif op == "MUL":
            b, a = pop(op), pop(op); stack.append(a * b)
        elif op == "DIV":
            b, a = pop(op), pop(op)
            if b == 0:
                raise ExecError(f"DIV by zero at seq {t.seq}")
            stack.append(a / b)
        elif op == "MOD":
            b, a = pop(op), pop(op)
            if b == 0:
                raise ExecError(f"MOD by zero at seq {t.seq}")
            stack.append(a % b)
        elif op == "AND":
            b, a = pop(op), pop(op); stack.append(float(_as_int(a, op, t) & _as_int(b, op, t)))
        elif op == "OR":
            b, a = pop(op), pop(op); stack.append(float(_as_int(a, op, t) | _as_int(b, op, t)))
        elif op == "XOR":
            b, a = pop(op), pop(op); stack.append(float(_as_int(a, op, t) ^ _as_int(b, op, t)))
        elif op == "NOT":
            a = pop(op); stack.append(float(~_as_int(a, op, t)))
        elif op == "SHL":
            b, a = pop(op), pop(op); n = _as_int(b, op, t)
            if n < 0:
                raise ExecError(f"SHL by negative amount {n} at seq {t.seq}")
            stack.append(float(_as_int(a, op, t) << n))
        elif op == "SHR":
            b, a = pop(op), pop(op); n = _as_int(b, op, t)
            if n < 0:
                raise ExecError(f"SHR by negative amount {n} at seq {t.seq}")
            stack.append(float(_as_int(a, op, t) >> n))
        elif op == "LT":
            b, a = pop(op), pop(op); stack.append(1.0 if a < b else 0.0)
        elif op == "LE":
            b, a = pop(op), pop(op); stack.append(1.0 if a <= b else 0.0)
        elif op == "GT":
            b, a = pop(op), pop(op); stack.append(1.0 if a > b else 0.0)
        elif op == "GE":
            b, a = pop(op), pop(op); stack.append(1.0 if a >= b else 0.0)
        elif op == "EQ":
            b, a = pop(op), pop(op); stack.append(1.0 if a == b else 0.0)
        elif op == "NE":
            b, a = pop(op), pop(op); stack.append(1.0 if a != b else 0.0)
        elif op == "DUP":
            x = pop(op); stack.append(x); stack.append(x)
        elif op == "POP":
            pop(op)
        elif op == "SWAP":
            b, a = pop(op), pop(op); stack.append(b); stack.append(a)
        elif op == "FETCH":
            # Read a fact straight out of THIS KB (operand pre-parsed to (s, r)).
            # The algorithm and the data it consumes live in one store — no
            # bridge, no copy. The read is cited so provenance stays unbroken.
            subj, rel = arg
            if subj.startswith("@"):
                # Parametric subject: resolve `@var` from this frame's locals.
                var = subj[1:]
                if var not in fr.variables:
                    raise ExecError(f"FETCH @{var}: variable not set in {fr.scope!r}")
                subj = str(fr.variables[var])
            facts = kb.out_facts(subj, rel)
            if not facts:
                raise ExecError(f"FETCH found no fact ({subj}, {rel}) in the KB")
            try:
                stack.append(float(facts[0].object))
            except (TypeError, ValueError):
                raise ExecError(f"FETCH ({subj}, {rel}): object "
                                f"{facts[0].object!r} is not numeric")
            fetched.append(f"{subj} {rel} {facts[0].object} [{facts[0].source_article}]")
        elif op == "EMIT":
            outputs.append(stack[-1] if stack else None)
        elif op == "JMP":
            nxt = arg                             # pre-resolved list index
        elif op == "JZ":
            nxt = arg if pop(op) == 0 else fr.pc + 1
        elif op == "CALL":
            fr.pc += 1                            # return address: after the CALL
            if len(frames) >= max_depth:
                raise ExecError(f"call depth {max_depth} exceeded (runaway recursion?)")
            if trace:
                tlog.append(_fmt(t, stack))
            cd, ad = _compile(kb, arg, cache)     # compiled once, re-used on recursion
            frames.append(_Frame(arg, cd, ad, 0, {}))   # fresh locals; shared stack
            continue
        elif op == "RET":
            if trace:
                tlog.append(_fmt(t, stack))
            frames.pop()                          # value(s) remain on the shared stack
            continue
        else:                                     # unreachable: validate() gates this
            raise ExecError(f"unhandled opcode {op!r}")

        if trace:
            tlog.append(_fmt(t, stack))
        fr.pc = nxt

    return ExecResult(stack[-1] if stack else None, tlog, steps, outputs, fetched)


def _fmt(t: Triple, stack: list[float]) -> str:
    operand = "" if t.object in (None, "") else f" {t.object}"
    return f"@{t.seq}: {t.relation}{operand}   stack={stack}   [{t.source_article}]"


# --------------------------------------------------------------------------
# Self-test (assert-based, matching the repo's runnable-test style).
# --------------------------------------------------------------------------
def _prog(scope, ops, source="test"):
    """Author a program as an ordered microtheory (relation=opcode, object=operand)."""
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]


def _run() -> int:
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            fails += 1

    # straight-line arithmetic: (P*R*T)
    kb = KB(triples=_prog("interest", [("LOAD", "P"), ("LOAD", "R"), ("MUL", None),
                                        ("LOAD", "T"), ("MUL", None), ("RET", None)]),
            alias_map={}, n_articles=0)
    check("straight-line program computes P*R*T",
          run(kb, "interest", {"P": 1000, "R": 0.05, "T": 3}).value == 150.0)

    # branch + loop: sum 1..n, but n<0 -> 0 (explicit back-edge)
    sumprog = [
        ("LOAD", "n"), ("PUSH", 0), ("LT", None), ("JZ", 6),      # 0-3 if n<0 goto 6
        ("PUSH", 0), ("RET", None),                               # 4-5 return 0
        ("PUSH", 0), ("STORE", "t"),                              # 6-7 t=0
        ("PUSH", 1), ("STORE", "i"),                              # 8-9 i=1
        ("LOAD", "i"), ("LOAD", "n"), ("LE", None), ("JZ", 23),   # 10-13 while i<=n
        ("LOAD", "t"), ("LOAD", "i"), ("ADD", None), ("STORE", "t"),   # 14-17 t+=i
        ("LOAD", "i"), ("PUSH", 1), ("ADD", None), ("STORE", "i"),     # 18-21 i+=1
        ("JMP", 10),                                              # 22 loop
        ("LOAD", "t"), ("RET", None),                             # 23-24 return t
    ]
    kb2 = KB(triples=_prog("sum", sumprog), alias_map={}, n_articles=0)

    def py_sum(n):
        return 0 if n < 0 else sum(range(1, n + 1))

    check("branch+loop program exactly replicates a Python function over -3..20",
          all(run(kb2, "sum", {"n": n}).value == py_sum(n) for n in range(-3, 21)))

    # stack ops: DUP/SWAP/POP — compute x*x via DUP, then SWAP/POP behaviour
    sq = KB(triples=_prog("sq", [("LOAD", "x"), ("DUP", None), ("MUL", None), ("RET", None)]),
            alias_map={}, n_articles=0)
    check("DUP enables x*x without a temp variable", run(sq, "sq", {"x": 9}).value == 81.0)
    sw = KB(triples=_prog("sw", [("PUSH", 3), ("PUSH", 7), ("SWAP", None), ("SUB", None), ("RET", None)]),
            alias_map={}, n_articles=0)
    check("SWAP exchanges the top two (7-3=4)", run(sw, "sw", {}).value == 4.0)

    # CALL: composition. A subroutine `inc` (arg on stack -> arg+1); main squares
    # its result: sq_inc(x) = (x+1)^2. Two microtheories, one calling the other.
    inc = _prog("inc", [("STORE", "a"), ("LOAD", "a"), ("PUSH", 1), ("ADD", None), ("RET", None)], "lib")
    sq_inc = _prog("sq_inc", [("LOAD", "x"), ("CALL", "inc"), ("DUP", None), ("MUL", None), ("RET", None)], "app")
    kbc = KB(triples=inc + sq_inc, alias_map={}, n_articles=0)
    check("CALL composes microtheories: (x+1)^2 via a subroutine",
          run(kbc, "sq_inc", {"x": 4}).value == 25.0)

    # CALL: recursion. factorial as a microtheory that calls itself (arg on stack).
    factprog = [
        ("STORE", "n"),                                       # 0  n = arg (from stack)
        ("LOAD", "n"), ("PUSH", 1), ("LE", None), ("JZ", 8),  # 1-4 if !(n<=1) goto 8
        ("PUSH", 1), ("RET", None),                           # 5-6 base case: return 1
        ("PUSH", 0),                                          # 7  pad (unreached)
        ("LOAD", "n"),                                        # 8  push n
        ("LOAD", "n"), ("PUSH", 1), ("SUB", None),            # 9-11 push n-1
        ("CALL", "fact"),                                     # 12 push fact(n-1)
        ("MUL", None), ("RET", None),                         # 13-14 return n*fact(n-1)
    ]
    kbf = KB(triples=_prog("fact", factprog, "lib"), alias_map={}, n_articles=0)

    def py_fact(n):
        r = 1
        for i in range(2, n + 1):
            r *= i
        return r

    check("recursive CALL: factorial matches Python over 0..8",
          all(_fact_call(kbf, n) == py_fact(n) for n in range(0, 9)))

    # EMIT: a program that produces a SEQUENCE of outputs (1,2,...,n)
    emit_final = [
        ("PUSH", 1), ("STORE", "i"),                          # 0-1 i=1
        ("LOAD", "i"), ("LOAD", "n"), ("LE", None), ("JZ", 14),  # 2-5 while i<=n
        ("LOAD", "i"), ("EMIT", None), ("POP", None),         # 6-8 emit i, clear stack
        ("LOAD", "i"), ("PUSH", 1), ("ADD", None), ("STORE", "i"),  # 9-12 i+=1
        ("JMP", 2),                                           # 13 loop
        ("PUSH", 0), ("RET", None),                           # 14-15 done
    ]
    kbe = KB(triples=_prog("count", emit_final), alias_map={}, n_articles=0)
    check("EMIT collects a sequence of outputs (1..5)",
          run(kbe, "count", {"n": 5}).outputs == [1.0, 2.0, 3.0, 4.0, 5.0])

    # FETCH: a program reads a fact straight out of the SAME KB (no data/code gap)
    data_and_program = (
        [Triple("widget", "PRICE", "25", "catalogue", 0, None, None, 1.0),   # a plain fact
         Triple("widget", "QTY", "4", "stock_sheet", 0, None, None, 1.0)]    # another plain fact
        + _prog("line_total", [("FETCH", "widget|PRICE"), ("FETCH", "widget|QTY"),
                               ("MUL", None), ("RET", None)], "pricing"))
    kbd = KB(triples=data_and_program, alias_map={}, n_articles=0)
    rfetch = run(kbd, "line_total", {})
    check("FETCH lets a program compute over the KB's own facts (25*4=100)",
          rfetch.value == 100.0)
    check("FETCH records the facts it read, cited", len(rfetch.reads) == 2
          and "[catalogue]" in rfetch.reads[0])

    # PARAMETRIC FETCH: one program written over a GENERIC subject, run against
    # any concrete entity. `@who|BALANCE` reads the subject from the input `who`,
    # so the SAME program serves every account without baking in a subject.
    accounts = [
        Triple("alice", "BALANCE", "120", "ledger", 0, None, None, 1.0),
        Triple("bob", "BALANCE", "40", "ledger", 0, None, None, 1.0),
        Triple("global", "MIN_BALANCE", "50", "policy", 0, None, None, 1.0),
    ]
    # surplus(who) = who.BALANCE - global.MIN_BALANCE  (mixes parametric + literal)
    surplus = _prog("surplus", [("FETCH", "@who|BALANCE"), ("FETCH", "global|MIN_BALANCE"),
                                ("SUB", None), ("RET", None)], "rules")
    kbp = KB(triples=accounts + surplus, alias_map={}, n_articles=0)
    check("parametric FETCH resolves @who against alice (120-50=70)",
          run(kbp, "surplus", {"who": "alice"}).value == 70.0)
    check("the SAME program serves bob with no rewrite (40-50=-10)",
          run(kbp, "surplus", {"who": "bob"}).value == -10.0)
    rp = run(kbp, "surplus", {"who": "alice"})
    check("parametric FETCH cites the RESOLVED subject, not '@who'",
          any("alice BALANCE" in r for r in rp.reads))
    check("parametric FETCH with the variable unset is a controlled refusal",
          _raises(lambda: run(kbp, "surplus", {})))
    check("a non-numeric input survives normalisation as a subject id",
          _norm_input("customer_7741") == "customer_7741" and _norm_input("3.5") == 3.5)

    # bitwise opcodes: integer logic for flags / masks / sets
    def _bit(scope, ops):
        return run(KB(triples=_prog(scope, ops), alias_map={}, n_articles=0), scope, {}).value
    check("AND: 12 & 10 == 8", _bit("a", [("PUSH", 12), ("PUSH", 10), ("AND", None), ("RET", None)]) == 8.0)
    check("OR: 12 | 10 == 14", _bit("o", [("PUSH", 12), ("PUSH", 10), ("OR", None), ("RET", None)]) == 14.0)
    check("XOR: 12 ^ 10 == 6", _bit("x", [("PUSH", 12), ("PUSH", 10), ("XOR", None), ("RET", None)]) == 6.0)
    check("SHL: 1 << 4 == 16", _bit("sl", [("PUSH", 1), ("PUSH", 4), ("SHL", None), ("RET", None)]) == 16.0)
    check("SHR: 240 >> 4 == 15", _bit("sr", [("PUSH", 240), ("PUSH", 4), ("SHR", None), ("RET", None)]) == 15.0)
    check("NOT: ~5 == -6 (two's complement)", _bit("nt", [("PUSH", 5), ("NOT", None), ("RET", None)]) == -6.0)
    check("clear-bits idiom: 7 AND (NOT 2) == 5",
          _bit("cb", [("PUSH", 7), ("PUSH", 2), ("NOT", None), ("AND", None), ("RET", None)]) == 5.0)
    bfrac = KB(triples=_prog("bf", [("PUSH", 2.5), ("PUSH", 1), ("AND", None), ("RET", None)]), alias_map={}, n_articles=0)
    check("bitwise op on a fractional operand is a controlled refusal",
          _raises(lambda: run(bfrac, "bf", {})))
    bneg = KB(triples=_prog("bn", [("PUSH", 1), ("PUSH", -1), ("SHL", None), ("RET", None)]), alias_map={}, n_articles=0)
    check("negative shift amount is refused", _raises(lambda: run(bneg, "bn", {})))

    # closed set: an unknown opcode is refused before execution
    bad = KB(triples=_prog("evil", [("LOAD", "x"), ("OPEN_FILE", "/etc/passwd")]),
             alias_map={}, n_articles=0)
    check("unknown opcode refused before any step runs",
          _raises(lambda: run(bad, "evil", {"x": 1})))

    # termination guard: an infinite loop raises rather than hangs
    spin = KB(triples=_prog("spin", [("JMP", 0)]), alias_map={}, n_articles=0)
    check("non-terminating program hits the step budget and raises",
          _raises(lambda: run(spin, "spin", {}, max_steps=1000)))

    # recursion guard: unbounded recursion hits the depth limit, not a crash
    rec = KB(triples=_prog("rec", [("CALL", "rec"), ("RET", None)]), alias_map={}, n_articles=0)
    check("runaway recursion hits the call-depth bound and raises",
          _raises(lambda: run(rec, "rec", {}, max_steps=10**9, max_depth=64)))

    # safety/fault: division by zero is a controlled refusal
    dz = KB(triples=_prog("dz", [("PUSH", 1), ("PUSH", 0), ("DIV", None), ("RET", None)]),
            alias_map={}, n_articles=0)
    check("division by zero is a controlled ExecError, not a crash",
          _raises(lambda: run(dz, "dz", {})))

    print("ALL PASS" if fails == 0 else f"{fails} FAILED")
    return fails


def _fact_call(kb, n):
    """Helper: push n then call fact (fact STOREs its arg from the stack)."""
    # author a tiny driver that pushes n and calls fact, so the arg is on the stack
    driver = _prog("_drive", [("PUSH", n), ("CALL", "fact"), ("RET", None)], "drv")
    kb2 = KB(triples=kb.triples + driver, alias_map={}, n_articles=0)
    return run(kb2, "_drive", {}).value


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except ExecError:
        return True


if __name__ == "__main__":
    sys.exit(1 if _run() else 0)
