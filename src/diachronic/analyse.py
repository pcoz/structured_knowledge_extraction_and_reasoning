"""Diachronic analysis — tracking changing patterns of thinking about
the same subject material over time.

This demo answers a question most knowledge bases can't: "How has the
concept of *X* been ASSEMBLED differently across periods?" Not just
'what facts changed?' — but 'what counted as the right way to
organise the facts at all?'

The atom is the test subject. The same word — atom — has been
classified as an indivisible philosophical principle (Greeks), a
rejected hypothesis (Aristotelians), a small hard sphere (Newton),
a chemical accounting unit (Dalton), a composite structure with
parts (Rutherford / Bohr), and a quantum wave function (Schrödinger
/ Heisenberg). Each era didn't just learn new things — it
restructured what the subject was.

The analyzer surfaces:

  - **Schema drift**: which IS_A classifications hold in which eras,
    and the moments when the dominant classification changes.
  - **Property turnover**: which properties were affirmed in one era
    and explicitly rejected in another (e.g., 'indivisible' across
    the 1911 Rutherford reversal).
  - **Co-occurring vocabulary**: which surrounding concepts each era
    organised atoms around (philosophy → mechanics → chemistry →
    physics → quantum theory).
  - **Authorial lineages**: who explained atoms in each era — the
    historical figures attached to each paradigm.

Why this matters for knowledge representation, and why LLMs struggle
specifically with this kind of historical structure — the script
prints a prose explanation as part of its output.
"""

from __future__ import annotations

import sys
from collections import defaultdict, Counter
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parent))

from corpus import build_atom_kb, ERA_BOUNDARIES
from kb.query import KB, Triple
from kb.temporal import _parse_date, _YEAR_STRIDE


# ----------------------------------------------------------------------
# Per-era bucketing.
#
# A fact is "active in era E" if its validity interval overlaps E's
# boundary. We're permissive on overlap — a Newtonian-era fact that
# extends slightly into the Dalton era is still counted in Newton's
# era for the dominant-classification analysis.
# ----------------------------------------------------------------------


def _facts_in_era(kb: KB, era_from: int, era_to: int) -> list[Triple]:
    """Return all triples whose validity interval overlaps the era."""
    facts = []
    for t in kb.triples:
        f = _parse_date(t.valid_from)
        to = _parse_date(t.valid_to)
        # Treat unbounded endpoints as the relevant infinity.
        f_eff = f if f is not None else -10**9
        to_eff = to if to is not None else 10**9
        # Convert era's plain int years (signed; negative = BCE) to the
        # SAME scale as the parsed triple dates. Use the temporal module's
        # year stride rather than a hardcoded copy, so this never desyncs
        # when the date encoding changes.
        ef = era_from * _YEAR_STRIDE
        et = era_to * _YEAR_STRIDE
        if to_eff < ef or f_eff > et:
            continue
        facts.append(t)
    return facts


def _is_a_classes_in_era(kb: KB, era_from: int, era_to: int) -> set[str]:
    return {t.object for t in _facts_in_era(kb, era_from, era_to)
            if t.subject == "atom" and t.relation == "IS_A"}


def _properties_in_era(kb: KB, era_from: int, era_to: int) -> set[str]:
    return {t.object for t in _facts_in_era(kb, era_from, era_to)
            if t.subject == "atom" and t.relation == "HAS_PROPERTY"}


def _rejected_properties_in_era(kb: KB, era_from: int, era_to: int) -> set[str]:
    return {t.object for t in _facts_in_era(kb, era_from, era_to)
            if t.subject == "atom" and t.relation == "REJECTS_PROPERTY"}


def _explainers_in_era(kb: KB, era_from: int, era_to: int) -> set[str]:
    return {t.object for t in _facts_in_era(kb, era_from, era_to)
            if t.subject == "atom" and t.relation == "EXPLAINED_BY"}


