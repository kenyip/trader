"""SQLite persistence for multi-symbol research ticks (incl. capital columns)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_DB = _REPO / ".cache" / "platform" / "research.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    n_symbols INTEGER NOT NULL,
    n_scored INTEGER NOT NULL,
    n_errors INTEGER NOT NULL,
    top_n INTEGER NOT NULL,
    period TEXT,
    notes TEXT,
    meta_json TEXT
);

CREATE TABLE IF NOT EXISTS symbol_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    asof TEXT,
    spot REAL,
    regime TEXT,
    vol_score REAL,
    premium_score REAL,
    alpha_score REAL,
    composite REAL,
    hv_20 REAL,
    hv_60 REAL,
    iv_rank REAL,
    ret_5d REAL,
    ret_14d REAL,
    ema_stack REAL,
    rsi_14 REAL,
    high_iv INTEGER,
    strategy_family TEXT,
    notes_json TEXT,
    error TEXT,
    share_lot_usd REAL,
    short_premium_bp_proxy REAL,
    long_debit_proxy REAL,
    contracts_at_3k_short INTEGER,
    contracts_at_5k_short INTEGER,
    contracts_at_15k_short INTEGER,
    contracts_at_3k_long INTEGER,
    contracts_at_5k_long INTEGER,
    contracts_at_15k_long INTEGER,
    capital_fit TEXT,
    capital_fit_long TEXT,
    FOREIGN KEY (run_id) REFERENCES research_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_symbol_scores_run ON symbol_scores(run_id);
CREATE INDEX IF NOT EXISTS idx_symbol_scores_composite ON symbol_scores(run_id, composite DESC);

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    composite REAL,
    vol_score REAL,
    premium_score REAL,
    alpha_score REAL,
    regime TEXT,
    strategy_family TEXT,
    reason TEXT,
    capital_fit TEXT,
    short_premium_bp_proxy REAL,
    long_debit_proxy REAL,
    FOREIGN KEY (run_id) REFERENCES research_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_opportunities_run ON opportunities(run_id, rank);
"""

# Columns added after first research.db ships — migrate on connect
_SYMBOL_SCORE_EXTRAS = [
    ("share_lot_usd", "REAL"),
    ("short_premium_bp_proxy", "REAL"),
    ("long_debit_proxy", "REAL"),
    ("contracts_at_3k_short", "INTEGER"),
    ("contracts_at_5k_short", "INTEGER"),
    ("contracts_at_15k_short", "INTEGER"),
    ("contracts_at_3k_long", "INTEGER"),
    ("contracts_at_5k_long", "INTEGER"),
    ("contracts_at_15k_long", "INTEGER"),
    ("capital_fit", "TEXT"),
    ("capital_fit_long", "TEXT"),
    ("atr_14", "REAL"),
]

_OPP_EXTRAS = [
    ("capital_fit", "TEXT"),
    ("short_premium_bp_proxy", "REAL"),
    ("long_debit_proxy", "REAL"),
]


def default_db_path() -> Path:
    return _DEFAULT_DB


def default_reports_dir() -> Path:
    return _REPO / ".cache" / "platform" / "research_reports"


