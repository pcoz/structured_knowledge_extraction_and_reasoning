"""Ingestion / import-consistency worked example.

Demonstrates what happens when you try to IMPORT data from one or more
sources into a single coherent body of knowledge and the data turns out to
be self-contradictory — including the deep case where no single triple is
wrong, but the logical CLOSURE of the sources is inconsistent.

SKEAR computes that closure on import and surfaces every contradiction with
the exact source sentences that produced it (a "since X therefore Y" trail),
rather than silently absorbing the inconsistency.

Run (from src/):  python -m ingestion.analyse
"""
