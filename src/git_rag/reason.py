"""Apply the kb.reason engine to the Git knowledge base.

Same fixpoint + disjunctive-rule + stratified-negation engine as the
Wikipedia KB (`src/kb/reason.py`), applied here to the structured Git
docs corpus. Builds a graph from the KnowledgeItem fields and derives:

  - Transitive closure of RELATED_TO (fixpoint), so a developer asking
    about commit-undo can be routed to merge-conflict resolution
    several hops away.
  - NEEDS_OPERATOR_ATTENTION ← HAS_CAUTION ∪ USES_DESTRUCTIVE_COMMAND
    (DisjunctiveRule — two channels indicating the operation isn't safe
    to run blindly).
  - RECOVERY_OPERATION classification (function-form disjunction over
    subtopic values).
  - SAFE_TO_AUTOMATE ← has commands ∧ NOT NEEDS_OPERATOR_ATTENTION
    (negation-as-failure over the derived disjunctive classification —
    requires stratified semantics to be well-defined).
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Same dual sys.path insert as src/ahab/reason.py so this script
# can be invoked from either the repo root or src/ directly, and
# can import both its sibling `knowledge` module and the parent
# `kb` package.
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parent))

from knowledge import GIT_KB, KnowledgeItem, by_id
from kb.query import KB, Triple
from kb.reason import (
    Rule, DisjunctiveRule, Derivation, kb_has,
    apply_all_rules_to_fixpoint,
)


# ----------------------------------------------------------------------
# Build a KB from KnowledgeItem records.
# ----------------------------------------------------------------------

# Substrings that, when found in a command line, mark the operation as
# destructive (history-rewriting or unrecoverable). Substring match
# rather than token match because some appear inside larger flags
# (e.g., "reset --hard" embedded in a longer command line). Order
# matters only for the "first match wins" short-circuit below.
DESTRUCTIVE_KEYWORDS = (
    "--force", "--hard", "filter-branch", "reset --hard",
    "push --force", "rm -rf",
)


def build_git_kb(items: list[KnowledgeItem]) -> KB:
    # Project each KnowledgeItem into 4-8 triples. Topic/subtopic/
    # intent are the matching keys for query.py; HAS_COMMANDS,
    # HAS_CAUTION, USES_DESTRUCTIVE_COMMAND are the operational flags
    # that the reasoning rules consume; RELATED_TO carries the graph
    # edges that the fixpoint rule will close transitively.
    triples: list[Triple] = []
    for item in items:
        triples.append(Triple(item.item_id, "HAS_TOPIC",
                              item.topic, "git-docs", 0))
        triples.append(Triple(item.item_id, "HAS_SUBTOPIC",
                              item.subtopic, "git-docs", 0))
        triples.append(Triple(item.item_id, "HAS_INTENT",
                              item.intent, "git-docs", 0))
        if item.commands:
            triples.append(Triple(item.item_id, "HAS_COMMANDS",
                                  "yes", "git-docs", 0))
            # Scan all commands as a single lowercased string. Emit at
            # most one USES_DESTRUCTIVE_COMMAND per item — the first
            # match is enough to flag the whole item for operator
            # attention via the disjunctive rule downstream.
            joined = " ".join(item.commands).lower()
            for kw in DESTRUCTIVE_KEYWORDS:
                if kw in joined:
                    triples.append(Triple(
                        item.item_id, "USES_DESTRUCTIVE_COMMAND",
                        kw, "git-docs", 0,
                    ))
                    break
        if item.cautions:
            triples.append(Triple(item.item_id, "HAS_CAUTION",
                                  "yes", "git-docs", 0))
        for rel in item.related_items:
            triples.append(Triple(item.item_id, "RELATED_TO",
                                  rel, "git-docs", 0))
    return KB(triples=triples, alias_map={}, n_articles=len(items))


# ----------------------------------------------------------------------
# Rules.
# ----------------------------------------------------------------------


def r_transitive_related(kb: KB) -> list[Derivation]:
    """Transitive closure of RELATED_TO → REACHABLE_FROM.

    Base case lifts RELATED_TO into REACHABLE_FROM; the inductive step
    extends with one more hop. Fixpoint closes arbitrarily long
    navigation chains."""
    out: list[Derivation] = []
    for t in kb.triples:
        if t.relation == "RELATED_TO":
            derived = Triple(
                t.subject, "REACHABLE_FROM", t.object, "(derived)", -1,
            )
            expl = (
                f"{t.subject} directly relates to {t.object}, so is "
                f"reachable from it."
            )
            out.append(Derivation("r_transitive_related", derived,
                                   [t], expl))
    for t1 in kb.triples:
        if t1.relation != "REACHABLE_FROM":
            continue
        for t2 in kb.out_facts(t1.object, "RELATED_TO"):
            if t2.object == t1.subject:
                continue
            derived = Triple(
                t1.subject, "REACHABLE_FROM", t2.object, "(derived)", -1,
            )
            expl = (
                f"{t1.subject} reaches {t1.object}, and {t1.object} "
                f"relates to {t2.object}; therefore {t1.subject} is "
                f"reachable from {t2.object}."
            )
            out.append(Derivation("r_transitive_related", derived,
                                   [t1, t2], expl))
    return out


# Disjunctive rule: an item needs operator attention if it carries
# either an explicit caution OR a destructive command. Alternative
# antecedent relations, one consequent.
R_NEEDS_CARE = DisjunctiveRule(
    name="r_needs_care",
    alternatives=["HAS_CAUTION", "USES_DESTRUCTIVE_COMMAND"],
    consequent="NEEDS_OPERATOR_ATTENTION",
    explanation_template=(
        "Item {subject} flagged for operator attention via {via}."
    ),
)


def r_recovery_operation(kb: KB) -> list[Derivation]:
    """subtopic ∈ {undo, recover, revert} → RECOVERY_OPERATION.

    Function-form disjunction over object values."""
    recovery_subs = {"undo", "recover", "revert"}
    out: list[Derivation] = []
    for t in kb.triples:
        if t.relation != "HAS_SUBTOPIC" or t.object not in recovery_subs:
            continue
        derived = Triple(
            t.subject, "IS", "RECOVERY_OPERATION", "(derived)", -1,
        )
        expl = (
            f"Item {t.subject} has subtopic '{t.object}' — a recovery "
            f"operation."
        )
        out.append(Derivation("r_recovery_operation", derived, [t], expl))
    return out


def r_safe_to_automate(kb: KB) -> list[Derivation]:
    """Item is SAFE_TO_AUTOMATE if it has commands AND no
    NEEDS_OPERATOR_ATTENTION flag (the derived flag from R_NEEDS_CARE).

    Negation-as-failure over a derived predicate: stratum 1 so the
    disjunctive R_NEEDS_CARE has already converged before this rule
    inspects its absence."""
    out: list[Derivation] = []
    for t in kb.triples:
        if t.relation != "HAS_COMMANDS":
            continue
        if kb_has(kb, t.subject, "NEEDS_OPERATOR_ATTENTION"):
            continue
        derived = Triple(
            t.subject, "IS", "SAFE_TO_AUTOMATE", "(derived)", -1,
        )
        expl = (
            f"Item {t.subject} has runnable commands and no caution "
            f"or destructive-command flag (closed-world over derived "
            f"classifications)."
        )
        out.append(Derivation("r_safe_to_automate", derived, [t], expl))
    return out


RULES = [
    Rule("r_transitive_related",  r_transitive_related),
    Rule("r_recovery_operation",  r_recovery_operation),
    R_NEEDS_CARE.to_rule(),
    Rule("r_safe_to_automate",    r_safe_to_automate,  stratum=1),
]


# ----------------------------------------------------------------------
# Demo.
# ----------------------------------------------------------------------


def main() -> None:
    print("=" * 78)
    print("Git RAG — structured reasoning over the knowledge base")
    print("=" * 78)
    print()
    print("Same engine as src/kb/reason.py. Different data: structured")
    print("Git docs (37 items, with related_items, commands, cautions,")
    print("intent, topic, subtopic). Derives multi-hop navigation,")
    print("operator-attention flags, and an automation-safety classifier.")
    print()

    kb = build_git_kb(GIT_KB)
    n_items = len({t.subject for t in kb.triples if t.relation == "HAS_TOPIC"})
    print(f"  Built KB: {len(kb.triples):,} base triples from "
          f"{n_items} items.")
    print()

    kb_ext, derivations, stats = apply_all_rules_to_fixpoint(kb, rules=RULES)
    print("FIXPOINT CONVERGENCE")
    print("-" * 78)
    print(f"  Stratum 0 iterations:  {stats['stratum_0_iters']} "
          f"(per-iter new facts: {stats['stratum_0_per_iter']})")
    print(f"  Stratum 1 derivations: {stats['stratum_1_count']}")
    print(f"  Total triples:         {len(kb_ext.triples):,}")
    print()

    by_rule: dict[str, int] = defaultdict(int)
    for d in derivations:
        by_rule[d.rule_name] += 1
    print("DERIVATIONS BY RULE")
    print("-" * 78)
    for rule_name, n in by_rule.items():
        print(f"  {rule_name:<32s} {n:>5d}")
    print()

    # --- Fixpoint: multi-hop navigation. ---
    print("FIXPOINT: TRANSITIVE NAVIGATION (REACHABLE_FROM)")
    print("-" * 78)
    seeds = ["commit.undo_last_unpushed", "branch.delete_local",
             "merge.handle_conflict"]
    for seed in seeds:
        direct = sorted({
            t.object for t in kb_ext.out_facts(seed, "RELATED_TO")
        })
        reach = sorted({
            t.object for t in kb_ext.out_facts(seed, "REACHABLE_FROM")
        })
        print(f"  {seed}:")
        print(f"    directly related to {len(direct)} item(s): {direct}")
        if len(reach) > len(direct):
            new_hops = sorted(set(reach) - set(direct))
            print(f"    reachable via fixpoint ({len(reach)} total): "
                  f"+{new_hops}")
    print()

    # --- Disjunctive rule (alternative relations). ---
    print("DISJUNCTIVE RULE: NEEDS_OPERATOR_ATTENTION")
    print("-" * 78)
    print("  (HAS_CAUTION ∪ USES_DESTRUCTIVE_COMMAND → "
          "NEEDS_OPERATOR_ATTENTION)")
    flagged = sorted({
        t.subject for t in kb_ext.triples
        if t.relation == "NEEDS_OPERATOR_ATTENTION"
    })
    print(f"  Items flagged: {len(flagged)}")
    for item_id in flagged[:8]:
        reasons = []
        if kb_has(kb_ext, item_id, "HAS_CAUTION"):
            reasons.append("has-caution")
        for rel, obj, _ in kb_ext.out_edges.get(item_id, []):
            if rel == "USES_DESTRUCTIVE_COMMAND":
                reasons.append(f"destructive-cmd:{obj}")
                break
        print(f"    → {item_id}  [{', '.join(reasons)}]")
    if len(flagged) > 8:
        print(f"    ... + {len(flagged) - 8} more")
    print()

    # --- Function-form disjunction over object values. ---
    print("CLASSIFICATION: RECOVERY_OPERATION "
          "(subtopic ∈ {undo, recover, revert})")
    print("-" * 78)
    recovery = sorted({
        t.subject for t in kb_ext.triples
        if t.relation == "IS" and t.object == "RECOVERY_OPERATION"
    })
    for item_id in recovery:
        item = by_id(item_id)
        sub = item.subtopic if item else "?"
        print(f"  → {item_id}  (subtopic: {sub})")
    print()

    # --- Negation-as-failure over a derived predicate. ---
    print("NEGATION-AS-FAILURE: SAFE_TO_AUTOMATE")
    print("-" * 78)
    print("  (has commands AND not NEEDS_OPERATOR_ATTENTION — negation")
    print("   over the derived disjunctive classification; stratum 1)")
    safe = sorted({
        t.subject for t in kb_ext.triples
        if t.relation == "IS" and t.object == "SAFE_TO_AUTOMATE"
    })
    print(f"  Safe items: {len(safe)}")
    for item_id in safe[:10]:
        item = by_id(item_id)
        topic = item.topic if item else "?"
        print(f"    → {item_id}  (topic: {topic})")
    if len(safe) > 10:
        print(f"    ... + {len(safe) - 10} more")
    print()

    # --- Cross-cutting query that combines fixpoint + classification. ---
    print("COMPOUND QUERY: recovery operations reachable from "
          "commit.undo_last_unpushed")
    print("-" * 78)
    reach_from_undo = {
        t.object
        for t in kb_ext.out_facts("commit.undo_last_unpushed", "REACHABLE_FROM")
    }
    recovery_set = set(recovery)
    answer = sorted(reach_from_undo & recovery_set)
    if answer:
        for item_id in answer:
            print(f"  → {item_id}")
    else:
        print(f"  (none — fixpoint reach × recovery classification = empty)")
    print()

    # --- "Why?" trace. ---
    print("\"WHY?\" TRACE FOR A DERIVED FACT")
    print("-" * 78)
    # Pick a non-trivial REACHABLE_FROM derivation.
    direct_pairs = {
        (t.subject, t.object) for t in kb_ext.triples
        if t.relation == "RELATED_TO"
    }
    target = None
    for t in kb_ext.triples:
        if t.relation != "REACHABLE_FROM":
            continue
        if (t.subject, t.object) in direct_pairs:
            continue
        target = (t.subject, t.relation, t.object)
        break
    if target is not None:
        trace = [d for d in derivations
                 if (d.output.subject, d.output.relation, d.output.object) == target]
        d = trace[0]
        print(f"  Q: Why is {target[0]} reachable from {target[2]}?")
        print(f"  Rule:        {d.rule_name}")
        for inp in d.inputs:
            print(f"  Input:       {inp.subject} --{inp.relation}--> {inp.object}")
        print(f"  Explanation: {d.explanation}")
    else:
        print("  (every REACHABLE_FROM is also a direct RELATED_TO — "
              "transitive closure didn't extend the graph)")
    print()

    print("=" * 78)
    print("Same engine, different domain. Audit trail per derivation,")
    print("zero AI calls at query time, sub-millisecond per fact.")
    print("=" * 78)
    print()


if __name__ == "__main__":
    main()
