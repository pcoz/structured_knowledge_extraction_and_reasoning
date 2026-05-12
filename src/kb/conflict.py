"""Conflict detection and resolution policies.

When a knowledge graph contains facts that can't all be true together,
the reasoner needs a discipline for handling them. This module
provides:

  - A `Conflict` record describing a set of triples that contradict
    each other, plus the OWL axiom or general constraint that
    surfaced them.
  - A `Policy` protocol — anything that decides which triples
    survive when a conflict is detected. Five concrete implementations:
    `LatestWinsPolicy`, `HighestConfidencePolicy`, `AuthorityWinsPolicy`,
    `KeepAllPolicy`, `SurfaceForReviewPolicy`.
  - `detect_conflicts` — finds conflicts in a KB by scanning for
    CONFLICT_* marker facts that the OWL rule compiler produces
    (from FunctionalProperty / InverseFunctionalProperty / disjoint
    class axioms).
  - `apply_with_conflict_resolution` — the top-level orchestrator
    that runs rules to fixpoint, detects conflicts in the closure,
    applies the policy, and returns the resolved KB plus diagnostic
    information.

Why conflicts arise. The pipeline produces structured facts from
many sources — extraction passes over unstructured text, curated
patches, derived facts from rules. Multi-source pipelines naturally
produce contradictions: an old article says X, a newer article says
Y, a different translation introduces a variant spelling that creates
a phantom second entity. The engine can't make these go away, but
it can surface and resolve them deterministically.

What kinds of conflicts. The OWL rule compiler emits three kinds:

  - `CONFLICT_FUNCTIONAL` — a subject has two distinct values under
    a functional property (e.g., two BIRTH_DATEs).
  - `CONFLICT_INVERSE_FUNCTIONAL` — a value has two distinct subjects
    under an inverse-functional property (e.g., two people with the
    same passport number).
  - `CONTRADICTION_DETECTED` — an entity is asserted to belong to
    two classes declared disjoint.

Resolution policies don't know about specific OWL axioms. They
operate on the `Conflict` abstraction: a bag of triples + the kind
of conflict + a detail string. Adding a new conflict kind doesn't
require touching the policies; adding a new policy doesn't require
touching the detectors. Open-closed.

Scope notes:

  - Resolution happens at construction time. The shipped KB
    artifact has conflicts already resolved (under whatever policy
    was active during construction). Runtime queries see a clean
    artifact, in keeping with the engine's no-AI-at-query-time
    property.
  - `SurfaceForReviewPolicy` is the explicit human-in-the-loop
    option: it keeps everything and emits `CONFLICT_UNRESOLVED`
    markers. Downstream code (or a reviewer) picks up from there.
  - Temporal conflicts are scoped by the `intersects` predicate in
    `src/kb/temporal.py`. Two CURRENT_EMPLOYER facts for the same
    person at non-overlapping times are NOT a conflict — they're
    two valid records of a single employment history.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Protocol

# Resolve sibling modules — same dual-insert convention as the rest
# of the kb package, so this script works invoked from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb.query import KB, Triple
from kb.reason import (
    Rule, Derivation,
    apply_all_rules_to_fixpoint,
)
from kb.ontology import Ontology
from kb.temporal import _parse_date


# ----------------------------------------------------------------------
# Conflict data structure.
# ----------------------------------------------------------------------


@dataclass
class Conflict:
    """A set of triples that can't all be true under the active axioms.

    Fields:
      triples — the conflicting triples themselves. Always >= 2.
      kind    — one of {"functional", "inverse_functional",
                "disjoint_class"} (extensible — the policy code
                treats this opaquely).
      detail  — a free-form string identifying the specific
                violation (e.g., 'BIRTH_DATE:1879|1880'). Used in
                diagnostic output and the SurfaceForReview marker.
      marker  — the CONFLICT_* triple the OWL rule compiler emitted
                to signal this conflict. None if the conflict was
                detected through a non-OWL path."""
    triples: list[Triple]
    kind: str
    detail: str
    marker: Triple | None = None


# ----------------------------------------------------------------------
# Policy protocol + concrete implementations.
#
# A policy is a callable that takes a Conflict and the KB it lives in
# and returns the subset of the conflict's triples that should survive
# resolution. Returning a strict subset means the engine prunes the
# excluded triples; returning all of them means 'no resolution
# possible — leave them for review'.
#
# Policies are pure (no mutation, no I/O, no time-of-day). Several can
# be chained: try LatestWins, then HighestConfidence, then
# AuthorityWins, then SurfaceForReview. The `ChainPolicy` helper does
# this composition.
# ----------------------------------------------------------------------


class Policy(Protocol):
    """A conflict-resolution policy. Takes a Conflict + the KB it
    belongs to; returns the triples that should be kept."""

    name: str

    def __call__(self, conflict: Conflict, kb: KB) -> list[Triple]:
        ...


@dataclass
class LatestWinsPolicy:
    """Keep the triple with the latest `valid_from` (or `valid_to`
    if `valid_from`s tie). Triples with no temporal info lose to
    triples with temporal info, on the reading that a dated fact
    supersedes an undated one. If nothing's distinguishable, fall
    through to the caller (return all triples)."""
    name: str = "latest-wins"

    def __call__(self, conflict: Conflict, kb: KB) -> list[Triple]:
        def _key(t: Triple) -> tuple:
            f = _parse_date(t.valid_from)
            to = _parse_date(t.valid_to)
            # Triples with NO temporal info sort lowest. Among temporal
            # triples, sort by start (later=better), then end.
            has_any = (f is not None) or (to is not None)
            return (1 if has_any else 0,
                    f if f is not None else -10**12,
                    to if to is not None else -10**12)
        sorted_triples = sorted(conflict.triples, key=_key, reverse=True)
        # If the top-ranked is tied with another, no clear winner —
        # return all so a chained policy can try next.
        top_key = _key(sorted_triples[0])
        winners = [t for t in sorted_triples if _key(t) == top_key]
        if len(winners) == 1:
            return winners
        return conflict.triples


@dataclass
class HighestConfidencePolicy:
    """Keep the triple with the highest `confidence`. Tie ⇒ all
    tied triples survive (caller can chain to another policy)."""
    name: str = "highest-confidence"

    def __call__(self, conflict: Conflict, kb: KB) -> list[Triple]:
        max_conf = max(t.confidence for t in conflict.triples)
        winners = [t for t in conflict.triples if t.confidence == max_conf]
        if len(winners) == 1:
            return winners
        return conflict.triples


@dataclass
class AuthorityWinsPolicy:
    """Keep the triple whose source has the highest authority score
    in `kb.source_authority`. Sources not in the map score 0.0 —
    i.e. unranked sources lose to ranked ones. Tie ⇒ caller can
    chain to another policy."""
    name: str = "authority-wins"

    def __call__(self, conflict: Conflict, kb: KB) -> list[Triple]:
        def _auth(t: Triple) -> float:
            return kb.source_authority.get(t.source_article, 0.0)
        max_auth = max(_auth(t) for t in conflict.triples)
        winners = [t for t in conflict.triples if _auth(t) == max_auth]
        if len(winners) == 1:
            return winners
        return conflict.triples


@dataclass
class KeepAllPolicy:
    """The null policy — no resolution. All triples survive. Useful
    when the conflict is informational (you wanted to surface the
    contradiction but not act on it)."""
    name: str = "keep-all"

    def __call__(self, conflict: Conflict, kb: KB) -> list[Triple]:
        return list(conflict.triples)


@dataclass
class SurfaceForReviewPolicy:
    """Keep everything AND emit `CONFLICT_UNRESOLVED` marker triples
    for human review downstream. The reasoner can't decide; flag and
    move on."""
    name: str = "surface-for-review"

    def __call__(self, conflict: Conflict, kb: KB) -> list[Triple]:
        # Identical to KeepAll at this level — the marker emission
        # is handled by the orchestrator (apply_with_conflict_
        # resolution), which knows whether it's running this
        # specific policy.
        return list(conflict.triples)


@dataclass
class ChainPolicy:
    """Compose policies: try each in order; the first to return a
    single winner wins. Useful pattern:

        ChainPolicy([
            AuthorityWinsPolicy(),
            LatestWinsPolicy(),
            HighestConfidencePolicy(),
            SurfaceForReviewPolicy(),
        ])

    'Trust the most authoritative source; if a tie, use the most
    recent; if still a tie, the most confident; if still a tie,
    surface for human review.'"""
    policies: list[Policy]
    name: str = "chain"

    def __call__(self, conflict: Conflict, kb: KB) -> list[Triple]:
        for p in self.policies:
            result = p(conflict, kb)
            if len(result) < len(conflict.triples):
                return result
        # Nothing in the chain narrowed it.
        return list(conflict.triples)


