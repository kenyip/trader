import unittest

import pandas as pd

from scripts.pcs_session_time_chronological_lab import (
    complete_gate,
    select_train_bucket,
    summarize_data_range,
    split_by_market_date,
)


class PcsSessionTimeChronologicalLabTest(unittest.TestCase):
    def test_split_is_chronological_and_never_splits_one_market_date(self):
        index = pd.DatetimeIndex(
            [
                f"2026-05-{day:02d} {hour:02d}:30"
                for day in range(1, 11)
                for hour in (9, 14)
            ]
        )
        frame = pd.DataFrame(
            {
                "market_date": [timestamp.date() for timestamp in index],
                "close": range(len(index)),
            },
            index=index,
        )

        train, holdout = split_by_market_date(frame, train_fraction=0.6)

        self.assertEqual(train["market_date"].nunique(), 6)
        self.assertEqual(holdout["market_date"].nunique(), 4)
        self.assertLess(max(train["market_date"]), min(holdout["market_date"]))

    def test_data_range_distinguishes_raw_archive_from_usable_feature_density(self):
        dates = pd.bdate_range("2026-05-01", periods=10)
        index = pd.DatetimeIndex(
            [
                pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=30)
                for day in dates
            ]
        )
        frame = pd.DataFrame(
            {
                "market_date": [timestamp.date() for timestamp in index],
                "feature_market_date": [
                    (timestamp - pd.Timedelta(days=1)).date() for timestamp in index
                ],
                "close": range(len(index)),
            },
            index=index,
        )
        frame.attrs["archive_provenance"] = {
            "source": "yfinance",
            "captured_at": "2026-05-15T21:00:00+00:00",
            "intraday": {"archive_rows": 780, "archive_market_dates": 60},
            "daily": {"archive_rows": 252, "archive_market_dates": 252},
        }
        train, holdout = split_by_market_date(frame)

        summary = summarize_data_range(frame, train, holdout)

        self.assertEqual(summary["raw_intraday_archive_rows"], 780)
        self.assertEqual(summary["raw_intraday_market_dates"], 60)
        self.assertEqual(summary["daily_feature_archive_market_dates"], 252)
        self.assertEqual(summary["usable_market_dates"], 10)
        self.assertEqual(summary["train_dates"], 6)
        self.assertEqual(summary["holdout_dates"], 4)
        self.assertEqual(summary["feature_date_violations"], 0)

    def test_train_selection_prefers_best_worst_cost_axis_only_among_gate_passes(self):
        rows = {
            "open": {
                "slip_5pct": self._axis(pnl=20.0, passed=True),
                "fixed_0p01": self._axis(pnl=10.0, passed=True),
            },
            "midday": {
                "slip_5pct": self._axis(pnl=100.0, passed=False),
                "fixed_0p01": self._axis(pnl=90.0, passed=True),
            },
            "late": {
                "slip_5pct": self._axis(pnl=8.0, passed=True),
                "fixed_0p01": self._axis(pnl=7.0, passed=True),
            },
        }

        selected = select_train_bucket(rows)

        self.assertEqual(selected, "open")

    def test_passing_holdout_cannot_rescue_a_failed_train_gate(self):
        passing_axes = {
            "slip_5pct": self._axis(pnl=10.0, passed=True),
            "fixed_0p01": self._axis(pnl=8.0, passed=True),
        }
        failing_train = {
            "slip_5pct": self._axis(pnl=-1.0, passed=False),
            "fixed_0p01": self._axis(pnl=8.0, passed=True),
        }
        windows = {
            "slip_5pct": {"window_max_dd": 10.0, "dense_negative_n": 0, "integrity": True},
            "fixed_0p01": {"window_max_dd": 10.0, "dense_negative_n": 0, "integrity": True},
        }

        self.assertFalse(complete_gate(failing_train, passing_axes, windows))
        self.assertTrue(complete_gate(passing_axes, passing_axes, windows))

    @staticmethod
    def _axis(*, pnl: float, passed: bool) -> dict:
        return {
            "pnl": pnl,
            "gate_pass": passed,
            "n_trades": 4,
            "max_dd": 10.0,
            "max_loss_usd": 100.0,
            "ledger_delta": 0.0,
            "same_bar_reentries": 0,
            "same_session_bucket_reentries": 0,
        }


if __name__ == "__main__":
    unittest.main()
