"""Worked-example corpus for the microtheory / framing-scope feature.

ONE subject — a recession — carried under FOUR incompatible schools of
economic thought at once. Each school is a microtheory (a `Triple.scope`):
internally coherent, sourced, with its own classification, cause,
prescription, unit of analysis, and key evidence. The schools genuinely
disagree; that disagreement is the point, and it is preserved as data.

A handful of GLOBAL facts (scope=None) are agreed by everyone — the raw
observations no school disputes.

This is the non-temporal analogue of the diachronic suite: there the scope
axis is the historical era; here it is the school of thought.
"""
from __future__ import annotations

from kb.query import KB, Triple

SUBJECT = "the_recession"

# The four microtheories (schools). Each value is a Triple.scope.
KEYNESIAN = "keynesian_school"
AUSTRIAN = "austrian_school"
MONETARIST = "monetarist_school"
MMT = "mmt_school"
SCHOOLS = [KEYNESIAN, AUSTRIAN, MONETARIST, MMT]

# (subject, relation, object, source, sentence, valid_from, valid_to, conf, scope)
_FACTS = [
    # --- GLOBAL: the agreed, framing-independent observations -------------
    (SUBJECT, "OCCURRED_IN", "2008", "national_accounts", 1, None, None, 1.0, None),
    (SUBJECT, "HAS_OBSERVATION", "gdp_contracted", "national_accounts", 2, None, None, 1.0, None),
    (SUBJECT, "HAS_OBSERVATION", "unemployment_rose", "labour_statistics", 1, None, None, 1.0, None),

    # --- KEYNESIAN microtheory -------------------------------------------
    (SUBJECT, "IS_A", "aggregate_demand_shortfall", "keynes_general_theory", 12, None, None, 1.0, KEYNESIAN),
    (SUBJECT, "PRIMARY_CAUSE", "collapse_in_aggregate_demand", "keynes_general_theory", 13, None, None, 1.0, KEYNESIAN),
    (SUBJECT, "PRESCRIBES", "fiscal_stimulus", "keynes_general_theory", 20, None, None, 1.0, KEYNESIAN),
    (SUBJECT, "UNIT_OF_ANALYSIS", "aggregate_economy", "keynes_general_theory", 3, None, None, 1.0, KEYNESIAN),
    (SUBJECT, "KEY_EVIDENCE", "idle_capacity_with_willing_workers", "keynesian_review_2010", 4, None, None, 0.9, KEYNESIAN),

    # --- AUSTRIAN microtheory --------------------------------------------
    (SUBJECT, "IS_A", "malinvestment_liquidation", "mises_human_action", 41, None, None, 1.0, AUSTRIAN),
    (SUBJECT, "PRIMARY_CAUSE", "artificially_low_interest_rates", "hayek_prices_production", 7, None, None, 1.0, AUSTRIAN),
    (SUBJECT, "PRESCRIBES", "allow_liquidation_no_bailout", "mises_human_action", 55, None, None, 1.0, AUSTRIAN),
    (SUBJECT, "UNIT_OF_ANALYSIS", "capital_structure", "hayek_prices_production", 2, None, None, 1.0, AUSTRIAN),
    (SUBJECT, "KEY_EVIDENCE", "credit_boom_preceded_bust", "austrian_review_2011", 6, None, None, 0.9, AUSTRIAN),

    # --- MONETARIST microtheory ------------------------------------------
    (SUBJECT, "IS_A", "monetary_contraction", "friedman_monetary_history", 88, None, None, 1.0, MONETARIST),
    (SUBJECT, "PRIMARY_CAUSE", "collapse_in_money_supply", "friedman_monetary_history", 90, None, None, 1.0, MONETARIST),
    (SUBJECT, "PRESCRIBES", "expand_money_supply", "friedman_monetary_history", 95, None, None, 1.0, MONETARIST),
    (SUBJECT, "UNIT_OF_ANALYSIS", "money_stock", "friedman_monetary_history", 5, None, None, 1.0, MONETARIST),
    (SUBJECT, "KEY_EVIDENCE", "velocity_and_M2_data", "monetarist_review_2009", 3, None, None, 0.9, MONETARIST),

    # --- MMT microtheory --------------------------------------------------
    (SUBJECT, "IS_A", "sectoral_balance_imbalance", "mmt_primer", 33, None, None, 1.0, MMT),
    (SUBJECT, "PRIMARY_CAUSE", "private_sector_deleveraging", "mmt_primer", 35, None, None, 1.0, MMT),
    (SUBJECT, "PRESCRIBES", "government_deficit_spending", "mmt_primer", 40, None, None, 1.0, MMT),
    (SUBJECT, "UNIT_OF_ANALYSIS", "sectoral_financial_balances", "mmt_primer", 2, None, None, 1.0, MMT),
    (SUBJECT, "KEY_EVIDENCE", "rising_private_savings_desire", "mmt_review_2012", 8, None, None, 0.9, MMT),
]

# The relations on which the schools are FUNCTIONALLY single-valued *within*
# a school — used to show that cross-school differences are NOT contradictions.
FUNCTIONAL_RELATIONS = {"IS_A", "PRIMARY_CAUSE", "PRESCRIBES", "UNIT_OF_ANALYSIS"}


def build_recession_kb() -> KB:
    triples = [Triple(s, r, o, src, idx, vf, vt, conf, scope)
               for (s, r, o, src, idx, vf, vt, conf, scope) in _FACTS]
    return KB(triples=triples, alias_map={}, n_articles=0)