def _vocabulary_in_era(kb: KB, era_from: int, era_to: int) -> set[str]:
    """All relation names used about 'atom' in this era — the era's
    organising verbs. Vocabulary drift across eras is one of the
    clearest fingerprints of paradigm shift."""
    return {t.relation for t in _facts_in_era(kb, era_from, era_to)
            if t.subject == "atom"}


def main() -> None:
    kb = build_atom_kb()

    print("=" * 78)
    print("Diachronic analysis: how 'atom' has been ASSEMBLED across 2,500 years")
    print("=" * 78)
    print()
    print(f"Corpus: {len(kb.triples)} dated triples drawn from primary sources")
    print(f"across six eras, spanning roughly 450 BCE to the present.")
    print()

    # ---- Per-era snapshots ----------------------------------------
    print("─" * 78)
    print("PER-ERA SNAPSHOTS — what the dominant view 'atom' was, era by era")
    print("─" * 78)
    print()

    for era_name, era_from, era_to in ERA_BOUNDARIES:
        classes = sorted(_is_a_classes_in_era(kb, era_from, era_to))
        props = sorted(_properties_in_era(kb, era_from, era_to))
        rejected = sorted(_rejected_properties_in_era(kb, era_from, era_to))
        explainers = sorted(_explainers_in_era(kb, era_from, era_to))
        vocab = sorted(_vocabulary_in_era(kb, era_from, era_to))
        era_label = f"{era_from:>5}..{era_to:<5}" if era_to < 9999 else f"{era_from:>5}..now  "

        print(f"  ┌─ {era_name}  ({era_label})")
        print(f"  │   IS_A:        {classes}")
        print(f"  │   properties:  {props}")
        if rejected:
            print(f"  │   *rejects:   {rejected}")
        print(f"  │   explained_by: {explainers}")
        print(f"  │   organising verbs: {vocab}")
        print(f"  └─")
        print()

    # ---- Schema drift: how IS_A changes era to era ---------------
    print("─" * 78)
    print("SCHEMA DRIFT — the classifications that held in each era")
    print("─" * 78)
    print()
    print("The same word 'atom' was a different KIND OF THING in each period.")
    print("This isn't just changed facts; the CATEGORY ITSELF was restructured:")
    print()

    prev_classes: set[str] = set()
    for era_name, era_from, era_to in ERA_BOUNDARIES:
        classes = _is_a_classes_in_era(kb, era_from, era_to)
        appeared = sorted(classes - prev_classes)
        disappeared = sorted(prev_classes - classes)
        prev_classes = classes
        print(f"  {era_name}")
        if appeared:
            print(f"    + new classifications: {appeared}")
        if disappeared:
            print(f"    - retired classifications: {disappeared}")
        if not appeared and not disappeared:
            print(f"    (no change from previous era)")
        print()

    # ---- The famous property reversal ----------------------------
    print("─" * 78)
    print("PROPERTY REVERSALS — properties held in one era, rejected in another")
    print("─" * 78)
    print()

    affirmed_by_era: dict[str, list[str]] = defaultdict(list)
    rejected_by_era: dict[str, list[str]] = defaultdict(list)
    for era_name, era_from, era_to in ERA_BOUNDARIES:
        for p in _properties_in_era(kb, era_from, era_to):
            affirmed_by_era[p].append(era_name)
        for p in _rejected_properties_in_era(kb, era_from, era_to):
            rejected_by_era[p].append(era_name)

    reversed_props = sorted(set(affirmed_by_era) & set(rejected_by_era))
    if reversed_props:
        for p in reversed_props:
            print(f"  '{p}'")
            print(f"     affirmed in: {affirmed_by_era[p]}")
            print(f"     rejected in: {rejected_by_era[p]}")
            print()
    else:
        print("  (none found)")
        print()

    # ---- Vocabulary drift ----------------------------------------
    print("─" * 78)
    print("VOCABULARY DRIFT — which organising verbs each era used")
    print("─" * 78)
    print()
    print("If the relations differ across eras, the SHAPE of the thinking")
    print("about the subject differs. Same subject, different conceptual")
    print("apparatus:")
    print()

    for era_name, era_from, era_to in ERA_BOUNDARIES:
        vocab = sorted(_vocabulary_in_era(kb, era_from, era_to))
        print(f"  {era_name}: {vocab}")
        print()

    # ---- Authorial lineages --------------------------------------
    print("─" * 78)
    print("AUTHORIAL LINEAGES — who organised each era's understanding")
    print("─" * 78)
    print()
    for era_name, era_from, era_to in ERA_BOUNDARIES:
        explainers = sorted(_explainers_in_era(kb, era_from, era_to))
        if explainers:
            print(f"  {era_name:<22s}  {explainers}")
    print()

    # ---- The deeper point ----------------------------------------
    print("=" * 78)
    print("WHY THIS MATTERS FOR KNOWLEDGE REPRESENTATION")
    print("=" * 78)
    print()
    print(_WHY_IT_MATTERS_PROSE.strip())
    print()
    print("=" * 78)
    print("WHY LLMS STRUGGLE WITH THIS, AND HOW SKEAR HANDLES IT")
    print("=" * 78)
    print()
    print(_LLM_FAILURE_PROSE.strip())
    print()
    print("=" * 78)


