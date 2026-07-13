import unittest

import numpy as np
import pandas as pd

from trader_platform.research.intraday_session_data import build_session_frame


class IntradaySessionDataTest(unittest.TestCase):
    def test_rth_buckets_use_new_york_boundaries_and_drop_extended_hours(self):
        index = pd.DatetimeIndex(
            [
                "2026-04-30 15:30",
                "2026-05-01 09:00",
                "2026-05-01 09:30",
                "2026-05-01 10:30",
                "2026-05-01 11:00",
                "2026-05-01 13:30",
                "2026-05-01 14:00",
                "2026-05-01 15:30",
                "2026-05-01 16:00",
            ],
            tz="America/New_York",
        )
        frame = self._raw(index)

        result = build_session_frame(frame, min_daily_history=1)
        result = result[result["market_date"] == pd.Timestamp("2026-05-01").date()]

        self.assertEqual(
            list(result["session_bucket"]),
            ["open", "open", "midday", "midday", "late", "late"],
        )
        self.assertEqual([timestamp.hour for timestamp in result.index], [9, 10, 11, 13, 14, 15])

    def test_entry_features_come_from_a_prior_completed_session(self):
        sessions = pd.bdate_range("2026-04-01", periods=25)
        timestamps = []
        closes = []
        for day_number, day in enumerate(sessions):
            for hour, minute, offset in ((9, 30, 0.0), (15, 30, 0.5)):
                timestamps.append(
                    pd.Timestamp(day).tz_localize("America/New_York")
                    + pd.Timedelta(hours=hour, minutes=minute)
                )
                closes.append(50.0 + day_number + offset)
        frame = self._raw(pd.DatetimeIndex(timestamps), closes=closes)

        result = build_session_frame(frame, min_daily_history=5)
        target_date = timestamps[-1].date()
        target_rows = result[result["market_date"] == target_date]

        self.assertFalse(target_rows.empty)
        self.assertTrue(all(target_rows["feature_market_date"] < target_date))
        self.assertEqual(target_rows["regime"].nunique(), 1)
        self.assertEqual(target_rows["iv_proxy"].nunique(), 1)

    def test_nonnumeric_or_nonfinite_ohlcv_rows_fail_closed(self):
        index = pd.DatetimeIndex(
            [
                "2026-04-30 15:30",
                "2026-05-01 09:30",
                "2026-05-01 10:00",
                "2026-05-01 10:30",
            ],
            tz="America/New_York",
        )
        frame = self._raw(index)
        frame["close"] = frame["close"].astype(object)
        frame.loc[index[2], "close"] = "bad"
        frame.loc[index[3], "volume"] = np.inf

        result = build_session_frame(frame, min_daily_history=1)

        self.assertEqual(list(result.index), [index[1]])

    @staticmethod
    def _raw(index: pd.DatetimeIndex, closes=None) -> pd.DataFrame:
        close_values = list(closes) if closes is not None else [50.0 + i for i in range(len(index))]
        return pd.DataFrame(
            {
                "open": close_values,
                "high": [value + 0.5 for value in close_values],
                "low": [value - 0.5 for value in close_values],
                "close": close_values,
                "volume": [1000.0] * len(index),
            },
            index=index,
        )


if __name__ == "__main__":
    unittest.main()
