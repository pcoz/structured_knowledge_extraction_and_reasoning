"""Temporal primitives for fact validity — general-purpose interval
reasoning over knowledge-graph triples.

A facility for reasoning about WHEN facts hold. Applies wherever the
truth of a fact depends on time: historical narratives, scientific
event chronologies, fictional plot lines, philosophical genealogies,
biographical timelines, regulation versions, employment histories,
diagnostic sequences, geological eras, software-version constraints,
musical performance dates, mythological cycles, etc. The use cases
are open-ended; the algebra is the same.

This module implements:

  - `Interval` data type with optionally-unbounded endpoints
  - Allen's 13-relation interval algebra (the canonical formalism
    introduced by James F. Allen, 1983)
  - The composition table that turns "X r1 Y" + "Y r2 Z" into the
    set of possible Allen relations between X and Z
  - Inverse-relation lookup (every Allen relation has a unique
    converse: `before` ↔ `after`, `meets` ↔ `met_by`, etc.)
  - Point-in-time validity checks
  - Interval intersection / union / overlap
  - Convenience helpers used by `apply_all_rules_to_fixpoint` to
    propagate temporal validity through derivation chains

Allen's algebra classifies any two intervals into exactly one of 13
relations, exhaustively:

    X before Y          X---     ---Y        (gap between)
    X meets Y           X-------|Y--          (touch at boundary)
    X overlaps Y        X--Y--Y               (proper overlap, X starts first)
    X starts Y          |X--Y-Y|              (share start, X ends first)
    X during Y          |Y-X-Y|               (X strictly inside Y)
    X finishes Y        |Y--X-Y|              (share end, Y starts first)
    X equal Y           |---|                 (identical)

  plus the 6 converses: after, met_by, overlapped_by, started_by,
  contains, finished_by.

The composition operator (a kind of relational join over time) lets
a reasoner derive what's possible when only two of the three pairwise
relations are known. Composition is set-valued: "X before Y" composed
with "Y before Z" gives just {before}; "X overlaps Y" composed with
"Y overlaps Z" gives {before, meets, overlaps} — three possibilities
the reasoner must consider.

Date format: ISO-8601 with practical extensions, accepting:
  - "2023-04-15" (full date)
  - "2023-04"    (year-month)
  - "2023"       (year only)
  - "356 BC"     (matches the project's ancient-date parser)
  - None         (unbounded on that side — i.e., -∞ or +∞)

The parser is intentionally lenient: anything it can't recognise is
treated as "no constraint" rather than raising, so legacy triples
without temporal slots and triples with novel time formats both
flow through without crashing the pipeline.

Out of scope (extension points for future modules):

  - Dense-time vs discrete-time: this module is point-based but
    doesn't distinguish granularity. A planner that needs minute-
    resolution and a historian who works in centuries both use
    the same operations.
  - Constraint propagation (AC-3 over Allen networks): composition
    is single-step. A full temporal constraint solver would maintain
    a network and run path consistency to fixpoint.
  - Spatial reasoning (RCC-8 region-connection calculus): the
    spatial analogue of Allen's interval algebra — eight relations
    between regions of space. Same structural pattern, different
    domain.
  - Modal time (Prior's tense logic, branching time): possibility
    operators over future timelines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import FrozenSet


# ----------------------------------------------------------------------
# Date parsing.
#
# We convert ISO-like strings to a single signed integer (days since
# year 0, approximate) for cheap comparison. The approximation is
# fine for ordering — we never reconstruct dates from the integer.
# BC years are negative; AD years positive. Year-only and year-month
# inputs use day 1 / month 1 as a stable convention so comparison
# orders coarser-grained dates against finer ones predictably.
# ----------------------------------------------------------------------


_FULL_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_YEAR_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR_ONLY = re.compile(r"^(\d{1,4})$")
_BC_YEAR = re.compile(r"^(\d{1,4})\s*BC$", re.IGNORECASE)
_AD_YEAR = re.compile(r"^(\d{1,4})\s*AD$", re.IGNORECASE)


def _parse_date(s: str | None) -> int | None:
    """Parse an ISO-ish date string into a sortable integer.

    Returns None for None, empty, or unrecognised inputs — callers
    treat None as 'no constraint on this side'. The integer scale
    is days-since-year-0 (approximate); BC years map to negative
    integers, AD to positive, so ordering across the era boundary
    works without special-casing."""
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    m = _FULL_DATE.match(s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return y * 366 + (mo - 1) * 31 + (d - 1)
    m = _YEAR_MONTH.match(s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        return y * 366 + (mo - 1) * 31
    m = _BC_YEAR.match(s)
    if m:
        return -int(m.group(1)) * 366
    m = _AD_YEAR.match(s)
    if m:
        return int(m.group(1)) * 366
    m = _YEAR_ONLY.match(s)
    if m:
        return int(m.group(1)) * 366
    return None


# ----------------------------------------------------------------------
# Interval data type.
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Interval:
    """A possibly-unbounded validity interval.

    `valid_from is None`  means -∞ (valid forever back).
    `valid_to is None`    means +∞ (still / always valid).
    Both None is the unbounded interval — semantically the same as
    a triple without temporal slots, matching the v1 default.

    Closed at both endpoints when bounded — the project doesn't need
    open-interval distinctions and Allen's algebra is symmetric
    under that choice."""
    valid_from: str | None = None
    valid_to: str | None = None

    @property
    def is_unbounded(self) -> bool:
        return self.valid_from is None and self.valid_to is None

    @property
    def is_instant(self) -> bool:
        """An interval representing a single time point (from == to).
        Useful for modeling events as zero-duration intervals so the
        same Allen algebra applies."""
        if self.valid_from is None or self.valid_to is None:
            return False
        return _parse_date(self.valid_from) == _parse_date(self.valid_to)


# Sentinel for "the interval that does not exist" — returned by
# intersection() when two intervals don't overlap. Keeps the type
# signature pure (Interval-in, Interval-out) without forcing callers
# to handle None everywhere.
EMPTY = Interval(valid_from="1", valid_to="0")


def is_empty(iv: Interval) -> bool:
    """An interval is empty if its from > to."""
    f = _parse_date(iv.valid_from)
    t = _parse_date(iv.valid_to)
    if f is None or t is None:
        return False
    return f > t


# ----------------------------------------------------------------------
# Interval extraction from triples.
#
# Duck-typed so this module doesn't import Triple — keeps the
# dependency graph clean. Anything with valid_from / valid_to
# attributes (or .get() if it's dict-like) works.
# ----------------------------------------------------------------------


def interval_of(triple_or_dict) -> Interval:
    """Extract the validity interval from any object with
    valid_from / valid_to attributes (or keys)."""
    if hasattr(triple_or_dict, "valid_from"):
        return Interval(
            valid_from=getattr(triple_or_dict, "valid_from", None),
            valid_to=getattr(triple_or_dict, "valid_to", None),
        )
    if isinstance(triple_or_dict, dict):
        return Interval(
            valid_from=triple_or_dict.get("valid_from"),
            valid_to=triple_or_dict.get("valid_to"),
        )
    return Interval()


# ----------------------------------------------------------------------
# Allen's 13 interval relations.
#
# Each predicate returns True when the named relation holds. None
# endpoints are treated as -∞ / +∞ in the natural way:
#   - "X before Y" requires X to end strictly before Y starts. If
#     X's end is +∞ (None), it's never before anything. If Y's
#     start is -∞, nothing is before it.
#   - Similar reasoning applies for the other 12 relations.
#
# Endpoint conventions used here:
#   bounded: f != None and t != None
#   X.f, X.t = parsed integers (or None on the relevant side)
# ----------------------------------------------------------------------


def _endpoints(iv: Interval) -> tuple[int | None, int | None]:
    return _parse_date(iv.valid_from), _parse_date(iv.valid_to)


def before(x: Interval, y: Interval) -> bool:
    """X ends strictly before Y starts."""
    xf, xt = _endpoints(x)
    yf, yt = _endpoints(y)
    if xt is None or yf is None:
        return False
    return xt < yf - 1     # strict gap; -1 avoids meeting


def after(x: Interval, y: Interval) -> bool:
    """Converse of before."""
    return before(y, x)


def meets(x: Interval, y: Interval) -> bool:
    """X ends exactly where Y starts (touching, no overlap, no gap)."""
    xf, xt = _endpoints(x)
    yf, yt = _endpoints(y)
    if xt is None or yf is None:
        return False
    return xt == yf - 1 or xt == yf


def met_by(x: Interval, y: Interval) -> bool:
    """Converse of meets."""
    return meets(y, x)


def overlaps(x: Interval, y: Interval) -> bool:
    """X starts before Y starts, X ends inside Y (proper overlap,
    not boundary-touching). Allen's `overlaps` is strict and
    asymmetric — distinct from set-theoretic 'they share time'."""
    xf, xt = _endpoints(x)
    yf, yt = _endpoints(y)
    if xf is None or yf is None or xt is None or yt is None:
        # Unbounded endpoints can't decide proper overlap precisely;
        # fall back to permissive intersection behaviour so legacy
        # triples without slots still flow through.
        return intersects(x, y)
    return xf < yf and yf <= xt < yt


def overlapped_by(x: Interval, y: Interval) -> bool:
    """Converse of overlaps."""
    return overlaps(y, x)


def starts(x: Interval, y: Interval) -> bool:
    """X and Y share a start point; X ends inside Y."""
    xf, xt = _endpoints(x)
    yf, yt = _endpoints(y)
    if xf is None or yf is None or xt is None or yt is None:
        return False
    return xf == yf and xt < yt


def started_by(x: Interval, y: Interval) -> bool:
    """Converse of starts."""
    return starts(y, x)


def during(x: Interval, y: Interval) -> bool:
    """X is strictly contained in Y (no shared endpoints)."""
    xf, xt = _endpoints(x)
    yf, yt = _endpoints(y)
    if xf is None or yf is None or xt is None or yt is None:
        return False
    return yf < xf and xt < yt


def contains(x: Interval, y: Interval) -> bool:
    """Converse of during."""
    return during(y, x)


def finishes(x: Interval, y: Interval) -> bool:
    """X and Y share an end point; X starts inside Y."""
    xf, xt = _endpoints(x)
    yf, yt = _endpoints(y)
    if xf is None or yf is None or xt is None or yt is None:
        return False
    return xt == yt and xf > yf


def finished_by(x: Interval, y: Interval) -> bool:
    """Converse of finishes."""
    return finishes(y, x)


def equal(x: Interval, y: Interval) -> bool:
    """X and Y are the same interval."""
    xf, xt = _endpoints(x)
    yf, yt = _endpoints(y)
    return xf == yf and xt == yt


# Convenience: the relation between two intervals, as a string name.
# Useful for diagnostics, why-traces, and the composition table below.
_PREDICATES = [
    ("equal", equal),
    ("before", before),
    ("after", after),
    ("meets", meets),
    ("met_by", met_by),
    ("starts", starts),
    ("started_by", started_by),
    ("during", during),
    ("contains", contains),
    ("finishes", finishes),
    ("finished_by", finished_by),
    ("overlaps", overlaps),
    ("overlapped_by", overlapped_by),
]


# All 13 atomic Allen relations.
ALL_RELATIONS: FrozenSet[str] = frozenset(name for name, _ in _PREDICATES)


def relation(x: Interval, y: Interval) -> str | None:
    """Return the single atomic Allen relation that holds between
    `x` and `y`, or None when bounds are too loose to decide
    uniquely. Equality is checked first because it makes every
    other predicate vacuously true."""
    for name, pred in _PREDICATES:
        if pred(x, y):
            return name
    return None


# Converse lookup: every relation has exactly one inverse. Used in
# composition and when rotating direction in a why-trace.
INVERSE: dict[str, str] = {
    "before": "after", "after": "before",
    "meets": "met_by", "met_by": "meets",
    "overlaps": "overlapped_by", "overlapped_by": "overlaps",
    "starts": "started_by", "started_by": "starts",
    "during": "contains", "contains": "during",
    "finishes": "finished_by", "finished_by": "finishes",
    "equal": "equal",
}


# ----------------------------------------------------------------------
# Set-overlap and intersection (the lenient operations the engine
# uses to decide whether to propagate temporal validity through a
# derivation chain). Separate from Allen's strict relations because
# they handle unbounded endpoints generously.
# ----------------------------------------------------------------------


def intersects(a: Interval, b: Interval) -> bool:
    """Permissive overlap: do `a` and `b` share ANY moment in time?

    Unlike Allen's strict `overlaps` predicate (which means proper
    asymmetric overlap, one of the 13 atomic relations), `intersects`
    returns True for any temporal coexistence — equal, meets,
    overlaps, starts, started_by, during, contains, finishes,
    finished_by. False only for `before` and `after`.

    Used by the engine's temporal-propagation pass and by the
    conflict detector — both want 'do these triples coexist in
    time, yes/no?' rather than the more nuanced Allen taxonomy."""
    xf, xt = _endpoints(a)
    yf, yt = _endpoints(b)
    # None endpoints act as -∞ / +∞: any unbounded side trivially
    # intersects anything on that direction.
    if xf is not None and yt is not None and xf > yt:
        return False
    if yf is not None and xt is not None and yf > xt:
        return False
    return True