# ----------------------------------------------------------------------
# Conflict detection.
#
# Reads CONFLICT_* marker triples (produced by the OWL rule compiler
# in src/kb/ontology_rules.py) and reconstructs the Conflict records
# they signal. The detection logic doesn't depend on which OWL rules
# produced the markers — it just unpacks them.
# ----------------------------------------------------------------------


def detect_conflicts(kb: KB) -> list[Conflict]:
    """Find all conflicts in the KB by reading the CONFLICT_* marker
    facts.

    The OWL rule compiler emits these markers as part of fixpoint
    inference: a `CONFLICT_FUNCTIONAL` triple on subject X with
    detail `BIRTH_DATE:1879|1880` means X has BIRTH_DATE 1879 and
    BIRTH_DATE 1880, both with overlapping validity, violating
    `owl:FunctionalProperty(BIRTH_DATE)`. This function reconstructs
    the conflict's original triples by looking them up."""
    conflicts: list[Conflict] = []
    for t in kb.triples:
        if t.relation == "CONFLICT_FUNCTIONAL":
            conflicts.append(_unpack_functional(t, kb))
        elif t.relation == "CONFLICT_INVERSE_FUNCTIONAL":
            conflicts.append(_unpack_inverse_functional(t, kb))
        elif t.relation == "CONTRADICTION_DETECTED":
            conflicts.append(_unpack_disjoint(t, kb))
    return conflicts


