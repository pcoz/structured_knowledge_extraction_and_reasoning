"""Unit test for the Triple.scope (flat microtheory) feature.

Assert-based, runnable directly (matching the repo's stress-test style):
    python -m microtheory.test_scope     # from src/
Exits non-zero on any failure.
"""
from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path

from kb.query import KB, Triple
from kb.ontology import Ontology
from kb.conflict import (apply_with_conflict_resolution, ChainPolicy,
                         AuthorityWinsPolicy, LatestWinsPolicy,
                         HighestConfidencePolicy)

ONTO = Ontology(functional_properties={"IS_A"})
POLICY = ChainPolicy([AuthorityWinsPolicy(), LatestWinsPolicy(),
                      HighestConfidencePolicy()])


def _conflicts(triples):
    kb = KB(triples=triples, alias_map={}, n_articles=0)
    _, _, c, _ = apply_with_conflict_resolution(kb, ontology=ONTO, policy=POLICY)
    return c


def run() -> int:
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            fails += 1

    # 1. schema + backward-compatible construction
    check("query.Triple exposes 'scope'", "scope" in {f.name for f in fields(Triple)})
    check("extract.Triple exposes 'scope'",
          __import__("kb.extract", fromlist=["Triple"]).Triple.__dataclass_fields__.get("scope") is not None)
    v1 = Triple("a", "R", "b", "src", 0)          # legacy 5-arg positional
    check("v1 positional construction works; scope defaults None", v1.scope is None)

    # 2. different non-global scopes do NOT conflict
    diff = [Triple("x", "IS_A", "p", "a", 0, None, None, 1.0, "mtA"),
            Triple("x", "IS_A", "q", "b", 0, None, None, 1.0, "mtB")]
    check("two different microtheories -> 0 conflicts", len(_conflicts(diff)) == 0)

    # 3. same scope still conflicts
    same = [Triple("x", "IS_A", "p", "a", 0, None, None, 1.0, "mtA"),
            Triple("x", "IS_A", "q", "b", 0, None, None, 1.0, "mtA")]
    check("same microtheory, two values -> conflict", len(_conflicts(same)) == 1)

    # 4. global (None) conflicts with anything (holds everywhere)
    glob = [Triple("x", "IS_A", "p", "a", 0, None, None, 1.0, None),
            Triple("x", "IS_A", "q", "b", 0, None, None, 1.0, "mtB")]
    check("global vs scoped -> conflict", len(_conflicts(glob)) == 1)

    # 5. in_scope returns scoped + global; scopes() lists microtheories
    kb = KB(triples=[Triple("x", "R", "1", "s", 0, None, None, 1.0, "A"),
                     Triple("x", "R", "2", "s", 0, None, None, 1.0, "B"),
                     Triple("x", "R", "g", "s", 0, None, None, 1.0, None)],
            alias_map={}, n_articles=0)
    inA = kb.in_scope("A")
    check("in_scope('A') = scoped-A + global", {t.object for t in inA} == {"1", "g"})
    check("in_scope(None) = only globals", {t.object for t in kb.in_scope(None)} == {"g"})
    check("scopes() = {A, B}", kb.scopes() == {"A", "B"})

    # 5b. ordered microtheory (a procedure): seq gives intrinsic step order
    check("query.Triple exposes 'seq'", "seq" in {f.name for f in fields(Triple)})
    check("extract.Triple exposes 'seq'",
          __import__("kb.extract", fromlist=["Triple"]).Triple.__dataclass_fields__.get("seq") is not None)
    check("v1 positional construction works; seq defaults None", v1.seq is None)
    # steps deliberately added out of order; seq is the truth, not input order
    proc = KB(triples=[
        Triple("brew", "STEP", "pour water",  "manual", 3, None, None, 1.0, "brew", 2),
        Triple("brew", "STEP", "boil kettle", "manual", 1, None, None, 1.0, "brew", 0),
        Triple("brew", "STEP", "add teabag",  "manual", 2, None, None, 1.0, "brew", 1),
        Triple("brew", "APPLIES_WHEN", "you want tea", "manual", 0, None, None, 1.0, "brew"),  # seq=None
        Triple("global_note", "R", "g", "s", 0, None, None, 1.0, None),                        # global
    ], alias_map={}, n_articles=0)
    steps = [t.object for t in proc.ordered_scope("brew") if t.relation == "STEP"]
    check("ordered_scope yields steps in seq order, not input order",
          steps == ["boil kettle", "add teabag", "pour water"])
    inb = proc.in_scope("brew", ordered=True)
    check("in_scope(ordered) puts seq-tagged members before unordered ones",
          [t for t in inb if t.seq is not None][0].seq == 0
          and all(t.seq is None for t in inb[3:]))
    check("ordered_scope excludes globals", all(t.scope == "brew" for t in proc.ordered_scope("brew")))
    check("ordered=False preserves the v1 set semantics (unchanged order)",
          [t.object for t in proc.in_scope("brew")] ==
          [t.object for t in proc.triples if t.scope == "brew" or t.scope is None])

    # 6. backward-compatible JSON load (existing KB has no 'scope' key)
    kb_json = Path(__file__).resolve().parents[1] / "kb" / "kb_1000_articles.json"
    if kb_json.exists():
        loaded = KB.load(kb_json)
        check("existing JSON KB loads; all scope=None",
              len(loaded.triples) > 0 and all(t.scope is None for t in loaded.triples))

    print("ALL PASS" if fails == 0 else f"{fails} FAILED")
    return fails


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
