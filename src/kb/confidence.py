"""Uncertainty combinators for rule-derived facts.

Every Triple carries a `confidence` field in [0.0, 1.0]. When a rule
derives a new fact from input facts, the engine assigns the derived
fact a confidence computed from its inputs. This module supplies the
combining functions; `apply_all_rules_to_fixpoint` calls them when
its `propagate_confidence` flag is set (the default).

The semantic interpretation of `confidence` is deliberately left to
the caller. Standard readings:

  - **Probabilistic** — confidence is P(fact is true) under some
    evidence model. noisy_and / noisy_or combinators assume
    independence between inputs.
  - **Fuzzy** — confidence is the degree of truth on a [0,1] scale,
    a la Zadeh's fuzzy logic. min / max combinators correspond to
    fuzzy ∧ / ∨.
  - **Subjective Bayesian** — confidence is a personal degree of
    belief. The combinators are still applicable; the
    interpretation is internal to the reasoner.
  - **Dempster-Shafer mass** — partial belief functions. We don't
    implement Dempster's combination rule directly; doing so would
    require triples to carry a full mass function rather than a
    single number. Mentioned as a future extension.

What this module deliberately doesn't do:

  - Full probabilistic Datalog (ProbLog-style) — multiple
    derivations of the same fact combining via inclusion-exclusion
    on independent probabilities. That's its own substantial
    framework and adds non-trivial cost to fixpoint convergence.
    Our `noisy_or` covers the common case (two independent
    derivations reinforcing the same conclusion); we don't pretend
    to cover dependent-evidence cases correctly.
  - Source-model integration (where confidence depends on which
    source produced the fact). Left to the caller — sources can
    set confidence at extraction time; we just propagate.
  - Confidence intervals or distributions instead of point
    estimates. A natural extension when single-number confidence
    proves too lossy, but a real schema change to Triple.

Combinators are pure functions. Same inputs always produce the
same output — same as the rest of the engine, in keeping with the
deterministic-artifact property.
"""

from __future__ import annotations

from typing import Iterable


# ----------------------------------------------------------------------
# Combining functions.
#
# All take an iterable of input confidences and return a single
# derived confidence. Pure functions — same input, same output —
# so they don't disturb the deterministic-artifact property.
# ----------------------------------------------------------------------


def noisy_and(confidences: Iterable[float]) -> float:
    """Product of inputs — derived confidence under the assumption
    that all inputs must hold and they're independent.

    Use case: a chained derivation like 'A tutored B, B tutored C →
    A is intellectual ancestor of C'. The conclusion holds with the
    joint confidence of both premises.

    Edge cases handled cleanly:
      - Empty input → 1.0 (no constraint reduces nothing)
      - Any input is 0.0 → 0.0 (chain breaks)
      - All 1.0 → 1.0 (existing behaviour preserved for default-
        confidence inputs; matches v1 semantics for back-compat)"""
    out = 1.0
    for c in confidences:
        out *= max(0.0, min(1.0, c))
    return out


def min_confidence(confidences: Iterable[float]) -> float:
    """Weakest-link combining: derived confidence is the minimum of
    inputs. More pessimistic than noisy-AND.

    Useful when input confidences should be treated as ordinal rather
    than multiplicative — e.g. evidence-grade tiers in clinical
    guidelines, where the chain is only as strong as the weakest
    citation."""
    vals = [max(0.0, min(1.0, c)) for c in confidences]
    return min(vals) if vals else 1.0


def noisy_or(confidences: Iterable[float]) -> float:
    """At-least-one-holds: 1 - product(1 - c_i). Suitable for
    multiple INDEPENDENT derivations supporting the same conclusion —
    the merge step when two rules derive the same triple.

    Strictly stronger than `max` for independent evidence: two
    derivations at confidence 0.7 each merge to 0.91, not 0.7."""
    p_none = 1.0
    for c in confidences:
        p_none *= (1.0 - max(0.0, min(1.0, c)))
    return 1.0 - p_none


# ----------------------------------------------------------------------
# Policy entry point.
#
# The engine calls derive_confidence() to propagate confidence to a
# new derivation. Modes:
#   - "product"  : noisy-AND (default, recommended)
#   - "min"      : weakest-link
#   - any callable: caller-supplied combiner for unusual schemes
# ----------------------------------------------------------------------


def derive_confidence(
    input_confidences: Iterable[float],
    mode: str | callable = "product",
) -> float:
    """Combine input confidences into a derived confidence.

    `mode` is either a string naming a built-in combiner ("product",
    "min", "noisy_or") or a callable that accepts an iterable of
    floats and returns one float."""
    if callable(mode):
        return float(mode(input_confidences))
    if mode == "product":
        return noisy_and(input_confidences)
    if mode == "min":
        return min_confidence(input_confidences)
    if mode == "noisy_or":
        return noisy_or(input_confidences)
    raise ValueError(
        f"unknown confidence combiner mode: {mode!r} "
        f"(use 'product', 'min', 'noisy_or', or a callable)"
    )


# ----------------------------------------------------------------------
# Merge / dedup combining.
#
# When two derivations produce the same (subject, relation, object),
# the engine collapses them into one — keeping the more-confident
# variant. This is the "noisy-OR over independent evidence lite"
# story: two distinct derivations reinforce the fact, but we don't
# pay full ProbLog cost.
# ----------------------------------------------------------------------


def merge_confidence(a: float, b: float, mode: str = "max") -> float:
    """Combine confidence of two duplicate triples that the dedup
    logic would otherwise collapse.

    `mode` defaults to "max" (keep the stronger). "noisy_or"
    rewards independent corroboration. "min" is conservative."""
    a = max(0.0, min(1.0, a))
    b = max(0.0, min(1.0, b))
    if mode == "max":
        return max(a, b)
    if mode == "min":
        return min(a, b)
    if mode == "noisy_or":
        return noisy_or([a, b])
    raise ValueError(f"unknown merge mode: {mode!r}")


# ----------------------------------------------------------------------
# Threshold filtering.
# ----------------------------------------------------------------------


def drop_below(triples, threshold: float):
    """Return triples whose confidence meets or exceeds the threshold.

    Used to prune low-confidence derived facts from the artifact
    before serialisation. Threshold of 0.0 keeps everything; 1.0
    keeps only fully-certain facts; intermediate values let callers
    tune the precision/recall trade-off."""
    return [t for t in triples if getattr(t, "confidence", 1.0) >= threshold]