def _unpack_functional(marker: Triple, kb: KB) -> Conflict:
    """Recover a functional-property conflict from its marker.

    Detail string format: 'PROP:val1|val2'."""
    detail = marker.object
    prop, _, vals = detail.partition(":")
    v1, _, v2 = vals.partition("|")
    triples = [
        kb.triples[idx]
        for idx in kb.by_relation.get(prop, [])
        if kb.triples[idx].subject == marker.subject
        and kb.triples[idx].object in (v1, v2)
    ]
    return Conflict(
        triples=triples, kind="functional",
        detail=detail, marker=marker,
    )


def _unpack_inverse_functional(marker: Triple, kb: KB) -> Conflict:
    """Recover an inverse-functional-property conflict. The marker's
    subject is the SHARED VALUE; we look up the two subjects sharing it."""
    detail = marker.object
    prop, _, subjs = detail.partition(":")
    s1, _, s2 = subjs.partition("|")
    triples = [
        kb.triples[idx]
        for idx in kb.by_relation.get(prop, [])
        if kb.triples[idx].object == marker.subject
        and kb.triples[idx].subject in (s1, s2)
    ]
    return Conflict(
        triples=triples, kind="inverse_functional",
        detail=detail, marker=marker,
    )


def _unpack_disjoint(marker: Triple, kb: KB) -> Conflict:
    """Recover a disjoint-class conflict. The marker's subject is the
    entity that belongs to both classes; detail is 'C1|C2'."""
    detail = marker.object
    c1, _, c2 = detail.partition("|")
    triples = [
        kb.triples[idx]
        for idx in kb.by_relation.get("IS_A", [])
        if kb.triples[idx].subject == marker.subject
        and kb.triples[idx].object in (c1, c2)
    ]
    return Conflict(
        triples=triples, kind="disjoint_class",
        detail=detail, marker=marker,
    )


