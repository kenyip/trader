"""Promote research top-N → hypothesis *candidates* (never live).

Paper research path only:
  ranked opportunities → HypothesisRegistry status=candidate
  optional engine backtest hooks → evidence_links

Does NOT touch agentic.enabled, place_*, funding, or live allowlist.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from trader_platform.hypothesis_registry import Hypothesis, HypothesisRegistry
from trader_platform.research.backtest_hooks import BacktestHookResult, run_backtest_hooks
from trader_platform.research.capital import attach_capital_to_score, filter_by_sleeve
from trader_platform.research.scorer import SymbolScore
from trader_platform.research.store import default_db_path, load_opportunities, load_run_scores, latest_run_id


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s.strip().lower()).strip("_")
    return s[:40] or "x"


def research_hypothesis_id(symbol: str, strategy_family: str) -> str:
    return f"hyp_research_{_slug(symbol)}_{_slug(strategy_family or 'unknown')}"


@dataclass
class PromoteItem:
    symbol: str
    rank: int
    composite: float
    strategy_family: str
    capital_fit: str
    hypothesis_id: str
    action: str  # created | exists | skipped
    status: str = "candidate"
    backtest: Optional[dict[str, Any]] = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PromoteReport:
    run_id: Optional[int]
    top_n: int
    sleeve_usd: Optional[float]
    items: list[PromoteItem] = field(default_factory=list)
    registry_path: str = ""
    never_live: bool = True
    backtest_ran: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "top_n": self.top_n,
            "sleeve_usd": self.sleeve_usd,
            "registry_path": self.registry_path,
            "never_live": self.never_live,
            "backtest_ran": self.backtest_ran,
            "n_created": sum(1 for i in self.items if i.action == "created"),
            "n_exists": sum(1 for i in self.items if i.action == "exists"),
            "n_skipped": sum(1 for i in self.items if i.action == "skipped"),
            "items": [i.to_dict() for i in self.items],
        }


def _scores_from_run(
    run_id: Optional[int],
    *,
    db_path: Optional[Path | str] = None,
    top_n: int = 10,
) -> tuple[Optional[int], list[SymbolScore]]:
    db = Path(db_path) if db_path else default_db_path()
    rid = run_id if run_id is not None else latest_run_id(db)
    if rid is None:
        return None, []
    rows = load_run_scores(rid, db)
    # Prefer opportunities rank order when present
    opps = load_opportunities(rid, db)
    order = [o["symbol"] for o in opps] if opps else []
    by_sym = {r["symbol"]: r for r in rows if not r.get("error")}

    ordered_rows: list[dict[str, Any]] = []
    if order:
        for s in order:
            if s in by_sym:
                ordered_rows.append(by_sym[s])
        for s, r in by_sym.items():
            if s not in order:
                ordered_rows.append(r)
    else:
        ordered_rows = sorted(rows, key=lambda r: float(r.get("composite") or 0), reverse=True)

    scores: list[SymbolScore] = []
    for r in ordered_rows[: max(top_n * 3, top_n)]:  # extra for sleeve filter
        if r.get("error"):
            continue
        sc = SymbolScore(
            symbol=str(r["symbol"]),
            asof=str(r.get("asof") or ""),
            spot=float(r.get("spot") or 0),
            regime=str(r.get("regime") or ""),
            vol_score=float(r.get("vol_score") or 0),
            premium_score=float(r.get("premium_score") or 0),
            alpha_score=float(r.get("alpha_score") or 0),
            composite=float(r.get("composite") or 0),
            hv_20=float(r.get("hv_20") or 0),
            hv_60=float(r.get("hv_60") or 0),
            iv_rank=float(r.get("iv_rank") or 0),
            ret_5d=float(r.get("ret_5d") or 0),
            ret_14d=float(r.get("ret_14d") or 0),
            ema_stack=float(r.get("ema_stack") or 0),
            rsi_14=float(r.get("rsi_14") or 0),
            atr_14=float(r.get("atr_14") or 0),
            high_iv=bool(r.get("high_iv")),
            strategy_family=str(r.get("strategy_family") or "unknown"),
        )
        # restore capital if persisted
        if r.get("capital_fit"):
            sc.capital_fit = r.get("capital_fit")  # type: ignore[attr-defined]
            sc.share_lot_usd = r.get("share_lot_usd")  # type: ignore[attr-defined]
            sc.short_premium_bp_proxy = r.get("short_premium_bp_proxy")  # type: ignore[attr-defined]
            sc.long_debit_proxy = r.get("long_debit_proxy")  # type: ignore[attr-defined]
            sc.contracts_at_3k_short = r.get("contracts_at_3k_short")  # type: ignore[attr-defined]
            sc.contracts_at_5k_short = r.get("contracts_at_5k_short")  # type: ignore[attr-defined]
            sc.contracts_at_15k_short = r.get("contracts_at_15k_short")  # type: ignore[attr-defined]
            sc.contracts_at_3k_long = r.get("contracts_at_3k_long")  # type: ignore[attr-defined]
            sc.contracts_at_5k_long = r.get("contracts_at_5k_long")  # type: ignore[attr-defined]
            sc.contracts_at_15k_long = r.get("contracts_at_15k_long")  # type: ignore[attr-defined]
            sc.capital_fit_long = r.get("capital_fit_long")  # type: ignore[attr-defined]
        else:
            attach_capital_to_score(sc)
        scores.append(sc)
    return rid, scores


def promote_top_n(
    *,
    scores: Optional[Sequence[SymbolScore]] = None,
    run_id: Optional[int] = None,
    top_n: int = 5,
    sleeve_usd: Optional[float] = None,
    sleeve_mode: str = "either",
    registry: Optional[HypothesisRegistry] = None,
    registry_path: Optional[Path | str] = None,
    db_path: Optional[Path | str] = None,
    run_backtests: bool = False,
    backtest_period: str = "2y",
    backtest_max: int = 5,
    dry_run: bool = False,
) -> PromoteReport:
    """Create/ensure candidate hypotheses for top-N research symbols.

    Hard rules:
    - status is always 'candidate' (never live/shadow/paper auto-jump)
    - no place_*, no agentic arming
    """
    reg = registry or HypothesisRegistry(registry_path)
    if not dry_run:
        reg.ensure_seeded()

    rid: Optional[int] = run_id
    work: list[SymbolScore]
    if scores is not None:
        work = [s for s in scores if not getattr(s, "error", None)]
        work = sorted(work, key=lambda s: s.composite, reverse=True)
    else:
        rid, work = _scores_from_run(run_id, db_path=db_path, top_n=top_n)

    for s in work:
        if getattr(s, "capital", None) is None and not getattr(s, "capital_fit", None):
            attach_capital_to_score(s)

    if sleeve_usd is not None and sleeve_usd > 0:
        work = filter_by_sleeve(work, float(sleeve_usd), mode=sleeve_mode)

    top = work[:top_n]
    report = PromoteReport(
        run_id=rid,
        top_n=top_n,
        sleeve_usd=sleeve_usd,
        registry_path=str(reg.path),
        never_live=True,
    )

    # Optional backtest hooks (bounded)
    bt_by_sym: dict[str, BacktestHookResult] = {}
    if run_backtests and top:
        dump = Path(db_path).parent / "research_backtests" if db_path else Path(".cache/platform/research_backtests")
        # default relative to repo when using default db
        if db_path is None:
            from trader_platform.research.store import default_db_path as _ddb

            dump = _ddb().parent / "research_backtests"
        results = run_backtest_hooks(
            [s.symbol for s in top],
            period=backtest_period,
            dump_dir=dump,
            max_symbols=backtest_max,
        )
        bt_by_sym = {r.symbol: r for r in results}
        report.backtest_ran = True

    existing_ids = {h.id for h in (reg.list() if not dry_run else [])}
    if dry_run:
        # still load to detect exists without mutating
        try:
            existing_ids = {h.id for h in reg.list()}
        except Exception:  # noqa: BLE001
            existing_ids = set()

    for rank, s in enumerate(top, start=1):
        fam = s.strategy_family or "unknown"
        hid = research_hypothesis_id(s.symbol, fam)
        cap_fit = str(getattr(s, "capital_fit", "") or "unknown")
        bt = bt_by_sym.get(s.symbol)
        evidence: list[str] = []
        if rid is not None:
            evidence.append(f"research.db run_id={rid} rank={rank} composite={s.composite}")
        if bt and bt.evidence_path:
            evidence.append(bt.evidence_path)
        if bt and bt.ok:
            evidence.append(f"backtest_hook:{s.symbol}:{bt.period}:trades={bt.n_trades}")

        thesis = (
            f"Research scout ranked {s.symbol} #{rank} (composite={s.composite:.1f}, "
            f"vol={s.vol_score:.1f}, premium={s.premium_score:.1f}, alpha={s.alpha_score:.1f}). "
            f"Regime={s.regime}; family hint={fam}. "
            f"Capital fit (short CSP proxy)={cap_fit}; "
            f"spot={s.spot:.2f}; CSP_BP≈{float(getattr(s, 'short_premium_bp_proxy', 0) or 0):.0f}; "
            f"long_debit≈{float(getattr(s, 'long_debit_proxy', 0) or 0):.0f}. "
            f"PAPER CANDIDATE ONLY — not live, not an order."
        )

        item = PromoteItem(
            symbol=s.symbol,
            rank=rank,
            composite=s.composite,
            strategy_family=fam,
            capital_fit=cap_fit,
            hypothesis_id=hid,
            action="skipped",
            status="candidate",
            backtest=bt.to_dict() if bt else None,
        )

        if dry_run:
            item.action = "exists" if hid in existing_ids else "created"
            item.notes = "dry_run"
            report.items.append(item)
            continue

        if hid in existing_ids:
            item.action = "exists"
            item.notes = "idempotent — already in registry as candidate path"
            # Optionally append evidence if we have new backtest path
            if evidence:
                try:
                    h = reg.get(hid)
                    store = reg.load()
                    for i, raw in enumerate(store["hypotheses"]):
                        if raw.get("id") == hid:
                            links = list(raw.get("evidence_links") or [])
                            for e in evidence:
                                if e not in links:
                                    links.append(e)
                            raw["evidence_links"] = links
                            # never escalate status
                            if raw.get("status") == "live":
                                pass  # leave human-set live alone; still report exists
                            store["hypotheses"][i] = raw
                            reg.save(store)
                            item.status = str(raw.get("status") or h.status)
                            break
                except Exception as exc:  # noqa: BLE001
                    item.notes = f"exists; evidence update failed: {exc}"
            report.items.append(item)
            continue

        try:
            # Sleeve mapping: research short-premium families → premium; else tactical
            sleeve = "premium"
            if "stand_aside" in fam or fam == "unknown":
                sleeve = "tactical"
            h = reg.add(
                hypothesis_id=hid,
                name=f"Research: {s.symbol} {fam}",
                thesis=thesis,
                sleeve=sleeve,
                instruments=[s.symbol],
                entry_logic_ref="strategies.pick_entry",
                exit_logic_ref="strategies.check_exits",
                status="candidate",  # NEVER live
                evidence_links=evidence,
                notes=(
                    f"source=research_promote_top; capital_fit={cap_fit}; "
                    f"never_auto_live=true; research_run={rid}"
                ),
            )
            item.action = "created"
            item.status = h.status
            assert h.status == "candidate"
            existing_ids.add(hid)
        except ValueError as exc:
            # race / duplicate
            if "duplicate" in str(exc).lower():
                item.action = "exists"
            else:
                item.action = "skipped"
                item.notes = str(exc)
        report.items.append(item)

    return report


def promote_report_markdown(report: PromoteReport) -> str:
    lines = [
        "# Research promote-top (paper candidates)",
        "",
        f"- run_id: {report.run_id}",
        f"- top_n: {report.top_n}",
        f"- sleeve_usd: {report.sleeve_usd}",
        f"- registry: `{report.registry_path}`",
        f"- never_live: **{report.never_live}**",
        f"- backtest_hooks: {report.backtest_ran}",
        "",
        "| Rk | Symbol | Comp | Family | CapFit | Hypothesis | Action | BT |",
        "|---:|--------|-----:|--------|--------|------------|--------|----|",
    ]
    for i in report.items:
        bt = ""
        if i.backtest:
            if i.backtest.get("ok"):
                m = i.backtest.get("metrics") or {}
                pnl = m.get("total_pnl_per_contract", m.get("total_pnl", ""))
                bt = f"n={i.backtest.get('n_trades', 0)} pnl/c={pnl}"
            else:
                bt = f"skip:{i.backtest.get('reason', '')[:40]}"
        lines.append(
            f"| {i.rank} | {i.symbol} | {i.composite:.1f} | {i.strategy_family} | "
            f"{i.capital_fit} | `{i.hypothesis_id}` | {i.action} | {bt} |"
        )
    lines.append("")
    lines.append("Hard rule: status=`candidate` only. No live promote from this path.")
    return "\n".join(lines)
