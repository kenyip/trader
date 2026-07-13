import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from trader_platform.research.intraday_session_data import (
    append_ohlcv_archive,
    build_session_frame,
    download_session_frame,
)


class IntradaySessionDataTest(unittest.TestCase):
    def test_append_archive_preserves_history_replaces_overlaps_and_records_provenance(self):
        first_index = pd.DatetimeIndex(
            ["2026-05-01 09:30", "2026-05-01 10:00"],
            tz="America/New_York",
        )
        second_index = pd.DatetimeIndex(
            ["2026-05-01 10:00", "2026-05-01 10:30"],
            tz="America/New_York",
        )
        first = self._raw(first_index, closes=[50.0, 51.0])
        second = self._raw(second_index, closes=[51.5, 52.0])

        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "BAC_30m.csv"
            metadata_path = Path(directory) / "BAC_30m.metadata.json"
            archived, first_summary = append_ohlcv_archive(
                first,
                archive_path=archive_path,
                metadata_path=metadata_path,
                symbol="BAC",
                interval="30m",
                requested_period="60d",
                captured_at="2026-05-01T14:00:00+00:00",
            )
            archived, second_summary = append_ohlcv_archive(
                second,
                archive_path=archive_path,
                metadata_path=metadata_path,
                symbol="BAC",
                interval="30m",
                requested_period="60d",
                captured_at="2026-05-01T14:30:00+00:00",
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(len(archived), 3)
        self.assertEqual(archived.index.tolist(), sorted(archived.index.tolist()))
        self.assertEqual(float(archived.loc[second_index[0], "close"]), 51.5)
        self.assertEqual(first_summary["new_rows"], 2)
        self.assertEqual(second_summary["new_rows"], 1)
        self.assertEqual(second_summary["replaced_rows"], 1)
        self.assertEqual(metadata["symbol"], "BAC")
        self.assertEqual(metadata["interval"], "30m")
        self.assertEqual(len(metadata["captures"]), 2)
        self.assertEqual(metadata["captures"][-1]["archive_rows"], 3)

    def test_append_archive_round_trips_new_york_dst_offsets(self):
        captures = [
            self._raw(
                pd.DatetimeIndex([timestamp], tz="America/New_York"),
                closes=[close],
            )
            for timestamp, close in (
                ("2026-10-30 15:30", 50.0),
                ("2026-11-02 09:30", 51.0),
                ("2026-11-02 10:00", 52.0),
            )
        ]

        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "BAC_30m.csv"
            metadata_path = Path(directory) / "BAC_30m.metadata.json"
            archived = None
            for number, capture in enumerate(captures):
                archived, _ = append_ohlcv_archive(
                    capture,
                    archive_path=archive_path,
                    metadata_path=metadata_path,
                    symbol="BAC",
                    interval="30m",
                    requested_period="60d",
                    captured_at=f"2026-11-02T1{number}:00:00+00:00",
                )

        self.assertIsNotNone(archived)
        self.assertEqual(len(archived), 3)
        self.assertEqual(str(archived.index.tz), "America/New_York")

    def test_append_archive_rejects_invalid_capture_before_writing(self):
        invalid = self._raw(
            pd.DatetimeIndex(["2026-05-01 09:30"], tz="America/New_York")
        ).drop(columns=["volume"])

        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "BAC_30m.csv"
            metadata_path = Path(directory) / "BAC_30m.metadata.json"
            with self.assertRaisesRegex(ValueError, "missing OHLCV"):
                append_ohlcv_archive(
                    invalid,
                    archive_path=archive_path,
                    metadata_path=metadata_path,
                    symbol="BAC",
                    interval="30m",
                    requested_period="60d",
                    captured_at="2026-05-01T14:00:00+00:00",
                )

            self.assertFalse(archive_path.exists())
            self.assertFalse(metadata_path.exists())

    def test_append_archive_rejects_nonfinite_capture_before_writing(self):
        invalid = self._raw(
            pd.DatetimeIndex(
                ["2026-05-01 09:30", "2026-05-01 10:00"],
                tz="America/New_York",
            )
        )
        invalid.loc[invalid.index[0], "close"] = np.inf

        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "BAC_30m.csv"
            metadata_path = Path(directory) / "BAC_30m.metadata.json"
            with self.assertRaisesRegex(ValueError, "nonnumeric or nonfinite"):
                append_ohlcv_archive(
                    invalid,
                    archive_path=archive_path,
                    metadata_path=metadata_path,
                    symbol="BAC",
                    interval="30m",
                    requested_period="60d",
                    captured_at="2026-05-01T14:00:00+00:00",
                )

            self.assertFalse(archive_path.exists())
            self.assertFalse(metadata_path.exists())

    def test_append_archive_rejects_source_change_without_mutating(self):
        capture = self._raw(
            pd.DatetimeIndex(["2026-05-01 09:30"], tz="America/New_York")
        )

        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "BAC_30m.csv"
            metadata_path = Path(directory) / "BAC_30m.metadata.json"
            append_ohlcv_archive(
                capture,
                archive_path=archive_path,
                metadata_path=metadata_path,
                symbol="BAC",
                interval="30m",
                requested_period="60d",
                captured_at="2026-05-01T14:00:00+00:00",
            )
            before_archive = archive_path.read_bytes()
            before_metadata = metadata_path.read_bytes()

            with self.assertRaisesRegex(ValueError, "source mismatch"):
                append_ohlcv_archive(
                    capture,
                    archive_path=archive_path,
                    metadata_path=metadata_path,
                    symbol="BAC",
                    interval="30m",
                    requested_period="60d",
                    captured_at="2026-05-01T14:30:00+00:00",
                    source="other-provider",
                )

            self.assertEqual(archive_path.read_bytes(), before_archive)
            self.assertEqual(metadata_path.read_bytes(), before_metadata)

    def test_download_session_frame_archives_intraday_and_daily_warmup(self):
        intraday_sessions = pd.bdate_range("2026-05-01", periods=5)
        intraday_index = pd.DatetimeIndex(
            [
                pd.Timestamp(day).tz_localize("America/New_York")
                + pd.Timedelta(hours=hour, minutes=minute)
                for day in intraday_sessions
                for hour, minute in ((9, 30), (15, 30))
            ]
        )
        daily_index = pd.bdate_range("2026-03-02", periods=45, tz="America/New_York")
        intraday = self._raw(intraday_index)
        daily = self._raw(daily_index)

        def downloader(symbol, *, period, interval, **kwargs):
            self.assertEqual(symbol, "BAC")
            return intraday if interval == "30m" else daily

        with tempfile.TemporaryDirectory() as directory:
            result = download_session_frame(
                "bac",
                archive_dir=Path(directory),
                captured_at="2026-05-08T21:00:00+00:00",
                downloader=downloader,
            )
            paths = {path.name for path in Path(directory).iterdir()}

        self.assertEqual(result["market_date"].nunique(), 5)
        self.assertEqual(result.attrs["archive_provenance"]["intraday"]["archive_market_dates"], 5)
        self.assertGreaterEqual(
            result.attrs["archive_provenance"]["daily"]["archive_market_dates"],
            40,
        )
        self.assertEqual(
            paths,
            {
                "BAC_30m.csv",
                "BAC_30m.metadata.json",
                "BAC_1d.csv",
                "BAC_1d.metadata.json",
            },
        )

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

    def test_archived_daily_warmup_makes_early_intraday_dates_usable_without_lookahead(self):
        intraday_sessions = pd.bdate_range("2026-05-01", periods=5)
        intraday_timestamps = []
        intraday_closes = []
        for day_number, day in enumerate(intraday_sessions):
            for hour, minute, offset in ((9, 30, 0.0), (15, 30, 0.5)):
                intraday_timestamps.append(
                    pd.Timestamp(day).tz_localize("America/New_York")
                    + pd.Timedelta(hours=hour, minutes=minute)
                )
                intraday_closes.append(70.0 + day_number + offset)
        intraday = self._raw(pd.DatetimeIndex(intraday_timestamps), closes=intraday_closes)
        warmup_index = pd.bdate_range("2026-04-01", periods=22, tz="America/New_York")
        warmup = self._raw(warmup_index, closes=[50.0 + i for i in range(len(warmup_index))])

        result = build_session_frame(
            intraday,
            min_daily_history=5,
            prior_daily=warmup,
        )

        self.assertEqual(result["market_date"].nunique(), 5)
        self.assertTrue(all(result["feature_market_date"] < result["market_date"]))
        self.assertEqual(
            set(result["data_provenance"]),
            {"archived_30m_underlying_with_prior_daily_features"},
        )

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
