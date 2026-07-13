"""Independent issuer-release cross-checks for archived dividend events."""

from __future__ import annotations

from dataclasses import dataclass
import html as html_module
from html.parser import HTMLParser
import json
import math
import re
from typing import Any, Callable, Iterable, Optional, Sequence, cast
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import pandas as pd

from trader_platform.research.dividend_event_archive import DividendEventArchive


_APPLE_HOST = "www.apple.com"
_APPLE_SITEMAP = "https://www.apple.com/newsroom/sitemap.xml"
_APPLE_RESULTS_PATH = re.compile(
    r"^/newsroom/\d{4}/\d{2}/apple-reports-[a-z0-9-]*results/$"
)
_DIVIDEND_SENTENCE = re.compile(
    r"has declared a (?:cash )?dividend of "
    r"\$([0-9]*\.[0-9]+|[0-9]+) per share of "
    r"(?:the Company|Apple)['’]s common stock"
    r"(?:, an increase of [0-9]+(?:\.[0-9]+)? percent)?"
    r"(?:\. The dividend is|,)? payable on "
    r"([A-Z][a-z]+ \d{1,2}, \d{4}),? to shareholders of record as of the "
    r"close of business on ([A-Z][a-z]+ \d{1,2}, \d{4})\.",
    flags=re.IGNORECASE,
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


@dataclass(frozen=True)
class AppleDividendRelease:
    url: str
    published_on: pd.Timestamp
    amount_per_share: float
    record_date: pd.Timestamp
    payment_date: pd.Timestamp
    security_identity: str = "apple_company_common_stock"

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "published_on": self.published_on.isoformat(),
            "amount_per_share": self.amount_per_share,
            "record_date": self.record_date.isoformat(),
            "payment_date": self.payment_date.isoformat(),
            "security_identity": self.security_identity,
        }


@dataclass(frozen=True)
class DividendEventCrosscheck:
    symbol: str
    archive_source: str
    issuer_source: str
    coverage_start: pd.Timestamp
    coverage_end: pd.Timestamp
    archive_events_before_window: int
    archive_events_after_window: int
    archive_events_in_window: int
    issuer_releases_in_window: int
    matched_events: int
    unmatched_archive_dates: tuple[str, ...]
    unmatched_issuer_dates: tuple[str, ...]
    conflicts: tuple[dict[str, Any], ...]
    provider_status: str
    qualified_fields: tuple[str, ...]
    unqualified_fields: tuple[str, ...]
    releases: tuple[AppleDividendRelease, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "symbol": self.symbol,
            "archive_source": self.archive_source,
            "issuer_source": self.issuer_source,
            "coverage_start": self.coverage_start.isoformat(),
            "coverage_end": self.coverage_end.isoformat(),
            "archive_events_before_window": self.archive_events_before_window,
            "archive_events_after_window": self.archive_events_after_window,
            "archive_events_in_window": self.archive_events_in_window,
            "issuer_releases_in_window": self.issuer_releases_in_window,
            "matched_events": self.matched_events,
            "unmatched_archive_dates": list(self.unmatched_archive_dates),
            "unmatched_issuer_dates": list(self.unmatched_issuer_dates),
            "conflicts": list(self.conflicts),
            "provider_status": self.provider_status,
            "qualified_fields": list(self.qualified_fields),
            "unqualified_fields": list(self.unqualified_fields),
            "releases": [release.to_dict() for release in self.releases],
            "claim_limit": (
                "bounded issuer concordance only; ex_date and out-of-window events "
                "remain single-source; not calibrated assignment or strategy-edge evidence"
            ),
        }


def _timestamp(value: Any) -> pd.Timestamp:
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}Z", value):
        value = value[:-1]
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        raise ValueError("timestamp cannot be missing")
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return cast(pd.Timestamp, ts).normalize()


def _canonical_apple_results_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.netloc == _APPLE_HOST
        and bool(_APPLE_RESULTS_PATH.fullmatch(parsed.path))
        and not parsed.query
        and not parsed.fragment
    )


def _published_date(page_html: str) -> pd.Timestamp:
    scripts = re.findall(
        r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for script in scripts:
        try:
            payload = json.loads(html_module.unescape(script))
        except json.JSONDecodeError:
            continue
        candidates: Iterable[Any] = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if candidate.get("@type") not in {"NewsArticle", "Article"}:
                continue
            value = candidate.get("datePublished")
            if value:
                return _timestamp(value)
    raise ValueError("Apple release lacks a valid NewsArticle datePublished")


def parse_apple_dividend_release(url: str, page_html: str) -> AppleDividendRelease:
    """Parse one canonical Apple results release with explicit common-stock wording."""
    if not _canonical_apple_results_url(url):
        raise ValueError("non-canonical Apple results release URL")
    parser = _TextExtractor()
    parser.feed(page_html)
    match = _DIVIDEND_SENTENCE.search(parser.text())
    if match is None:
        raise ValueError("Apple release lacks an explicit common stock dividend declaration")
    amount = float(match.group(1))
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("Apple release dividend amount is invalid")
    return AppleDividendRelease(
        url=url,
        published_on=_published_date(page_html),
        amount_per_share=amount,
        payment_date=_timestamp(match.group(2)),
        record_date=_timestamp(match.group(3)),
    )


def apple_results_urls_from_sitemap(sitemap_xml: str | bytes) -> list[str]:
    """Return canonical Apple financial-results release URLs from one sitemap."""
    try:
        root = ElementTree.fromstring(sitemap_xml)
    except ElementTree.ParseError as exc:
        raise ValueError("invalid Apple Newsroom sitemap") from exc
    urls = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "loc" or not element.text:
            continue
        url = element.text.strip()
        if _canonical_apple_results_url(url):
            urls.append(url)
    if len(urls) != len(set(urls)):
        raise ValueError("Apple Newsroom sitemap contains duplicate results URLs")
    return urls


def _fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "TraderResearch/1.0"})
    with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed HTTPS hosts
        return response.read().decode("utf-8")


