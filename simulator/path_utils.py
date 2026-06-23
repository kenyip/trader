"""Path ID helpers for simulator scenarios (avoid cross-batch collisions)."""

from __future__ import annotations
import pandas as pd


def assign_global_path_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Remap path_id to a globally unique integer per (ticker, scenario_type, local path_id)."""
    out = df.copy()
    if "path_id" not in out.columns:
        return out
    keys = ["ticker", "scenario_type", "path_id"]
    present = [k for k in keys if k in out.columns]
    if len(present) < 2:
        return out
    out["path_id"] = out.groupby(present, sort=False).ngroup().astype(int)
    return out