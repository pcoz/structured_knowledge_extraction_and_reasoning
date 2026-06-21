# Ordered Microtheories — procedures, programs, and code-as-data in SKEAR

> **See also**: [README](../README.md) ·
> [ARCHITECTURE](ARCHITECTURE.md) ·
> [DEVELOPER_GUIDE](DEVELOPER_GUIDE.md) ·
> [USE_CASES](USE_CASES.md) ·
> [COMPARISONS](COMPARISONS.md) ·
> [NOVELTIES](NOVELTIES.md) ·
> [LICENSE](../LICENSE.md)

This is the complete, self-contained guide to one capability: **ordered
microtheories** and the **executor** built on them. If you read nothing else,
read this — it is the only document you need to author, read, run, and reason
about procedures and programs expressed as SKEAR knowledge.

The runnable companions live in `src/microtheory/`:
`procedure.py`, `program.py`, `replicate.py`, and the core executor
`src/kb/execute.py`. Every claim below is demonstrated by an assertion in one of
those files; run them (from `src/`) as you read:

```
python -m microtheory.procedure     # an ordered microtheory IS a procedure
python -m microtheory.program       # an ordered microtheory as a substitute for code
python -m microtheory.replicate     # replicate real Python; measure the efficiency
python -m microtheory.showcase      # recursion, mutual recursion, composition, EMIT
python -m microtheory.unified       # the algorithm and the data in one KB (no disconnect)
python -m microtheory.parametric    # one rule, every entity: FETCH @var|relation
python -m microtheory.complexity    # a polynomial (O(M^2)->O(M)) speedup from the index
python -m microtheory.paradigm      # capstone: query + reason + execute on one KB
python -m microtheory.fraud         # applied capstone: fraud detection, every flag cited
python -m kb.execute                # the executor's own self-test
python -m kb.transpile              # the transpiler's own self-test
```

---

## 1. The one idea

A SKEAR microtheory (`Triple.scope`) is a **set** of facts that hold together
in one context — see [NOVELTIES §6](NOVELTIES.md) and `src/microtheory/`. A flat
microtheory has no inherent order; the four schools-of-economics example doesn't
care which fact you read first.

An **ordered microtheory** adds one optional field, `Triple.seq`, that gives each
member a **position**. That turns the set into a **sequence**. A sequence of
facts is a *list of steps*; a list of steps is a **procedure**; and a procedure
whose steps are *operations* is a **program**.

```
flat microtheory   = a SET of co-scoped facts            (Triple.scope)
ordered microtheory = a SEQUENCE of co-scoped facts       (Triple.scope + Triple.seq)
                    = a procedure (steps for a human)
                    = a program  (opcodes for the executor)
```

Nothing else in SKEAR changes. `seq=None` (the default) means "unordered set
member", so every existing KB, scope, and test behaves exactly as before. Order
is **opt-in, per fact, backward-compatible** — the same way `scope` itself was
added.

---

## 2. The schema: `seq`

`Triple` (in both `kb/query.py` and `kb/extract.py`) carries:

```python
scope: str | None = None    # which microtheory (None = global, holds everywhere)
seq:   int | None = None    # position within an ORDERED microtheory
                            #   None  -> unordered set member (the v1 default)
                            #   0,1,2 -> this fact is step 0, 1, 2 ... of `scope`
```

`seq` is **independent of `source_sentence_idx`**. The latter records *where the
fact came from* in a source document; `seq` records *what step it is* in the
procedure. Two facts ingested from different sources can still be steps 1 and 2
of one procedure.

### Reading an ordered microtheory

```python
kb.in_scope(scope)                 # v1: the scope's facts + globals, input order
kb.in_scope(scope, ordered=True)   # NEW: sorted into the sequence —
                                   #   seq-tagged members ascend by seq, then
                                   #   source_sentence_idx as a stable tiebreak;
                                   #   untagged members / globals follow
kb.ordered_scope(scope)            # NEW: the scope's OWN steps only, in order
                                   #   (globals excluded) — read a procedure out
```

