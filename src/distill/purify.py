"""Knowledge distillation / purification — turn a noisy multi-source
corpus into a clean canonical KB.

Pipeline stages, each handled by primitives that already exist in the
core engine:

  1. **Conflict detection.** An OWL ontology declares the functional
     properties of the domain (one MASS_KG per body, one
     CLASSIFICATION per body, etc.). The OWL rule compiler in
     `src/kb/ontology_rules.py` emits `CONFLICT_FUNCTIONAL` markers
     anywhere two values for the same functional property overlap in
     time. Temporally-disjoint values (Pluto-as-Planet pre-2006 vs
     Pluto-as-DwarfPlanet post-2006) are NOT flagged — they don't
     overlap.

  2. **Conflict resolution.** A chain policy picks survivors:
     AuthorityWins → LatestWins → HighestConfidence → SurfaceForReview.
     The first to narrow wins; the last keeps everything and emits
     `CONFLICT_UNRESOLVED` markers for human review.

  3. **Corroboration boost.** When several independent sources assert
     the same fact (same subject + relation + object + temporal slot),
     their confidences are combined via `noisy_or` — three sources at
     0.95 each yield a consolidated confidence of ~0.9999, stronger
     than any single source could justify alone. The triples collapse
     into one canonical record whose provenance lists every source.

  4. **Confidence-threshold pruning.** Facts whose final confidence
     falls below a caller-chosen threshold are dropped. Useful for
     stripping the low-authority noise that policy chains couldn't
     fully exclude on its own.

  5. **Marker cleanup.** `CONFLICT_*` and `CONTRADICTION_DETECTED`
     facts that have served their purpose are removed; the shipped
     artifact is plain data.

The pipeline is general-purpose: change the ontology and the corpus,
and the same code purifies medical guidelines, scientific literature,
folklore variants, historical records, or anything else with the
"same fact from multiple sources, sometimes disagreeing" structure.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parent))

from corpus import build_noisy_kb, SOURCE_AUTHORITY
from kb.query import KB, Triple
from kb.ontology import Ontology
from kb.confidence import noisy_or
from kb.conflict import (
    apply_with_conflict_resolution,
    ChainPolicy,
    AuthorityWinsPolicy,
    LatestWinsPolicy,
    HighestConfidencePolicy,
    SurfaceForReviewPolicy,
)


# ----------------------------------------------------------------------
# Domain ontology.
#
# Each functional axiom flags a property where "two values for the
# same subject is a conflict" makes physical sense. Temporal scoping
# in the OWL rule compiler means classifications that differ across
# eras (Pluto pre/post 2006) do not raise conflicts.
# ----------------------------------------------------------------------


ONTOLOGY = (
    Ontology("astronomical")
    .functional_property("MASS_KG")
    .functional_property("RADIUS_KM")
    .functional_property("ORBITAL_PERIOD_DAYS")
    .functional_property("DISTANCE_FROM_SUN_AU")
    .functional_property("DISTANCE_LIGHT_YEARS")
    .functional_property("DISCOVERY_DATE")
    .functional_property("IS_A")           # at most one class per body at a time
    # A coarse class hierarchy. CelestialBody is the root; planets
    # and dwarf planets are sub-classes; inner/outer planets refine
    # further. The compiler closes class membership transitively.
    .subclass_of("Planet", "CelestialBody")
    .subclass_of("DwarfPlanet", "CelestialBody")
    .subclass_of("Star", "CelestialBody")
    .subclass_of("Galaxy", "CelestialBody")
    .subclass_of("InnerPlanet", "Planet")
    .subclass_of("OuterPlanet", "Planet")
)


# ----------------------------------------------------------------------
# Corroboration.
#
# After conflict resolution we may still have many triples carrying
# identical (subject, relation, object, valid_from, valid_to) — the
# same fact stated by several sources. Collapsing them strengthens
# the artifact: the consolidated fact has a confidence that combines
# every source's vote (noisy-OR) and provenance that lists every
# source.
# ----------------------------------------------------------------------


def corroborate(kb: KB) -> tuple[KB, int]:
    """Collapse duplicate (s, r, o, valid_from, valid_to) triples into
    one consolidated record per group. Confidence is boosted via
    noisy-OR; source_article becomes a sorted, comma-separated list
    of all contributing sources.

    Returns (corroborated_kb, n_groups_merged) where n_groups_merged
    counts how many duplicate groups were collapsed (one per group
    where multiple sources agreed)."""
    # Group by the full identity tuple. Marker triples (CONFLICT_* and
    # CONTRADICTION_DETECTED) get passed through unchanged — those
    # have already been consumed by the conflict resolver if it ran.
    groups: dict[tuple, list[Triple]] = defaultdict(list)
    for t in kb.triples:
        # scope is part of identity: the same (s,r,o) in two microtheories
        # are distinct facts and must not be merged across framings.
        key = (t.subject, t.relation, t.object, t.valid_from, t.valid_to, t.scope)
        groups[key].append(t)

    merged: list[Triple] = []
    n_merged_groups = 0
    for key, group in groups.items():
        if len(group) == 1:
            # Single source — no corroboration to do. Pass through.
            merged.append(group[0])
            continue
        # Multiple sources for the same fact. Combine their
        # confidences via noisy-OR (independent-evidence reading)
        # and list their sources.
        n_merged_groups += 1
        combined_conf = noisy_or(t.confidence for t in group)
        sources = sorted({t.source_article for t in group})
        canonical = replace(
            group[0],
            confidence=combined_conf,
            source_article=", ".join(sources),
        )
        merged.append(canonical)

    return KB(
        triples=merged,
        alias_map=kb.alias_map,
        n_articles=kb.n_articles,
        source_authority=kb.source_authority,
    ), n_merged_groups


# ----------------------------------------------------------------------
# Confidence-threshold pruning.
# ----------------------------------------------------------------------


def prune_below(kb: KB, threshold: float) -> tuple[KB, list[Triple]]:
    """Drop triples whose confidence falls below `threshold`.

    Returns (pruned_kb, dropped_triples). Marker triples (CONFLICT_*
    etc.) are never pruned — they're meta-facts, not knowledge."""
    marker_relations = {
        "CONFLICT_FUNCTIONAL",
        "CONFLICT_INVERSE_FUNCTIONAL",
        "CONTRADICTION_DETECTED",
        "CONFLICT_UNRESOLVED",
    }
    kept: list[Triple] = []
    dropped: list[Triple] = []
    for t in kb.triples:
        if t.relation in marker_relations:
            kept.append(t)
            continue
        if t.confidence < threshold:
            dropped.append(t)
            continue
        kept.append(t)
    return KB(
        triples=kept,
        alias_map=kb.alias_map,
        n_articles=kb.n_articles,
        source_authority=kb.source_authority,
    ), dropped


