"""A deliberately-noisy multi-source corpus for the distillation demo.

The facts here are astronomical (planets, dwarf planets, the Sun, the
Andromeda Galaxy) — a domain chosen because it has natural multi-source
structure, historical revisions to measurements, and one famous
classification dispute (Pluto, reclassified by the IAU in 2006). The
corpus is constructed to exhibit every pathology the purification
pipeline targets:

  - **Corroboration.** The same fact asserted by several independent
    sources. The purifier combines their confidences via noisy-OR,
    producing a stronger consolidated fact than any single source
    could justify alone.

  - **Functional-property conflicts.** Different values for the same
    functional property (e.g., MASS_KG of Mercury): the OWL rule
    compiler detects them and a chain policy resolves which value
    survives.

  - **Outdated measurements.** Older estimates of Andromeda's
    distance (1.0e6 ly in 1965, 2.0e6 in 1985, 2.5e6 in modern
    sources) — resolved by authority weighting plus latest-wins.

  - **Low-authority noise.** Wrong values from a blog post or a
    careless old encyclopedia, marked at low confidence. Either the
    conflict resolver picks against them or the confidence-threshold
    pruner drops them.

  - **Historical classification changes.** Pluto IS_A Planet
    (valid_to "2006-08-24") vs Pluto IS_A DwarfPlanet (valid_from
    "2006-08-24"). With temporal scoping the OWL functional-
    property axiom CORRECTLY does NOT flag these as conflicting:
    they don't overlap in time.

Source authority is published as a flat dict; higher = more
authoritative. The purifier's AuthorityWinsPolicy reads it.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parent))

from kb.query import KB, Triple


# ----------------------------------------------------------------------
# Source authority ranking.
#
# Authority is a property of the SOURCE, not the fact. The purifier's
# AuthorityWinsPolicy consults this dict — entries not listed score
# 0.0, which is the standard "unranked sources lose to ranked ones"
# behaviour from src/kb/conflict.py.
# ----------------------------------------------------------------------


SOURCE_AUTHORITY = {
    "IAU_2023":             1.00,   # International Astronomical Union
    "NASA_factsheet":       0.95,
    "peer_reviewed_paper":  0.95,
    "textbook_2010":        0.70,
    "britannica_1985":      0.50,
    "old_encyclopedia_1965": 0.30,
    "blog_post":            0.15,
}


# ----------------------------------------------------------------------
# Raw fact rows.
#
# Tuple layout: (subject, relation, object, source, valid_from,
# valid_to, confidence). `None` for unbounded temporal endpoints;
# default confidence of 1.0 if omitted (we always set it explicitly
# here so the noise model is visible).
#
# Grouped by subject for readability. Within each group:
#   * "consensus" rows — multiple sources agree → corroboration target
#   * "conflict" rows — different values for a functional property
#   * "low-conf" rows — wrong or imprecise; will be pruned or beaten
# ----------------------------------------------------------------------


_RAW_FACTS: list[tuple] = [
    # -- Mercury -----------------------------------------------------
    # Corroboration: 4 sources agree it's a Planet.
    ("Mercury", "IS_A", "Planet", "IAU_2023",              None, None, 1.00),
    ("Mercury", "IS_A", "Planet", "NASA_factsheet",        None, None, 0.95),
    ("Mercury", "IS_A", "Planet", "britannica_1985",       None, None, 0.55),
    ("Mercury", "IS_A", "Planet", "textbook_2010",         None, None, 0.70),
    # Mass — modern consensus value plus an older disagreeing value.
    ("Mercury", "MASS_KG", "3.30e23", "IAU_2023",          None, None, 1.00),
    ("Mercury", "MASS_KG", "3.30e23", "NASA_factsheet",    None, None, 0.95),
    ("Mercury", "MASS_KG", "3.30e23", "textbook_2010",     None, None, 0.70),
    ("Mercury", "MASS_KG", "3.18e23", "britannica_1985",   None, None, 0.55),  # outdated
    # Radius.
    ("Mercury", "RADIUS_KM", "2440",  "IAU_2023",          None, None, 1.00),
    ("Mercury", "RADIUS_KM", "2440",  "NASA_factsheet",    None, None, 0.95),
    # Orbital period — modern + low-confidence imprecise blog value.
    ("Mercury", "ORBITAL_PERIOD_DAYS", "87.97",
     "IAU_2023",        None, None, 1.00),
    ("Mercury", "ORBITAL_PERIOD_DAYS", "88",
     "blog_post",       None, None, 0.40),                                    # low precision

    # -- Earth ------------------------------------------------------
    ("Earth", "IS_A", "Planet", "IAU_2023",                None, None, 1.00),
    ("Earth", "IS_A", "Planet", "NASA_factsheet",          None, None, 0.95),
    ("Earth", "IS_A", "InnerPlanet", "textbook_2010",      None, None, 0.70),
    ("Earth", "MASS_KG", "5.972e24", "IAU_2023",           None, None, 1.00),
    ("Earth", "MASS_KG", "5.972e24", "NASA_factsheet",     None, None, 0.95),
    ("Earth", "MASS_KG", "5.0e24",   "blog_post",          None, None, 0.20),  # wrong
    ("Earth", "RADIUS_KM", "6371",   "IAU_2023",           None, None, 1.00),

    # -- Mars -------------------------------------------------------
    ("Mars", "IS_A", "Planet", "IAU_2023",                 None, None, 1.00),
    ("Mars", "IS_A", "Planet", "NASA_factsheet",           None, None, 0.95),
    ("Mars", "MASS_KG", "6.39e23",   "IAU_2023",           None, None, 1.00),
    ("Mars", "ORBITAL_PERIOD_DAYS", "687",  "IAU_2023",    None, None, 1.00),
    ("Mars", "ORBITAL_PERIOD_DAYS", "685",  "blog_post",   None, None, 0.30),  # wrong

    # -- Jupiter ----------------------------------------------------
    ("Jupiter", "IS_A", "Planet", "IAU_2023",              None, None, 1.00),
    ("Jupiter", "IS_A", "Planet", "NASA_factsheet",        None, None, 0.95),
    ("Jupiter", "IS_A", "OuterPlanet", "textbook_2010",    None, None, 0.70),
    ("Jupiter", "MASS_KG", "1.898e27", "IAU_2023",         None, None, 1.00),
    ("Jupiter", "MASS_KG", "1.9e27",  "britannica_1985",   None, None, 0.55),  # rounded; treated as conflict

    # -- Saturn -----------------------------------------------------
    ("Saturn", "IS_A", "Planet", "IAU_2023",               None, None, 1.00),
    ("Saturn", "RADIUS_KM", "58232", "IAU_2023",           None, None, 1.00),
    ("Saturn", "RADIUS_KM", "60000", "old_encyclopedia_1965",
                                                            None, None, 0.20),  # imprecise

    # -- Pluto: the controversial one -------------------------------
    # Historical classification: Planet before 2006-08-24.
    ("Pluto", "IS_A", "Planet", "old_encyclopedia_1965",
                                                            None, "2006-08-23", 0.30),
    ("Pluto", "IS_A", "Planet", "britannica_1985",
                                                            None, "2006-08-23", 0.55),
    ("Pluto", "IS_A", "Planet", "textbook_2010",   # early-edition entry
                                                            None, "2006-08-23", 0.70),
    # Reclassified by IAU 2006-08-24.
    ("Pluto", "IS_A", "DwarfPlanet", "IAU_2023",
                                                            "2006-08-24", None, 1.00),
    ("Pluto", "IS_A", "DwarfPlanet", "NASA_factsheet",
                                                            "2006-08-24", None, 0.95),
    # Discovery: corroborated agreement (1930).
    ("Pluto", "DISCOVERY_DATE", "1930", "IAU_2023",        None, None, 1.00),
    ("Pluto", "DISCOVERY_DATE", "1930", "britannica_1985", None, None, 0.55),
    ("Pluto", "DISCOVERY_DATE", "1930", "textbook_2010",   None, None, 0.70),
    ("Pluto", "DISCOVERER", "Clyde Tombaugh", "IAU_2023",  None, None, 1.00),
    ("Pluto", "DISCOVERER", "Clyde Tombaugh", "NASA_factsheet",
                                                            None, None, 0.95),

    # -- Andromeda Galaxy -------------------------------------------
    ("Andromeda Galaxy", "IS_A", "Galaxy", "IAU_2023",     None, None, 1.00),
    ("Andromeda Galaxy", "IS_A", "Galaxy", "NASA_factsheet", None, None, 0.95),
    # Distance has been progressively revised upward. Modern value
    # corroborated by three high-authority sources.
    ("Andromeda Galaxy", "DISTANCE_LIGHT_YEARS", "2.5e6",
     "IAU_2023",            None, None, 1.00),
    ("Andromeda Galaxy", "DISTANCE_LIGHT_YEARS", "2.5e6",
     "NASA_factsheet",      None, None, 0.95),
    ("Andromeda Galaxy", "DISTANCE_LIGHT_YEARS", "2.5e6",
     "peer_reviewed_paper", None, None, 0.95),
    ("Andromeda Galaxy", "DISTANCE_LIGHT_YEARS", "2.0e6",
     "britannica_1985",     None, None, 0.55),                                 # outdated
    ("Andromeda Galaxy", "DISTANCE_LIGHT_YEARS", "1.0e6",
     "old_encyclopedia_1965", None, None, 0.30),                                # very outdated
    ("Andromeda Galaxy", "DISTANCE_LIGHT_YEARS", "0.9e6",
     "blog_post",           None, None, 0.15),                                 # wrong

    # -- The Sun ----------------------------------------------------
    ("Sun", "IS_A", "Star", "IAU_2023",                    None, None, 1.00),
    ("Sun", "IS_A", "Star", "NASA_factsheet",              None, None, 0.95),
    ("Sun", "MASS_KG", "1.989e30",   "IAU_2023",           None, None, 1.00),
    ("Sun", "MASS_KG", "1.989e30",   "NASA_factsheet",     None, None, 0.95),
    ("Sun", "MASS_KG", "1.989e30",   "peer_reviewed_paper",
                                                            None, None, 0.95),
    ("Sun", "MASS_KG", "2.0e30",     "blog_post",          None, None, 0.20),  # rounded; treated as conflict

    # -- Uranus / Neptune (discovery facts) -------------------------
    ("Uranus", "IS_A", "Planet", "IAU_2023",               None, None, 1.00),
    ("Uranus", "DISCOVERY_DATE", "1781", "IAU_2023",       None, None, 1.00),
    ("Uranus", "DISCOVERER", "William Herschel",
     "IAU_2023",            None, None, 1.00),
    ("Neptune", "IS_A", "Planet", "IAU_2023",              None, None, 1.00),
    ("Neptune", "DISCOVERY_DATE", "1846", "IAU_2023",      None, None, 1.00),
    ("Neptune", "DISCOVERER", "Johann Galle",              # multi-discoverer dispute possible
     "IAU_2023",            None, None, 0.85),
    ("Neptune", "DISCOVERER", "Urbain Le Verrier",
     "britannica_1985",     None, None, 0.55),

    # -- Standalone low-confidence facts -- noise the conflict
    # resolver can't filter (no contradicting value exists), so they
    # only get dropped by the confidence-threshold pruning stage.
    ("Saturn", "DENSITY_GCM3", "0.687", "blog_post",       None, None, 0.40),
    ("Mercury", "SURFACE_TEMP_K", "440", "blog_post",      None, None, 0.45),
    ("Eris", "IS_A", "DwarfPlanet", "blog_post",           None, None, 0.30),
]


# ----------------------------------------------------------------------
# Loader.
# ----------------------------------------------------------------------


def build_noisy_kb() -> KB:
    """Materialise the noisy corpus as a KB ready for purification.

    Loads `source_authority` so the AuthorityWinsPolicy works without
    extra wiring. Sets `source_sentence_idx = -1` on every triple
    (no sentence-level provenance — these are facts from named
    sources, not extractor output)."""
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