`ordered=False` is unchanged, so a scope with no `seq` reads exactly as it did
before. (Asserted in `microtheory/test_scope.py`.)

---

## 3. Procedures (steps for a human)

A procedure is an ordered microtheory whose steps are `STEP` facts. Author one by
giving each step a `seq`:

```python
from kb.query import KB, Triple

SRC = "bp_monitor_manual"
steps = [
    Triple("measure_bp", "STEP", "rest_quietly_for_5_minutes", SRC, 0, None, None, 1.0, "measure_bp", 0),
    Triple("measure_bp", "STEP", "sit_with_back_supported",    SRC, 1, None, None, 1.0, "measure_bp", 1),
    Triple("measure_bp", "STEP", "bare_the_upper_arm",         SRC, 2, None, None, 1.0, "measure_bp", 2),
    Triple("measure_bp", "STEP", "apply_cuff_at_heart_level",  SRC, 3, None, None, 1.0, "measure_bp", 3),
    Triple("measure_bp", "STEP", "press_start_and_stay_still", SRC, 4, None, None, 1.0, "measure_bp", 4),
    Triple("measure_bp", "STEP", "record_the_reading",         SRC, 5, None, None, 1.0, "measure_bp", 5),
]
kb = KB(triples=steps, alias_map={}, n_articles=0)

for i, t in enumerate(kb.ordered_scope("measure_bp"), 1):
    print(i, t.object)          # 1 rest_quietly_for_5_minutes ... 6 record_the_reading
```

Because a procedure is *still just scoped triples*, every SKEAR faculty composes
with it for free (all shown in `microtheory/procedure.py`):

- **Procedures as framings.** Two variants of one task (e.g. a canonical protocol
  vs a rushed one) are two ordered microtheories. Diff them by `seq`; the
  difference is queryable data, not narrative.
- **Scope-aware conflict.** "Variant A does it differently from variant B" is
  **not** a contradiction (different microtheories) — exactly as for the
  schools-of-economics example — while a genuine contradiction *within one
  variant* still fires.
- **Reasoning over order.** Emit `PRECEDES(step_i, step_{i+1})` and hand it to the
  real fixpoint reasoner (`kb.reason`): it computes the full precedence closure,
  and a non-linearizable (cyclic) procedure surfaces as derived self-precedence —
  a structural bug caught by reasoning, with no bespoke cycle checker.

---

## 4. Programs (the executor) — SKEAR as a substitute for code

If a procedure's steps are **operations**, the ordered microtheory is an
**executable program**, run by SKEAR's third operational faculty: the executor
in `kb/execute.py`. (The first two faculties are *query* — lookup/traversal — and
*reason* — deductive inference. The executor is *structure → computation*.)

The algorithm then lives as **data**: inspectable, scoped, cited, diffable, and
reason-over-able — not opaque code. One executor runs every program; behaviour
is in the KB.

### Authoring a program

A program is a scope whose member triples are `(opcode, operand)` with `seq` as
the instruction address. A small helper makes this readable:

```python
from kb.query import KB, Triple
from kb.execute import run

def prog(scope, ops, source="manual"):
    """Author a program as an ordered microtheory: relation=opcode, object=operand."""
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]

# Simple interest: I = P * R * T
kb = KB(triples=prog("interest",
        [("LOAD", "P"), ("LOAD", "R"), ("MUL", None),
         ("LOAD", "T"), ("MUL", None), ("RET", None)]),
        alias_map={}, n_articles=0)

result = run(kb, "interest", {"P": 1000, "R": 0.05, "T": 3})
print(result.value)     # 150.0
print(result.steps)     # instructions executed
for line in result.trace:
    print(line)         # a cited "why" trace, one line per executed step
```

### The execution model

- A **stack machine.** Most opcodes pop operands off a shared operand stack and
  push a result. `LOAD`/`STORE` move between the stack and named **variables**
  (variables are *per call frame* — that is what makes recursion work).
