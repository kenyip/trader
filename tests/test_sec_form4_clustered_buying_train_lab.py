import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

import numpy as np
import pandas as pd

from scripts.sec_form4_clustered_buying_train_lab import (
    CANDIDATE_ID,
    FAMILY_ID,
    build_cluster_signals,
    download_archives,
    evaluate_train,
    freeze_price_blueprints,
    parse_quarter_archive,
)


class SecForm4ClusteredBuyingTrainLabTest(unittest.TestCase):
    @staticmethod
    def _zip_payload() -> bytes:
        submissions = pd.DataFrame(
            [
                {
                    "ACCESSION_NUMBER": "good-1",
                    "FILING_DATE": "06-JAN-2025",
                    "PERIOD_OF_REPORT": "03-JAN-2025",
                    "DATE_OF_ORIG_SUB": "",
                    "NO_SECURITIES_OWNED": "0",
                    "NOT_SUBJECT_SEC16": "0",
                    "FORM3_HOLDINGS_REPORTED": "",
                    "FORM4_TRANS_REPORTED": "1",
                    "DOCUMENT_TYPE": "4",
                    "ISSUERCIK": "0000000001",
                    "ISSUERNAME": "Example",
                    "ISSUERTRADINGSYMBOL": "AAPL",
                    "REMARKS": "",
                    "AFF10B5ONE": "0",
                },
                {
                    "ACCESSION_NUMBER": "amended-1",
                    "FILING_DATE": "06-JAN-2025",
                    "PERIOD_OF_REPORT": "03-JAN-2025",
                    "DATE_OF_ORIG_SUB": "03-JAN-2025",
                    "NO_SECURITIES_OWNED": "0",
                    "NOT_SUBJECT_SEC16": "0",
                    "FORM3_HOLDINGS_REPORTED": "",
                    "FORM4_TRANS_REPORTED": "1",
                    "DOCUMENT_TYPE": "4/A",
                    "ISSUERCIK": "0000000001",
                    "ISSUERNAME": "Example",
                    "ISSUERTRADINGSYMBOL": "AAPL",
                    "REMARKS": "",
                    "AFF10B5ONE": "0",
                },
                {
                    "ACCESSION_NUMBER": "late-1",
                    "FILING_DATE": "20-JAN-2025",
                    "PERIOD_OF_REPORT": "03-JAN-2025",
                    "DATE_OF_ORIG_SUB": "",
                    "NO_SECURITIES_OWNED": "0",
                    "NOT_SUBJECT_SEC16": "0",
                    "FORM3_HOLDINGS_REPORTED": "",
                    "FORM4_TRANS_REPORTED": "1",
                    "DOCUMENT_TYPE": "4",
                    "ISSUERCIK": "0000000001",
                    "ISSUERNAME": "Example",
                    "ISSUERTRADINGSYMBOL": "AAPL",
                    "REMARKS": "",
                    "AFF10B5ONE": "0",
                },
            ]
        )
        owners = pd.DataFrame(
            [
                {"ACCESSION_NUMBER": "good-1", "RPTOWNERCIK": "101", "RPTOWNERNAME": "Officer", "RPTOWNER_RELATIONSHIP": "Officer", "RPTOWNER_TITLE": "CEO", "RPTOWNER_TXT": "", "RPTOWNER_STREET1": "", "RPTOWNER_STREET2": "", "RPTOWNER_CITY": "", "RPTOWNER_STATE": "", "RPTOWNER_ZIPCODE": "", "RPTOWNER_STATE_DESC": "", "FILE_NUMBER": ""},
                {"ACCESSION_NUMBER": "amended-1", "RPTOWNERCIK": "102", "RPTOWNERNAME": "Director", "RPTOWNER_RELATIONSHIP": "Director", "RPTOWNER_TITLE": "", "RPTOWNER_TXT": "", "RPTOWNER_STREET1": "", "RPTOWNER_STREET2": "", "RPTOWNER_CITY": "", "RPTOWNER_STATE": "", "RPTOWNER_ZIPCODE": "", "RPTOWNER_STATE_DESC": "", "FILE_NUMBER": ""},
                {"ACCESSION_NUMBER": "late-1", "RPTOWNERCIK": "103", "RPTOWNERNAME": "Director", "RPTOWNER_RELATIONSHIP": "Director", "RPTOWNER_TITLE": "", "RPTOWNER_TXT": "", "RPTOWNER_STREET1": "", "RPTOWNER_STREET2": "", "RPTOWNER_CITY": "", "RPTOWNER_STATE": "", "RPTOWNER_ZIPCODE": "", "RPTOWNER_STATE_DESC": "", "FILE_NUMBER": ""},
            ]
        )
        transaction_columns = [
            "ACCESSION_NUMBER", "NONDERIV_TRANS_SK", "SECURITY_TITLE", "SECURITY_TITLE_FN",
            "TRANS_DATE", "TRANS_DATE_FN", "DEEMED_EXECUTION_DATE", "DEEMED_EXECUTION_DATE_FN",
            "TRANS_FORM_TYPE", "TRANS_CODE", "EQUITY_SWAP_INVOLVED", "EQUITY_SWAP_TRANS_CD_FN",
            "TRANS_TIMELINESS", "TRANS_TIMELINESS_FN", "TRANS_SHARES", "TRANS_SHARES_FN",
            "TRANS_PRICEPERSHARE", "TRANS_PRICEPERSHARE_FN", "TRANS_ACQUIRED_DISP_CD",
            "TRANS_ACQUIRED_DISP_CD_FN", "SHRS_OWND_FOLWNG_TRANS", "SHRS_OWND_FOLWNG_TRANS_FN",
            "VALU_OWND_FOLWNG_TRANS", "VALU_OWND_FOLWNG_TRANS_FN", "DIRECT_INDIRECT_OWNERSHIP",
            "DIRECT_INDIRECT_OWNERSHIP_FN", "NATURE_OF_OWNERSHIP", "NATURE_OF_OWNERSHIP_FN",
        ]
        transactions = pd.DataFrame(
            [
                {"ACCESSION_NUMBER": "good-1", "NONDERIV_TRANS_SK": "1", "SECURITY_TITLE": "Class A Common Stock", "TRANS_DATE": "03-JAN-2025", "TRANS_FORM_TYPE": "4", "TRANS_CODE": "P", "TRANS_SHARES": "1000", "TRANS_PRICEPERSHARE": "20", "TRANS_ACQUIRED_DISP_CD": "A", "DIRECT_INDIRECT_OWNERSHIP": "D"},
                {"ACCESSION_NUMBER": "good-1", "NONDERIV_TRANS_SK": "2", "SECURITY_TITLE": "Preferred Stock", "TRANS_DATE": "03-JAN-2025", "TRANS_FORM_TYPE": "4", "TRANS_CODE": "P", "TRANS_SHARES": "1000", "TRANS_PRICEPERSHARE": "20", "TRANS_ACQUIRED_DISP_CD": "A", "DIRECT_INDIRECT_OWNERSHIP": "D"},
                {"ACCESSION_NUMBER": "amended-1", "NONDERIV_TRANS_SK": "3", "SECURITY_TITLE": "Common Stock", "TRANS_DATE": "03-JAN-2025", "TRANS_FORM_TYPE": "4", "TRANS_CODE": "P", "TRANS_SHARES": "1000", "TRANS_PRICEPERSHARE": "20", "TRANS_ACQUIRED_DISP_CD": "A", "DIRECT_INDIRECT_OWNERSHIP": "D"},
                {"ACCESSION_NUMBER": "late-1", "NONDERIV_TRANS_SK": "4", "SECURITY_TITLE": "Common Stock", "TRANS_DATE": "03-JAN-2025", "TRANS_FORM_TYPE": "4", "TRANS_CODE": "P", "TRANS_SHARES": "1000", "TRANS_PRICEPERSHARE": "20", "TRANS_ACQUIRED_DISP_CD": "A", "DIRECT_INDIRECT_OWNERSHIP": "D"},
            ],
            columns=transaction_columns,
        ).fillna("")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("SUBMISSION.tsv", submissions.to_csv(sep="\t", index=False))
            archive.writestr("REPORTINGOWNER.tsv", owners.to_csv(sep="\t", index=False))
            archive.writestr("NONDERIV_TRANS.tsv", transactions.to_csv(sep="\t", index=False))
        return buffer.getvalue()

    @staticmethod
    def _price_frame(start: str = "2013-01-02", periods: int = 3400) -> pd.DataFrame:
        index = pd.bdate_range(start, periods=periods)
        close = np.linspace(90.0, 150.0, periods)
        return pd.DataFrame({"close": close}, index=index)

    def test_official_archive_parser_excludes_amendments_late_rows_and_noncommon_security(self):
        frame, meta = parse_quarter_archive(self._zip_payload(), archive_label="fixture.zip")
        self.assertEqual(len(frame), 1)
        row = frame.iloc[0]
        self.assertEqual(row["accession_number"], "good-1")
        self.assertEqual(row["owner_ciks"], ("101",))
        self.assertEqual(row["qualified_transaction_rows"], 1)
        self.assertEqual(row["qualified_value_usd"], 20_000.0)
        self.assertEqual(meta["qualified_accession_rows"], 1)
        self.assertEqual(len(meta["sha256"]), 64)

    def test_first_download_is_reopened_from_persisted_bytes_before_parsing(self):
        downloaded = self._zip_payload()
        persisted_suffix = b"persisted-representation"
        parsed_payloads = []
        original_write_bytes = Path.write_bytes

        def write_transformed(path, payload):
            return original_write_bytes(path, payload + persisted_suffix)

        def parse_persisted(payload, *, archive_label):
            parsed_payloads.append(payload)
            frame = pd.DataFrame(
                [
                    {
                        "accession_number": archive_label,
                        "issuer_cik": "1",
                        "symbol": "AAPL",
                        "filing_date": pd.Timestamp("2025-01-06"),
                        "owner_ciks": ("101",),
                        "qualified_value_usd": 20_000.0,
                    }
                ]
            )
            return frame, {
                "archive_label": archive_label,
                "sha256": "a" * 64,
                "zip_bytes": len(payload),
                "submission_rows": 1,
                "qualified_accession_rows": 1,
            }

        response = Mock(status_code=200, content=downloaded)
        session = Mock()
        session.get.return_value = response
        session.headers = {}
        with tempfile.TemporaryDirectory() as tmp, patch(
            "scripts.sec_form4_clustered_buying_train_lab.requests.Session", return_value=session
        ), patch.object(Path, "write_bytes", write_transformed), patch(
            "scripts.sec_form4_clustered_buying_train_lab.parse_quarter_archive",
            side_effect=parse_persisted,
        ):
            frame, provenance = download_archives(
                Path(tmp), start_year=2025, end_year=2025, user_agent="fixture"
            )

        self.assertEqual(len(frame), 4)
        self.assertEqual(len(provenance), 4)
        self.assertEqual(len(parsed_payloads), 4)
        self.assertTrue(all(payload.endswith(persisted_suffix) for payload in parsed_payloads))

    def test_cluster_requires_two_accessions_and_two_distinct_owners_then_suppresses_overlap(self):
        filings = pd.DataFrame(
            [
                {"accession_number": "a", "issuer_cik": "1", "symbol": "AAPL", "filing_date": pd.Timestamp("2024-01-02"), "owner_ciks": ("10",), "qualified_value_usd": 60_000.0},
                {"accession_number": "b", "issuer_cik": "1", "symbol": "AAPL", "filing_date": pd.Timestamp("2024-01-05"), "owner_ciks": ("11",), "qualified_value_usd": 50_000.0},
                {"accession_number": "c", "issuer_cik": "1", "symbol": "AAPL", "filing_date": pd.Timestamp("2024-01-10"), "owner_ciks": ("12",), "qualified_value_usd": 200_000.0},
                {"accession_number": "d", "issuer_cik": "1", "symbol": "AAPL", "filing_date": pd.Timestamp("2024-02-10"), "owner_ciks": ("13",), "qualified_value_usd": 70_000.0},
                {"accession_number": "e", "issuer_cik": "1", "symbol": "AAPL", "filing_date": pd.Timestamp("2024-02-12"), "owner_ciks": ("14",), "qualified_value_usd": 40_000.0},
            ]
        )
        signals = build_cluster_signals(filings)
        self.assertEqual([str(row["signal_date"].date()) for row in signals], ["2024-01-05", "2024-02-12"])
        self.assertEqual(signals[0]["n_accessions"], 2)
        self.assertEqual(signals[0]["n_distinct_owners"], 2)
        self.assertEqual(signals[0]["aggregate_value_usd"], 110_000.0)

    def test_price_blueprint_uses_only_pre_filing_feature_and_next_session_entry(self):
        frames = {"SPY": self._price_frame(), "AAPL": self._price_frame()}
        signal = {
            "symbol": "AAPL", "issuer_cik": "1", "signal_date": pd.Timestamp("2024-01-06"),
            "window_start": pd.Timestamp("2023-12-17"), "accession_numbers": ("a", "b"),
            "owner_ciks": ("10", "11"), "n_accessions": 2, "n_distinct_owners": 2,
            "aggregate_value_usd": 150_000.0,
        }
        blueprints, rejects = freeze_price_blueprints([signal], frames)
        self.assertFalse(rejects)
        row = blueprints[0]
        self.assertLess(row["feature_date"], row["signal_date"])
        self.assertGreater(row["entry_date"], row["signal_date"])
        self.assertEqual(row["exit_pos"], row["entry_pos"] + 10)

    def test_complete_aligned_train_panel_passes_frozen_discovery_gate(self):
        symbols = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL"]
        frames = {"SPY": self._price_frame()}
        for symbol in symbols:
            frame = self._price_frame()
            frame["close"] = 100.0
            frames[symbol] = frame
        dates = frames["AAPL"].index
        rows = []
        for index in range(24):
            symbol = symbols[index % len(symbols)]
            year_offset = index // 4
            event_target = pd.Timestamp(f"{2017 + year_offset}-10-02")
            signal_pos = int(np.searchsorted(dates.values, np.datetime64(event_target)))
            signal_date = pd.Timestamp(dates[signal_pos])
            entry_pos = signal_pos + 1
            exit_pos = entry_pos + 10
            control_pos = signal_pos - 70 - (index % 4) * 12
            control_entry = control_pos + 1
            control_exit = control_entry + 10
            frames[symbol].iloc[exit_pos, frames[symbol].columns.get_loc("close")] = 103.0
            rows.append(
                {
                    "symbol": symbol,
                    "signal_date": signal_date,
                    "feature_date": pd.Timestamp(dates[signal_pos - 1]),
                    "entry_date": pd.Timestamp(dates[entry_pos]),
                    "exit_date": pd.Timestamp(dates[exit_pos]),
                    "accession_numbers": (f"{index}-a", f"{index}-b"),
                    "n_accessions": 2,
                    "n_distinct_owners": 2,
                    "aggregate_value_usd": 150_000.0,
                    "control_feature_date": pd.Timestamp(dates[control_pos]),
                    "control_entry_date": pd.Timestamp(dates[control_entry]),
                    "control_exit_date": pd.Timestamp(dates[control_exit]),
                    "ret20_match_gap": 0.0,
                    "control_distance_sessions": signal_pos - control_pos,
                }
            )
        result = evaluate_train(rows, frames, n_train_eligible=24, bootstrap_samples=500)
        self.assertTrue(result["gate_pass"], result["gate_checks"])
        self.assertEqual(len(result["symbols"]), 6)
        self.assertEqual(len(result["signal_years"]), 6)
        self.assertGreater(result["event_mean_return_after_10bps"], 0.0025)
        self.assertGreater(result["paired_excess_block_bootstrap_lb90"], 0.0)

    def test_positive_point_estimate_with_nonpositive_uncertainty_fails_closed(self):
        symbols = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL"]
        frames = {"SPY": self._price_frame()}
        for symbol in symbols:
            frame = self._price_frame()
            frame["close"] = 100.0
            frames[symbol] = frame
        dates = frames["AAPL"].index
        rows = []
        event_returns = [0.20] * 8 + [-0.05] * 16
        for index, event_return in enumerate(event_returns):
            symbol = symbols[index % len(symbols)]
            signal_pos = 900 + index * 80
            entry_pos = signal_pos + 1
            exit_pos = entry_pos + 10
            control_pos = signal_pos - 50
            control_entry = control_pos + 1
            control_exit = control_entry + 10
            frames[symbol].iloc[exit_pos, frames[symbol].columns.get_loc("close")] = 100.0 * (1.0 + event_return)
            rows.append(
                {
                    "symbol": symbol,
                    "signal_date": pd.Timestamp(dates[signal_pos]),
                    "feature_date": pd.Timestamp(dates[signal_pos - 1]),
                    "entry_date": pd.Timestamp(dates[entry_pos]),
                    "exit_date": pd.Timestamp(dates[exit_pos]),
                    "accession_numbers": (f"{index}-a", f"{index}-b"),
                    "n_accessions": 2,
                    "n_distinct_owners": 2,
                    "aggregate_value_usd": 150_000.0,
                    "control_feature_date": pd.Timestamp(dates[control_pos]),
                    "control_entry_date": pd.Timestamp(dates[control_entry]),
                    "control_exit_date": pd.Timestamp(dates[control_exit]),
                    "ret20_match_gap": 0.0,
                    "control_distance_sessions": 50,
                }
            )
        result = evaluate_train(
            rows,
            frames,
            n_train_eligible=24,
            bootstrap_samples=500,
            min_years=1,
        )
        self.assertGreater(result["event_mean_return_after_10bps"], 0.0)
        self.assertFalse(result["gate_pass"])
        self.assertFalse(result["gate_checks"]["paired_excess_block_bootstrap_lb90_positive"])

    def test_worst_decile_is_explicitly_event_return_not_paired_excess(self):
        symbols = ["AAPL", "MSFT"]
        frames = {"SPY": self._price_frame()}
        dates = pd.DatetimeIndex(frames["SPY"].index)

        def date_at(position: int):
            return pd.Timestamp(str(dates[position]))

        rows = []
        for index, (symbol, event_return, control_return) in enumerate(
            [("AAPL", -0.05, 0.04), ("MSFT", 0.02, 0.00)]
        ):
            frame = self._price_frame()
            frame["close"] = 100.0
            signal_pos = 1000 + index * 200
            entry_pos = signal_pos + 1
            exit_pos = entry_pos + 10
            control_pos = signal_pos - 50
            control_entry = control_pos + 1
            control_exit = control_entry + 10
            frame.iloc[exit_pos, frame.columns.get_loc("close")] = 100.0 * (1.0 + event_return)
            frame.iloc[control_exit, frame.columns.get_loc("close")] = 100.0 * (1.0 + control_return)
            frames[symbol] = frame
            rows.append(
                {
                    "symbol": symbol,
                    "signal_date": date_at(signal_pos),
                    "feature_date": date_at(signal_pos - 1),
                    "entry_date": date_at(entry_pos),
                    "exit_date": date_at(exit_pos),
                    "accession_numbers": (f"{index}-a", f"{index}-b"),
                    "n_accessions": 2,
                    "n_distinct_owners": 2,
                    "aggregate_value_usd": 150_000.0,
                    "control_feature_date": date_at(control_pos),
                    "control_entry_date": date_at(control_entry),
                    "control_exit_date": date_at(control_exit),
                    "ret20_match_gap": 0.0,
                    "control_distance_sessions": 50,
                }
            )
        result = evaluate_train(
            rows,
            frames,
            n_train_eligible=2,
            bootstrap_samples=100,
            min_pairs=1,
            min_years=1,
            min_symbols=1,
        )
        event_tail = min(row["event_return_after_10bps"] for row in result["pairs"])
        paired_tail = min(row["paired_excess"] for row in result["pairs"])
        self.assertAlmostEqual(result["event_return_worst_decile_mean"], event_tail)
        self.assertNotAlmostEqual(result["event_return_worst_decile_mean"], paired_tail)
        self.assertNotIn("worst_decile_mean", result)
        self.assertIn("event_return_worst_decile_at_least_negative_8pct", result["gate_checks"])

    def test_ids_remain_stable(self):
        self.assertEqual(CANDIDATE_ID, "SEC_FORM4_CLUSTERED_INSIDER_BUYING_CALL_21D_V1")
        self.assertEqual(FAMILY_ID, "SEC_FORM4_CLUSTERED_OPEN_MARKET_BUYING_FORWARD_UPDRIFT")


if __name__ == "__main__":
    unittest.main()
