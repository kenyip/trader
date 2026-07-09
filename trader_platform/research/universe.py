"""Configurable multi-symbol research universe.

Research universe ≠ live risk allowlist. Live gates stay in risk_limits.yaml;
this module only defines what symbols research may *rank*.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence

_PKG = Path(__file__).resolve().parent
_DEFAULT_YAML = _PKG / "universe.yaml"


def default_universe_path() -> Path:
    return _DEFAULT_YAML


def load_universe(
    path: Optional[Path | str] = None,
    *,
    only: Optional[Sequence[str]] = None,
) -> list[str]:
    """Load symbol list from YAML. Returns uppercase unique tickers, stable order."""
    p = Path(path) if path else _DEFAULT_YAML
    if not p.exists():
        # Hard fallback so research never collapses to TSLA-only if YAML missing.
        symbols = _FALLBACK_UNIVERSE
    else:
        symbols = _parse_yaml_symbols(p)

    out: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        u = str(s).strip().upper()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)

    if only:
        allow = {x.upper() for x in only}
        out = [s for s in out if s in allow]

    if len(out) < 2:
        raise ValueError(
            f"Research universe must have ≥2 symbols (got {out}). "
            "Do not limit research to a single name; edit universe.yaml."
        )
    return out


def load_universe_meta(path: Optional[Path | str] = None) -> dict[str, Any]:
    """Full YAML dict (symbols + groups + description) for reports."""
    p = Path(path) if path else _DEFAULT_YAML
    if not p.exists():
        return {
            "version": 0,
            "description": "fallback hard-coded universe",
            "symbols": list(_FALLBACK_UNIVERSE),
            "groups": {},
            "path": str(p),
        }
    data = _load_yaml(p)
    data["path"] = str(p)
    return data


def _parse_yaml_symbols(path: Path) -> list[str]:
    data = _load_yaml(path)
    symbols = data.get("symbols") or []
    if not isinstance(symbols, list):
        raise ValueError(f"{path}: 'symbols' must be a list")
    return [str(s) for s in symbols]


def _load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text()
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError("root must be a mapping")
        return data
    except ImportError:
        return _minimal_yaml_symbols(text)


def _minimal_yaml_symbols(text: str) -> dict[str, Any]:
    """Stdlib-only parse of the symbols: list block (no PyYAML required)."""
    symbols: list[str] = []
    in_symbols = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.strip().startswith("symbols:"):
            in_symbols = True
            continue
        if in_symbols:
            stripped = line.strip()
            # next top-level key ends the list
            if stripped and not stripped.startswith("-") and ":" in stripped and not line.startswith(" "):
                break
            if stripped.startswith("-"):
                tok = stripped[1:].strip().strip("\"'")
                if tok:
                    symbols.append(tok)
            elif stripped and not line.startswith(" ") and not line.startswith("\t"):
                break
    return {"symbols": symbols, "version": 1}


# Keep fallback multi-name if YAML deleted — never TSLA-only.
_FALLBACK_UNIVERSE = (
    "SPY",
    "QQQ",
    "IWM",
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "AMD",
    "TSLA",
    "TSLL",
    "COIN",
    "PLTR",
    "JPM",
)