- **`seq` is the address space.** The program counter starts at the lowest `seq`.
  `JMP a` / `JZ a` set it to the instruction whose `seq` is `a`. Authoring with
  contiguous `seq` 0..N-1 makes addresses obvious.
- **Inputs** are passed as a dict and seed the top-level frame's variables.
- The program ends at `RET` (or by running off the end); the **value** is the top
  of the stack, and any `EMIT`ted values are collected in `result.outputs`.

---

## 5. The complete opcode reference

The instruction set is **closed**: only these opcodes execute. Anything else is
refused *before* the program runs (no `eval`, no host/IO access). Stack effect is
written `before -- after` (top of stack on the right).

| opcode | operand | stack effect | meaning |
|--------|---------|--------------|---------|
| `PUSH c` | number | `-- c` | push the numeric constant `c` |
| `LOAD v` | var name | `-- x` | push the value of variable/input `v` |
| `STORE v` | var name | `x --` | pop and store into variable `v` |
| `ADD` | — | `a b -- a+b` | addition |
| `SUB` | — | `a b -- a-b` | subtraction |
| `MUL` | — | `a b -- a*b` | multiplication |
| `DIV` | — | `a b -- a/b` | division (by zero → `ExecError`) |
| `MOD` | — | `a b -- a%b` | remainder (by zero → `ExecError`) |
| `LT LE GT GE EQ NE` | — | `a b -- (1.0/0.0)` | comparisons; push `1.0` if true else `0.0` |
| `DUP` | — | `x -- x x` | duplicate the top |
| `POP` | — | `x --` | discard the top |
| `SWAP` | — | `a b -- b a` | exchange the top two |
| `JMP a` | address | `--` | jump to the instruction at `seq == a` |
| `JZ a` | address | `c --` | pop `c`; if `c == 0` jump to `a`, else fall through |
| `CALL scope` | scope name | `… -- …` | call another ordered microtheory as a subroutine |
| `RET` | — | `… -- …` | return to caller (or stop at top level); value = top of stack |
| `EMIT` | — | `x -- x` | append the top of stack to `result.outputs` (leaves it on the stack) |
| `FETCH s\|r` | `subject\|relation` | `-- x` | read fact `(s, r)` from this KB; push its object as a number (cited in `result.reads`) |
| `FETCH @v\|r` | `@var\|relation` | `-- x` | **parametric** subject: resolve the subject from local variable `v` (an entity id supplied as input), then fetch `(that subject, r)`. One rule, every entity — see §8b |

Values are numbers (`float`). This is deliberate (see §9, Honest scope). Subjects
passed in for parametric `FETCH @var|relation` are the one exception: a
non-numeric input is kept verbatim as an entity id (a subject, not a quantity).

---

## 6. Control flow, worked: branch + loop

`JZ`/`JMP` plus `seq`-addresses express any branch or loop. Here is the Python

```python
def sum_to_n(n):
    if n < 0:
        return 0
    total = 0
    i = 1
    while i <= n:
        total += i
        i += 1
    return total
```

as an ordered microtheory (addresses in comments; the back-edge `JMP 10` makes
the loop explicit):

```python
sumprog = [
    ("LOAD", "n"), ("PUSH", 0), ("LT", None), ("JZ", 6),       # 0-3  if n<0 goto 6
    ("PUSH", 0), ("RET", None),                                # 4-5  return 0
    ("PUSH", 0), ("STORE", "t"),                               # 6-7  t = 0
    ("PUSH", 1), ("STORE", "i"),                               # 8-9  i = 1
    ("LOAD", "i"), ("LOAD", "n"), ("LE", None), ("JZ", 23),    # 10-13 while i<=n else goto 23
    ("LOAD", "t"), ("LOAD", "i"), ("ADD", None), ("STORE", "t"),  # 14-17 t += i
    ("LOAD", "i"), ("PUSH", 1), ("ADD", None), ("STORE", "i"),    # 18-21 i += 1
    ("JMP", 10),                                               # 22  loop
    ("LOAD", "t"), ("RET", None),                              # 23-24 return t
]
```

