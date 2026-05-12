"""Apply the kb.reason engine to Ahab's utterance corpus.

Same fixpoint + disjunctive-rule + stratified-negation engine as the
Wikipedia knowledge graph (`src/kb/reason.py`) — different data shape.
Builds a graph from the utterance metadata (themes, addressee, speech-
act, mood) and derives:

  - Theme co-occurrence and its transitive closure (fixpoint)
  - A unified speech-label relation pulled from speech-act ∪ mood
    (DisjunctiveRule — alternative antecedent relations, one consequent)
  - Confrontational vs introspective utterances
    (function-form disjunction over object values)
  - Isolated themes that never co-occur with another (negation-as-failure)

Demonstrates that the engine generalises from encyclopedic KGs to
conversational metadata. Same code paths, different domain.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# sys.path manipulation so the script runs whether invoked as
# `python src/ahab/reason.py` from the repo root or from inside src/.
# The two inserts give us both the sibling `utterances` module and
# the `kb` package one directory up.
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parent))

from utterances import AHAB_UTTERANCES, Utterance
from kb.query import KB, Triple
from kb.reason import (
    Rule, DisjunctiveRule, Derivation, kb_has,
    apply_all_rules_to_fixpoint,
)
from kb.ontology import Ontology
from kb.conflict import apply_with_conflict_resolution, KeepAllPolicy


# ----------------------------------------------------------------------
# Build a KB from utterance metadata.
# ----------------------------------------------------------------------


def _theme_frequencies(utterances: list[Utterance]) -> Counter:
    """How often each theme appears across the corpus. Used to assign
    per-theme confidence: frequently-attested themes are treated as
    more reliably annotated than themes mentioned once."""
    c: Counter = Counter()
    for u in utterances:
        for theme in u.themes:
            c[theme] += 1
    return c


def _theme_confidence(freq: int, max_freq: int) -> float:
    """Map a theme's corpus frequency to a confidence in [0.5, 1.0].

    A log-scale: rare themes (one mention) get the floor 0.5; the
    most-attested theme gets 1.0; everything else interpolates
    smoothly. Log rather than linear so a theme appearing 10 times
    is treated as much more reliable than one appearing once — but
    not 10× more reliable, which would be too aggressive."""
    import math
    if max_freq <= 1 or freq <= 0:
        return 1.0
    return 0.5 + 0.5 * (math.log(freq) / math.log(max_freq))


def build_utterance_kb(utterances: list[Utterance]) -> KB:
    """Project each Utterance into 4-5 triples keyed by a synthetic
    utterance id ("u00".."u34").

    HAS_THEME triples carry a confidence reflecting how often the
    theme appears in the corpus — frequently-attested themes are
    treated as more reliably annotated than themes mentioned once.
    The engine propagates this confidence through derivation chains
    (theme co-occurrence → transitive thematic reach), so chains
    through rare themes carry visibly lower confidence than chains
    through common ones.

    Source_sentence_idx slot holds the utterance index — derived
    facts can be traced back to the specific utterance (the closest
    analogue to Wikipedia's source_article + sentence_idx for this
    corpus)."""
    freq = _theme_frequencies(utterances)
    max_freq = max(freq.values()) if freq else 1

    triples: list[Triple] = []
    for i, u in enumerate(utterances):
        uid = f"u{i:02d}"
        for theme in u.themes:
            conf = _theme_confidence(freq[theme], max_freq)
            triples.append(Triple(
                uid, "HAS_THEME", theme, "Moby-Dick", i,
                confidence=conf,
            ))
        # The other utterance metadata (addressee, speech-act, mood)
        # stays at default confidence 1.0 — they're direct facts about
        # the utterance, not interpretive labels like themes.
        triples.append(Triple(uid, "ADDRESSED_TO", u.addressee, "Moby-Dick", i))
        triples.append(Triple(uid, "IS_SPEECH_ACT", u.speech_act, "Moby-Dick", i))
        triples.append(Triple(uid, "HAS_MOOD", u.mood, "Moby-Dick", i))
    return KB(triples=triples, alias_map={}, n_articles=len(utterances))


# ----------------------------------------------------------------------
# Rules.
# ----------------------------------------------------------------------


def r_theme_co_occurrence(kb: KB) -> list[Derivation]:
    """Same-utterance theme pairs → CO_OCCURS_WITH (one direction).

    Emits CO_OCCURS_WITH(T1, T2) for every theme pair sharing an
    utterance, with T1 < T2 lexicographically. The OWL ontology
    declares CO_OCCURS_WITH symmetric, so the reverse direction
    auto-derives — saves us emitting both halves manually.

    Confidence is propagated: a derived CO_OCCURS_WITH inherits the
    noisy-AND of its two input HAS_THEME confidences (which are
    set by the corpus-frequency heuristic in build_utterance_kb).
    Rare themes co-occurring with rare themes get visibly lower
    confidence than two common themes' co-occurrence."""
    out: list[Derivation] = []
    # Group themes by utterance to avoid the cross-utterance O(N²).
    themes_by_utt: dict[str, list[Triple]] = defaultdict(list)
    for t in kb.triples:
        if t.relation == "HAS_THEME":
            themes_by_utt[t.subject].append(t)
    # Emit each unordered pair once across the corpus — OWL's
    # symmetric_property axiom will produce the reverse direction.
    seen: set[tuple[str, str]] = set()
    for uid, theme_triples in themes_by_utt.items():
        # Sort so we always emit (low, high) — deterministic and
        # avoids needing to canonicalise pairs later.
        sorted_themes = sorted(theme_triples, key=lambda t: t.object)
        for i, t1 in enumerate(sorted_themes):
            for t2 in sorted_themes[i + 1:]:
                key = (t1.object, t2.object)
                if key in seen:
                    continue
                seen.add(key)
                derived = Triple(
                    t1.object, "CO_OCCURS_WITH", t2.object, "(derived)", -1,
                )
                expl = (
                    f"Themes '{t1.object}' and '{t2.object}' both appear "
                    f"in utterance {uid}."
                )
                out.append(Derivation("r_theme_co_occurrence",
                                       derived, [t1, t2], expl))
    return out


