import unittest
from datetime import datetime, timezone
from typing import cast

import pandas as pd

from trader_platform.research.corporate_action_risk import DividendEvent
from trader_platform.research.dividend_event_archive import DividendEventArchive
from trader_platform.research.dividend_event_crosscheck import (
    AppleDividendRelease,
    apple_results_urls_from_sitemap,
    crosscheck_apple_dividends,
    parse_apple_dividend_release,
)


_RELEASE_URL = (
    "https://www.apple.com/newsroom/2025/10/"
    "apple-reports-fourth-quarter-results/"
)


def _release_html(
    *,
    published="2025-10-30Z",
    amount="0.26",
    security="the Company’s common stock",
):
    return f"""
    <html><head>
      <script type="application/ld+json">
        {{"@type":"NewsArticle","datePublished":"{published}"}}
      </script>
    </head><body>
      <div>Apple’s board of directors has declared a cash dividend of
      ${amount} per share of {security}. The dividend is payable on
      November 13, 2025, to shareholders of record as of the close of
      business on November 10, 2025.</div>
    </body></html>
    """


def _archive(events):
    return DividendEventArchive(
        symbol="AAPL",
        observed_at=pd.Timestamp("2026-07-13T04:18:39"),
        coverage_start=min(event.known_at for event in events),
        source="nasdaq_dividend_history",
        events=tuple(events),
        source_rows=len(events),
        retained_rows=len(events),
        truncated_at_missing_known_at=False,
    )


