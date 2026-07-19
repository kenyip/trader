"""Named signal catalog + bar snapshots for Desk B opportunity rules.

Inventory lives in ``configs/signal_catalog.yaml``. Values come from
``data.add_features`` columns — this module does not invent new features.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import yaml

_REPO = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = _REPO / "configs" / "signal_catalog.yaml"


@dataclass(frozen=True)
class SignalDef:
    name: str
    column: str
    group: str
    units: str
    lag_safe: bool
    description: str
    source: str
    known_lie: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SignalCatalog:
    version: int
    source_module: str
    feature_builder: str
    asof_convention: str
    signals: dict[str, SignalDef]
    entry_relevant: tuple[str, ...] = ()
    path: Optional[Path] = None

    def names(self) -> frozenset[str]:
        return frozenset(self.signals.keys())

    def get(self, name: str) -> SignalDef:
        key = str(name).strip()
        if key not in self.signals:
            raise KeyError(f"unknown signal: {name!r} (not in signal catalog)")
        return self.signals[key]

    def require_lag_safe(self, name: str) -> SignalDef:
        sig = self.get(name)
        if not sig.lag_safe:
            raise ValueError(f"signal {name!r} is not lag_safe for entry use")
        return sig

    def columns(self) -> tuple[str, ...]:
        return tuple(s.column for s in self.signals.values())


@dataclass
class SignalSnapshot:
    """Timestamped feature bag for one symbol (values keyed by signal name)."""

    symbol: str
    asof: str
    values: dict[str, Any] = field(default_factory=dict)
    missing: tuple[str, ...] = ()
    catalog_version: int | None = None

    def get(self, name: str, default: Any = None) -> Any:
        return self.values.get(name, default)

    def require(self, name: str) -> Any:
        if name not in self.values:
            raise KeyError(f"signal {name!r} missing from snapshot (asof={self.asof})")
        return self.values[name]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATALOG_CACHE: SignalCatalog | None = None
_CATALOG_PATH_CACHE: Path | None = None


def load_signal_catalog(
    path: str | Path | None = None,
    *,
    reload: bool = False,
) -> SignalCatalog:
    """Load and validate the signal catalog YAML."""
    global _CATALOG_CACHE, _CATALOG_PATH_CACHE
    p = Path(path) if path else DEFAULT_CATALOG_PATH
    if (
        not reload
        and _CATALOG_CACHE is not None
        and _CATALOG_PATH_CACHE == p
    ):
        return _CATALOG_CACHE
    if not p.exists():
        raise FileNotFoundError(f"signal catalog not found: {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("signal catalog root must be a mapping")
    signals_raw = raw.get("signals") or {}
    if not isinstance(signals_raw, Mapping) or not signals_raw:
        raise ValueError("signal catalog requires non-empty 'signals' mapping")
    signals: dict[str, SignalDef] = {}
    for name, body in signals_raw.items():
        if not isinstance(body, Mapping):
            raise ValueError(f"signal {name!r} must be a mapping")
        column = str(body.get("column") or name).strip()
        if not column:
            raise ValueError(f"signal {name!r} missing column")
        signals[str(name)] = SignalDef(
            name=str(name),
            column=column,
            group=str(body.get("group") or "unknown"),
            units=str(body.get("units") or "unknown"),
            lag_safe=bool(body.get("lag_safe", True)),
            description=str(body.get("description") or ""),
            source=str(body.get("source") or "unknown"),
            known_lie=(
                None
                if body.get("known_lie") in (None, "", "null")
                else str(body.get("known_lie"))
            ),
        )
    entry = tuple(
        str(x) for x in (raw.get("entry_relevant") or []) if str(x).strip()
    )
    for name in entry:
        if name not in signals:
            raise ValueError(f"entry_relevant lists unknown signal: {name!r}")
    catalog = SignalCatalog(
        version=int(raw.get("version") or 1),
        source_module=str(raw.get("source_module") or "data"),
        feature_builder=str(raw.get("feature_builder") or "add_features"),
        asof_convention=str(raw.get("asof_convention") or "bar_close_no_lookahead"),
        signals=signals,
        entry_relevant=entry,
        path=p,
    )
    _CATALOG_CACHE = catalog
    _CATALOG_PATH_CACHE = p
    return catalog


def snapshot_from_row(
    row: Mapping[str, Any] | Any,
    *,
    symbol: str,
    asof: str,
    catalog: SignalCatalog | None = None,
    signal_names: Optional[Sequence[str]] = None,
) -> SignalSnapshot:
    """Project a feature bar into a named SignalSnapshot.

    Unknown catalog names raise. Missing columns on the row are listed in
    ``missing`` and omitted from ``values`` (callers decide strictness).
    """
    cat = catalog or load_signal_catalog()
    if signal_names is None:
        names = list(cat.signals.keys())
    else:
        names = [str(n) for n in signal_names]
        for n in names:
            cat.get(n)  # validate

    values: dict[str, Any] = {}
    missing: list[str] = []
    # Support pandas Series and plain mappings
    def _get(col: str) -> Any:
        if hasattr(row, "get"):
            return row.get(col)
        try:
            return row[col]
        except Exception:
            return None

    for name in names:
        sig = cat.get(name)
        raw = _get(sig.column)
        if raw is None:
            # pandas NA
            try:
                import pandas as pd

                if hasattr(row, "index") and sig.column in getattr(row, "index", []):
                    val = row[sig.column]
                    if pd.isna(val):
                        missing.append(name)
                        continue
                    values[name] = _normalize_value(val)
                    continue
            except Exception:
                pass
            missing.append(name)
            continue
        try:
            import pandas as pd

            if pd.isna(raw):
                missing.append(name)
                continue
        except Exception:
            pass
        values[name] = _normalize_value(raw)

    return SignalSnapshot(
        symbol=str(symbol).upper(),
        asof=str(asof),
        values=values,
        missing=tuple(missing),
        catalog_version=cat.version,
    )


def _normalize_value(raw: Any) -> Any:
    if hasattr(raw, "item"):
        try:
            return raw.item()
        except Exception:
            pass
    if isinstance(raw, (bool, int, float, str)):
        return raw
    # numpy bools/ints
    try:
        import numpy as np

        if isinstance(raw, (np.bool_,)):
            return bool(raw)
        if isinstance(raw, (np.integer,)):
            return int(raw)
        if isinstance(raw, (np.floating,)):
            return float(raw)
    except Exception:
        pass
    return raw