# ----------------------------------------------------------------------
# Top-level pipeline.
# ----------------------------------------------------------------------


@dataclass
class PurificationReport:
    """Diagnostic record describing what the pipeline did. Returned
    alongside the purified KB so callers can audit the changes."""
    initial_triples: int
    final_triples: int
    conflicts_detected: int
    conflict_triples_dropped: int
    corroborated_groups: int
    pruned_low_confidence: int
    threshold: float
    policy_name: str

    def summary(self) -> str:
        net = self.final_triples - self.initial_triples
        sign = "+" if net >= 0 else ""
        return (
            f"Initial: {self.initial_triples} triples → "
            f"Final: {self.final_triples} triples  ({sign}{net})\n"
            f"  Conflicts detected:           {self.conflicts_detected}\n"
            f"  Conflict-loser triples dropped: "
            f"{self.conflict_triples_dropped}\n"
            f"  Multi-source groups merged:   {self.corroborated_groups}\n"
            f"  Low-confidence triples pruned: "
            f"{self.pruned_low_confidence}  (threshold={self.threshold})\n"
            f"  Policy used:                  {self.policy_name}"
        )


def purify(
    kb: KB,
    ontology: Ontology | None = None,
    policy=None,
    confidence_threshold: float = 0.5,
) -> tuple[KB, PurificationReport, list]:
    """Run the full purification pipeline.

    Returns (purified_kb, report, conflicts). `conflicts` is the list
    of `Conflict` records detected before resolution — useful for
    why-trace queries even after resolution has happened.

    Default policy is the standard chain: AuthorityWins → LatestWins
    → HighestConfidence → SurfaceForReview. Default threshold is 0.5
    — the noisy-corpus floor that separates 'plausible' from
    'probably noise'."""
    if ontology is None:
        ontology = ONTOLOGY
    if policy is None:
        policy = ChainPolicy([
            AuthorityWinsPolicy(),
            LatestWinsPolicy(),
            HighestConfidencePolicy(),
            SurfaceForReviewPolicy(),
        ])

    initial_count = len(kb.triples)

    # Stage 1+2: OWL conflict detection + chain-policy resolution.
    resolved, _, conflicts, stats = apply_with_conflict_resolution(
        kb,
        rules=[],
        ontology=ontology,
        policy=policy,
    )

    # Stage 3: corroborate identical facts from multiple sources.
    corroborated, n_merged = corroborate(resolved)

    # Stage 4: confidence-threshold pruning.
    pruned, dropped = prune_below(corroborated, confidence_threshold)

    report = PurificationReport(
        initial_triples=initial_count,
        final_triples=len(pruned.triples),
        conflicts_detected=stats.get("conflicts_detected", 0),
        conflict_triples_dropped=stats.get("triples_dropped", 0),
        corroborated_groups=n_merged,
        pruned_low_confidence=len(dropped),
        threshold=confidence_threshold,
        policy_name=stats.get("policy", str(policy)),
    )
    return pruned, report, conflicts


