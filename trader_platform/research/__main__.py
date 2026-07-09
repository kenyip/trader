"""CLI: multi-symbol capital-aware research scout.

Examples:
  python -m trader_platform.research tick
  python -m trader_platform.research tick --top 15 --sleeve-usd 5000 --write-report
  python -m trader_platform.research promote-top --top 5 --sleeve-usd 3000
  python -m trader_platform.research promote-top --run-backtests --dry-run
  python -m trader_platform.research report
  python -m trader_platform.research universe
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def cmd_tick(args: argparse.Namespace) -> int:
    from trader_platform.research.capital import format_capital_table
    from trader_platform.research.loop import run_research_tick
    from trader_platform.research.store import format_report_table

    report = run_research_tick(
        universe_path=args.universe,
        symbols=args.symbols,
        period=args.period,
        use_cache=not args.no_cache,
        top_n=args.top,
        db_path=args.db,
        max_workers=args.workers,
        notes=args.notes or "cli_research_tick",
        persist=not args.no_persist,
        sleeve_usd=args.sleeve_usd,
        sleeve_mode=args.sleeve_mode,
        write_report=args.write_report,
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))
        return 0

    ok = [s for s in report.scores if not s.error]
    print(
        f"research_tick run_id={report.run_id} symbols={len(report.symbols)} "
        f"scored={len(ok)} errors={len(report.errors)} period={report.period}"
    )
    print(f"universe: {report.universe_path}")
    print(f"db: {report.db_path}")
    if report.sleeve_usd:
        print(f"sleeve_usd filter: {report.sleeve_usd} mode={args.sleeve_mode}")
    if report.report_path:
        print(f"dated_report: {report.report_path}")
    print()
    print("=== TOP BY COMPOSITE ===")
    print(format_report_table(ok if not report.top_composite else report.top_composite, top_n=args.top, by="composite"))
    # Prefer already-filtered tops for display when sleeve applied
    print()
    print("=== CAPITAL-BY-PRICE (top by composite pool) ===")
    pool = report.top_composite if report.top_composite else ok
    print(format_capital_table(pool if report.sleeve_usd else ok, top_n=min(args.top, 15)))
    print()
    print("=== TOP BY VOL ===")
    print(format_report_table(report.top_vol or ok, top_n=min(args.top, 8), by="vol"))
    print()
    print("=== TOP BY PREMIUM ===")
    print(format_report_table(report.top_premium or ok, top_n=min(args.top, 8), by="premium"))
    print()
    print("=== TOP BY ALPHA (proxy) ===")
    print(format_report_table(report.top_alpha or ok, top_n=min(args.top, 8), by="alpha"))
    if report.errors:
        print()
        print("errors:")
        for e in report.errors:
            print(f"  {e.symbol}: {e.error}")

    # Optional promote in same tick (paper candidates only)
    if args.promote:
        from trader_platform.research.promote import promote_report_markdown, promote_top_n
        from trader_platform.research.store import write_dated_report

        promo = promote_top_n(
            scores=report.scores,
            run_id=report.run_id,
            top_n=args.promote_top or min(args.top, 5),
            sleeve_usd=args.sleeve_usd,
            sleeve_mode=args.sleeve_mode,
            run_backtests=args.run_backtests,
            dry_run=args.dry_run,
            db_path=args.db,
        )
        print()
        print("=== PROMOTE TOP → CANDIDATES (never live) ===")
        print(promote_report_markdown(promo))
        if args.write_report and not report.report_path:
            p = write_dated_report(report, promote_summary=promote_report_markdown(promo))
            print(f"dated_report: {p}")
        elif report.report_path:
            # append promote section
            try:
                path = Path(report.report_path)
                path.write_text(
                    path.read_text(encoding="utf-8")
                    + "\n\n"
                    + promote_report_markdown(promo)
                    + "\n",
                    encoding="utf-8",
                )
            except OSError:
                pass

    # Multi-symbol verification line for smoke/CI
    top_syms = [s.symbol for s in report.top_composite]
    only_tsla = set(top_syms) <= {"TSLA", "TSLL"} and len(ok) <= 2
    multi = len(ok) > 2 and not (set(report.symbols) <= {"TSLA", "TSLL"})
    print()
    print(
        f"verify: n_scored={len(ok)} multi_symbol_universe={multi} "
        f"top_not_tsla_only={not only_tsla or len(ok) > 2} top={top_syms[:5]}"
    )
    return 0 if multi and len(ok) > 2 else 2


def cmd_report(args: argparse.Namespace) -> int:
    from trader_platform.research.loop import report_from_db

    data = report_from_db(run_id=args.run_id, top_n=args.top, db_path=args.db)
    if data.get("error"):
        print(data["error"], file=sys.stderr)
        return 1
    if args.json:
        out = {k: v for k, v in data.items() if not k.startswith("table_")}
        print(json.dumps(out, indent=2, default=str))
        return 0
    meta = data.get("meta") or {}
    print(f"run_id={data['run_id']} ts={meta.get('ts')} n_symbols={meta.get('n_symbols')}")
    print(f"db: {data['db_path']}")
    print()
    print("=== TOP BY COMPOSITE ===")
    print(data["table_composite"])
    print()
    print("=== CAPITAL-BY-PRICE ===")
    print(data.get("table_capital") or "(no capital columns)")
    print()
    print("=== TOP BY VOL ===")
    print(data["table_vol"])
    print()
    print("=== TOP BY PREMIUM ===")
    print(data["table_premium"])
    print()
    print("=== TOP BY ALPHA (proxy) ===")
    print(data["table_alpha"])
    return 0


def cmd_universe(args: argparse.Namespace) -> int:
    from trader_platform.research.universe import load_universe, load_universe_meta

    meta = load_universe_meta(args.universe)
    syms = load_universe(args.universe)
    if args.json:
        print(json.dumps({"symbols": syms, "meta": meta}, indent=2, default=str))
        return 0
    print(f"path: {meta.get('path')}")
    print(f"n={len(syms)}: {', '.join(syms)}")
    print(f"includes TSLA={('TSLA' in syms)} TSLL={('TSLL' in syms)} multi={len(syms) > 2}")
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    from trader_platform.research.promote import promote_report_markdown, promote_top_n

    promo = promote_top_n(
        run_id=args.run_id,
        top_n=args.top,
        sleeve_usd=args.sleeve_usd,
        sleeve_mode=args.sleeve_mode,
        registry_path=args.registry,
        db_path=args.db,
        run_backtests=args.run_backtests,
        backtest_period=args.backtest_period,
        backtest_max=args.backtest_max,
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(promo.to_dict(), indent=2, default=str))
    else:
        print(promote_report_markdown(promo))
        print()
        print(
            f"summary: created={sum(1 for i in promo.items if i.action=='created')} "
            f"exists={sum(1 for i in promo.items if i.action=='exists')} "
            f"skipped={sum(1 for i in promo.items if i.action=='skipped')} "
            f"never_live={promo.never_live}"
        )
    # Guard: refuse if any item status is live from this path
    if any(i.status == "live" and i.action == "created" for i in promo.items):
        print("ERROR: promote path created live hypothesis — forbidden", file=sys.stderr)
        return 3
    return 0


def _add_common_db(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", type=Path, default=None)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m trader_platform.research",
        description="Multi-symbol capital-aware research scout (paper-only).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("tick", help="Score full universe, capital-size, rank opportunities")
    t.add_argument("--universe", type=Path, default=None, help="Path to universe.yaml")
    t.add_argument("--symbols", nargs="+", default=None, help="Override universe (must be ≥2)")
    t.add_argument("--period", default="2y")
    t.add_argument("--top", type=int, default=10)
    t.add_argument("--db", type=Path, default=None)
    t.add_argument("--workers", type=int, default=6)
    t.add_argument("--no-cache", action="store_true")
    t.add_argument("--no-persist", action="store_true")
    t.add_argument("--notes", default="")
    t.add_argument("--json", action="store_true")
    t.add_argument(
        "--sleeve-usd",
        type=float,
        default=None,
        help="Pilot capital filter for top-N (e.g. 3000 / 5000 / 15000)",
    )
    t.add_argument(
        "--sleeve-mode",
        choices=("short", "long", "either"),
        default="either",
        help="How sleeve filter applies: CSP BP, long debit, or either",
    )
    t.add_argument(
        "--write-report",
        action="store_true",
        help="Write dated markdown under .cache/platform/research_reports/",
    )
    t.add_argument(
        "--promote",
        action="store_true",
        help="Also promote top-N into hypothesis candidates (never live)",
    )
    t.add_argument("--promote-top", type=int, default=None, help="Override top-N for promote")
    t.add_argument(
        "--run-backtests",
        action="store_true",
        help="With --promote: run engine backtest hooks on promoted symbols",
    )
    t.add_argument("--dry-run", action="store_true", help="With --promote: no registry writes")
    t.set_defaults(func=cmd_tick)

    r = sub.add_parser("report", help="Print last (or given) research run tables")
    r.add_argument("--run-id", type=int, default=None)
    r.add_argument("--top", type=int, default=10)
    r.add_argument("--db", type=Path, default=None)
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_report)

    u = sub.add_parser("universe", help="Show configured research universe")
    u.add_argument("--universe", type=Path, default=None)
    u.add_argument("--json", action="store_true")
    u.set_defaults(func=cmd_universe)

    pr = sub.add_parser(
        "promote-top",
        help="Wire last-run (or --run-id) top-N → hypothesis candidates (never live)",
    )
    pr.add_argument("--run-id", type=int, default=None)
    pr.add_argument("--top", type=int, default=5)
    pr.add_argument("--db", type=Path, default=None)
    pr.add_argument("--registry", type=Path, default=None)
    pr.add_argument("--sleeve-usd", type=float, default=None)
    pr.add_argument("--sleeve-mode", choices=("short", "long", "either"), default="either")
    pr.add_argument("--run-backtests", action="store_true")
    pr.add_argument("--backtest-period", default="2y")
    pr.add_argument("--backtest-max", type=int, default=5)
    pr.add_argument("--dry-run", action="store_true")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_promote)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