`microtheory/replicate.py` runs the analogous GCD and grade-ladder programs and
asserts they match the Python **exactly** over thousands of inputs.

---

## 7. `CALL` — composition and recursion (microtheories calling microtheories)

`CALL scope` is the single most powerful opcode. It invokes **another ordered
microtheory** as a subroutine:

- the callee **shares the operand stack** — arguments are whatever is on the
  stack, the result is whatever it leaves there;
- the callee gets a **fresh local-variable frame** (so the same program can call
  itself recursively without clobbering its variables);
- when the callee hits `RET`, execution resumes in the caller right **after** the
  `CALL`.

This is microtheory **composition**: a procedure that, at some step, runs another
procedure. It is the concrete, working start of the **nested/inheriting
microtheory lattice** that [NOVELTIES](NOVELTIES.md) lists as an open hard
problem — procedures calling sub-procedures, all still inspectable triples.

### Composition

```python
# inc: arg on stack -> arg + 1
inc    = prog("inc",    [("STORE","a"), ("LOAD","a"), ("PUSH",1), ("ADD",None), ("RET",None)])
# sq_inc(x) = (x+1)^2, by CALLing inc then squaring with DUP/MUL
sq_inc = prog("sq_inc", [("LOAD","x"), ("CALL","inc"), ("DUP",None), ("MUL",None), ("RET",None)])
kb = KB(triples=inc + sq_inc, alias_map={}, n_articles=0)
run(kb, "sq_inc", {"x": 4}).value      # 25.0
```

### Recursion

```python
# factorial: arg on the stack; calls itself.
factprog = [
    ("STORE","n"),                                   # 0  n = arg
    ("LOAD","n"), ("PUSH",1), ("LE",None), ("JZ",8), # 1-4 if !(n<=1) goto 8
    ("PUSH",1), ("RET",None),                        # 5-6 base case: return 1
    ("PUSH",0),                                      # 7  pad (unreached)
    ("LOAD","n"),                                    # 8  push n
    ("LOAD","n"), ("PUSH",1), ("SUB",None),          # 9-11 push n-1
    ("CALL","fact"),                                 # 12 push fact(n-1)
    ("MUL",None), ("RET",None),                      # 13-14 return n*fact(n-1)
]
```

Recursion is bounded by `max_depth` (default 256): runaway recursion raises
`ExecError`, it does not blow the Python stack.

Worked: `microtheory/showcase.py` runs mutual recursion (`is_even`/`is_odd`),
recursive Fibonacci, and `lcm` composing `gcd` — each matched to Python; the
provenance-native capstone `microtheory/paradigm.py` composes a payment program.

---

## 8. `EMIT` — producing a sequence of outputs

Most programs return one value. Some need to produce a *list* — e.g. enumerate
steps, emit each row of a result, or **spit out an ordered set of instructions**
(the original motivating use case for ordered microtheories). `EMIT` appends the
top of the stack to `result.outputs` and leaves it in place:

```python
count = prog("count", [
    ("PUSH",1), ("STORE","i"),                              # i = 1
    ("LOAD","i"), ("LOAD","n"), ("LE",None), ("JZ",14),     # while i<=n
    ("LOAD","i"), ("EMIT",None), ("POP",None),              # emit i
    ("LOAD","i"), ("PUSH",1), ("ADD",None), ("STORE","i"),  # i += 1
    ("JMP",2),
    ("PUSH",0), ("RET",None),
])
run(KB(triples=count, alias_map={}, n_articles=0), "count", {"n": 5}).outputs
# [1.0, 2.0, 3.0, 4.0, 5.0]
```

Worked: `microtheory/showcase.py` uses `EMIT` for FizzBuzz (a code per number)
and for enumerating primes via a `CALL`ed `is_prime`.

---

## 8a. `FETCH` — the algorithm and the data in one store (no disconnect)

