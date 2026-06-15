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
