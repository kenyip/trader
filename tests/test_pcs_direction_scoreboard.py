import unittest

from scripts.pcs_direction_scoreboard import build_scoreboard


class DirectionScoreboardTest(unittest.TestCase):
    def test_compares_structures_only_on_shared_regime_windows(self):
        regime = {
            "evidence": {
                "option_mark_provenance": "observed_historical_option_quotes",
                "complete_observed_trade_joins": True,
                "observed_history_sufficient_for_edge": True,
                "observed_market_dates": 100,
            },
            "results": [
                {
                    "hyp_id": "pcs",
                    "symbol": "AAA",
                    "structure": "put_credit_spread",
                    "full_history": {"max_loss_usd": 80.0, "dd": 70.0},
                    "yearly_and_chunks": [
                        {"label": "year_2025", "ok": True, "n_trades": 5, "pnl": 10.0, "dd": 20.0},
                        {"label": "chunk6m_only_pcs", "ok": True, "n_trades": 9, "pnl": -99.0, "dd": 99.0},
                    ],
                    "canonical": [
                        {"label": "canon_flat", "ok": True, "n_trades": 3, "pnl": -5.0, "dd": 8.0}
                    ],
                    "summary": {"regime_hold": True},
                },
                {
                    "hyp_id": "ccs",
                    "symbol": "BBB",
                    "structure": "call_credit_spread",
                    "full_history": {"max_loss_usd": 120.0, "dd": 90.0},
                    "yearly_and_chunks": [
                        {"label": "year_2025", "ok": True, "n_trades": 4, "pnl": -7.0, "dd": 30.0}
                    ],
                    "canonical": [
                        {"label": "canon_flat", "ok": True, "n_trades": 0, "pnl": 0.0, "dd": 0.0}
                    ],
                    "summary": {"regime_hold": True},
                },
            ]
        }
        cost = {
            "results": [
                {
                    "hyp_id": "pcs",
                    "by_slip": [{"slippage_pct": 0.05, "n_trades": 12, "pnl": 4.0, "verdict": "SHIP"}],
                    "summary": {"cost_hold": True},
                },
                {
                    "hyp_id": "ccs",
                    "by_slip": [{"slippage_pct": 0.05, "n_trades": 8, "pnl": -2.0, "verdict": "NULL"}],
                    "summary": {"cost_hold": True},
                },
            ]
        }

        result = build_scoreboard(regime, cost)

        self.assertEqual(result["common_window_labels"], ["canon_flat", "year_2025"])
        pcs = next(row for row in result["rows"] if row["hyp_id"] == "pcs")
        self.assertEqual(pcs["direction_bias"], "bullish")
        self.assertEqual(pcs["common_dense_negative_n"], 1)
        self.assertEqual(pcs["common_window_max_dd"], 20.0)
        self.assertTrue(pcs["after_cost_positive_nonvacuous"])
        self.assertEqual(result["metric_eligible_hyp_ids"], ["pcs"])
        self.assertEqual(result["l1_hyp_ids"], [])
        self.assertEqual(result["l1_evidence"]["option_mark_provenance"], "black_scholes_proxy")
        self.assertEqual(result["l1_evidence"]["reason"], "proxy_or_unknown_option_marks_cannot_earn_l1")
        self.assertNotEqual(result["leader_hyp_id"], "ccs")

    def test_quality_rank_prefers_tighter_risk_before_dense_negative_count(self):
        regime = {
            "results": [
                {
                    "hyp_id": "tight",
                    "symbol": "AAA",
                    "structure": "put_credit_spread",
                    "full_history": {"max_loss_usd": 75.0, "dd": 70.0},
                    "yearly_and_chunks": [
                        {"label": "year_2025", "ok": True, "n_trades": 5, "pnl": -2.0, "dd": 70.0}
                    ],
                    "canonical": [],
                    "summary": {"regime_hold": True},
                },
                {
                    "hyp_id": "loose",
                    "symbol": "BBB",
                    "structure": "call_credit_spread",
                    "full_history": {"max_loss_usd": 200.0, "dd": 140.0},
                    "yearly_and_chunks": [
                        {"label": "year_2025", "ok": True, "n_trades": 5, "pnl": 2.0, "dd": 140.0}
                    ],
                    "canonical": [],
                    "summary": {"regime_hold": True},
                },
            ]
        }
        cost = {
            "results": [
                {
                    "hyp_id": hyp_id,
                    "by_slip": [{"slippage_pct": 0.05, "n_trades": 5, "pnl": -5.0, "verdict": "NULL"}],
                    "summary": {"cost_hold": True},
                }
                for hyp_id in ("tight", "loose")
            ]
        }

        result = build_scoreboard(regime, cost)

        self.assertEqual(result["leader_hyp_id"], "tight")


if __name__ == "__main__":
    unittest.main()