# ----------------------------------------------------------------------
# Ontology — declarative replacement for the old r_thematic_reach.
#
# Two OWL axioms in place of one Python function:
#   - CO_OCCURS_WITH is symmetric: r_theme_co_occurrence emits one
#     direction; the symmetric axiom derives the other.
#   - CO_OCCURS_WITH ⊑ THEMATICALLY_REACHES (sub-property): every
#     co-occurrence is also a thematic reach. This is the base case
#     for transitive closure.
#   - THEMATICALLY_REACHES is transitive: closes the relation.
#
# Functional axioms also surface metadata anomalies — if an
# extraction ever assigned multiple addressees/speech-acts/moods to
# one utterance, the conflict module would flag it.
# ----------------------------------------------------------------------


ONTOLOGY = (
    Ontology("ahab")
    .symmetric_property("CO_OCCURS_WITH")
    .sub_property_of("CO_OCCURS_WITH", "THEMATICALLY_REACHES")
    .transitive_property("THEMATICALLY_REACHES")
    # Each utterance has exactly one addressee, speech-act, and mood.
    # If the corpus ever asserted two, the OWL functional rule emits
    # CONFLICT_FUNCTIONAL — surfaced by conflict.detect_conflicts.
    .functional_property("ADDRESSED_TO")
    .functional_property("IS_SPEECH_ACT")
    .functional_property("HAS_MOOD")
)


