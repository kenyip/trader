"""Corrupt VIX cache must not kill every evolve/B3/B4/research path."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def test_load_vix_discards_glued_row_cache_and_refetches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import data as data_mod

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(data_mod, "CACHE_DIR", cache_dir)

    bad = cache_dir / "VIX_10y.csv"
    # Real failure mode: value glued to next date → 3 fields on one line.
    bad.write_text(
        "Date,vix\n"
        "2017-09-12,10.58\n"
        "2017-09-13,10.202017-09-14,10.4399995803833\n"
        "2017-09-15,10.17\n",
        encoding="utf-8",
    )

    idx = pd.to_datetime(["2017-09-12", "2017-09-13", "2017-09-14", "2017-09-15"])
    fresh = pd.DataFrame(
        {
            "Open": [10.0, 10.1, 10.2, 10.3],
            "High": [11.0, 11.1, 11.2, 11.3],
            "Low": [9.0, 9.1, 9.2, 9.3],
            "Close": [10.5, 10.6, 10.7, 10.8],
            "Volume": [1, 1, 1, 1],
        },
        index=idx,
    )

    class _YF:
        @staticmethod
        def download(*_a, **_k):
            return fresh.copy()

    monkeypatch.setattr(data_mod, "yf", _YF)
    monkeypatch.setattr(data_mod, "_should_refresh_cache", lambda _d: False)

    s = data_mod.load_vix("10y", use_cache=True)
    assert len(s) == 4
    assert float(s.iloc[0]) == pytest.approx(10.5)
    # Cache rewritten as clean 2-col series.
    rewritten = pd.read_csv(cache_dir / "VIX_10y.csv", index_col=0, parse_dates=True)
    assert rewritten.shape[1] == 1
    assert len(rewritten) == 4


def test_load_vix_returns_empty_when_refetch_also_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import data as data_mod

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(data_mod, "CACHE_DIR", cache_dir)
    (cache_dir / "VIX_10y.csv").write_text("Date,vix\nbad,line,extra\n", encoding="utf-8")

    class _YF:
        @staticmethod
        def download(*_a, **_k):
            raise RuntimeError("network down")

    monkeypatch.setattr(data_mod, "yf", _YF)
    s = data_mod.load_vix("10y", use_cache=True)
    assert len(s) == 0
    assert s.name == "vix"
