"""Multi-symbol research scout: rank trade symbols by vol / premium / alpha + capital fit.

Research universe is deliberately broader than live risk_limits.instrument_allowlist.
Paper-only — never places live orders.

See docs/RESEARCH_LOOP.md and docs/RESEARCH_CRON.md.
"""

from trader_platform.research.universe import load_universe, default_universe_path
from trader_platform.research.scorer import score_symbol, SymbolScore
from trader_platform.research.loop import run_research_tick, ResearchReport
from trader_platform.research.capital import compute_capital, CapitalMetrics
from trader_platform.research.promote import promote_top_n, PromoteReport

__all__ = [
    "load_universe",
    "default_universe_path",
    "score_symbol",
    "SymbolScore",
    "run_research_tick",
    "ResearchReport",
    "compute_capital",
    "CapitalMetrics",
    "promote_top_n",
    "PromoteReport",
]