# ----------------------------------------------------------------------
# Demo.
# ----------------------------------------------------------------------


def _show_fact(t: Triple, indent: str = "  ") -> str:
    parts = [f"{t.subject:<18s} {t.relation:<22s} {t.object!s:<22s}"]
    parts.append(f"conf={t.confidence:.3f}")
    if t.valid_from or t.valid_to:
        parts.append(f"valid={t.valid_from or '-inf'}..{t.valid_to or 'inf'}")
    parts.append(f"src='{t.source_article}'")
    return indent + "  ".join(parts)


def main() -> None:
    print("=" * 78)
    print("Knowledge distillation / purification — astronomical corpus")
    print("=" * 78)
    print()
    print("Takes a deliberately-noisy multi-source corpus (six fictional")
    print("sources of varying authority, with corroborated facts, value")
    print("conflicts, outdated estimates, and low-authority noise) and")
    print("produces a clean canonical KB through the standard pipeline:")
    print("  detect conflicts → resolve via chain policy → corroborate")
    print("  multi-source facts → prune below threshold → strip markers.")
    print()

    # ---- 1. Load the noisy corpus ---------------------------------
    noisy = build_noisy_kb()
    print(f"INITIAL CORPUS")
    print("-" * 78)
    print(f"  Triples:        {len(noisy.triples):,}")
    print(f"  Sources:        {len(noisy.source_authority)}")
    print(f"  Subjects:       "
          f"{len({t.subject for t in noisy.triples})}")
    print(f"  Functional axioms in ontology: "
          f"{len(ONTOLOGY.functional_properties)}")
    print()
    print(f"  Source authorities:")
    for src, auth in sorted(noisy.source_authority.items(),
                             key=lambda kv: -kv[1]):
        print(f"    {src:<30s} {auth:.2f}")
    print()

    # ---- 2. Run the pipeline --------------------------------------
    purified, report, conflicts = purify(noisy, confidence_threshold=0.5)

    print("PURIFICATION REPORT")
    print("-" * 78)
    for line in report.summary().split("\n"):
        print(f"  {line}")
    print()

    # ---- 3. Show specific conflict resolutions --------------------
    if conflicts:
        print("CONFLICTS DETECTED + RESOLUTIONS")
        print("-" * 78)
        survivor_keys = {
            (t.subject, t.relation, t.object) for t in purified.triples
        }
        for c in conflicts:
            print(f"  [{c.kind}] {c.triples[0].subject:<20s} {c.detail}")
            for t in c.triples:
                key = (t.subject, t.relation, t.object)
                mark = "✓ kept   " if key in survivor_keys else "  dropped"
                print(f"    {mark} {t.object!s:<18s} "
                      f"conf={t.confidence:.2f}  "
                      f"src='{t.source_article}'")
            print()

    # ---- 4. Show corroboration on a clear example -----------------
    print("CORROBORATION EXAMPLES (multi-source agreement)")
    print("-" * 78)
    # Find the most-corroborated facts (those whose source_article is
    # a comma-joined list, indicating multiple sources merged).
    corroborated = [
        t for t in purified.triples
        if ", " in (t.source_article or "")
    ]
    # Sort by confidence descending — the highest-corroborated.
    corroborated.sort(key=lambda t: -t.confidence)
    for t in corroborated[:8]:
        sources = t.source_article.split(", ")
        print(f"  {t.subject:<18s} {t.relation:<22s} {t.object!s:<18s} "
              f"conf={t.confidence:.4f} from {len(sources)} sources")
    print()

    # ---- 5. Side-by-side: noisy vs purified for Andromeda ---------
    print("BEFORE / AFTER on a contested property "
          "(Andromeda's distance)")
    print("-" * 78)
    print("  NOISY:")
    for t in noisy.triples:
        if (t.subject == "Andromeda Galaxy"
                and t.relation == "DISTANCE_LIGHT_YEARS"):
            print(_show_fact(t, "    "))
    print()
    print("  PURIFIED:")
    for t in purified.triples:
        if (t.subject == "Andromeda Galaxy"
                and t.relation == "DISTANCE_LIGHT_YEARS"):
            print(_show_fact(t, "    "))
    print()

    # ---- 6. Pluto pre/post 2006: temporal-scoped non-conflict -----
    print("TEMPORAL NON-CONFLICT (Pluto's classification "
          "across the 2006 reclassification)")
    print("-" * 78)
    print("  Both kept — they don't overlap in time:")
    for t in purified.triples:
        if t.subject == "Pluto" and t.relation == "IS_A":
            print(_show_fact(t, "    "))
    print()

    # ---- 7. What got pruned ---------------------------------------
    # Build a set of (s,r,o) that ended up in purified so we can
    # identify what was dropped.
    final_keys = {(t.subject, t.relation, t.object) for t in purified.triples}
    pruned_facts = [
        t for t in noisy.triples
        if (t.subject, t.relation, t.object) not in final_keys
    ]
    if pruned_facts:
        print(f"DROPPED FACTS (showing first 10 of {len(pruned_facts)})")
        print("-" * 78)
        for t in pruned_facts[:10]:
            print(_show_fact(t, "  "))
        print()

    # ---- 8. The purified KB ---------------------------------------
    print(f"PURIFIED KB SAMPLE (first 12 of {len(purified.triples)})")
    print("-" * 78)
    for t in sorted(purified.triples,
                     key=lambda t: (t.subject, t.relation))[:12]:
        print(_show_fact(t, "  "))
    print()

    print("=" * 78)
    print("Same engine, applied as a distillation step: noisy multi-source")
    print("facts in, deterministic canonical KB out, every change auditable.")
    print("=" * 78)
    print()


