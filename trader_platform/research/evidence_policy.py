"""Evidence provenance policy for research-to-readiness promotion."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

OBSERVED_OPTION_MARKS = "observed_historical_option_quotes"
PROXY_OPTION_MARKS = "black_scholes_proxy"


@dataclass(frozen=True)
class L1EvidenceDecision:
    eligible: bool
    option_mark_provenance: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_l1_evidence(
    *,
    option_mark_provenance: str,
    complete_observed_trade_joins: bool = False,
    observed_history_sufficient_for_edge: bool = False,
    observed_market_dates: int = 0,
) -> L1EvidenceDecision:
    """Fail closed unless option P/L is backed by sufficient observed history.

    The three-date forward archive floor is only a capture/join plumbing gate. It
    cannot, by itself, establish a historical edge or make a result L1 eligible.
    """
    provenance = str(option_mark_provenance or "unknown").strip().lower()
    if provenance != OBSERVED_OPTION_MARKS:
        return L1EvidenceDecision(False, provenance, "proxy_or_unknown_option_marks_cannot_earn_l1")
    if int(observed_market_dates) <= 3:
        return L1EvidenceDecision(False, provenance, "three_or_fewer_market_dates_are_plumbing_not_edge_evidence")
    if not complete_observed_trade_joins:
        return L1EvidenceDecision(False, provenance, "observed_entry_exit_leg_coverage_incomplete")
    if not observed_history_sufficient_for_edge:
        return L1EvidenceDecision(False, provenance, "observed_history_not_demonstrated_sufficient_for_edge")
    return L1EvidenceDecision(True, provenance, "observed_option_history_and_trade_coverage_sufficient")