# Speech-label: collapse two metadata channels (speech-act + mood) into a
# single 'HAS_SPEECH_LABEL' relation. Showcases DisjunctiveRule's
# alternative-relations shape: same consequent, different antecedent
# relation names.
R_SPEECH_LABEL = DisjunctiveRule(
    name="r_speech_label",
    alternatives=["IS_SPEECH_ACT", "HAS_MOOD"],
    consequent="HAS_SPEECH_LABEL",
    explanation_template=(
        "Utterance {subject} has speech-label '{object}' "
        "(via {via})."
    ),
)


def r_confrontational(kb: KB) -> list[Derivation]:
    """speech-act ∈ {oath, command, declaration, curse} → CONFRONTATIONAL.

    Disjunction over object values (not antecedent relations), so
    expressed as a Python function. The set membership IS the
    disjunction. DisjunctiveRule's relation-set shape would not capture
    this cleanly without extra machinery."""
    confrontational = {"oath", "command", "declaration", "curse"}
    out: list[Derivation] = []
    for t in kb.triples:
        if t.relation != "IS_SPEECH_ACT" or t.object not in confrontational:
            continue
        derived = Triple(
            t.subject, "IS", "CONFRONTATIONAL_UTTERANCE", "(derived)", -1,
        )
        expl = (
            f"Utterance {t.subject} is a {t.object} — a confrontational "
            f"speech-act."
        )
        out.append(Derivation("r_confrontational", derived, [t], expl))
    return out


def r_introspective(kb: KB) -> list[Derivation]:
    """mood ∈ {melancholy, anguished, reflective, philosophical,
    contemplative, bitter} → INTROSPECTIVE."""
    introspective = {"melancholy", "anguished", "reflective",
                     "philosophical", "contemplative", "bitter"}
    out: list[Derivation] = []
    for t in kb.triples:
        if t.relation != "HAS_MOOD" or t.object not in introspective:
            continue
        derived = Triple(
            t.subject, "IS", "INTROSPECTIVE_UTTERANCE", "(derived)", -1,
        )
        expl = f"Utterance {t.subject} has {t.object} mood — introspective."
        out.append(Derivation("r_introspective", derived, [t], expl))
    return out


def r_isolated_theme(kb: KB) -> list[Derivation]:
    """A theme is ISOLATED if no CO_OCCURS_WITH relation involves it.

    Negation-as-failure: stratum 1, runs after the positive theme
    co-occurrence rule has converged. Closed-world — sound only on
    the corpus as given."""
    all_themes = {t.object for t in kb.triples if t.relation == "HAS_THEME"}
    out: list[Derivation] = []
    for theme in sorted(all_themes):
        if kb_has(kb, theme, "CO_OCCURS_WITH"):
            continue
        derived = Triple(theme, "IS", "ISOLATED_THEME", "(derived)", -1)
        expl = (
            f"Theme '{theme}' appears in the corpus but does not "
            f"co-occur with any other theme (closed-world)."
        )
        out.append(Derivation("r_isolated_theme", derived, [], expl))
    return out


def r_peaceful_addressee(kb: KB) -> list[Derivation]:
    """An addressee X is PEACEFUL if no utterance addressed to X is
    CONFRONTATIONAL. Stratum 1 — runs after r_confrontational (stratum 0)
    has produced its classifications.

    Demonstrates negation-as-failure over a derived predicate: the
    absence we're checking ("no confrontational utterance for this
    addressee") refers to facts another rule produced earlier in the
    pipeline. Stratification keeps the result well-defined."""
    addressees = {t.object for t in kb.triples if t.relation == "ADDRESSED_TO"}
    confrontational_addressees: set[str] = set()
    for t in kb.triples:
        if t.relation != "ADDRESSED_TO":
            continue
        for rel, obj, _ in kb.out_edges.get(t.subject, []):
            if rel == "IS" and obj == "CONFRONTATIONAL_UTTERANCE":
                confrontational_addressees.add(t.object)
                break
    out: list[Derivation] = []
    for addr in sorted(addressees - confrontational_addressees):
        derived = Triple(addr, "IS", "PEACEFUL_ADDRESSEE", "(derived)", -1)
        expl = (
            f"No utterance addressed to '{addr}' is confrontational "
            f"(closed-world over derived classifications)."
        )
        out.append(Derivation("r_peaceful_addressee", derived, [], expl))
    return out