def connect(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else _DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    def cols(table: str) -> set[str]:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    sc = cols("symbol_scores")
    for name, typ in _SYMBOL_SCORE_EXTRAS:
        if name not in sc:
            conn.execute(f"ALTER TABLE symbol_scores ADD COLUMN {name} {typ}")
    oc = cols("opportunities")
    for name, typ in _OPP_EXTRAS:
        if name not in oc:
            conn.execute(f"ALTER TABLE opportunities ADD COLUMN {name} {typ}")
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def save_run(
    scores: Sequence[Any],
    *,
    top_n: int = 10,
    period: str = "2y",
    notes: str = "",
    meta: Optional[dict[str, Any]] = None,
    db_path: Optional[Path | str] = None,
) -> int:
    """Persist a research tick. Returns run_id."""
    scored = [s for s in scores if getattr(s, "error", None) is None]
    errors = [s for s in scores if getattr(s, "error", None) is not None]
    ranked = sorted(scored, key=lambda s: s.composite, reverse=True)

    conn = connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO research_runs (ts, n_symbols, n_scored, n_errors, top_n, period, notes, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now(),
                len(scores),
                len(scored),
                len(errors),
                top_n,
                period,
                notes,
                json.dumps(meta or {}, default=str),
            ),
        )
        run_id = int(cur.lastrowid)

        for s in scores:
            conn.execute(
                """
                INSERT INTO symbol_scores (
                    run_id, symbol, asof, spot, regime,
                    vol_score, premium_score, alpha_score, composite,
                    hv_20, hv_60, iv_rank, ret_5d, ret_14d, ema_stack, rsi_14,
                    high_iv, strategy_family, notes_json, error,
                    share_lot_usd, short_premium_bp_proxy, long_debit_proxy,
                    contracts_at_3k_short, contracts_at_5k_short, contracts_at_15k_short,
                    contracts_at_3k_long, contracts_at_5k_long, contracts_at_15k_long,
                    capital_fit, capital_fit_long, atr_14
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id,
                    s.symbol,
                    s.asof,
                    s.spot,
                    s.regime,
                    s.vol_score,
                    s.premium_score,
                    s.alpha_score,
                    s.composite,
                    s.hv_20,
                    s.hv_60,
                    s.iv_rank,
                    s.ret_5d,
                    s.ret_14d,
                    s.ema_stack,
                    s.rsi_14,
                    1 if s.high_iv else 0,
                    s.strategy_family,
                    json.dumps(list(s.notes or [])),
                    s.error,
                    float(getattr(s, "share_lot_usd", 0) or 0),
                    float(getattr(s, "short_premium_bp_proxy", 0) or 0),
                    float(getattr(s, "long_debit_proxy", 0) or 0),
                    int(getattr(s, "contracts_at_3k_short", 0) or 0),
                    int(getattr(s, "contracts_at_5k_short", 0) or 0),
                    int(getattr(s, "contracts_at_15k_short", 0) or 0),
                    int(getattr(s, "contracts_at_3k_long", 0) or 0),
                    int(getattr(s, "contracts_at_5k_long", 0) or 0),
                    int(getattr(s, "contracts_at_15k_long", 0) or 0),
                    str(getattr(s, "capital_fit", "") or ""),
                    str(getattr(s, "capital_fit_long", "") or ""),
                    float(getattr(s, "atr_14", 0) or 0),
                ),
            )

        for rank, s in enumerate(ranked[:top_n], start=1):
            reason_parts = [
                f"composite={s.composite:.1f}",
                f"vol={s.vol_score:.1f}",
                f"premium={s.premium_score:.1f}",
                f"alpha={s.alpha_score:.1f}",
                f"regime={s.regime}",
                f"family={s.strategy_family}",
                f"capital_fit={getattr(s, 'capital_fit', '')}",
                f"csp_bp={float(getattr(s, 'short_premium_bp_proxy', 0) or 0):.0f}",
            ]
            if s.notes:
                reason_parts.append("notes=" + ",".join(s.notes))
            conn.execute(
                """
                INSERT INTO opportunities (
                    run_id, rank, symbol, composite, vol_score, premium_score, alpha_score,
                    regime, strategy_family, reason,
                    capital_fit, short_premium_bp_proxy, long_debit_proxy
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id,
                    rank,
                    s.symbol,
                    s.composite,
                    s.vol_score,
                    s.premium_score,
                    s.alpha_score,
                    s.regime,
                    s.strategy_family,
                    " | ".join(reason_parts),
                    str(getattr(s, "capital_fit", "") or ""),
                    float(getattr(s, "short_premium_bp_proxy", 0) or 0),
                    float(getattr(s, "long_debit_proxy", 0) or 0),
                ),
            )
        conn.commit()
        return run_id
    finally:
        conn.close()


def latest_run_id(db_path: Optional[Path | str] = None) -> Optional[int]:
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT id FROM research_runs ORDER BY id DESC LIMIT 1").fetchone()
        return int(row["id"]) if row else None
    finally:
        conn.close()


