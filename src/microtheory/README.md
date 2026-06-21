# SKEAR — Worked Examples (microtheories)

Nineteen runnable worked examples, each demonstrating one SKEAR capability on cited
data. Run any from `src/` with `python -m microtheory.<name>` (it prints a worked
walk-through and self-checks). The canonical, fuller write-up of the executor and
every opcode is [`docs/ORDERED_MICROTHEORIES.md`](../../docs/ORDERED_MICROTHEORIES.md);
this is the quick index.

## Foundations — framing, procedures, programs

| # | Example | Shows |
|---|---|---|
| 1 | `analyse` | flat **framing scopes**: one subject under several incompatible framings, each coherent + sourced; scope-aware conflict detection |
| 2 | `breakage` | how **overlapping** microtheories break knowledge — and why scoping fixes it |
| 3 | `procedure` | a microtheory as an ordered **procedure** (steps as data) |
| 4 | `program` | a microtheory as an executable **program** (opcodes as data) |
| 5 | `replicate` | the executor **replicates real Python** exactly (verified equivalence) |
| 6 | `showcase` | the expanded opcodes: recursion, mutual recursion, composition, `EMIT` |
| 7 | `unified` | **no disconnect** — the algorithm lives *with* the data in one KB |
| 8 | `complexity` | a **polynomial speedup** (O(M²)→O(M)) from the derived index |

## Capabilities — the closed instruction set

| # | Example | Shows |
|---|---|---|
| 9 | `paradigm` | capstone: **query + reason + execute** on one KB |
| 10 | `fraud` | end-to-end **fraud detection** as cited microtheories |
| 11 | `parametric` | **one rule, every entity** — parametric `FETCH @var\|relation` |
| 12 | `bitwise` | **masks / flags / sets** — `AND OR XOR NOT SHL SHR` over cited facts |
| 13 | `decision_engine` | capstone: a clinical prescribing **decision engine** using all faculties |
| 14 | `higher_order` | **`MAP` / `FILTER` / `FOLD`** over a cited series (reduce/map/filter) |
| 15 | `lending_engine` | capstone: a **lending engine** incl. higher-order ops |

## Systems, dispatch, and decisioning

| # | Example | Shows |
|---|---|---|
| 16 | `architecture` | model a system with **`OPAQUE`** black boxes, then open them one by one (recursive refinement) |
| 17 | `distributed_architecture` | a platform's **architecture as queryable cited knowledge** (trust boundary, blast radius, PII-to-black-box, side-effect reach) |
| 18 | `dispatch` | **`DISPATCH`** — the computation chosen by a cited fact (vtable / opcode table / state machine) |
| 19 | `decisioning` | capstone: **five interacting decision systems** that resolve themselves — no business branch in the orchestrator |

*(`corpus.py` and `test_scope.py` are test fixtures, not worked examples.)*

## Run them all
```
cd src
for m in analyse breakage procedure program replicate showcase unified complexity \
         paradigm fraud parametric bitwise decision_engine higher_order lending_engine \
         architecture distributed_architecture dispatch decisioning; do
  python -m microtheory.$m >/dev/null && echo "PASS $m" || echo "FAIL $m"
done
```

See also: [`README.md`](../../README.md) · [`docs/ORDERED_MICROTHEORIES.md`](../../docs/ORDERED_MICROTHEORIES.md)
· [`docs/DEVELOPER_GUIDE.md`](../../docs/DEVELOPER_GUIDE.md) · [`RELEASE_NOTES.md`](../../RELEASE_NOTES.md).