def snapshot_apple_dividend_releases(
    *, fetch_text: Callable[[str], str] = _fetch_text
) -> tuple[AppleDividendRelease, ...]:
    sitemap = fetch_text(_APPLE_SITEMAP)
    urls = apple_results_urls_from_sitemap(sitemap)
    if not urls:
        raise ValueError("Apple Newsroom sitemap has no financial-results releases")
    releases = [parse_apple_dividend_release(url, fetch_text(url)) for url in urls]
    return tuple(sorted(releases, key=lambda release: release.published_on))


def crosscheck_apple_dividends(
    archive: DividendEventArchive,
    releases: Sequence[AppleDividendRelease],
    *,
    coverage_start: Optional[pd.Timestamp] = None,
) -> DividendEventCrosscheck:
    """Fail closed unless every archive and issuer event agrees in a bounded window."""
    if archive.symbol != "AAPL" or archive.source != "nasdaq_dividend_history":
        raise ValueError("Apple cross-check requires the normalized AAPL Nasdaq archive")
    if not releases:
        raise ValueError("Apple cross-check requires at least one issuer release")
    for release in releases:
        if not _canonical_apple_results_url(release.url):
            raise ValueError("release URL is not a canonical issuer results release")
        if release.security_identity != "apple_company_common_stock":
            raise ValueError("release lacks canonical issuer security identity")
        if not math.isfinite(release.amount_per_share) or release.amount_per_share <= 0:
            raise ValueError("issuer dividend amount must be positive and finite")
        if not release.published_on <= release.record_date <= release.payment_date:
            raise ValueError("issuer dividend dates are not chronologically valid")
    ordered = tuple(sorted(releases, key=lambda release: release.published_on))
    published_dates = [release.published_on for release in ordered]
    if len(published_dates) != len(set(published_dates)):
        raise ValueError("duplicate issuer publication date")

    start = _timestamp(coverage_start if coverage_start is not None else ordered[0].published_on)
    end = _timestamp(ordered[-1].published_on)
    if start > end:
        raise ValueError("cross-check coverage starts after its final issuer release")
    issuer_in_window = tuple(
        release for release in ordered if start <= release.published_on <= end
    )
    issuer_by_date = {release.published_on: release for release in issuer_in_window}
    archive_in_window = tuple(
        event for event in archive.events if start <= event.known_at <= end
    )

    matched = 0
    conflicts: list[dict[str, Any]] = []
    unmatched_archive: list[str] = []
    archive_dates = set()
    for event in archive_in_window:
        archive_dates.add(event.known_at)
        release = issuer_by_date.get(event.known_at)
        if release is None:
            unmatched_archive.append(event.known_at.date().isoformat())
            continue
        if not math.isclose(
            event.amount_per_share,
            release.amount_per_share,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            conflicts.append(
                {
                    "known_at": event.known_at.date().isoformat(),
                    "reason": "amount_mismatch",
                    "archive_amount_per_share": event.amount_per_share,
                    "issuer_amount_per_share": release.amount_per_share,
                    "issuer_url": release.url,
                }
            )
            continue
        matched += 1

    unmatched_issuer = sorted(
        release.published_on.date().isoformat()
        for release in issuer_in_window
        if release.published_on not in archive_dates
    )
    complete = (
        bool(archive_in_window)
        and matched == len(archive_in_window) == len(issuer_in_window)
        and not conflicts
        and not unmatched_archive
        and not unmatched_issuer
    )
    qualified = (
        ("known_at", "amount_per_share", "security_identity") if complete else ()
    )
    return DividendEventCrosscheck(
        symbol=archive.symbol,
        archive_source=archive.source,
        issuer_source="apple_newsroom_earnings_release",
        coverage_start=start,
        coverage_end=end,
        archive_events_before_window=sum(
            event.known_at < start for event in archive.events
        ),
        archive_events_after_window=sum(event.known_at > end for event in archive.events),
        archive_events_in_window=len(archive_in_window),
        issuer_releases_in_window=len(issuer_in_window),
        matched_events=matched,
        unmatched_archive_dates=tuple(sorted(unmatched_archive)),
        unmatched_issuer_dates=tuple(unmatched_issuer),
        conflicts=tuple(conflicts),
        provider_status=(
            "partial_issuer_corroboration" if complete else "single_source_conflict"
        ),
        qualified_fields=qualified,
        unqualified_fields=("ex_date",),
        releases=issuer_in_window,
    )
