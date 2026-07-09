"""Execution mode flags for the income platform."""

from __future__ import annotations

from enum import Enum


class Mode(str, Enum):
    RESEARCH = "research"
    PAPER = "paper"
    SHADOW = "shadow"
    AGENTIC_LIVE = "agentic_live"


VALID_MODES = {m.value for m in Mode}


def parse_mode(value: str) -> Mode:
    key = (value or "").strip().lower()
    if key not in VALID_MODES:
        raise ValueError(f"invalid mode {value!r}; expected one of {sorted(VALID_MODES)}")
    return Mode(key)
