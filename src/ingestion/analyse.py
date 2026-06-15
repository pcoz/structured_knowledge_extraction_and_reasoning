"""Ingestion worked example — importing self-contradictory data.

We try to import four "authoritative" source exports for one asset into a
single coherent record. The naive append looks fine. But computing the
logical closure on import surfaces three contradictions — one of them
LATENT (no single triple is wrong; the inconsistency only appears after the
taxonomy is applied) — each traced back to the exact source sentences that
produced it.

The point: importing into a structured, reasoning KB does not silently
absorb contradictory knowledge. It locates the self-contradiction in the
source data and proves it, so you can fix the source, route the genuinely
perspectival differences to scoped microtheories, or surface-for-review —
deliberately, rather than shipping an incoherent KB.

Run (from src/):  python -m ingestion.analyse
"""
from __future__ import annotations

import sys

from kb.conflict import (apply_with_conflict_resolution, ChainPolicy,
                         AuthorityWinsPolicy, HighestConfidencePolicy,
                         SurfaceForReviewPolicy)
from ingestion.corpus import (build_import_kb, build_ontology, ASSET, SOURCES)

LINE = "=" * 78


def _trace_sources(triple, deriv_by_output):
    """Walk a (possibly derived) triple back to the originating source
    sentences. Returns a sorted list of 'source#sentence' strings."""
    key = (triple.subject, triple.relation, triple.object)
    if key not in deriv_by_output:
        if triple.source_article and triple.source_article != "(derived)":
            return [f"{triple.source_article}#{triple.source_sentence_idx}"]
        return []
    out = []
    for inp in deriv_by_output[key].inputs:
        out.extend(_trace_sources(inp, deriv_by_output))
    return sorted(set(out))


def main() -> None:
    kb = build_import_kb()
    onto = build_ontology()
    failures = 0

    print(LINE)
    print("INGESTION WORKED EXAMPLE — importing self-contradictory data")
    print(LINE)

    print(f"\nImporting {len(kb.triples)} records for {ASSET} from {len(SOURCES)} sources:")
    for s in SOURCES:
        print(f"   - {s}")
    print("\nNaive append: every record loads without error. The raw triples look")
    print("individually plausible — no source is obviously wrong.")

    # --- Import = compute the closure + detect contradictions ----------
    newkb, derivs, conflicts, _ = apply_with_conflict_resolution(
        kb, ontology=onto, policy=ChainPolicy([AuthorityWinsPolicy(),
                                               HighestConfidencePolicy()]))
    deriv_by_output = {(d.output.subject, d.output.relation, d.output.object): d
                       for d in derivs}

    print("\n--- On import, computing the logical closure surfaces: ---")
    print(f"    {len(conflicts)} contradiction(s) in what looked like clean data.\n")

    kinds = sorted({c.kind for c in conflicts})
    for c in conflicts:
        print(f"  [{c.kind}] {c.detail}")
        # which source sentences are implicated?
        srcs = sorted(set(sum((_trace_sources(t, deriv_by_output) for t in c.triples), [])))
        print(f"      traces to source sentences: {srcs}")
        # if it was derived (latent), show the reasoning trail
        if c.marker is not None:
            chain = deriv_by_output.get((c.marker.subject, "CONTRADICTION_DETECTED", c.marker.object))
        print()

    # --- Spotlight the LATENT one with its "since X therefore Y" proof --
    print("--- The latent contradiction, proved step by step ---")
    contradiction_derivs = [d for d in derivs
                            if d.output.relation == "CONTRADICTION_DETECTED"]
    subclass_derivs = [d for d in derivs
                       if d.output.relation == "IS_A" and d.output.source_article == "(derived)"]
    for d in subclass_derivs:
        print(f"   • {d.explanation}")
    for d in contradiction_derivs:
        print(f"   ✗ {d.explanation}")
    print("   => PUMP-7 is asserted to be BOTH a rotodynamic machine (via vendor_export_A's")
    print("      'CentrifugalPump') AND a positive-displacement machine (via vendor_export_B's")
    print("      'PositiveDisplacementPump') — physically impossible. Neither source is wrong")
    print("      alone; the contradiction lives in their combination.")

    # --- The difficulty: a consistent merge must DISCARD sourced data --
    print("\n--- The difficulty of importing anyway ---")
    review_kb, _, review_conflicts, _ = apply_with_conflict_resolution(
        kb, ontology=onto, policy=SurfaceForReviewPolicy())
    print("    To produce a single consistent record you must either:")
    print("      (a) resolve by policy — which DISCARDS sourced facts (data loss):")
    resolved_kb, _, _, _ = apply_with_conflict_resolution(
        kb, ontology=onto, policy=ChainPolicy([AuthorityWinsPolicy(),
                                               HighestConfidencePolicy()]))
    kept_flow = sorted({t.object for t in resolved_kb.triples if t.relation == "RATED_FLOW_GPM"})
    print(f"          e.g. RATED_FLOW_GPM resolves to {kept_flow} — the other sourced value is dropped;")
    print("      (b) SurfaceForReview — keep the conflict flagged for a human "
          f"({len(review_conflicts)} flagged); or")
    print("      (c) recognise these are NOT legitimate framings (a pump can't be both")
    print("          machine types) — so scoping them as microtheories would be WRONG;")
    print("          the data must be corrected at the source.")

    # --- assertions ----------------------------------------------------
    has_disjoint = any(c.kind == "disjoint_class" for c in conflicts)
    has_functional = any(c.kind == "functional" for c in conflicts)
    has_latent = len(contradiction_derivs) >= 1
    for name, cond in [("disjoint-class contradiction surfaced", has_disjoint),
                       ("functional contradiction surfaced", has_functional),
                       ("latent (derived) contradiction surfaced via closure", has_latent),
                       ("latent one required a derivation step", len(subclass_derivs) >= 1)]:
        print(f"\n  {'PASS' if cond else 'FAIL'}  {name}")
        failures += (not cond)

    print("\n" + LINE)
    print("ALL ASSERTIONS PASSED." if failures == 0 else f"{failures} ASSERTION(S) FAILED.")
    print(
        "Takeaway: structured import is a consistency CHECKPOINT. A store that merely\n"
        "appends-and-serves would absorb all four sources and answer queries from an\n"
        "internally self-contradictory record — silently. Computing the closure on\n"
        "import makes the source's self-contradiction explicit, located, and provable,\n"
        "so it can be fixed rather than served."
    )
    print(LINE)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