class DividendEventCrosscheckTest(unittest.TestCase):
    def test_apple_release_parser_requires_explicit_common_stock_identity(self):
        release = parse_apple_dividend_release(_RELEASE_URL, _release_html())

        self.assertEqual(release.published_on, pd.Timestamp("2025-10-30"))
        self.assertEqual(release.amount_per_share, 0.26)
        self.assertEqual(release.record_date, pd.Timestamp("2025-11-10"))
        self.assertEqual(release.payment_date, pd.Timestamp("2025-11-13"))
        self.assertEqual(release.security_identity, "apple_company_common_stock")

        with self.assertRaisesRegex(ValueError, "common stock"):
            parse_apple_dividend_release(
                _RELEASE_URL,
                _release_html(security="an unspecified security"),
            )

    def test_parser_accepts_issuer_wording_used_for_annual_dividend_increases(self):
        page = _release_html().replace(
            "common stock. The dividend",
            "common stock, an increase of 4 percent. The dividend",
        )

        release = parse_apple_dividend_release(_RELEASE_URL, page)

        self.assertEqual(release.amount_per_share, 0.26)
        self.assertEqual(release.security_identity, "apple_company_common_stock")

    def test_parser_accepts_legacy_issuer_common_stock_wording(self):
        page = (
            _release_html(amount=".73")
            .replace(
                "Apple’s board of directors has declared a cash dividend",
                "Reflecting the approved increase, the Board has declared a cash dividend",
            )
            .replace(
                "the Company’s common stock. The dividend is payable",
                "Apple’s common stock payable",
            )
        )

        release = parse_apple_dividend_release(_RELEASE_URL, page)

        self.assertEqual(release.amount_per_share, 0.73)
        self.assertEqual(release.security_identity, "apple_company_common_stock")

    def test_sitemap_keeps_only_canonical_apple_results_releases(self):
        sitemap = """<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://www.apple.com/newsroom/2025/10/apple-reports-fourth-quarter-results/</loc></url>
          <url><loc>https://www.apple.com/newsroom/2025/10/apple-introduces-widget/</loc></url>
          <url><loc>https://example.com/newsroom/2025/10/apple-reports-fourth-quarter-results/</loc></url>
        </urlset>"""

        self.assertEqual(apple_results_urls_from_sitemap(sitemap), [_RELEASE_URL])

    def test_complete_bounded_match_qualifies_only_issuer_observed_fields(self):
        archive = _archive(
            [
                DividendEvent(
                    "AAPL", pd.Timestamp("2025-02-10"), 0.25, pd.Timestamp("2025-01-30")
                ),
                DividendEvent(
                    "AAPL", pd.Timestamp("2025-11-10"), 0.26, pd.Timestamp("2025-10-30")
                ),
            ]
        )
        releases = [
            AppleDividendRelease(
                url=_RELEASE_URL,
                published_on=pd.Timestamp("2025-10-30"),
                amount_per_share=0.26,
                record_date=pd.Timestamp("2025-11-10"),
                payment_date=pd.Timestamp("2025-11-13"),
            )
        ]

        result = crosscheck_apple_dividends(archive, releases)

        self.assertEqual(result.provider_status, "partial_issuer_corroboration")
        self.assertEqual(result.archive_events_in_window, 1)
        self.assertEqual(result.matched_events, 1)
        self.assertEqual(result.archive_events_before_window, 1)
        self.assertEqual(
            result.qualified_fields,
            ("known_at", "amount_per_share", "security_identity"),
        )
        self.assertEqual(result.unqualified_fields, ("ex_date",))

    def test_matching_issuer_record_date_does_not_qualify_archive_ex_date(self):
        shared_date = cast(pd.Timestamp, pd.Timestamp("2025-11-10"))
        published_on = cast(pd.Timestamp, pd.Timestamp("2025-10-30"))
        payment_date = cast(pd.Timestamp, pd.Timestamp("2025-11-13"))
        archive = _archive(
            [
                DividendEvent(
                    "AAPL", shared_date, 0.26, published_on
                )
            ]
        )
        releases = [
            AppleDividendRelease(
                url=_RELEASE_URL,
                published_on=published_on,
                amount_per_share=0.26,
                record_date=shared_date,
                payment_date=payment_date,
            )
        ]

        result = crosscheck_apple_dividends(archive, releases)

        self.assertEqual(result.provider_status, "partial_issuer_corroboration")
        self.assertEqual(
            result.qualified_fields,
            ("known_at", "amount_per_share", "security_identity"),
        )
        self.assertEqual(result.unqualified_fields, ("ex_date",))

    def test_amount_conflict_fails_closed_without_partial_match_credit(self):
        archive = _archive(
            [
                DividendEvent(
                    "AAPL", pd.Timestamp("2025-11-10"), 0.25, pd.Timestamp("2025-10-30")
                )
            ]
        )
        releases = [
            AppleDividendRelease(
                url=_RELEASE_URL,
                published_on=pd.Timestamp("2025-10-30"),
                amount_per_share=0.26,
                record_date=pd.Timestamp("2025-11-10"),
                payment_date=pd.Timestamp("2025-11-13"),
            )
        ]

        result = crosscheck_apple_dividends(archive, releases)

        self.assertEqual(result.provider_status, "single_source_conflict")
        self.assertEqual(result.matched_events, 0)
        self.assertEqual(result.qualified_fields, ())
        self.assertEqual(len(result.conflicts), 1)
        self.assertEqual(result.conflicts[0]["reason"], "amount_mismatch")

    def test_missing_bounded_issuer_release_fails_closed(self):
        archive = _archive(
            [
                DividendEvent(
                    "AAPL", pd.Timestamp("2025-08-11"), 0.26, pd.Timestamp("2025-07-31")
                ),
                DividendEvent(
                    "AAPL", pd.Timestamp("2025-11-10"), 0.26, pd.Timestamp("2025-10-30")
                ),
            ]
        )
        releases = [
            AppleDividendRelease(
                url=_RELEASE_URL,
                published_on=pd.Timestamp("2025-10-30"),
                amount_per_share=0.26,
                record_date=pd.Timestamp("2025-11-10"),
                payment_date=pd.Timestamp("2025-11-13"),
            )
        ]

        result = crosscheck_apple_dividends(
            archive,
            releases,
            coverage_start=pd.Timestamp("2025-07-01"),
        )

        self.assertEqual(result.provider_status, "single_source_conflict")
        self.assertEqual(result.unmatched_archive_dates, ("2025-07-31",))

    def test_duplicate_issuer_publication_date_is_rejected(self):
        archive = _archive(
            [
                DividendEvent(
                    "AAPL", pd.Timestamp("2025-11-10"), 0.26, pd.Timestamp("2025-10-30")
                )
            ]
        )
        release = AppleDividendRelease(
            url=_RELEASE_URL,
            published_on=pd.Timestamp("2025-10-30"),
            amount_per_share=0.26,
            record_date=pd.Timestamp("2025-11-10"),
            payment_date=pd.Timestamp("2025-11-13"),
        )

        with self.assertRaisesRegex(ValueError, "duplicate issuer publication"):
            crosscheck_apple_dividends(archive, [release, release])

    def test_crosscheck_rejects_invalid_issuer_chronology(self):
        published_on = cast(pd.Timestamp, pd.Timestamp("2025-10-30"))
        archive = _archive(
            [
                DividendEvent(
                    "AAPL",
                    cast(pd.Timestamp, pd.Timestamp("2025-11-10")),
                    0.26,
                    published_on,
                )
            ]
        )
        release = AppleDividendRelease(
            url=_RELEASE_URL,
            published_on=published_on,
            amount_per_share=0.26,
            record_date=cast(pd.Timestamp, pd.Timestamp("2025-10-29")),
            payment_date=cast(pd.Timestamp, pd.Timestamp("2025-11-13")),
        )

        with self.assertRaisesRegex(ValueError, "chronologically valid"):
            crosscheck_apple_dividends(archive, [release])

    def test_crosscheck_rejects_forged_issuer_identity_metadata(self):
        archive = _archive(
            [
                DividendEvent(
                    "AAPL", pd.Timestamp("2025-11-10"), 0.26, pd.Timestamp("2025-10-30")
                )
            ]
        )
        forged = AppleDividendRelease(
            url="https://example.com/newsroom/2025/10/apple-reports-fourth-quarter-results/",
            published_on=pd.Timestamp("2025-10-30"),
            amount_per_share=0.26,
            record_date=pd.Timestamp("2025-11-10"),
            payment_date=pd.Timestamp("2025-11-13"),
        )

        with self.assertRaisesRegex(ValueError, "canonical issuer"):
            crosscheck_apple_dividends(archive, [forged])


if __name__ == "__main__":
    unittest.main()