RULES = [
    # Co-occurrence is hand-written because it bridges from the
    # domain-specific HAS_THEME shape to the generic CO_OCCURS_WITH —
    # OWL axioms can't see inside an utterance.
    Rule("r_theme_co_occurrence", r_theme_co_occurrence),
    # The disjunctive speech-label rule stays — collapsing two
    # metadata channels into one is the natural DisjunctiveRule shape.
    R_SPEECH_LABEL.to_rule(),
    # Classification rules stay as Python — disjunction over object
    # values (mood ∈ {introspective set}) is the natural function form.
    Rule("r_confrontational", r_confrontational),
    Rule("r_introspective", r_introspective),
    # Stratum-1 negation rules stay — negation isn't OWL-shaped.
    Rule("r_isolated_theme", r_isolated_theme, stratum=1),
    Rule("r_peaceful_addressee", r_peaceful_addressee, stratum=1),
]


# ----------------------------------------------------------------------
# Demo.
# ----------------------------------------------------------------------


def main() -> None:
    print("=" * 78)
    print("Captain Ahab — reasoning over the utterance corpus")
    print("=" * 78)
    print()
    print("Same engine as src/kb/reason.py, applied to conversational")
    print("metadata. Shows that fixpoint + disjunction + stratified")
    print("negation generalise beyond encyclopedic knowledge graphs.")
    print()

    kb = build_utterance_kb(AHAB_UTTERANCES)
    n_themes = len({t.object for t in kb.triples if t.relation == "HAS_THEME"})
    print(f"  Built KB: {len(kb.triples):,} base triples from "
          f"{len(AHAB_UTTERANCES)} utterances "
          f"({n_themes} distinct themes).")
    print()

    # Run the full pipeline: hand-rules + OWL ontology + (vacuous)
    # conflict resolution. The ontology declares the property
    # characteristics; the engine compiles them into rules and runs
    # them alongside the hand-written ones.
    kb_ext, derivations, conflicts, stats = apply_with_conflict_resolution(
        kb, rules=RULES, ontology=ONTOLOGY, policy=KeepAllPolicy(),
    )
    print("FIXPOINT CONVERGENCE")
    print("-" * 78)
    print(f"  Stratum 0 iterations:  {stats['stratum_0_iters']} "
          f"(per-iter new facts: {stats['stratum_0_per_iter']})")
    print(f"  Stratum 1 derivations: {stats['stratum_1_count']}")
    print(f"  Conflicts detected:    {stats['conflicts_detected']}")
    print(f"  Total triples after reasoning: {len(kb_ext.triples):,}")
    print()

    by_rule: dict[str, int] = defaultdict(int)
    for d in derivations:
        by_rule[d.rule_name] += 1
    print("DERIVATIONS BY RULE")
    print("-" * 78)
    for rule_name, n in by_rule.items():
        print(f"  {rule_name:<32s} {n:>5d}")
    print()

    # --- Fixpoint demo: transitive theme reach (via OWL axioms). ---
    print("FIXPOINT VIA OWL: TRANSITIVE THEME CLOSURES")
    print("-" * 78)
    print("  (The OWL ontology declared CO_OCCURS_WITH symmetric and")
    print("   sub-property of the transitive THEMATICALLY_REACHES.")
    print("   The hand-written r_thematic_reach is now redundant — the")
    print("   engine closes the chain from the declarative axioms alone.)")
    print()
    for seed in ["whale", "vengeance", "soul", "weariness", "fate"]:
        direct = sorted({
            t.object for t in kb_ext.out_facts(seed, "CO_OCCURS_WITH")
        })
        reach = sorted({
            t.object for t in kb_ext.out_facts(seed, "THEMATICALLY_REACHES")
        })
        print(f"  '{seed}': directly co-occurs with {len(direct)} themes, "
              f"transitively reaches {len(reach)}")
        new_via_closure = sorted(set(reach) - set(direct))
        if new_via_closure:
            print(f"    new via closure: {new_via_closure[:6]}"
                  f"{'...' if len(new_via_closure) > 6 else ''}")
    print()

    # --- Confidence attenuation through transitive chains. ---
    print("CONFIDENCE ATTENUATION THROUGH TRANSITIVE CHAINS")
    print("-" * 78)
    print("  (HAS_THEME confidence is set from theme frequency in the")
    print("   corpus — common themes are treated as more reliably")
    print("   annotated. The engine propagates noisy-AND through every")
    print("   derivation, so longer transitive reach chains carry")
    print("   visibly lower confidence.)")
    print()
    # Show the confidence of a few direct vs transitive reaches.
    # 'fate' is the most-attested theme; chains through it should
    # carry higher confidence than chains through 'anguish' (one
    # mention only).
    samples = []
    for t in kb_ext.triples:
        if t.relation != "THEMATICALLY_REACHES":
            continue
        if t.subject in ("scar", "weariness") and t.confidence < 1.0:
            samples.append(t)
    samples.sort(key=lambda t: t.confidence)
    print(f"  Lowest-confidence THEMATICALLY_REACHES facts "
          f"(showing 6 of {len(samples)}):")
    for t in samples[:6]:
        print(f"    {t.subject:<10s} -> {t.object:<15s} "
              f"conf={t.confidence:.3f}")
    print()
    # Show that HAS_THEME confidences vary.
    theme_conf: dict[str, float] = {}
    for t in kb_ext.triples:
        if t.relation == "HAS_THEME":
            theme_conf[t.object] = t.confidence
    by_conf = sorted(theme_conf.items(), key=lambda x: x[1])
    print("  HAS_THEME confidences (least to most attested):")
    for theme, conf in by_conf[:4]:
        print(f"    '{theme}'  conf={conf:.3f}")
    print("    ...")
    for theme, conf in by_conf[-2:]:
        print(f"    '{theme}'  conf={conf:.3f}")
    print()

    # --- Disjunctive rule (alternative relations). ---
    print("DISJUNCTIVE RULE: HAS_SPEECH_LABEL (IS_SPEECH_ACT ∪ HAS_MOOD)")
    print("-" * 78)
    n_labels = sum(1 for t in kb_ext.triples
                   if t.relation == "HAS_SPEECH_LABEL")
    distinct_labels = sorted({
        t.object for t in kb_ext.triples if t.relation == "HAS_SPEECH_LABEL"
    })
    print(f"  Total HAS_SPEECH_LABEL facts: {n_labels} "
          f"({len(distinct_labels)} distinct labels)")
    print(f"  Sample labels: {distinct_labels[:10]}")
    # An example utterance and its labels.
    u0_labels = sorted({
        t.object for t in kb_ext.out_facts("u00", "HAS_SPEECH_LABEL")
    })
    u00 = AHAB_UTTERANCES[0]
    print(f"  u00 (\"{u00.text[:50]}...\"): labels = {u0_labels}")
    print()

    # --- Function-form disjunction over object values. ---
    print("CLASSIFICATION (function-form disjunction over object values)")
    print("-" * 78)
    confrontational = [
        t.subject for t in kb_ext.triples
        if t.relation == "IS" and t.object == "CONFRONTATIONAL_UTTERANCE"
    ]
    introspective = [
        t.subject for t in kb_ext.triples
        if t.relation == "IS" and t.object == "INTROSPECTIVE_UTTERANCE"
    ]
    overlap = sorted(set(confrontational) & set(introspective))
    only_conf = sorted(set(confrontational) - set(introspective))
    only_intr = sorted(set(introspective) - set(confrontational))
    print(f"  Confrontational only:  {len(only_conf):>2d}")
    print(f"  Introspective only:    {len(only_intr):>2d}")
    print(f"  Both (rare):           {len(overlap):>2d}")
    if overlap:
        for uid in overlap[:3]:
            idx = int(uid[1:])
            u = AHAB_UTTERANCES[idx]
            print(f"    {uid} (Ch.{u.chapter}, {u.speech_act}/{u.mood}): "
                  f"\"{u.text[:55]}...\"")
    print()

    # --- Negation-as-failure: isolated themes (often empty — that
    # is itself a meaningful answer the engine can give deterministically). ---
    print("NEGATION-AS-FAILURE (1): ISOLATED THEMES")
    print("-" * 78)
    isolated = sorted({
        t.subject for t in kb_ext.triples
        if t.relation == "IS" and t.object == "ISOLATED_THEME"
    })
    if isolated:
        for theme in isolated:
            count = sum(
                1 for t in kb_ext.triples
                if t.relation == "HAS_THEME" and t.object == theme
            )
            print(f"  → '{theme}' (appears {count}× but never with another theme)")
    else:
        print(f"  (none — every theme co-occurs with at least one other)")
    print()

    # --- Negation over a derived predicate. ---
    print("NEGATION-AS-FAILURE (2): PEACEFUL ADDRESSEES")
    print("-" * 78)
    print("  (addressees who never receive a confrontational utterance —")
    print("   negation over the CONFRONTATIONAL classification derived")
    print("   earlier in the pipeline)")
    peaceful = sorted({
        t.subject for t in kb_ext.triples
        if t.relation == "IS" and t.object == "PEACEFUL_ADDRESSEE"
    })
    for addr in peaceful:
        n = sum(1 for t in kb_ext.triples
                if t.relation == "ADDRESSED_TO" and t.object == addr)
        print(f"  → '{addr}' ({n} utterance(s) addressed; none confrontational)")
    print()

    # --- "Why?" trace: pick a transitively-reached pair, not a direct
    # co-occurrence, to make the fixpoint chain visible. ---
    print("\"WHY?\" TRACE FOR A TRANSITIVELY-DERIVED FACT")
    print("-" * 78)
    direct_pairs = {
        (t.subject, t.object) for t in kb_ext.triples
        if t.relation == "CO_OCCURS_WITH"
    }
    target = None
    for t in kb_ext.triples:
        if t.relation != "THEMATICALLY_REACHES":
            continue
        if (t.subject, t.object) in direct_pairs:
            continue
        # Prefer a pair that the casual reader can sanity-check.
        if t.subject in {"weariness", "scar", "doubt"}:
            target = (t.subject, t.relation, t.object)
            break
    if target is None:
        # Fallback to any transitively-only pair.
        for t in kb_ext.triples:
            if t.relation != "THEMATICALLY_REACHES":
                continue
            if (t.subject, t.object) not in direct_pairs:
                target = (t.subject, t.relation, t.object)
                break
    if target is not None:
        trace = [d for d in derivations
                 if (d.output.subject, d.output.relation, d.output.object) == target]
        d = trace[0]
        print(f"  Q: Why does '{target[0]}' thematically reach '{target[2]}'?")
        print(f"     ('{target[0]}' and '{target[2]}' never appear together "
              f"in one utterance — derived via fixpoint.)")
        print(f"  Rule:        {d.rule_name}")
        for inp in d.inputs:
            print(f"  Input:       {inp.subject} --{inp.relation}--> {inp.object}")
        print(f"  Explanation: {d.explanation}")
    print()

    print("=" * 78)
    print("Same engine, different data. Every derived fact carries a")
    print("\"since X therefore Y\" explanation, just like the Wikipedia KB.")
    print("=" * 78)
    print()


if __name__ == "__main__":
    main()