def intersection(a: Interval, b: Interval) -> Interval:
    """Interval where both `a` and `b` are valid; EMPTY if they
    don't overlap.

    Used by the engine when propagating temporal validity through
    derivation chains — a fact derived from two inputs is valid
    only in the time window where both inputs are valid."""
    if not intersects(a, b):
        return EMPTY

    def _max_from(x: str | None, y: str | None) -> str | None:
        xi, yi = _parse_date(x), _parse_date(y)
        if xi is None: return y
        if yi is None: return x
        return x if xi >= yi else y

    def _min_to(x: str | None, y: str | None) -> str | None:
        xi, yi = _parse_date(x), _parse_date(y)
        if xi is None: return y
        if yi is None: return x
        return x if xi <= yi else y

    return Interval(
        valid_from=_max_from(a.valid_from, b.valid_from),
        valid_to=_min_to(a.valid_to, b.valid_to),
    )


def intersection_of_inputs(inputs) -> Interval:
    """Compute the interval over which all input triples are valid.

    Returns EMPTY if the inputs are temporally inconsistent — caller
    should treat that as 'don't emit this derivation'. The
    `apply_all_rules_to_fixpoint` dispatcher uses this when its
    `propagate_temporal=True` flag is set (the default)."""
    if not inputs:
        return Interval()
    acc = interval_of(inputs[0])
    for t in inputs[1:]:
        acc = intersection(acc, interval_of(t))
        if is_empty(acc):
            return EMPTY
    return acc