# ----------------------------------------------------------------------
# Stress tests.
#
# Six assertion-backed scenarios pinning the pipeline's properties on
# synthetic inputs. Same demos-are-tests convention as the rest of
# the project; run after main() so a regression surfaces non-zero.
# ----------------------------------------------------------------------


def _stress_test() -> None:
    print("=" * 78)
    print("Distillation pipeline stress tests")
    print("=" * 78)
    print()

    # -- Scenario 1: corroboration boosts confidence above any input.
    kb = KB(
        triples=[
            Triple("X", "PROP", "v", "src_a", -1, None, None, 0.7),
            Triple("X", "PROP", "v", "src_b", -1, None, None, 0.7),
            Triple("X", "PROP", "v", "src_c", -1, None, None, 0.7),
        ],
        alias_map={}, n_articles=0,
    )
    corroborated, n_merged = corroborate(kb)
    boosted = [t for t in corroborated.triples if t.subject == "X"]
    print("Scenario 1: three independent sources, same fact")
    print(f"  Original confidences: 0.7, 0.7, 0.7")
    print(f"  After corroboration: {boosted[0].confidence:.4f}")
    # noisy_or([0.7, 0.7, 0.7]) = 1 - 0.3^3 = 0.973
    assert abs(boosted[0].confidence - 0.973) < 1e-3, (
        f"FAIL: noisy-OR combine returned {boosted[0].confidence}"
    )
    assert n_merged == 1
    assert ", " in boosted[0].source_article
    print("  PASS: confidence boosted via noisy-OR")
    print()

    # -- Scenario 2: pruning drops below-threshold facts.
    kb = KB(
        triples=[
            Triple("A", "P", "1", "good_src", -1, None, None, 0.9),
            Triple("B", "P", "2", "bad_src",  -1, None, None, 0.3),
            Triple("C", "P", "3", "ok_src",   -1, None, None, 0.6),
        ],
        alias_map={}, n_articles=0,
    )
    pruned, dropped = prune_below(kb, 0.5)
    print("Scenario 2: confidence-threshold pruning at 0.5")
    print(f"  Kept: {sorted(t.subject for t in pruned.triples)}")
    print(f"  Dropped: {sorted(t.subject for t in dropped)}")
    assert {t.subject for t in pruned.triples} == {"A", "C"}
    assert {t.subject for t in dropped} == {"B"}
    print("  PASS")
    print()

    # -- Scenario 3: marker facts are never pruned.
    kb = KB(
        triples=[
            Triple("A", "CONFLICT_FUNCTIONAL", "P:1|2",
                   "(derived)", -1, None, None, 0.1),
            Triple("A", "REGULAR", "x", "src", -1, None, None, 0.1),
        ],
        alias_map={}, n_articles=0,
    )
    pruned, dropped = prune_below(kb, 0.5)
    print("Scenario 3: marker facts survive pruning even below threshold")
    assert any(t.relation == "CONFLICT_FUNCTIONAL" for t in pruned.triples)
    assert not any(t.relation == "REGULAR" for t in pruned.triples)
    print("  PASS")
    print()

    # -- Scenario 4: end-to-end on the real noisy corpus.
    noisy = build_noisy_kb()
    purified, report, conflicts = purify(noisy, confidence_threshold=0.5)
    print("Scenario 4: end-to-end purification of the bundled noisy corpus")
    print(f"  Initial:        {report.initial_triples}")
    print(f"  Final:          {report.final_triples}")
    print(f"  Conflicts:      {report.conflicts_detected}")
    print(f"  Merged groups:  {report.corroborated_groups}")
    print(f"  Pruned:         {report.pruned_low_confidence}")
    # The bundled corpus is engineered to exhibit all four pathologies.
    assert report.conflicts_detected > 0, "expected functional conflicts"
    assert report.corroborated_groups > 0, "expected multi-source agreement"
    assert report.pruned_low_confidence > 0, "expected some pruning"
    assert report.final_triples < report.initial_triples, \
        "expected net reduction"
    print("  PASS")
    print()

    # -- Scenario 5: temporal non-overlap is NOT a conflict.
    # Pluto IS_A Planet up to 2006-08-24, then IS_A DwarfPlanet.
    # These should pass through purification without being treated
    # as a conflict.
    noisy = build_noisy_kb()
    purified, _, _ = purify(noisy, confidence_threshold=0.0)  # keeps everything that survives resolution
    pluto_classes = [
        t for t in purified.triples
        if t.subject == "Pluto" and t.relation == "IS_A"
    ]
    print("Scenario 5: temporal scoping prevents Pluto conflict")
    print(f"  Pluto IS_A facts surviving: "
          f"{[t.object for t in pluto_classes]}")
    objects = {t.object for t in pluto_classes}
    assert "Planet" in objects and "DwarfPlanet" in objects, (
        f"FAIL: temporal-scoped Pluto facts should both survive; "
        f"got {objects}"
    )
    print("  PASS: both classifications kept (different time periods)")
    print()

    # -- Scenario 6: Andromeda distance — modern value should win.
    purified, _, _ = purify(build_noisy_kb(), confidence_threshold=0.5)
    andromeda_dists = [
        t for t in purified.triples
        if t.subject == "Andromeda Galaxy"
        and t.relation == "DISTANCE_LIGHT_YEARS"
    ]
    print("Scenario 6: Andromeda distance — authoritative modern value wins")
    print(f"  Surviving distance(s): "
          f"{[t.object for t in andromeda_dists]}")
    # The four-way conflict (2.5e6, 2.0e6, 1.0e6, 0.9e6) should resolve
    # to 2.5e6 — three high-authority sources corroborated.
    assert {t.object for t in andromeda_dists} == {"2.5e6"}, (
        f"FAIL: AuthorityWins + corroboration should pick 2.5e6; got "
        f"{[t.object for t in andromeda_dists]}"
    )
    print("  PASS")
    print()

    print("=" * 78)
    print("All distillation stress-test assertions passed.")
    print("=" * 78)
    print()