A fact is a plain triple; a program is an ordered microtheory; both live in the
**same** KB. `FETCH subject|relation` reads a fact straight out of that KB and
pushes its object as a number — so a program operates directly on the knowledge
base's own facts. There is no separate data layer, no ORM, no serialization
bridge, and the result's provenance spans **both** the program steps (`trace`)
and the facts it read (`reads`).

```python
data_and_program = [
    Triple("widget", "PRICE", "25", "catalogue", 0, None, None, 1.0),   # a plain fact
    Triple("widget", "QTY",   "4",  "stock",     0, None, None, 1.0),   # another plain fact
] + prog("line_total", [("FETCH","widget|PRICE"), ("FETCH","widget|QTY"),
                        ("MUL",None), ("RET",None)])
kb = KB(triples=data_and_program, alias_map={}, n_articles=0)
r = run(kb, "line_total", {})
r.value      # 100.0
r.reads      # ["widget PRICE 25 [catalogue]", "widget QTY 4 [stock]"]  — cited data
```

Three consequences, all in `microtheory/unified.py`:

1. **Compute over live facts.** The program carries no copy of the data; change a
   fact and rerun the same program — the answer updates, with no code change.
2. **One provenance model.** A computed number cites the facts it came from and
   the steps that produced it — end to end, in one trail.
3. **The loop closes.** A program's result can be asserted back as an ordinary
   fact, immediately queryable (`KB.out_facts`) and reason-over-able, and a
   downstream program can `FETCH` it. The three faculties — query, reason,
   execute — operate on one substrate.

This removes the data/algorithm seam that conventional stacks bridge with glue
code and lossy serialization.

## 8b. Parametric `FETCH` — one rule, every entity

`FETCH widget|PRICE` bakes the subject into the operand, tying the program to one
entity. Real business rules are generic: "a customer's loan offer is three times
their monthly income plus their balance" must run against *any* customer. The
parametric form `FETCH @var|relation` reads the subject from a local variable —
an entity id supplied as an input — so a **single** ordered microtheory serves a
whole population. Literal and parametric FETCHes mix freely in one rule: per-
entity facts (`@who|BALANCE`) alongside shared ones (`bank|INCOME_MULTIPLE`).

```python
LOAN_OFFER = [("FETCH","@who|MONTHLY_INCOME"), ("FETCH","bank|INCOME_MULTIPLE"),
              ("MUL",None), ("FETCH","@who|BALANCE"), ("ADD",None), ("RET",None)]
run(kb, "loan_offer", {"who": "c_alice"}).value   # 13500.0, cited to c_alice
run(kb, "loan_offer", {"who": "c_bob"}).value     #  7800.0 — SAME program, no rewrite
```

Two properties worth their own demonstration (`microtheory/parametric.py`):

1. **Cited to the resolved subject.** Each answer's `reads` name the concrete
   entity (`c_alice MONTHLY_INCOME 4000 [kyc_intake]`), never the placeholder
   `@who`. The parametric operand disappears into provenance.
