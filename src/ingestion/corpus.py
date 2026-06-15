"""Corpus for the ingestion / import-consistency worked example.

We import records for ONE asset (PUMP-7) from four "authoritative" sources
into a single global KB — no scoping, because the intent is one coherent
asset record, not several legitimate framings. The sources collectively
contain three kinds of contradiction:

  1. DIRECT functional violation  — two different RATED_FLOW values.
  2. DIRECT disjoint-class clash   — InService vs Decommissioned.
  3. LATENT (derived) contradiction — each source classifies the pump
     plausibly, but the ontology's subclass closure makes PUMP-7 a member
     of two physically-incompatible machine families at once. No single
     triple is wrong; the inconsistency only appears after reasoning.

The ontology is ordinary engineering taxonomy — the kind any asset master
would encode.
"""
from __future__ import annotations

from kb.query import KB, Triple
from kb.ontology import Ontology

ASSET = "PUMP-7"


def build_ontology() -> Ontology:
    return (Ontology()
            .declare_classes("CentrifugalPump", "PositiveDisplacementPump",
                             "RotodynamicMachine", "PositiveDisplacementMachine",
                             "InService", "Decommissioned")
            # taxonomy: each pump kind rolls up to a machine family
            .subclass_of("CentrifugalPump", "RotodynamicMachine")
            .subclass_of("PositiveDisplacementPump", "PositiveDisplacementMachine")
            # physical reality: a machine can't be both families, and an asset
            # can't be simultaneously in service and decommissioned
            .disjoint_with("RotodynamicMachine", "PositiveDisplacementMachine")
            .disjoint_with("InService", "Decommissioned")
            .functional_property("RATED_FLOW_GPM"))


# (subject, relation, object, source, sentence)
_RECORDS = [
    # --- vendor_export_A: a centrifugal pump, 500 gpm ------------------
    (ASSET, "IS_A", "CentrifugalPump", "vendor_export_A", 11),
    (ASSET, "RATED_FLOW_GPM", "500", "vendor_export_A", 12),
    (ASSET, "MANUFACTURER", "Acme", "vendor_export_A", 3),

    # --- vendor_export_B: a positive-displacement pump ----------------
    # (looks fine on its own; collides with A only through the taxonomy)
    (ASSET, "IS_A", "PositiveDisplacementPump", "vendor_export_B", 7),
    (ASSET, "MANUFACTURER", "Acme", "vendor_export_B", 2),

    # --- legacy_cmms: different rated flow, and marked decommissioned --
    (ASSET, "RATED_FLOW_GPM", "650", "legacy_cmms", 88),
    (ASSET, "IS_A", "Decommissioned", "legacy_cmms", 90),

    # --- field_audit_2024: confirms it is in service ------------------
    (ASSET, "IS_A", "InService", "field_audit_2024", 4),
]

SOURCES = ["vendor_export_A", "vendor_export_B", "legacy_cmms", "field_audit_2024"]


def build_import_kb() -> KB:
    """The naive merge: append every source's records into one global KB."""
    triples = [Triple(s, r, o, src, idx) for (s, r, o, src, idx) in _RECORDS]
    return KB(triples=triples, alias_map={}, n_articles=0,
              source_authority={"vendor_export_A": 0.8, "vendor_export_B": 0.8,
                                "legacy_cmms": 0.3, "field_audit_2024": 0.95})