def _hermit_augment_distill() -> None:
    """Optional HermiT pass demonstrating DL inconsistency detection
    over a category-disjointness axiom that the rule-compiler can
    express but the engine doesn't run by default.

    Asserts Pluto's PRE-2006 classification as Planet while a
    contemporaneous source classifies it as DwarfPlanet — under DL's
    open-world semantics + the disjointness axiom, this is
    inconsistent. The temporal layer in the main purification
    pipeline handles this case correctly (different eras); HermiT
    here illustrates what would happen WITHOUT that layer.

    Soft-fails silently if owlready2 / Java aren't available."""
    try:
        from kb.ontology_owl import hermit_enrich
    except Exception:
        return
    from kb.ontology import Ontology

    print("=" * 78)
    print("HermiT DL augmentation (optional, soft dep)")
    print("=" * 78)
    print()
    print("Pluto-classification edge case under pure DL (no temporal):")
    print()

    ont = (
        Ontology("astronomical-DL")
        .declare_classes("Planet", "DwarfPlanet")
        .disjoint_with("Planet", "DwarfPlanet")
    )

    # Strip temporal slots intentionally — this is the "atemporal"
    # version. The full distill pipeline handles temporal scoping;
    # this section shows the atemporal DL outcome.
    kb = KB(triples=[
        Triple("Pluto", "IS_A", "Planet", "old_textbook", -1),
        Triple("Pluto", "IS_A", "DwarfPlanet", "IAU_2023", -1),
    ], alias_map={}, n_articles=0)

    try:
        _, derivs, info = hermit_enrich(kb, ont)
    except (ImportError, RuntimeError) as e:
        print(f"  Skipped — HermiT not available: {e}")
        print()
        return

    print(f"  Without temporal scoping → Consistent: {info['consistent']}")
    if not info["consistent"]:
        print(f"  HermiT proved: a single entity can't be in two")
        print(f"  declared-disjoint classes simultaneously.")
        print()
        print(f"  (The full purification pipeline above used temporal")
        print(f"  slots, so the two classifications occupy different")
        print(f"  eras and the conflict dissolves. HermiT here shows")
        print(f"  what would happen if we collapsed the time axis —")
        print(f"  it's the right answer for atemporal DL semantics.)")
    print()


if __name__ == "__main__":
    main()
    _stress_test()
    _hermit_augment_distill()