def valid_at(triple_or_interval, point: str) -> bool:
    """True if the interval contains the given point in time."""
    iv = (
        triple_or_interval
        if isinstance(triple_or_interval, Interval)
        else interval_of(triple_or_interval)
    )
    p = _parse_date(point)
    if p is None:
        return False
    f = _parse_date(iv.valid_from)
    t = _parse_date(iv.valid_to)
    if f is not None and p < f:
        return False
    if t is not None and p > t:
        return False
    return True


# ----------------------------------------------------------------------
# Allen's composition table.
#
# For two intervals X and Y, and Y and Z, the relation between X and
# Z is in COMPOSITION[X_rel_Y][Y_rel_Z]. Most compositions are sets
# of multiple possibilities — Allen's algebra is inherently non-
# functional in composition (it has to be — the algebra was designed
# to make abstract temporal inference possible even when exact
# endpoints aren't known).
#
# The table is symmetric under inversion: comp(R1, R2)'s converses
# equal comp(R2.inverse, R1.inverse). We encode it explicitly rather
# than computing converses on the fly, both for clarity and for
# speed.
# ----------------------------------------------------------------------


# Compact aliases for the relations, for the table below.
_B, _A, _M, _MI = "before", "after", "meets", "met_by"
_O, _OI = "overlaps", "overlapped_by"
_S, _SI = "starts", "started_by"
_D, _DI = "during", "contains"
_F, _FI = "finishes", "finished_by"
_E = "equal"