# ----------------------------------------------------------------------
# The embedded explanation that makes this a *teaching* example, not
# just a demo. Printed by main() as part of the run, so anyone who
# executes the script sees the rationale alongside the output.
# ----------------------------------------------------------------------


_WHY_IT_MATTERS_PROSE = """
Most knowledge bases pick one schema and live inside it. They model
'an atom' as a fixed thing with fixed properties — usually whichever
classification was current when the KB was built. They treat the
schema as background and the facts as foreground.

But real knowledge doesn't work that way. The way we ORGANISE a
concept — what we call it, what we say it's made of, what we relate
it to, what laws we say it obeys — is itself part of the knowledge.
And that organisation EVOLVES.

In the atom corpus above, every era used the same word 'atom' but
assembled it differently:

  - Greeks built it from indivisibility and eternity.
  - Aristotelians built it as an alternative they rejected.
  - Newtonians built it from mechanical properties (hard, massive).
  - Daltonians built it from chemical identity (atomic weight).
  - Rutherford/Bohr REVERSED the indivisibility and built it from parts.
  - Quantum theorists built it from a wave function.

A KB that flattens this — that gives one answer to 'what is an
atom?' — is committing to one paradigm and silently discarding the
others. For physics that might be tolerable. For domains where the
historical record matters (law, medicine, scholarship, regulatory
compliance, intellectual history), it's a quiet but corrosive lie.

A KB that explicitly carries the temporal scope, the source-era
authority, and the schema-as-data lets you ask the actual questions:
'what did doctors believe about X in 1955?'; 'when did the
classification of Y shift?'; 'who was the first to reject property
Z?'. These aren't fact-retrieval questions. They're questions about
THE EVOLUTION OF UNDERSTANDING — and they require a representation
where the schema can carry a date and a source.
"""