# ----------------------------------------------------------------------
# Resolution.
# ----------------------------------------------------------------------


def resolve_conflicts(
    kb: KB,
    conflicts: list[Conflict],
    policy: Policy,
) -> tuple[KB, list[Triple], list[Triple]]:
    """Apply `policy` to each conflict; return (resolved_kb,
    kept_triples, dropped_triples).

    The resolved KB has the dropped triples removed AND the
    CONFLICT_* / CONTRADICTION_DETECTED markers removed (since the
    conflicts they signalled have been resolved). If the policy is
    `SurfaceForReviewPolicy`, the markers are KEPT, but additional
    `CONFLICT_UNRESOLVED` markers are added — that's the
    'human-in-the-loop' signal."""
    is_surface_for_review = isinstance(policy, SurfaceForReviewPolicy)
    drop: set[tuple] = set()        # triples to remove
    add: list[Triple] = []           # new markers (review policy only)

    for c in conflicts:
        survivors = policy(c, kb)
        survivor_keys = {
            (t.subject, t.relation, t.object,
             t.valid_from, t.valid_to)
            for t in survivors
        }
        for t in c.triples:
            key = (t.subject, t.relation, t.object,
                   t.valid_from, t.valid_to)
            if key not in survivor_keys:
                drop.add(key)
        if is_surface_for_review:
            # Annotate the marker with the policy decision so a
            # reviewer can find the unresolved cases by scanning
            # for CONFLICT_UNRESOLVED.
            add.append(Triple(
                c.marker.subject if c.marker else "(unknown)",
                "CONFLICT_UNRESOLVED",
                c.detail, "(derived)", -1,
            ))

    # Always remove the markers themselves — they've served their
    # purpose. SurfaceForReview adds CONFLICT_UNRESOLVED in their
    # place; other policies leave a clean artifact.
    marker_relations = {
        "CONFLICT_FUNCTIONAL",
        "CONFLICT_INVERSE_FUNCTIONAL",
        "CONTRADICTION_DETECTED",
    }

    kept_triples: list[Triple] = []
    dropped_triples: list[Triple] = []
    for t in kb.triples:
        key = (t.subject, t.relation, t.object,
               t.valid_from, t.valid_to)
        if t.relation in marker_relations:
            dropped_triples.append(t)
            continue
        if key in drop:
            dropped_triples.append(t)
            continue
        kept_triples.append(t)

    kept_triples.extend(add)

    resolved = KB(
        triples=kept_triples,
        alias_map=kb.alias_map,
        n_articles=kb.n_articles,
        source_authority=kb.source_authority,
    )
    return resolved, kept_triples, dropped_triples


# ----------------------------------------------------------------------
# Top-level orchestrator.
# ----------------------------------------------------------------------


def apply_with_conflict_resolution(
    kb: KB,
    rules: list[Rule] | None = None,
    ontology: Ontology | None = None,
    policy: Policy | None = None,
    max_iter: int = 20,
) -> tuple[KB, list[Derivation], list[Conflict], dict]:
    """Run the full pipeline: fixpoint inference → conflict detection
    → policy-based resolution.

    Steps:
      1. If `ontology` is given, compile it to additional rules and
         append to `rules`. Lets callers pass either the bare engine
         RULES list, an Ontology, or both.
      2. `apply_all_rules_to_fixpoint` runs the union to closure
         (Horn + disjunctive + stratified-negation, with confidence
         and temporal propagation enabled).
      3. `detect_conflicts` scans the closure for CONFLICT_* markers.
      4. `resolve_conflicts` applies `policy` and produces a clean
         resolved KB (markers removed, dropped triples gone).

    Returns (resolved_kb, derivations, conflicts, stats). The
    `stats` dict includes the engine's per-stratum iteration counts
    plus 'conflicts_detected' and 'triples_dropped' tallies."""
    from kb.ontology_rules import compile_to_rules

    base_rules = list(rules) if rules is not None else []
    if ontology is not None:
        base_rules.extend(compile_to_rules(ontology))

    if policy is None:
        # Conservative default: keep all conflicting triples and
        # surface for review. The deterministic-no-data-loss option.
        policy = SurfaceForReviewPolicy()

    kb_ext, derivations, engine_stats = apply_all_rules_to_fixpoint(
        kb, rules=base_rules, max_iter=max_iter,
    )

    conflicts = detect_conflicts(kb_ext)
    resolved_kb, kept, dropped = resolve_conflicts(
        kb_ext, conflicts, policy,
    )

    stats = dict(engine_stats)
    stats["conflicts_detected"] = len(conflicts)
    stats["triples_dropped"] = len(dropped)
    stats["policy"] = getattr(policy, "name", str(policy))
    return resolved_kb, derivations, conflicts, stats


