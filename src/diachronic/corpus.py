"""A multi-era corpus tracking how 'atom' has been *assembled* as a
concept across 2,500 years of natural philosophy and science.

This isn't a corpus where the facts simply change. It's a corpus
where the SAME WORD — atom — gets STRUCTURED DIFFERENTLY in each
era. Different IS_A classes, different parts, different properties,
different things atoms connect to. The schema isn't fixed and the
facts laid over it; the schema is part of the historical record.

Six eras represented:

  1. Greek atomism (~450 BCE - 50 CE) — atom as indivisible
     philosophical principle. Subject of speculation, not measurement.
  2. Aristotelian rejection (~300 BCE - 1600 CE) — atomism set
     aside in favour of continuous matter. Atom = rejected hypothesis.
  3. Mechanical / Newtonian (~1600 - 1800) — atom rehabilitated as
     a small hard physical body. Empirical for the first time.
  4. Daltonian / chemical (~1808 - 1900) — atom as quantitative
     basis of chemistry. Defined by atomic weight.
  5. Rutherford / Bohr (~1911 - 1925) — atom as COMPOSITE structure
     with parts. The historical reversal: 'indivisible' is wrong.
  6. Quantum mechanical (~1925 - present) — atom as quantum system
     described by a wave function. Definite position rejected.

Each era's facts come from named primary sources with confidence
reflecting that era's level of consensus. The temporal slots scope
each assertion to its period — so the same subject 'atom' carries
genuinely incompatible classifications across eras without being
self-contradictory at any single time.

Why this matters for knowledge representation, and why LLMs struggle
with it specifically — see the prose in src/diachronic/analyse.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parent))

from kb.query import KB, Triple


# Authority of each historical source. Primary works rank higher than
# secondary commentaries.
SOURCE_AUTHORITY = {
    "Democritus_fragments":   0.90,
    "Lucretius_DRN":          0.85,
    "Epicurus_LetterToHerodotus": 0.85,
    "Aristotle_Physics":      0.95,
    "Newton_Opticks":         0.95,
    "Newton_Principia":       0.95,
    "Gassendi_Syntagma":      0.80,
    "Dalton_NewSystem_1808":  0.95,
    "Avogadro_1811":          0.90,
    "Rutherford_1911":        0.95,
    "Bohr_1913":              0.95,
    "Schrodinger_1926":       0.95,
    "Heisenberg_1927":        0.95,
    "modern_textbook":        0.85,
}


# Row layout: (subject, relation, object, source, valid_from, valid_to, confidence)
# Dates are approximate. Eras overlap somewhat in reality — that's
# faithful to the historical record (Aristotelianism didn't end the
# day Newton was born; quantum mechanics didn't end the Bohr model).
_RAW_FACTS: list[tuple] = [

    # ============================================================
    # ERA 1: Greek atomism (~450 BCE — 50 CE)
    # The atom as an *indivisible philosophical principle*.
    # ============================================================
    ("atom", "IS_A", "IndivisiblePrinciple",
     "Democritus_fragments", "-450", "50", 0.85),
    ("atom", "IS_A", "PhilosophicalCategory",
     "Democritus_fragments", "-450", "50", 0.85),
    ("atom", "HAS_PROPERTY", "indivisible",
     "Democritus_fragments", "-450", "50", 0.90),
    ("atom", "HAS_PROPERTY", "eternal",
     "Democritus_fragments", "-450", "50", 0.85),
    ("atom", "HAS_PROPERTY", "uncreated",
     "Lucretius_DRN", "-50", "50", 0.85),
    ("atom", "HAS_PROPERTY", "various_shapes",
     "Lucretius_DRN", "-50", "50", 0.80),
    ("atom", "COMBINES_WITH", "atom",
     "Democritus_fragments", "-450", "50", 0.85),
    ("atom", "EXPLAINS", "all_phenomena",
     "Epicurus_LetterToHerodotus", "-300", "50", 0.75),
    ("atom", "EXPLAINED_BY", "Democritus",
     "Democritus_fragments", "-450", "50", 0.95),
    ("atom", "EXPLAINED_BY", "Epicurus",
     "Epicurus_LetterToHerodotus", "-300", "50", 0.95),
    ("atom", "DISCUSSED_IN", "Naturalism",
     "Lucretius_DRN", "-50", "50", 0.85),
    ("atom", "ORGANIZED_AS", "ReductiveMetaphysics",
     "Democritus_fragments", "-450", "50", 0.85),

    # ============================================================
    # ERA 2: Aristotelian rejection (~300 BCE — 1600 CE)
    # Atomism set aside; matter understood as continuous.
    # ============================================================
    ("atom", "IS_A", "RejectedHypothesis",
     "Aristotle_Physics", "-340", "1600", 0.90),
    ("atomism", "REJECTED_BY", "Aristotle",
     "Aristotle_Physics", "-340", "1600", 0.95),
    ("matter", "IS_A", "ContinuousSubstance",
     "Aristotle_Physics", "-340", "1600", 0.90),
    ("matter", "HAS_PROPERTY", "infinitely_divisible",
     "Aristotle_Physics", "-340", "1600", 0.85),
    ("atom", "DISCUSSED_IN", "ScholasticPhilosophy",
     "Aristotle_Physics", "-340", "1600", 0.70),
    ("atom", "ORGANIZED_AS", "ContraryToReason",
     "Aristotle_Physics", "-340", "1600", 0.80),

    # ============================================================
    # ERA 3: Mechanical / Newtonian (~1600 — 1800)
    # Atom rehabilitated. Now a *small hard physical body*.
    # The category shifts: from philosophical → physical.
    # ============================================================
    ("atom", "IS_A", "SmallHardSphere",
     "Newton_Opticks", "1704", "1800", 0.90),
    ("atom", "IS_A", "PhysicalObject",
     "Newton_Opticks", "1704", "1800", 0.95),
    ("atom", "HAS_PROPERTY", "hard",
     "Newton_Opticks", "1704", "1800", 0.90),
    ("atom", "HAS_PROPERTY", "indivisible",  # Newton still held this
     "Newton_Opticks", "1704", "1800", 0.85),
    ("atom", "HAS_PROPERTY", "massive",
     "Newton_Principia", "1687", "1800", 0.90),
    ("atom", "HAS_PROPERTY", "impenetrable",
     "Newton_Opticks", "1704", "1800", 0.85),
    ("atom", "OBEYS_LAW", "NewtonsLawsOfMotion",
     "Newton_Principia", "1687", "1800", 0.90),
    ("atom", "EXPLAINED_BY", "Newton",
     "Newton_Opticks", "1704", "1800", 0.95),
    ("atom", "EXPLAINED_BY", "Gassendi",
     "Gassendi_Syntagma", "1658", "1800", 0.80),
    ("atom", "ORGANIZED_AS", "MechanicalCorpuscle",
     "Newton_Opticks", "1704", "1800", 0.85),

    # ============================================================
    # ERA 4: Daltonian / chemical (~1808 — 1900)
    # Atom as quantitative basis of chemistry. Defined by weight.
    # The category shifts again: from physical body → chemical
    # element identity.
    # ============================================================
    ("atom", "IS_A", "ChemicalElement",
     "Dalton_NewSystem_1808", "1808", "1900", 0.95),
    ("atom", "IS_A", "QuantitativeUnit",
     "Dalton_NewSystem_1808", "1808", "1900", 0.90),
    ("atom", "HAS_PROPERTY", "atomic_weight",
     "Dalton_NewSystem_1808", "1808", "1900", 0.95),
    ("atom", "HAS_PROPERTY", "characteristic_of_element",
     "Dalton_NewSystem_1808", "1808", "1900", 0.90),
    ("atom", "HAS_PROPERTY", "indivisible",  # Daltonians still held this
     "Dalton_NewSystem_1808", "1808", "1900", 0.85),
    ("atom", "COMBINES_VIA", "fixed_ratios",
     "Dalton_NewSystem_1808", "1808", "1900", 0.95),
    ("atom", "RELATED_TO", "Molecule",
     "Avogadro_1811", "1811", "1900", 0.90),
    ("atom", "OBEYS_LAW", "LawOfDefiniteProportions",
     "Dalton_NewSystem_1808", "1808", "1900", 0.95),
    ("atom", "EXPLAINED_BY", "Dalton",
     "Dalton_NewSystem_1808", "1808", "1900", 0.95),
    ("atom", "EXPLAINED_BY", "Avogadro",
     "Avogadro_1811", "1811", "1900", 0.90),
    ("atom", "ORGANIZED_AS", "ChemicalAccountingUnit",
     "Dalton_NewSystem_1808", "1808", "1900", 0.90),

    # ============================================================
    # ERA 5: Rutherford / Bohr (~1911 — 1925)
    # Atom revealed as COMPOSITE — it has parts.
    # This is the famous reversal: 'indivisible' is wrong.
    # ============================================================
    ("atom", "IS_A", "CompositeStructure",
     "Rutherford_1911", "1911", "1925", 0.95),
    ("atom", "IS_A", "PhysicalSystem",
     "Rutherford_1911", "1911", "1925", 0.95),
    ("atom", "HAS_PART", "electron",
     "Rutherford_1911", "1911", "1925", 0.95),
    ("atom", "HAS_PART", "nucleus",
     "Rutherford_1911", "1911", "1925", 0.95),
    ("atom", "HAS_PART", "proton",
     "Rutherford_1911", "1919", "1925", 0.95),
    ("atom", "HAS_PROPERTY", "mostly_empty_space",
     "Rutherford_1911", "1911", "1925", 0.95),
    ("atom", "HAS_PROPERTY", "positively_charged_core",
     "Rutherford_1911", "1911", "1925", 0.95),
    ("atom", "HAS_PROPERTY", "quantized_energy_levels",
     "Bohr_1913", "1913", "1925", 0.90),
    ("atom", "REJECTS_PROPERTY", "indivisible",  # the reversal
     "Rutherford_1911", "1911", None, 0.95),
    ("atom", "EXPLAINED_BY", "Rutherford",
     "Rutherford_1911", "1911", "1925", 0.95),
    ("atom", "EXPLAINED_BY", "Bohr",
     "Bohr_1913", "1913", "1925", 0.95),
    ("atom", "ORGANIZED_AS", "PlanetaryModel",
     "Bohr_1913", "1913", "1925", 0.90),

    # ============================================================
    # ERA 6: Quantum mechanical (~1925 — present)
    # Atom as quantum system described by a wave function.
    # 'Definite position' rejected. Planetary model superseded.
    # ============================================================
    ("atom", "IS_A", "QuantumSystem",
     "Schrodinger_1926", "1926", None, 0.95),
    ("atom", "IS_A", "ProbabilisticEntity",
     "Schrodinger_1926", "1926", None, 0.90),
    ("atom", "HAS_PROPERTY", "wave_particle_duality",
     "Schrodinger_1926", "1926", None, 0.95),
    ("atom", "HAS_PROPERTY", "orbital_structure",
     "Schrodinger_1926", "1926", None, 0.95),
    ("atom", "HAS_PART", "electron",  # described as cloud now
     "modern_textbook", "1926", None, 0.95),
    ("atom", "HAS_PART", "electron_cloud",
     "modern_textbook", "1926", None, 0.90),
    ("atom", "DESCRIBED_BY", "SchrodingerEquation",
     "Schrodinger_1926", "1926", None, 0.95),
    ("atom", "DESCRIBED_BY", "HeisenbergUncertainty",
     "Heisenberg_1927", "1927", None, 0.95),
    ("atom", "REJECTS_PROPERTY", "definite_position",
     "Heisenberg_1927", "1927", None, 0.95),
    ("atom", "REJECTS_PROPERTY", "planetary_orbits",
     "modern_textbook", "1926", None, 0.90),
    ("atom", "EXPLAINED_BY", "Schrodinger",
     "Schrodinger_1926", "1926", None, 0.95),
    ("atom", "EXPLAINED_BY", "Heisenberg",
     "Heisenberg_1927", "1927", None, 0.95),
    ("atom", "ORGANIZED_AS", "QuantumWaveFunction",
     "Schrodinger_1926", "1926", None, 0.95),
]


# A coarse era label keyed by (valid_from start year, valid_to end year).
# Used by analyse.py to bucket facts into eras for diagnostic reports.
ERA_BOUNDARIES = [
    ("Greek atomism",       -450,   50),
    ("Aristotelian",        -340, 1600),
    ("Mechanical/Newtonian", 1600, 1800),
    ("Daltonian/chemical",   1808, 1900),
    ("Rutherford/Bohr",      1911, 1925),
    ("Quantum mechanical",   1926, 9999),
]


def build_atom_kb() -> KB:
    """Materialise the multi-era atom corpus as a KB."""
    triples = [
        Triple(s, r, o, src, -1, vf, vt, conf)
        for (s, r, o, src, vf, vt, conf) in _RAW_FACTS
    ]
    return KB(
        triples=triples,
        alias_map={},
        n_articles=0,
        source_authority=dict(SOURCE_AUTHORITY),
    )