_LLM_FAILURE_PROSE = """
LLMs are trained on a corpus that BLENDS every era together. Greek
atomism, Newtonian mechanics, Daltonian chemistry, and quantum
theory all live in the same weight space. When you ask 'what is an
atom?', the model produces a smooth confident answer that draws
from the entire blend — usually weighted toward whatever's most
common in the training data (modern textbook physics) but with no
guarantee.

Three specific failures the diachronic analysis above would catch:

  1. **Era-mixing.** Ask an LLM 'what did 18th-century scientists
     think atoms were made of?' and you can get an answer that
     references electrons or quantum states — concepts that didn't
     exist in the 18th century. The model has no internal switch
     for 'restrict to era X'. The temporal slot on every SKEAR
     triple is exactly that switch.

  2. **Reversal-erasure.** The fact that Rutherford's 1911 result
     made the 'indivisible' property of atoms WRONG is one of the
     most important moments in the history of science. An LLM may
     describe atoms today as 'made of subatomic particles' without
     ever flagging that this is a reversal of what the word meant
     for 2,000+ years. SKEAR's REJECTS_PROPERTY relation, with its
     own valid_from date, makes the reversal a queryable event.

  3. **Schema-flattening.** Ask 'how has the concept of the atom
     evolved?' to an LLM and you'll get fluent prose. But the
     answer is a *synthesis* of training data, not a record of who
     said what when. The structural fact that the IS_A class
     changed — from PhilosophicalCategory to PhysicalObject to
     ChemicalElement to CompositeStructure to QuantumSystem — is
     not preserved as STRUCTURE. SKEAR keeps that as actual data:
     five different IS_A triples, each with its own era.

How SKEAR handles it, mechanically:

  - **Temporal slots on every Triple.** valid_from / valid_to scope
    each assertion to its period. The same subject 'atom' carries
    incompatible classifications across eras without being self-
    contradictory at any single moment.

  - **Schema-as-data.** IS_A and ORGANIZED_AS are first-class
    relations, not metadata. The era's *way of thinking* (the
    schema) is preserved alongside the era's facts.

  - **Source provenance per assertion.** source_article on each
    Triple identifies the era's authoritative voice. The
    AuthorityWinsPolicy in the conflict module respects which
    source is canonical for which era.

  - **Conflict detection without flattening.** Functional axioms on
    IS_A would normally flag five different classifications as a
    contradiction. With temporal scoping (`intersects` in
    src/kb/temporal.py), the same five classifications coexist
    cleanly — they're not contradictory, they're sequential.

  - **Query-time time-travel.** valid_at(triple, '1750-01-01')
    returns the Newtonian-era classification; valid_at the same
    triple at '1820-01-01' returns Dalton's. The same KB serves
    different temporal queries with different answers — none
    fabricated.

The atom example is one subject. The same machinery applies to
every concept whose understanding has shifted over time: 'matter',
'gravity', 'mind', 'species', 'race', 'sovereignty', 'marriage',
'evidence'. Knowledge representation that takes history seriously
needs schema-as-data + temporal scope. SKEAR has both.
"""


# ----------------------------------------------------------------------
# Assertion-backed stress tests.
# ----------------------------------------------------------------------