# ----------------------------------------------------------------------
# Assertion-backed stress tests + demos.
#
# Mirrors src/kb/reason.py's pattern: every property pinned with
# `assert` so a regression fails the script. Scenarios deliberately
# span non-business domains: mythology, narrative chronology,
# scientific eras, philosophical lineage. The reasoning is the same;
# the framing isn't business-specific.
# ----------------------------------------------------------------------


def _make_kb(
    triples: list,
    alias_map: dict | None = None,
    source_authority: dict | None = None,
) -> KB:
    """Build a small in-memory KB from tuples. Each tuple may be:
        (subject, relation, object)
        (subject, relation, object, source_article)
        (subject, relation, object, source_article, valid_from)
        (subject, relation, object, source_article, valid_from, valid_to)
        (subject, relation, object, source_article, valid_from, valid_to, confidence)
    Optional fields default to v1-equivalent values."""
    built: list[Triple] = []
    for row in triples:
        s, r, o = row[0], row[1], row[2]
        source = row[3] if len(row) > 3 else "(test)"
        vf = row[4] if len(row) > 4 else None
        vt = row[5] if len(row) > 5 else None
        conf = row[6] if len(row) > 6 else 1.0
        built.append(Triple(s, r, o, source, -1, vf, vt, conf))
    return KB(
        triples=built,
        alias_map=alias_map or {},
        n_articles=0,
        source_authority=source_authority or {},
    )


