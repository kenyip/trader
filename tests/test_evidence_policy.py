import unittest

from trader_platform.research.evidence_policy import (
    OBSERVED_OPTION_MARKS,
    PROXY_OPTION_MARKS,
    assess_l1_evidence,
)


class EvidencePolicyTest(unittest.TestCase):
    def test_black_scholes_proxy_cannot_earn_l1_even_with_good_metrics(self):
        result = assess_l1_evidence(
            option_mark_provenance=PROXY_OPTION_MARKS,
            complete_observed_trade_joins=True,
            observed_history_sufficient_for_edge=True,
            observed_market_dates=500,
        )
        self.assertFalse(result.eligible)
        self.assertEqual(result.reason, "proxy_or_unknown_option_marks_cannot_earn_l1")

    def test_three_observed_dates_are_plumbing_not_edge_evidence(self):
        result = assess_l1_evidence(
            option_mark_provenance=OBSERVED_OPTION_MARKS,
            complete_observed_trade_joins=True,
            observed_history_sufficient_for_edge=True,
            observed_market_dates=3,
        )
        self.assertFalse(result.eligible)
        self.assertEqual(result.reason, "three_or_fewer_market_dates_are_plumbing_not_edge_evidence")

    def test_observed_marks_still_require_complete_joins_and_sufficient_history(self):
        incomplete = assess_l1_evidence(
            option_mark_provenance=OBSERVED_OPTION_MARKS,
            complete_observed_trade_joins=False,
            observed_history_sufficient_for_edge=True,
            observed_market_dates=100,
        )
        insufficient = assess_l1_evidence(
            option_mark_provenance=OBSERVED_OPTION_MARKS,
            complete_observed_trade_joins=True,
            observed_history_sufficient_for_edge=False,
            observed_market_dates=100,
        )
        eligible = assess_l1_evidence(
            option_mark_provenance=OBSERVED_OPTION_MARKS,
            complete_observed_trade_joins=True,
            observed_history_sufficient_for_edge=True,
            observed_market_dates=100,
        )
        self.assertFalse(incomplete.eligible)
        self.assertFalse(insufficient.eligible)
        self.assertTrue(eligible.eligible)


if __name__ == "__main__":
    unittest.main()
