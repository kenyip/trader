"""Promotion criteria checklist. Structure is real; deep gauntlet wiring has TODOs.

No auto-promote to live without an evidence record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from platform.hypothesis_registry import Hypothesis, HypothesisRegistry


@dataclass
class GateItem:
    id: str
    description: str
    required_for: tuple[str, ...]  # statuses that require this gate
    status: str = "todo"  # todo | pass | fail | skip
    detail: str = ""


@dataclass
class PromotionReport:
    hypothesis_id: str
    target_status: str
    allowed: bool
    items: list[GateItem] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "target_status": self.target_status,
            "allowed": self.allowed,
            "blockers": list(self.blockers),
            "items": [
                {
                    "id": i.id,
                    "description": i.description,
                    "required_for": list(i.required_for),
                    "status": i.status,
                    "detail": i.detail,
                }
                for i in self.items
            ],
        }


def default_checklist() -> list[GateItem]:
    return [
        GateItem(
            id="walk_forward",
            description="Walk-forward / OOS validation recorded (just optimize --static or equivalent)",
            required_for=("shadow", "live"),
        ),
        GateItem(
            id="scenarios",
            description="12-regime scenario suite green or documented tradeoffs (just scenarios)",
            required_for=("paper", "shadow", "live"),
        ),
        GateItem(
            id="costs",
            description="Costs/slippage assumptions stated; no free-lunch claim",
            required_for=("shadow", "live"),
        ),
        GateItem(
            id="drawdown",
            description="Drawdown / catastrophe threshold respected (cost function)",
            required_for=("shadow", "live"),
        ),
        GateItem(
            id="evidence_record",
            description="At least one evidence_links entry pointing to report or doc",
            required_for=("live",),
        ),
        GateItem(
            id="null_results_logged",
            description="Competing falsifications / nulls logged so we don't re-propose",
            required_for=("live",),
        ),
        GateItem(
            id="risk_envelope",
            description="Fits risk_limits.yaml (size, instruments, strategy allowlist)",
            required_for=("paper", "shadow", "live"),
        ),
        GateItem(
            id="human_arm_live",
            description="Human Stage1 OAuth + agentic_live arming (not automatic)",
            required_for=("live",),
        ),
    ]


def evaluate_promotion(
    hyp: Hypothesis,
    target_status: str,
    *,
    checklist: Optional[list[GateItem]] = None,
    # Manual evidence overrides for M0–M1 stubs — pass True when operator attaches results.
    overrides: Optional[dict[str, str]] = None,
) -> PromotionReport:
    """Evaluate whether hyp may move to target_status.

    M0–M1: without overrides, evidence_record is the only auto-check from registry data.
    Other gates remain status='todo' and block live/shadow until filled.
    TODO: wire walk_forward / scenarios by calling existing validate_rule / run_scenarios entry points.
    """
    items = checklist or default_checklist()
    overrides = overrides or {}
    blockers: list[str] = []

    for item in items:
        if item.id in overrides:
            item.status = overrides[item.id]
            continue
        if item.id == "evidence_record":
            if hyp.evidence_links:
                item.status = "pass"
                item.detail = f"{len(hyp.evidence_links)} link(s)"
            else:
                item.status = "fail"
                item.detail = "no evidence_links"
        elif item.id == "null_results_logged":
            # Optional but preferred for live; pass if any, else todo (not hard fail yet).
            item.status = "pass" if hyp.null_results else "todo"
            item.detail = f"{len(hyp.null_results)} null(s)" if hyp.null_results else "none yet"
        elif item.id == "human_arm_live":
            item.status = "todo"
            item.detail = "requires Ken Stage1 arming on Mac"
        else:
            item.status = "todo"
            item.detail = "TODO: wire automated check"

    for item in items:
        if target_status not in item.required_for:
            continue
        if item.status == "fail":
            blockers.append(f"{item.id}: {item.detail or item.description}")
        elif item.status == "todo" and target_status == "live":
            # Live requires explicit pass/skip on required gates (no silent auto-promote).
            blockers.append(f"{item.id}: incomplete ({item.detail or 'todo'})")

    if target_status == "live" and not hyp.evidence_links and "evidence_record" not in {
        b.split(":")[0] for b in blockers
    }:
        blockers.append("evidence_record: required for live")

    allowed = len(blockers) == 0
    # Paper/testing can proceed with todos remaining (research freedom).
    if target_status in ("candidate", "testing", "paper", "retired", "rejected"):
        hard = [b for b in blockers if b.startswith("evidence_record") and target_status == "live"]
        # Only hard-fail on explicit fails for non-live targets
        hard = [b for b in blockers if ": " in b and "incomplete" not in b]
        # For paper, only evidence is not required; scenarios todo is OK
        if target_status != "live":
            allowed = not any(i.status == "fail" and target_status in i.required_for for i in items)
            blockers = [
                f"{i.id}: {i.detail or i.description}"
                for i in items
                if i.status == "fail" and target_status in i.required_for
            ]

    return PromotionReport(
        hypothesis_id=hyp.id,
        target_status=target_status,
        allowed=allowed,
        items=items,
        blockers=blockers,
    )


def can_promote(
    registry: HypothesisRegistry,
    hypothesis_id: str,
    target_status: str,
    **kwargs: Any,
) -> PromotionReport:
    hyp = registry.get(hypothesis_id)
    return evaluate_promotion(hyp, target_status, **kwargs)