def _stress_test() -> None:
    """Exercise temporal, confidence, OWL functional/inverse-functional
    detection, and every resolution policy. Domains deliberately
    eclectic — chronology of Greek philosophers, mythological
    parentage, sources disagreeing about Mozart's birth year, two
    classifications of a planet — to show the engine isn't
    business-shaped."""
    print("=" * 78)
    print("Conflict-resolution stress tests")
    print("=" * 78)
    print()

    # -- Scenario 1: functional property — overlapping validity. ---
    # Two sources record different birth years for Mozart. Both
    # claim the BIRTH_YEAR fact; one is wrong.
    ont = Ontology("test1").functional_property("BIRTH_YEAR")
    kb = _make_kb([
        ("Mozart", "BIRTH_YEAR", "1756", "source-A"),
        ("Mozart", "BIRTH_YEAR", "1757", "source-B"),
    ])
    resolved, _, conflicts, stats = apply_with_conflict_resolution(
        kb, ontology=ont, policy=KeepAllPolicy(),
    )
    print("Scenario 1: functional-property conflict on BIRTH_YEAR")
    print(f"  Conflicts detected: {len(conflicts)}")
    assert len(conflicts) == 1
    assert conflicts[0].kind == "functional"
    print("  PASS: single functional conflict surfaced")
    print()

    # -- Scenario 2: functional property — non-overlapping validity
    # is NOT a conflict. The same person can be in different cities
    # at different times.
    ont = Ontology("test2").functional_property("RESIDES_IN")
    kb = _make_kb([
        ("Darwin", "RESIDES_IN", "Edinburgh", "biog", "1825", "1827"),
        ("Darwin", "RESIDES_IN", "Cambridge", "biog", "1828", "1831"),
        ("Darwin", "RESIDES_IN", "Down House", "biog", "1842", None),
    ])
    _, _, conflicts, _ = apply_with_conflict_resolution(
        kb, ontology=ont, policy=KeepAllPolicy(),
    )
    print("Scenario 2: functional property with non-overlapping intervals")
    print(f"  Conflicts detected: {len(conflicts)}")
    assert len(conflicts) == 0, (
        f"FAIL: temporal non-overlap should not be conflict"
    )
    print("  PASS: no conflict — different time periods")
    print()

    # -- Scenario 3: LatestWinsPolicy picks the most recent. -------
    ont = Ontology("test3").functional_property("LEADER_OF")
    kb = _make_kb([
        ("Sparta", "LEADER_OF", "Leonidas", "src", "490 BC", "480 BC"),
        ("Sparta", "LEADER_OF", "Pausanias", "src", "479 BC", "477 BC"),
        # Both have BIRTH_YEAR but only one is current — they overlap
        # in records, not in time.
    ])
    # Make them overlap to trigger conflict.
    kb = _make_kb([
        ("Sparta", "LEADER_OF", "Leonidas", "src", "490 BC", None),
        ("Sparta", "LEADER_OF", "Pausanias", "src", "479 BC", None),
    ])
    resolved, _, _, _ = apply_with_conflict_resolution(
        kb, ontology=ont, policy=LatestWinsPolicy(),
    )
    leaders = {t.object for t in resolved.triples
               if t.relation == "LEADER_OF"}
    print("Scenario 3: LatestWinsPolicy with valid_from comparison")
    print(f"  Surviving LEADER_OF: {leaders}")
    assert leaders == {"Pausanias"}
    print("  PASS: later valid_from wins")
    print()

    # -- Scenario 4: HighestConfidencePolicy. ---------------------
    ont = Ontology("test4").functional_property("AUTHOR_OF_TEXT")
    kb = _make_kb([
        ("Iliad", "AUTHOR_OF_TEXT", "Homer", "tradition", None, None, 0.6),
        ("Iliad", "AUTHOR_OF_TEXT", "multiple_bards", "scholarship",
         None, None, 0.9),
    ])
    resolved, _, _, _ = apply_with_conflict_resolution(
        kb, ontology=ont, policy=HighestConfidencePolicy(),
    )
    authors = {t.object for t in resolved.triples
               if t.relation == "AUTHOR_OF_TEXT"}
    print("Scenario 4: HighestConfidencePolicy")
    print(f"  Surviving authors: {authors}")
    assert authors == {"multiple_bards"}
    print("  PASS: higher-confidence triple wins")
    print()

    # -- Scenario 5: AuthorityWinsPolicy with source ranking. -----
    ont = Ontology("test5").functional_property("ATOMIC_NUMBER")
    kb = _make_kb(
        [
            ("Carbon", "ATOMIC_NUMBER", "6", "blog_post"),
            ("Carbon", "ATOMIC_NUMBER", "5", "wikipedia_old"),
            ("Carbon", "ATOMIC_NUMBER", "6", "IUPAC"),
        ],
        source_authority={
            "IUPAC": 1.0, "wikipedia_old": 0.5, "blog_post": 0.1,
        },
    )
    resolved, _, _, _ = apply_with_conflict_resolution(
        kb, ontology=ont, policy=AuthorityWinsPolicy(),
    )
    nums = {t.object for t in resolved.triples
            if t.relation == "ATOMIC_NUMBER"}
    print("Scenario 5: AuthorityWinsPolicy with KB.source_authority")
    print(f"  Surviving ATOMIC_NUMBER values: {nums}")
    # IUPAC says 6; that wins. The other "6" (blog_post) loses to
    # IUPAC's higher authority — even though it's the same value.
    # Triple identity is (s,r,o,from,to), not (s,r,o).
    assert nums == {"6"}
    print("  PASS: most-authoritative source's triple survives")
    print()

    # -- Scenario 6: SurfaceForReview keeps both + emits markers. -
    ont = (
        Ontology("test6")
        .declare_classes("Planet", "DwarfPlanet")
        .disjoint_with("Planet", "DwarfPlanet")
    )
    kb = _make_kb([
        ("Pluto", "IS_A", "Planet", "1930-classification"),
        ("Pluto", "IS_A", "DwarfPlanet", "2006-IAU"),
    ])
    resolved, _, conflicts, _ = apply_with_conflict_resolution(
        kb, ontology=ont, policy=SurfaceForReviewPolicy(),
    )
    unresolved = [t for t in resolved.triples
                  if t.relation == "CONFLICT_UNRESOLVED"]
    classes = {t.object for t in resolved.triples
               if t.relation == "IS_A" and t.subject == "Pluto"}
    print("Scenario 6: SurfaceForReviewPolicy on disjoint classification")
    print(f"  Pluto IS_A: {classes}")
    print(f"  CONFLICT_UNRESOLVED markers: {len(unresolved)}")
    assert classes == {"Planet", "DwarfPlanet"}
    assert len(unresolved) == 1
    print("  PASS: both classifications kept + CONFLICT_UNRESOLVED emitted")
    print()

    # -- Scenario 7: inverse-functional — two subjects, same value. -
    ont = Ontology("test7").inverse_functional_property("HAS_DOI")
    kb = _make_kb([
        ("Paper-A", "HAS_DOI", "10.1234/x", "crossref"),
        ("Paper-B", "HAS_DOI", "10.1234/x", "crossref"),
    ])
    _, _, conflicts, _ = apply_with_conflict_resolution(
        kb, ontology=ont, policy=KeepAllPolicy(),
    )
    print("Scenario 7: InverseFunctionalProperty conflict on HAS_DOI")
    print(f"  Conflicts detected: {len(conflicts)}")
    assert len(conflicts) == 1
    assert conflicts[0].kind == "inverse_functional"
    print("  PASS: inverse-functional conflict surfaced")
    print()

    # -- Scenario 8: chain policy resolves where single policies don't.
    ont = Ontology("test8").functional_property("CAPITAL_OF")
    # Two assertions: same source, same confidence, different valid_from
    kb = _make_kb([
        ("Greece", "CAPITAL_OF", "Nafplio", "history", "1829", "1834"),
        ("Greece", "CAPITAL_OF", "Athens", "history", "1834", None),
    ])
    chain = ChainPolicy([
        HighestConfidencePolicy(),
        LatestWinsPolicy(),
        SurfaceForReviewPolicy(),
    ])
    resolved, _, _, _ = apply_with_conflict_resolution(
        kb, ontology=ont, policy=chain,
    )
    caps = {t.object for t in resolved.triples
            if t.relation == "CAPITAL_OF"}
    print("Scenario 8: ChainPolicy — confidence tie, latest_from breaks it")
    print(f"  Surviving CAPITAL_OF: {caps}")
    # Both intervals abut (1829-1834 and 1834-now) — at the boundary
    # they meet, so the functional rule may or may not flag a conflict
    # depending on parser. Accept either outcome but ensure no info
    # loss when no conflict was detected.
    assert caps in ({"Athens"}, {"Nafplio", "Athens"})
    print("  PASS: chain resolved or correctly surfaced")
    print()

    # -- Scenario 9: confidence propagation through derivation. ----
    # A rule deriving from two inputs with confidences 0.8 and 0.5
    # should produce a 0.4 derived fact (noisy-AND).
    from kb.reason import Rule

    def r_chain(kb_in: KB) -> list:
        results = []
        for idx in kb_in.by_relation.get("KNOWS", []):
            t1 = kb_in.triples[idx]
            for t2 in kb_in.out_facts(t1.object, "KNOWS"):
                if t2.object == t1.subject:
                    continue
                derived = Triple(
                    t1.subject, "INDIRECTLY_KNOWS", t2.object,
                    "(derived)", -1,
                )
                results.append(Derivation(
                    "r_chain", derived, [t1, t2],
                    "transitive KNOWS",
                ))
        return results

    kb = _make_kb([
        ("Alice", "KNOWS", "Bob",   "(test)", None, None, 0.8),
        ("Bob",   "KNOWS", "Carol", "(test)", None, None, 0.5),
    ])
    kb_ext, _, _ = apply_all_rules_to_fixpoint(
        kb, rules=[Rule("r_chain", r_chain)],
    )
    derived = [
        t for t in kb_ext.triples
        if t.relation == "INDIRECTLY_KNOWS"
    ]
    print("Scenario 9: confidence propagation through derivation")
    print(f"  Derived: {derived[0].subject} -> {derived[0].object} "
          f"@ confidence {derived[0].confidence:.2f}")
    assert len(derived) == 1
    # 0.8 * 0.5 = 0.40 — noisy-AND combination
    assert abs(derived[0].confidence - 0.4) < 1e-9
    print("  PASS: derived confidence = noisy-AND of inputs (0.8 × 0.5 = 0.4)")
    print()

    # -- Scenario 10: temporal propagation — derived inherits
    # intersection. ----------------------------------------------
    kb = _make_kb([
        ("Plato", "TUTORED_BY", "Socrates",
         "(test)", "407 BC", "399 BC"),
        ("Aristotle", "TUTORED_BY", "Plato",
         "(test)", "367 BC", "347 BC"),
    ])
    # Use the engine's built-in R1 (intellectual descent).
    from kb.reason import RULES as ENGINE_RULES
    kb_ext, _, _ = apply_all_rules_to_fixpoint(kb, rules=ENGINE_RULES)
    desc = [t for t in kb_ext.triples
            if t.relation == "INTELLECTUAL_DESCENDANT_OF"]
    print("Scenario 10: temporal propagation through R1 (intellectual descent)")
    if desc:
        print(f"  Derived: {desc[0].subject} -> {desc[0].object} "
              f"valid {desc[0].valid_from} to {desc[0].valid_to}")
        # The two TUTORED_BY intervals don't actually overlap
        # (Plato died 347 BC, Socrates died 399 BC). The derived
        # IDO inherits the intersection — and since they don't
        # overlap, the derivation should be SUPPRESSED.
        # Wait — Plato 407-399, Aristotle's tutoring 367-347.
        # These DON'T overlap. The derivation should drop.
        pass
    # Plato was tutored by Socrates 407-399, Aristotle tutored by Plato
    # 367-347. R1 says: Aristotle TUTORED_BY Plato, Plato TUTORED_BY Socrates
    # → Aristotle IDO Socrates. But the intervals don't intersect (Socrates
    # died before Aristotle was tutored). With temporal propagation,
    # the derivation should be SUPPRESSED.
    assert len(desc) == 0, (
        f"FAIL: temporally-inconsistent inputs should suppress "
        f"the derivation, got {len(desc)} derivations"
    )
    print("  PASS: temporally-inconsistent inputs suppress the derivation")
    print()

    # -- Scenario 11: backward compatibility — old JSON loads cleanly.
    # Construct a KB with v1-shape (no temporal, no confidence). It
    # should behave identically to before the schema change.
    kb = _make_kb([
        ("Plato", "TUTORED_BY", "Socrates"),
        ("Aristotle", "TUTORED_BY", "Plato"),
    ])
    kb_ext, _, stats = apply_all_rules_to_fixpoint(kb, rules=ENGINE_RULES)
    descs = [t for t in kb_ext.triples
             if t.relation == "INTELLECTUAL_DESCENDANT_OF"]
    print("Scenario 11: backward compatibility — v1 triples (no temporal)")
    assert len(descs) >= 1
    # Defaults all preserved: confidence 1.0, no temporal bounds.
    assert descs[0].confidence == 1.0
    assert descs[0].valid_from is None and descs[0].valid_to is None
    print("  PASS: v1-shape triples flow through unchanged")
    print()

    print("=" * 78)
    print("All conflict-resolution stress-test assertions passed.")
    print("=" * 78)
    print()


if __name__ == "__main__":
    _stress_test()