2. **Self-describing dependencies.** A parametric operand is inspectable *data*,
   so the system can DECLARE — before running — exactly which facts the rule will
   read for a given entity (resolve `@who` over the rule's own FETCH triples), and
   that declared surface is provably equal to what execution reads. A rule's per-
   entity data dependencies are themselves knowledge.

An unset variable is a controlled refusal (`ExecError`), not a wrong answer — the
same safe-by-construction stance as an unknown opcode.

---

## 9. Safety, determinism, and termination (why this is trustworthy)

The executor keeps the same guarantees as the rest of SKEAR:

- **Closed instruction set.** `validate()` runs first and **refuses** any program
  containing an opcode outside `OPCODES`, or a unary opcode missing its operand.
  No instruction can do anything the opcode table doesn't define — there is no
  `eval`, no file/network/host access, no dynamic Python dispatch. A malicious
  `("SYSTEM_CALL", "rm -rf /")` step is rejected before step zero.
- **Determinism.** Same program + same inputs → same result. Always.
- **Auditability.** Every executed step is recorded in `result.trace` with the
  source of the instruction — a step-by-step "why" for the output.
- **Guaranteed termination.** `max_steps` bounds total work and `max_depth`
  bounds the call stack. A non-terminating loop or infinite recursion raises
  `ExecError` instead of hanging — the executor's analogue of the reasoner's
  fixpoint divergence guard.
- **Controlled faults.** Division/modulo by zero, stack underflow, undefined
  variables, and bad jump/call targets all raise `ExecError`, never an
  uncontrolled crash.

---

## 10. Replicating real code, and the efficiency story (honest)

`microtheory/replicate.py` replicates real Python functions **exactly** as ordered
microtheories (Euclid's GCD — a loop with `MOD`; a piecewise grade ladder — a
branch chain) and proves byte-for-byte behavioural equality over large input
sweeps. Then it measures the efficiency, **honestly**:

- It does **not** win on raw bytes for a single function — you pay once for the
  executor, and a rule's operands cost about the same either way. Plain code is
  smaller in the small. We say so.
- It **wins on bug-capable code**: once the executor exists, every new behaviour
  adds **zero** new lines of code — the behaviour is data. The executor is the
  only thing that can contain a bug, and it is fixed and self-tested.
- It **wins on information content at scale**: across a family of similar rules,
  the shared opcode structure compresses to ~0, so the per-rule compressed size
  keeps falling (measured with `zlib`) — only the differing operands carry
  information. This is [NOVELTY §2](NOVELTIES.md) (compact selectors) made
  concrete.
- And the rule stays **inspectable, diffable, cited, and reason-over-able** —
  none of which opaque code (or an LLM asked to "just compute it") gives you.

The takeaway: use ordered microtheories as a substitute for code where the logic
is a sequence of well-defined operations and you value inspectability,
versionability, auditability, and amortization across a rule-base — not as a
general-purpose programming language.

---

## 11. Honest scope (what this is NOT)

- **Numeric values only.** The stack holds numbers. Strings, collections, and a
  heap are deliberately out of scope for now; they would be a larger extension,
  not a "slight" one. (Human-readable *procedures* in §3 carry text freely — that
  is the `STEP` object; the *executor* in §4+ is numeric.)
- **First-order, finite-state-friendly.** It is a register/stack machine with
  jumps and calls — Turing-expressive given unbounded steps, but it is not a
  high-level language and is not meant to be one.
- **The win is operational, not magical.** See §10 — no claim of beating compiled
  code on speed or single-function size.
- **`CALL` is composition, not yet a full context lattice.** It gives subroutine
  composition over microtheories; full CYC-style inheritance/lifting between
  contexts remains future work (tracked in [NOVELTIES](NOVELTIES.md)).

---

## 12. Cheat sheet

```python
from kb.query import KB, Triple
from kb.execute import run, ExecError, OPCODES

# author: relation = opcode, object = operand, seq = address, scope = program name
def prog(scope, ops, source="manual"):
    return [Triple("p", op, ("" if a is None else str(a)), source, i, None, None, 1.0, scope, i)
            for i, (op, a) in enumerate(ops)]

kb = KB(triples=prog("myprog", [("LOAD","x"), ("DUP",None), ("MUL",None), ("RET",None)]),
        alias_map={}, n_articles=0)

r = run(kb, "myprog", inputs={"x": 7}, max_steps=100_000, max_depth=256)
r.value      # 49.0  (top of stack at RET)
r.outputs    # []    (values from EMIT)
r.steps      # instructions executed
r.trace      # cited per-step log

# reading procedures (human steps)
kb.ordered_scope("myprog")            # the scope's steps, in seq order
kb.in_scope("myprog", ordered=True)   # steps + globals, ordered
kb.scopes()                           # all microtheories present
```

Run the worked examples (`from src/`): `python -m microtheory.procedure`,
`… .program`, `… .replicate`, `… .showcase`, `… .unified`, `… .complexity`,
`… .paradigm`, `… .fraud`, `python -m kb.execute`, `python -m kb.transpile`.
