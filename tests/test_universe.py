"""Discovery universe add/remove/status."""

from __future__ import annotations

import json
from pathlib import Path

from trader_platform.research.discovery_universe import (
    active_symbols,
    add_symbol,
    load_discovery_universe,
    remove_symbol,
    resolve_discovery_symbols,
    set_status,
    summary,
)


def test_discovery_universe_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "u.json"
    path.write_text(
        json.dumps(
            {
                "symbols": {
                    "AAA": {"status": "active", "tags": ["core"], "notes": ""},
                    "BBB": {"status": "watch", "tags": ["high_vol"], "notes": ""},
                }
            }
        ),
        encoding="utf-8",
    )
    assert active_symbols(path) == ["AAA"]
    add_symbol("ccc", tags=["ai_growth"], path=path)
    assert "CCC" in active_symbols(path)
    set_status("AAA", "demoted", path=path)
    assert "AAA" not in active_symbols(path)
    remove_symbol("CCC", hard=True, path=path)
    assert "CCC" not in load_discovery_universe(path)["symbols"]
    s = summary(path)
    assert s["n_active"] == 0
    assert "BBB" in s["by_status"]["watch"]


def test_resolve_precedence(tmp_path: Path) -> None:
    path = tmp_path / "u.json"
    path.write_text(
        json.dumps({"symbols": {"TSLA": {"status": "active", "tags": [], "notes": ""}}}),
        encoding="utf-8",
    )
    assert resolve_discovery_symbols(["KO"], path=path) == ["KO"]
    assert resolve_discovery_symbols(None, path=path) == ["TSLA"]
    assert resolve_discovery_symbols(
        None, use_universe=False, seed_symbols=["BAC", "F"], path=path
    ) == ["BAC", "F"]


def test_legacy_research_universe_still_loads() -> None:
    """Do not break paper research scout universe.yaml loader."""
    from trader_platform.research.universe import default_universe_path, load_universe

    names = load_universe()
    assert len(names) >= 2
    assert default_universe_path().name == "universe.yaml"
    # Preferred cold defensive names must stay research-visible (2026-08-07 coach).
    assert "KO" in names
    assert "INTC" in names
