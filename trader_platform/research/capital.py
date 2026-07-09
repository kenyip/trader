"""Capital-by-price sizing proxies for multi-symbol research.

Honest proxies — not broker margin formulas or live chain quotes.
Used to rank pilot fit at $3k / $5k / $15k sleeves and filter top-N.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import floor
from typing import Any, Optional, Sequence

# Pilot / lab funding sleeves (Stage2 capital plan alignment)
SLEEVE_3K = 3_000.0
SLEEVE_5K = 5_000.0
SLEEVE_15K = 15_000.0
DEFAULT_SLEEVES = (SLEEVE_3K, SLEEVE_5K, SLEEVE_15K)

# Slightly OTM CSP collateral ≈ 95% of spot * 100 (research proxy)
OTM_CSP_FACTOR = 0.95
# Typical OTM long option debit ≈ 2% of spot per share * 100
LONG_DEBIT_PCT = 0.02


@dataclass
class CapitalMetrics:
    """Per-symbol capital requirements and affordability at pilot sleeves."""

    spot: float
    share_lot_usd: float  # 100 * spot
    short_premium_bp_proxy: float  # cash-secured short put / covered-call rough BP
    long_debit_proxy: float  # long option debit proxy (1 contract)
    contracts_at_3k_short: int
    contracts_at_5k_short: int
    contracts_at_15k_short: int
    contracts_at_3k_long: int
    contracts_at_5k_long: int
    contracts_at_15k_long: int
    capital_fit: str  # fit_3k | fit_5k | fit_15k | oversized | unknown
    capital_fit_long: str  # same tiers for long-debit path
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def fits_sleeve(self, sleeve_usd: float, *, mode: str = "either") -> bool:
        """True if ≥1 contract affordable at sleeve_usd.

        mode: 'short' | 'long' | 'either' (default — pilot can use long debit on rich names)
        """
        if sleeve_usd <= 0:
            return False
        short_ok = self.short_premium_bp_proxy > 0 and sleeve_usd >= self.short_premium_bp_proxy
        long_ok = self.long_debit_proxy > 0 and sleeve_usd >= self.long_debit_proxy
        if mode == "short":
            return short_ok
        if mode == "long":
            return long_ok
        return short_ok or long_ok


def _contracts(budget: float, cost: float) -> int:
    if cost <= 0 or budget <= 0:
        return 0
    return max(0, int(floor(budget / cost)))


def _fit_tier(c3: int, c5: int, c15: int) -> str:
    if c3 >= 1:
        return "fit_3k"
    if c5 >= 1:
        return "fit_5k"
    if c15 >= 1:
        return "fit_15k"
    return "oversized"


def compute_capital(
    spot: float,
    *,
    atr_14: float = 0.0,
    otm_factor: float = OTM_CSP_FACTOR,
    long_debit_pct: float = LONG_DEBIT_PCT,
) -> CapitalMetrics:
    """Derive capital columns from spot (and optional ATR for long debit floor)."""
    s = float(spot or 0.0)
    if s <= 0:
        return CapitalMetrics(
            spot=0.0,
            share_lot_usd=0.0,
            short_premium_bp_proxy=0.0,
            long_debit_proxy=0.0,
            contracts_at_3k_short=0,
            contracts_at_5k_short=0,
            contracts_at_15k_short=0,
            contracts_at_3k_long=0,
            contracts_at_5k_long=0,
            contracts_at_15k_long=0,
            capital_fit="unknown",
            capital_fit_long="unknown",
            notes="no_spot",
        )

    share_lot = s * 100.0
    # Cash-secured put / covered call: full share lot * OTM factor
    short_bp = share_lot * float(otm_factor)
    # Long debit: pct of spot * 100, floored by half-ATR * 100 when ATR known
    long_from_pct = s * long_debit_pct * 100.0
    long_from_atr = max(float(atr_14 or 0.0), 0.0) * 0.5 * 100.0
    long_debit = max(long_from_pct, long_from_atr, 25.0)  # $25 floor per contract

    c3s = _contracts(SLEEVE_3K, short_bp)
    c5s = _contracts(SLEEVE_5K, short_bp)
    c15s = _contracts(SLEEVE_15K, short_bp)
    c3l = _contracts(SLEEVE_3K, long_debit)
    c5l = _contracts(SLEEVE_5K, long_debit)
    c15l = _contracts(SLEEVE_15K, long_debit)

    notes_parts: list[str] = []
    if short_bp > SLEEVE_15K:
        notes_parts.append("csp_above_15k")
    if c3s == 0 and c3l >= 1:
        notes_parts.append("long_debit_fits_3k_csp_does_not")

    return CapitalMetrics(
        spot=round(s, 4),
        share_lot_usd=round(share_lot, 2),
        short_premium_bp_proxy=round(short_bp, 2),
        long_debit_proxy=round(long_debit, 2),
        contracts_at_3k_short=c3s,
        contracts_at_5k_short=c5s,
        contracts_at_15k_short=c15s,
        contracts_at_3k_long=c3l,
        contracts_at_5k_long=c5l,
        contracts_at_15k_long=c15l,
        capital_fit=_fit_tier(c3s, c5s, c15s),
        capital_fit_long=_fit_tier(c3l, c5l, c15l),
        notes=",".join(notes_parts),
    )


def attach_capital_to_score(score: Any) -> Any:
    """Mutate/enrich a SymbolScore-like object with capital fields. Returns score."""
    cap = compute_capital(
        float(getattr(score, "spot", 0) or 0),
        atr_14=float(getattr(score, "atr_14", 0) or 0),
    )
    # Attach both nested metrics and flat fields for store/table
    score.capital = cap  # type: ignore[attr-defined]
    score.share_lot_usd = cap.share_lot_usd  # type: ignore[attr-defined]
    score.short_premium_bp_proxy = cap.short_premium_bp_proxy  # type: ignore[attr-defined]
    score.long_debit_proxy = cap.long_debit_proxy  # type: ignore[attr-defined]
    score.contracts_at_3k_short = cap.contracts_at_3k_short  # type: ignore[attr-defined]
    score.contracts_at_5k_short = cap.contracts_at_5k_short  # type: ignore[attr-defined]
    score.contracts_at_15k_short = cap.contracts_at_15k_short  # type: ignore[attr-defined]
    score.contracts_at_3k_long = cap.contracts_at_3k_long  # type: ignore[attr-defined]
    score.contracts_at_5k_long = cap.contracts_at_5k_long  # type: ignore[attr-defined]
    score.contracts_at_15k_long = cap.contracts_at_15k_long  # type: ignore[attr-defined]
    score.capital_fit = cap.capital_fit  # type: ignore[attr-defined]
    score.capital_fit_long = cap.capital_fit_long  # type: ignore[attr-defined]
    return score


def filter_by_sleeve(
    scores: Sequence[Any],
    sleeve_usd: float,
    *,
    mode: str = "either",
) -> list[Any]:
    """Keep scores that fit the pilot sleeve (capital-aware pilot filter)."""
    out: list[Any] = []
    for s in scores:
        if getattr(s, "error", None):
            continue
        if getattr(s, "capital", None) is None:
            attach_capital_to_score(s)
        cap = getattr(s, "capital", None)
        if cap is not None and cap.fits_sleeve(sleeve_usd, mode=mode):
            out.append(s)
    return out


def format_capital_table(scores: Sequence[Any], *, top_n: int = 15) -> str:
    """CLI table: capital columns for ranked symbols."""
    rows: list[Any] = []
    for s in scores:
        if getattr(s, "error", None):
            continue
        if getattr(s, "capital", None) is None and hasattr(s, "spot"):
            attach_capital_to_score(s)
        rows.append(s)
    rows = sorted(rows, key=lambda r: float(getattr(r, "composite", 0) or 0), reverse=True)[:top_n]

    header = (
        f"{'Rk':>3}  {'Sym':<6}  {'Spot':>8}  {'100*S':>9}  {'CSP_BP':>9}  "
        f"{'LongDeb':>8}  {'@3kS':>4}  {'@5kS':>4}  {'@15kS':>5}  "
        f"{'@3kL':>4}  {'FitS':<10}  {'FitL':<10}"
    )
    lines = [header, "-" * len(header)]
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"{i:>3}  {str(getattr(r, 'symbol', '')):<6}  "
            f"{float(getattr(r, 'spot', 0) or 0):8.2f}  "
            f"{float(getattr(r, 'share_lot_usd', 0) or 0):9.0f}  "
            f"{float(getattr(r, 'short_premium_bp_proxy', 0) or 0):9.0f}  "
            f"{float(getattr(r, 'long_debit_proxy', 0) or 0):8.0f}  "
            f"{int(getattr(r, 'contracts_at_3k_short', 0) or 0):4d}  "
            f"{int(getattr(r, 'contracts_at_5k_short', 0) or 0):4d}  "
            f"{int(getattr(r, 'contracts_at_15k_short', 0) or 0):5d}  "
            f"{int(getattr(r, 'contracts_at_3k_long', 0) or 0):4d}  "
            f"{str(getattr(r, 'capital_fit', '') or ''):<10}  "
            f"{str(getattr(r, 'capital_fit_long', '') or ''):<10}"
        )
    return "\n".join(lines)