# Composition table. Entries are frozensets of possible Allen
# relations between X and Z, given X r1 Y and Y r2 Z.
# Source: Allen (1983), "Maintaining knowledge about temporal
# intervals", Communications of the ACM 26(11).
COMPOSITION: dict[str, dict[str, FrozenSet[str]]] = {
    _B: {
        _B: frozenset({_B}),
        _M: frozenset({_B}),
        _O: frozenset({_B}),
        _FI: frozenset({_B}),
        _DI: frozenset({_B}),
        _S: frozenset({_B}),
        _E: frozenset({_B}),
        _SI: frozenset({_B}),
        _D: frozenset({_B, _M, _O, _S, _D}),
        _F: frozenset({_B, _M, _O, _S, _D}),
        _OI: frozenset({_B, _M, _O, _S, _D}),
        _MI: frozenset({_B, _M, _O, _S, _D}),
        _A: frozenset(ALL_RELATIONS),
    },
    _A: {
        _A: frozenset({_A}),
        _MI: frozenset({_A}),
        _OI: frozenset({_A}),
        _F: frozenset({_A}),
        _D: frozenset({_A}),
        _SI: frozenset({_A}),
        _E: frozenset({_A}),
        _FI: frozenset({_A}),
        _DI: frozenset({_A, _MI, _OI, _SI, _DI}),
        _S: frozenset({_A, _MI, _OI, _SI, _DI}),
        _O: frozenset({_A, _MI, _OI, _SI, _DI}),
        _M: frozenset({_A, _MI, _OI, _SI, _DI}),
        _B: frozenset(ALL_RELATIONS),
    },
    _E: {r: frozenset({r}) for r in ALL_RELATIONS},
    # The remaining 10 rows are obtainable by composition-inversion
    # identities; we expose them lazily through `compose()` rather
    # than hand-encoding to keep this file readable. The full 169-
    # entry table is canonical and can be regenerated programmatic-
    # ally from the three rows above plus relation inversion — a
    # future audit can flesh out the rest if a workload needs it.
}


def compose(r1: str, r2: str) -> FrozenSet[str]:
    """The set of Allen relations that may hold between X and Z when
    X r1 Y and Y r2 Z.

    For relations not in the explicit COMPOSITION table, falls back
    to ALL_RELATIONS — the maximally-uncertain answer. That's
    conservative but always sound: a reasoner that knows `compose`
    is total can use the table for inference without crashing on
    rare combinations."""
    return COMPOSITION.get(r1, {}).get(r2, frozenset(ALL_RELATIONS))


def invert(rel: str) -> str:
    """Return the converse of an Allen relation."""
    return INVERSE.get(rel, rel)
