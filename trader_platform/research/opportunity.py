"""Opportunity layer: thesis rules → Opportunity | StandAside → structure plans.

Engine contract: config drives decisions. This module never places orders.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

import yaml

from trader_platform.research.regime_router_sim import select_structure
from trader_platform.research.signals import (
    SignalCatalog,
    SignalSnapshot,
    load_signal_catalog,
    snapshot_from_row,
)
from trader_platform.research.strategy_spec import (
    StrategySpec,
    strategy_spec_from_mapping,
)

try:
    from trader_platform.research.pcs_sim import entry_filters_pass
except Exception:  # pragma: no cover
    entry_filters_pass = None  # type: ignore[assignment]

_REPO = Path(__file__).resolve().parents[2]
DEFAULT_THESIS_DIR = _REPO / "configs" / "theses"

STRUCTURE_NAMES = frozenset(
    {"put_credit_spread", "call_credit_spread", "iron_condor"}
)


@dataclass(frozen=True)
class StandAside:
    thesis_id: str
    symbol: str
    asof: str
    reason: str
    rule_hits: tuple[str, ...] = ()

    @property
    def is_opportunity(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "decision": "stand_aside"}


@dataclass(frozen=True)
class Opportunity:
    thesis_id: str
    symbol: str
    asof: str
    regime: str
    structure: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    rule_hits: tuple[str, ...] = ()

    @property
    def is_opportunity(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "decision": "opportunity"}


Decision = Union[Opportunity, StandAside]


@dataclass(frozen=True)
class StructurePlan:
    structure: str
    expiration_rule: dict[str, Any] = field(default_factory=dict)
    strike_rule: dict[str, Any] = field(default_factory=dict)
    entry_premium_rule: dict[str, Any] = field(default_factory=dict)
    max_loss_usd: float = 300.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ManagementPlan:
    profit_target: float | None = None
    defined_loss_exit_frac: float | None = None
    dte_stop: int | None = None
    delta_breach: float | None = None
    regime_flip_exit_enabled: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        raw = d.pop("raw", {}) or {}
        return {**raw, **{k: v for k, v in d.items() if v is not None and k != "raw"}}


@dataclass
class Thesis:
    """Executable claim: opportunity rules + structure/manage defaults."""

    thesis_id: str
    forecast_type: str = ""
    economic_mechanism: str = ""
    symbols: tuple[str, ...] = ()
    router_policy: str = "pcs_non_bear"
    # Optional explicit regime allow-list (if empty, router_policy decides)
    regime_allow: tuple[str, ...] = ()
    regime_deny: tuple[str, ...] = ()
    # Signal bounds: {signal_name: {min?: float, max?: float}}
    signal_bounds: dict[str, dict[str, float]] = field(default_factory=dict)
    # Extra entry-filter keys compatible with pcs_sim.entry_filters_pass
    entry: dict[str, Any] = field(default_factory=dict)
    management: dict[str, Any] = field(default_factory=dict)
    structure_defaults: dict[str, Any] = field(default_factory=dict)
    max_structures: int = 1
    discovery_gates: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    # Optional path / family bridge
    family_id: str = ""
    source_spec_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "thesis_id": self.thesis_id,
            "family_id": self.family_id,
            "forecast_type": self.forecast_type,
            "economic_mechanism": self.economic_mechanism,
            "symbols": list(self.symbols),
            "router_policy": self.router_policy,
            "regime_allow": list(self.regime_allow),
            "regime_deny": list(self.regime_deny),
            "signal_bounds": dict(self.signal_bounds),
            "entry": dict(self.entry),
            "management": dict(self.management),
            "structure_defaults": dict(self.structure_defaults),
            "max_structures": int(self.max_structures),
            "discovery_gates": dict(self.discovery_gates),
            "notes": self.notes,
            "source_spec_path": self.source_spec_path,
        }


def thesis_from_mapping(raw: Mapping[str, Any]) -> Thesis:
    data = dict(raw)
    thesis_id = str(data.get("thesis_id") or data.get("candidate_id") or "").strip()
    if not thesis_id:
        raise ValueError("thesis_id required")
    symbols = tuple(
        str(s).strip().upper()
        for s in (data.get("symbols") or [])
        if str(s).strip()
    )
    bounds_raw = data.get("signal_bounds") or data.get("opportunity_signal_bounds") or {}
    if not isinstance(bounds_raw, Mapping):
        raise ValueError("signal_bounds must be a mapping")
    bounds: dict[str, dict[str, float]] = {}
    for sig, body in bounds_raw.items():
        if not isinstance(body, Mapping):
            raise ValueError(f"signal_bounds[{sig!r}] must be a mapping")
        item: dict[str, float] = {}
        if "min" in body:
            item["min"] = float(body["min"])
        if "max" in body:
            item["max"] = float(body["max"])
        bounds[str(sig)] = item

    regime_allow = tuple(
        str(x).lower() for x in (data.get("regime_allow") or []) if str(x).strip()
    )
    regime_deny = tuple(
        str(x).lower() for x in (data.get("regime_deny") or []) if str(x).strip()
    )
    max_structures = int(data.get("max_structures") or 1)
    if max_structures < 1 or max_structures > 3:
        raise ValueError("max_structures must be in 1..3")

    return Thesis(
        thesis_id=thesis_id,
        forecast_type=str(data.get("forecast_type") or ""),
        economic_mechanism=str(data.get("economic_mechanism") or ""),
        symbols=symbols,
        router_policy=str(data.get("router_policy") or "pcs_non_bear").strip().lower(),
        regime_allow=regime_allow,
        regime_deny=regime_deny,
        signal_bounds=bounds,
        entry=dict(data.get("entry") or {}),
        management=dict(data.get("management") or {}),
        structure_defaults=dict(data.get("structure_defaults") or data.get("structure") or {}),
        max_structures=max_structures,
        discovery_gates=dict(data.get("discovery_gates") or {}),
        notes=str(data.get("notes") or ""),
        family_id=str(data.get("family_id") or ""),
        source_spec_path=str(data.get("source_spec_path") or ""),
    )


def load_thesis(path: str | Path) -> Thesis:
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"thesis file must be a mapping: {p}")
    thesis = thesis_from_mapping(raw)
    if not thesis.source_spec_path:
        thesis.source_spec_path = str(p)
    return thesis


def list_thesis_paths(directory: str | Path | None = None) -> list[Path]:
    d = Path(directory) if directory else DEFAULT_THESIS_DIR
    if not d.exists():
        return []
    return sorted(list(d.glob("*.yaml")) + list(d.glob("*.yml")))


def thesis_from_strategy_spec(spec: StrategySpec, *, thesis_id: str | None = None) -> Thesis:
    """Bridge living StrategySpec seats into the opportunity emitter.

    Mechanical mapping only — does not invent new edge rules.
    """
    mgmt = dict(spec.management or {})
    entry = dict(spec.entry or {})
    bounds: dict[str, dict[str, float]] = {}
    if "iv_rank_min" in mgmt:
        bounds["iv_rank"] = {"min": float(mgmt["iv_rank_min"])}
    if "iv_rank_max" in mgmt:
        bounds.setdefault("iv_rank", {})["max"] = float(mgmt["iv_rank_max"])

    # Prefer explicit structure when single_structure mode
    structure_defaults: dict[str, Any] = {}
    if spec.evaluation_mode == "single_structure" and spec.structure:
        structure_defaults["structure"] = spec.structure

    return Thesis(
        thesis_id=thesis_id or spec.candidate_id,
        forecast_type=spec.forecast_type,
        economic_mechanism=spec.economic_mechanism,
        symbols=tuple(spec.symbols),
        router_policy=str(spec.router_policy or "pcs_non_bear").lower(),
        signal_bounds=bounds,
        entry=entry,
        management=mgmt,
        structure_defaults=structure_defaults,
        max_structures=1,
        discovery_gates=spec.discovery_gates.to_dict(),
        notes=spec.notes,
        family_id=spec.family_id,
    )


def _row_from_snapshot(snap: SignalSnapshot) -> Any:
    import pandas as pd

    return pd.Series(dict(snap.values))


def _check_signal_bounds(
    thesis: Thesis, snap: SignalSnapshot, catalog: SignalCatalog
) -> tuple[bool, list[str]]:
    hits: list[str] = []
    for name, bound in (thesis.signal_bounds or {}).items():
        catalog.get(name)  # must be catalogued
        if name in snap.missing or name not in snap.values:
            hits.append(f"missing:{name}")
            return False, hits
        try:
            val = float(snap.values[name])
        except (TypeError, ValueError):
            hits.append(f"non_numeric:{name}")
            return False, hits
        if "min" in bound and val < float(bound["min"]):
            hits.append(f"{name}<{bound['min']}")
            return False, hits
        if "max" in bound and val > float(bound["max"]):
            hits.append(f"{name}>{bound['max']}")
            return False, hits
        hits.append(f"{name}_ok")
    return True, hits


def evaluate_opportunity(
    thesis: Thesis,
    snap: SignalSnapshot,
    *,
    catalog: SignalCatalog | None = None,
) -> Decision:
    """Apply thesis rules to a signal snapshot. Never places orders."""
    cat = catalog or load_signal_catalog()
    regime = str(snap.get("regime") or "unknown").lower()
    hits: list[str] = []

    if thesis.regime_deny and regime in thesis.regime_deny:
        return StandAside(
            thesis_id=thesis.thesis_id,
            symbol=snap.symbol,
            asof=snap.asof,
            reason=f"regime_deny:{regime}",
            rule_hits=tuple(hits + [f"deny:{regime}"]),
        )
    if thesis.regime_allow and regime not in thesis.regime_allow:
        return StandAside(
            thesis_id=thesis.thesis_id,
            symbol=snap.symbol,
            asof=snap.asof,
            reason=f"regime_not_allowed:{regime}",
            rule_hits=tuple(hits + [f"allow_miss:{regime}"]),
        )

    ok_bounds, bound_hits = _check_signal_bounds(thesis, snap, cat)
    hits.extend(bound_hits)
    if not ok_bounds:
        return StandAside(
            thesis_id=thesis.thesis_id,
            symbol=snap.symbol,
            asof=snap.asof,
            reason="signal_bounds_failed",
            rule_hits=tuple(hits),
        )

    # Build a cfg for entry filters + iv_rank (pcs_sim style)
    cfg: dict[str, Any] = {}
    cfg.update(dict(thesis.management or {}))
    cfg.update(dict(thesis.entry or {}))
    row = _row_from_snapshot(snap)

    if entry_filters_pass is not None and (thesis.entry or any(
        k.startswith("entry_") for k in cfg
    )):
        if not entry_filters_pass(row, cfg):
            return StandAside(
                thesis_id=thesis.thesis_id,
                symbol=snap.symbol,
                asof=snap.asof,
                reason="entry_filters_failed",
                rule_hits=tuple(hits + ["entry_filters"]),
            )
        hits.append("entry_filters_ok")

    # iv_rank_min already in signal_bounds when bridged; also honor cfg key
    if "iv_rank_min" in cfg and "iv_rank" not in (thesis.signal_bounds or {}):
        try:
            iv = float(snap.get("iv_rank"))
        except (TypeError, ValueError):
            return StandAside(
                thesis_id=thesis.thesis_id,
                symbol=snap.symbol,
                asof=snap.asof,
                reason="iv_rank_missing",
                rule_hits=tuple(hits + ["iv_rank_missing"]),
            )
        if iv < float(cfg["iv_rank_min"]):
            return StandAside(
                thesis_id=thesis.thesis_id,
                symbol=snap.symbol,
                asof=snap.asof,
                reason=f"iv_rank<{cfg['iv_rank_min']}",
                rule_hits=tuple(hits + [f"iv_rank<{cfg['iv_rank_min']}"]),
            )
        hits.append("iv_rank_min_ok")

    # Structure via router policy (same as regime_router_sim)
    configs = {
        "put_credit_spread": dict(cfg),
        "call_credit_spread": dict(cfg),
        "iron_condor": dict(cfg),
    }
    # seed iron_condor iv threshold if present
    if "iv_rank_min" in cfg:
        configs["iron_condor"].setdefault("iv_rank_min", cfg["iv_rank_min"])

    forced = str((thesis.structure_defaults or {}).get("structure") or "").strip().lower()
    if forced:
        if forced not in STRUCTURE_NAMES:
            raise ValueError(f"invalid structure in thesis defaults: {forced!r}")
        # still respect simple regime gates for forced single structure
        if forced == "put_credit_spread" and regime == "bearish":
            structure = None
        elif forced == "call_credit_spread" and regime == "bullish":
            structure = None
        else:
            structure = forced
    else:
        structure = select_structure(row, configs, policy=thesis.router_policy)

    if not structure:
        return StandAside(
            thesis_id=thesis.thesis_id,
            symbol=snap.symbol,
            asof=snap.asof,
            reason=f"router_stand_aside:{thesis.router_policy}:{regime}",
            rule_hits=tuple(hits + ["router_none"]),
        )

    return Opportunity(
        thesis_id=thesis.thesis_id,
        symbol=snap.symbol,
        asof=snap.asof,
        regime=regime,
        structure=structure,
        reason=f"setup:{structure}:{regime}",
        evidence={
            "iv_rank": snap.get("iv_rank"),
            "regime": regime,
            "router_policy": thesis.router_policy,
        },
        rule_hits=tuple(hits + [f"structure:{structure}"]),
    )


def plan_structures(
    decision: Decision,
    thesis: Thesis,
) -> list[StructurePlan]:
    """Build 0–N structure plans. Stand-aside → empty list."""
    if isinstance(decision, StandAside) or not decision.is_opportunity:
        return []
    assert isinstance(decision, Opportunity)
    mgmt = dict(thesis.management or {})
    entry = dict(thesis.entry or {})
    max_loss = float(mgmt.get("max_loss_budget_usd") or 300.0)
    plan = StructurePlan(
        structure=decision.structure,
        expiration_rule={
            "long_dte": mgmt.get("long_dte"),
            "dte_stop": mgmt.get("dte_stop"),
        },
        strike_rule={
            "long_target_delta": mgmt.get("long_target_delta"),
            "spread_width": mgmt.get("spread_width"),
            "delta_breach": mgmt.get("delta_breach"),
        },
        entry_premium_rule={
            "min_credit_pct": mgmt.get("min_credit_pct"),
            **{k: v for k, v in entry.items() if k.startswith("entry_")},
        },
        max_loss_usd=max_loss,
        notes=thesis.notes[:200] if thesis.notes else "",
    )
    n = max(1, min(3, int(thesis.max_structures)))
    return [plan][:n]


def management_plan_from_thesis(thesis: Thesis) -> ManagementPlan:
    mgmt = dict(thesis.management or {})
    return ManagementPlan(
        profit_target=mgmt.get("profit_target"),
        defined_loss_exit_frac=mgmt.get("defined_loss_exit_frac"),
        dte_stop=mgmt.get("dte_stop"),
        delta_breach=mgmt.get("delta_breach"),
        regime_flip_exit_enabled=mgmt.get("regime_flip_exit_enabled"),
        raw=mgmt,
    )


def strategy_spec_from_thesis(
    thesis: Thesis,
    *,
    symbols: Optional[Sequence[str]] = None,
    candidate_id: str | None = None,
    evaluation_mode: str = "regime_router",
) -> StrategySpec:
    """Serialize thesis DNA into a StrategySpec for evaluate_proxy."""
    syms = tuple(str(s).upper() for s in (symbols or thesis.symbols or ()))
    if not syms:
        raise ValueError("symbols required to build StrategySpec from thesis")
    raw: dict[str, Any] = {
        "candidate_id": candidate_id or thesis.thesis_id,
        "family_id": thesis.family_id or thesis.thesis_id,
        "evaluation_mode": evaluation_mode,
        "forecast_type": thesis.forecast_type or "unspecified",
        "economic_mechanism": thesis.economic_mechanism or "unspecified",
        "symbols": list(syms),
        "router_policy": thesis.router_policy,
        "management": dict(thesis.management),
        "entry": dict(thesis.entry),
        "discovery_gates": dict(thesis.discovery_gates),
        "notes": thesis.notes,
    }
    forced = str((thesis.structure_defaults or {}).get("structure") or "").strip()
    if forced and evaluation_mode == "single_structure":
        raw["structure"] = forced
    return strategy_spec_from_mapping(raw)


def evaluate_from_row(
    thesis: Thesis,
    row: Mapping[str, Any] | Any,
    *,
    symbol: str,
    asof: str,
    catalog: SignalCatalog | None = None,
) -> Decision:
    cat = catalog or load_signal_catalog()
    names = list(cat.entry_relevant) + ["regime", "iv_rank", "close"]
    # include bound signals
    names.extend(thesis.signal_bounds.keys())
    # unique preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for n in names:
        if n in cat.names() and n not in seen:
            seen.add(n)
            ordered.append(n)
    snap = snapshot_from_row(
        row, symbol=symbol, asof=asof, catalog=cat, signal_names=ordered
    )
    return evaluate_opportunity(thesis, snap, catalog=cat)
