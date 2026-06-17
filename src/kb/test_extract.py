"""Regression tests for the extraction normalisation / validity / alias / SVO
fixes. Runnable standalone (`python src/kb/test_extract.py`) or via pytest.

spaCy-dependent tests SKIP gracefully when spaCy / its model is unavailable, so
the suite passes on the lightweight default install.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # -> src/

from kb.extract import (                                              # noqa: E402
    normalize_entity, strip_trailing_subject, valid_triple,
    canonicalize_entity, build_alias_map, extract_facts_spacy,
    DEFAULT_ASYMMETRIC_RELATIONS, DEFAULT_VERB_RELATIONS, _get_spacy,
)

# ---- entity normalisation (possessive clitics + duplicate-token collapse) ----
def test_normalize_possessive():
    assert normalize_entity("Aristotle's") == "Aristotle"
    assert normalize_entity("Marie Curie's") == "Marie Curie"

def test_normalize_duplicate_collapse():
    assert normalize_entity("Aristotle Aristotle") == "Aristotle"
    assert normalize_entity("Alchemy Alchemy") == "Alchemy"
    assert normalize_entity("Plato") == "Plato"        # untouched

# ---- greedy subject-merge repair ----
def test_strip_trailing_subject():
    assert strip_trailing_subject("Aristotle", "Nicomachean Ethics Aristotle") == "Nicomachean Ethics"
    assert strip_trailing_subject("Plato", "Academy") == "Academy"      # no change

# ---- validity invariant (irreflexive relations, configurable) ----
def test_valid_triple_default():
    assert valid_triple("Aristotle", "TUTORED", "Alexander")
    assert not valid_triple("Aristotle", "WROTE", "Aristotle")
    assert valid_triple("benzene", "SYNTHESIZES", "benzene")           # not in default set

def test_valid_triple_configurable():
    chem = DEFAULT_ASYMMETRIC_RELATIONS | {"SYNTHESIZES"}
    assert not valid_triple("benzene", "SYNTHESIZES", "benzene", chem)  # augmented -> rejected
    legal = {"SUPERSEDES"}
    assert not valid_triple("Act5", "SUPERSEDES", "Act5", legal)        # override

# ---- canonicalisation routes through normalisation ----
def test_canonicalize_normalises():
    assert canonicalize_entity("Aristotle's", {}) == "Aristotle"

# ---- alias map: unambiguous, NER-gated (no Academy -> Academy Awards) ----
def test_alias_map_no_spacy_surname_only():
    am = build_alias_map(["Albert Einstein", "Academy Awards"], nlp=None)
    assert am.get("Einstein") == "Albert Einstein"     # surname aliased
    assert am.get("Academy") is None                   # first token NOT aliased (no spaCy)

def test_alias_map_spacy_person_only():
    nlp = _get_spacy()
    if nlp is None:
        print("   [skip] spaCy unavailable"); return
    am = build_alias_map(["Academy Awards", "Albert Einstein", "Marie Curie"], nlp=nlp)
    assert am.get("Academy") is None and am.get("Awards") is None   # EVENT/ORG: no single-token alias
    assert am.get("Einstein") == "Albert Einstein"
    assert am.get("Curie") == "Marie Curie"

# ---- spaCy dependency-parse SVO (clause-correct; cross-domain) ----
def test_spacy_cicero_trap():
    if _get_spacy() is None:
        print("   [skip] spaCy unavailable"); return
    ts = extract_facts_spacy("Aristotle wrote treatises influencing Cicero.", "Aristotle", 0)
    assert not any(t.object == "Cicero" for t in ts), "must not bind cross-clause Cicero"

def test_spacy_passive_inversion():
    if _get_spacy() is None:
        print("   [skip] spaCy unavailable"); return
    ts = extract_facts_spacy("Aristotle was tutored by Plato.", "Aristotle", 0)
    assert any(t.subject == "Plato" and t.relation == "TUTORED" and t.object == "Aristotle" for t in ts)

def test_spacy_cross_domain_and_config():
    if _get_spacy() is None:
        print("   [skip] spaCy unavailable"); return
    ts = extract_facts_spacy("Acme Corporation founded Beta Division.", "Acme Corporation", 0)
    assert any(t.relation == "FOUNDED" and "Beta Division" in t.object for t in ts)
    vr = {**DEFAULT_VERB_RELATIONS, "synthesize": "SYNTHESIZES"}
    ts2 = extract_facts_spacy("Wohler synthesized Urea.", "Wohler", 0, verb_relations=vr)
    assert any(t.relation == "SYNTHESIZES" and t.object == "Urea" for t in ts2)

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t(); print(f"PASS  {t.__name__}"); passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
