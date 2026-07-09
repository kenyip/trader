"""Optional engine backtest hooks for research-promoted symbols.

Never places orders. When Backtester/strategies are available, runs a short
paper research backtest and returns metrics; otherwise returns a skip reason.

Hooks are best-effort: multi-name research symbols without tuned knobs still
use get_config(ticker) defaults (often StrategyConfig() fallthrough).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence


@dataclass
class BacktestHookResult:
    symbol: str
    ok: bool
    skipped: bool = False
    reason: str = ""
    period: str = ""
    n_trades: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    evidence_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def engine_available() -> tuple[bool, str]:
    """Return (ok, detail) if backtest engine imports cleanly."""
    try:
        from backtest import Backtester, compute_metrics  # noqa: F401
        from data import build  # noqa: F401
        from strategies import get_config, pick_entry, check_exits  # noqa: F401

        return True, "backtest+data+strategies importable"
    except Exception as exc:  # noqa: BLE001
        return False, f"engine unavailable: {exc}"


def run_symbol_backtest(
    symbol: str,
    *,
    period: str = "2y",
    use_cache: bool = True,
    dump_dir: Optional[Path | str] = None,
) -> BacktestHookResult:
    """Run engine backtest for one symbol (research/paper evidence only)."""
    sym = symbol.upper()
    ok, detail = engine_available()
    if not ok:
        return BacktestHookResult(symbol=sym, ok=False, skipped=True, reason=detail, period=period)

    try:
        from data import build
        from backtest import Backtester, compute_metrics, trades_to_dataframe
        from strategies import get_config, pick_entry, check_exits, pick_covered_call, pick_roll

        df = build(sym, period=period, use_cache=use_cache)
        if df is None or len(df) < 50:
            return BacktestHookResult(
                symbol=sym,
                ok=False,
                skipped=True,
                reason="insufficient history",
                period=period,
            )

        cfg = get_config(sym)
        bt = Backtester(
            df=df,
            config=cfg,
            entry_fn=pick_entry,
            exit_fn=check_exits,
            ticker=sym,
            wheel_cc_fn=pick_covered_call if getattr(cfg, "wheel_enabled", False) else None,
            roll_fn=pick_roll if getattr(cfg, "roll_on_max_loss", False) else None,
        )
        trades = bt.run()
        metrics = compute_metrics(trades) if trades is not None else {}
        # normalize metrics to plain dict of scalars when possible
        m: dict[str, Any] = {}
        if isinstance(metrics, dict):
            m = {k: (float(v) if hasattr(v, "real") else v) for k, v in metrics.items()}
        else:
            # dataclass or object
            for k in (
                "total_pnl",
                "n_trades",
                "win_rate",
                "max_drawdown",
                "avg_pnl",
                "profit_factor",
            ):
                if hasattr(metrics, k):
                    val = getattr(metrics, k)
                    try:
                        m[k] = float(val)
                    except (TypeError, ValueError):
                        m[k] = val

        evidence = ""
        if dump_dir and trades:
            out_dir = Path(dump_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{sym}_research_trades.csv"
            try:
                trades_to_dataframe(trades).to_csv(path, index=False)
                evidence = str(path)
            except Exception:  # noqa: BLE001
                evidence = ""

        n = len(trades) if trades is not None else int(m.get("n_trades") or 0)
        return BacktestHookResult(
            symbol=sym,
            ok=True,
            skipped=False,
            reason="ok",
            period=period,
            n_trades=n,
            metrics=m,
            evidence_path=evidence,
        )
    except Exception as exc:  # noqa: BLE001
        return BacktestHookResult(
            symbol=sym,
            ok=False,
            skipped=True,
            reason=f"backtest error: {exc}",
            period=period,
        )


def run_backtest_hooks(
    symbols: Sequence[str],
    *,
    period: str = "2y",
    use_cache: bool = True,
    dump_dir: Optional[Path | str] = None,
    max_symbols: int = 5,
) -> list[BacktestHookResult]:
    """Run hooks for up to max_symbols (keep research ticks bounded)."""
    results: list[BacktestHookResult] = []
    for sym in list(symbols)[:max_symbols]:
        results.append(
            run_symbol_backtest(
                sym,
                period=period,
                use_cache=use_cache,
                dump_dir=dump_dir,
            )
        )
    return results