def _stress_test() -> None:
    print()
    print("=" * 78)
    print("Diachronic-analysis stress tests")
    print("=" * 78)
    print()

    kb = build_atom_kb()

    # Scenario 1: the corpus exists and is non-trivial.
    print("Scenario 1: corpus loads with multi-era facts")
    eras_with_facts = [
        e for e in ERA_BOUNDARIES
        if _facts_in_era(kb, e[1], e[2])
    ]
    assert len(eras_with_facts) >= 5, (
        f"FAIL: expected facts in ≥5 eras, got {len(eras_with_facts)}"
    )
    print(f"  PASS: {len(eras_with_facts)} eras represented in corpus")
    print()

    # Scenario 2: schema drift — different IS_A classes per era.
    print("Scenario 2: 'atom' carries different IS_A classes across eras")
    seen_classes_per_era = {}
    for era_name, ef, et in ERA_BOUNDARIES:
        classes = _is_a_classes_in_era(kb, ef, et)
        if classes:
            seen_classes_per_era[era_name] = classes
    # No two eras should have identical class sets — that would
    # indicate the corpus isn't actually capturing paradigm shifts.
    all_class_sets = [frozenset(s) for s in seen_classes_per_era.values()]
    assert len(set(all_class_sets)) >= 4, (
        f"FAIL: expected ≥4 distinct IS_A class sets across eras"
    )
    print(f"  PASS: {len(set(all_class_sets))} distinct IS_A class sets across "
          f"{len(seen_classes_per_era)} populated eras")
    print()

    # Scenario 3: indivisible-reversal — the famous Rutherford moment.
    print("Scenario 3: 'indivisible' is affirmed in early eras, "
          "rejected in Rutherford+")
    affirmed = []
    rejected = []
    for era_name, ef, et in ERA_BOUNDARIES:
        if "indivisible" in _properties_in_era(kb, ef, et):
            affirmed.append(era_name)
        if "indivisible" in _rejected_properties_in_era(kb, ef, et):
            rejected.append(era_name)
    print(f"  Affirmed in: {affirmed}")
    print(f"  Rejected in: {rejected}")
    assert affirmed and rejected, (
        f"FAIL: expected both affirmed and rejected eras for 'indivisible'"
    )
    # Affirmation and rejection should not overlap in the same era.
    assert not (set(affirmed) & set(rejected)), (
        f"FAIL: same era both affirms and rejects 'indivisible'"
    )
    print(f"  PASS: clean affirmation → rejection trajectory")
    print()

    # Scenario 4: temporal scoping prevents false conflict on IS_A.
    # If we ran HermiT (or our functional-property axiom) over the
    # whole corpus without temporal scoping, we'd see five "atom is
    # in two disjoint classes" violations. With temporal scoping, the
    # classifications coexist sequentially.
    print("Scenario 4: temporal scoping prevents flattening into conflict")
    from kb.temporal import intersects, Interval
    is_a_triples = [t for t in kb.triples
                    if t.subject == "atom" and t.relation == "IS_A"]
    # Pair up; count overlapping intervals.
    overlapping_pairs = 0
    distinct_pairs = 0
    for i, t1 in enumerate(is_a_triples):
        for t2 in is_a_triples[i + 1:]:
            distinct_pairs += 1
            if intersects(
                Interval(t1.valid_from, t1.valid_to),
                Interval(t2.valid_from, t2.valid_to),
            ):
                overlapping_pairs += 1
    print(f"  Distinct IS_A pairs:    {distinct_pairs}")
    print(f"  Temporally overlapping: {overlapping_pairs}")
    # Most pairs should NOT overlap — each era's classes belong to
    # that era only. Some overlap (e.g., Rutherford's CompositeStructure
    # extending into the quantum era) is OK.
    assert overlapping_pairs < distinct_pairs / 2, (
        f"FAIL: too many overlapping IS_A pairs — the eras aren't separated"
    )
    print(f"  PASS: most pairs are temporally disjoint (sequential, not "
          f"contradictory)")
    print()

    # Scenario 5: vocabulary drift — different relations per era.
    # This is the schema-as-data effect: the ORGANISING VERBS change.
    print("Scenario 5: organising vocabulary drifts across eras")
    vocab_per_era = {
        e[0]: _vocabulary_in_era(kb, e[1], e[2])
        for e in ERA_BOUNDARIES
    }
    populated_vocabs = {n: v for n, v in vocab_per_era.items() if v}
    # Compute pairwise jaccard distance; expect non-trivial diversity.
    eras = list(populated_vocabs.keys())
    distances = []
    for i in range(len(eras)):
        for j in range(i + 1, len(eras)):
            a = populated_vocabs[eras[i]]
            b = populated_vocabs[eras[j]]
            j_sim = len(a & b) / len(a | b) if (a | b) else 1.0
            distances.append(1.0 - j_sim)
    avg_dist = sum(distances) / len(distances) if distances else 0.0
    print(f"  Average pairwise vocabulary drift (Jaccard distance): "
          f"{avg_dist:.2f}")
    assert avg_dist > 0.3, (
        f"FAIL: vocabulary too similar across eras ({avg_dist:.2f})"
    )
    print(f"  PASS: eras use measurably different organising verbs")
    print()

    print("=" * 78)
    print("All diachronic-analysis stress-test assertions passed.")
    print("=" * 78)


if __name__ == "__main__":
    main()
    _stress_test()