def load_run_scores(run_id: int, db_path: Optional[Path | str] = None) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT * FROM symbol_scores WHERE run_id = ? ORDER BY composite DESC
            """,
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def load_opportunities(run_id: int, db_path: Optional[Path | str] = None) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT * FROM opportunities WHERE run_id = ? ORDER BY rank ASC
            """,
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def load_run_meta(run_id: int, db_path: Optional[Path | str] = None) -> Optional[dict[str, Any]]:
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def format_report_table(
    scores: Sequence[dict[str, Any]] | Sequence[Any],
    *,
    top_n: int = 10,
    by: str = "composite",
) -> str:
    """Markdown-ish table for CLI / artifact."""
    rows: list[dict[str, Any]] = []
    for s in scores:
        if hasattr(s, "to_dict"):
            d = s.to_dict()
        elif isinstance(s, dict):
            d = s
        else:
            d = {
                "symbol": getattr(s, "symbol", "?"),
                "composite": getattr(s, "composite", 0),
                "vol_score": getattr(s, "vol_score", 0),
                "premium_score": getattr(s, "premium_score", 0),
                "alpha_score": getattr(s, "alpha_score", 0),
                "regime": getattr(s, "regime", ""),
                "strategy_family": getattr(s, "strategy_family", ""),
                "iv_rank": getattr(s, "iv_rank", 0),
                "capital_fit": getattr(s, "capital_fit", ""),
                "spot": getattr(s, "spot", 0),
                "error": getattr(s, "error", None),
            }
        if d.get("error"):
            continue
        rows.append(d)

    key = by if by in ("composite", "vol_score", "premium_score", "alpha_score") else "composite"
    key_map = {"vol": "vol_score", "premium": "premium_score", "alpha": "alpha_score"}
    key = key_map.get(by, key)
    rows.sort(key=lambda r: float(r.get(key) or 0), reverse=True)
    rows = rows[:top_n]

    header = (
        f"{'Rk':>3}  {'Symbol':<6}  {'Comp':>6}  {'Vol':>6}  {'Prem':>6}  "
        f"{'Alpha':>6}  {'IVR':>5}  {'Spot':>8}  {'FitS':<10}  {'Regime':<8}  Family"
    )
    lines = [header, "-" * len(header)]
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"{i:>3}  {str(r.get('symbol','')):<6}  "
            f"{float(r.get('composite') or 0):6.1f}  "
            f"{float(r.get('vol_score') or 0):6.1f}  "
            f"{float(r.get('premium_score') or 0):6.1f}  "
            f"{float(r.get('alpha_score') or 0):6.1f}  "
            f"{float(r.get('iv_rank') or 0):5.1f}  "
            f"{float(r.get('spot') or 0):8.2f}  "
            f"{str(r.get('capital_fit') or ''):<10}  "
            f"{str(r.get('regime') or ''):<8}  "
            f"{r.get('strategy_family') or ''}"
        )
    return "\n".join(lines)


def write_dated_report(
    report: Any,
    *,
    reports_dir: Optional[Path | str] = None,
    promote_summary: Optional[str] = None,
) -> Path:
    """Write a markdown research report under .cache/platform/research_reports/."""
    from trader_platform.research.capital import format_capital_table

    out_dir = Path(reports_dir) if reports_dir else default_reports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rid = getattr(report, "run_id", 0) or 0
    path = out_dir / f"{day}_run{rid}.md"

    ok = [s for s in report.scores if not s.error]
    lines = [
        f"# Research tick report — {day} run_id={rid}",
        "",
        f"- period: `{report.period}`",
        f"- universe: `{report.universe_path}`",
        f"- db: `{report.db_path}`",
        f"- symbols: {len(report.symbols)} scored_ok={len(ok)} errors={len(report.errors)}",
        f"- paper_only: **true** (no trading / no place_* / no agentic arming)",
        "",
        "## Top by composite",
        "",
        "```",
        format_report_table(ok, top_n=getattr(report, "top_n_used", 10) or 10, by="composite"),
        "```",
        "",
        "## Capital-by-price sizing",
        "",
        "```",
        format_capital_table(ok, top_n=15),
        "```",
        "",
        "Proxies: CSP_BP ≈ 0.95 × 100 × spot; long debit ≈ max(2%×spot×100, 0.5×ATR×100).",
        "",
        "## Top symbols",
        "",
    ]
    for i, s in enumerate(report.top_composite, start=1):
        lines.append(
            f"{i}. **{s.symbol}** composite={s.composite:.1f} fit={getattr(s, 'capital_fit', '')} "
            f"spot={s.spot:.2f} family={s.strategy_family}"
        )
    if promote_summary:
        lines.extend(["", "## Promote", "", promote_summary, ""])
    if report.errors:
        lines.extend(["", "## Errors", ""])
        for e in report.errors:
            lines.append(f"- {e.symbol}: {e.error}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
